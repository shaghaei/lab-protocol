"""Class comparison, outlier flags, station analysis and likely causes.

All checks are rule-based and deterministic, and work for any experiment
definition. Each finding names the rule that produced it.
"""
from dataclasses import dataclass, field
from itertools import combinations
from math import sqrt
from statistics import median

from .calc import GroupResult, run_result
from .experiments import Experiment
from .formula import FormulaError

Z_LIMIT = 3.0           # robust z-score above which a group counts as an outlier
MIN_CLASS_SIZE = 5      # below this, no class comparison is made
MIN_STATION_SIZE = 3    # below this, no station comparison is made
SWAP_TRIGGER = 0.01     # minimum relative distance of a run from the others to try the typo check
SWAP_TOLERANCE = 0.003  # minimum relative agreement required after a digit swap

CAUSES_SPREAD = [
    "The endpoint or reading was judged differently between runs.",
    "Reading error (parallax, a drop hanging at the tip, balance not settled).",
    "A value written down or typed incorrectly.",
]


@dataclass
class ClassStats:
    n: int
    median: float
    spread: float  # robust SD: 1.4826 * MAD, at least the experiment's min_spread


@dataclass
class Finding:
    kind: str   # digit_swap, spread, outlier_low, outlier_high, station, outside_expected
    message: str
    rule: str
    causes: list = field(default_factory=list)


def lc(label: str) -> str:
    """Lower-case the first letter for use inside a sentence, but keep acronyms like KHP."""
    return label[:1].lower() + label[1:] if len(label) > 1 and label[1].islower() else label


def fmt(exp: Experiment, value: float, signed: bool = False) -> str:
    sign = "+" if signed else ""
    unit = f" {exp.result_unit}" if exp.result_unit else ""
    return f"{value:{sign}.{exp.result_decimals}f}{unit}"


def class_stats(means: list, exp: Experiment) -> ClassStats | None:
    if len(means) < MIN_CLASS_SIZE:
        return None
    med = median(means)
    mad = median(abs(v - med) for v in means)
    return ClassStats(len(means), med, max(1.4826 * mad, exp.min_spread))


def robust_z(value: float, stats: ClassStats) -> float:
    return (value - stats.median) / stats.spread


def station_deviations(by_station: dict, stats: ClassStats) -> dict:
    """{station: (median, deviation, flagged)}; flagged beyond 3 standard errors of a median."""
    out = {}
    for station, values in sorted(by_station.items()):
        if len(values) < MIN_STATION_SIZE:
            continue
        med = median(values)
        dev = med - stats.median
        limit = Z_LIMIT * 1.253 * stats.spread / sqrt(len(values))
        out[station] = (med, dev, abs(dev) > limit)
    return out


def swapped_variants(value: float, decimals: int) -> list:
    """All values reachable by swapping two different digits of the value as written."""
    text = f"{value:.{decimals}f}"
    positions = [i for i, ch in enumerate(text) if ch.isdigit()]
    out = []
    for i, j in combinations(positions, 2):
        if text[i] == text[j]:
            continue
        chars = list(text)
        chars[i], chars[j] = chars[j], chars[i]
        out.append((float("".join(chars)), "".join(chars)))
    return out


def find_digit_swap(group: GroupResult, exp: Experiment) -> Finding | None:
    """Check whether one run agrees with the others after swapping two digits of one value."""
    runs = group.runs
    if len(runs) < 3:
        return None
    # Scale both limits with the run-to-run noise the experiment allows, so a
    # noisy method does not produce typo suspicions from ordinary scatter.
    trigger = max(SWAP_TRIGGER, 2 * exp.max_rsd_percent / 100)
    tolerance = max(SWAP_TOLERANCE, exp.max_rsd_percent / 100 / 2)
    tree = exp.compiled_formula()
    # Only the run furthest from the median of all runs is a candidate; the
    # reference is then the median of the remaining runs.
    centre = median(o.result for o in runs)
    r = max(runs, key=lambda o: abs(o.result - centre))
    ref = median(o.result for o in runs if o is not r)
    if ref and abs(r.result - ref) / abs(ref) >= trigger:
        for q in exp.quantities:
            original = r.values[q.key]
            for new_value, new_text in swapped_variants(original, q.decimals):
                if not q.min_value <= new_value <= q.max_value:
                    continue
                trial = dict(r.values, **{q.key: new_value})
                if any(trial[a] <= trial[b] for a, b in exp.constraints):
                    continue
                try:
                    new_result = run_result(trial, exp, tree)
                except FormulaError:
                    continue
                if abs(new_result - ref) / abs(ref) < tolerance:
                    unit = f" {q.unit}" if q.unit else ""
                    old_text = f"{original:.{q.decimals}f}"
                    return Finding(
                        "digit_swap",
                        f"Run {r.index}: {lc(q.label)} {old_text}{unit} may be a typo for "
                        f"{new_text}{unit}. With {new_text}{unit} this run gives "
                        f"{exp.result_symbol} = {fmt(exp, new_result)}, in line with the other runs.",
                        f"Swapping two digits of one value makes this run agree with the others "
                        f"within {tolerance * 100:.1f} %.",
                    )
    return None


def assess_group(group: GroupResult, station: int, stats: ClassStats | None,
                 stations: dict, exp: Experiment) -> list:
    """All findings for one group, most specific first."""
    findings = []
    swap = find_digit_swap(group, exp)
    if swap:
        findings.append(swap)

    if group.rsd_percent is not None and group.rsd_percent > exp.max_rsd_percent:
        findings.append(Finding(
            "spread",
            f"The runs disagree: relative standard deviation {group.rsd_percent:.2f} %.",
            f"RSD above {exp.max_rsd_percent:g} % between the runs of one group.",
            [] if swap else CAUSES_SPREAD,
        ))

    if stats is not None:
        z = robust_z(group.mean, stats)
        st = stations.get(station)
        if st and st[2] and abs(z) <= Z_LIMIT:
            findings.append(Finding(
                "station",
                f"Station {station} stands out: the median of its groups is "
                f"{fmt(exp, st[1], signed=True)} against the class. Your result may be affected "
                "by the equipment.",
                "Station median beyond three standard errors of the class median.",
                ["Check the balance, burette or glassware at this station with the assistant."],
            ))
        if abs(z) > Z_LIMIT:
            high = z > 0
            causes = list(exp.causes_high if high else exp.causes_low)
            if st and st[2] and (st[1] > 0) == high:
                causes.insert(0, f"Equipment at station {station}: the median of all groups at "
                                 f"this station is also {'high' if high else 'low'} "
                                 f"({fmt(exp, st[1], signed=True)} against the class).")
            if swap:
                causes = ["See the possible typo above first."]
            findings.append(Finding(
                "outlier_high" if high else "outlier_low",
                f"{exp.result_symbol} = {fmt(exp, group.mean)} is {'higher' if high else 'lower'} "
                f"than the class (median {fmt(exp, stats.median)}, robust z = {z:+.1f}).",
                f"Robust z-score beyond ±{Z_LIMIT:g} against {stats.n} groups.",
                causes,
            ))

    if not exp.expected_min <= group.mean <= exp.expected_max:
        findings.append(Finding(
            "outside_expected",
            f"{exp.result_symbol} = {fmt(exp, group.mean)} is outside the usual range "
            f"{fmt(exp, exp.expected_min)} to {fmt(exp, exp.expected_max)}.",
            f"Result more than {exp.tolerance_percent:g} % away from the expected "
            f"{exp.expected:g}.",
        ))
    return findings
