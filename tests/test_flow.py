"""Min-Cost-Flow-Kern: Handinstanzen (aus messreihe_ecr/check.py übernommen), Flusserhaltung,
Kausalität."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from lcr_flow import solve_window  # noqa: E402

HOLD_COST, RATE, PENALTY = 0.3, 1.0, 200.0


def _hand_instance(b):
    """2 Häfen A (bei 0 km) und B (bei 22 km, lead=1 bei speed=22), T=3."""
    return dict(p=2, T=3, coords=[(0, 0), (22, 0)], dist=[[0, 22], [22, 0]], lead=[[0, 1], [1, 0]], b=b)


def test_hand_instance_surplus_before_demand_costs_only_transport():
    """A hat in t=0 Ueberschuss +5, B braucht in t=1 genau -5: alles sofort transportieren, Kosten
    5 * 22 = 110 (kein Grund zu halten oder Fehlmenge zu zahlen)."""
    inst = _hand_instance([[5, 0, 0], [0, -5, 0]])
    cost, transport, hold, shortfall = solve_window(inst, 0, 2, [0, 0], {}, HOLD_COST, RATE, PENALTY)
    assert cost == pytest.approx(110.0)
    assert transport[(0, 1)] == 5
    assert sum(shortfall.values()) == 0


def test_hand_instance_causality_surplus_after_demand_forces_full_penalty():
    """B braucht in t=0, A hat Ueberschuss erst in t=1: keine Kante kann rückwärts in der Zeit
    liefern -> volle Notleasing-Strafe 5 * 200 = 1000."""
    inst = _hand_instance([[0, 5, 0], [-5, 0, 0]])
    cost, transport, hold, shortfall = solve_window(inst, 0, 2, [0, 0], {}, HOLD_COST, RATE, PENALTY)
    assert cost == pytest.approx(1000.0)
    assert shortfall.get(1, 0) == 5


def test_flow_conservation_holds_for_random_windows():
    """demand_total (gesamte Fehlmenge) wird vollständig geflossen (solve_window prüft das per
    assert selbst; hier zusätzlich: Summe Transport-Abgang + Halte-Abgang <= verfügbare Menge)."""
    import lcr_scenario as SC

    for seed in range(10):
        inst = SC.make_instance(4, 6, seed)
        held = [3.0] * 4
        cost, transport, hold, shortfall = solve_window(inst, 0, 5, held, {}, HOLD_COST, RATE, PENALTY)
        assert cost >= 0
        for p in range(4):
            outflow = hold.get(p, 0.0) + sum(q for (pp, qq), q in transport.items() if pp == p)
            available = held[p] + max(0, inst["b"][p][0])
            assert outflow <= available + 1e-6


def test_no_edges_can_move_backward_in_time_by_construction():
    """Bei k=0 (Fenster = eine einzige Periode) gibt es keine Halte- oder Transportkante: jeder
    Bedarf zahlt zwangsläufig die volle Strafe, jeder Ueberschuss bleibt ungenutzt."""
    inst = dict(p=2, T=3, coords=[(0, 0), (22, 0)], dist=[[0, 22], [22, 0]], lead=[[0, 1], [1, 0]], b=[[5, 0, 0], [-3, 0, 0]])
    cost, transport, hold, shortfall = solve_window(inst, 0, 0, [0, 0], {}, HOLD_COST, RATE, PENALTY)
    assert transport == {} and hold == {}
    assert shortfall[1] == 3
    assert cost == pytest.approx(3 * PENALTY)


def test_pending_inflow_is_added_at_its_arrival_period():
    inst = _hand_instance([[0, 0, 0], [0, -4, 0]])
    cost, transport, hold, shortfall = solve_window(inst, 0, 2, [0, 0], {(1, 1): 4.0}, HOLD_COST, RATE, PENALTY)
    assert shortfall.get(1, 0) == 0 and cost == pytest.approx(0.0)
