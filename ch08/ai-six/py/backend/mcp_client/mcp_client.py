import asyncio
from contextlib import AsyncExitStack
from urllib.parse import urlparse

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client


class MCPClient:
    """Standalone MCP client for connecting to and interacting with MCP servers."""
    def __init__(self):
        self.sessions: dict[str, ClientSession] = {}
        self._server_tools: dict[str, list[dict]] = {}
        self.exit_stack = AsyncExitStack()

    async def connect_to_server(self, server_id: str, server_path_or_url: str) -> list[dict]:
        """Connect to a single MCP server and return its tools."""
        if server_id in self.sessions:
            # Already connected, return cached tools
            return self._server_tools.get(server_id, [])
        
        # Check if this is a URL (remote server) or file path (local server)
        parsed = urlparse(server_path_or_url)
        is_url = parsed.scheme in ('http', 'https')
        
        if is_url:
            try:
                transport = await self.exit_stack.enter_async_context(sse_client(server_path_or_url))
                read, write = transport
                session = await self.exit_stack.enter_async_context(ClientSession(read, write))
            except Exception as e:
                print(f"Failed to connect to remote MCP server {server_path_or_url}: {e}")
                raise
        else:
            # Local file-based server
            if server_path_or_url.endswith('.py'):
                command = "python"
            elif server_path_or_url.endswith('.sh'):
                command = "bash"
            elif server_path_or_url.endswith('.js'):
                command = "node"
            else:
                raise ValueError(f"Unsupported server type: {server_path_or_url}")
            
            server_params = StdioServerParameters(
                command=command,
                args=[server_path_or_url],
                env=None
            )
            
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            stdio, write = stdio_transport
            session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))

        # Initialize session with timeout
        await asyncio.wait_for(session.initialize(), timeout=10.0)

        # List tools with timeout
        response = await asyncio.wait_for(session.list_tools(), timeout=10.0)
        tools = [{
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.inputSchema
        } for tool in response.tools]

        # Cache the session and tools
        self.sessions[server_id] = session
        self._server_tools[server_id] = tools
        
        return tools


    async def invoke_tool(self, server_id: str, tool_name: str, tool_args: dict) -> str:
        """Invoke a specific tool on the specified MCP server."""
        session = self.sessions.get(server_id)
        if not session:
            raise RuntimeError(f"No active session for server '{server_id}'. Connect to server first.")

        try:
            print(f"Invoking tool {tool_name} on server {server_id} with args: {tool_args}")
            # Add timeout to prevent hanging on slow/unresponsive servers
            result = await asyncio.wait_for(
                session.call_tool(tool_name, tool_args),
                timeout=30.0  # 30 second timeout
            )
            print(f"Tool {tool_name} completed successfully")
            return result.content[0].text if result.content else ""
        except asyncio.TimeoutError:
            print(f"Tool invocation timed out for {server_id}:{tool_name} after 30 seconds")
            raise RuntimeError(f"Tool invocation timed out for {server_id}:{tool_name} after 30 seconds")
        except Exception as e:
            print(f"Tool invocation failed for {server_id}:{tool_name}: {e}")
            raise

    def get_server_tools(self, server_id: str) -> list[dict]:
        """Get cached tools for a server."""
        return self._server_tools.get(server_id, [])
    
    def is_connected(self, server_id: str) -> bool:
        """Check if connected to a server."""
        return server_id in self.sessions
        
    async def disconnect_server(self, server_id: str):
        """Disconnect from a specific server."""
        if server_id in self.sessions:
            # Session cleanup handled by exit_stack
            del self.sessions[server_id]
            if server_id in self._server_tools:
                del self._server_tools[server_id]
    
    async def cleanup(self):
        """Cleanup all resources."""
        self.sessions.clear()
        self._server_tools.clear()
        await self.exit_stack.aclose()
