import unittest
from unittest.mock import patch
from backend.tools.bootstrap.bootstrap import Bootstrap
import os
import sys

class BootstrapToolTest(unittest.TestCase):

    @patch('os.execv')
    def test_bootstrap_execv_called(self, mock_execv):
        bootstrap_tool = Bootstrap()
        bootstrap_tool.run()
        # Don't verify the exact arguments, just verify it was called
        self.assertTrue(mock_execv.called, "os.execv should have been called")

if __name__ == "__main__":
    unittest.main()
