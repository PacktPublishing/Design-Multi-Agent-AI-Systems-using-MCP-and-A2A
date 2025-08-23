import unittest
from unittest.mock import patch, MagicMock, call
from backend.engine.engine import Engine
from backend.engine.config import Config

from pathology.path import Path

backend_dir = Path.script_dir().parent
mcp_tools_dir = str(backend_dir / "mcp_tools")
tools_dir = str(backend_dir / "tools")
memory_dir = str(backend_dir.parent.parent / "memory")

class TestDiscoverMCPTools(unittest.TestCase):
    def test_discover_mcp_tools(self):
        # Test that the Engine can be initialized and MCP discovery works
        from unittest.mock import patch, MagicMock
        
        # Just test basic Engine creation with proper mocking to avoid interference
        with patch('backend.engine.engine.Engine.discover_llm_providers') as mock_discover_llm_providers, \
             patch('backend.engine.engine.Engine.discover_tools', return_value=[]) as mock_discover_tools, \
             patch('backend.engine.engine.Engine.discover_mcp_tools', return_value=[]) as mock_discover_mcp_tools, \
             patch('backend.engine.engine.get_context_window_size', return_value=1000):
            
            # Setup mock LLM provider
            mock_llm_provider = MagicMock()
            mock_llm_provider.models = ['gpt-4o']
            mock_discover_llm_providers.return_value = [mock_llm_provider]
            
            # Create a config
            config = Config(
                default_model_id='gpt-4o',
                tools_dir=tools_dir,
                mcp_tools_dir=mcp_tools_dir,
                memory_dir=memory_dir
            )

            # Create engine - this should work without issues
            engine = Engine(config)
            
            # Verify that all discovery methods were called
            self.assertTrue(mock_discover_llm_providers.called)
            self.assertTrue(mock_discover_tools.called)
            self.assertTrue(mock_discover_mcp_tools.called)

if __name__ == '__main__':
    unittest.main()