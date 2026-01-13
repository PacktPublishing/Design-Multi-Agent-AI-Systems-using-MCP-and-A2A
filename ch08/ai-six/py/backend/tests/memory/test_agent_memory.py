import unittest
import tempfile
import shutil
import os
from unittest.mock import MagicMock, patch

from backend.agent.config import Config
from backend.agent.agent import Agent
from backend.object_model import LLMProvider, ToolCall, AssistantMessage
from backend.agent.session import Session
from backend.agent.session_manager import SessionManager


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""
    
    def __init__(self):
        self.mock_responses = []
        
    def add_mock_response(self, content, tool_calls=None):
        """Add a mock response to be returned by the send method."""
        self.mock_responses.append(AssistantMessage(
            content=content,
            role="assistant",
            tool_calls=tool_calls,
            usage=None
        ))
        
    def send(self, messages, tool_dict, model=None):
        """Return the next mock response."""
        if not self.mock_responses:
            return AssistantMessage(content="Default response", role="assistant", tool_calls=None, usage=None)
        return self.mock_responses.pop(0)
        
    @property
    def models(self):
        return ["mock-model"]
        
    def model_response_to_message(self, response):
        """Convert a response to a message."""
        return {
            "role": "assistant",
            "content": response.content,
            "tool_calls": [
                {
                    "id": t.id,
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "arguments": t.arguments
                    }
                } for t in response.tool_calls
            ] if response.tool_calls else []
        }


