"""Turn the builder form into an experiment definition and back."""
from .calc import run_result, validate_run
from .experiments import CATEGORIES, Constant, Experiment, Quantity, check_definition
from .formula import FormulaError

MAX_QUANTITIES = 8
MAX_CONSTANTS = 5


def num(raw, default=None):
    raw = ("" if raw is None else str(raw)).strip().replace(",", ".")
    if raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return None


def _lines(text: str) -> list:
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]


def to_form(exp: Experiment | None, title_prefix: str = "") -> dict:
    """Field values for the builder, pre-filled from an experiment (or empty)."""
    if exp is None:
        return {"category": "Other", "runs": "3", "stations": "6", "result_decimals": "2",
                "tolerance_percent": "5", "max_rsd_percent": "1", "quantities": [], "constants": []}
    return {
        "title": f"{title_prefix}{exp.title}" if title_prefix else exp.title,
        "category": exp.category, "summary": exp.summary,
        "runs": str(exp.runs), "stations": str(exp.stations),
        "formula": exp.formula, "result_label": exp.result_label,
        "result_symbol": exp.result_symbol, "result_unit": exp.result_unit,
        "result_decimals": str(exp.result_decimals), "expected": f"{exp.expected:g}",
        "tolerance_percent": f"{exp.tolerance_percent:g}", "min_spread": f"{exp.min_spread:g}",
        "max_rsd_percent": f"{exp.max_rsd_percent:g}",
        "constraints": "\n".join(f"{a} > {b}" for a, b in exp.constraints),
        "causes_low": "\n".join(exp.causes_low), "causes_high": "\n".join(exp.causes_high),
        "procedure": "\n".join(exp.procedure),
        "quantities": [{"key": q.key, "label": q.label, "unit": q.unit, "min": f"{q.min_value:g}",
                        "max": f"{q.max_value:g}", "decimals": str(q.decimals),
                        "example": f"{q.example:.{q.decimals}f}"} for q in exp.quantities],
        "constants": [{"key": c.key, "label": c.label, "value": f"{c.value:g}", "unit": c.unit}
                      for c in exp.constants],
    }


def read_form(form) -> dict:
    """Collect raw builder fields from a submitted form."""
    f = {k: form.get(k, "") for k in ("title", "category", "summary", "runs", "stations", "formula",
                                      "result_label", "result_symbol", "result_unit",
                                      "result_decimals", "expected", "tolerance_percent",
                                      "min_spread", "max_rsd_percent", "constraints",
                                      "causes_low", "causes_high", "procedure")}
    f["quantities"] = []
    for i in range(1, MAX_QUANTITIES + 1):
        row = {k: form.get(f"q{i}_{k}", "").strip()
               for k in ("key", "label", "unit", "min", "max", "decimals", "example")}
        if row["key"] or row["label"]:
            f["quantities"].append(row)
    f["constants"] = []
    for i in range(1, MAX_CONSTANTS + 1):
        row = {k: form.get(f"c{i}_{k}", "").strip() for k in ("key", "label", "value", "unit")}
        if row["key"] or row["value"]:
            f["constants"].append(row)
    return f


def build(f: dict, eid: str) -> tuple:
    """Return (experiment or None, problems)."""
    problems = []

    def need(name, label, cast=float):
        v = num(f.get(name))
        if v is None:
            problems.append(f"{label}: enter a number.")
            return 0
        return cast(v)

    quantities = []
    for i, row in enumerate(f["quantities"], start=1):
        values = [num(row[k]) for k in ("min", "max", "decimals", "example")]
        if any(v is None for v in values):
            problems.append(f"Quantity {i} ({row['key'] or 'no symbol'}): fill in min, max, decimals "
                            "and example as numbers.")
            continue
        quantities.append(Quantity(row["key"], row["label"], row["unit"], values[0], values[1],
                                   int(values[2]), values[3]))
    constants = []
    for i, row in enumerate(f["constants"], start=1):
        value = num(row["value"])
        if value is None:
            problems.append(f"Constant {i} ({row['key'] or 'no symbol'}): enter its value as a number.")
            continue
        constants.append(Constant(row["key"], row["label"] or row["key"], value, row["unit"]))
    constraints = []
    for line in _lines(f["constraints"]):
        parts = [p.strip() for p in line.split(">")]
        if len(parts) != 2 or not all(parts):
            problems.append(f"Rule '{line}': write it as 'A > B', for example V_end > V_start.")
            continue
        constraints.append(parts)

    expected = need("expected", "Expected result")
    min_spread = num(f.get("min_spread"))
    if min_spread is None or min_spread == 0:
        min_spread = abs(expected) * 0.003 if expected else 0.001

    exp = Experiment(
        id=eid, title=f["title"].strip(), category=f["category"], summary=f["summary"].strip(),
        quantities=quantities, constants=constants, formula=f["formula"].strip(),
        result_label=f["result_label"].strip() or "Result",
        result_symbol=f["result_symbol"].strip() or "R", result_unit=f["result_unit"].strip(),
        result_decimals=need("result_decimals", "Decimals of the result", int),
        expected=expected, tolerance_percent=need("tolerance_percent", "Usual range"),
        min_spread=min_spread, max_rsd_percent=need("max_rsd_percent", "Allowed spread between runs"),
        runs=need("runs", "Runs per group", int), stations=need("stations", "Lab stations", int),
        constraints=constraints, causes_low=_lines(f["causes_low"]),
        causes_high=_lines(f["causes_high"]), procedure=_lines(f["procedure"]), builtin=False,
    )
    problems += check_definition(exp)
    return (None if problems else exp), problems


def test_run(exp: Experiment) -> dict:
    """Calculate the result from the example values, as a check before saving."""
    values = {q.key: q.example for q in exp.quantities}
    errors, warnings = validate_run(values, exp, 1)
    result = None
    if not errors:
        try:
            result = run_result(values, exp)
        except FormulaError as e:
            errors.append(str(e))
    return {"values": values, "result": result, "errors": errors, "warnings": warnings}


__all__ = ["CATEGORIES", "to_form", "read_form", "build", "test_run", "num"]
