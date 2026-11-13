"""Evaluate the rule-based checks against the ground truth of the synthetic class.

    python scripts/evaluate.py

Detection: a group with an injected error should get at least one finding,
a clean group none. Diagnosis: the first finding should point to the right cause.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analysis import assess_group, class_stats, station_deviations  # noqa: E402
from app.calc import Titration, evaluate_group  # noqa: E402
from app.experiments import NAOH_TITER as EXP  # noqa: E402
from app.synthetic import generate  # noqa: E402

# label -> test whether the findings name the right cause
EXPECTED = {
    "endpoint_overshoot": lambda fs: any(f.kind == "outlier_low" for f in fs),
    "burette_not_rinsed": lambda fs: any(f.kind == "outlier_low" for f in fs),
    "wet_standard": lambda fs: any(f.kind == "outlier_high" for f in fs),
    "digit_swap": lambda fs: bool(fs) and fs[0].kind == "digit_swap",
    "balance_offset": lambda fs: any(f.kind == "station" or
                                     (f.causes and f.causes[0].startswith("Equipment at station"))
                                     for f in fs),
}


def main() -> None:
    groups = generate()
    results = [(g, [Titration(*t) for t in g["titrations"]]) for g in groups]
    evals = [(g, ts, evaluate_group(ts, EXP)) for g, ts in results]
    stats = class_stats([r.mean_factor for _, _, r in evals], EXP)
    by_station = {}
    for g, _, r in evals:
        by_station.setdefault(g["station"], []).append(r.mean_factor)
    stations = station_deviations(by_station, stats)

    tp = fp = fn = tn = right_cause = 0
    rows = []
    for g, ts, r in evals:
        fs = assess_group(r, ts, g["station"], stats, stations, EXP)
        has_error = g["label"] != "none"
        flagged = bool(fs)
        tp += has_error and flagged
        fn += has_error and not flagged
        fp += (not has_error) and flagged
        tn += (not has_error) and not flagged
        ok = EXPECTED[g["label"]](fs) if has_error else not flagged
        right_cause += has_error and ok
        rows.append((g["code"], g["station"], g["label"], ", ".join(f.kind for f in fs) or "-", ok))

    for row in rows:
        print(f"{row[0]}  st{row[1]}  {row[2]:<20} {row[3]:<45} {'ok' if row[4] else 'MISS'}")
    n_err = tp + fn
    print(f"\nGroups with injected errors: {n_err}, clean groups: {fp + tn}")
    print(f"Detected: {tp}/{n_err}  ·  false alarms: {fp}/{fp + tn}")
    print(f"Right cause named: {right_cause}/{n_err}")


if __name__ == "__main__":
    main()
