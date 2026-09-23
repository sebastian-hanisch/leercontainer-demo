"""Wiederverwendbares Panel: Kennzahlen (2 x 2) und Karte mit Zeitschrittregler - für die
Hauptansicht (eingestellte Vorschau) und je Ausprägung im Vergleich-Expander (Plan Abschnitt 6/8)."""
import streamlit as st

import lcr_constants as C
from lcr_visualization import map_figure, map_title


def render_metrics(columns, result, baseline_result, exact_total, is_baseline=False):
    """Vier Kennzahlen (Gesamtkosten, davon Notleasing, davon Transport+Halten, Abstand zum Optimum);
    Delta immer "dieses Ergebnis minus rein reaktiv" (weniger ist besser), ausser bei der Referenz
    selbst (kein Delta) und beim Abstand zum Optimum (keine Referenz, absolute Größe)."""
    m = columns
    m[0].metric("Gesamtkosten", f"{result.total:,.0f}".replace(",", "."), delta=None if is_baseline else f"{result.total - baseline_result.total:+,.0f}".replace(",", "."),
               delta_color="inverse", help="Transport- und Haltekosten plus Notleasing-Strafe über den ganzen Planungshorizont.")
    m[1].metric("davon Notleasing", f"{result.shortfall_cost:,.0f}".replace(",", "."),
               delta=None if is_baseline else f"{result.shortfall_cost - baseline_result.shortfall_cost:+,.0f}".replace(",", "."), delta_color="inverse",
               help="Strafe für Bedarf, der nicht rechtzeitig aus eigenem Bestand oder Transport gedeckt war (kurzfristiges Zumieten/Chartern).")
    transport_hold = result.transport + result.hold
    base_transport_hold = baseline_result.transport + baseline_result.hold
    m[2].metric("davon Transport+Halten", f"{transport_hold:,.0f}".replace(",", "."), delta=None if is_baseline else f"{transport_hold - base_transport_hold:+,.0f}".replace(",", "."),
               delta_color="inverse", help="Kosten des Umverteilens selbst: Transportkanten (distanzabhängig) plus Haltekanten (Lagerkosten je Periode).")
    gap = 100.0 * (result.total - exact_total) / exact_total if exact_total else 0.0
    m[3].metric("Abstand zum Optimum", f"{gap:.1f} %", help="Aufschlag gegen die exakte volle Vorschau (Optimum); 0 % ist das Optimum selbst.")


def render_step_map(prefix, outcome, inst, net):
    """Zeitschrittregler + Hafenkarte für eine Ausprägung (kein Abspielen - eine bewusste Ansicht je
    Schritt, wie bei den Hafen-Demos)."""
    n_periods = inst["T"]
    t = st.slider("Periode", 0, n_periods - 1, key=f"{prefix}_period_slider", help="Zeigt, welche Transporte in dieser Periode geplant und ausgeführt werden.")
    steps = outcome.result.steps
    step = steps[t] if t < len(steps) else None
    shortfall_here = sum(step.shortfall.values()) if step is not None else 0.0
    st.plotly_chart(map_figure(inst, net, step, map_title(outcome.label, t, n_periods, shortfall_here)), width="stretch", key=f"{prefix}_map_chart")


def render_mode_panel(prefix, outcome, outcomes, inst, net):
    """Beschreibung, Kennzahlen (2 x 2) und Karte + Zeitschrittregler einer Ausprägung (je Tab im
    Vergleich-Expander). Deltas lesen sich immer als "diese Ausprägung minus rein reaktiv"."""
    base = next(o for o in outcomes if o.key == C.BASELINE).result
    exact = next(o for o in outcomes if o.key == C.MODE_FULL).result
    is_base = outcome.key == C.BASELINE

    st.markdown(C.MODE_DESCRIPTIONS[outcome.key])
    st.caption(f"Vorschau-Fenster k = {outcome.k}.")

    row1, row2 = st.columns(2), st.columns(2)
    render_metrics(row1 + row2, outcome.result, base, exact.total, is_baseline=is_base)
    render_step_map(prefix, outcome, inst, net)
