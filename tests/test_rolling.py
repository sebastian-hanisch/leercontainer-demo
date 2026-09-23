"""Rollierender Horizont: Konsistenz (volle Vorschau ab t=0 = einmaliger globaler Solve), Monotonie
über k, Randfälle (aus messreihe_ecr/check.py übernommen und erweitert)."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import lcr_scenario as SC  # noqa: E402
from lcr_rolling import run_global_exact, run_rolling_horizon  # noqa: E402

HOLD_COST, RATE, PENALTY = 0.3, 1.0, 200.0


@pytest.mark.parametrize("n_ports", [3, 4, 6])
@pytest.mark.parametrize("seed", range(15))
def test_full_lookahead_from_start_matches_single_global_solve(n_ports, seed):
    inst = SC.make_instance(n_ports, 6, seed)
    exact = run_global_exact(inst, HOLD_COST, RATE, PENALTY)
    full = run_rolling_horizon(inst, inst["T"] - 1, HOLD_COST, RATE, PENALTY).total
    assert full == pytest.approx(exact, abs=1e-6)


@pytest.mark.parametrize("seed", range(25))
def test_monotonicity_more_lookahead_never_hurts(seed):
    inst = SC.make_instance(4, 8, seed)
    costs = [run_rolling_horizon(inst, k, HOLD_COST, RATE, PENALTY).total for k in range(inst["T"])]
    for a, b in zip(costs, costs[1:]):
        assert b <= a + 1e-6


def test_hand_instance_matches_check_py_reference():
    inst = dict(p=2, T=3, coords=[(0, 0), (22, 0)], dist=[[0, 22], [22, 0]], lead=[[0, 1], [1, 0]], b=[[5, 0, 0], [0, -5, 0]])
    assert run_global_exact(inst, HOLD_COST, RATE, PENALTY) == pytest.approx(110.0)


def test_k_zero_is_purely_reactive_and_pays_full_penalty_for_current_shortfall():
    inst = SC.make_instance(4, 6, 5)
    r = run_rolling_horizon(inst, 0, HOLD_COST, RATE, PENALTY)
    manual_penalty = sum(max(0, -inst["b"][p][t]) for p in range(4) for t in range(6)) * PENALTY
    # bei k=0 kann NIE etwas rechtzeitig transportiert werden (lead >= 1 > Fensterbreite 0): jede
    # Periode zahlt ihren eigenen negativen Bedarf in voller Höhe.
    assert r.shortfall_cost == pytest.approx(manual_penalty)
    assert r.transport == 0.0


def test_full_lookahead_equals_exact_with_a_single_period():
    inst = SC.make_instance(3, 2, 0)
    exact = run_global_exact(inst, HOLD_COST, RATE, PENALTY)
    full = run_rolling_horizon(inst, 1, HOLD_COST, RATE, PENALTY).total
    assert full == pytest.approx(exact, abs=1e-6)


def test_minimum_port_count_runs():
    inst = SC.make_instance(3, 6, 0)
    r = run_rolling_horizon(inst, 3, HOLD_COST, RATE, PENALTY)
    assert r.total >= 0


def test_instance_without_any_demand_costs_nothing():
    inst = dict(p=3, T=4, coords=SC.make_ports(3, 0), dist=SC.dist_matrix(SC.make_ports(3, 0)), lead=SC.lead_matrix(SC.dist_matrix(SC.make_ports(3, 0)), 22), b=[[0] * 4 for _ in range(3)])
    r = run_rolling_horizon(inst, 3, HOLD_COST, RATE, PENALTY)
    assert r.total == 0.0 and r.shortfall_qty == 0.0
    assert run_global_exact(inst, HOLD_COST, RATE, PENALTY) == 0.0


def test_unreachable_demand_forces_full_penalty_regardless_of_lookahead():
    """Bedarf VOR jedem möglichen Ueberschuss (Kausalität): keine Vorschau kann das reparieren."""
    inst = dict(p=2, T=2, coords=[(0, 0), (22, 0)], dist=[[0, 22], [22, 0]], lead=[[0, 1], [1, 0]], b=[[0, 5], [-5, 0]])
    for k in (0, 1):
        r = run_rolling_horizon(inst, k, HOLD_COST, RATE, PENALTY)
        assert r.total == pytest.approx(5 * PENALTY)


def test_record_true_produces_one_step_per_period_with_consistent_stock():
    inst = SC.make_instance(4, 6, 2)
    r = run_rolling_horizon(inst, 3, HOLD_COST, RATE, PENALTY, record=True)
    assert len(r.steps) == inst["T"]
    assert [s.t for s in r.steps] == list(range(inst["T"]))
    assert r.steps[0].held_stock_start == (0.0, 0.0, 0.0, 0.0)         # nichts vorrätig vor der ersten Periode


def test_record_steps_transport_totals_match_aggregate_result():
    inst = SC.make_instance(4, 7, 9)
    r = run_rolling_horizon(inst, 4, HOLD_COST, RATE, PENALTY, record=True)
    total_transport_cost = sum(qty * RATE * inst["dist"][p][q] for s in r.steps for (p, q), qty in s.transport_out.items())
    total_shortfall_cost = sum(qty * PENALTY for s in r.steps for qty in s.shortfall.values())
    assert total_transport_cost == pytest.approx(r.transport)
    assert total_shortfall_cost == pytest.approx(r.shortfall_cost)
