"""
Build Correction Applier Module

Applies table corrections during the build step using DOM manipulation.
This module processes HTML tables that were generated with hash data attributes
and applies manual corrections based on stored correction files.
"""

import hashlib
from typing import Dict, Any, Optional
from pathlib import Path
import logging
from bs4 import BeautifulSoup, Tag

from src.modules.manual_review_module.correction_manager import CorrectionManager
from src.utils.table_hash_utils import generate_table_hash_from_html


class BuildCorrectionApplier:
    """Applies table corrections during the build step using DOM manipulation."""
    
    def __init__(self, base_path: str = "data/zhlex"):
        self.correction_manager = CorrectionManager(base_path)
        self.logger = logging.getLogger(__name__)
    
    def apply_corrections_to_html(self, soup: BeautifulSoup, law_id: str, 
                                 version: str, folder: str) -> BeautifulSoup:
        """
        Apply table corrections to HTML using BeautifulSoup DOM manipulation.
        
        This method:
        1. Identifies tables in the HTML by their data attributes
        2. Generates content hashes for each table  
        3. Applies corrections based on hash matches
        4. Returns modified HTML with corrections applied
        
        Args:
            soup: BeautifulSoup object containing the HTML
            law_id: Law identifier (e.g., "170.4")
            version: Version number (e.g., "118")
            folder: Folder containing the law data
            
        Returns:
            Modified BeautifulSoup object with corrections applied
        """
        corrections = self.correction_manager.get_corrections(law_id, version, folder)
        if not corrections:
            self.logger.debug(f"No corrections found for law {law_id} version {version}")
            return soup
        
        # Find all tables in the HTML
        tables = soup.find_all('table', {'data-table-hash': True})
        
        corrections_applied = {
            "total_tables": len(tables),
            "undefined": 0,
            "confirmed_without_changes": 0,
            "confirmed_with_changes": 0,
            "rejected": 0,
            "merged": 0,
            "no_correction_found": 0
        }
        
        for table in tables:
            table_hash = table.get('data-table-hash')
            
            if table_hash in corrections.get('tables', {}):
                correction = corrections['tables'][table_hash]
                status = self._normalize_status(correction)
                
                self.logger.debug(f"Applying correction to table {table_hash} with status {status}")
                self._apply_correction_to_table(table, correction, status, soup)
                
                # Track correction application
                if status == "undefined":
                    corrections_applied["undefined"] += 1
                elif status == "confirmed_without_changes":
                    corrections_applied["confirmed_without_changes"] += 1
                elif status == "confirmed_with_changes":
                    corrections_applied["confirmed_with_changes"] += 1
                elif status == "rejected":
                    corrections_applied["rejected"] += 1
                elif status.startswith("merged_with_"):
                    corrections_applied["merged"] += 1
            else:
                corrections_applied["no_correction_found"] += 1
                self.logger.debug(f"No correction found for table {table_hash}, keeping original")
        
        self.logger.info(f"Applied corrections for {law_id} v{version}: {corrections_applied}")
        return soup
    
    def _normalize_status(self, correction: Dict[str, Any]) -> str:
        """
        Normalize legacy status values to the new status system.
        
        Args:
            correction: Single table correction data
            
        Returns:
            Normalized status string
        """
        status = correction.get("status", "undefined")
        
        # Handle new status system (pass through unchanged)
        if status in ["undefined", "confirmed_without_changes", "confirmed_with_changes", "rejected"]:
            return status
        
        # Handle merge statuses (pass through unchanged)
        if status.startswith("merged"):
            return status
            
        # Handle legacy status system
        if status == "confirmed":
            # Check if corrections exist to determine the correct new status
            has_corrections = (
                "corrected_structure" in correction and 
                correction["corrected_structure"] != correction.get("original_structure", [])
            )
            if has_corrections:
                return "confirmed_with_changes"
            else:
                return "confirmed_without_changes"
                
        elif status == "edited":
            return "confirmed_with_changes"
        
        # Unknown status, default to undefined
        self.logger.warning(f"Unknown status '{status}' for table {correction.get('hash', 'unknown')}, defaulting to 'undefined'")
        return "undefined"
    
    def _apply_correction_to_table(self, table_elem: Tag, correction: Dict[str, Any], status: str, soup: BeautifulSoup):
        """Apply a specific correction to a table element."""
        
        if status == "confirmed_without_changes":
            # No changes needed
            pass
            
        elif status == "confirmed_with_changes":
            # Replace table content with corrected structure
            corrected_structure = correction.get("corrected_structure", [])
            if corrected_structure:
                self._rebuild_table_from_structure(table_elem, corrected_structure, soup)
            else:
                self.logger.warning(f"Table marked as 'confirmed_with_changes' but no corrected_structure found")
                
        elif status == "rejected":
            # Convert table to paragraphs
            self._convert_table_to_paragraphs(table_elem, soup)
            
        elif status.startswith("merged_with_"):
            # Handle table merging (remove this table, target will include content)
            self.logger.info(f"Removing merged table with hash {table_elem.get('data-table-hash')}")
            table_elem.decompose()
    
    def _rebuild_table_from_structure(self, table_elem: Tag, corrected_structure: list, soup: BeautifulSoup):
        """
        Rebuild table content from corrected structure.
        
        Args:
            table_elem: Table element to modify
            corrected_structure: List of rows, each row is a list of cell contents
        """
        
        # Clear existing table content
        table_elem.clear()
        
        # Preserve table attributes
        table_attrs = table_elem.attrs.copy()
        
        # Create new table structure
        if corrected_structure:
            # Determine if first row should be header
            first_row = corrected_structure[0]
            is_header = True  # Assume first row is header for law tables
            
            # Create thead if first row is header
            if is_header and len(corrected_structure) > 1:
                thead = soup.new_tag("thead")
                tr = soup.new_tag("tr")
                
                for cell_text in first_row:
                    th = soup.new_tag("th")
                    th.string = cell_text if cell_text else ""
                    tr.append(th)
                
                thead.append(tr)
                table_elem.append(thead)
                
                # Create tbody for remaining rows
                if len(corrected_structure) > 1:
                    tbody = soup.new_tag("tbody")
                    
                    for row in corrected_structure[1:]:
                        tr = soup.new_tag("tr")
                        
                        for cell_text in row:
                            td = soup.new_tag("td")
                            td.string = cell_text if cell_text else ""
                            tr.append(td)
                        
                        tbody.append(tr)
                    
                    table_elem.append(tbody)
            else:
                # All rows as tbody
                tbody = soup.new_tag("tbody")
                
                for row in corrected_structure:
                    tr = soup.new_tag("tr")
                    
                    for cell_text in row:
                        td = soup.new_tag("td")
                        td.string = cell_text if cell_text else ""
                        tr.append(td)
                    
                    tbody.append(tr)
                
                table_elem.append(tbody)
        
        # Restore table attributes
        for attr, value in table_attrs.items():
            table_elem[attr] = value
        
        self.logger.debug(f"Rebuilt table with {len(corrected_structure)} rows")
    
    def _convert_table_to_paragraphs(self, table_elem: Tag, soup: BeautifulSoup):
        """
        Convert table to regular paragraphs.
        
        Args:
            table_elem: Table element to convert
        """
        # Extract all text content from table
        paragraphs = []
        
        for row in table_elem.find_all('tr'):
            row_texts = []
            for cell in row.find_all(['td', 'th']):
                text = cell.get_text(strip=True)
                if text:
                    row_texts.append(text)
            
            if row_texts:
                # Join cell contents with spaces
                paragraph_text = ' '.join(row_texts)
                paragraphs.append(paragraph_text)
        
        # Replace table with paragraphs
        if paragraphs:
            for paragraph_text in paragraphs:
                p = soup.new_tag("p")
                p.string = paragraph_text
                table_elem.insert_before(p)
        
        # Remove the original table
        table_elem.decompose()
        
        self.logger.debug(f"Converted table to {len(paragraphs)} paragraphs")


