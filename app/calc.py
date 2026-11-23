"""Validation and calculation for one group's runs (pure functions).

A run is a dict {quantity symbol: value}. The experiment's formula turns a run
into a result; a group's result is the mean of its runs.
"""
from dataclasses import dataclass
from statistics import mean, stdev

from .experiments import Experiment
from .formula import FormulaError, evaluate


def lc(label: str) -> str:
    return label[:1].lower() + label[1:] if len(label) > 1 and label[1].islower() else label


@dataclass
class RunResult:
    index: int
    values: dict
    result: float


@dataclass
class GroupResult:
    runs: list
    mean: float
    sd: float | None
    rsd_percent: float | None


def _fmt(value: float, decimals: int) -> str:
    return f"{value:.{decimals}f}"


def run_result(values: dict, exp: Experiment, tree=None) -> float:
    tree = tree or exp.compiled_formula()
    scope = {c.key: c.value for c in exp.constants}
    scope.update(values)
    return evaluate(tree, scope)


def validate_run(values: dict, exp: Experiment, index: int) -> tuple[list, list]:
    """Return (errors, warnings) for one run. Errors block saving."""
    errors, warnings = [], []
    label = f"Run {index}"
    for q in exp.quantities:
        v = values.get(q.key)
        unit = f" {q.unit}" if q.unit else ""
        if v is None:
            errors.append(f"{label}: enter a number for {lc(q.label)}.")
            continue
        if q.min_value <= v <= q.max_value:
            continue
        if q.min_value <= v / 1000 <= q.max_value:
            errors.append(f"{label}: {lc(q.label)} {v:g}{unit} is too large. Was it entered in "
                          f"the thousandth unit (for example mg instead of g)?")
        elif q.min_value <= v * 1000 <= q.max_value:
            errors.append(f"{label}: {lc(q.label)} {v:g}{unit} is too small. Was it entered in "
                          f"the larger unit (for example L instead of mL)?")
        else:
            errors.append(f"{label}: {lc(q.label)} must be between "
                          f"{q.min_value:g} and {q.max_value:g}{unit}.")
    if errors:
        return errors, warnings

    for a, b in exp.constraints:
        if values[a] <= values[b]:
            qa, qb = exp.quantity(a), exp.quantity(b)
            errors.append(f"{label}: {lc(qa.label)} must be larger than {lc(qb.label)}. "
                          "Were the two values swapped?")
    if errors:
        return errors, warnings

    try:
        r = run_result(values, exp)
    except FormulaError as e:
        errors.append(f"{label}: {e}")
        return errors, warnings
    wide = 3 * exp.tolerance_percent / 100 * abs(exp.expected)
    if abs(r - exp.expected) > wide:
        unit = f" {exp.result_unit}" if exp.result_unit else ""
        warnings.append(f"{label}: {exp.result_symbol} = {_fmt(r, exp.result_decimals)}{unit} is far "
                        f"from the expected {exp.expected:g}{unit}. Check the values once more.")
    return errors, warnings


def evaluate_group(runs: list, exp: Experiment) -> GroupResult:
    tree = exp.compiled_formula()
    results = [RunResult(i, v, run_result(v, exp, tree)) for i, v in enumerate(runs, start=1)]
    values = [r.result for r in results]
    m = mean(values)
    sd = stdev(values) if len(values) > 1 else None
    rsd = abs(sd / m) * 100 if sd is not None and m else None
    return GroupResult(results, m, sd, rsd)
