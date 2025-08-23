import unittest
from unittest.mock import patch, MagicMock
from backend.tools.base import command_tool
from backend.tools.file_system.awk import Awk


class AwkToolTest(unittest.TestCase):

    @patch.object(command_tool, "sh")
    def test_run_awk_as_current_user(self, mock_sh):
        # Setup mock
        mock_awk = MagicMock()
        mock_sh.awk = mock_awk
        
        # Run test
        awk_tool = Awk(user=None)
        awk_tool.run(args="/tmp/testfile.txt")
        
        # Verify expected call was made
        mock_awk.assert_called_with("/tmp/testfile.txt")

    @patch.object(command_tool, "sh")
    def test_run_awk_as_different_user(self, mock_sh):
        # Setup mock
        mock_sudo = MagicMock()
        mock_sh.sudo = mock_sudo
        
        # Run test
        awk_tool = Awk("other-user")
        awk_tool.run(args="/home/other-user/testfile.txt")
        
        # Verify expected call was made
        mock_sudo.assert_called_with("-u", "other-user", "awk", "/home/other-user/testfile.txt")


if __name__ == "__main__":
    unittest.main()