def extract_law_id_version_from_path(html_file_path: str) -> tuple:
    """
    Extract law_id and version from HTML file path.
    
    Args:
        html_file_path: Path to the HTML file
        
    Returns:
        Tuple of (law_id, version) or (None, None) if not extractable
    """
    try:
        path = Path(html_file_path)
        parts = path.parts
        
        # Look for zhlex_files or zhlex_files_test in the path
        for i, part in enumerate(parts):
            if part in ["zhlex_files", "zhlex_files_test", "fedlex_files", "fedlex_files_test"]:
                if i + 2 < len(parts):
                    law_id = parts[i + 1]  # e.g., "170.4"
                    version = parts[i + 2]  # e.g., "118"
                    return law_id, version
                break
        
        return None, None
    except Exception:
        return None, None


def folder_from_path(html_file_path: str) -> str:
    """
    Extract folder name from HTML file path.
    
    Args:
        html_file_path: Path to the HTML file
        
    Returns:
        Folder name (e.g., "zhlex_files_test") or "zhlex_files" as default
    """
    try:
        path = Path(html_file_path)
        if "zhlex_files_test" in str(path):
            return "zhlex_files_test"
        elif "fedlex_files_test" in str(path):
            return "fedlex_files_test"
        elif "fedlex_files" in str(path):
            return "fedlex_files"
        else:
            return "zhlex_files"
    except Exception:
        return "zhlex_files"