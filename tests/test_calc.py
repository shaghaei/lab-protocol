import pytest

from app.calc import Titration, concentration_mol_l, evaluate_group, expected_volume_ml, validate_titration
from app.experiments import NAOH_TITER as EXP


def test_concentration_hand_example():
    # 0.40844 g KHP = 2.000 mmol; 20.00 mL -> exactly 0.1000 mol/L
    assert concentration_mol_l(0.40844, 20.00, EXP) == pytest.approx(0.1000, abs=1e-6)


def test_volume_from_readings():
    assert Titration(0.4, 0.35, 20.85).volume_ml == pytest.approx(20.50)


def test_group_mean_and_rsd():
    ts = [Titration(0.40844, 0.00, 20.00)] * 3
    g = evaluate_group(ts, EXP)
    assert g.mean_factor == pytest.approx(1.0, abs=1e-6)
    assert g.rsd_percent == pytest.approx(0.0, abs=1e-9)


def test_expected_volume():
    assert expected_volume_ml(0.40844, EXP) == pytest.approx(20.00, abs=1e-3)


def test_milligram_entry_is_blocked_with_hint():
    errors, _ = validate_titration(Titration(408.4, 0.0, 20.0), EXP, 1)
    assert any("milligrams" in e for e in errors)


def test_swapped_readings_are_blocked():
    errors, _ = validate_titration(Titration(0.4, 20.0, 0.5), EXP, 1)
    assert any("swapped" in e for e in errors)


def test_reading_above_capacity_is_blocked():
    errors, _ = validate_titration(Titration(0.4, 0.0, 55.0), EXP, 1)
    assert errors


def test_implausible_volume_gives_warning_not_error():
    errors, warnings = validate_titration(Titration(0.40844, 0.0, 35.0), EXP, 1)
    assert not errors
    assert warnings
