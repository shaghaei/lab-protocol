"""Write the synthetic class to data/ as two CSV files.

    python scripts/generate_synthetic.py

data/synthetic_measurements.csv  one row per titration (what students would enter)
data/synthetic_labels.csv        ground truth per group (for evaluation only)
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.synthetic import generate  # noqa: E402


def main() -> None:
    out = ROOT / "data"
    out.mkdir(exist_ok=True)
    groups = generate()
    with open(out / "synthetic_measurements.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["group", "station", "titration", "mass_g", "start_ml", "end_ml"])
        for g in groups:
            for k, (m, s, e) in enumerate(g["titrations"], start=1):
                w.writerow([g["code"], g["station"], k, f"{m:.4f}", f"{s:.2f}", f"{e:.2f}"])
    with open(out / "synthetic_labels.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["group", "station", "injected_error"])
        for g in groups:
            w.writerow([g["code"], g["station"], g["label"]])
    print(f"Wrote {len(groups)} groups to {out}")


if __name__ == "__main__":
    main()
