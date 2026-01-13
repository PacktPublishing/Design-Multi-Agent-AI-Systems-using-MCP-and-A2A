# import unittest
# from unittest.mock import patch
# from backend.tools.github.github import Github
# import sh
#
# class TestGithub(unittest.TestCase):
#
#     def setUp(self):
#         self.github = Github()
#
#     def test_list_repositories(self):
#         """ Test listing repositories using the gh CLI. """
#         # Mocking the subprocess call to return a controlled output
#         with patch.object(sh, 'gh', return_value='repo1\nrepo2\n') as mock_gh:
#             output = self.github.run(args='repo list')
#             self.assertIn('repo1', output)
#             self.assertIn('repo2', output)
#             mock_gh.assert_called_once_with('repo', 'list')
#
#     # Additional tests could be added with proper mocking or safe run configurations
#
# if __name__ == '__main__':
#     unittest.main()
