"""Evaluate the rule-based checks against the ground truth of the synthetic classes.

    python scripts/evaluate.py            # all built-in experiments
    python scripts/evaluate.py --detail   # one line per group

Detection: a group with an injected error should get at least one finding, a
clean group none. Diagnosis: the findings should point in the right direction
(low, high, typo, station).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analysis import assess_group, class_stats, station_deviations  # noqa: E402
from app.calc import evaluate_group  # noqa: E402
from app.experiments import BUILTINS  # noqa: E402
from app.synthetic import CLASSES, generate  # noqa: E402


def right_cause(label: str, station_dir: str, findings: list) -> bool:
    kinds = [f.kind for f in findings]
    if label == "low":
        return "outlier_low" in kinds
    if label == "high":
        return "outlier_high" in kinds
    if label == "swap":
        return bool(findings) and findings[0].kind == "digit_swap"
    if label == "station":
        return "station" in kinds or any(f.causes and f.causes[0].startswith("Equipment at station")
                                         for f in findings)
    return not findings


def evaluate(exp, seed=None, detail=False) -> tuple:
    groups = generate(exp) if seed is None else generate(exp, seed)
    results = [(g, evaluate_group(g["runs"], exp)) for g in groups]
    stats = class_stats([r.mean for _, r in results], exp)
    by_station = {}
    for g, r in results:
        by_station.setdefault(g["station"], []).append(r.mean)
    stations = station_deviations(by_station, stats)
    station_dir = CLASSES[exp.id][2]
    tp = fp = n_err = n_clean = right = 0
    for g, r in results:
        fs = assess_group(r, g["station"], stats, stations, exp)
        err = g["label"] != "none"
        n_err += err
        n_clean += not err
        tp += err and bool(fs)
        fp += (not err) and bool(fs)
        ok = right_cause(g["label"], station_dir, fs)
        right += err and ok
        if detail:
            print(f"  {g['code']} st{g['station']} {g['label']:<8} {str(g['mechanism']):<15} "
                  f"{r.mean:10.4f}  {', '.join(f.kind for f in fs) or '-':<45} {'ok' if ok else 'MISS'}")
    return tp, n_err, fp, n_clean, right


def main() -> None:
    detail = "--detail" in sys.argv
    print(f"{'Experiment':<45} {'detected':>9} {'false alarms':>13} {'right cause':>12}")
    totals = [0, 0, 0, 0, 0]
    for exp in BUILTINS:
        if detail:
            print(exp.title)
        tp, n_err, fp, n_clean, right = evaluate(exp, detail=detail)
        totals = [a + b for a, b in zip(totals, (tp, n_err, fp, n_clean, right))]
        print(f"{exp.title:<45} {tp:>4}/{n_err:<4} {fp:>7}/{n_clean:<5} {right:>6}/{n_err:<4}")
    tp, n_err, fp, n_clean, right = totals
    print(f"{'All experiments':<45} {tp:>4}/{n_err:<4} {fp:>7}/{n_clean:<5} {right:>6}/{n_err:<4}")


if __name__ == "__main__":
    main()
