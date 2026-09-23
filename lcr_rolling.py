"""Rollierender Horizont mit Vorschau-Fenster k: Kernlogik unverändert aus messreihe_ecr/ecr.py
übernommen (run_global_exact, run_rolling_horizon), um `record=True` erweitert, damit die App die
je Periode geplanten Transporte für den Zeitschrittregler zeigen kann (Abschnitt 6/8 des Detailplans).

k=0: rein reaktiv (kennt nur die gerade abgelaufene Periode: das Fenster [t, t] hat keine Halte- oder
Transportkante, jeder unmittelbare Bedarf zahlt also die volle Notleasing-Strafe, jeder Ueberschuss
bleibt ungenutzt bis er - falls überhaupt noch im Fenster - später gebraucht wird).
k=T-1 ab der ersten Periode: sieht von Anfang an den ganzen Horizont -> reproduziert exakt den
einmaligen globalen Solve (siehe tests/test_rolling.py, wie messreihe_ecr/check.py)."""
from dataclasses import dataclass, field

from lcr_flow import solve_window


def run_global_exact(inst, hold_cost, rate, penalty):
    """Ein einziger Min-Cost-Flow über den GANZEN Horizont (volle Vorschau von Anfang an) = das
    Optimum. Kein separater Exakt-Algorithmus: derselbe solve_window, nur mit maximalem Fenster."""
    cost, _, _, _ = solve_window(inst, 0, inst["T"] - 1, [0] * inst["p"], {}, hold_cost, rate, penalty)
    return cost


@dataclass(frozen=True)
class Step:
    """Was in Periode t geplant und ausgeführt wird (für den Zeitschrittregler der Karte)."""
    t: int
    held_stock_start: tuple      # Bestand je Hafen zu Beginn der Periode (vor der Entscheidung)
    transport_out: dict          # (p, q) -> Menge, die in dieser Periode abgeht
    hold_out: dict               # p -> Menge, die am Hafen bleibt
    shortfall: dict              # p -> ungedeckter Bedarf in dieser Periode (Notleasing)


@dataclass(frozen=True)
class RollingResult:
    total: float
    transport: float
    hold: float
    shortfall_cost: float
    shortfall_qty: float
    steps: tuple = field(default=())


def run_rolling_horizon(inst, k, hold_cost, rate, penalty, record=False):
    """k = Vorschaufenster in Perioden (0 = rein reaktiv, T-1 = volle Vorschau, reproduziert den
    exakten Wert). Führt bei jeder Periode nur die dort abgehenden Entscheidungen aus."""
    P, T = inst["p"], inst["T"]
    held = [0.0] * P
    pending = {}
    total_transport_cost = 0.0
    total_hold_cost = 0.0
    total_shortfall_cost = 0.0
    total_shortfall_qty = 0.0
    steps = []
    for t in range(T):
        window_end = min(t + k, T - 1)
        held_stock_in = held[:]
        pending_now = {key: v for key, v in pending.items() if key[1] <= window_end}
        _, transport_out, hold_out, shortfall_now = solve_window(
            inst, t, window_end, held_stock_in, pending_now, hold_cost, rate, penalty)
        if record:
            steps.append(Step(t, tuple(held_stock_in), dict(transport_out), dict(hold_out), dict(shortfall_now)))
        held = [0.0] * P
        for p in range(P):
            held[p] += hold_out.get(p, 0.0)
            total_hold_cost += hold_out.get(p, 0.0) * hold_cost
        for (p, q), qty in transport_out.items():
            if qty <= 0:
                continue
            arr = t + inst["lead"][p][q]
            total_transport_cost += qty * rate * inst["dist"][p][q]
            if arr < T:
                pending[(q, arr)] = pending.get((q, arr), 0.0) + qty
        for p, qty in shortfall_now.items():
            if qty > 0:
                total_shortfall_cost += qty * penalty
                total_shortfall_qty += qty
        # Ankünfte, die genau zu Beginn der nächsten Periode landen, wandern von "unterwegs" in
        # "vorrätig"; alles Spätere bleibt unterwegs. Muss aus pending ENTFERNT werden, sonst
        # zählt solve_window sie beim nächsten Aufruf zusätzlich zu held_stock_in nochmal mit.
        still_pending = {}
        for (p, arr), qty in pending.items():
            if arr == t + 1:
                held[p] += qty
            elif arr > t + 1:
                still_pending[(p, arr)] = qty
        pending = still_pending
    total = total_transport_cost + total_hold_cost + total_shortfall_cost
    return RollingResult(total, total_transport_cost, total_hold_cost, total_shortfall_cost, total_shortfall_qty, tuple(steps))
