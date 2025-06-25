"""Utility functions for the Fedlex module.

This module provides shared utility functions used across the Fedlex
processing pipeline, including date formatting, file operations, and
validation functions.

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
import arrow
from functools import wraps
import time

from . import fedlex_config as config

logger = logging.getLogger(__name__)


def format_date(date_str: Optional[str]) -> str:
    """Format a date string to YYYYMMDD format.
    
    Args:
        date_str: Date string in various formats or None
        
    Returns:
        Formatted date string in YYYYMMDD format or empty string
    """
    if not date_str or not isinstance(date_str, str):
        return ""
    
    try:
        return arrow.get(date_str).format(config.DATE_FORMAT)
    except (arrow.parser.ParserError, TypeError, ValueError):
        logger.debug(f"Could not parse date string: {date_str}")
        return ""


def is_valid_sr_number(sr_number: str) -> bool:
    """Validate SR number format.
    
    Args:
        sr_number: SR notation to validate
        
    Returns:
        True if valid SR number format
    """
    return bool(sr_number and re.match(config.SR_NUMBER_PATTERN, sr_number.strip()))


def is_valid_date_folder(folder_name: str) -> bool:
    """Check if folder name matches date format YYYYMMDD.
    
    Args:
        folder_name: Folder name to validate
        
    Returns:
        True if valid date folder format
    """
    return bool(re.fullmatch(config.DATE_FOLDER_PATTERN, folder_name))


def load_json_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """Load JSON file with error handling.
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        Parsed JSON data or None if error
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
        return None


def save_json_file(data: Dict[str, Any], file_path: Path) -> bool:
    """Save data to JSON file with error handling.
    
    Args:
        data: Data to save
        file_path: Path to save to
        
    Returns:
        True if successful, False otherwise
    """
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except IOError as e:
        logger.error(f"Error writing to {file_path}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error saving {file_path}: {e}")
        return False


def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator for retrying failed operations.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}): {e}"
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"{func.__name__} failed after {max_retries} attempts: {e}"
                        )
            
            raise last_exception
        
        return wrapper
    return decorator


def extract_public_url(filestore_url: str) -> str:
    """Extract public-facing URL from filestore URL.
    
    Args:
        filestore_url: Fedlex filestore URL
        
    Returns:
        Public-facing www.fedlex.admin.ch URL or empty string
    """
    if not filestore_url or not isinstance(filestore_url, str):
        return ""
    
    match = re.search(config.FILESTORE_URL_PATTERN, filestore_url)
    if match:
        path_part, lang = match.groups()
        return config.PUBLIC_URL_TEMPLATE.format(path=path_part, lang=lang)
    else:
        logger.debug(f"Could not extract public URL from: {filestore_url}")
        return ""


def group_by_sr_number(file_paths: List[Path]) -> Dict[str, List[Path]]:
    """Group file paths by SR number.
    
    Args:
        file_paths: List of metadata file paths
        
    Returns:
        Dictionary mapping SR numbers to their file paths
    """
    groups = {}
    
    for file_path in file_paths:
        # Extract SR number from filename (e.g., "101.1-20240101-metadata.json")
        match = re.search(r"([0-9.]+)-\d{8}-metadata\.json$", file_path.name)
        if match:
            sr_number = match.group(1)
            groups.setdefault(sr_number, []).append(file_path)
    
    return groups


def find_metadata_files(base_dir: Path) -> List[Path]:
    """Find all metadata JSON files in the directory structure.
    
    Args:
        base_dir: Base directory to search
        
    Returns:
        List of metadata file paths
    """
    metadata_files = []
    
    if not base_dir.exists():
        logger.error(f"Base directory not found: {base_dir}")
        return metadata_files
    
    # Pattern: base_dir/SR_NUMBER/YYYYMMDD/SR_NUMBER-YYYYMMDD-metadata.json
    for sr_dir in base_dir.iterdir():
        if sr_dir.is_dir() and is_valid_sr_number(sr_dir.name):
            for date_dir in sr_dir.iterdir():
                if date_dir.is_dir() and is_valid_date_folder(date_dir.name):
                    metadata_pattern = f"{sr_dir.name}-{date_dir.name}-metadata.json"
                    metadata_file = date_dir / metadata_pattern
                    if metadata_file.exists():
                        metadata_files.append(metadata_file)
    
    return metadata_files


def parse_numeric_date(date_str: str) -> Optional[float]:
    """Convert YYYYMMDD string to numeric format.
    
    Args:
        date_str: Date in YYYYMMDD format
        
    Returns:
        Float representation of date or None
    """
    try:
        return float(date_str) if date_str and date_str.isdigit() else None
    except ValueError:
        return None


def is_law_repealed(aufhebungsdatum: str) -> bool:
    """Check if a law has been repealed based on aufhebungsdatum.
    
    Args:
        aufhebungsdatum: Repeal date in YYYYMMDD format or empty
        
    Returns:
        True if law has been repealed
    """
    return bool(aufhebungsdatum and aufhebungsdatum.strip())


def normalize_sr_number(sr_number: str) -> str:
    """Normalize SR number by removing leading '0.' for consistency.
    
    Args:
        sr_number: SR number to normalize
        
    Returns:
        Normalized SR number
    """
    if sr_number.startswith("0."):
        return sr_number[2:]
    return sr_number


def is_international_law(sr_number: str) -> bool:
    """Check if SR number represents international law.
    
    Args:
        sr_number: SR notation
        
    Returns:
        True if international law (starts with 0.)
    """
    return sr_number.strip().startswith(config.INTERNATIONAL_LAW_PREFIX)