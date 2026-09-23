"""Szenario: Häfen, Distanzen, Vorlaufzeiten, Netto-Einspeisung, Fehlerfälle."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import lcr_scenario as SC  # noqa: E402


def test_make_ports_is_deterministic_and_seed_dependent():
    a = SC.make_ports(5, 42)
    b = SC.make_ports(5, 42)
    c = SC.make_ports(5, 43)
    assert a == b and a != c and len(a) == 5
    assert all(0 <= x <= 100 and 0 <= y <= 100 for x, y in a)


def test_dist_matrix_symmetric_zero_diagonal_and_triangle_inequality():
    coords = SC.make_ports(6, 1)
    d = SC.dist_matrix(coords)
    n = len(coords)
    for i in range(n):
        assert d[i][i] == 0.0
        for j in range(n):
            assert d[i][j] == pytest.approx(d[j][i])
    for i in range(n):
        for j in range(n):
            for k in range(n):
                assert d[i][k] <= d[i][j] + d[j][k] + 1e-9


def test_lead_matrix_matches_exact_hand_computed_values():
    """Regressionstest gegen ein Vorzeichen-/Off-by-one-Rundungsproblem: konkrete Distanzen mit
    bekanntem exaktem round(dist/speed)."""
    coords = [(0, 0), (22, 0), (50, 0), (90, 0)]      # Distanzen zu Hafen 0: 22, 50, 90
    dist = SC.dist_matrix(coords)
    lead = SC.lead_matrix(dist, 22)
    assert lead[0][1] == 1            # round(22/22) = 1
    assert lead[0][2] == 2            # round(50/22) = round(2.27) = 2
    assert lead[0][3] == 4            # round(90/22) = round(4.09) = 4


def test_lead_matrix_at_least_one_and_scales_inversely_with_speed():
    coords = [(0, 0), (30, 0), (90, 0)]
    dist = SC.dist_matrix(coords)
    fast = SC.lead_matrix(dist, 100)
    slow = SC.lead_matrix(dist, 10)
    assert all(fast[i][j] >= 1 for i in range(3) for j in range(3) if i != j)
    assert slow[0][2] > fast[0][2]                                   # doppelt so langsam -> länger (bei genügend Distanz)
    assert fast[1][1] == 0 and slow[1][1] == 0


def test_make_instance_sums_close_to_zero_and_has_right_shape():
    inst = SC.make_instance(5, 10, 7)
    assert inst["p"] == 5 and inst["T"] == 10
    assert len(inst["b"]) == 5 and all(len(row) == 10 for row in inst["b"])
    # exakt 0 ist nach der Zentrierung nicht garantiert (jeder Wert wird EINZELN gerundet, die
    # Rundungsfehler können sich zu einem kleinen Rest aufsummieren); nur der Rest muss klein sein.
    assert abs(sum(sum(row) for row in inst["b"])) <= 20
    assert all(isinstance(v, int) for row in inst["b"] for v in row)  # gerundet


def test_make_instance_is_deterministic():
    a = SC.make_instance(4, 8, 99, sigma=5, speed=15)
    b = SC.make_instance(4, 8, 99, sigma=5, speed=15)
    assert a["b"] == b["b"] and a["coords"] == b["coords"] and a["lead"] == b["lead"]


def test_higher_sigma_increases_spread_on_average():
    import statistics
    spreads_low, spreads_high = [], []
    for seed in range(15):
        low = SC.make_instance(5, 10, seed, sigma=1)
        high = SC.make_instance(5, 10, seed, sigma=7)
        spreads_low.append(statistics.pstdev(v for row in low["b"] for v in row))
        spreads_high.append(statistics.pstdev(v for row in high["b"] for v in row))
    assert statistics.fmean(spreads_high) > statistics.fmean(spreads_low)


def test_mean_lead_matches_manual_average():
    inst = SC.make_instance(4, 6, 3)
    p, lead = inst["p"], inst["lead"]
    manual = [lead[i][j] for i in range(p) for j in range(p) if i != j]
    assert SC.mean_lead(inst) == pytest.approx(sum(manual) / len(manual))


def test_net_by_port_matches_row_sums():
    inst = SC.make_instance(5, 8, 11)
    assert SC.net_by_port(inst) == [sum(row) for row in inst["b"]]


@pytest.mark.parametrize("n_ports,n_periods", [(2, 6), (1, 6), (0, 6)])
def test_too_few_ports_raises(n_ports, n_periods):
    with pytest.raises(ValueError):
        SC.make_instance(n_ports, n_periods, 0)


@pytest.mark.parametrize("n_periods", [1, 0, -1])
def test_too_few_periods_raises(n_periods):
    with pytest.raises(ValueError):
        SC.make_instance(4, n_periods, 0)


def test_minimum_valid_instance_works():
    inst = SC.make_instance(3, 2, 0)
    assert inst["p"] == 3 and inst["T"] == 2
