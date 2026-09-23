"""Auswertung: eine Instanz mit allen drei Ausprägungen (reaktiv/eingestellt/voll), Stichprobe über
viele Instanzen, Kosten-über-k-Kurve, gepaarte Differenz, Urteil, Diagnose (bedingte Meldung).

Reine Rechnung ohne Streamlit. "Kosten" ist immer die Gesamtkosten (Transport + Halten + Notleasing);
alle Vergleiche sind gepaart (dieselbe Instanz), Unterschied = Ausprägung minus Referenz "rein
reaktiv" bzw. minus Optimum, negativ = besser (weniger Kosten)."""
import math
import statistics
from dataclasses import dataclass
from typing import NamedTuple

import lcr_constants as C
import lcr_rolling as RL
import lcr_scenario as SC


class Params(NamedTuple):
    """Alle Einstellungen, die eine Instanz und ihre Auswertung bestimmen (ohne Seed)."""
    n_ports: int
    n_periods: int
    speed: int
    sigma: int
    penalty: int
    k: int


def make_instance(p, seed):
    return SC.make_instance(p.n_ports, p.n_periods, seed, sigma=p.sigma, speed=p.speed)


def k_star(inst):
    """Faustregel k* ~= 1,6 x mittlere Vorlaufzeit, begrenzt auf [0, Perioden - 1]."""
    lead = SC.mean_lead(inst)
    return min(inst["T"] - 1, max(0, round(C.K_STAR_FACTOR * lead)))


# ---------------------------------------------------------------------------------------------------
# Eine Instanz, die drei Ausprägungen
# ---------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Outcome:
    key: str
    label: str
    k: int
    result: RL.RollingResult


def run_for_k(inst, p, k, record=False):
    """Ergebnis (RollingResult) für ein konkretes Vorschau-Fenster k auf einer Instanz."""
    return RL.run_rolling_horizon(inst, k, C.HOLD_COST, C.RATE, p.penalty, record=record)


def run_mode(inst, p, mode, record=False):
    """Ergebnis (RollingResult) einer Ausprägung (reaktiv/eingestellt/voll) auf einer Instanz."""
    k = {C.MODE_REACTIVE: 0, C.MODE_CONFIGURED: p.k, C.MODE_FULL: inst["T"] - 1}[mode]
    return RL.run_rolling_horizon(inst, k, C.HOLD_COST, C.RATE, p.penalty, record=record)


def run_outcomes(inst, p, record=False):
    """Die drei Ausprägungen (Reihenfolge C.MODE_KEYS) auf derselben Instanz."""
    out = []
    for key in C.MODE_KEYS:
        k = {C.MODE_REACTIVE: 0, C.MODE_CONFIGURED: p.k, C.MODE_FULL: inst["T"] - 1}[key]
        out.append(Outcome(key, C.MODE_LABELS[key], k, RL.run_rolling_horizon(inst, k, C.HOLD_COST, C.RATE, p.penalty, record=record)))
    return out


def outcome_of(outcomes, key):
    return next(o for o in outcomes if o.key == key)


def cost_curve(inst, p):
    """Gesamtkosten über dem Vorschau-Fenster k = 0 .. Perioden - 1 (für die Kosten-über-k-Kurve)."""
    return tuple(RL.run_rolling_horizon(inst, k, C.HOLD_COST, C.RATE, p.penalty).total for k in range(inst["T"]))


# ---------------------------------------------------------------------------------------------------
# Stichprobe
# ---------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class InstanceResult:
    seed: int
    mean_lead: float
    costs: tuple        # Gesamtkosten je k (Index 0 .. Perioden - 1)
    configured_k: int   # das k, das als "eingestellt" gilt (aus Params.k, begrenzt auf Perioden - 1)

    @property
    def exact(self):
        return self.costs[-1]

    @property
    def reactive(self):
        return self.costs[0]

    @property
    def configured(self):
        return self.costs[min(self.configured_k, len(self.costs) - 1)]


