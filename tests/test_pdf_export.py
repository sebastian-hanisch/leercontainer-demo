"""PDF-Export: Sonderzeichen-Bereinigung (fpdf2 stürzt bei bestimmten Zeichen ab), Inhalt für jede
Diagnose-Art, mit und ohne Stichprobe/Kurve."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import lcr_constants as C  # noqa: E402
import lcr_evaluation as E  # noqa: E402
from lcr_pdf_export import diagnosis_text, generate_lcr_pdf, pdf_text, verdict_text  # noqa: E402


@pytest.mark.parametrize("char", ["–", "—", "−", "€", "≥", "≤", "→", "≈", "±", "⚠️", "✅", "ℹ️", "🙈", "👀", "🔮"])
def test_pdf_text_removes_every_known_crash_character(char):
    out = pdf_text(f"Text {char} Ende")
    out.encode("latin-1")                    # darf nicht scheitern
    assert char not in out


def test_pdf_text_keeps_umlauts():
    text = pdf_text("Länge Überschuss Mängel groß")
    assert text == "Länge Überschuss Mängel groß"


def test_pdf_text_is_idempotent_and_latin1_safe_for_arbitrary_unicode():
    weird = "Test 漢字 ✈ Ω" + "–€≥"
    out = pdf_text(weird)
    out.encode("latin-1")  # darf nicht scheitern (Rest wird ersetzt/entfernt)


def _scenario(seed=0, k=4):
    p = E.Params(5, 10, 22, 3, 200, k)
    inst = E.make_instance(p, seed)
    outcomes = E.run_outcomes(inst, p, record=True)
    full = next(o for o in outcomes if o.key == C.MODE_FULL)
    configured = next(o for o in outcomes if o.key == C.MODE_CONFIGURED)
    diag = E.diagnose(inst, p, configured.result, full.result.total)
    return p, inst, outcomes, diag


@pytest.mark.parametrize("k", [0, 4, 9])
def test_generate_pdf_runs_for_every_diagnosis_kind(k):
    p, inst, outcomes, diag = _scenario(seed=636, k=k)
    kstar = E.k_star(inst)
    pdf_bytes = generate_lcr_pdf(p, 636, inst, outcomes, diag, kstar)
    assert pdf_bytes[:5] == b"%PDF-" and len(pdf_bytes) > 1000


def test_generate_pdf_with_sample_and_costs():
    p, inst, outcomes, diag = _scenario(seed=636, k=4)
    kstar = E.k_star(inst)
    sample = E.sample(p, 10)
    costs = E.cost_curve(inst, p)
    pdf_bytes = generate_lcr_pdf(p, 636, inst, outcomes, diag, kstar, sample=sample, costs=costs)
    assert pdf_bytes[:5] == b"%PDF-"


def test_generate_pdf_at_extreme_settings_does_not_crash():
    p = E.Params(8, 14, 40, 7, 800, 13)
    inst = E.make_instance(p, 1)
    outcomes = E.run_outcomes(inst, p, record=True)
    full = next(o for o in outcomes if o.key == C.MODE_FULL)
    configured = next(o for o in outcomes if o.key == C.MODE_CONFIGURED)
    diag = E.diagnose(inst, p, configured.result, full.result.total)
    pdf_bytes = generate_lcr_pdf(p, 1, inst, outcomes, diag, E.k_star(inst))
    assert pdf_bytes[:5] == b"%PDF-"


def test_diagnosis_text_mentions_the_right_recommendation_per_kind():
    diag_short = E.Diagnosis("too_short", 50.0, 3.0, 1)
    diag_near = E.Diagnosis("near_optimal", 1.0, 3.0, 8)
    diag_ok = E.Diagnosis("ok", 15.0, 3.0, 3)
    assert "kürzer als die mittlere Vorlaufzeit" in pdf_text(diagnosis_text(diag_short))
    assert "kaum noch Luft" in pdf_text(diagnosis_text(diag_near))
    assert "15.0 %" in diagnosis_text(diag_ok)


def test_verdict_text_reports_percent_when_available_and_absolute_otherwise():
    v_pct = E.Verdict("better", -5.0, 1.0, -25.0, 10, "configured", "exact")
    v_abs = E.Verdict("worse", 5.0, 1.0, None, 10, "configured", "exact")
    assert "25 % weniger" in verdict_text(v_pct, "Label")
    assert "5 mehr" in verdict_text(v_abs, "Label")
