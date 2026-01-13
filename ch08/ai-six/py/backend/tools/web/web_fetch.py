import os
import json
import hashlib
import requests
from urllib.parse import urlparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from backend.object_model import Tool, Parameter


class CacheManager:
    """Manages caching of web content and metadata."""
    
    def __init__(self, downloads_dir: str):
        self.downloads_dir = Path(downloads_dir)
        self.content_dir = self.downloads_dir / "content"
        self.metadata_dir = self.downloads_dir / "metadata"
        self.url_index_file = self.downloads_dir / "url_index.json"
        self._directories_created = False
    
    def _ensure_directories(self):
        """Create directories if they don't exist yet."""
        if not self._directories_created:
            self.content_dir.mkdir(parents=True, exist_ok=True)
            self.metadata_dir.mkdir(parents=True, exist_ok=True)
            self._directories_created = True
    
    def get_url_hash(self, url: str) -> str:
        """Generate a hash for the URL to use as filename."""
        return hashlib.sha256(url.encode()).hexdigest()[:12]
    
    def get_content_hash(self, content: bytes) -> str:
        """Generate a hash for the content."""
        return hashlib.sha256(content).hexdigest()[:12]
    
    def load_url_index(self) -> Dict[str, str]:
        """Load the URL to file hash mapping."""
        if self.url_index_file.exists():
            try:
                with open(self.url_index_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    def save_url_index(self, index: Dict[str, str]):
        """Save the URL to file hash mapping."""
        self._ensure_directories()
        with open(self.url_index_file, 'w') as f:
            json.dump(index, f, indent=2)
    
    def get_cached_file(self, url: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Get cached file path and metadata for a URL."""
        url_index = self.load_url_index()
        url_hash = self.get_url_hash(url)
        
        if url_hash in url_index:
            content_hash = url_index[url_hash]
            metadata_file = self.metadata_dir / f"{content_hash}.json"
            
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    
                    content_file = self.content_dir / f"{content_hash}.{metadata.get('extension', 'bin')}"
                    if content_file.exists():
                        return str(content_file), metadata
                except (json.JSONDecodeError, IOError):
                    pass
        
        return None
    
    def save_content(self, url: str, content: bytes, metadata: Dict[str, Any]) -> str:
        """Save content and metadata, return file path."""
        self._ensure_directories()
        content_hash = self.get_content_hash(content)
        
        # Determine file extension
        content_type = metadata.get('content_type', '')
        extension = self._get_extension_from_content_type(content_type)
        if not extension:
            extension = self._get_extension_from_url(url)
        
        # Save content file
        content_file = self.content_dir / f"{content_hash}.{extension}"
        with open(content_file, 'wb') as f:
            f.write(content)
        
        # Update metadata
        metadata['file_hash'] = f"sha256:{hashlib.sha256(content).hexdigest()}"
        metadata['extension'] = extension
        
        # Save metadata file
        metadata_file = self.metadata_dir / f"{content_hash}.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Update URL index
        url_index = self.load_url_index()
        url_hash = self.get_url_hash(url)
        url_index[url_hash] = content_hash
        self.save_url_index(url_index)
        
        return str(content_file)
    
    def _get_extension_from_content_type(self, content_type: str) -> str:
        """Get file extension from content type."""
        type_map = {
            'text/html': 'html',
            'text/plain': 'txt',
            'application/json': 'json',
            'application/xml': 'xml',
            'text/xml': 'xml',
            'text/css': 'css',
            'text/javascript': 'js',
            'application/javascript': 'js',
            'application/pdf': 'pdf',
            'image/png': 'png',
            'image/jpeg': 'jpg',
            'image/gif': 'gif',
            'image/svg+xml': 'svg'
        }
        
        main_type = content_type.split(';')[0].strip().lower()
        return type_map.get(main_type, 'bin')
    
    def _get_extension_from_url(self, url: str) -> str:
        """Get file extension from URL."""
        parsed = urlparse(url)
        path = Path(parsed.path)
        extension = path.suffix.lstrip('.')
        return extension if extension else 'html'


class WebFetch(Tool):
    """Tool for fetching content from URLs with caching support."""
    
    def __init__(self, downloads_dir: str = None):
        """Initialize WebFetch tool.
        
        Args:
            downloads_dir: Directory to store downloaded content. 
                          Defaults to './downloads' relative to current working directory.
        """
        if downloads_dir is None:
            downloads_dir = os.path.join(os.getcwd(), 'downloads')
        
        self.cache_manager = CacheManager(downloads_dir)
        
        parameters = [
            # Required
            Parameter('url', 'string', 'URL to fetch'),
            
            # Content Control
            Parameter('max_length', 'integer', 'Maximum number of characters to return. Default: 5000'),
            Parameter('start_index', 'integer', 'Start content from this character index. Default: 0'),
            Parameter('raw', 'boolean', 'Get raw content without processing. Default: false'),
            
            # HTTP Configuration
            Parameter('method', 'string', 'HTTP method (GET, POST, PUT, DELETE, PATCH). Default: GET'),
            Parameter('headers', 'object', 'HTTP headers as JSON object. Default: {}'),
            Parameter('data', 'string', 'Request body for POST/PUT. Can be JSON string or form data'),
            Parameter('timeout', 'integer', 'Request timeout in seconds. Default: 30'),
            Parameter('verify_ssl', 'boolean', 'Verify SSL certificates. Default: true'),
            Parameter('user_agent', 'string', 'Custom User-Agent header. Default: "AI-6-WebFetch/1.0"'),
            Parameter('force_refresh', 'boolean', 'Skip cache and force fresh fetch. Default: false'),
        ]
        
        super().__init__(
            name='web_fetch',
            description='Fetch content from URLs with caching support. Returns file path and metadata.',
            parameters=parameters,
            required={'url'}
        )
    
    def run(self, **kwargs) -> str:
        """Execute the web fetch operation."""
        try:
            # Extract parameters
            url = kwargs['url']
            max_length = kwargs.get('max_length', 5000)
            start_index = kwargs.get('start_index', 0)
            raw = kwargs.get('raw', False)
            method = kwargs.get('method', 'GET').upper()
            headers = kwargs.get('headers', {})
            data = kwargs.get('data')
            timeout = kwargs.get('timeout', 30)
            verify_ssl = kwargs.get('verify_ssl', True)
            user_agent = kwargs.get('user_agent', 'AI-6-WebFetch/1.0')
            force_refresh = kwargs.get('force_refresh', False)
            
            # Validate URL
            if not self._is_valid_url(url):
                return json.dumps({
                    "url": url,
                    "status": "error",
                    "status_code": None,
                    "error": "Invalid URL format",
                    "error_type": "validation_error",
                    "suggestion": "Ensure URL starts with http:// or https://"
                })
            
            # Check cache first (only for GET requests without data)
            cached_result = None
            if method == 'GET' and not data and not force_refresh:
                cached_result = self.cache_manager.get_cached_file(url)
            
            if cached_result:
                file_path, metadata = cached_result
                # Check if we need to validate cache with server
                if self._should_revalidate_cache(metadata):
                    fresh_result = self._fetch_with_conditional_request(url, metadata, headers, timeout, verify_ssl, user_agent)
                    if fresh_result:
                        file_path, metadata = fresh_result
                    # If 304 Not Modified, use cached version
                
                # Process cached content
                return self._prepare_response(url, file_path, metadata, max_length, start_index, raw, cached=True)
            
            # Perform fresh fetch
            return self._fetch_fresh(url, method, headers, data, timeout, verify_ssl, user_agent, max_length, start_index, raw)
            
        except Exception as e:
            return json.dumps({
                "url": kwargs.get('url', ''),
                "status": "error",
                "status_code": None,
                "error": f"Unexpected error: {str(e)}",
                "error_type": "internal_error",
                "suggestion": "Check the URL and try again. Contact support if the issue persists."
            })
    
    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format and security."""
        try:
            parsed = urlparse(url)
            return parsed.scheme in ['http', 'https'] and parsed.netloc
        except Exception:
            return False
    
    def _should_revalidate_cache(self, metadata: Dict[str, Any]) -> bool:
        """Check if cached content should be revalidated."""
        # Always revalidate if we have ETag or Last-Modified
        return 'etag' in metadata or 'last_modified' in metadata
    
    def _fetch_with_conditional_request(self, url: str, metadata: Dict[str, Any], 
                                      headers: Dict[str, str], timeout: int, 
                                      verify_ssl: bool, user_agent: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Fetch with conditional headers, return None if 304 Not Modified."""
        conditional_headers = headers.copy()
        conditional_headers['User-Agent'] = user_agent
        
        if 'etag' in metadata:
            conditional_headers['If-None-Match'] = metadata['etag']
        if 'last_modified' in metadata:
            conditional_headers['If-Modified-Since'] = metadata['last_modified']
        
        try:
            response = requests.get(url, headers=conditional_headers, 
                                  timeout=timeout, verify=verify_ssl)
            
            if response.status_code == 304:
                # Content not modified, use cache
                return None
            
            # Content was modified, save new version
            content = response.content
            new_metadata = self._extract_metadata(response, url)
            file_path = self.cache_manager.save_content(url, content, new_metadata)
            return file_path, new_metadata
            
        except Exception:
            # If conditional request fails, use cached version
            return None
    
    def _fetch_fresh(self, url: str, method: str, headers: Dict[str, str], 
                    data: str, timeout: int, verify_ssl: bool, user_agent: str,
                    max_length: int, start_index: int, raw: bool) -> str:
        """Perform a fresh HTTP request."""
        try:
            # Prepare headers
            request_headers = headers.copy()
            request_headers['User-Agent'] = user_agent
            
            # Make request
            response = requests.request(
                method=method,
                url=url,
                headers=request_headers,
                data=data,
                timeout=timeout,
                verify=verify_ssl,
                allow_redirects=True
            )
            
            # Handle HTTP errors
            if not response.ok:
                return json.dumps({
                    "url": url,
                    "status": "error",
                    "status_code": response.status_code,
                    "error": f"{response.reason} - {response.text[:200]}",
                    "error_type": "http_error",
                    "suggestion": f"Server returned {response.status_code}. Check URL and try again."
                })
            
            # Extract content and metadata
            content = response.content
            metadata = self._extract_metadata(response, url)
            
            # Save to cache (only for GET requests)
            if method == 'GET':
                file_path = self.cache_manager.save_content(url, content, metadata)
            else:
                # For non-GET requests, create temporary file
                import tempfile
                temp_dir = Path(tempfile.gettempdir()) / "ai6_webfetch"
                temp_dir.mkdir(exist_ok=True)
                temp_file = temp_dir / f"temp_{metadata['file_hash'][:8]}.bin"
                with open(temp_file, 'wb') as f:
                    f.write(content)
                file_path = str(temp_file)
            
            return self._prepare_response(url, file_path, metadata, max_length, start_index, raw, cached=False)
            
        except requests.exceptions.Timeout:
            return json.dumps({
                "url": url,
                "status": "error",
                "status_code": None,
                "error": f"Request timeout after {timeout} seconds",
                "error_type": "timeout",
                "suggestion": "Try increasing the timeout parameter or check network connectivity."
            })
        except requests.exceptions.ConnectionError as e:
            return json.dumps({
                "url": url,
                "status": "error", 
                "status_code": None,
                "error": f"Connection error: {str(e)}",
                "error_type": "connection_error",
                "suggestion": "Check the URL and network connectivity."
            })
        except requests.exceptions.SSLError as e:
            return json.dumps({
                "url": url,
                "status": "error",
                "status_code": None,
                "error": f"SSL error: {str(e)}",
                "error_type": "ssl_error",
                "suggestion": "Try setting verify_ssl to false, or check the site's SSL certificate."
            })
        except Exception as e:
            return json.dumps({
                "url": url,
                "status": "error",
                "status_code": None,
                "error": f"Request error: {str(e)}",
                "error_type": "request_error",
                "suggestion": "Check the URL and request parameters."
            })
    
    def _extract_metadata(self, response: requests.Response, original_url: str) -> Dict[str, Any]:
        """Extract metadata from HTTP response."""
        metadata = {
            "url": original_url,
            "final_url": response.url,
            "content_type": response.headers.get('content-type', ''),
            "content_length": len(response.content),
            "encoding": response.encoding or 'utf-8',
            "fetch_time": datetime.now().isoformat(),
            "cached": False
        }
        
        # Optional headers
        if 'last-modified' in response.headers:
            metadata['last_modified'] = response.headers['last-modified']
        if 'etag' in response.headers:
            metadata['etag'] = response.headers['etag']
        
        return metadata
    
    def _prepare_response(self, url: str, file_path: str, metadata: Dict[str, Any],
                         max_length: int, start_index: int, raw: bool, cached: bool) -> str:
        """Prepare the final response with content processing."""
        try:
            # Read file content
            with open(file_path, 'rb') as f:
                content_bytes = f.read()
            
            # Decode content
            encoding = metadata.get('encoding', 'utf-8')
            try:
                content = content_bytes.decode(encoding)
            except UnicodeDecodeError:
                content = content_bytes.decode('utf-8', errors='replace')
            
            # Apply start_index and max_length
            original_length = len(content)
            if start_index > 0:
                content = content[start_index:]
            
            truncated = False
            if max_length and len(content) > max_length:
                content = content[:max_length]
                truncated = True
            
            # Process content if not raw
            if not raw:
                content = self._process_content(content, metadata.get('content_type', ''))
            
            # Update metadata
            metadata.update({
                "cached": cached,
                "truncated": truncated,
                "start_index": start_index,
                "returned_length": len(content),
                "total_length": original_length
            })
            
            return json.dumps({
                "url": url,
                "status": "success",
                "status_code": 200,  # Assume 200 for cached content
                "file_path": file_path,
                "content": content,
                "metadata": metadata
            })
            
        except Exception as e:
            return json.dumps({
                "url": url,
                "status": "error",
                "status_code": None,
                "error": f"Error processing content: {str(e)}",
                "error_type": "processing_error",
                "suggestion": "Try using raw=true to get unprocessed content."
            })
    
    def _process_content(self, content: str, content_type: str) -> str:
        """Process content based on content type."""
        if 'application/json' in content_type:
            try:
                parsed = json.loads(content)
                return json.dumps(parsed, indent=2)
            except json.JSONDecodeError:
                pass
        
        # For other content types, return as-is
        # In a full implementation, you might add HTML to Markdown conversion here
        return content