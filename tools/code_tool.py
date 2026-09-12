import os
import sys
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import WORKSPACE_DIR, CODE_EXEC_TIMEOUT


def execute_python(code: str) -> str:
    """
    Executes Python code locally in the workspace directory.
    Useful for data analysis, system file generation, or complex scripting.
    """
    filename = "temp_execution.py"
    filepath = os.path.join(WORKSPACE_DIR, filename)

    try:
        # Write the code to a file
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)

        # Execute it
        result = subprocess.run(
            ["python", filepath],
            cwd=WORKSPACE_DIR,
            capture_output=True,
            text=True,
            timeout=CODE_EXEC_TIMEOUT
        )

        output = result.stdout
        if result.stderr:
            output += f"\nErrors:\n{result.stderr}"

        return output if output.strip() else "Code executed successfully with no output."

    except subprocess.TimeoutExpired:
        return f"Execution timed out after {CODE_EXEC_TIMEOUT} seconds."
    except Exception as e:
        return f"Failed to execute code: {str(e)}"
    finally:
        # Cleanup temp file if needed (we'll leave it for debugging)
        pass
