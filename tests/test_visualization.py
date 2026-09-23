"""Figuren: Kosten-über-k-Kurve, Vergleichskurve, Hafenkarte - alle Achsen fest (fixedrange), Marken
und Hover-Texte vorhanden."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import lcr_constants as C  # noqa: E402
import lcr_evaluation as E  # noqa: E402
import lcr_scenario as SC  # noqa: E402
import lcr_visualization as V  # noqa: E402


def _axes_are_locked(fig):
    return fig.layout.xaxis.fixedrange is True and fig.layout.yaxis.fixedrange is True


@pytest.fixture
def scenario():
    p = E.Params(5, 10, 22, 3, 200, 4)
    inst = E.make_instance(p, 0)
    outcomes = E.run_outcomes(inst, p, record=True)
    costs = E.cost_curve(inst, p)
    return inst, outcomes, costs


def test_cost_curve_figure_locks_axes_and_has_current_point(scenario):
    inst, outcomes, costs = scenario
    fig = V.cost_curve_figure(costs, E.k_star(inst), 4)
    assert _axes_are_locked(fig)
    assert len(fig.data) >= 2                                     # Linie + eingestellter Punkt
    point_trace = fig.data[-1]
    assert list(point_trace.x) == [4] and list(point_trace.y) == [costs[4]]


def test_cost_curve_figure_omits_k_star_marker_when_it_equals_current():
    fig_same = V.cost_curve_figure([100, 80, 60, 60], 2, 2)
    fig_diff = V.cost_curve_figure([100, 80, 60, 60], 1, 2)
    assert len(fig_same.layout.shapes) < len(fig_diff.layout.shapes)


def test_comparison_curve_figure_has_one_marker_per_outcome(scenario):
    inst, outcomes, costs = scenario
    fig = V.comparison_curve_figure(costs, outcomes)
    assert _axes_are_locked(fig)
    marker_traces = [t for t in fig.data if t.mode == "markers"]
    assert len(marker_traces) == len(outcomes)


def test_map_figure_locks_axes_and_colors_surplus_and_deficit(scenario):
    inst, outcomes, costs = scenario
    net = SC.net_by_port(inst)
    fig = V.map_figure(inst, net, None, "Titel")
    assert _axes_are_locked(fig)
    port_trace = fig.data[-1]
    colors = list(port_trace.marker.color)
    assert len(colors) == len(net)
    for c, v in zip(colors, net):
        assert c == (C.SURPLUS_COLOR if v >= 0 else C.DEFICIT_COLOR)


def test_map_figure_draws_an_arrow_per_transport_in_the_given_step(scenario):
    inst, outcomes, costs = scenario
    net = SC.net_by_port(inst)
    configured = next(o for o in outcomes if o.key == C.MODE_CONFIGURED)
    step_with_transport = next((s for s in configured.result.steps if any(q > 0 for q in s.transport_out.values())), None)
    assert step_with_transport is not None, "Testinstanz sollte mindestens einen Transport enthalten"
    fig = V.map_figure(inst, net, step_with_transport, "Titel")
    n_arrows = sum(1 for q in step_with_transport.transport_out.values() if q > 0)
    assert len(fig.layout.annotations) == n_arrows


def test_map_figure_rings_ports_with_shortfall_in_the_given_step(scenario):
    inst, outcomes, costs = scenario
    net = SC.net_by_port(inst)
    reactive = next(o for o in outcomes if o.key == C.MODE_REACTIVE)
    step_with_shortfall = next((s for s in reactive.result.steps if any(q > 0 for q in s.shortfall.values())), None)
    assert step_with_shortfall is not None, "k=0 sollte in dieser Testinstanz Notleasing haben"
    fig = V.map_figure(inst, net, step_with_shortfall, "Titel")
    port_trace = fig.data[-1]
    line_colors = list(port_trace.marker.line.color)
    ringed = [i for i in range(len(net)) if line_colors[i] == C.SHORTFALL_RING_COLOR]
    expected = [i for i in range(len(net)) if step_with_shortfall.shortfall.get(i, 0) > 0]
    assert ringed == expected


def test_map_title_reports_period_and_shortfall():
    t = V.map_title("Label", 3, 10, 5.0)
    assert "Label" in t and "Periode 3 von 9" in t and "5" in t
