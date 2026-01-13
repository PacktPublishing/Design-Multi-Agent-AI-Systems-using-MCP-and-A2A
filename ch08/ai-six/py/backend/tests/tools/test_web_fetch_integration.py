import os
import json
import tempfile
import unittest
import time
from pathlib import Path

from backend.tools.web.web_fetch import WebFetch

@unittest.skip("Skip stress test by default")
class TestWebFetchIntegration(unittest.TestCase):
    """Integration tests for WebFetch with real public sources."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        cls.temp_dir = tempfile.mkdtemp()
        cls.web_fetch = WebFetch(downloads_dir=cls.temp_dir)
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests."""
        import shutil
        shutil.rmtree(cls.temp_dir, ignore_errors=True)
    
    def test_fetch_simple_webpage(self):
        """Test fetching a simple HTML webpage."""
        # Use httpbin.org which is designed for testing HTTP requests
        url = "https://httpbin.org/html"
        
        result = self.web_fetch.run(url=url, max_length=2000)
        response = json.loads(result)
        
        # Verify successful response
        self.assertEqual(response['status'], 'success')
        self.assertEqual(response['status_code'], 200)
        self.assertEqual(response['url'], url)
        
        # Verify content
        self.assertIn('content', response)
        self.assertIn('<html>', response['content'].lower())
        
        # Verify metadata
        metadata = response['metadata']
        self.assertIn('text/html', metadata['content_type'])
        self.assertGreater(metadata['content_length'], 0)
        self.assertFalse(metadata['cached'])
        
        # Verify file exists
        self.assertTrue(os.path.exists(response['file_path']))
        
        print(f"✓ Successfully fetched HTML webpage: {len(response['content'])} chars")
    
    def test_fetch_json_api(self):
        """Test fetching JSON data from a public API."""
        url = "https://httpbin.org/json"
        
        result = self.web_fetch.run(url=url, max_length=5000)
        response = json.loads(result)
        
        # Verify successful response
        self.assertEqual(response['status'], 'success')
        self.assertEqual(response['status_code'], 200)
        
        # Verify JSON content
        self.assertIn('application/json', response['metadata']['content_type'])
        
        # Content should be pretty-formatted JSON (not raw)
        content = response['content']
        self.assertIn('\n', content)  # Pretty-formatted JSON has newlines
        
        # Should be valid JSON
        try:
            json.loads(content)
        except json.JSONDecodeError:
            self.fail("Response content should be valid JSON")
        
        print(f"✓ Successfully fetched JSON API: {response['metadata']['content_length']} bytes")
    
    def test_fetch_with_user_agent(self):
        """Test fetching with custom user agent."""
        url = "https://httpbin.org/user-agent"
        custom_ua = "TestBot/1.0"
        
        result = self.web_fetch.run(
            url=url,
            user_agent=custom_ua,
            max_length=1000
        )
        response = json.loads(result)
        
        self.assertEqual(response['status'], 'success')
        
        # The response should contain our user agent
        content = json.loads(response['content'])
        self.assertEqual(content['user-agent'], custom_ua)
        
        print(f"✓ Successfully used custom User-Agent: {custom_ua}")
    
    def test_fetch_with_headers(self):
        """Test fetching with custom headers."""
        url = "https://httpbin.org/headers"
        custom_headers = {
            "X-Test-Header": "integration-test",
            "Accept": "application/json"
        }
        
        result = self.web_fetch.run(
            url=url,
            headers=custom_headers,
            max_length=2000
        )
        response = json.loads(result)
        
        self.assertEqual(response['status'], 'success')
        
        # Parse the response to check headers were sent
        content = json.loads(response['content'])
        received_headers = content['headers']
        
        self.assertEqual(received_headers['X-Test-Header'], 'integration-test')
        self.assertEqual(received_headers['Accept'], 'application/json')
        
        print("✓ Successfully sent custom headers")
    
    def test_fetch_large_content_truncation(self):
        """Test fetching large content with truncation."""
        # This endpoint returns a large amount of data
        url = "https://httpbin.org/drip"
        params = "?duration=1&numbytes=10000"  # 10KB of data
        full_url = url + params
        
        result = self.web_fetch.run(
            url=full_url,
            max_length=500,  # Limit to 500 chars
            timeout=15  # Increase timeout for drip endpoint
        )
        response = json.loads(result)
        
        self.assertEqual(response['status'], 'success')
        
        # Content should be truncated
        self.assertEqual(len(response['content']), 500)
        self.assertTrue(response['metadata']['truncated'])
        self.assertGreater(response['metadata']['total_length'], 500)
        
        print(f"✓ Successfully truncated large content: {response['metadata']['total_length']} -> 500 chars")
    
    def test_fetch_with_start_index(self):
        """Test fetching content with start index."""
        url = "https://httpbin.org/uuid"
        
        # First get the full content
        result_full = self.web_fetch.run(url=url, max_length=1000)
        full_response = json.loads(result_full)
        full_content = full_response['content']
        
        # Now get content starting from index 10
        result_partial = self.web_fetch.run(
            url=url,
            start_index=10,
            max_length=20
        )
        partial_response = json.loads(result_partial)
        
        self.assertEqual(partial_response['status'], 'success')
        self.assertEqual(partial_response['metadata']['start_index'], 10)
        
        # Content should match the slice of full content
        expected = full_content[10:30]  # start_index=10, max_length=20
        self.assertEqual(partial_response['content'], expected)
        
        print(f"✓ Successfully used start_index: got chars 10-30")
    
    def test_caching_with_etag(self):
        """Test caching behavior with ETag headers."""
        # httpbin.org/etag/[etag] returns an ETag header
        url = "https://httpbin.org/etag/test123"
        
        # First request
        result1 = self.web_fetch.run(url=url, max_length=1000)
        response1 = json.loads(result1)
        
        self.assertEqual(response1['status'], 'success')
        self.assertFalse(response1['metadata']['cached'])
        
        # Second request should use cache (and make conditional request)
        result2 = self.web_fetch.run(url=url, max_length=1000)
        response2 = json.loads(result2)
        
        self.assertEqual(response2['status'], 'success')
        # Content should be the same
        self.assertEqual(response1['content'], response2['content'])
        
        print("✓ Successfully handled ETag caching")
    
    def test_error_handling_404(self):
        """Test error handling for 404 Not Found."""
        url = "https://httpbin.org/status/404"
        
        result = self.web_fetch.run(url=url)
        response = json.loads(result)
        
        self.assertEqual(response['status'], 'error')
        self.assertEqual(response['status_code'], 404)
        self.assertEqual(response['error_type'], 'http_error')
        self.assertIn('NOT FOUND', response['error'].upper())
        
        print("✓ Successfully handled 404 error")
    
    def test_error_handling_timeout(self):
        """Test error handling for timeout."""
        # Use httpbin.org/delay/10 with short timeout
        url = "https://httpbin.org/delay/10"
        
        result = self.web_fetch.run(url=url, timeout=2)  # 2 second timeout
        response = json.loads(result)
        
        self.assertEqual(response['status'], 'error')
        self.assertEqual(response['error_type'], 'timeout')
        self.assertIn('timeout after 2 seconds', response['error'])
        
        print("✓ Successfully handled timeout error")
    
    def test_redirects(self):
        """Test following redirects."""
        # httpbin.org/redirect/1 redirects once
        url = "https://httpbin.org/redirect/1"
        
        result = self.web_fetch.run(url=url, max_length=1000)
        response = json.loads(result)
        
        self.assertEqual(response['status'], 'success')
        
        # Final URL should be different from original
        self.assertNotEqual(response['metadata']['final_url'], url)
        self.assertIn('/get', response['metadata']['final_url'])
        
        print(f"✓ Successfully followed redirect: {url} -> {response['metadata']['final_url']}")
    
    def test_raw_vs_processed_content(self):
        """Test difference between raw and processed content."""
        url = "https://httpbin.org/json"
        
        # Get processed content
        result_processed = self.web_fetch.run(url=url, raw=False, max_length=2000)
        processed_response = json.loads(result_processed)
        
        # Get raw content  
        result_raw = self.web_fetch.run(url=url, raw=True, max_length=2000)
        raw_response = json.loads(result_raw)
        
        self.assertEqual(processed_response['status'], 'success')
        self.assertEqual(raw_response['status'], 'success')
        
        # Processed JSON should have formatting (newlines)
        self.assertIn('\n', processed_response['content'])
        
        # Raw content should be compact (no extra formatting)
        # Note: httpbin might return formatted JSON, so we just check they're different formats
        self.assertNotEqual(processed_response['content'], raw_response['content'])
        
        print("✓ Successfully differentiated raw vs processed content")


class TestWebFetchStressTest(unittest.TestCase):
    """Stress tests for WebFetch."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.web_fetch = WebFetch(downloads_dir=self.temp_dir)
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @unittest.skip("Skip stress test by default")
    def test_multiple_concurrent_requests(self):
        """Test handling multiple requests (simulated concurrency)."""
        urls = [
            "https://httpbin.org/json",
            "https://httpbin.org/html", 
            "https://httpbin.org/xml",
            "https://httpbin.org/uuid",
            "https://httpbin.org/user-agent"
        ]
        
        results = []
        for url in urls:
            result = self.web_fetch.run(url=url, max_length=1000)
            response = json.loads(result)
            results.append(response)
        
        # All should succeed
        for response in results:
            self.assertEqual(response['status'], 'success')
        
        print(f"✓ Successfully handled {len(urls)} requests")


if __name__ == '__main__':
    # Run integration tests only if INTEGRATION_TESTS env var is set
    if os.getenv('INTEGRATION_TESTS', '0') == '1':
        unittest.main()
    else:
        print("Skipping integration tests. Set INTEGRATION_TESTS=1 to run.")
        print("Example: INTEGRATION_TESTS=1 python -m backend.tests.tools.test_web_fetch_integration")