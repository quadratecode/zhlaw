"""
HTTP operation utilities for ZHLaw processing system.

This module provides common HTTP operations with consistent error handling,
retries, and logging.

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import time
from typing import Dict, Optional, Any, Callable
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.logging_config import get_logger
from src.exceptions import NetworkException, ScrapingException
from src.config import APIConfig
from src.constants import HTTPStatus

logger = get_logger(__name__)


class HTTPClient:
    """HTTP client with retry logic and consistent error handling."""
    
    def __init__(
        self,
        max_retries: int = APIConfig.MAX_RETRIES,
        timeout: int = APIConfig.REQUEST_TIMEOUT,
        user_agent: str = "Mozilla/5.0 (compatible; ZHLaw/1.0)",
        delay_between_requests: float = APIConfig.WEB_REQUEST_DELAY
    ):
        """
        Initialize HTTP client with retry configuration.
        
        Args:
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds
            user_agent: User agent string
            delay_between_requests: Delay between requests in seconds
        """
        self.max_retries = max_retries
        self.timeout = timeout
        self.user_agent = user_agent
        self.delay_between_requests = delay_between_requests
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Create a requests session with retry configuration."""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set default headers
        session.headers.update({
            "User-Agent": self.user_agent
        })
        
        return session
    
    def get(
        self, 
        url: str, 
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        allow_redirects: bool = True,
        **kwargs
    ) -> requests.Response:
        """
        Make a GET request with error handling.
        
        Args:
            url: URL to request
            params: Query parameters
            headers: Additional headers
            allow_redirects: Whether to follow redirects
            **kwargs: Additional arguments for requests
            
        Returns:
            Response object
            
        Raises:
            NetworkException: If request fails
        """
        try:
            # Add delay between requests
            time.sleep(self.delay_between_requests)
            
            # Merge headers
            request_headers = self.session.headers.copy()
            if headers:
                request_headers.update(headers)
            
            logger.debug(f"Making GET request to: {url}")
            response = self.session.get(
                url,
                params=params,
                headers=request_headers,
                timeout=self.timeout,
                allow_redirects=allow_redirects,
                **kwargs
            )
            
            response.raise_for_status()
            logger.debug(f"Request successful: {url} (Status: {response.status_code})")
            
            return response
            
        except requests.exceptions.Timeout:
            raise NetworkException(url, details={"error": "Request timed out"})
        except requests.exceptions.ConnectionError:
            raise NetworkException(url, details={"error": "Connection failed"})
        except requests.exceptions.HTTPError as e:
            raise NetworkException(
                url, 
                status_code=e.response.status_code if e.response else None,
                details={"error": str(e)}
            )
        except Exception as e:
            raise NetworkException(url, details={"error": str(e), "type": type(e).__name__})
    
    def post(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> requests.Response:
        """
        Make a POST request with error handling.
        
        Args:
            url: URL to request
            data: Form data
            json: JSON data
            headers: Additional headers
            **kwargs: Additional arguments for requests
            
        Returns:
            Response object
            
        Raises:
            NetworkException: If request fails
        """
        try:
            # Add delay between requests
            time.sleep(self.delay_between_requests)
            
            # Merge headers
            request_headers = self.session.headers.copy()
            if headers:
                request_headers.update(headers)
            
            logger.debug(f"Making POST request to: {url}")
            response = self.session.post(
                url,
                data=data,
                json=json,
                headers=request_headers,
                timeout=self.timeout,
                **kwargs
            )
            
            response.raise_for_status()
            logger.debug(f"Request successful: {url} (Status: {response.status_code})")
            
            return response
            
        except Exception as e:
            # Reuse GET error handling
            if isinstance(e, NetworkException):
                raise
            return self.get(url)  # This will raise the appropriate exception
    
    def download_file(
        self,
        url: str,
        destination: Path,
        chunk_size: int = 8192,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Path:
        """
        Download a file with progress tracking.
        
        Args:
            url: URL to download
            destination: Path to save the file
            chunk_size: Download chunk size
            progress_callback: Optional callback for progress updates (current, total)
            
        Returns:
            Path to downloaded file
            
        Raises:
            NetworkException: If download fails
        """
        try:
            # Ensure parent directory exists
            destination.parent.mkdir(parents=True, exist_ok=True)
            
            response = self.get(url, stream=True)
            total_size = int(response.headers.get('content-length', 0))
            
            logger.info(f"Downloading {url} to {destination}")
            
            downloaded = 0
            with open(destination, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if progress_callback and total_size > 0:
                            progress_callback(downloaded, total_size)
            
            logger.info(f"Successfully downloaded: {destination}")
            return destination
            
        except Exception as e:
            # Clean up partial download
            if destination.exists():
                destination.unlink()
            
            if isinstance(e, NetworkException):
                raise
            raise NetworkException(
                url,
                details={"error": f"Failed to download file: {str(e)}"}
            )
    
    def close(self):
        """Close the HTTP session."""
        self.session.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


class WebScraper:
    """Web scraping utilities with BeautifulSoup integration."""
    
    def __init__(self, http_client: Optional[HTTPClient] = None):
        """
        Initialize web scraper.
        
        Args:
            http_client: Optional HTTP client instance
        """
        self.http_client = http_client or HTTPClient()
        self._owns_client = http_client is None
    
    def fetch_page(self, url: str, **kwargs) -> str:
        """
        Fetch a web page and return its content.
        
        Args:
            url: URL to fetch
            **kwargs: Additional arguments for HTTP client
            
        Returns:
            Page content as string
            
        Raises:
            ScrapingException: If page cannot be fetched
        """
        try:
            response = self.http_client.get(url, **kwargs)
            return response.text
        except NetworkException as e:
            raise ScrapingException(
                url,
                "Failed to fetch page",
                {"network_error": str(e)}
            )
    
    def fetch_json(self, url: str, **kwargs) -> Dict[str, Any]:
        """
        Fetch JSON data from a URL.
        
        Args:
            url: URL to fetch
            **kwargs: Additional arguments for HTTP client
            
        Returns:
            Parsed JSON data
            
        Raises:
            ScrapingException: If JSON cannot be fetched or parsed
        """
        try:
            response = self.http_client.get(url, **kwargs)
            # Check content type
            content_type = response.headers.get('content-type', '')
            if 'application/json' not in content_type:
                logger.warning(f"Expected JSON but got {content_type} from {url}")
            return response.json()
        except NetworkException as e:
            raise ScrapingException(
                url,
                "Failed to fetch JSON",
                {"network_error": str(e)}
            )
        except (ValueError, requests.exceptions.JSONDecodeError) as e:
            raise ScrapingException(
                url,
                "Invalid JSON response",
                {"parse_error": str(e)}
            )
    
    def close(self):
        """Close the HTTP client if owned by this scraper."""
        if self._owns_client:
            self.http_client.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def retry_on_failure(
    func: Callable,
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Any:
    """
    Retry a function on failure with exponential backoff.
    
    Args:
        func: Function to retry
        max_attempts: Maximum number of attempts
        delay: Initial delay between attempts
        backoff_factor: Multiplier for delay after each failure
        exceptions: Tuple of exceptions to catch
        
    Returns:
        Function result
        
    Raises:
        Last exception if all attempts fail
    """
    last_exception = None
    current_delay = delay
    
    for attempt in range(max_attempts):
        try:
            return func()
        except exceptions as e:
            last_exception = e
            if attempt < max_attempts - 1:
                logger.warning(
                    f"Attempt {attempt + 1}/{max_attempts} failed: {e}. "
                    f"Retrying in {current_delay}s..."
                )
                time.sleep(current_delay)
                current_delay *= backoff_factor
            else:
                logger.error(f"All {max_attempts} attempts failed")
    
    raise last_exception


# Convenience functions
def download_file(url: str, destination: Path) -> Path:
    """Convenience function to download a file."""
    with HTTPClient() as client:
        return client.download_file(url, destination)


def fetch_json(url: str) -> Dict[str, Any]:
    """Convenience function to fetch JSON data."""
    with WebScraper() as scraper:
        return scraper.fetch_json(url)