class TestAgentMemory(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for testing
        self.test_dir = tempfile.mkdtemp()
        
        # Create a mock LLM provider
        self.llm_provider = MockLLMProvider()
        
        # Create a config object for the engine
        
        # Create a config with the mock provider
        self.config = Config(
            default_model_id="mock-model",
            tools_dirs=["/Users/gigi/git/ai-six/py/backend/tools"],
            mcp_tools_dirs=["/Users/gigi/git/ai-six/py/backend/mcp_tools"],
            memory_dir=self.test_dir
        )
        
        # Patch the provider discovery method
        self.discover_patcher = patch('backend.agent.agent.Agent.discover_llm_providers')
        self.mock_discover = self.discover_patcher.start()
        self.mock_discover.return_value = [self.llm_provider]
        
        # Patch ToolManager to avoid actual discovery
        self.tool_manager_patcher = patch('backend.agent.tool_manager.get_tool_dict')
        self.mock_tool_manager = self.tool_manager_patcher.start()
        self.mock_tool_manager.return_value = {}
        
        # Patch the get_context_window_size function to return a fixed value for testing
        self.window_size_patcher = patch('backend.agent.agent.get_context_window_size')
        self.mock_window_size = self.window_size_patcher.start()
        self.mock_window_size.return_value = 1000
        
        # Create an agent with the config
        self.agent = Agent(self.config)
        
    def tearDown(self):
        # Stop the patchers
        self.discover_patcher.stop()
        self.tool_manager_patcher.stop()
        self.window_size_patcher.stop()
        
        # Clean up the temporary directory
        shutil.rmtree(self.test_dir)
        
    def test_session_initialization(self):
        """Test that the session is initialized correctly."""
        self.assertIsNotNone(self.agent.session)
        self.assertIsInstance(self.agent.session, Session)
        self.assertIsNotNone(self.agent.session_manager)
        self.assertIsInstance(self.agent.session_manager, SessionManager)
        self.assertEqual(len(self.agent.session.messages), 0)
        
    def test_send_message(self):
        """Test sending a message and receiving a response."""
        # Set up the mock response
        self.llm_provider.add_mock_response("I'll help you with that!")
        
        # Send a message
        response = self.agent.send_message("Hello", "mock-model", None)
        
        # Check the response
        self.assertEqual(response, "I'll help you with that!")
        
        # Check that the message was added to the session
        self.assertEqual(len(self.agent.session.messages), 2)
        self.assertEqual(self.agent.session.messages[0].role, "user")
        self.assertEqual(self.agent.session.messages[0].content, "Hello")
        self.assertEqual(self.agent.session.messages[1].role, "assistant")
        self.assertEqual(self.agent.session.messages[1].content, "I'll help you with that!")
        
    def test_session_saving(self):
        """Test that sessions are saved correctly."""
        # Set up the mock response
        self.llm_provider.add_mock_response("I'll help you with that!")
        
        # Send a message
        self.agent.send_message("Hello", "mock-model", None)
        
        # Explicitly save the session
        self.agent.session.save()
        
        # Get the session ID
        session_id = self.agent.get_session_id()
        
        # Check that the session file exists - file is now just session_id.json without a title
        session_file = f"{self.test_dir}/{session_id}.json"
        self.assertTrue(os.path.exists(session_file))
        
        # Create a new config with the session ID
        new_config = Config(
            default_model_id="mock-model",
            tools_dirs=["/Users/gigi/git/ai-six/py/backend/tools"],
            mcp_tools_dirs=["/Users/gigi/git/ai-six/py/backend/mcp_tools"],
            memory_dir=self.test_dir,
            session_id=session_id
        )
        
        # Create a new agent with the config (using the same patchers as in setUp)
        with patch('backend.agent.agent.Agent.discover_llm_providers', return_value=[self.llm_provider]), \
             patch('backend.agent.tool_manager.get_tool_dict', return_value={}):
            new_agent = Agent(new_config)
        
        # Check that the session was loaded
        self.assertEqual(len(new_agent.session.messages), 2)
        self.assertEqual(new_agent.session.messages[0].role, "user")
        self.assertEqual(new_agent.session.messages[0].content, "Hello")
        
    def test_session_list_and_delete(self):
        """Test listing and deleting sessions."""
        # Set up the mock response
        self.llm_provider.add_mock_response("I'll help you with that!")
        
        # Send a message to create a session
        self.agent.send_message("Hello", "mock-model", None)
        
        # Explicitly save the session
        self.agent.session.save()
        
        # Get the session ID
        session_id = self.agent.get_session_id()
        
        # Get list of sessions - will be a dict in the new implementation
        sessions = self.agent.list_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertTrue(session_id in sessions)
        
        # Delete the session
        success = self.agent.delete_session(session_id)
        
        # We can't delete the active session
        self.assertFalse(success)
        
        # Create a config for another engine
        another_config = Config(
            default_model_id="mock-model",
            tools_dirs=["/Users/gigi/git/ai-six/py/backend/tools"],
            mcp_tools_dirs=["/Users/gigi/git/ai-six/py/backend/mcp_tools"],
            memory_dir=self.test_dir
        )
        
        # Create another agent with a new session
        with patch('backend.agent.agent.Agent.discover_llm_providers', return_value=[self.llm_provider]), \
             patch('backend.agent.tool_manager.get_tool_dict', return_value={}):
            another_agent = Agent(another_config)
        
        # Get the new session ID and save it
        another_session_id = another_agent.get_session_id()
        another_agent.session.save()  # We need to save this session too
        
        # Now delete the first session from this new agent
        success = another_agent.delete_session(session_id)
        self.assertTrue(success)
        
        # List sessions again
        sessions = self.agent.list_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertTrue(session_id not in sessions)
        self.assertTrue(another_session_id in sessions)
        
    def test_checkpoint_interval(self):
        """Test the checkpoint interval functionality."""
        # Set the checkpoint interval to 2
        self.agent.checkpoint_interval = 2
        
        # Set up mock responses
        self.llm_provider.add_mock_response("Response 1")
        self.llm_provider.add_mock_response("Response 2")
        
        # Reset the message count explicitly to ensure we start fresh
        self.agent.message_count_since_checkpoint = 0
        
        with patch.object(self.agent.session, 'save') as mock_save:
            # First message (user)
            self.agent.session.add_message({"role": "user", "content": "Message 1"})
            self.agent._checkpoint_if_needed()  # Manually call to increment counter to 1
            
            # First message (assistant)
            self.agent.session.add_message({"role": "assistant", "content": "Response 1"})
            self.agent._checkpoint_if_needed()  # Increment counter to 2, which matches interval
            
            # Verify the session was saved after the second message (assistant)
            mock_save.assert_called_once()
            self.assertEqual(self.agent.message_count_since_checkpoint, 0)  # Should be reset
            
            # Counter should be reset, so add two more messages to hit 2 again
            
            # Second message (user)
            self.agent.session.add_message({"role": "user", "content": "Message 2"})
            self.agent._checkpoint_if_needed()  # Increment counter to 1
            
            # Second message (assistant)
            self.agent.session.add_message({"role": "assistant", "content": "Response 2"})
            self.agent._checkpoint_if_needed()  # Increment counter to 2 again
            
            # Should be called twice now
            self.assertEqual(mock_save.call_count, 2)
            self.assertEqual(self.agent.message_count_since_checkpoint, 0)
            
    def test_tool_call_handling(self):
        """Test handling of tool calls."""
        # Create a mock tool call
        tool_call = ToolCall(
            id="call_123",
            name="echo",
            arguments='{"text":"Hello, world!"}',
            required=["text"]
        )
        
        # Set up the mock response with a tool call
        self.llm_provider.add_mock_response(
            content="I'll execute that tool for you",
            tool_calls=[tool_call]
        )
        
        # Set up a mock for the tool execution
        tool_result = "Hello, world!"
        self.agent.tool_dict["echo"] = MagicMock()
        self.agent.tool_dict["echo"].run.return_value = tool_result
        
        # Set up a mock tool call handler
        tool_call_handler = MagicMock()
        
        # Mock the generate_tool_call_id function to return consistent IDs for testing
        with patch('backend.agent.agent.generate_tool_call_id', return_value='tool_test_id_123'):
            # Send a message that will trigger a tool call
            self.agent.send_message("Run echo", "mock-model", tool_call_handler)
            
            # Check that the tool call handler was called with the right arguments
            tool_call_handler.assert_called_once_with("echo", {"text": "Hello, world!"}, tool_result)
            
            # Check that the messages include the tool call and response
            messages = self.agent.session.messages
            self.assertEqual(len(messages), 4)  # user, assistant, tool, assistant
            self.assertEqual(messages[0].role, "user")
            self.assertEqual(messages[1].role, "assistant")
            self.assertEqual(messages[2].role, "tool")
            self.assertEqual(messages[2].name, "echo")
            
            # Verify that the tool_call_id was properly set with our mocked ID
            self.assertEqual(messages[2].tool_call_id, "tool_test_id_123")


if __name__ == "__main__":
    unittest.main()
