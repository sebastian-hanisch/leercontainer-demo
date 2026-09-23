"""
Leercontainer-Repositionierung - interaktive Fall-Demo
Sebastian Hanisch - Operations Research und Machine Learning

Welle 1 der Seefracht-Linie: nach dem Löschen ist ein Container leer; Importhäfen sammeln sie,
Exporthäfen brauchen sie für neue Ladung. Die Demo zeigt, wie teuer es ist, künftigen Bedarf nicht
zu kennen - und wie wenig Vorschau (in Perioden) nötig ist, um trotzdem nah am Optimum zu bleiben.

Lauffähig mit: streamlit run app.py
"""
import pandas as pd
import streamlit as st

import lcr_constants as C
import lcr_evaluation as E
import lcr_scenario as SC
import lcr_visualization as V
from lcr_pdf_export import generate_lcr_pdf
from lcr_presets import (apply_preset, bounds, clamp_settings, init_session_state_defaults, k_max, limit_dependent_state, load_permalink_settings, randomize_seed, SETTING_SPECS,
                         sync_query_params)
from lcr_ui_panel import render_metrics, render_mode_panel, render_step_map

st.set_page_config(page_title="Leercontainer-Repositionierung - Sebastian Hanisch", layout="wide")

SCENARIO_KEYS = list(SETTING_SPECS)
REACTIVE, CONFIGURED, FULL = C.MODE_REACTIVE, C.MODE_CONFIGURED, C.MODE_FULL


@st.cache_data(show_spinner=False, max_entries=32)
def _compute_scenario(key):
    """Eine Instanz (Seed) mit allen drei Ausprägungen und der Kosten-über-k-Kurve."""
    seed = key[-1]
    p = E.Params(*key[:-1])
    inst = E.make_instance(p, seed)
    outcomes = E.run_outcomes(inst, p, record=True)
    costs = E.cost_curve(inst, p)
    return inst, outcomes, costs, E.k_star(inst)


@st.cache_data(show_spinner=False, max_entries=16)
def _compute_sample(key):
    """Stichprobe (Seeds 0..SAMPLE_INSTANCES-1), unabhängig vom eingestellten Seed."""
    return E.sample(E.Params(*key), C.SAMPLE_INSTANCES)


st.title("📦 Leercontainer-Repositionierung: Wie weit vorausschauen?")
st.markdown(
    """
Nach dem Löschen ist ein Container leer: an **Überschusshäfen** stapeln sich leere Boxen, an **Mangelhäfen** fehlen sie, um neue Ladung zu stauen. Eine Reederei muss sie zwischen den Häfen
umverteilen, bevor der nächste Bedarf entsteht - aber wie weit im Voraus muss sie den künftigen Bedarf überhaupt kennen? Diese Demo zeigt, wie teuer reines Reagieren ist und wie wenig
**Vorschau-Fenster** nötig ist, um trotzdem nah am Optimum zu bleiben. Wie das Modell funktioniert, steht im Expander "Wie funktioniert diese Demo?" weiter unten, die formale Beschreibung im
Expander "📐 Mathematische Formulierung".
"""
)

st.caption("🎯 Schnellstart – ein Beispielszenario laden:")
PRESET_HELP = {
    "Standard": "Der Grundfall: rein reaktiv kostet massiv mehr, eine moderate Vorschau schließt fast die ganze Lücke.",
    "Kurze Route": "Kurzstrecken-Verkehre (z. B. Intra-Asien): schon wenig Vorschau reicht.",
    "Lange Route": "Lange Vorlaufzeiten (z. B. Transpazifik-ähnlich): dieselbe Vorschau reicht hier bei Weitem nicht.",
    "Unruhiges Aufkommen": "Starke Schwankungen im Aufkommen erhöhen die absoluten Kosten deutlich, ändern aber die Kurvenform kaum.",
    "Teures Notleasing": "Je teurer die Nothilfe (kurzfristiges Chartern), desto überproportional teurer wird Blindheit.",
}
preset_names = list(C.PRESETS.keys())
for row in (preset_names[:3], preset_names[3:]):
    cols = st.columns(3)
    for col, name in zip(cols, row):
        with col:
            st.button(name, width="stretch", on_click=apply_preset, args=(name,), help=PRESET_HELP[name])

