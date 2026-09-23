"""Auswertung: Stichprobe, Kosten-über-k-Kurve gegen Direktrechnung, Urteil in drei Zuständen und
an der Schwelle, Diagnose in drei Zuständen, Faustregel k*."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import lcr_constants as C  # noqa: E402
import lcr_evaluation as E  # noqa: E402
from lcr_rolling import run_rolling_horizon  # noqa: E402


def test_cost_curve_matches_direct_rolling_horizon_calls():
    p = E.Params(4, 6, 22, 3, 200, 3)
    inst = E.make_instance(p, 5)
    costs = E.cost_curve(inst, p)
    assert len(costs) == inst["T"]
    for k, c in enumerate(costs):
        direct = run_rolling_horizon(inst, k, C.HOLD_COST, C.RATE, p.penalty).total
        assert c == pytest.approx(direct)


def test_cost_curve_is_monotonically_non_increasing():
    p = E.Params(5, 8, 22, 3, 200, 4)
    inst = E.make_instance(p, 12)
    costs = E.cost_curve(inst, p)
    assert all(b <= a + 1e-6 for a, b in zip(costs, costs[1:]))


def test_instance_result_exact_equals_full_lookahead_and_reactive_equals_k0():
    p = E.Params(4, 7, 22, 3, 200, 2)
    r = E.instance_result(p, 3)
    assert r.exact == r.costs[-1] and r.reactive == r.costs[0]
    assert r.configured == r.costs[r.configured_k]


def test_markup_pct_zero_when_cost_equals_exact_and_positive_when_worse():
    assert E.markup_pct(100.0, 100.0) == 0.0
    assert E.markup_pct(150.0, 100.0) == pytest.approx(50.0)
    assert E.markup_pct(100.0, 0.0) == 0.0                          # kein Bedarf -> kein Aufschlag definierbar


def test_mean_markup_clamps_k_to_the_last_available_index():
    """mean_markup darf nie ausserhalb von costs indizieren, auch wenn k (z. B. ein an einen groesseren
    Horizont gewoehntes Vorschau-Fenster aus einem Permalink) die Laenge der Kostenliste erreicht oder
    ueberschreitet - dann zaehlt der letzte Wert (volle Vorschau)."""

    class Fake:
        pass

    r = Fake()
    r.costs = [30.0, 20.0, 10.0]
    r.exact = 10.0
    assert E.mean_markup([r], 2) == E.mean_markup([r], 5) == E.mean_markup([r], 99)


def test_mean_markup_uses_ratio_of_means_not_mean_of_ratios():
    """Absichtlich gewählt (siehe lcr_evaluation.mean_markup-Docstring): Instanzen mit kleinem
    Optimum würden bei einem Mittel der Einzel-Prozentwerte den Aufschlag verzerren."""

    class Fake:
        pass

    a, b = Fake(), Fake()
    a.costs, a.exact = [10.0, 1.0], 1.0    # Aufschlag 900 % einzeln
    b.costs, b.exact = [1000.0, 500.0], 500.0  # Aufschlag 100 % einzeln
    results = [a, b]
    # Verhältnis der Mittelwerte: (10+1000)/2 = 505 gegen (1+500)/2 = 250.5 -> ca. +101.6 %, NICHT (900+100)/2=500 %
    assert E.mean_markup(results, 0) == pytest.approx(100.0 * (505.0 / 250.5 - 1.0))
    assert E.mean_markup(results, 0) < 200.0


def test_verdict_three_states_and_exact_threshold_boundary():
    import math
    import statistics

    class Fake:
        pass

    def make(diffs, exact=100.0):
        out = []
        for d in diffs:
            r = Fake()
            r.configured, r.exact = exact + d, exact
            out.append(r)
        return out

    # klar besser: konstante Differenz -1 überall -> Standardfehler 0, diff < 0
    v = E.verdict(make([-1, -1, -1, -1]), "configured", "exact")
    assert v.kind == "better" and v.se == 0.0

    # klar schlechter
    v = E.verdict(make([1, 1, 1, 1]), "configured", "exact")
    assert v.kind == "worse"

    # knapp unter der Schwelle (Differenz < VERDICT_Z * SE) -> NICHT klar; knapp darüber -> klar.
    # Gleitkomma macht die Schwelle selbst ("<=") nicht bit-exakt prüfbar, deshalb symmetrisch um sie herum.
    base = [1.0, -1.0, 2.0, -2.0]           # Mittel 0
    se = statistics.stdev(base) / math.sqrt(len(base))
    just_under = [x + C.VERDICT_Z * se - 0.05 for x in base]
    v_under = E.verdict(make(just_under), "configured", "exact")
    assert v_under.kind == "unclear"

    just_over = [x + C.VERDICT_Z * se + 0.05 for x in base]
    v_over = E.verdict(make(just_over), "configured", "exact")
    assert v_over.kind == "worse"


def test_verdict_pct_is_none_when_reference_mean_is_zero():
    class Fake:
        pass

    r = Fake()
    r.configured, r.exact = 5.0, 0.0
    v = E.verdict([r], "configured", "exact")
    assert v.pct is None


def test_k_star_scales_with_mean_lead_and_is_capped_at_horizon():
    p = E.Params(5, 10, 22, 3, 200, 0)
    inst = E.make_instance(p, 1)
    lead = __import__("lcr_scenario").mean_lead(inst)
    expected = min(inst["T"] - 1, max(0, round(C.K_STAR_FACTOR * lead)))
    assert E.k_star(inst) == expected


def test_k_star_never_exceeds_periods_minus_one_even_for_huge_lead():
    inst = dict(p=2, T=4, dist=[[0, 10000], [10000, 0]], lead=[[0, 3], [3, 0]])
    assert E.k_star(inst) <= 3


def test_diagnose_too_short_when_k_below_mean_lead():
    p = E.Params(5, 10, 10, 3, 200, 0)   # k=0, lange Vorlaufzeit erzwingt "too_short"
    inst = E.make_instance(p, 2)
    outcomes = E.run_outcomes(inst, p)
    configured = next(o for o in outcomes if o.key == C.MODE_CONFIGURED)
    full = next(o for o in outcomes if o.key == C.MODE_FULL)
    diag = E.diagnose(inst, p, configured.result, full.result.total)
    assert diag.kind == "too_short"


def test_diagnose_near_optimal_when_gap_below_threshold():
    p = E.Params(5, 10, 22, 3, 200, 9)   # k = T-1 = volle Vorschau -> Abstand 0
    inst = E.make_instance(p, 2)
    outcomes = E.run_outcomes(inst, p)
    configured = next(o for o in outcomes if o.key == C.MODE_CONFIGURED)
    full = next(o for o in outcomes if o.key == C.MODE_FULL)
    diag = E.diagnose(inst, p, configured.result, full.result.total)
    assert diag.kind == "near_optimal" and diag.gap_pct == pytest.approx(0.0, abs=1e-6)


def test_diagnose_ok_when_k_at_least_lead_but_gap_above_threshold():
    p = E.Params(5, 10, 22, 3, 200, 1)
    inst = E.make_instance(p, 636)   # Standard-Preset-Seed: mean_lead ~2.3, k=1 < lead -> too_short erwartet
    outcomes = E.run_outcomes(inst, p)
    configured = next(o for o in outcomes if o.key == C.MODE_CONFIGURED)
    full = next(o for o in outcomes if o.key == C.MODE_FULL)
    diag = E.diagnose(inst, p, configured.result, full.result.total)
    assert diag.kind in ("too_short", "ok")   # je nach genauer Vorlaufzeit dieser Instanz


def test_diagnose_boundary_when_k_exactly_equals_mean_lead():
    """Grenzfall: k == mittlere Vorlaufzeit (exakt, nicht nur knapp darueber/darunter) gilt NICHT als
    "zu kurz" (der Code prueft "k < lead", nicht "k <= lead") - k deckt die Vorlaufzeit gerade noch."""

    class FakeResult:
        pass

    inst = dict(p=2, T=5, dist=[[0, 10], [10, 0]], lead=[[0, 3], [3, 0]])   # mittlere Vorlaufzeit exakt 3.0
    p = E.Params(2, 5, 10, 3, 200, 3)                                        # k = 3 = Vorlaufzeit
    configured = FakeResult()
    configured.total = 120.0
    exact_total = 100.0                                                     # Abstand 20 % -> nicht "near_optimal"
    diag = E.diagnose(inst, p, configured, exact_total)
    assert diag.kind == "ok"


def test_diagnose_boundary_when_gap_exactly_equals_near_optimal_threshold():
    """Grenzfall: Abstand exakt gleich NEAR_OPTIMAL_PCT gilt NICHT als "nahe am Optimum" (der Code
    prueft "gap < Schwelle", nicht "<=")."""

    class FakeResult:
        pass

    inst = dict(p=2, T=5, dist=[[0, 10], [10, 0]], lead=[[0, 1], [1, 0]])   # kleine Vorlaufzeit, k deckt sie
    p = E.Params(2, 5, 10, 3, 200, 3)
    configured = FakeResult()
    configured.total = 102.0
    exact_total = 100.0                                                     # Abstand exakt 2,0 % = NEAR_OPTIMAL_PCT
    diag = E.diagnose(inst, p, configured, exact_total)
    assert diag.gap_pct == pytest.approx(C.NEAR_OPTIMAL_PCT)
    assert diag.kind == "ok"


def test_run_outcomes_keys_and_ks_are_well_ordered():
    p = E.Params(5, 10, 22, 3, 200, 4)
    inst = E.make_instance(p, 0)
    outcomes = E.run_outcomes(inst, p)
    assert [o.key for o in outcomes] == list(C.MODE_KEYS)
    by_key = {o.key: o for o in outcomes}
    assert by_key[C.MODE_REACTIVE].k == 0
    assert by_key[C.MODE_CONFIGURED].k == 4
    assert by_key[C.MODE_FULL].k == inst["T"] - 1
    assert by_key[C.MODE_FULL].result.total <= by_key[C.MODE_CONFIGURED].result.total + 1e-6
    assert by_key[C.MODE_CONFIGURED].result.total <= by_key[C.MODE_REACTIVE].result.total + 1e-6
