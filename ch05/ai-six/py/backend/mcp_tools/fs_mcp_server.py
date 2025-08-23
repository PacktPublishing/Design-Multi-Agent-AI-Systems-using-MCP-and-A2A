import os
from mcp.server.fastmcp import FastMCP
import sh

mcp = FastMCP("FileSystem Tools", "")

@mcp.tool()
def ls(path: str) -> str:
    """Lists directory contents."""
    return sh.ls(path)

@mcp.tool()
def cat(file: str) -> str:
    """Concatenates and displays file contents."""
    return sh.cat(file)

@mcp.tool()
def pwd() -> str:
    """Prints the current working directory."""
    return os.getcwd()

@mcp.tool()
def mkdir(directory: str) -> str:
    """Creates a new directory."""
    return sh.mkdir(directory)

@mcp.tool()
def cp(source: str, destination: str) -> str:
    """Copies files or directories."""
    return sh.cp(source, destination)


if __name__ == "__main__":
    mcp.run()

