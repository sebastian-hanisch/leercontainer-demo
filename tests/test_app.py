"""AppTest: Skelett und Footer, jedes Preset, Permalink mit berechneter Grenze, alle Regler an Min und
Max, Kennzahlen im 2 x 2-Raster, die bedingte Meldung in allen Zustaenden, Urteil in allen Zustaenden,
Vergleichstabelle, PDF, Texte."""
import pathlib

import pytest
from streamlit.proto.Metric_pb2 import Metric as MetricProto
from streamlit.testing.v1 import AppTest

import lcr_constants as C
import lcr_evaluation as E
import lcr_stories as ST
from lcr_presets import k_star_default, SETTING_SPECS

APP = str(pathlib.Path(__file__).resolve().parent.parent / "app.py")
FOOTER = ("Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
          "Operations Research und Machine Learning. Interesse an einer maßgeschneiderten Lösung für "
          "Ihr Unternehmen? [Kontakt aufnehmen](https://sebastianhanisch.net/kontakt.html)")


@pytest.fixture(autouse=True)
def clean_cache():
    """st.cache_data ist prozessweit: Tests, die Einstellungen aendern, duerfen keine
    zwischengespeicherten Ergebnisse anderer Tests sehen."""
    import streamlit as st
    st.cache_data.clear()
    yield


def fresh(**query):
    at = AppTest.from_file(APP, default_timeout=180)
    for k, v in query.items():
        at.query_params[k] = v
    at.run()
    assert not at.exception, at.exception
    return at


def set_and_run(at, **values):
    for key, value in values.items():
        (at.number_input if key.endswith("_input") else at.slider)(key=key).set_value(value)
    at.run()
    assert not at.exception, at.exception
    return at


def main_metrics(at):
    return [(m.label, m.value, m.delta) for m in at.metric[:4]]


def click(at, label):
    next(b for b in at.button if b.label == label).click().run()
    assert not at.exception, at.exception
    return at


def message(at, needle):
    for group in (at.success, at.warning, at.info):
        for x in group:
            if needle in x.value:
                return x.value
    return None


def _fmt(v):
    return f"{v:,.0f}".replace(",", ".")


# ---------------------------------------------------------------------------------------------------
# Skelett
# ---------------------------------------------------------------------------------------------------
def test_skeleton_and_footer():
    at = fresh()
    assert [h.value for h in at.sidebar.header] == ["⚙️ Einstellungen"]                # genau EIN Header
    assert len(at.title) == 1 and "Leercontainer" in at.title[0].value
    assert any(v.value.startswith("## 🎯") for v in at.markdown)
    assert any(v.value.startswith("### 📐") for v in at.markdown)
    assert [e.label for e in at.expander] == ["🔧 Wie wir das erreichen – Vorschau im Vergleich", "Wie funktioniert diese Demo?", "📐 Mathematische Formulierung"]
    assert any(c.value == FOOTER for c in at.caption)
    presets = [b.label for b in at.button if b.label in C.PRESETS]
    assert presets == list(C.PRESETS) and len(presets) == 5 and all(len(n) <= 22 for n in presets)
    assert [s.label for s in at.sidebar.slider][:5] == ["Häfen", "Perioden", "Schiffsgeschwindigkeit (relativ)", "Volatilität des Aufkommens", "Notleasing-Kosten je Container"]
    assert "Vorschau-Fenster k" in [s.label for s in at.sidebar.slider]
    assert [n.label for n in at.sidebar.number_input] == ["Seed"] and any(b.label == "🎲 Neue Häfen" for b in at.sidebar.button)


