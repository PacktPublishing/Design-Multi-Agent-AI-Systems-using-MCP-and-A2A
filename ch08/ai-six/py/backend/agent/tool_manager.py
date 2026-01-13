import asyncio
import os
from pathlib import Path
import importlib.util
import inspect
from typing import Optional, Mapping

from backend.object_model.tool import Tool
from backend.tools.base.mcp_tool import MCPTool
from backend.mcp_client.mcp_client import MCPClient
from backend.agent.config import ToolConfig, Config

from backend.a2a_client.a2a_client import A2AServerConfig
from backend.a2a_client.a2a_manager import A2AManager
from backend.tools.base.a2a_tool import A2ATool


def get_tool_dict(tool_config: ToolConfig, agent_configs: list[Config] = None) -> dict[str, Tool]:
    """Get a dictionary of all available tools from various sources.

    Args:
        tool_config: ToolConfig object containing tool configuration
        agent_configs: Optional list of agent configs to create agent tools

    Returns:
        Dict mapping tool names to Tool instances
    """
    tools: list[Tool] = []

    # 1. Discover AI-6 native tools from all directories
    for tools_dir in tool_config.tools_dirs:
        native_tools = _discover_native_tools(
            tools_dir,
            tool_config.tool_config
        )
        tools.extend(native_tools)

    # 2. Discover local MCP tools from all directories  
    for mcp_tools_dir in tool_config.mcp_tools_dirs:
        local_mcp_tools = _discover_local_mcp_tools(mcp_tools_dir)
        tools.extend(local_mcp_tools)

    # 3. Get tools of remote MCP servers
    if tool_config.remote_mcp_servers:
        remote_mcp_tools = _get_remote_mcp_tools(
            tool_config.remote_mcp_servers
        )
        tools.extend(remote_mcp_tools)

    # 4. Get tools from A2A servers
    if tool_config.a2a_servers:
        a2a_tools = _get_a2a_tools(tool_config.a2a_servers)
        tools.extend(a2a_tools)

    # 5. Create agent tools if agent configs provided
    if agent_configs:
        agent_tools = _create_agent_tools(agent_configs)
        tools.extend(agent_tools)

    # 6. Filter tools based on enabled/disabled configuration
    tools = _filter_tools(tools, tool_config.enabled_tools, tool_config.disabled_tools)

    return {tool.name: tool for tool in tools}


def configure_a2a_integration(tool_dict: dict[str, Tool], memory_dir: str, session_id: str, message_injector) -> dict[str, Tool]:
    """Configure A2A integration if A2A tools are present.
    
    Args:
        tool_dict: Dictionary of existing tools
        memory_dir: Directory for A2A state persistence
        session_id: Session ID for A2A integration
        message_injector: Callback function for injecting SystemMessages
        
    Returns:
        Updated tool dictionary with A2A task management tools
    """
    # Check if any A2A tools are present
    has_a2a_tools = any(isinstance(tool, A2ATool) for tool in tool_dict.values())
    
    if not has_a2a_tools:
        return tool_dict
    
    # Import here to avoid circular imports
    from backend.tools.a2a_task_manager.a2a_task_manager import (
        A2ATaskListTool, A2ATaskCancelTool, A2ATaskMessageTool, A2ATaskStatusTool
    )
    
    # Initialize A2A manager
    A2AManager.initialize(memory_dir, session_id, message_injector)
    
    # Configure the message pump with all registered clients
    A2AManager.configure_message_pump()
    
    # Add A2A task management tools
    task_list_tool = A2ATaskListTool()
    task_cancel_tool = A2ATaskCancelTool()
    task_message_tool = A2ATaskMessageTool()
    task_status_tool = A2ATaskStatusTool()
    
    # Add task tools to tool dictionary
    updated_tool_dict = tool_dict.copy()
    updated_tool_dict[task_list_tool.name] = task_list_tool
    updated_tool_dict[task_cancel_tool.name] = task_cancel_tool
    updated_tool_dict[task_message_tool.name] = task_message_tool
    updated_tool_dict[task_status_tool.name] = task_status_tool
    
    return updated_tool_dict


def _filter_tools(tools: list[Tool], enabled_tools: Optional[list[str]], disabled_tools: Optional[list[str]]) -> list[Tool]:
    """Filter tools based on enabled/disabled configuration.
    
    Args:
        tools: List of tools to filter
        enabled_tools: If not None, only include tools with names in this list
        disabled_tools: If not None, exclude tools with names in this list
        
    Returns:
        Filtered list of tools
    """
    if enabled_tools is None and disabled_tools is None:
        # No filtering - return all tools
        return tools
        
    filtered_tools = []
    
    for tool in tools:
        tool_name = tool.name
        
        # If enabled_tools is specified, only include tools in that list
        if enabled_tools is not None:
            if tool_name in enabled_tools:
                filtered_tools.append(tool)
        
        # If disabled_tools is specified, exclude tools in that list
        elif disabled_tools is not None:
            if tool_name not in disabled_tools:
                filtered_tools.append(tool)
                
    return filtered_tools


