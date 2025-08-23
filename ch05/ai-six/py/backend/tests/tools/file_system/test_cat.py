import unittest
from unittest.mock import patch
from backend.tools.base import command_tool
from backend.tools.file_system.cat import Cat


class CatToolTest(unittest.TestCase):

    @patch.object(command_tool, "sh")
    def test_run_cat_as_current_user(self, mock_sh):
        cat_tool = Cat(user=None)
        cat_tool.run(args="/tmp/testfile.txt")
        mock_sh.cat.assert_called_with("/tmp/testfile.txt")

    @patch.object(command_tool, "sh")
    def test_run_cat_as_different_user(self, mock_sh):
        cat_tool = Cat("other-user")
        cat_tool.run(args="/home/other-user/testfile.txt")
        mock_sh.sudo.assert_called_with("-u", "other-user", "cat", "/home/other-user/testfile.txt", )


if __name__ == "__main__":
    unittest.main()