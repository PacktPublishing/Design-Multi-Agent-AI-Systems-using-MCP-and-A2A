import unittest
import tempfile
import shutil
import os
from unittest.mock import MagicMock, patch

from backend.agent.config import Config
from backend.agent.agent import Agent
from backend.object_model import LLMProvider, Usage, AssistantMessage

class MockLLMProvider(LLMProvider):
    def send(self, messages, tool_dict, model=None):
        return AssistantMessage(content="Test response", role="assistant", tool_calls=None, usage=Usage(10, 10))
    
    @property
    def models(self):
        return ["mock-model"]
    
    def model_response_to_message(self, response):
        return {"role": response.role, "content": response.content}

class TestSetup(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.llm_provider = MockLLMProvider()
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)
    
    def test_agent_initialization(self):
        # Create the config
        config = Config(
            default_model_id="mock-model",
            tools_dirs=["/Users/gigi/git/ai-six/py/backend/tools"],
            mcp_tools_dirs=["/Users/gigi/git/ai-six/py/backend/mcp_tools"],
            memory_dir=self.test_dir
        )
        
        # Patch the discover_llm_providers method to return our mock provider
        # Also patch get_context_window_size to return a fixed value for testing
        with patch('backend.agent.agent.Agent.discover_llm_providers') as mock_discover, \
             patch('backend.agent.agent.get_context_window_size') as mock_window_size:
            mock_discover.return_value = [self.llm_provider]
            mock_window_size.return_value = 1000
            
            # Create the agent
            agent = Agent(config)
            
            # Verify the agent was initialized correctly
            self.assertEqual(agent.default_model_id, "mock-model")
            # Token threshold should be 80% of 1000 = 800
            self.assertEqual(agent.token_threshold, 800)
            self.assertEqual(len(agent.llm_providers), 1)
            self.assertIs(agent.llm_providers[0], self.llm_provider)

if __name__ == "__main__":
    unittest.main()