def _discover_native_tools(tools_dir: str, tool_config: Mapping[str, dict]) -> list[Tool]:
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
                        # Skip base classes that require constructor arguments
                        if obj.__name__ in ['MCPTool', 'CommandTool', 'A2ATool', 
                                          'A2ATaskListTool', 'A2ATaskCancelTool', 
                                          'A2ATaskMessageTool', 'A2ATaskStatusTool']:
                            continue
                            
                        # Check if tool is enabled in config
                        tool_name = obj.__name__
                        if tool_name in tool_config and not tool_config[tool_name].get('enabled', True):
                            continue

                        try:
                            # Instantiate the tool
                            tool_instance = obj()
                            tools.append(tool_instance)
                        except TypeError as e:
                            # Skip tools that can't be instantiated without arguments
                            print(f"Warning: Skipping {obj.__name__} - requires constructor arguments: {e}")
                            continue

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

    # Run async discovery - handle both sync and async contexts
    try:
        # Check if we're already in an event loop
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context, create a task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, discover_async())
                return future.result()
        except RuntimeError:
            # No event loop, we can use asyncio.run
            return asyncio.run(discover_async())
    except Exception as e:
        print(f"Warning: MCP tool discovery failed: {e}")
        return []


def _create_agent_tools(agent_configs: list[Config]) -> list[Tool]:
    """Create agent tools from agent configurations.
    
    Args:
        agent_configs: List of agent configurations
        
    Returns:
        List of AgentTool instances
    """
    tools: list[Tool] = []
    
    # Import here to avoid circular imports
    from backend.object_model.agent_tool import AgentTool
    
    for agent_config in agent_configs:
        try:
            if agent_config.name:  # Only create tools for named agents
                agent_tool = AgentTool(agent_config)
                tools.append(agent_tool)
        except Exception as e:
            print(f"Warning: Failed to create agent tool for {agent_config.name}: {e}")
            continue
    
    return tools


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

    # Run async connection - handle both sync and async contexts
    try:
        # Check if we're already in an event loop
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context, create a task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, connect_async())
                future.result()
        except RuntimeError:
            # No event loop, we can use asyncio.run
            asyncio.run(connect_async())
    except Exception as e:
        print(f"Warning: Remote MCP server connection failed: {e}")
        return []

    return tools


def _get_a2a_tools(a2a_servers: list[dict]) -> list[Tool]:
    """Connect to A2A servers and get their tools.

    Args:
        a2a_servers: List of A2A server configurations
        Each server config should have: {'name': 'server_name', 'url': 'http://...'}

    Returns:
        List of A2ATool instances for A2A skills
    """
    tools: list[Tool] = []

    async def discover_async():
        discovered_tools = []

        try:
            for server_config_dict in a2a_servers:
                try:
                    server_name = server_config_dict.get('name')
                    server_url = server_config_dict.get('url')

                    if not server_name or not server_url:
                        print(f"Warning: A2A server config missing 'name' or 'url': {server_config_dict}")
                        continue

                    # Create A2A server configuration
                    server_config = A2AServerConfig(
                        name=server_name,
                        url=server_url,
                        timeout=server_config_dict.get('timeout', 30.0),
                        api_key=server_config_dict.get('api_key')
                    )
                    
                    # Get a client for this server (ensures it's registered)
                    client = A2AManager.ensure_client(server_config)

                    # Get skills (discovers agent if needed)
                    skills = await asyncio.wait_for(
                        client.get_skills(server_name),
                        timeout=server_config.timeout
                    )

                    # Create A2ATool instances for each skill
                    for skill in skills:
                        try:
                            a2a_tool = A2ATool(server_name, skill)
                            discovered_tools.append(a2a_tool)
                        except Exception as e:
                            skill_name = skill.id if hasattr(skill, 'id') else getattr(skill, 'name', 'unknown')
                            print(f"Warning: Failed to create A2A tool for skill {skill_name}: {e}")
                            continue

                except Exception as e:
                    print(f"Warning: Failed to discover A2A server {server_config_dict}: {e}")
                    continue

        finally:
            await client.cleanup()

        return discovered_tools

    # Run async discovery - handle both sync and async contexts
    try:
        # Check if we're already in an event loop
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context, create a task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, discover_async())
                return future.result()
        except RuntimeError:
            # No event loop, we can use asyncio.run
            return asyncio.run(discover_async())
    except Exception as e:
        print(f"Warning: A2A tool discovery failed: {e}")
        return []