st.caption("🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, um ein Szenario zu teilen.")

load_permalink_settings()
init_session_state_defaults()
limit_dependent_state()

with st.sidebar:
    st.header("⚙️ Einstellungen")
    n_ports = st.slider("Häfen", *bounds("n_ports_slider"), key="n_ports_slider", help="Anzahl der Häfen im Zeit-Raum-Netz.")
    n_periods = st.slider("Perioden", *bounds("n_periods_slider"), key="n_periods_slider", help="Planungshorizont T. Ändert sich die Zahl der Perioden, wird das Vorschau-Fenster begrenzt, nicht verworfen.")
    _seed_now = st.session_state.get("seed_input", C.SEED_DEFAULT)
    _speed_now = st.session_state.get("speed_slider", C.SPEED_DEFAULT)
    _dist_preview = SC.dist_matrix(SC.make_ports(int(n_ports), int(_seed_now)))
    _lead_preview = SC.mean_lead(dict(p=int(n_ports), lead=SC.lead_matrix(_dist_preview, _speed_now)))
    speed = st.slider("Schiffsgeschwindigkeit (relativ)", *bounds("speed_slider"), step=C.SPEED_STEP, key="speed_slider",
                      help=f"Steuert die Vorlaufzeit = Distanz/Geschwindigkeit (aufgerundet auf mindestens 1 Periode); bei dieser Einstellung im Mittel {_lead_preview:.2f} Perioden.")
    sigma = st.slider("Volatilität des Aufkommens", *bounds("sigma_slider"), key="sigma_slider", help="Streuung der Netto-Einspeisung je Hafen und Periode um die feste Import-/Export-Neigung.")
    penalty = st.slider("Notleasing-Kosten je Container", *bounds("penalty_slider"), step=C.PENALTY_STEP, key="penalty_slider",
                        help="Strafe je Container, dessen Bedarf nicht rechtzeitig aus Bestand oder Transport gedeckt ist (kurzfristiges Zumieten/Chartern).")
    kmax = k_max(int(n_periods))
    if kmax > 0:
        k = st.slider("Vorschau-Fenster k", 0, kmax, key="k_slider",
                      help=f"0 = rein reaktiv, {kmax} = volle Vorschau (Optimum). Faustregel: k* ≈ 1,6 × mittlere Vorlaufzeit; wird live in der Kurve unten markiert.")
    else:
        k = 0
        st.caption("Vorschau-Fenster: bei nur einer Periode gibt es nichts vorauszuplanen.")
    seed = st.number_input("Seed", *bounds("seed_input"), key="seed_input", step=1, help="Bestimmt Hafenlage und Netto-Einspeisung je Periode.")
    st.button("🎲 Neue Häfen", width="stretch", on_click=randomize_seed, help="Würfelt einen neuen Seed für Hafenlage und Aufkommen.")

k = clamp_settings(int(n_periods), int(k))
sync_query_params({key: st.session_state[key] for key in SCENARIO_KEYS})

p = E.Params(int(n_ports), int(n_periods), int(speed), int(sigma), int(penalty), k)
scenario_key = (*p, int(seed))
with st.spinner("Löse den Min-Cost-Flow..."):
    inst, outcomes, costs, kstar = _compute_scenario(scenario_key)
by_key = {o.key: o for o in outcomes}
reactive, configured, full = by_key[REACTIVE], by_key[CONFIGURED], by_key[FULL]
net = SC.net_by_port(inst)
diag = E.diagnose(inst, p, configured.result, full.result.total)

# ---------------------------------------------------------------------------------------------------
# Hauptansicht
# ---------------------------------------------------------------------------------------------------
st.markdown("## 🎯 Wie teuer ist zu wenig Vorschau?")
st.caption(f"{p.n_ports} Häfen, {p.n_periods} Perioden, mittlere Vorlaufzeit {diag.mean_lead:.2f} Perioden. Vorschau-Fenster k = {configured.k} (Faustregel k* = {kstar}). "
          f"Delta = eingestellte Vorschau minus rein reaktiv (k=0).")

metric_rows = [st.columns(2), st.columns(2)]
render_metrics(metric_rows[0] + metric_rows[1], configured.result, reactive.result, full.result.total, is_baseline=False)

