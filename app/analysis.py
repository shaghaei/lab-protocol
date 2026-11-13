"""Class comparison, outlier flags, station analysis and likely causes.

All checks are rule-based and deterministic. Each finding says which rule
produced it, so a student or assistant can follow the reasoning.
"""
from dataclasses import dataclass, field
from itertools import combinations
from math import sqrt
from statistics import median

from .calc import Titration, GroupResult, titration_factor
from .experiments import Experiment

Z_LIMIT = 3.0          # robust z-score above which a group counts as an outlier
MIN_CLASS_SIZE = 5     # below this, no class comparison is made
MIN_STATION_SIZE = 3   # below this, no station comparison is made
SWAP_TOLERANCE = 0.003  # relative distance to the other titrations after a digit swap

# Likely causes by direction, written from general lab practice.
CAUSES_LOW = [
    "Endpoint overshot: titrated past the first faint, lasting pink.",
    "Burette not rinsed with NaOH solution, so the titrant was diluted by water.",
    "Air bubble in the burette tip that escaped during the titration.",
]
CAUSES_HIGH = [
    "KHP not dried: the weighed mass contains moisture, so fewer moles were titrated.",
    "Endpoint taken too early: the pink colour faded within about 30 seconds.",
    "Part of the KHP stayed on the weighing boat or funnel and never reached the flask.",
    "Balance reads too high (check whether other groups at the same station are also high).",
]
CAUSES_SPREAD = [
    "Endpoint colour judged differently between titrations.",
    "Reading error at the burette (parallax, or a drop hanging at the tip).",
    "A value written down or typed incorrectly.",
]


@dataclass
class ClassStats:
    n: int
    median_f: float
    spread_f: float  # robust standard deviation: 1.4826 * MAD, at least exp.min_spread_f


@dataclass
class Finding:
    kind: str        # outlier_low, outlier_high, spread, outside_expected, station, digit_swap
    message: str
    rule: str
    causes: list = field(default_factory=list)


def class_stats(mean_factors: list, exp: Experiment) -> ClassStats | None:
    if len(mean_factors) < MIN_CLASS_SIZE:
        return None
    med = median(mean_factors)
    mad = median(abs(f - med) for f in mean_factors)
    return ClassStats(len(mean_factors), med, max(1.4826 * mad, exp.min_spread_f))


def robust_z(value: float, stats: ClassStats) -> float:
    return (value - stats.median_f) / stats.spread_f


def station_deviations(by_station: dict, stats: ClassStats) -> dict:
    """Return {station: (median_f, deviation, flagged)} for stations with enough groups.

    A station is flagged when its median differs from the class median by more
    than three standard errors of a median (1.253 * spread / sqrt(n)).
    """
    out = {}
    for station, factors in sorted(by_station.items()):
        if len(factors) < MIN_STATION_SIZE:
            continue
        med = median(factors)
        dev = med - stats.median_f
        limit = Z_LIMIT * 1.253 * stats.spread_f / sqrt(len(factors))
        out[station] = (med, dev, abs(dev) > limit)
    return out


def _swapped_variants(value: float) -> list:
    """All values reachable by swapping two different digits of a 2-decimal reading."""
    text = f"{value:.2f}"
    positions = [i for i, ch in enumerate(text) if ch.isdigit()]
    variants = []
    for i, j in combinations(positions, 2):
        if text[i] == text[j]:
            continue
        chars = list(text)
        chars[i], chars[j] = chars[j], chars[i]
        variants.append((float("".join(chars)), "".join(chars)))
    return variants


def find_digit_swap(titrations: list, exp: Experiment) -> Finding | None:
    """Check whether one titration becomes consistent with the others after a digit swap."""
    if len(titrations) < 3:
        return None
    factors = [titration_factor(t, exp) for t in titrations]
    for idx, t in enumerate(titrations):
        others = [f for k, f in enumerate(factors) if k != idx]
        ref = median(others)
        if abs(factors[idx] - ref) / ref < 0.01:
            continue
        for field_name in ("end_ml", "start_ml"):
            original = getattr(t, field_name)
            for new_value, new_text in _swapped_variants(original):
                candidate = Titration(t.mass_g, t.start_ml, t.end_ml)
                setattr(candidate, field_name, new_value)
                if candidate.volume_ml <= 0:
                    continue
                f_new = titration_factor(candidate, exp)
                if abs(f_new - ref) / ref < SWAP_TOLERANCE:
                    reading = "end" if field_name == "end_ml" else "start"
                    return Finding(
                        "digit_swap",
                        f"Titration {idx + 1}: the {reading} reading {original:.2f} mL may be a "
                        f"typo for {new_text} mL. With {new_text} mL this titration gives "
                        f"f = {f_new:.4f}, in line with the other two.",
                        "Swapping two digits makes this titration agree with the others "
                        f"within {SWAP_TOLERANCE * 100:.1f}%.",
                    )
    return None


def assess_group(group: GroupResult, titrations: list, station: int, stats: ClassStats | None,
                 stations: dict, exp: Experiment) -> list:
    """All findings for one group, most specific first."""
    findings = []

    swap = find_digit_swap(titrations, exp)
    if swap:
        findings.append(swap)

    if group.rsd_percent is not None and group.rsd_percent > exp.max_rsd_percent:
        findings.append(Finding(
            "spread",
            f"The titrations disagree: relative standard deviation {group.rsd_percent:.2f}%.",
            f"RSD above {exp.max_rsd_percent}% between the titrations of one group.",
            [] if swap else CAUSES_SPREAD,
        ))

    if stats is not None:
        z = robust_z(group.mean_factor, stats)
        st = stations.get(station)
        if st and st[2] and abs(z) <= Z_LIMIT:
            findings.append(Finding(
                "station",
                f"Station {station} stands out: the median of its groups is "
                f"{st[1]:+.4f} against the class. Your value may be affected by the equipment.",
                "Station median beyond three standard errors of the class median.",
                ["Check the balance and burette at this station with the assistant."],
            ))
        if abs(z) > Z_LIMIT:
            high = z > 0
            causes = list(CAUSES_HIGH if high else CAUSES_LOW)
            st = stations.get(station)
            if st and st[2] and (st[1] > 0) == high:
                causes.insert(0, f"Equipment at station {station}: the median of all groups at "
                                 f"this station is also {'high' if high else 'low'} "
                                 f"({st[1]:+.4f} against the class).")
            if swap:
                causes = ["See the possible typo above first."]
            findings.append(Finding(
                "outlier_high" if high else "outlier_low",
                f"f = {group.mean_factor:.4f} is {'higher' if high else 'lower'} than the class "
                f"(median {stats.median_f:.4f}, robust z = {z:+.1f}).",
                f"Robust z-score beyond ±{Z_LIMIT:g} against {stats.n} groups.",
                causes,
            ))

    if not exp.expected_f_min <= group.mean_factor <= exp.expected_f_max:
        findings.append(Finding(
            "outside_expected",
            f"f = {group.mean_factor:.4f} is outside the usual range "
            f"{exp.expected_f_min}–{exp.expected_f_max} for a freshly prepared solution.",
            "Factor outside the expected range.",
        ))
    return findings
