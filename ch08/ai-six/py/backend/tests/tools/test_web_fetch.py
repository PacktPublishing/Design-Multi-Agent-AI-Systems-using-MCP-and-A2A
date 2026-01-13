import os
import json
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from backend.tools.web.web_fetch import WebFetch, CacheManager


class TestCacheManager(unittest.TestCase):
    """Test the CacheManager component."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.cache_manager = CacheManager(self.temp_dir)
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test cache manager initializes paths correctly but doesn't create directories until needed."""
        # Directories should not exist yet
        assert not self.cache_manager.content_dir.exists()
        assert not self.cache_manager.metadata_dir.exists()
        
        # But paths should be set correctly
        assert self.cache_manager.content_dir == Path(self.temp_dir) / "content"
        assert self.cache_manager.metadata_dir == Path(self.temp_dir) / "metadata"
    
    def test_lazy_directory_creation(self):
        """Test that directories are created only when needed."""
        # Initially directories don't exist
        assert not self.cache_manager.content_dir.exists()
        assert not self.cache_manager.metadata_dir.exists()
        
        # Save some content - this should trigger directory creation
        url = "https://example.com/test.html"
        content = b"<html><body>Test</body></html>"
        metadata = {"content_type": "text/html"}
        
        file_path = self.cache_manager.save_content(url, content, metadata)
        
        # Now directories should exist
        assert self.cache_manager.content_dir.exists()
        assert self.cache_manager.metadata_dir.exists()
        assert os.path.exists(file_path)
    
    def test_url_hashing(self):
        """Test URL hashing is consistent."""
        url = "https://example.com/test"
        hash1 = self.cache_manager.get_url_hash(url)
        hash2 = self.cache_manager.get_url_hash(url)
        
        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 12)
    
    def test_content_hashing(self):
        """Test content hashing works correctly."""
        content = b"test content"
        hash1 = self.cache_manager.get_content_hash(content)
        hash2 = self.cache_manager.get_content_hash(content)
        
        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 12)
    
    def test_url_index_operations(self):
        """Test URL index save/load operations."""
        test_index = {"hash1": "content1", "hash2": "content2"}
        
        # Save index
        self.cache_manager.save_url_index(test_index)
        
        # Load index
        loaded_index = self.cache_manager.load_url_index()
        self.assertEqual(loaded_index, test_index)
    
    def test_save_and_retrieve_content(self):
        """Test saving content and retrieving it."""
        url = "https://example.com/test.html"
        content = b"<html><body>Test</body></html>"
        metadata = {
            "content_type": "text/html",
            "content_length": len(content),
            "encoding": "utf-8"
        }
        
        # Save content
        file_path = self.cache_manager.save_content(url, content, metadata)
        
        # Verify file exists
        self.assertTrue(os.path.exists(file_path))
        
        # Retrieve cached content
        cached_file, cached_metadata = self.cache_manager.get_cached_file(url)
        
        self.assertEqual(cached_file, file_path)
        self.assertIn('file_hash', cached_metadata)
        self.assertEqual(cached_metadata['content_type'], 'text/html')
    
    def test_extension_detection(self):
        """Test file extension detection from content type."""
        test_cases = [
            ('text/html', 'html'),
            ('application/json', 'json'),
            ('text/plain', 'txt'),
            ('image/png', 'png'),
            ('application/pdf', 'pdf'),
            ('unknown/type', 'bin')
        ]
        
        for content_type, expected_ext in test_cases:
            ext = self.cache_manager._get_extension_from_content_type(content_type)
            self.assertEqual(ext, expected_ext)