if diag.kind == "too_short":
    st.warning(f"⚠️ Die eingestellte Vorschau (k={diag.configured_k}) ist **kürzer als die mittlere Vorlaufzeit** ({diag.mean_lead:.1f} Perioden): mindestens auf die Vorlaufzeit erhöhen, "
              f"sonst bleibt viel Notleasing kaum vermeidbar. Abstand zum Optimum: **{diag.gap_pct:.1f} %**.")
elif diag.kind == "near_optimal":
    st.success(f"✅ Mit k={diag.configured_k} liegt der Abstand zum Optimum bei **{diag.gap_pct:.1f} %** – kaum noch Luft nach oben, mehr Vorschau lohnt sich kaum.")
else:
    st.info(f"ℹ️ Mit k={diag.configured_k} liegt der Abstand zum Optimum bei **{diag.gap_pct:.1f} %**.")

st.markdown("#### 🗺️ Häfen und geplante Transporte")
render_step_map("main", configured, inst, net)
st.caption("Blau = Netto-Überschuss über den ganzen Horizont, rot = Netto-Bedarf (Radius = Betrag); Pfeile zeigen die in der gewählten Periode geplanten Transporte, roter Rand = Notleasing in "
          "dieser Periode.")

pdf_slot = st.container()

st.markdown("---")

# ---------------------------------------------------------------------------------------------------
# Kernabschnitt
# ---------------------------------------------------------------------------------------------------
st.markdown("### 📐 Wie weit muss ich vorausschauen?")
st.markdown(
    """
Kernfrage dieser Demo: Bei welcher Vorschau ist eine Reederei nah genug am Optimum, ohne den ganzen Planungshorizont sehen zu müssen? Die Kurve zeigt die Gesamtkosten über dem Vorschau-Fenster
k für **Ihre Instanz** - Faustregel k* (grau) und Optimum (grün gestrichelt) als Marken, Ihr eingestelltes k als roter Punkt.
"""
)
st.plotly_chart(V.cost_curve_figure(costs, kstar, configured.k), width="stretch", key="cost_curve_chart")

with st.spinner("Rechne Stichprobe..."):
    sample_key = tuple(p)
    samp = _compute_sample(sample_key)
st.caption(f"Basis: {C.SAMPLE_INSTANCES} Instanzen (Seeds 0-{C.SAMPLE_INSTANCES - 1}, nicht Ihr Seed) mit Ihren Einstellungen. Rechenzeit gemessen: ein einzelner Min-Cost-Flow mit Dijkstra und "
          f"Potentialen löst die Standardgröße in wenigen Millisekunden, selbst {C.N_PORTS_RANGE[1]} Häfen × {C.N_PERIODS_RANGE[1]} Perioden (die größte einstellbare Instanz) noch in rund "
          f"25-30 ms - ohne Knopf möglich, live bei jedem Reglerzug.")


def _show_verdict(label, v):
    if v.kind == "better":
        amount = f"**{abs(v.pct):.0f} % weniger**" if v.pct is not None else f"**{abs(v.diff):.0f} weniger**"
        st.success(f"✅ **{label}**: im Mittel {amount} Kosten ({v.diff:+.0f} je Instanz, Standardfehler {v.se:.0f}).")
    elif v.kind == "worse":
        amount = f"**{v.pct:.0f} % mehr**" if v.pct is not None else f"**{v.diff:.0f} mehr**"
        st.warning(f"⚠️ **{label}**: im Mittel {amount} Kosten ({v.diff:+.0f} je Instanz, Standardfehler {v.se:.0f}).")
    else:
        st.info(f"ℹ️ Kein klarer Unterschied bei **{label}**: die Differenz ({v.diff:+.0f} Kosten, gemittelt über die Instanzen) liegt innerhalb des Rauschens (Standardfehler {v.se:.0f}).")


st.markdown("**Urteil über die Stichprobe** (gepaarte Differenz je Instanz, klar ab mehr als zwei Standardfehlern)")
v_reactive = E.verdict(samp, "configured", "reactive")
v_exact = E.verdict(samp, "configured", "exact")
_show_verdict("Eingestellte Vorschau gegen rein reaktiv", v_reactive)
_show_verdict("Eingestellte Vorschau gegen das Optimum", v_exact)

