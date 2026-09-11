import sympy

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
