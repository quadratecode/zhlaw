"""Date conversion utilities for legal data processing.

This module handles conversion between different date formats used in legal data,
particularly the YYYYMMDD format used in Swiss legal texts and standard SQL dates.

Functions:
    convert_date_string(date_str): Convert YYYYMMDD string to SQL date
    validate_date(date_str): Validate date string format
    parse_date_safe(date_str): Safe date parsing with error handling

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def convert_date_string(date_str: str) -> Optional[str]:
    """Convert YYYYMMDD date string to SQL date format (YYYY-MM-DD).
    
    Args:
        date_str: Date string in YYYYMMDD format
        
    Returns:
        String in YYYY-MM-DD format or None if invalid/empty
    """
    if not date_str or date_str.strip() == '':
        return None
        
    try:
        # Remove any whitespace
        date_str = date_str.strip()
        
        # Check if it's already in YYYY-MM-DD format
        if '-' in date_str:
            # Validate the format
            datetime.strptime(date_str, '%Y-%m-%d')
            return date_str
        
        # Convert YYYYMMDD to YYYY-MM-DD
        if len(date_str) == 8 and date_str.isdigit():
            year = date_str[:4]
            month = date_str[4:6]
            day = date_str[6:8]
            
            # Validate the date
            formatted_date = f"{year}-{month}-{day}"
            datetime.strptime(formatted_date, '%Y-%m-%d')
            return formatted_date
        else:
            logger.warning(f"Invalid date format: {date_str}")
            return None
            
    except ValueError as e:
        logger.warning(f"Could not parse date '{date_str}': {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error parsing date '{date_str}': {e}")
        return None


def validate_date(date_str: str) -> bool:
    """Validate if a date string is in valid YYYYMMDD or YYYY-MM-DD format.
    
    Args:
        date_str: Date string to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not date_str or date_str.strip() == '':
        return True  # Empty dates are valid (NULL)
        
    try:
        date_str = date_str.strip()
        
        # Check YYYY-MM-DD format
        if '-' in date_str:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
            
        # Check YYYYMMDD format
        if len(date_str) == 8 and date_str.isdigit():
            year = date_str[:4]
            month = date_str[4:6]
            day = date_str[6:8]
            datetime.strptime(f"{year}-{month}-{day}", '%Y-%m-%d')
            return True
            
        return False
        
    except ValueError:
        return False
    except Exception:
        return False


def parse_date_safe(date_str: str, field_name: str = "date") -> Optional[str]:
    """Safely parse a date string with detailed logging.
    
    Args:
        date_str: Date string to parse
        field_name: Name of the field for logging purposes
        
    Returns:
        Parsed date string or None if invalid
    """
    if not date_str or date_str.strip() == '':
        logger.debug(f"Empty {field_name} field")
        return None
        
    result = convert_date_string(date_str)
    if result is None:
        logger.warning(f"Could not parse {field_name}: '{date_str}'")
    else:
        logger.debug(f"Parsed {field_name}: '{date_str}' -> '{result}'")
        
    return result


def convert_boolean_safe(value) -> Optional[bool]:
    """Safely convert various boolean representations to Python boolean.
    
    Args:
        value: Value to convert (bool, str, int, etc.)
        
    Returns:
        Boolean value or None if cannot be determined
    """
    if value is None:
        return None
        
    if isinstance(value, bool):
        return value
        
    if isinstance(value, str):
        value = value.strip().lower()
        if value in ('true', '1', 'yes', 'on'):
            return True
        elif value in ('false', '0', 'no', 'off', ''):
            return False
        else:
            logger.warning(f"Could not parse boolean value: '{value}'")
            return None
            
    if isinstance(value, int):
        return bool(value)
        
    logger.warning(f"Could not parse boolean value: '{value}' (type: {type(value)})")
    return None


def safe_float_conversion(value) -> Optional[float]:
    """Safely convert value to float.
    
    Args:
        value: Value to convert
        
    Returns:
        Float value or None if conversion fails
    """
    if value is None or value == '':
        return None
        
    try:
        return float(value)
    except (ValueError, TypeError) as e:
        logger.warning(f"Could not convert to float: '{value}' - {e}")
        return None


def safe_int_conversion(value) -> Optional[int]:
    """Safely convert value to integer.
    
    Args:
        value: Value to convert
        
    Returns:
        Integer value or None if conversion fails
    """
    if value is None or value == '':
        return None
        
    try:
        # Handle float strings
        if isinstance(value, str) and '.' in value:
            return int(float(value))
        return int(value)
    except (ValueError, TypeError) as e:
        logger.warning(f"Could not convert to int: '{value}' - {e}")
        return None