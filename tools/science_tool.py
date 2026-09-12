import os
import sys
import sympy

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


def evaluate_math(expression: str) -> str:
    """
    Evaluate a mathematical expression or equation using SymPy.
    Supports advanced algebra, calculus, and arithmetic.
    """
    try:
        # sympify converts a string into a SymPy expression safely
        expr = sympy.sympify(expression)
        result = expr.evalf()
        return f"Result of {expression}: {result}"
    except Exception as e:
        return f"Math Error processing '{expression}': {str(e)}"
