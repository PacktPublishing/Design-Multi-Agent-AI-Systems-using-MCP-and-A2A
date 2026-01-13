import unittest
from unittest.mock import patch, MagicMock, call
from backend.agent.agent import Agent
from backend.agent.config import Config

from pathology.path import Path

backend_dir = Path.script_dir().parent
mcp_tools_dir = str(backend_dir / "mcp_tools")
tools_dir = str(backend_dir / "tools")
memory_dir = str(backend_dir.parent.parent / "memory")

class TestDiscoverMCPTools(unittest.TestCase):
    def test_discover_mcp_tools(self):
        # Test that the Agent can be initialized and MCP discovery works
        from unittest.mock import patch, MagicMock
        
        # Mock ToolManager instead of Agent.discover_tools
        with patch('backend.agent.agent.Agent.discover_llm_providers') as mock_discover_llm_providers, \
             patch('backend.agent.tool_manager.get_tool_dict', return_value={}) as mock_get_tool_dict, \
             patch('backend.agent.agent.get_context_window_size', return_value=1000):
            
            # Setup mock LLM provider
            mock_llm_provider = MagicMock()
            mock_llm_provider.models = ['gpt-4o']
            mock_discover_llm_providers.return_value = [mock_llm_provider]
            
            # Create a config  
            config = Config(
                default_model_id='gpt-4o',
                tools_dirs=[tools_dir],
                mcp_tools_dirs=[mcp_tools_dir],
                memory_dir=memory_dir
            )

            # Create agent - this should work without issues
            agent = Agent(config)
            
            # Verify that discovery methods were called
            self.assertTrue(mock_discover_llm_providers.called)
            self.assertTrue(mock_get_tool_dict.called)

if __name__ == '__main__':
    unittest.main()
