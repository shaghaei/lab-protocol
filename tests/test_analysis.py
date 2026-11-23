import pytest

from app.analysis import assess_group, class_stats, find_digit_swap, robust_z, station_deviations
from app.calc import evaluate_group
from app.experiments import BUILTINS, NAOH_TITER as EXP
from scripts.evaluate import evaluate


def clean_class():
    return [0.987, 0.988, 0.986, 0.987, 0.989, 0.985, 0.988, 0.987]


def test_class_stats_uses_minimum_spread():
    stats = class_stats(clean_class(), EXP)
    assert stats.median == pytest.approx(0.987)
    assert stats.spread == pytest.approx(EXP.min_spread)


def test_too_small_class_gives_no_stats():
    assert class_stats([0.99, 0.98], EXP) is None


def test_outlier_low_uses_experiment_causes():
    stats = class_stats(clean_class(), EXP)
    g = evaluate_group([{"m_KHP": 0.40844, "V_start": 0.0, "V_end": 20.45}] * 3, EXP)
    low = [f for f in assess_group(g, 1, stats, {}, EXP) if f.kind == "outlier_low"]
    assert low and low[0].causes[0] == EXP.causes_low[0]


def test_station_effect_is_named_first():
    stats = class_stats(clean_class(), EXP)
    stations = station_deviations({4: [1.000, 0.999, 1.001]}, stats)
    g = evaluate_group([{"m_KHP": 0.40844, "V_start": 0.0, "V_end": 19.98}] * 3, EXP)
    high = [f for f in assess_group(g, 4, stats, stations, EXP) if f.kind == "outlier_high"][0]
    assert high.causes[0].startswith("Equipment at station 4")


def test_digit_swap_is_detected():
    runs = [{"m_KHP": 0.4100, "V_start": 0.20, "V_end": 20.54},
            {"m_KHP": 0.4200, "V_start": 0.40, "V_end": 22.14},   # true 21.24
            {"m_KHP": 0.4150, "V_start": 0.10, "V_end": 20.69}]
    finding = find_digit_swap(evaluate_group(runs, EXP), EXP)
    assert finding is not None and "21.24" in finding.message


def test_consistent_runs_have_no_swap():
    runs = [{"m_KHP": 0.40844, "V_start": 0.0, "V_end": 20.0}] * 3
    assert find_digit_swap(evaluate_group(runs, EXP), EXP) is None


def test_robust_z_sign():
    assert robust_z(0.997, class_stats(clean_class(), EXP)) > 3


@pytest.mark.parametrize("exp", BUILTINS, ids=lambda e: e.id)
def test_synthetic_class_is_diagnosed(exp):
    detected, n_err, false_alarms, _, right = evaluate(exp)
    assert detected == n_err and false_alarms == 0 and right == n_err