def test_main_metrics_are_2x2_with_signed_deltas_against_reactive():
    at = fresh()
    k_default = k_star_default(C.N_PERIODS_DEFAULT, C.SPEED_DEFAULT)
    p = E.Params(C.N_PORTS_DEFAULT, C.N_PERIODS_DEFAULT, C.SPEED_DEFAULT, C.SIGMA_DEFAULT, C.PENALTY_DEFAULT, k_default)
    inst = E.make_instance(p, C.SEED_DEFAULT)
    outcomes = E.run_outcomes(inst, p)
    by_key = {o.key: o for o in outcomes}
    reactive, configured, full = by_key[C.MODE_REACTIVE].result, by_key[C.MODE_CONFIGURED].result, by_key[C.MODE_FULL].result

    labels = [m[0] for m in main_metrics(at)]
    assert labels == ["Gesamtkosten", "davon Notleasing", "davon Transport+Halten", "Abstand zum Optimum"]
    values = [m[1] for m in main_metrics(at)]
    gap = 100.0 * (configured.total - full.total) / full.total
    assert values == [_fmt(configured.total), _fmt(configured.shortfall_cost), _fmt(configured.transport + configured.hold), f"{gap:.1f} %"]
    deltas = [m[2] for m in main_metrics(at)]
    assert deltas[:3] == [f"{configured.total - reactive.total:+,.0f}".replace(",", "."), f"{configured.shortfall_cost - reactive.shortfall_cost:+,.0f}".replace(",", "."),
                          f"{(configured.transport + configured.hold) - (reactive.transport + reactive.hold):+,.0f}".replace(",", ".")]
    # nur die Gesamtkosten sind per Monotonie garantiert nie teurer als rein reaktiv (Farbe folgt dem
    # Vorzeichen des Deltas, "inverse": negativ = gruen); einzelne Bestandteile (z. B. Transport+Halten)
    # koennen dafuer sogar steigen, wenn dadurch mehr Notleasing vermieden wird - keine Garantie je Kennzahl.
    def _expected_color(delta):
        if delta < 0:
            return MetricProto.GREEN
        if delta > 0:
            return MetricProto.RED
        return MetricProto.GRAY

    raw_deltas = [configured.total - reactive.total, configured.shortfall_cost - reactive.shortfall_cost, (configured.transport + configured.hold) - (reactive.transport + reactive.hold)]
    assert [m.proto.color for m in at.metric[:3]] == [_expected_color(d) for d in raw_deltas]
    assert at.metric[0].proto.color == MetricProto.GREEN                              # Gesamtkosten: per Monotonie garantiert


def test_charts_are_present_with_unique_keys():
    at = fresh()
    charts = at.get("plotly_chart")
    keys = [c.key for c in charts]
    assert len(set(keys)) == len(keys) and all(keys) and len(keys) == 6              # Hauptkarte, Kosten-Kurve, 3 Tab-Karten, Vergleichskurve


# ---------------------------------------------------------------------------------------------------
# Presets, Permalink
# ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("name", list(C.PRESETS))
def test_every_preset_loads_within_widget_bounds_and_shows_its_story(name):
    at = fresh()
    click(at, name)
    preset = C.PRESETS[name]
    assert at.slider(key="n_ports_slider").value == preset["n_ports"] and at.slider(key="n_periods_slider").value == preset["n_periods"]
    assert at.slider(key="speed_slider").value == preset["speed"] and at.slider(key="sigma_slider").value == preset["sigma"]
    assert at.slider(key="penalty_slider").value == preset["penalty"] and at.slider(key="k_slider").value == preset["k"]
    assert at.number_input(key="seed_input").value == preset["seed"]
    for state_key, spec in SETTING_SPECS.items():
        if spec.lo is not None and state_key != "k_slider":
            value = at.session_state[state_key]
            assert spec.lo <= value <= spec.hi

    p = E.Params(preset["n_ports"], preset["n_periods"], preset["speed"], preset["sigma"], preset["penalty"], preset["k"])
    shown = E.instance_result(p, preset["seed"])
    for ok, text in ST.criteria(name, [shown]):
        assert ok, f"{name}: {text}"

    gap = 100.0 * (shown.configured - shown.exact) / shown.exact if shown.exact else 0.0
    assert main_metrics(at)[3][1] == f"{gap:.1f} %"


def test_permalink_is_clamped_snapped_and_ignores_garbage():
    at = fresh(np="99", sg="abc", sp="17", vw="junk", nt="3")
    assert at.slider(key="n_ports_slider").value == C.N_PORTS_RANGE[1]                # geklemmt
    assert at.slider(key="sigma_slider").value == C.SIGMA_DEFAULT                     # Muell ignoriert
    assert at.slider(key="speed_slider").value == 15                                  # auf Schrittweite 5 gerundet
    assert at.slider(key="n_periods_slider").value == C.N_PERIODS_RANGE[0]            # unter der Spezifikationsuntergrenze geklemmt


