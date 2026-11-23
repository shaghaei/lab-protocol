"""Safe evaluation of result formulas written by users.

A formula is a plain arithmetic expression over the experiment's quantities
and constants, for example ``m_KHP / M_KHP / ((V_end - V_start) / 1000) / c_nom``.
Only numbers, names, + - * / ** and a few math functions are allowed; anything
else (attributes, imports, calls to other functions) is rejected before use.
"""
import ast
import math

FUNCTIONS = {"sqrt": math.sqrt, "log": math.log, "log10": math.log10, "exp": math.exp,
             "abs": abs, "min": min, "max": max}
BINOPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
          ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b,
          ast.Pow: lambda a, b: a ** b}
UNARY = {ast.USub: lambda a: -a, ast.UAdd: lambda a: a}
MAX_LENGTH = 300


class FormulaError(ValueError):
    pass


def parse(expression: str, allowed_names: set) -> ast.Expression:
    """Parse and check a formula. Raises FormulaError with a readable message."""
    expression = (expression or "").strip()
    if not expression:
        raise FormulaError("The formula is empty.")
    if len(expression) > MAX_LENGTH:
        raise FormulaError(f"The formula is longer than {MAX_LENGTH} characters.")
    try:
        tree = ast.parse(expression.replace("^", "**"), mode="eval")
    except SyntaxError:
        raise FormulaError("The formula is not a valid expression. Check brackets and operators.")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Expression, ast.Load, ast.operator, ast.unaryop)):
            continue
        if isinstance(node, ast.BinOp) and type(node.op) in BINOPS:
            if isinstance(node.op, ast.Pow) and not (isinstance(node.right, ast.Constant)
                                                     and abs(node.right.value) <= 10):
                raise FormulaError("Powers must use a number between -10 and 10 as exponent.")
            continue
        if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY:
            continue
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
                and not isinstance(node.value, bool):
            continue
        if isinstance(node, ast.Name):
            if node.id in FUNCTIONS:
                continue
            if node.id not in allowed_names:
                raise FormulaError(f"Unknown name '{node.id}'. Use the symbols of your quantities "
                                   "and constants.")
            continue
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in FUNCTIONS and not node.keywords:
            continue
        raise FormulaError("Only numbers, symbols, + - * / ^ and sqrt, log, log10, exp, abs, "
                           "min, max are allowed.")
    return tree


def _eval(node, values: dict) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body, values)
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, ast.Name):
        return float(values[node.id])
    if isinstance(node, ast.BinOp):
        return BINOPS[type(node.op)](_eval(node.left, values), _eval(node.right, values))
    if isinstance(node, ast.UnaryOp):
        return UNARY[type(node.op)](_eval(node.operand, values))
    if isinstance(node, ast.Call):
        return float(FUNCTIONS[node.func.id](*[_eval(a, values) for a in node.args]))
    raise FormulaError("Unsupported expression.")


def evaluate(tree: ast.Expression, values: dict) -> float:
    try:
        result = _eval(tree, values)
    except ZeroDivisionError:
        raise FormulaError("Division by zero with these values.")
    except (ValueError, OverflowError, TypeError, KeyError):
        raise FormulaError("The formula cannot be calculated with these values.")
    if isinstance(result, complex) or math.isnan(result) or math.isinf(result):
        raise FormulaError("The formula gives no real number with these values.")
    return result