with pdf_slot:
    st.download_button(
        "📄 Ergebnis als PDF herunterladen",
        data=generate_lcr_pdf(p, int(seed), inst, outcomes, diag, kstar, sample=samp, costs=costs),
        file_name="leercontainer_ergebnis.pdf", mime="application/pdf", key="primary_pdf_download",
        help="Szenario, Ausprägungsvergleich, Diagnose, Kosten-über-k-Kurve und die Stichprobe mit Urteil.")

st.markdown("---")

# ---------------------------------------------------------------------------------------------------
# Vorschau im Vergleich
# ---------------------------------------------------------------------------------------------------
with st.expander("🔧 Wie wir das erreichen – Vorschau im Vergleich"):
    tabs = st.tabs([o.label for o in outcomes] + ["📊 Vergleich"])
    for tab, outcome in zip(tabs, outcomes):
        with tab:
            render_mode_panel(f"tab_{outcome.key}", outcome, outcomes, inst, net)
    with tabs[3]:
        rows = []
        for o in outcomes:
            r = o.result
            gap = 100.0 * (r.total - full.result.total) / full.result.total if full.result.total else 0.0
            rows.append({"Ausprägung": o.label, "Vorschau k": o.k, "Gesamtkosten": round(r.total), "davon Notleasing": round(r.shortfall_cost),
                        "davon Transport+Halten": round(r.transport + r.hold), "Abstand zum Optimum": f"{gap:.1f} %"})
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        st.plotly_chart(V.comparison_curve_figure(costs, outcomes), width="stretch", key="comparison_curve_chart")
        st.caption("Eine Instanz, drei Ausprägungen einer einzigen Reglerfamilie: dasselbe Fenster-Prinzip mit k=0 (rein reaktiv), dem eingestellten k und k=Perioden-1 (volle Vorschau = Optimum).")

with st.expander("Wie funktioniert diese Demo?"):
    st.markdown(
        """
**Das Netz.** Ein Zeit-Raum-Netz aus Häfen × Perioden. Jeder Hafen hat eine Netto-Einspeisung je Periode (positiv = freiwerdende Leercontainer, negativ = Bedarf), über den Horizont auf Summe 0
zentriert (kein globaler Dauerüberschuss/-mangel). Haltekanten (ein Hafen zur nächsten Periode) kosten wenig, Transportkanten (ein Hafen zu einem anderen) kosten distanzabhängig und brauchen eine
**Vorlaufzeit** = Distanz/Geschwindigkeit (aufgerundet auf mindestens 1 Periode) - nichts kann rückwärts in der Zeit fließen. Statt einer harten Bilanzpflicht gibt es eine **Notleasing-Kante**:
unbefriedigter Bedarf löst eine feste Strafe je Container aus, realistisch gedeutet als kurzfristiges Zumieten/Chartern. Das macht das Modell immer lösbar, auch wenn ein Bedarf durch die
Zeitstruktur real nicht mehr rechtzeitig erreichbar ist.

**Die eine Reglerfamilie: das Vorschau-Fenster k.** Bei jeder Periode wird derselbe Min-Cost-Flow gelöst, aber nur über das Fenster [t, t+k]; ausgeführt werden nur die bei t abgehenden
Entscheidungen, dann rollt die Planung einen Schritt weiter (rollierender Horizont). k=0 kennt nur die gerade abgelaufene Periode (rein reaktiv), k=Perioden-1 kennt von Anfang an den ganzen
Horizont - das ist bereits das exakte Optimum, **kein separater Exakt-Algorithmus nötig**: derselbe Löser, nur mit maximalem Fenster.

**Faustregel k* ≈ 1,6 × mittlere Vorlaufzeit.** Die Vorlaufzeit ist die Zeit, die eine Transport-Entscheidung zum Wirken braucht; die nötige Vorschau skaliert mit ihr, nicht mit dem ganzen
Planungshorizont. Empirisch geprüft (siehe Kurve oben), nicht bewiesen - der Regler bleibt frei einstellbar, die Faustregel ist nur eine Marke.

**Grenzen dieses Modells** (bewusst so gewählt, damit die Aussage ehrlich bleibt):

- Die Vorschau ist **perfekt** innerhalb des Fensters (kein Prognosefehler) - das misst den **Wert von Information**, nicht Robustheit gegen Prognoseunschärfe.
- **Kein struktureller Dauerüberschuss/-mangel** (Summe 0 je Instanz); echte globale Ungleichgewichte (z. B. ein starkes Export-Import-Ungleichgewicht einer Region) sind nicht modelliert.
- **Transport- und Lagerkapazität sind unbegrenzt** (kein Wettbewerb mit bezahlter Fracht um Schiffsraum, keine Yard-Grenze).
- **Vorlaufzeiten sind deterministisch** (keine Fahrzeitschwankung).
- Alle Zahlen sind **Größenordnungen aus einem vereinfachten Modell, keine Messung an echten Reedereidaten.**
        """
    )

