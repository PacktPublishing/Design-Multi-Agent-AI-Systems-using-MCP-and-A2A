import unittest
from unittest.mock import patch
from backend.tools.base import command_tool
from backend.tools.file_system.sed import Sed


class SedToolTest(unittest.TestCase):

    @patch.object(command_tool, "sh")
    def test_run_sed_as_current_user(self, mock_sh):
        sed_tool = Sed(user=None)
        sed_tool.run(args="s/old/new/g /tmp/testfile.txt")
        mock_sh.sed.assert_called_with("s/old/new/g", "/tmp/testfile.txt")

    @patch.object(command_tool, "sh")
    def test_run_sed_as_different_user(self, mock_sh):
        sed_tool = Sed("other-user")
        sed_tool.run(args="s/old/new/g /home/other-user/testfile.txt")
        mock_sh.sudo.assert_called_with("-u", "other-user", "sed", "s/old/new/g", "/home/other-user/testfile.txt")


if __name__ == "__main__":
    unittest.main()
