"""Orakel-Tests: der Min-Cost-Flow-Kern und der rollierende Horizont gegen unabhängige Rechenwege.

* Jedes Fenster (inkl. Bestand und unterwegs befindlicher Ware) wird zusätzlich als Bestandsbilanz-LP
  (scipy/HiGHS, andere Modellierung als das Zeit-Raum-Netz mit Quelle/Senke) gelöst: gleiche Kosten.
* k=0 hat eine geschlossene Form: Strafe x Summe aller Bedarfe (negative Einspeisungen).
* Die aufgezeichneten Schritte werden unabhängig nachgespielt (Bestand, Transit, Kosten).
"""
import random

import numpy as np
import pytest

import lcr_constants as C
import lcr_rolling as RL
import lcr_scenario as SC
from lcr_flow import solve_window

linprog = pytest.importorskip("scipy.optimize").linprog
HOLD, RATE = C.HOLD_COST, C.RATE


def _lp_window(inst, ws, we, held, pending, penalty):
    P, dist, lead, b = inst["p"], inst["dist"], inst["lead"], inst["b"]
    var = {}
    for t in range(ws, we + 1):
        for p in range(P):
            var[("s", p, t)] = len(var)
            if t + 1 <= we:
                var[("h", p, t)] = len(var)
            for q in range(P):
                if p != q and t + lead[p][q] <= we:
                    var[("x", p, q, t)] = len(var)
    c = np.zeros(len(var))
    for key, i in var.items():
        c[i] = penalty if key[0] == "s" else HOLD if key[0] == "h" else RATE * dist[key[1]][key[2]]
    rows, rhs = [], []
    for t in range(ws, we + 1):
        for p in range(P):
            row = np.zeros(len(var))
            for q in range(P):
                if q != p:
                    if ("x", p, q, t) in var:
                        row[var[("x", p, q, t)]] += 1
                    if ("x", q, p, t - lead[q][p]) in var:
                        row[var[("x", q, p, t - lead[q][p])]] -= 1
            if ("h", p, t) in var:
                row[var[("h", p, t)]] += 1
            if ("h", p, t - 1) in var:
                row[var[("h", p, t - 1)]] -= 1
            row[var[("s", p, t)]] -= 1
            rows.append(row)
            rhs.append(b[p][t] + (held[p] if t == ws else 0) + pending.get((p, t), 0))
    res = linprog(c, A_ub=np.array(rows), b_ub=np.array(rhs), bounds=(0, None), method="highs")
    assert res.status == 0
    return res.fun


def _instances(count, seed=7):
    rng = random.Random(seed)
    for _ in range(count):
        yield (SC.make_instance(rng.randint(3, 5), rng.randint(6, 8), rng.randint(0, 9999),
                                sigma=rng.randint(1, 7), speed=rng.choice([10, 22, 40])),
               rng.choice([50, 200, 800]))


def test_global_optimum_and_reactive_closed_form():
    for inst, penalty in _instances(25):
        exact = RL.run_global_exact(inst, HOLD, RATE, penalty)
        assert exact == pytest.approx(_lp_window(inst, 0, inst["T"] - 1, [0] * inst["p"], {}, penalty), rel=1e-9)
        reactive = RL.run_rolling_horizon(inst, 0, HOLD, RATE, penalty).total
        assert reactive == pytest.approx(penalty * sum(max(-v, 0) for row in inst["b"] for v in row))


def test_every_rolling_window_matches_lp_and_replay_reproduces_cost():
    for inst, penalty in _instances(12, seed=11):
        P, T, b = inst["p"], inst["T"], inst["b"]
        for k in (1, 3, T - 1):
            res = RL.run_rolling_horizon(inst, k, HOLD, RATE, penalty, record=True)
            stock, pending, total = [0] * P, {}, 0.0
            for st in res.steps:
                t, we = st.t, min(st.t + k, T - 1)
                window = {key: v for key, v in pending.items() if key[1] <= we}
                cost = solve_window(inst, t, we, list(stock), window, HOLD, RATE, penalty)[0]
                assert cost == pytest.approx(_lp_window(inst, t, we, stock, window, penalty), rel=1e-9)
                assert list(st.held_stock_start) == pytest.approx(stock)
                for p in range(P):
                    v = stock[p] + b[p][t]
                    out = sum(q for (pp, _), q in st.transport_out.items() if pp == p)
                    hold = st.hold_out.get(p, 0)
                    assert st.shortfall.get(p, 0) == max(-v, 0)
                    assert out + hold <= max(v, 0) + 1e-9
                    total += penalty * st.shortfall.get(p, 0) + HOLD * hold
                stock = [st.hold_out.get(p, 0) for p in range(P)]
                for (p, q), qty in st.transport_out.items():
                    total += qty * RATE * inst["dist"][p][q]
                    if qty > 0 and t + inst["lead"][p][q] < T:
                        key = (q, t + inst["lead"][p][q])
                        pending[key] = pending.get(key, 0) + qty
                nxt = {}
                for (p, arr), qty in pending.items():
                    if arr == t + 1:
                        stock[p] += qty
                    elif arr > t + 1:
                        nxt[(p, arr)] = qty
                pending = nxt
            assert total == pytest.approx(res.total)
