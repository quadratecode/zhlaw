"""
Table Hash Utilities

Shared utilities for generating table hashes consistently across processing and build steps.
This ensures that table hashes generated during processing match those generated during build.
"""

import hashlib
from typing import List, Dict, Any
from bs4 import BeautifulSoup, Tag


def generate_table_hash_from_elements(table_elements: List[Dict[str, Any]]) -> str:
    """
    Generate content-based hash for table elements (JSON format from processing).
    
    Args:
        table_elements: List of JSON elements belonging to the same table
        
    Returns:
        16-character hash string
    """
    content = []
    for element in sorted(table_elements, key=lambda x: x.get('Path', '')):
        text = element.get('Text', '').strip()
        if text:
            content.append(text)
    
    content_str = '|'.join(content)
    return hashlib.sha256(content_str.encode('utf-8')).hexdigest()[:16]


def generate_table_hash_from_html(table_elem: Tag) -> str:
    """
    Generate content-based hash from HTML table element (build step).
    
    Args:
        table_elem: BeautifulSoup table element
        
    Returns:
        16-character hash string matching the processing step
    """
    content = []
    
    # Extract text content from all cells in reading order
    for cell in table_elem.find_all(['td', 'th']):
        text = cell.get_text(strip=True)
        if text:
            content.append(text)
    
    content_str = '|'.join(content)
    return hashlib.sha256(content_str.encode('utf-8')).hexdigest()[:16]


def analyze_tables_in_elements(elements: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Analyze all tables in JSON elements and compute their hashes.
    
    Args:
        elements: List of JSON elements
        
    Returns:
        Dictionary mapping table_id to table information including hash and element indices
    """
    table_info = {}
    
    for i, element in enumerate(elements):
        table_id = element.get("attributes", {}).get("TableID")
        if table_id is not None:
            if table_id not in table_info:
                table_info[table_id] = {
                    "indices": [],
                    "elements": []
                }
            table_info[table_id]["indices"].append(i)
            table_info[table_id]["elements"].append(element)
    
    # Compute hash for each table
    for table_id, info in table_info.items():
        info["hash"] = generate_table_hash_from_elements(info["elements"])
    
    return table_info