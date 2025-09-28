import asyncio
import threading

from backend.object_model.tool import Tool, Parameter
from backend.mcp_client.mcp_client import MCPClient


def _json_schema_to_parameters(schema: dict) -> tuple[list[Parameter], set[str]]:
    """Convert JSON schema to Tool parameters and required set."""
    parameters = []
    required = set()
    
    if not isinstance(schema, dict) or 'properties' not in schema:
        return parameters, required
    
    # Get required fields
    if 'required' in schema and isinstance(schema['required'], list):
        required = set(schema['required'])
    
    # Convert properties to parameters
    for prop_name, prop_def in schema['properties'].items():
        param_type = prop_def.get('type', 'string')
        description = prop_def.get('description', f'{prop_name} parameter')
        
        # Map JSON schema types to our parameter types
        if param_type == 'array':
            param_type = 'array'
        elif param_type in ['integer', 'number']:
            param_type = 'number'
        elif param_type == 'boolean':
            param_type = 'boolean'
        else:
            param_type = 'string'
            
        parameters.append(Parameter(
            name=prop_name,
            type=param_type,
            description=description
        ))
    
    return parameters, required


class MCPTool(Tool):
    """Tool that uses MCP (Model Context Protocol) servers."""
    
    # Shared MCP client instance across all MCP tools
    _client: MCPClient = None
    _client_lock = threading.Lock()
    # Shared event loop for all MCP operations
    _event_loop = None
    _loop_thread = None
    _loop_lock = threading.Lock()
    
    def __init__(self, server_id: str, server_path_or_url: str, tool_info: dict):
        """Initialize from MCP tool information."""
        tool_name = tool_info['name']
        description = tool_info.get('description', f'{server_id} tool: {tool_name}')
        
        # Convert parameters from JSON schema
        parameters, required = _json_schema_to_parameters(
            tool_info.get('parameters', {})
        )
        
        super().__init__(name=tool_name, description=description, parameters=parameters, required=required)
        self.server_id = server_id
        self.server_path_or_url = server_path_or_url
        self.mcp_tool_name = tool_name

    @classmethod
    def _get_client(cls) -> MCPClient:
        """Get or create the shared MCP client instance."""
        if cls._client is None:
            with cls._client_lock:
                if cls._client is None:
                    cls._client = MCPClient()
        return cls._client
    
    @classmethod
    def _get_or_create_loop(cls):
        """Get or create a shared event loop for MCP operations."""
        # Always use our own managed loop for sync tool execution
        # This avoids "event loop is closed" issues from creating/closing loops repeatedly
        
        if cls._event_loop is None or cls._event_loop.is_closed():
            with cls._loop_lock:
                if cls._event_loop is None or cls._event_loop.is_closed():
                    cls._event_loop = asyncio.new_event_loop()
                    
        return cls._event_loop
    
    def _ensure_connected(self):
        """Ensure connection to the MCP server."""
        client = self._get_client()
        loop = self._get_or_create_loop()
        if not client.is_connected(self.server_id):
            # Use shared event loop for connection
            asyncio.set_event_loop(loop)
            loop.run_until_complete(client.connect_to_server(self.server_id, self.server_path_or_url))
        return client, loop
    
    def run(self, **kwargs) -> str:
        """Execute the MCP tool with the given arguments."""
        client, loop = self._ensure_connected()
        return loop.run_until_complete(
            client.invoke_tool(self.server_id, self.mcp_tool_name, kwargs)
        )
    
    @classmethod
    def cleanup_all(cls):
        """Cleanup all MCP connections. Call this on shutdown."""
        if cls._client is not None:
            # Use our managed loop for cleanup
            loop = cls._get_or_create_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(cls._client.cleanup())
            finally:
                # Now we can close our managed loop
                if cls._event_loop and not cls._event_loop.is_closed():
                    cls._event_loop.close()
                cls._event_loop = None
            cls._client = None
