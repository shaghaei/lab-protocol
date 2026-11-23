import pytest

from app.calc import evaluate_group, run_result, validate_run
from app.experiments import BUILTINS, HYDRATE, HYDROGEN, NAOH_TITER, PIPETTE, VINEGAR


def test_naoh_hand_example():
    # 0.40844 g KHP = 2.000 mmol; 20.00 mL -> exactly 0.1000 mol/L -> f = 1
    run = {"m_KHP": 0.40844, "V_start": 0.0, "V_end": 20.0}
    assert run_result(run, NAOH_TITER) == pytest.approx(1.0, abs=1e-6)


def test_vinegar_hand_example():
    # 16.87 mL of NaOH (f 0.987) for 20 mL of a 1:10 dilution -> about 50 g/L
    run = {"V_sample": 20.0, "f_NaOH": 0.987, "V_start": 0.30, "V_end": 17.17}
    assert run_result(run, VINEGAR) == pytest.approx(49.99, abs=0.01)


def test_pipette_density_at_20_degrees():
    # 9.9820 g water at 20 °C (density 0.99820 g/mL) -> 10.000 mL
    run = {"m_empty": 50.0, "m_full": 59.9820, "T_water": 20.0}
    assert run_result(run, PIPETTE) == pytest.approx(10.000, abs=0.002)


def test_hydrate_pentahydrate():
    # 1.0000 g CuSO4·5H2O loses 0.3608 g water -> x = 5
    run = {"m_crucible": 20.0, "m_before": 21.0, "m_after": 20.6392}
    assert run_result(run, HYDRATE) == pytest.approx(5.0, abs=0.01)


def test_hydrogen_ideal_gas():
    # 1 mmol Mg gives 22.414 mL H2 at 0 °C and 1013.25 hPa -> 22.414 L/mol
    run = {"m_Mg": 0.024305, "V_gas": 22.414, "T_room": 0.0, "p_air": 1013.25}
    assert run_result(run, HYDROGEN) == pytest.approx(22.414, rel=1e-6)


@pytest.mark.parametrize("exp", BUILTINS, ids=lambda e: e.id)
def test_examples_are_valid_and_near_expected(exp):
    run = {q.key: q.example for q in exp.quantities}
    errors, warnings = validate_run(run, exp, 1)
    assert not errors and not warnings
    assert abs(run_result(run, exp) - exp.expected) / exp.expected < exp.tolerance_percent / 100


def test_milli_unit_hint():
    errors, _ = validate_run({"m_KHP": 410.0, "V_start": 0.0, "V_end": 20.0}, NAOH_TITER, 1)
    assert any("thousandth" in e for e in errors)


def test_constraint_blocks_swapped_readings():
    errors, _ = validate_run({"m_KHP": 0.41, "V_start": 20.0, "V_end": 0.5}, NAOH_TITER, 1)
    assert any("swapped" in e for e in errors)


def test_missing_value():
    errors, _ = validate_run({"m_KHP": None, "V_start": 0.0, "V_end": 20.0}, NAOH_TITER, 1)
    assert errors


def test_group_mean_and_rsd():
    runs = [{"m_KHP": 0.40844, "V_start": 0.0, "V_end": 20.0}] * 3
    g = evaluate_group(runs, NAOH_TITER)
    assert g.mean == pytest.approx(1.0, abs=1e-6)
    assert g.rsd_percent == pytest.approx(0.0, abs=1e-9)
