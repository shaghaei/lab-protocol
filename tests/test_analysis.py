import pytest

from app.analysis import assess_group, class_stats, find_digit_swap, robust_z, station_deviations
from app.calc import Titration, evaluate_group
from app.experiments import NAOH_TITER as EXP


def clean_class():
    return [0.987, 0.988, 0.986, 0.987, 0.989, 0.985, 0.988, 0.987]


def test_class_stats_uses_minimum_spread():
    stats = class_stats(clean_class(), EXP)
    assert stats.median_f == pytest.approx(0.987)
    assert stats.spread_f == pytest.approx(EXP.min_spread_f)


def test_too_small_class_gives_no_stats():
    assert class_stats([0.99, 0.98], EXP) is None


def test_outlier_low_is_flagged_with_causes():
    stats = class_stats(clean_class(), EXP)
    ts = [Titration(0.40844, 0.0, 20.45)] * 3  # f ~ 0.978
    g = evaluate_group(ts, EXP)
    findings = assess_group(g, ts, 1, stats, {}, EXP)
    low = [f for f in findings if f.kind == "outlier_low"]
    assert low and "Endpoint overshot" in low[0].causes[0]


def test_station_effect_is_named_first():
    stats = class_stats(clean_class(), EXP)
    stations = station_deviations({4: [1.000, 0.999, 1.001]}, stats)
    assert stations[4][2]
    ts = [Titration(0.40844, 0.0, 19.98)] * 3  # f ~ 1.001
    g = evaluate_group(ts, EXP)
    findings = assess_group(g, ts, 4, stats, stations, EXP)
    high = [f for f in findings if f.kind == "outlier_high"][0]
    assert high.causes[0].startswith("Equipment at station 4")


def test_digit_swap_is_detected():
    # f = 0.987 for all three; the true end reading of titration 2 is 21.24 mL
    ts = [
        Titration(0.4100, 0.20, 20.54),
        Titration(0.4200, 0.40, 22.14),  # typo: digits 1 and 2 swapped
        Titration(0.4150, 0.10, 20.69),
    ]
    finding = find_digit_swap(ts, EXP)
    assert finding is not None
    assert "21.24" in finding.message


def test_consistent_titrations_have_no_swap():
    ts = [Titration(0.40844, 0.0, 20.00)] * 3
    assert find_digit_swap(ts, EXP) is None


def test_robust_z_sign():
    stats = class_stats(clean_class(), EXP)
    assert robust_z(0.997, stats) > 3
