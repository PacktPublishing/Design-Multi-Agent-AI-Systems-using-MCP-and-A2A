import unittest
from unittest.mock import patch
from backend.tools.base import command_tool
from backend.tools.file_system.patch import Patch


class PatchToolTest(unittest.TestCase):

    @patch.object(command_tool, "sh")
    def test_run_patch_as_current_user(self, mock_sh):
        patch_tool = Patch(user=None)
        patch_tool.run(args="/tmp/testfile.patch")
        mock_sh.patch.assert_called_with("/tmp/testfile.patch")

    @patch.object(command_tool, "sh")
    def test_run_patch_as_different_user(self, mock_sh):
        patch_tool = Patch("other-user")
        patch_tool.run(args="/home/other-user/testfile.patch")
        mock_sh.sudo.assert_called_with("-u", "other-user", "patch", "/home/other-user/testfile.patch")


if __name__ == "__main__":
    unittest.main()
