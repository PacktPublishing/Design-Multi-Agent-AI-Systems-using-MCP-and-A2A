import unittest
import tempfile
import os
import json
import shutil

from backend.agent.session import Session
from backend.object_model import Usage, ToolCall, UserMessage, AssistantMessage, ToolMessage


class TestSession(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for testing
        self.test_dir = tempfile.mkdtemp()
        self.session = Session(self.test_dir)
        
    def tearDown(self):
        # Clean up the temporary directory
        shutil.rmtree(self.test_dir)
        
    def test_initialization(self):
        """Test that the Session is initialized correctly."""
        self.assertIsNotNone(self.session.session_id)
        self.assertTrue(self.session.title.startswith('Untiled session ~'))
        self.assertEqual(self.session.messages, [])
        self.assertEqual(self.session.usage.input_tokens, 0)
        self.assertEqual(self.session.usage.output_tokens, 0)
        
    def test_save_and_load(self):
        """Test saving and loading a session with dictionary messages."""
        # Create some test messages as dictionaries
        user_message = {
            "role": "user",
            "content": "Hello AI!",
            "usage": {
                "input_tokens": 10,
                "output_tokens": 0
            }
        }
        
        assistant_message = {
            "role": "assistant",
            "content": "Hello! How can I help you today?",
            "usage": {
                "input_tokens": 0,
                "output_tokens": 15
            }
        }
        
        # Convert to Message objects and add to session
        user_msg = UserMessage(content="Hello AI!")
        assistant_msg = AssistantMessage(
            content="Hello! How can I help you today?",
            usage=Usage(input_tokens=10, output_tokens=15)
        )
        self.session.add_message(user_msg)
        self.session.add_message(assistant_msg)
        
        # Save the session
        self.session.save()
        
        # Check that the file was created
        filename = f"{self.test_dir}/{self.session.session_id}.json"
        self.assertTrue(os.path.exists(filename))
        
        # Create a new session and load the data
        new_session = Session(self.test_dir)
        new_session.load(self.session.session_id)
        
        # Check that the data was loaded correctly
        self.assertEqual(new_session.session_id, self.session.session_id)
        self.assertEqual(new_session.title, self.session.title)
        self.assertEqual(len(new_session.messages), 2)
        
        # Verify messages are loaded as Message objects with the right structure
        self.assertIsInstance(new_session.messages[0], UserMessage)
        self.assertEqual(new_session.messages[0].role, "user")
        self.assertEqual(new_session.messages[0].content, "Hello AI!")
        
        # Check usage is still a Usage object
        self.assertIsInstance(new_session.usage, Usage)
        self.assertEqual(new_session.usage.input_tokens, 10)
        self.assertEqual(new_session.usage.output_tokens, 15)
        
    def test_complex_session(self):
        """Test session with tool calls and tool responses."""
        # Create a user message
        user_message = {
            "role": "user",
            "content": "What files are in the current directory?",
            "usage": {
                "input_tokens": 12,
                "output_tokens": 0
            }
        }
        
        # Create an assistant message with tool calls
        assistant_message = {
            "role": "assistant",
            "content": "Let me check the files for you.",
            "tool_calls": [
                {
                    "id": "call_123",
                    "name": "ls",
                    "arguments": {"path": "."},
                    "required": ["path"]
                }
            ],
            "usage": {
                "input_tokens": 0,
                "output_tokens": 18
            }
        }
        
        # Create a tool response message
        tool_response = {
            "role": "tool",
            "tool_call_id": "call_123",
            "name": "ls",
            "content": '{"result": ["file1.txt", "file2.py", "folder1"]}'
        }
        
        # Create a final assistant message
        final_response = {
            "role": "assistant",
            "content": "I found these files in the current directory: file1.txt, file2.py, and a folder called folder1.",
            "usage": {
                "input_tokens": 0,
                "output_tokens": 25
            }
        }
        
        # Convert to Message objects and add to session
        user_msg = UserMessage(content="What files are in the current directory?")
        
        tool_call = ToolCall(
            id="call_123",
            name="ls", 
            arguments='{"path": "."}',
            required=["path"]
        )
        assistant_msg = AssistantMessage(
            content="Let me check the files for you.",
            tool_calls=[tool_call],
            usage=Usage(input_tokens=12, output_tokens=18)
        )
        
        tool_msg = ToolMessage(
            content='{"result": ["file1.txt", "file2.py", "folder1"]}',
            name="ls",
            tool_call_id="call_123"
        )
        
        final_msg = AssistantMessage(
            content="I found these files in the current directory: file1.txt, file2.py, and a folder called folder1.",
            usage=Usage(input_tokens=0, output_tokens=25)
        )
        
        self.session.add_message(user_msg)
        self.session.add_message(assistant_msg)
        self.session.add_message(tool_msg)
        self.session.add_message(final_msg)
        
        # Save the session
        self.session.save()
        
        # Create a new session and load the data
        new_session = Session(self.test_dir)
        new_session.load(self.session.session_id)
        
        # Check that the data was loaded correctly
        self.assertEqual(len(new_session.messages), 4)
        
        # Test message structure
        self.assertEqual(new_session.messages[0].role, "user")
        self.assertEqual(new_session.messages[1].role, "assistant")
        self.assertEqual(new_session.messages[2].role, "tool")
        self.assertEqual(new_session.messages[3].role, "assistant")
        
        # Check tool calls were loaded correctly as ToolCall objects
        self.assertIsNotNone(new_session.messages[1].tool_calls)
        self.assertEqual(new_session.messages[1].tool_calls[0].id, "call_123")
        self.assertEqual(new_session.messages[1].tool_calls[0].name, "ls")
        # Note: arguments is stored as JSON string in ToolCall
        import json
        args = json.loads(new_session.messages[1].tool_calls[0].arguments)
        self.assertEqual(args["path"], ".")
        
        # Check tool response structure
        self.assertEqual(new_session.messages[2].tool_call_id, "call_123")
        self.assertEqual(new_session.messages[2].name, "ls")
        
        # Check usage (12 + 0 = 12 input tokens, 18 + 25 = 43 output tokens)
        self.assertEqual(new_session.usage.input_tokens, 12)
        self.assertEqual(new_session.usage.output_tokens, 43)
        
    def test_add_message(self):
        """Test adding a message and updating the usage stats."""
        # Create messages
        user_message = UserMessage(content="Hello")
        assistant_message = AssistantMessage(
            content="Hello there!",
            usage=Usage(input_tokens=5, output_tokens=8)
        )
        
        # Add the messages
        self.session.add_message(user_message)
        self.session.add_message(assistant_message)
        
        # Check that the messages were added
        self.assertEqual(len(self.session.messages), 2)
        self.assertEqual(self.session.messages[0].role, "user")
        self.assertEqual(self.session.messages[1].role, "assistant")
        
        # Check that usage was updated (only from AssistantMessage)
        self.assertEqual(self.session.usage.input_tokens, 5)
        self.assertEqual(self.session.usage.output_tokens, 8)


if __name__ == "__main__":
    unittest.main()
