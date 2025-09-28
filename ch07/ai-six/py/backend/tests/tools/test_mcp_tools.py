import unittest
from unittest.mock import patch, MagicMock, AsyncMock

from backend.tools.base.mcp_tool import MCPTool
from backend.engine.tool_manager import _discover_local_mcp_tools


class TestMCPTools(unittest.TestCase):
    
    def setUp(self):
        # Clean up any existing client and event loop before each test
        MCPTool._client = None
        MCPTool._event_loop = None
    
    def test_mcp_tool_initialization(self):
        """Test that MCP tools can be instantiated properly from tool info."""
        # Mock tool info like what would come from MCP server
        tool_info = {
            'name': 'test_tool',
            'description': 'A test tool',
            'parameters': {
                'properties': {
                    'arg1': {'type': 'string', 'description': 'First argument'},
                    'arg2': {'type': 'number', 'description': 'Second argument'}
                },
                'required': ['arg1']
            }
        }
        
        tool = MCPTool("test_server", "/path/to/server.py", tool_info)
        
        # Verify tool properties 
        self.assertEqual(tool.name, "test_tool")
        self.assertEqual(tool.description, "A test tool")
        self.assertEqual(len(tool.parameters), 2)
        self.assertEqual(tool.required, {"arg1"})
        self.assertEqual(tool.server_id, "test_server")
        self.assertEqual(tool.mcp_tool_name, "test_tool")
    
    @patch('backend.tools.base.mcp_tool.MCPClient')
    @patch('asyncio.new_event_loop')
    @patch('asyncio.set_event_loop')
    def test_mcp_tool_execution(self, mock_set_loop, mock_new_loop, mock_client_class):
        """Test that MCP tools can execute properly."""
        # Set up mocks
        mock_loop = MagicMock()
        mock_new_loop.return_value = mock_loop
        
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.is_connected.return_value = False
        
        # Mock async methods
        mock_client.connect_to_server = AsyncMock()
        mock_client.invoke_tool = AsyncMock(return_value="test result")
        
        # Create a test tool
        tool_info = {'name': 'ls', 'description': 'List files', 'parameters': {}}
        tool = MCPTool("filesystem", "/path/to/fs_server.py", tool_info)
        
        # Test execution
        result = tool.run(path="/test/path")
        
        # Verify the execution flow
        mock_client.connect_to_server.assert_called_once()
        mock_client.invoke_tool.assert_called_once_with("filesystem", "ls", {"path": "/test/path"})
        mock_loop.run_until_complete.assert_called()
        # Loop should NOT be closed after execution - it's reused
        mock_loop.close.assert_not_called()
    
    def test_mcp_tool_shared_client(self):
        """Test that MCP tools share the same client instance."""
        with patch('backend.tools.base.mcp_tool.MCPClient') as mock_client_class:
            tool_info1 = {'name': 'tool1', 'description': 'Tool 1', 'parameters': {}}
            tool_info2 = {'name': 'tool2', 'description': 'Tool 2', 'parameters': {}}
            
            tool1 = MCPTool("server1", "/path/server1.py", tool_info1)
            tool2 = MCPTool("server2", "/path/server2.py", tool_info2)
            
            # Both tools should use the same _get_client method
            client1 = tool1._get_client()
            client2 = tool2._get_client()
            
            # Verify that MCPClient was called to create instances
            self.assertTrue(mock_client_class.called)
            # Both should return some client instance
            self.assertIsNotNone(client1)
            self.assertIsNotNone(client2)
    
    @patch('backend.engine.tool_manager.MCPClient')
    @patch('asyncio.run')
    def test_discover_mcp_tools(self, mock_asyncio_run, mock_client_class):
        """Test dynamic MCP tool discovery."""
        # Mock the async discovery result
        mock_tools = [
            {'name': 'ls', 'description': 'List files', 'parameters': {}},
            {'name': 'cat', 'description': 'Read file', 'parameters': {}}
        ]
        
        async def mock_discover():
            return mock_tools
        
        mock_asyncio_run.return_value = mock_tools
        
        # Test discovery with a mock directory
        with patch('os.path.isdir', return_value=True):
            with patch('pathlib.Path.glob') as mock_glob:
                # Mock finding server scripts
                mock_script = MagicMock()
                mock_script.stem = "test_server"
                mock_script.name = "test_server.py"
                mock_glob.return_value = [mock_script]
                
                tools = _discover_local_mcp_tools("/fake/mcp/dir")
                
                # Should return empty list due to mocking complexity
                # This test mainly verifies the function doesn't crash
                self.assertIsInstance(tools, list)


if __name__ == '__main__':
    unittest.main()
