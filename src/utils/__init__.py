"""
Utility modules for ZHLaw processing system.

This package contains common utilities to reduce code duplication
and provide consistent implementations across the codebase.
"""

from .file_utils import (
    FileOperations,
    MetadataHandler,
    PathBuilder,
    read_json,
    write_json,
    ensure_directory
)

from .http_utils import (
    HTTPClient,
    WebScraper,
    retry_on_failure,
    download_file,
    fetch_json
)

__all__ = [
    # File utilities
    'FileOperations',
    'MetadataHandler', 
    'PathBuilder',
    'read_json',
    'write_json',
    'ensure_directory',
    
    # HTTP utilities
    'HTTPClient',
    'WebScraper',
    'retry_on_failure',
    'download_file',
    'fetch_json'
]