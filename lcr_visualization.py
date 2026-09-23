"""Plotly-Figuren der Leercontainer-Demo: Hafenkarte (Ueberschuss/Bedarf, Transporte je Zeitschritt),
Kosten-über-k-Kurve, Vergleich der drei Ausprägungen.

Konventionen des Portfolios: Achsen `fixedrange` (Touch-Scrollen), Vorlage plotly_white, Marker-Linien
in mittlerem Grau, Ueberschriften stehen als Markdown UEBER dem Diagramm. Plotly wird erst in den
Funktionen importiert, damit die reine Rechnung ohne Plotly testbar bleibt."""
import lcr_constants as C

LEGEND_BOTTOM = dict(orientation="h", yref="container", yanchor="bottom", y=0.0, x=0)


def _lock_axes(fig):
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def _vline(fig, x, text, color=None, dash="dot", position="top"):
    fig.add_vline(x=x, line=dict(color=color or C.MARKER_LINE_COLOR, width=2, dash=dash), annotation_text=text, annotation_position=position, annotation_font=dict(size=11))


# ---------------------------------------------------------------------------------------------------
# Kosten-über-k-Kurve
# ---------------------------------------------------------------------------------------------------
def cost_curve_figure(costs, k_star_value, current_k):
    """Gesamtkosten über dem Vorschau-Fenster k; gestrichelte grüne Linie beim Optimum, graue Marke
    bei der Faustregel k*, roter Punkt beim eingestellten k."""
    import plotly.graph_objects as go

    ks = list(range(len(costs)))
    exact = costs[-1]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ks, y=list(costs), mode="lines+markers", name="Gesamtkosten", line=dict(color=C.MODE_COLORS[C.MODE_CONFIGURED], width=2.5), marker=dict(size=6),
                             hovertemplate="Vorschau k=%{x}<br>%{y:.0f} Gesamtkosten<extra></extra>"))
    fig.add_hline(y=exact, line=dict(color=C.EXACT_LINE_COLOR, width=2, dash="dash"), annotation_text="Optimum (volle Vorschau)", annotation_position="bottom right", annotation_font=dict(size=11))
    if k_star_value in ks and k_star_value != current_k:
        _vline(fig, k_star_value, "Faustregel k*", dash="dot", position="top")
    fig.add_trace(go.Scatter(x=[current_k], y=[costs[current_k]], mode="markers", marker=dict(size=13, color=C.MODE_COLORS[C.MODE_REACTIVE], line=dict(width=2, color="white")),
                             name="eingestellt", hovertemplate="eingestellt: k=%{x}<br>%{y:.0f}<extra></extra>"))
    fig.update_layout(template="plotly_white", height=C.CHART_HEIGHT, margin=dict(t=30, b=45), showlegend=False, hovermode="closest",
                      xaxis_title="Vorschau-Fenster k (Perioden)", yaxis_title="Gesamtkosten")
    fig.update_xaxes(tickmode="array", tickvals=ks)
    fig.update_yaxes(rangemode="tozero")
    return _lock_axes(fig)


def comparison_curve_figure(costs, outcomes):
    """Dieselbe Kurve, aber mit allen drei Ausprägungen markiert (Vergleichs-Tab)."""
    import plotly.graph_objects as go

    ks = list(range(len(costs)))
    exact = costs[-1]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ks, y=list(costs), mode="lines+markers", name="Gesamtkosten", line=dict(color=C.MARKER_LINE_COLOR, width=2), marker=dict(size=5),
                             hovertemplate="Vorschau k=%{x}<br>%{y:.0f} Gesamtkosten<extra></extra>"))
    fig.add_hline(y=exact, line=dict(color=C.EXACT_LINE_COLOR, width=2, dash="dash"))
    for o in outcomes:
        k = min(o.k, len(costs) - 1)
        fig.add_trace(go.Scatter(x=[k], y=[costs[k]], mode="markers", name=C.MODE_SHORT[o.key], marker=dict(size=13, color=C.MODE_COLORS[o.key], line=dict(width=2, color="white")),
                                 hovertemplate=f"{C.MODE_SHORT[o.key]}: k=%{{x}}<br>%{{y:.0f}}<extra></extra>"))
    fig.update_layout(template="plotly_white", height=C.CHART_HEIGHT, margin=dict(t=25, b=90), legend=LEGEND_BOTTOM, hovermode="closest",
                      xaxis_title="Vorschau-Fenster k (Perioden)", yaxis_title="Gesamtkosten")
    fig.update_xaxes(tickmode="array", tickvals=ks)
    fig.update_yaxes(rangemode="tozero")
    return _lock_axes(fig)


