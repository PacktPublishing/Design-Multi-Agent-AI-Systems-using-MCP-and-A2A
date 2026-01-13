import unittest
import tempfile
import os
import json
import shutil

from backend.agent.session_manager import SessionManager


class TestSessionManager(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for testing
        self.test_dir = tempfile.mkdtemp()
        self.session_manager = SessionManager(self.test_dir)
        
        # Create some test session files
        self.create_test_session("session1", "Test Session 1")
        self.create_test_session("session2", "Test Session 2")
        self.create_test_session("session3", "Test Session 3")
        
    def tearDown(self):
        # Clean up the temporary directory
        shutil.rmtree(self.test_dir)
        
    def create_test_session(self, session_id, title):
        """Helper method to create a test session file."""
        # New format is just session_id.json
        filename = f"{self.test_dir}/{session_id}.json"
        with open(filename, 'w') as f:
            json.dump({
                "session_id": session_id,
                "title": title,
                "messages": [
                    {"role": "user", "content": f"Test message for {title}"}
                ],
                "usage": {"input_tokens": 10, "output_tokens": 15}
            }, f, indent=4)
        
    def test_list_sessions(self):
        """Test that sessions are listed correctly."""
        sessions = self.session_manager.list_sessions()
        
        # Check that all sessions are in the list
        self.assertEqual(len(sessions), 3)
        self.assertIn("session1", sessions)
        self.assertIn("session2", sessions)
        self.assertIn("session3", sessions)
        
        self.assertEqual(sessions["session1"]["title"], "Test Session 1")
        self.assertEqual(sessions["session2"]["title"], "Test Session 2")
        self.assertEqual(sessions["session3"]["title"], "Test Session 3")
        
    def test_delete_session(self):
        """Test deleting a session."""
        # Delete a session
        self.session_manager.delete_session("session2")
        
        # Check that the file was deleted
        sessions = self.session_manager.list_sessions()
        self.assertEqual(len(sessions), 2)
        self.assertIn("session1", sessions)
        self.assertNotIn("session2", sessions)
        self.assertIn("session3", sessions)
        
        # Check that the file was actually removed from the file system
        files = os.listdir(self.test_dir)
        self.assertEqual(len(files), 2)
        self.assertIn("session1.json", files)
        self.assertNotIn("session2.json", files)
        self.assertIn("session3.json", files)
        
    def test_delete_nonexistent_session(self):
        """Test deleting a session that doesn't exist."""
        # Try to delete a nonexistent session
        with self.assertRaises(RuntimeError):
            self.session_manager.delete_session("nonexistent")
        
        # Check that no files were deleted
        sessions = self.session_manager.list_sessions()
        self.assertEqual(len(sessions), 3)
        
    def test_empty_directory(self):
        """Test listing sessions in an empty directory."""
        # Create a new empty directory
        empty_dir = tempfile.mkdtemp()
        empty_manager = SessionManager(empty_dir)
        
        # Check that no sessions are listed
        sessions = empty_manager.list_sessions()
        self.assertEqual(len(sessions), 0)
        
        # Clean up
        shutil.rmtree(empty_dir)
        
    def test_non_json_files(self):
        """Test that non-JSON files are ignored."""
        # Create a non-JSON file
        with open(f"{self.test_dir}/not_a_session.txt", 'w') as f:
            f.write("This is not a session file")
        
        # Check that the non-JSON file is ignored
        sessions = self.session_manager.list_sessions()
        self.assertEqual(len(sessions), 3)
        
    def test_malformed_filename(self):
        """Test handling of malformed filenames."""
        # In the new format, all .json files are considered valid sessions
        # Let's create an invalid JSON file instead
        with open(f"{self.test_dir}/malformed.json", 'w') as f:
            f.write("{NOT_VALID_JSON")
            
        # Listing should still work, ignoring the malformed JSON
        sessions = self.session_manager.list_sessions()
        self.assertEqual(len(sessions), 3)


if __name__ == "__main__":
    unittest.main()
