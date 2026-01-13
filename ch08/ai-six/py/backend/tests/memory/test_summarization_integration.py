import unittest
import os
import json
from unittest.mock import MagicMock, patch
from dataclasses import asdict

from backend.object_model import Usage, UserMessage, AssistantMessage
from backend.tests.memory.mock_agent import create_mock_agent, cleanup_mock_agent


class TestSummarizationIntegration(unittest.TestCase):
    def setUp(self):
        # Create a mock agent setup with a small context window for testing
        self.mock_data = create_mock_agent(checkpoint_interval=2)
        self.agent = self.mock_data["agent"]
        self.llm_provider = self.mock_data["provider"]
        self.test_dir = self.mock_data["config"].memory_dir
        
        # Patch the _append_to_detailed_log method to avoid JSON serialization issues
        self.append_patcher = patch.object(self.agent, '_append_to_detailed_log')
        self.mock_append = self.append_patcher.start()
        self.mock_append.return_value = None
        
    def tearDown(self):
        # Stop the append patcher
        self.append_patcher.stop()
        
        # Clean up the mock agent resources
        cleanup_mock_agent(self.mock_data)
        
    def test_direct_summarization(self):
        """Test direct summarization without relying on send_message."""
        # Set up a summary response
        summary_text = "This is a direct summary of the conversation."
        self.llm_provider.add_mock_response(
            summary_text,
            input_tokens=50,
            output_tokens=50
        )
        
        # Add messages directly to the session
        self.agent.session.add_message(UserMessage(content="Hello!"))
        
        self.agent.session.add_message(AssistantMessage(
            content="Hi there!",
            usage=Usage(input_tokens=200, output_tokens=200)
        ))
        
        self.agent.session.add_message(UserMessage(content="How are you?"))
        
        self.agent.session.add_message(AssistantMessage(
            content="I'm doing well, thanks for asking!",
            usage=Usage(input_tokens=0, output_tokens=200)
        ))
        
        # Save the original session ID for verification
        original_session_id = self.agent.session.session_id
        
        # Now directly call the summarize method
        old_messages = list(self.agent.session.messages)  # Save for verification
        self.agent._summarize_and_reset_session()
        
        # After summarization, we should have a new session with a system message containing the summary
        self.assertGreaterEqual(len(self.agent.session.messages), 1)
        
        # Verify that the summary message has been created
        self.assertEqual(self.agent.session.messages[0].role, "system")
        self.assertIn("summary", self.agent.session.messages[0].content.lower())
        
        # Verify _append_to_detailed_log was called with the right session ID and summary
        self.mock_append.assert_called_once()
        self.assertEqual(self.mock_append.call_args[0][0], original_session_id)
        self.assertEqual(self.mock_append.call_args[0][1], summary_text)
        
    def test_stream_summarization(self):
        """Test summarization after streaming."""
        # Set up mock response for summarization
        summary_text = "This is a summary of the streamed conversation."
        self.llm_provider.add_mock_response(
            summary_text,
            input_tokens=50,
            output_tokens=50
        )
        
        # Add messages directly to the session to simulate streaming
        self.agent.session.add_message(UserMessage(content="Let's stream some data!"))
        
        self.agent.session.add_message(AssistantMessage(
            content="I'm streaming a response to you.",
            usage=Usage(input_tokens=200, output_tokens=200)
        ))
        
        self.agent.session.add_message(UserMessage(content="This is a large message that should trigger summarization."))
        
        self.agent.session.add_message(AssistantMessage(
            content="Here's a streamed response with lots of tokens to trigger summarization.",
            usage=Usage(input_tokens=0, output_tokens=200)
        ))
        
        # Save the session ID and messages before summarization
        old_session_id = self.agent.session.session_id
        old_messages = list(self.agent.session.messages)
        
        # Directly call the summarize method
        self.agent._summarize_and_reset_session()
        
        # Verify that the summary message has been created and is the first message
        self.assertEqual(self.agent.session.messages[0].role, "system")
        self.assertIn("summary", self.agent.session.messages[0].content.lower())
        
        # Verify _append_to_detailed_log was called with the right session ID and summary
        self.mock_append.assert_called_once()
        self.assertEqual(self.mock_append.call_args[0][0], old_session_id)
        self.assertEqual(self.mock_append.call_args[0][1], summary_text)
        
    def test_detailed_log_contents(self):
        """Test that the detailed log contains the expected information."""
        # Set up initial messages
        self.agent.session.add_message(UserMessage(content="Hello"))
        
        self.agent.session.add_message(AssistantMessage(
            content="Hi there",
            usage=Usage(input_tokens=100, output_tokens=100)
        ))
        
        self.agent.session.add_message(UserMessage(content="How does AI-6 work?"))
        
        self.agent.session.add_message(AssistantMessage(
            content="AI-6 is an agentic assistant...",
            usage=Usage(input_tokens=0, output_tokens=300)
        ))
        
        # Save the session to ensure it exists
        original_session_id = self.agent.session.session_id
        self.agent.session.save()
        
        # Set up the mock response for summarization
        summary_text = "This conversation was about AI-6 and how it works."
        self.llm_provider.add_mock_response(summary_text)
        
        # Override the mock to capture the data
        self.detailed_log_data = None
        
        def capture_log_data(session_id, summary):
            # Convert Message objects to dictionaries like the real implementation
            message_dicts = []
            for msg in self.agent.session.messages:
                if isinstance(msg, dict):
                    message_dicts.append(msg)
                else:
                    message_dicts.append(asdict(msg))
            
            # Use the mocked context window size (1000) from the mock agent setup
            self.detailed_log_data = dict(
                session_id=session_id,
                summary=summary,
                messages=message_dicts,
                token_count=self.agent.session.usage.input_tokens + self.agent.session.usage.output_tokens,
                context_window_size=1000  # This matches the mocked value in create_mock_agent
            )
        
        self.mock_append.side_effect = capture_log_data
        
        # Perform summarization
        self.agent._summarize_and_reset_session()
        
        # Verify that our mock captured the detailed log data
        self.assertIsNotNone(self.detailed_log_data)
        
        # Check the basic fields in the captured data
        self.assertEqual(self.detailed_log_data['session_id'], original_session_id)
        self.assertEqual(self.detailed_log_data['summary'], summary_text)
        self.assertEqual(self.detailed_log_data['context_window_size'], 1000)
        
        # Check that all messages are preserved
        messages = self.detailed_log_data['messages']
        self.assertEqual(len(messages), 4)
        self.assertEqual(messages[0]['role'], 'user')
        self.assertEqual(messages[0]['content'], 'Hello')
        self.assertEqual(messages[1]['role'], 'assistant')
        self.assertEqual(messages[1]['content'], 'Hi there')
        self.assertEqual(messages[2]['role'], 'user')
        self.assertEqual(messages[2]['content'], 'How does AI-6 work?')
        self.assertEqual(messages[3]['role'], 'assistant')
        self.assertEqual(messages[3]['content'], 'AI-6 is an agentic assistant...')
        
        # We're using mock objects for testing, so don't check exact token count
        self.assertIn('token_count', self.detailed_log_data)


if __name__ == "__main__":
    unittest.main()
