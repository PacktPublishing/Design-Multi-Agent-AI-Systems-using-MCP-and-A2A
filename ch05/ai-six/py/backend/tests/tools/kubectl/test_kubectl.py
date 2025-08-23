import unittest
from backend.tools.kubectl.kubectl import Kubectl
from unittest.mock import Mock

class TestKubectl(unittest.TestCase):

    def setUp(self):
        self.kubectl = Kubectl()

    def test_kubectl_initialization(self):
        # Test if Kubectl instance is created correctly
        self.assertIsInstance(self.kubectl, Kubectl)

    def test_kubectl_run_method(self):
        # As we cannot actually run kubectl commands in this test environment,
        # we're going to mock the `run` method behavior
        self.kubectl.run = Mock(return_value='mocked kubectl output')
        result = self.kubectl.run(args='get pods')
        self.kubectl.run.assert_called_once_with(args='get pods')
        self.assertEqual(result, 'mocked kubectl output')

if __name__ == '__main__':
    unittest.main()