import unittest
from unittest.mock import MagicMock, patch

from backend.tools.memory.list_sessions import ListSessions
from backend.tools.memory.load_session import LoadSession
from backend.tools.memory.delete_session import DeleteSession
from backend.tools.memory.get_session_id import GetSessionId


class TestMemoryTools(unittest.TestCase):
    def setUp(self):
        # Create a mock engine
        self.mock_engine = MagicMock()
        self.mock_engine.get_session_id.return_value = "current-session"
        
    def test_list_sessions_tool(self):
        """Test the ListSessions tool."""
        # Set up the mock engine
        self.mock_engine.list_sessions.return_value = ["session1", "session2", "session3"]
        
        # Create the tool
        tool = ListSessions(self.mock_engine)
        
        # Run the tool
        result = tool.run()
        
        # Check that the engine's list_sessions method was called
        self.mock_engine.list_sessions.assert_called_once()
        
        # Check that the result contains the session IDs
        self.assertIn("session1", result)
        self.assertIn("session2", result)
        self.assertIn("session3", result)
        
    def test_list_sessions_tool_no_sessions(self):
        """Test the ListSessions tool when there are no sessions."""
        # Set up the mock engine
        self.mock_engine.list_sessions.return_value = []
        
        # Create the tool
        tool = ListSessions(self.mock_engine)
        
        # Run the tool
        result = tool.run()
        
        # Check that the engine's list_sessions method was called
        self.mock_engine.list_sessions.assert_called_once()
        
        # Check that the result indicates no sessions
        self.assertIn("No sessions found", result)
        
    def test_load_session_tool(self):
        """Test the LoadSession tool."""
        # Set up the mock engine
        self.mock_engine.load_session.return_value = True
        
        # Create the tool
        tool = LoadSession(self.mock_engine)
        
        # Run the tool
        result = tool.run(session_id="test-session")
        
        # Check that the engine's load_session method was called with the correct ID
        self.mock_engine.load_session.assert_called_once_with("test-session")
        
        # Check that the result indicates success
        self.assertIn("Successfully loaded", result)
        
    def test_load_session_tool_failure(self):
        """Test the LoadSession tool when loading fails."""
        # Set up the mock engine
        self.mock_engine.load_session.return_value = False
        
        # Create the tool
        tool = LoadSession(self.mock_engine)
        
        # Run the tool
        result = tool.run(session_id="nonexistent-session")
        
        # Check that the engine's load_session method was called with the correct ID
        self.mock_engine.load_session.assert_called_once_with("nonexistent-session")
        
        # Check that the result indicates failure
        self.assertIn("Failed to load", result)
        
    def test_get_session_id_tool(self):
        """Test the GetSessionId tool."""
        # Create the tool
        tool = GetSessionId(self.mock_engine)
        
        # Run the tool
        result = tool.run()
        
        # Check that the engine's get_session_id method was called
        self.mock_engine.get_session_id.assert_called_once()
        
        # Check that the result contains the current session ID
        self.assertIn("current-session", result)
        
    def test_delete_session_tool(self):
        """Test the DeleteSession tool."""
        # Set up the mock engine
        self.mock_engine.list_sessions.return_value = ["session1", "session2", "session3"]
        self.mock_engine.delete_session.return_value = True
        
        # Create the tool
        tool = DeleteSession(self.mock_engine)
        
        # Run the tool
        result = tool.run(session_id="session2")
        
        # Check that the engine's delete_session method was called with the correct ID
        self.mock_engine.delete_session.assert_called_once_with("session2")
        
        # Check that the result indicates success
        self.assertIn("Successfully deleted", result)
        
    def test_delete_session_tool_nonexistent(self):
        """Test the DeleteSession tool with a nonexistent session."""
        # Set up the mock engine
        self.mock_engine.delete_session.return_value = False
        
        # Create the tool
        tool = DeleteSession(self.mock_engine)
        
        # Run the tool
        result = tool.run(session_id="nonexistent-session")
        
        # Check that the engine's delete_session method was called
        self.mock_engine.delete_session.assert_called_once_with("nonexistent-session")
        
        # Check that the result indicates failure
        self.assertIn("Failed to delete", result)
        
    def test_delete_session_tool_current_session(self):
        """Test the DeleteSession tool with the current session."""
        # Set up the mock engine
        self.mock_engine.list_sessions.return_value = ["session1", "current-session", "session3"]
        
        # Create the tool
        tool = DeleteSession(self.mock_engine)
        
        # Run the tool
        result = tool.run(session_id="current-session")
        
        # Check that the engine's delete_session method was not called
        self.mock_engine.delete_session.assert_not_called()
        
        # Check that the result indicates the current session cannot be deleted
        self.assertIn("Cannot delete the current active session", result)


if __name__ == "__main__":
    unittest.main()