def test_permalink_limits_the_preview_window_instead_of_dropping_it():
    at = fresh(nt="6", k="13")
    assert at.slider(key="n_periods_slider").value == 6
    assert at.slider(key="k_slider").value == 5 and at.slider(key="k_slider").max == 5


def test_permalink_roundtrip_reflects_settings():
    at = fresh(np="6", nt="8", sp="30", sg="5", pn="450", k="3", seed="11")
    values = {k: at.session_state[k] for k in SETTING_SPECS}
    assert values == {"n_ports_slider": 6, "n_periods_slider": 8, "speed_slider": 30, "sigma_slider": 5, "penalty_slider": 450, "k_slider": 3, "seed_input": 11}
    for key, spec in SETTING_SPECS.items():
        got = at.query_params[spec.url_param]
        got = got[0] if isinstance(got, list) else got
        assert got == spec.encoder(values[key]), key


def test_changing_period_count_limits_the_preview_window():
    at = fresh()
    at = set_and_run(at, n_periods_slider=14)
    at = set_and_run(at, k_slider=13)
    assert at.slider(key="k_slider").value == 13 and at.slider(key="k_slider").max == 13
    at = set_and_run(at, n_periods_slider=6)
    assert at.slider(key="k_slider").value == 5 and at.slider(key="k_slider").max == 5


def test_new_ports_button_changes_only_the_seed():
    at = fresh()
    before = {k: at.session_state[k] for k in SETTING_SPECS if k != "seed_input"}
    click(at, "🎲 Neue Häfen")
    assert {k: at.session_state[k] for k in SETTING_SPECS if k != "seed_input"} == before
    assert C.SEED_RANGE[0] <= at.session_state["seed_input"] <= C.SEED_RANGE[1]


# ---------------------------------------------------------------------------------------------------
# Regler an den Grenzen
# ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("key,value", [("n_ports_slider", 3), ("n_ports_slider", 8), ("n_periods_slider", 6), ("n_periods_slider", 14), ("speed_slider", 10), ("speed_slider", 40),
                                       ("sigma_slider", 1), ("sigma_slider", 7), ("penalty_slider", 50), ("penalty_slider", 800), ("k_slider", 0)])
def test_every_slider_works_at_its_minimum_and_maximum(key, value):
    at = set_and_run(fresh(), **{key: value})
    assert at.session_state[key] == value and len(at.metric) >= 4


def test_k_slider_works_at_its_maximum():
    at = fresh()
    kmax = at.slider(key="k_slider").max
    at = set_and_run(at, k_slider=int(kmax))
    assert at.session_state["k_slider"] == int(kmax)


def test_extreme_combination_runs_without_exception():
    at = fresh(np="3", nt="6", sp="10", sg="1", pn="50", k="0")
    assert not at.exception and at.slider(key="k_slider").value == 0
    at = fresh(np="8", nt="14", sp="40", sg="7", pn="800", k="13")
    assert not at.exception and at.slider(key="k_slider").value == 13


# ---------------------------------------------------------------------------------------------------
# Bedingte Meldung
# ---------------------------------------------------------------------------------------------------
def test_message_too_short_when_k_below_mean_lead():
    at = set_and_run(fresh(), speed_slider=10, k_slider=0)                             # lange Vorlaufzeit, k=0
    msg = message(at, "kürzer als die mittlere Vorlaufzeit")
    assert msg is not None and "Abstand zum Optimum" in msg


def test_message_near_optimal_at_full_lookahead():
    at = fresh()
    kmax = at.slider(key="k_slider").max
    at = set_and_run(at, k_slider=int(kmax))
    msg = message(at, "kaum noch Luft nach oben")
    assert msg is not None


def test_message_ok_state_names_the_gap():
    at = fresh()                                                                       # Default: k = Faustregel, weder zu kurz noch nahe am Optimum
    msg = message(at, "Abstand zum Optimum")
    assert msg is not None and "kürzer" not in msg and "Luft" not in msg


