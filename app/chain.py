"""Chained steps: a later step takes a value from the result of an earlier one.

The value passed on is the class median of the earlier step's group results, so
one outlying group cannot spoil the rest of the chain. At submission the value
is stored with the run, so a group's result stays reproducible even if more
results arrive in the earlier step later.
"""
from statistics import median

from . import db
from .calc import evaluate_group


def step_result(conn, step: dict) -> tuple:
    """(class median or None, number of groups) for one course step."""
    exp = db.get_experiment(conn, step["experiment_id"])
    subs = db.list_submissions(conn, step["experiment_id"], step["id"])
    if not subs or exp is None:
        return None, 0
    return median(evaluate_group(s["runs"], exp).mean for s in subs), len(subs)


def linked_values(conn, step: dict) -> dict:
    """{quantity key: {"value", "source", "n"}}; value is None while the source has no results."""
    out = {}
    for key, source_id in step["links"].items():
        source = db.get_step(conn, source_id)
        value, n = step_result(conn, source) if source else (None, 0)
        out[key] = {"value": value, "source": source, "n": n}
    return out
