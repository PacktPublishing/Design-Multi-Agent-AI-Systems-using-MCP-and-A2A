import unittest
from unittest.mock import patch, MagicMock
from backend.tools.claude.claude import Claude


class ClaudeToolTest(unittest.TestCase):

    def setUp(self):
        self.claude_tool = Claude()

    def test_init(self):
        self.assertEqual(self.claude_tool.name, 'claude')
        self.assertIn('prompt', [p.name for p in self.claude_tool.parameters])
        self.assertIn('model', [p.name for p in self.claude_tool.parameters])
        self.assertIn('max_tokens', [p.name for p in self.claude_tool.parameters])
        self.assertIn('temperature', [p.name for p in self.claude_tool.parameters])
        self.assertEqual(self.claude_tool.required, {'prompt'})

    def test_configure(self):
        config = {'api_key': 'test-api-key'}
        
        with patch('backend.tools.claude.claude.anthropic') as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            
            self.claude_tool.configure(config)
            
            self.assertEqual(self.claude_tool.api_key, 'test-api-key')
            mock_anthropic.Anthropic.assert_called_once_with(api_key='test-api-key')
            self.assertEqual(self.claude_tool.client, mock_client)

    def test_run_without_configuration(self):
        result = self.claude_tool.run(prompt="test prompt")
        self.assertIn("Error: Claude API key not configured", result)

    def test_run_with_configuration(self):
        # Configure the tool
        mock_client = MagicMock()
        self.claude_tool.client = mock_client
        
        # Mock the API response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="This is Claude's response")]
        mock_client.messages.create.return_value = mock_response
        
        # Test the run method
        result = self.claude_tool.run(prompt="test prompt")
        
        # Verify the API was called correctly
        mock_client.messages.create.assert_called_once_with(
            model='claude-4-sonnet-20250115',
            max_tokens=1000,
            temperature=0.7,
            messages=[{"role": "user", "content": "test prompt"}]
        )
        
        self.assertEqual(result, "This is Claude's response")

    def test_run_with_custom_parameters(self):
        # Configure the tool
        mock_client = MagicMock()
        self.claude_tool.client = mock_client
        
        # Mock the API response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Custom response")]
        mock_client.messages.create.return_value = mock_response
        
        # Test with custom parameters
        result = self.claude_tool.run(
            prompt="custom prompt",
            model="claude-3-5-haiku-20241022",
            max_tokens=500,
            temperature=0.3
        )
        
        # Verify the API was called with custom parameters
        mock_client.messages.create.assert_called_once_with(
            model='claude-3-5-haiku-20241022',
            max_tokens=500,
            temperature=0.3,
            messages=[{"role": "user", "content": "custom prompt"}]
        )
        
        self.assertEqual(result, "Custom response")

    def test_run_api_error(self):
        # Configure the tool
        mock_client = MagicMock()
        self.claude_tool.client = mock_client
        
        # Mock an API error
        mock_client.messages.create.side_effect = Exception("API Error")
        
        # Test error handling
        result = self.claude_tool.run(prompt="test prompt")
        
        self.assertIn("Error calling Claude API: API Error", result)


if __name__ == "__main__":
    unittest.main()