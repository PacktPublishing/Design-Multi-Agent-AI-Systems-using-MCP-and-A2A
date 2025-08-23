import os
import re
import unittest
from unittest.mock import patch, MagicMock

from backend.llm_providers.openai_provider import OpenAIProvider
from backend.object_model import AssistantMessage, ToolCall, Usage, UserMessage


class TestOpenAIStreaming(unittest.TestCase):
    """Test the streaming functionality of the OpenAI provider."""

    def setUp(self):
        """Set up the test environment."""
        # Skip tests if no API key is available
        if 'OPENAI_API_KEY' not in os.environ:
            self.skipTest("OPENAI_API_KEY environment variable not set")
            
        self.api_key = os.environ['OPENAI_API_KEY']
        self.provider = OpenAIProvider(self.api_key)
    
    @patch('openai.OpenAI')
    def test_stream_method_exists(self, mock_openai):
        """Test that the stream method exists and returns an iterator."""
        # Setup mock
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        # Create a mock stream response
        mock_stream = [
            MagicMock(choices=[MagicMock(delta=MagicMock(content="Hello"))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=" world"))]),
        ]
        mock_client.chat.completions.create.return_value = mock_stream
        
        # Create a provider with the mock
        provider = OpenAIProvider("fake-key")
        
        # Call the stream method
        messages = [{"role": "user", "content": "Hello"}]
        tool_dict = {}
        
        # Get the iterator
        stream_iterator = provider.stream(messages, tool_dict)
        
        # Verify it's an iterator
        self.assertTrue(hasattr(stream_iterator, '__iter__'))
    
    def test_stream_integration(self):
        """Integration test for streaming with the actual OpenAI API."""
        # This test will only run if OPENAI_API_KEY is set
        messages = [UserMessage(content="Say hello world")]
        tool_dict = {}
        
        # Get the stream
        stream = self.provider.stream(messages, tool_dict)
        
        # Collect all chunks
        chunks = list(stream)
        
        # Verify we got at least one response
        self.assertTrue(len(chunks) > 0)
        
        # Verify the final response contains "hello world" (case insensitive)
        final_response = chunks[-1]
        self.assertIsInstance(final_response, AssistantMessage)
        self.assertTrue(re.search(r'hello.+world', final_response.content.lower()))

if __name__ == '__main__':
    unittest.main()