def instance_result(p, seed):
    inst = make_instance(p, seed)
    costs = cost_curve(inst, p)
    return InstanceResult(seed, SC.mean_lead(inst), costs, min(p.k, inst["T"] - 1))


def sample(p, n=C.SAMPLE_INSTANCES, start=0):
    """n Instanzen (Seeds start .. start+n-1, unabhängig vom eingestellten Seed)."""
    return tuple(instance_result(p, seed) for seed in range(start, start + n))


def markup_pct(cost, exact):
    """Aufschlag gegen das Optimum in %; 0, wenn das Optimum selbst 0 kostet (kein Bedarf)."""
    return 100.0 * (cost - exact) / exact if exact else 0.0


def mean_markup(results, k):
    """Aufschlag von Vorschau-Fenster k gegen das Optimum, gemittelt über die Instanzen - als
    Verhältnis der Mittelwerte (mean Kosten bei k durch mean Optimum), NICHT als Mittel der
    Einzel-Aufschläge: das ist dieselbe Methode wie in messreihe_ecr/sweep.py (report()), Instanzen
    mit sehr kleinem Optimum würden sonst ihren eigenen Prozentwert überproportional aufblasen."""
    avg_cost = statistics.fmean(r.costs[min(k, len(r.costs) - 1)] for r in results)
    avg_exact = statistics.fmean(r.exact for r in results)
    return markup_pct(avg_cost, avg_exact)


def mean_of(results, field):
    """field in {'reactive', 'configured', 'exact'}."""
    return statistics.fmean(getattr(r, field) for r in results)


def paired(results, field, reference="exact"):
    """Gepaarte Differenz field - reference je Instanz (negativ = billiger)."""
    return [getattr(r, field) - getattr(r, reference) for r in results]


def _se(d):
    return statistics.stdev(d) / math.sqrt(len(d)) if len(d) > 1 else 0.0


@dataclass(frozen=True)
class Verdict:
    kind: str           # "better" (billiger) | "worse" | "unclear"
    diff: float          # field minus reference je Instanz (negativ = billiger)
    se: float
    pct: object          # Unterschied in % der Referenz; None, wenn die Referenz im Mittel 0 ist
    n: int
    field: str
    reference: str


def verdict(results, field, reference="exact"):
    """Bewertung gegen die Referenz. 'Klar' heißt: Unterschied > VERDICT_Z Standardfehler der
    gepaarten Differenz je Instanz; sonst 'unclear'."""
    d = paired(results, field, reference)
    diff, se = statistics.fmean(d), _se(d)
    ref_mean = mean_of(results, reference)
    if se == 0:
        kind = "unclear" if diff == 0 else ("better" if diff < 0 else "worse")
    else:
        kind = "unclear" if abs(diff) <= C.VERDICT_Z * se else ("better" if diff < 0 else "worse")
    return Verdict(kind, diff, se, 100.0 * diff / ref_mean if ref_mean else None, len(d), field, reference)


# ---------------------------------------------------------------------------------------------------
# Diagnose (bedingte Meldung, Plan Abschnitt 6)
# ---------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Diagnosis:
    kind: str            # "too_short" | "near_optimal" | "ok"
    gap_pct: float        # Abstand der eingestellten Vorschau zum Optimum in %
    mean_lead: float
    configured_k: int


def diagnose(inst, p, configured_result, exact_total):
    """Bedingte Meldung: Vorschau < mittlere Vorlaufzeit -> zu kurz; Abstand < NEAR_OPTIMAL_PCT ->
    kaum noch Luft nach oben; sonst nichts Besonderes (nur die Kennzahlen sprechen)."""
    lead = SC.mean_lead(inst)
    gap = markup_pct(configured_result.total, exact_total)
    k = min(p.k, inst["T"] - 1)
    if k < lead:
        kind = "too_short"
    elif gap < C.NEAR_OPTIMAL_PCT:
        kind = "near_optimal"
    else:
        kind = "ok"
    return Diagnosis(kind, gap, lead, k)
