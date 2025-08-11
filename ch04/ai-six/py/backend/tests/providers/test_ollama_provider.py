import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

from backend.llm_providers.ollama_provider import OllamaProvider


class TestOllamaProvider(unittest.TestCase):

    def setUp(self):
        # Initialize OllamaProvider with a mock model
        self.provider = OllamaProvider(model="llama3")

    @patch('ollama.chat')
    def test_usage_extraction(self, mock_chat):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.message.content = "Mock response"
        mock_response.message.role = "assistant"
        mock_response.message.tool_calls = []
        
        # Add the usage attributes as get method return values
        mock_response.get.side_effect = lambda key, default=0: 15 if key == 'prompt_eval_count' else 5 if key == 'eval_count' else default
        
        mock_chat.return_value = mock_response

        # Test sending messages
        response = self.provider.send(messages=[], tool_dict={})

        # Check the usage was set correctly
        self.assertEqual(response.usage.input_tokens, 15)
        self.assertEqual(response.usage.output_tokens, 5)


if __name__ == "__main__":
    unittest.main()