# ---------------------------------------------------------------------------------------------------
# Kernabschnitt: Urteil
# ---------------------------------------------------------------------------------------------------
def test_three_verdict_sentences_with_the_right_labels():
    at = fresh()
    texts = [x.value for group in (at.success, at.warning, at.info) for x in group if "gegen rein reaktiv" in x.value or "gegen das Optimum" in x.value]
    assert len(texts) == 2
    assert any("Eingestellte Vorschau gegen rein reaktiv" in t for t in texts)
    assert any("Eingestellte Vorschau gegen das Optimum" in t for t in texts)


def _fake_verdict(monkeypatch, kind, pct):
    import lcr_evaluation as E_mod
    monkeypatch.setattr(E_mod, "verdict", lambda res, field, reference="exact": E_mod.Verdict(kind, -3.0 if kind == "better" else 3.0, 1.0, pct, 20, field, reference))


@pytest.mark.parametrize("kind,pct,expected", [
    ("better", -40.0, "im Mittel **40 % weniger** Kosten (-3 je Instanz, Standardfehler 1)."),
    ("better", None, "im Mittel **3 weniger** Kosten (-3 je Instanz, Standardfehler 1)."),
    ("worse", 25.0, "im Mittel **25 % mehr** Kosten (+3 je Instanz, Standardfehler 1)."),
    ("worse", None, "im Mittel **3 mehr** Kosten (+3 je Instanz, Standardfehler 1)."),
])
def test_verdict_sentences_in_the_four_variants(monkeypatch, kind, pct, expected):
    _fake_verdict(monkeypatch, kind, pct)
    at = fresh()
    texts = [x.value for x in (at.success if kind == "better" else at.warning) if "im Mittel" in x.value and "Kosten" in x.value]
    assert len(texts) >= 1 and all(expected in t for t in texts[:1])


def test_verdict_unclear(monkeypatch):
    _fake_verdict(monkeypatch, "unclear", 1.0)
    at = fresh()
    us = [i.value for i in at.info if "Kein klarer Unterschied" in i.value]
    assert len(us) == 2 and all("Rauschens" in u for u in us)


def test_sample_does_not_depend_on_the_seed():
    at = fresh()
    before = [c.value for c in at.caption if "Basis:" in c.value and "Instanzen" in c.value]
    at = set_and_run(at, seed_input=5)
    after = [c.value for c in at.caption if "Basis:" in c.value and "Instanzen" in c.value]
    assert before == after and len(before) >= 1


# ---------------------------------------------------------------------------------------------------
# Vorschau im Vergleich, PDF, Texte
# ---------------------------------------------------------------------------------------------------
def test_comparison_table_has_a_row_per_outcome():
    at = fresh()
    df = at.dataframe[0].value
    assert list(df["Vorschau k"]) == [0, at.session_state["k_slider"], at.slider(key="k_slider").max]
    assert list(df.columns) == ["Ausprägung", "Vorschau k", "Gesamtkosten", "davon Notleasing", "davon Transport+Halten", "Abstand zum Optimum"]
    assert df["Abstand zum Optimum"].iloc[-1] == "0.0 %"                              # volle Vorschau = Optimum


def test_each_mode_tab_shows_metrics_and_a_map():
    at = fresh()
    tab_metrics = at.metric[4:]
    assert len(tab_metrics) == 12                                                     # 3 Tabs x 4 Kennzahlen
    charts = at.get("plotly_chart")
    assert sum(1 for c in charts if c.key.startswith("tab_")) == 3                    # eine Karte je Tab


def test_pdf_download_button_is_offered():
    at = fresh()
    buttons = at.get("download_button")
    assert len(buttons) == 1 and buttons[0].proto.label == "📄 Ergebnis als PDF herunterladen"


def test_texts_state_the_model_the_rule_of_thumb_and_the_limits():
    at = fresh()
    text = "\n".join(m.value for m in at.expander[1].markdown)
    for needle in ("Notleasing-Kante", "Vorschau-Fenster k", "Faustregel", "kein separater Exakt-Algorithmus", "Wert von Information", "Größenordnungen aus einem vereinfachten Modell"):
        assert needle in text, needle
    math_text = "\n".join(m.value for m in at.expander[2].markdown)
    for needle in ("Zeit-Raum-Netz", "Dijkstra", "SPFA", "k^\\ast", "2 \\, \\mathrm{SE}"):
        assert needle in math_text, needle
