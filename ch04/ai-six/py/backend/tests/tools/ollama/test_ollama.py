import unittest
from unittest.mock import patch
from backend.tools.base import command_tool
from backend.tools.ollama.ollama import Ollama

class TestOllama(unittest.TestCase):
    def setUp(self):
        self.tool = Ollama()

    @patch.object(command_tool, "sh")
    def test_run_ollama_as_current_user(self, mock_sh):
        git_tool = Ollama(user=None)
        git_tool.run(args="ps")
        mock_sh.ollama.assert_called_with("ps")

    @patch.object (command_tool, "sh")
    def test_run_ollama_as_different_user(self, mock_sh):
        git_tool = Ollama("other-user")
        git_tool.run(args="list")
        mock_sh.sudo.assert_called_with("-u", "other-user", "ollama", "list")

if __name__ == '__main__':
    unittest.main()