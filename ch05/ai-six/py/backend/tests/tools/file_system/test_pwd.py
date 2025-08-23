import unittest
from backend.tools.file_system.pwd import Pwd
import os

class TestPwdTool(unittest.TestCase):
    def test_pwd(self):
        pwd_tool = Pwd(user=None)  # Initialize Pwd tool without using sudo
        current_directory = pwd_tool.run(args='').strip()

        # Verify that the current directory returned by the tool is correct
        self.assertEqual(current_directory, os.getcwd())  # Assuming root directory for the sake of the test

if __name__ == '__main__':
    unittest.main()
