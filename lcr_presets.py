"""Regler-Spezifikation, Permalink, Presets und Seed-Knopf (Standardmuster aus dem OR-Demo-Portfolio,
siehe rfr_presets.py in reefer-demo).

Ein Regler hat eine BERECHNETE Grenze: das Vorschau-Fenster k (höchstens Perioden - 1). `clamp_settings`
begrenzt es, statt es zu verwerfen; die App ruft es vor dem Erzeugen der Regler auf (Permalink, Preset,
geänderte Periodenzahl) - wie beim Puffer-Regler der Reefer-Demo."""
import math
import random
from dataclasses import dataclass
from typing import Callable, Optional

import streamlit as st

import lcr_constants as C


def _int_text(value):
    return str(int(value))


@dataclass(frozen=True)
class SettingSpec:
    url_param: str
    caster: Callable
    default: object
    lo: Optional[float] = None
    hi: Optional[float] = None
    step: Optional[int] = None
    encoder: Callable = _int_text


SETTING_SPECS = {
    "n_ports_slider": SettingSpec("np", int, C.N_PORTS_DEFAULT, *C.N_PORTS_RANGE, 1),
    "n_periods_slider": SettingSpec("nt", int, C.N_PERIODS_DEFAULT, *C.N_PERIODS_RANGE, 1),
    "speed_slider": SettingSpec("sp", int, C.SPEED_DEFAULT, *C.SPEED_RANGE, C.SPEED_STEP),
    "sigma_slider": SettingSpec("sg", int, C.SIGMA_DEFAULT, *C.SIGMA_RANGE, 1),
    "penalty_slider": SettingSpec("pn", int, C.PENALTY_DEFAULT, *C.PENALTY_RANGE, C.PENALTY_STEP),
    "k_slider": SettingSpec("k", int, None, *C.K_RANGE, 1),  # Default hängt von n_periods ab (Faustregel), siehe init_session_state_defaults
    "seed_input": SettingSpec("seed", int, C.SEED_DEFAULT, *C.SEED_RANGE, 1),
}

PRESET_STATE_KEYS = {
    "n_ports": "n_ports_slider", "n_periods": "n_periods_slider", "speed": "speed_slider", "sigma": "sigma_slider",
    "penalty": "penalty_slider", "k": "k_slider", "seed": "seed_input",
}


def bounds(state_key):
    spec = SETTING_SPECS[state_key]
    return spec.lo, spec.hi


def parse_setting(spec, raw):
    """Wert aus der Adresszeile: umwandeln, auf den Bereich begrenzen, auf die Schrittweite runden.
    None, wenn er sich nicht auswerten lässt."""
    try:
        value = spec.caster(raw)
    except (ValueError, TypeError):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if spec.lo is not None:
        value = max(spec.lo, value)
    if spec.hi is not None:
        value = min(spec.hi, value)
    if spec.step and spec.step > 1 and spec.lo is not None:
        value = spec.lo + round((value - spec.lo) / spec.step) * spec.step
        value = min(spec.hi, value)
    return value


def k_star_default(n_periods, speed):
    """Default für das Vorschau-Fenster: die Faustregel k* zur mittleren Vorlaufzeit EINES
    typischen Netzes bei dieser Geschwindigkeit (dist ~ 100/sqrt(2) im Mittel auf der 100x100-Karte,
    grob); nur für den Regler-Default, nicht für die Auswertung (die rechnet k* live pro Instanz)."""
    approx_lead = max(1.0, 45.0 / speed)
    return min(n_periods - 1, max(1, round(C.K_STAR_FACTOR * approx_lead)))


def k_max(n_periods):
    return max(0, n_periods - 1)


def clamp_settings(n_periods, k):
    """Vorschau-Fenster k auf seine berechnete Grenze (Perioden - 1) begrenzt, nicht verworfen."""
    return max(0, min(int(k), k_max(int(n_periods))))


def limit_dependent_state():
    """Begrenzt das abhängige Vorschau-Fenster im session_state (vor dem Erzeugen der Widgets aufrufen)."""
    s = st.session_state
    s["k_slider"] = clamp_settings(s["n_periods_slider"], s["k_slider"])


def init_session_state_defaults():
    for state_key, spec in SETTING_SPECS.items():
        if state_key not in st.session_state:
            if state_key == "k_slider":
                st.session_state[state_key] = k_star_default(C.N_PERIODS_DEFAULT, C.SPEED_DEFAULT)
            else:
                st.session_state[state_key] = spec.default


def load_permalink_settings():
    if "permalink_loaded" in st.session_state:
        return
    qp = st.query_params
    for state_key, spec in SETTING_SPECS.items():
        if spec.url_param in qp:
            value = parse_setting(spec, qp[spec.url_param])
            if value is not None:
                st.session_state[state_key] = value
    if "k_slider" not in st.session_state:
        n_periods = st.session_state.get("n_periods_slider", C.N_PERIODS_DEFAULT)
        speed = st.session_state.get("speed_slider", C.SPEED_DEFAULT)
        st.session_state["k_slider"] = k_star_default(n_periods, speed)
    st.session_state["permalink_loaded"] = True


def sync_query_params(values):
    """values: dict state_key -> aktueller Wert (aus den Widgets)."""
    try:
        for state_key, value in values.items():
            st.query_params[SETTING_SPECS[state_key].url_param] = SETTING_SPECS[state_key].encoder(value)
    except Exception:
        pass


def apply_preset(name):
    for field, state_key in PRESET_STATE_KEYS.items():
        st.session_state[state_key] = C.PRESETS[name][field]


def randomize_seed():
    """Würfelt einen neuen Seed für die Häfen und das Aufkommen."""
    st.session_state["seed_input"] = random.randint(*C.SEED_RANGE)
