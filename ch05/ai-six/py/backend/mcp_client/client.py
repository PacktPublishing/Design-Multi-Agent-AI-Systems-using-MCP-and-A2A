import asyncio
import os
from contextlib import AsyncExitStack
from typing import List

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class Client:
    def __init__(self, server_directory: str):
        self.server_directory = server_directory
        self.session = None
        self.exit_stack = AsyncExitStack()

    async def connect_to_servers(self) -> List[str]:
        """Connect to all MCP servers in the specified directory and list available tools."""
        tool_list = []
        for filename in os.listdir(self.server_directory):
            if filename.endswith('.py') or filename.endswith('.js'):
                server_path = os.path.join(self.server_directory, filename)
                tools = await self.connect_to_server(server_path)
                tool_list.extend(tools)
        return tool_list

    async def connect_to_server(self, server_path: str) -> List[dict]:
        """Connect to a single MCP server and return its tools."""
        is_python = server_path.endswith('.py')
        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_path],
            env=None
        )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        response = await self.session.list_tools()
        tools = [{
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.inputSchema
        } for tool in response.tools]

        return tools

    async def invoke_tool(self, tool_name: str, tool_args: dict) -> str:
        """Invoke a specific tool on the connected MCP server."""
        if not self.session:
            raise RuntimeError("No active session. Connect to a server first.")

        result = await self.session.call_tool(tool_name, tool_args)
        return result.content

    async def cleanup(self):
        """Cleanup resources."""
        await self.exit_stack.aclose()