with st.expander("📐 Mathematische Formulierung"):
    st.markdown(
        r"""
**Zeit-Raum-Netz.** Knoten $(p, t)$ für Hafen $p \in \{1, \dots, P\}$, Periode $t \in \{0, \dots, T-1\}$; Netto-Einspeisung $b(p, t)$, über den Horizont zentriert auf $\sum_{p,t} b(p,t) = 0$.

**Kanten.** Haltekante $(p, t) \to (p, t+1)$, Kosten $h$ je Einheit. Transportkante $(p, t) \to (q, t + \mathrm{lead}(p,q))$, Kosten $c \cdot \mathrm{dist}(p,q)$ je Einheit, mit
$\mathrm{lead}(p,q) = \max(1, \mathrm{round}(\mathrm{dist}(p,q) / v))$ Perioden ($v$ = Geschwindigkeit). Fehlmengen-Kante an jedem Bedarfsknoten, Kosten Strafe $\pi$ je Einheit statt harter
Kapazitätsgrenze - das Min-Cost-Flow-Problem ist damit immer lösbar.

**Exakt.** Ein einziger Min-Cost-Flow über den ganzen Horizont $t \in \{0, \dots, T-1\}$ liefert das globale Optimum.

**Heuristik(k).** Löse bei jeder Periode $t$ denselben Min-Cost-Flow, aber nur über die Knoten mit Zeitindex in $[t, \min(t+k, T-1)]$; führe nur die bei $t$ abgehenden Kanten aus, wiederhole für
$t+1$. Für $k = T-1$ ab $t=0$ reproduziert das exakt den einmaligen globalen Solve (geprüft, siehe `tests/test_rolling.py`).

**Löser.** Sukzessive kürzeste (erweiternde) Wege via Dijkstra mit Potentialen (Johnson-Technik): das Ausgangsnetz hat nur nichtnegative Kosten, die Potentiale starten bei 0 und bleiben danach
nichtnegativ, Dijkstra bleibt also korrekt anwendbar. Eine SPFA/Warteschlangen-Bellman-Ford-Variante entartet auf dieser Kantenstruktur (viele negative Restkanten nach Augmentierungen) schon bei
kleinen Instanzen zu unbrauchbarer Laufzeit.

**Faustregel.** $k^\ast = \min(T-1, \max(0, \mathrm{round}(1{,}6 \cdot \overline{\mathrm{lead}})))$ mit der mittleren Vorlaufzeit $\overline{\mathrm{lead}}$ über alle geordneten Hafenpaare.

**Vergleich über Instanzen.** Für eine Ausprägung gegen eine Referenz auf denselben Instanzen $i = 1, \dots, N$ ist $\Delta_i$ die Differenz der Gesamtkosten (negativ = billiger); berichtet
werden Mittel und Standardfehler der gepaarten Differenz. Ein Unterschied gilt als klar, wenn $|\bar\Delta| > 2 \, \mathrm{SE}(\Delta)$.

Implementiert in `lcr_flow.py` (Min-Cost-Flow), `lcr_rolling.py` (rollierender Horizont), `lcr_scenario.py` (Häfen, Vorlaufzeiten, Aufkommen) und `lcr_evaluation.py` (Stichprobe, Kurve, Urteil,
Diagnose).
        """
    )

st.markdown("---")

st.caption(
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning. Interesse an einer maßgeschneiderten Lösung für "
    "Ihr Unternehmen? [Kontakt aufnehmen](https://sebastianhanisch.net/kontakt.html)"
)
