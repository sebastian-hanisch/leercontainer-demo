"""Regler-Spezifikation, Permalink (Parsen/Begrenzen/Runden), berechnete Grenze des Vorschau-Fensters,
Presets, Seed-Knopf."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import lcr_constants as C  # noqa: E402
import lcr_presets as P  # noqa: E402


def test_k_max_tracks_periods_minus_one():
    assert P.k_max(10) == 9 and P.k_max(6) == 5 and P.k_max(1) == 0 and P.k_max(0) == 0


def test_clamp_settings_limits_instead_of_dropping():
    assert P.clamp_settings(10, 13) == 9
    assert P.clamp_settings(10, -3) == 0
    assert P.clamp_settings(10, 4) == 4


@pytest.mark.parametrize("raw,expected", [("abc", None), ("", None), ("nan", None), ("inf", None)])
def test_parse_setting_rejects_garbage(raw, expected):
    spec = P.SETTING_SPECS["n_ports_slider"]
    assert P.parse_setting(spec, raw) == expected


def test_parse_setting_clamps_to_range():
    spec = P.SETTING_SPECS["n_ports_slider"]
    assert P.parse_setting(spec, "999") == C.N_PORTS_RANGE[1]
    assert P.parse_setting(spec, "-5") == C.N_PORTS_RANGE[0]


def test_parse_setting_snaps_to_step():
    spec = P.SETTING_SPECS["penalty_slider"]      # step 50, range 50..800
    assert P.parse_setting(spec, "123") == 100     # rundet auf den nächsten Schritt


def test_parse_setting_rounds_not_truncates_at_step_boundary():
    """Regressionstest: (Wert - Untergrenze) / Schrittweite = 1,6 muss auf 2 GERUNDET werden (150),
    nicht auf 1 abgeschnitten (100) - round() und int() stimmen nur zufällig überein, wenn der
    Bruchteil unter 0,5 liegt."""
    spec = P.SETTING_SPECS["penalty_slider"]       # step 50, lo 50
    assert P.parse_setting(spec, "130") == 150      # (130-50)/50 = 1.6 -> round = 2 -> 50 + 100


def test_k_star_default_applies_the_1_6_factor():
    """Regressionstest: der Default MUSS die Faustregel k* ~= 1,6 x Vorlaufzeit verwenden, nicht nur
    die (ungewichtete) Vorlaufzeit selbst."""
    # speed=45 -> approx_lead = max(1.0, 45/45) = 1.0 -> round(1.6 * 1.0) = round(1.6) = 2
    assert P.k_star_default(10, 45) == 2
    # speed=15 -> approx_lead = max(1.0, 45/15) = 3.0 -> round(1.6 * 3.0) = round(4.8) = 5
    assert P.k_star_default(10, 15) == 5


def test_k_star_default_is_within_bounds():
    for n_periods in range(6, 15):
        for speed in range(10, 41, 5):
            d = P.k_star_default(n_periods, speed)
            assert 0 <= d <= n_periods - 1


def test_apply_preset_sets_every_field():
    import streamlit as st
    st.session_state.clear()
    for name in C.PRESETS:
        P.apply_preset(name)
        preset = C.PRESETS[name]
        for field, state_key in P.PRESET_STATE_KEYS.items():
            assert st.session_state[state_key] == preset[field], (name, field)


def test_randomize_seed_stays_within_range():
    import streamlit as st
    st.session_state.clear()
    for _ in range(20):
        P.randomize_seed()
        assert C.SEED_RANGE[0] <= st.session_state["seed_input"] <= C.SEED_RANGE[1]


def test_bounds_matches_constants():
    assert P.bounds("n_ports_slider") == C.N_PORTS_RANGE
    assert P.bounds("penalty_slider") == C.PENALTY_RANGE


def test_every_preset_seed_and_k_are_within_their_own_bounds():
    for name, preset in C.PRESETS.items():
        assert C.SEED_RANGE[0] <= preset["seed"] <= C.SEED_RANGE[1]
        assert 0 <= preset["k"] <= preset["n_periods"] - 1
        assert C.N_PORTS_RANGE[0] <= preset["n_ports"] <= C.N_PORTS_RANGE[1]
        assert C.N_PERIODS_RANGE[0] <= preset["n_periods"] <= C.N_PERIODS_RANGE[1]
        assert C.SPEED_RANGE[0] <= preset["speed"] <= C.SPEED_RANGE[1]
        assert C.SIGMA_RANGE[0] <= preset["sigma"] <= C.SIGMA_RANGE[1]
        assert C.PENALTY_RANGE[0] <= preset["penalty"] <= C.PENALTY_RANGE[1]