class TestWebFetch(unittest.TestCase):
    """Test the WebFetch tool."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.web_fetch = WebFetch(downloads_dir=self.temp_dir)
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_tool_initialization(self):
        """Test WebFetch tool initializes correctly."""
        self.assertEqual(self.web_fetch.name, 'web_fetch')
        self.assertIn('url', [p.name for p in self.web_fetch.parameters])
        self.assertEqual(self.web_fetch.required, {'url'})
    
    def test_url_validation(self):
        """Test URL validation logic."""
        valid_urls = [
            "https://example.com",
            "http://test.org/path",
            "https://api.github.com/repos"
        ]
        
        invalid_urls = [
            "not-a-url",
            "ftp://example.com",
            "file:///etc/passwd",
            ""
        ]
        
        for url in valid_urls:
            self.assertTrue(self.web_fetch._is_valid_url(url), f"Should be valid: {url}")
        
        for url in invalid_urls:
            self.assertFalse(self.web_fetch._is_valid_url(url), f"Should be invalid: {url}")
    
    def test_invalid_url_error(self):
        """Test error handling for invalid URLs."""
        result = self.web_fetch.run(url="invalid-url")
        response = json.loads(result)
        
        self.assertEqual(response['status'], 'error')
        self.assertEqual(response['error_type'], 'validation_error')
        self.assertIn('Invalid URL', response['error'])
    
    @patch('backend.tools.web.web_fetch.requests.request')
    def test_successful_fetch(self, mock_request):
        """Test successful HTTP fetch."""
        # Mock response
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.content = b'{"message": "Hello, World!"}'
        mock_response.url = "https://api.example.com/test"
        mock_response.headers = {
            'content-type': 'application/json',
            'last-modified': 'Wed, 21 Oct 2015 07:28:00 GMT'
        }
        mock_response.encoding = 'utf-8'
        mock_request.return_value = mock_response
        
        # Run fetch
        result = self.web_fetch.run(
            url="https://api.example.com/test",
            max_length=1000
        )
        
        response = json.loads(result)
        
        # Verify response
        self.assertEqual(response['status'], 'success')
        self.assertEqual(response['status_code'], 200)
        self.assertIn('file_path', response)
        self.assertIn('content', response)
        self.assertIn('metadata', response)
        
        # Verify metadata
        metadata = response['metadata']
        self.assertEqual(metadata['content_type'], 'application/json')
        self.assertFalse(metadata['cached'])
        
        # Verify file was created
        self.assertTrue(os.path.exists(response['file_path']))
    
    @patch('backend.tools.web.web_fetch.requests.request')
    def test_http_error_handling(self, mock_request):
        """Test HTTP error handling."""
        # Mock 404 response
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 404
        mock_response.reason = "Not Found"
        mock_response.text = "Page not found"
        mock_request.return_value = mock_response
        
        result = self.web_fetch.run(url="https://example.com/notfound")
        response = json.loads(result)
        
        self.assertEqual(response['status'], 'error')
        self.assertEqual(response['status_code'], 404)
        self.assertEqual(response['error_type'], 'http_error')
        self.assertIn('Not Found', response['error'])
    
    @patch('backend.tools.web.web_fetch.requests.request')
    def test_timeout_handling(self, mock_request):
        """Test timeout error handling."""
        from requests.exceptions import Timeout
        mock_request.side_effect = Timeout("Request timeout")
        
        result = self.web_fetch.run(url="https://example.com", timeout=5)
        response = json.loads(result)
        
        self.assertEqual(response['status'], 'error')
        self.assertEqual(response['error_type'], 'timeout')
        self.assertIn('timeout after 5 seconds', response['error'])
    
    @patch('backend.tools.web.web_fetch.requests.request')
    def test_ssl_error_handling(self, mock_request):
        """Test SSL error handling."""
        from requests.exceptions import SSLError
        mock_request.side_effect = SSLError("SSL Certificate error")
        
        result = self.web_fetch.run(url="https://badssl.example")
        response = json.loads(result)
        
        self.assertEqual(response['status'], 'error')
        # SSLError is caught in the SSL error handler
        self.assertIn('error_type', response)
        self.assertIn('SSL', response['error'])
    
    @patch('backend.tools.web.web_fetch.requests.request')
    def test_content_truncation(self, mock_request):
        """Test content truncation with max_length."""
        # Mock response with long content
        long_content = "A" * 10000
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.content = long_content.encode()
        mock_response.url = "https://example.com/long"
        mock_response.headers = {'content-type': 'text/plain'}
        mock_response.encoding = 'utf-8'
        mock_request.return_value = mock_response
        
        # Fetch with limited length
        result = self.web_fetch.run(
            url="https://example.com/long",
            max_length=100
        )
        
        response = json.loads(result)
        
        self.assertEqual(response['status'], 'success')
        self.assertEqual(len(response['content']), 100)
        self.assertTrue(response['metadata']['truncated'])
        self.assertEqual(response['metadata']['returned_length'], 100)
        self.assertEqual(response['metadata']['total_length'], 10000)
    
    @patch('backend.tools.web.web_fetch.requests.request')
    def test_start_index_parameter(self, mock_request):
        """Test start_index parameter for content windowing."""
        content = "0123456789ABCDEFGHIJ"
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.content = content.encode()
        mock_response.url = "https://example.com/indexed"
        mock_response.headers = {'content-type': 'text/plain'}
        mock_response.encoding = 'utf-8'
        mock_request.return_value = mock_response
        
        # Fetch starting from index 10
        result = self.web_fetch.run(
            url="https://example.com/indexed",
            start_index=10,
            max_length=5
        )
        
        response = json.loads(result)
        
        self.assertEqual(response['status'], 'success')
        self.assertEqual(response['content'], "ABCDE")
        self.assertEqual(response['metadata']['start_index'], 10)
        self.assertEqual(response['metadata']['returned_length'], 5)
    
    @patch('backend.tools.web.web_fetch.requests.request')
    def test_json_processing(self, mock_request):
        """Test JSON content processing."""
        json_content = '{"name":"test","value":123}'
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.content = json_content.encode()
        mock_response.url = "https://api.example.com/data"
        mock_response.headers = {'content-type': 'application/json'}
        mock_response.encoding = 'utf-8'
        mock_request.return_value = mock_response
        
        # Fetch without raw flag (should format JSON)
        result = self.web_fetch.run(url="https://api.example.com/data")
        response = json.loads(result)
        
        self.assertEqual(response['status'], 'success')
        # Content should be pretty-formatted JSON
        self.assertIn('\n', response['content'])  # Pretty-formatted JSON has newlines
        
        # Test with raw flag (should not format)
        result_raw = self.web_fetch.run(
            url="https://api.example.com/data",
            raw=True
        )
        response_raw = json.loads(result_raw)
        self.assertEqual(response_raw['content'], json_content)
    
    @patch('backend.tools.web.web_fetch.requests.get')
    @patch('backend.tools.web.web_fetch.requests.request')
    def test_caching_behavior(self, mock_request, mock_get):
        """Test that caching works correctly."""
        # Mock first response
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.content = b'Test content'
        mock_response.url = "https://example.com/cached"
        mock_response.headers = {
            'content-type': 'text/plain',
            'etag': '"abc123"',
            'last-modified': 'Wed, 21 Oct 2015 07:28:00 GMT'
        }
        mock_response.encoding = 'utf-8'
        mock_request.return_value = mock_response
        
        # First fetch
        result1 = self.web_fetch.run(url="https://example.com/cached")
        response1 = json.loads(result1)
        
        # Should make HTTP request
        self.assertEqual(mock_request.call_count, 1)
        self.assertFalse(response1['metadata']['cached'])
        
        # Mock conditional request (304 Not Modified)
        mock_304_response = Mock()
        mock_304_response.status_code = 304
        mock_get.return_value = mock_304_response
        
        # Second fetch should use cached content with conditional request
        result2 = self.web_fetch.run(url="https://example.com/cached")
        response2 = json.loads(result2)
        
        # Content should be the same
        self.assertEqual(response1['content'], response2['content'])
        # Should indicate cached content was used
        self.assertTrue(response2['metadata']['cached'])


if __name__ == '__main__':
    unittest.main()