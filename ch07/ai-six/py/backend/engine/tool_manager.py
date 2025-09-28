import asyncio
import os
from pathlib import Path
import importlib.util
import inspect

from backend.object_model.tool import Tool
from backend.tools.base.mcp_tool import MCPTool
from backend.mcp_client.mcp_client import MCPClient
from backend.engine.config import ToolConfig


def get_tool_dict(tool_config: ToolConfig) -> dict[str, Tool]:
    """Get a dictionary of all available tools from various sources.

    Args:
        tool_config: ToolConfig object containing tool configuration

    Returns:
        Dict mapping tool names to Tool instances
    """
    tools: list[Tool] = []

    # 1. Discover AI-6 native tools
    if tool_config.tools_dir:
        native_tools = _discover_native_tools(
            tool_config.tools_dir,
            tool_config.tool_config
        )
        tools.extend(native_tools)

    # 2. Discover local MCP tools
    if tool_config.mcp_tools_dir:
        local_mcp_tools = _discover_local_mcp_tools(tool_config.mcp_tools_dir)
        tools.extend(local_mcp_tools)

    # 3. Get tools of remote MCP servers
    if tool_config.remote_mcp_servers:
        remote_mcp_tools = _get_remote_mcp_tools(
            tool_config.remote_mcp_servers
        )
        tools.extend(remote_mcp_tools)

    return {tool.name: tool for tool in tools}

def _discover_native_tools(tools_dir: str, tool_config: dict) -> list[Tool]:
    """Discover custom tools from the tools directory.

    Args:
        tools_dir: Directory to search for tool files
        tool_config: Configuration for tools

    Returns:
        List of Tool instances
    """
    tools: list[Tool] = []
    base_path = Path(tools_dir).resolve()
    module_root_path = base_path.parents[2]  # Three levels up

    # Walk through all .py files in the directory (recursive)
    for file_path in base_path.rglob("*.py"):
        if file_path.name == "__init__.py":
            continue
        try:
            # Get the path relative to the Python root dir
            relative_path = file_path.relative_to(module_root_path)
            # Convert path parts to a valid Python module name
            module_parts = list(relative_path.parts[:-1]) + [relative_path.stem]
            module_name = ".".join(module_parts)

            # Dynamically import the module
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Find all Tool subclasses in the module
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (
                            issubclass(obj, Tool)
                            and obj != Tool
                            and obj.__module__ == module_name
                    ):
                        # Check if tool is enabled in config
                        tool_name = obj.__name__
                        if tool_name in tool_config and not tool_config[tool_name].get('enabled', True):
                            continue

                        # Instantiate the tool
                        tool_instance = obj()
                        tools.append(tool_instance)

        except Exception as e:
            print(f"Warning: Failed to load tool from {file_path}: {e}")
            continue

    return tools


def _discover_local_mcp_tools(mcp_servers_dir: str) -> list[MCPTool]:
    """Discover MCP tools dynamically by connecting to MCP servers."""
    if not os.path.isdir(mcp_servers_dir):
        return []

    async def discover_async():
        tools: list[Tool] = []
        client = MCPClient()

        try:
            # Iterate over all files in the directory
            for file_name in os.listdir(mcp_servers_dir):
                script_path = os.path.join(mcp_servers_dir, file_name)

                # Check if it's a file
                if not os.path.isfile(script_path):
                    continue

                try:
                    # Connect to server and get its tools with timeout
                    server_tools = await asyncio.wait_for(
                        client.connect_to_server(script_path, script_path),
                        timeout=5.0
                    )

                    # Create MCPTool instances for each tool
                    for tool_info in server_tools:
                        mcp_tool = MCPTool(script_path, script_path, tool_info)
                        tools.append(mcp_tool)

                except Exception as e:
                    # Skip servers that fail to connect or timeout
                    error_msg = str(e) if str(e) else f"{type(e).__name__}: {e}"
                    print(f"Warning: Failed to connect to MCP server {script_path}: {error_msg}")
                    continue

        finally:
            await client.cleanup()

        return tools

    # Run async discovery in sync context
    try:
        return asyncio.run(discover_async())
    except Exception as e:
        print(f"Warning: MCP tool discovery failed: {e}")
        return []


def _get_remote_mcp_tools(remote_servers: list[dict]) -> list[Tool]:
    """Connect to remote MCP servers and get their tools.

    Args:
        remote_servers: List of remote server configurations
        Each server config should have: {'url': 'https://...', 'name': '...'}

    Returns:
        List of MCPTool instances for remote tools
    """
    tools: list[Tool] = []

    async def connect_async():
        client = MCPClient()

        try:
            for server_config in remote_servers:
                try:
                    server_url = server_config.get('url')
                    server_name = server_config.get('name', server_url)

                    if not server_url:
                        print(f"Warning: Remote MCP server config missing 'url': {server_config}")
                        continue

                    # Connect to remote server with timeout
                    server_tools = await asyncio.wait_for(
                        client.connect_to_server(server_name, server_url),
                        timeout=10.0
                    )

                    # Create MCPTool instances for each remote tool
                    for tool_info in server_tools:
                        # Use server_url as script_path for remote tools
                        mcp_tool = MCPTool(server_name, server_url, tool_info)
                        tools.append(mcp_tool)

                except Exception as e:
                    print(f"Warning: Failed to connect to remote MCP server {server_config}: {e}")
                    continue

        finally:
            await client.cleanup()

    # Run async connection in sync context
    try:
        asyncio.run(connect_async())
    except Exception as e:
        print(f"Warning: Remote MCP server connection failed: {e}")
        return []

    return tools
