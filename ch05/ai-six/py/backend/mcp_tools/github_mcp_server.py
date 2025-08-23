import sh
from mcp.server.fastmcp import FastMCP
from typing import List

mcp = FastMCP("GitHub CLI Tools", "Tools for interacting with GitHub through the gh CLI")

@mcp.tool()
def gh(args: List[str]) -> str:
    """
    Executes GitHub CLI commands with the provided arguments.

    See https://docs.github.com/en/github-cli/github-cli/github-cli-reference

    Parameters:
    - args: List of string arguments to pass to the gh command
    """
    try:
        # Execute the gh command with all provided arguments
        result = sh.gh(*args)
        return str(result)
    except sh.ErrorReturnCode as e:
        return f"Error: {e.stderr.decode() if hasattr(e, 'stderr') else str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    mcp.run()