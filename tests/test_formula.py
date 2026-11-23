import pytest

from app.formula import FormulaError, evaluate, parse


def test_basic_arithmetic_and_power():
    tree = parse("a * (b - c) / d + e^2", {"a", "b", "c", "d", "e"})
    assert evaluate(tree, {"a": 2, "b": 5, "c": 1, "d": 4, "e": 3}) == pytest.approx(11.0)


def test_functions_allowed():
    tree = parse("sqrt(x) + log10(y)", {"x", "y"})
    assert evaluate(tree, {"x": 16, "y": 100}) == pytest.approx(6.0)


@pytest.mark.parametrize("expr", [
    "__import__('os').system('ls')",
    "x.__class__",
    "open('f')",
    "[x for x in y]",
    "x if y else z",
    "x ** y",
    "lambda: 1",
])
def test_unsafe_or_unsupported_is_rejected(expr):
    with pytest.raises(FormulaError):
        parse(expr, {"x", "y", "z"})


def test_unknown_name_is_named():
    with pytest.raises(FormulaError, match="Unknown name 'q'"):
        parse("x + q", {"x"})


def test_division_by_zero_is_reported():
    tree = parse("x / y", {"x", "y"})
    with pytest.raises(FormulaError, match="Division by zero"):
        evaluate(tree, {"x": 1, "y": 0})
