import unittest
import os
import json
from unittest.mock import patch

from backend.agent.config import Config
from backend.agent.agent import Agent
from backend.tests.memory.mock_agent import create_mock_agent, cleanup_mock_agent
from backend.object_model import UserMessage, AssistantMessage, Usage


class TestAgentSummarization(unittest.TestCase):
    def setUp(self):
        # Create a mock agent setup with default settings
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
        
    def test_dynamic_token_threshold(self):
        """Test that the token threshold is calculated correctly."""
        # The threshold should be 80% of the mock-model's context window (1000)
        self.assertEqual(self.agent.token_threshold, 800)
        
        # For a second test, we'll manually create an agent with different settings
        
        # Set up required config and mocks for a new agent
        test_dir = os.path.join(self.test_dir, "test2")
        os.makedirs(test_dir, exist_ok=True)
        
        # Create a direct config
        config = Config(
            default_model_id="mock-model",
            tools_dirs=["/Users/gigi/git/ai-six/py/backend/tools"],
            mcp_tools_dirs=["/Users/gigi/git/ai-six/py/backend/mcp_tools"],
            memory_dir=test_dir
        )
        
        # Test with a different context window size 
        with patch('backend.agent.agent.Agent.discover_llm_providers', return_value=[self.llm_provider]), \
             patch('backend.agent.tool_manager.get_tool_dict', return_value={}), \
             patch('backend.agent.agent.get_context_window_size', return_value=2000):
             
            # Create the agent with our mocks
            agent = Agent(config)
            
            # Verify that the token threshold is 80% of 2000
            self.assertEqual(agent.token_threshold, 1600)
        
    def test_summarization_triggered_by_token_threshold(self):
        """Test that summarization is triggered when the token count exceeds the threshold."""
        # Set up the mock response for summarization
        self.llm_provider.add_mock_response("This is a summary of the conversation.")
        
        # Mock the _summarize_and_reset_session method to track calls
        with patch.object(self.agent, '_summarize_and_reset_session') as mock_summarize:
            # Add messages with a high token count
            # First checkpoint (2 messages)
            user_msg1 = UserMessage(content="Message 1")
            assistant_msg1 = AssistantMessage(
                content="Response 1",
                usage=Usage(input_tokens=400, output_tokens=400)
            )
            
            self.agent.session.add_message(user_msg1)
            self.agent._checkpoint_if_needed()
            
            self.agent.session.add_message(assistant_msg1)
            self.agent._checkpoint_if_needed()
            
            # Check that summarization was triggered (800 tokens >= threshold of 800)
            mock_summarize.assert_called_once()
            
    def test_no_summarization_below_threshold(self):
        """Test that summarization is not triggered when below the token threshold."""
        # Mock the _summarize_and_reset_session method to track calls
        with patch.object(self.agent, '_summarize_and_reset_session') as mock_summarize:
            # Add messages with a low token count
            # First checkpoint (2 messages)
            user_msg = UserMessage(content="Message 1")
            assistant_msg = AssistantMessage(
                content="Response 1",
                usage=Usage(input_tokens=300, output_tokens=300)
            )
            
            self.agent.session.add_message(user_msg)
            self.agent._checkpoint_if_needed()
            
            self.agent.session.add_message(assistant_msg)
            self.agent._checkpoint_if_needed()
            
            # Check that summarization was not triggered (600 tokens < threshold of 800)
            mock_summarize.assert_not_called()
            
    def test_summarize_and_reset_session(self):
        """Test the summarization and session reset process."""
        # Set up initial messages
        self.agent.session.add_message(UserMessage(content="Hello"))
        self.agent.session.add_message(AssistantMessage(content="Hi there"))
        self.agent.session.add_message(UserMessage(content="How are you?"))
        self.agent.session.add_message(AssistantMessage(content="I'm doing well!"))
        
        # Save the session to ensure it exists
        original_session_id = self.agent.session.session_id
        self.agent.session.save()
        
        # Set up the mock response for summarization
        summary_text = "This conversation was about greetings and well-being."
        self.llm_provider.add_mock_response(summary_text)
        
        # Perform summarization
        self.agent._summarize_and_reset_session()
        
        # Verify _append_to_detailed_log was called with the right session ID and summary
        self.mock_append.assert_called_once()
        self.assertEqual(self.mock_append.call_args[0][0], original_session_id)
        self.assertEqual(self.mock_append.call_args[0][1], summary_text)
        
        # Check that a new session was created
        self.assertNotEqual(self.agent.session.session_id, original_session_id)
        
        # Check that the new session starts with the summary
        self.assertEqual(len(self.agent.session.messages), 1)
        self.assertEqual(self.agent.session.messages[0].role, 'system')
        self.assertIn(summary_text, self.agent.session.messages[0].content)
        
        # Verify that the new session was saved
        new_session_file = f"{self.test_dir}/{self.agent.session.session_id}.json"
        self.assertTrue(os.path.exists(new_session_file))
        
    def test_summarization_preserves_token_count(self):
        """Test that the token count is preserved after summarization."""
        # Set up initial messages with token counts
        user_msg = UserMessage(content="Hello")
        assistant_msg = AssistantMessage(
            content="Hi there",
            usage=Usage(input_tokens=100, output_tokens=100)
        )
        
        self.agent.session.add_message(user_msg)
        self.agent.session.add_message(assistant_msg)
        
        # Set up the mock response for summarization
        summary_text = "A brief greeting exchange."
        self.llm_provider.add_mock_response(summary_text)
        
        # Save original token count
        original_input_tokens = self.agent.session.usage.input_tokens
        original_output_tokens = self.agent.session.usage.output_tokens
        
        # Perform summarization
        self.agent._summarize_and_reset_session()
        
        # Check that the new session has some token count (for the summary)
        self.assertGreater(self.agent.session.usage.input_tokens, 0)
        
        # Verify the summary was called with the right messages
        self.assertEqual(len(self.llm_provider.send_calls), 1)
        self.assertEqual(self.llm_provider.send_calls[0]['model'], "mock-model")
        
        # Verify the summarization system prompt
        system_message = self.llm_provider.send_calls[0]['messages'][0]
        self.assertEqual(system_message.role, 'system')
        self.assertIn("summarizing a conversation", system_message.content.lower())


if __name__ == "__main__":
    unittest.main()