# ---------------------------------------------------------------------------------------------------
# Hafenkarte
# ---------------------------------------------------------------------------------------------------
def map_title(label, t, n_periods, shortfall_qty):
    return f"<b>{label}</b><br><sub>Periode {t} von {n_periods - 1} · Notleasing hier: {shortfall_qty:g}</sub>"


def map_figure(inst, net, step, title):
    """Häfen als Kreise (blau = Netto-Ueberschuss über den ganzen Horizont, rot = Netto-Bedarf,
    Radius = Betrag); für die gegebene Periode (step, aus lcr_rolling.Step oder None) werden die dort
    geplanten Transporte als Pfeile eingeblendet, Häfen mit Fehlmenge in dieser Periode rot umrandet."""
    import plotly.graph_objects as go

    coords = inst["coords"]
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    max_abs = max((abs(v) for v in net), default=1) or 1
    sizes = [14 + 26 * (abs(v) / max_abs) for v in net]
    colors = [C.SURPLUS_COLOR if v >= 0 else C.DEFICIT_COLOR for v in net]

    fig = go.Figure()
    annotations = []
    if step is not None:
        for (p, q), qty in step.transport_out.items():
            if qty <= 0:
                continue
            arr = step.t + inst["lead"][p][q]
            annotations.append(dict(x=xs[q], y=ys[q], ax=xs[p], ay=ys[p], xref="x", yref="y", axref="x", ayref="y", showarrow=True, arrowhead=3, arrowsize=1,
                                    arrowwidth=min(6, 1.5 + qty ** 0.5), arrowcolor=C.TRANSPORT_LINE_COLOR, opacity=0.85))
        mx = [(xs[p] + xs[q]) / 2 for (p, q) in step.transport_out if step.transport_out[(p, q)] > 0]
        my = [(ys[p] + ys[q]) / 2 for (p, q) in step.transport_out if step.transport_out[(p, q)] > 0]
        hov = [f"Hafen {p + 1} -> Hafen {q + 1}: {qty:g} Container<br>Ankunft Periode {step.t + inst['lead'][p][q]}"
               for (p, q), qty in step.transport_out.items() if qty > 0]
        if mx:
            fig.add_trace(go.Scatter(x=mx, y=my, mode="markers", marker=dict(size=10, color=C.TRANSPORT_LINE_COLOR, opacity=0.01), hovertext=hov, hoverinfo="text", showlegend=False))

    ring_ports = [i for i in range(len(coords)) if step is not None and step.shortfall.get(i, 0) > 0]
    hover = []
    for i in range(len(coords)):
        held = step.held_stock_start[i] if step is not None else None
        held_txt = f"<br>Bestand zu Periodenbeginn: {held:g}" if held is not None else ""
        short = step.shortfall.get(i, 0) if step is not None else 0
        short_txt = f"<br>Notleasing diese Periode: {short:g}" if short > 0 else ""
        hover.append(f"<b>Hafen {i + 1}</b><br>Netto über den Horizont: {net[i]:+g}{held_txt}{short_txt}")
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="markers+text", marker=dict(size=sizes, color=colors, opacity=0.8,
                                                                          line=dict(width=[3 if i in ring_ports else 1 for i in range(len(coords))],
                                                                                   color=[C.SHORTFALL_RING_COLOR if i in ring_ports else "white" for i in range(len(coords))])),
                             text=[str(i + 1) for i in range(len(coords))], textfont=dict(size=11, color="white"), hovertext=hover, hoverinfo="text", showlegend=False))

    fig.update_layout(title=dict(text=title, font=dict(size=14), x=0.02), template="plotly_white", height=C.MAP_HEIGHT, margin=dict(l=10, r=10, t=58, b=10), annotations=annotations,
                      hovermode="closest")
    fig.update_xaxes(range=[-5, 105], visible=False)
    fig.update_yaxes(range=[-5, 105], visible=False)
    return _lock_axes(fig)
