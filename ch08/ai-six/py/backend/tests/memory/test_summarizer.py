import unittest
from unittest.mock import MagicMock

from backend.agent.summarizer import Summarizer
from backend.object_model import AssistantMessage, UserMessage, ToolMessage, ToolCall


class TestSummarizer(unittest.TestCase):
    def setUp(self):
        # Create a mock LLM provider
        self.mock_llm_provider = MagicMock()
        
        # Set up the summarizer with the mock provider
        self.summarizer = Summarizer(self.mock_llm_provider)
        
        # Sample messages for testing
        self.sample_messages = [
            UserMessage(content="Hello, AI-6!"),
            AssistantMessage(content="Hello! How can I help you today?"),
            UserMessage(content="Tell me about yourself."),
            AssistantMessage(content="I am AI-6, an agentic AI assistant.")
        ]
        
        # Sample model ID
        self.model_id = "test-model"
        
    def test_format_session(self):
        """Test formatting a session for the LLM."""
        formatted = self.summarizer._format_session(self.sample_messages)
        
        # Check that the formatting is correct
        expected_format = (
            "User: Hello, AI-6!\n\n"
            "Assistant: Hello! How can I help you today?\n\n"
            "User: Tell me about yourself.\n\n"
            "Assistant: I am AI-6, an agentic AI assistant."
        )
        self.assertEqual(formatted, expected_format)
        
    def test_format_session_with_tool_calls(self):
        """Test formatting a session that includes tool calls."""
        messages_with_tools = self.sample_messages + [
            ToolMessage(content="file1.txt\nfile2.txt", name="ls", tool_call_id="call_123")
        ]
        
        formatted = self.summarizer._format_session(messages_with_tools)
        
        # Check that the formatting is correct
        expected_format = (
            "User: Hello, AI-6!\n\n"
            "Assistant: Hello! How can I help you today?\n\n"
            "User: Tell me about yourself.\n\n"
            "Assistant: I am AI-6, an agentic AI assistant.\n\n"
            "Tool (ls): file1.txt\nfile2.txt"
        )
        self.assertEqual(formatted, expected_format)
        
    def test_summarize(self):
        """Test summarizing a session."""
        # Set up the mock response
        mock_response = AssistantMessage(
            content="This is a summary of the session.",
            role="assistant",
            tool_calls=None,
            usage=MagicMock(input_tokens=10, output_tokens=5)
        )
        self.mock_llm_provider.send.return_value = mock_response
        
        # Call the summarize method
        summary = self.summarizer.summarize(self.sample_messages, self.model_id)
        
        # Check that the LLM provider was called correctly
        self.mock_llm_provider.send.assert_called_once()
        
        # Get the arguments passed to the send method
        args, _ = self.mock_llm_provider.send.call_args
        messages_arg, tools_arg, model_id_arg = args
        
        # Check that the correct model ID was used
        self.assertEqual(model_id_arg, self.model_id)
        
        # Check that the tools dictionary is empty
        self.assertEqual(tools_arg, {})
        
        # Check that the messages include a system message and a user message
        self.assertEqual(len(messages_arg), 2)
        self.assertEqual(messages_arg[0].role, "system")
        self.assertEqual(messages_arg[1].role, "user")
        
        # Check that the user message contains the formatted session
        self.assertIn(self.summarizer._format_session(self.sample_messages), messages_arg[1].content)
        
        # Check that the returned summary is correct
        self.assertEqual(summary, "This is a summary of the session.")


if __name__ == "__main__":
    unittest.main()
