import unittest
from unittest.mock import patch, MagicMock
from backend.tools.test_runner import test_runner
from backend.tools.test_runner.test_runner import TestRunner

class PythonTestRunnerTest(unittest.TestCase):

    @patch.object(test_runner, 'sh')
    def test_run_tests(self, mock_sh):
        """Test running tests successfully."""
        # Arrange
        runner = TestRunner()

        # Act
        _ = runner.run(test_directory='some/test/directory')

        # Assert
        mock_sh.python.assert_called_once_with('-m', 'unittest', 'discover', '-s', 'some/test/directory')

if __name__ == "__main__":
    unittest.main()
