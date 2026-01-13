# import unittest
# from unittest.mock import patch
# from backend.tools.base import command_tool
# from backend.tools.file_system.ls import Ls
#
#
# class LsToolTest(unittest.TestCase):
#
#     @patch.object(command_tool, "sh")
#     def test_run_ls_as_current_user(self, mock_sh):
#         ls_tool = Ls(user=None)
#         ls_tool.run(args="-l /tmp")
#         mock_sh.ls.assert_called_with("-l", "/tmp")
#
#     @patch.object(command_tool, "sh")
#     def test_run_ls_as_different_user(self, mock_sh):
#         ls_tool = Ls("other-user")
#         ls_tool.run(args="-a /home")
#         mock_sh.sudo.assert_called_with("-u", "other-user", "ls", "-a", "/home")
#
#
# if __name__ == "__main__":
#     unittest.main()
