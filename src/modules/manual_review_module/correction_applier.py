"""
Correction Applier Module

Applies table corrections during the HTML generation process.
"""

import hashlib
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import logging

from src.modules.manual_review_module.correction_manager import CorrectionManager


class CorrectionApplier:
    """Applies table corrections to JSON elements during HTML generation."""
    
    def __init__(self, base_path: str = "data/zhlex"):
        self.correction_manager = CorrectionManager(base_path)
        self.logger = logging.getLogger(__name__)
    
    def apply_corrections(self, elements: List[Dict[str, Any]], law_id: str, 
                         version: str, folder: str = "zhlex_files") -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Apply corrections to elements based on saved correction files.
        
        Args:
            elements: List of elements from JSON
            law_id: Law identifier (e.g., "170.4")
            version: Version number (e.g., "118")
            folder: Folder containing the law data
            
        Returns:
            Tuple of (modified_elements, corrections_applied)
        """
        # Get corrections for this law
        corrections = self.correction_manager.get_corrections(law_id, folder)
        if not corrections:
            self.logger.debug(f"No corrections found for law {law_id}")
            return elements, {}
        
        self.logger.info(f"Applying corrections for law {law_id} version {version}")
        
        # Track which corrections were applied
        corrections_applied = {
            "total_tables": 0,
            "rejected": 0,
            "confirmed": 0,
            "edited": 0,
            "merged": 0
        }
        
        # First pass: identify all tables and their hashes
        table_info = self._analyze_tables(elements)
        corrections_applied["total_tables"] = len(table_info)
        
        # Second pass: apply corrections
        modified_elements = []
        processed_table_ids = set()
        skip_elements = set()
        
        for i, element in enumerate(elements):
            # Skip elements that were marked for skipping (e.g., merged tables)
            if i in skip_elements:
                continue
                
            table_id = element.get("attributes", {}).get("TableID")
            
            if table_id is not None and table_id not in processed_table_ids:
                # This is the first element of a table
                table_hash = table_info.get(table_id, {}).get("hash")
                
                if table_hash and table_hash in corrections.get("tables", {}):
                    correction = corrections["tables"][table_hash]
                    status = correction.get("status", "")
                    
                    if status == "rejected":
                        # Remove TableID from all elements of this table
                        corrections_applied["rejected"] += 1
                        modified_elements.extend(
                            self._reject_table(elements, table_id, table_info[table_id]["indices"])
                        )
                        processed_table_ids.add(table_id)
                        
                    elif status == "confirmed":
                        # Keep table as-is
                        corrections_applied["confirmed"] += 1
                        modified_elements.extend(
                            self._get_table_elements(elements, table_info[table_id]["indices"])
                        )
                        processed_table_ids.add(table_id)
                        
                    elif status == "edited":
                        # Apply edits to table
                        corrections_applied["edited"] += 1
                        modified_elements.extend(
                            self._edit_table(elements, table_id, table_info[table_id]["indices"],
                                           correction.get("corrected_structure", []))
                        )
                        processed_table_ids.add(table_id)
                        
                    elif status.startswith("merged_with_"):
                        # Handle table merging
                        corrections_applied["merged"] += 1
                        target_hash = status.replace("merged_with_", "")
                        
                        # Find target table ID
                        target_table_id = None
                        for tid, info in table_info.items():
                            if info.get("hash") == target_hash:
                                target_table_id = tid
                                break
                        
                        if target_table_id:
                            # Only perform merge if we haven't processed the target yet
                            if target_table_id not in processed_table_ids:
                                merged_elements = self._merge_tables(
                                    elements, table_id, table_hash, target_hash,
                                    table_info, corrections.get("tables", {})
                                )
                                modified_elements.extend(merged_elements)
                                
                                # Mark both tables as processed
                                processed_table_ids.add(table_id)
                                processed_table_ids.add(target_table_id)
                            else:
                                # Target already processed, skip this source table
                                self.logger.info(f"Skipping merge source table {table_id} as target {target_table_id} already processed")
                        else:
                            self.logger.error(f"Target table with hash {target_hash} not found for merge")
                            # Keep original table if merge fails
                            modified_elements.extend(
                                self._get_table_elements(elements, table_info[table_id]["indices"])
                            )
                            processed_table_ids.add(table_id)
                    else:
                        # Unknown status, keep as-is
                        modified_elements.extend(
                            self._get_table_elements(elements, table_info[table_id]["indices"])
                        )
                        processed_table_ids.add(table_id)
                else:
                    # No correction for this table
                    if table_id not in processed_table_ids:
                        modified_elements.extend(
                            self._get_table_elements(elements, table_info.get(table_id, {}).get("indices", []))
                        )
                        processed_table_ids.add(table_id)
                        
            elif table_id is None:
                # Not a table element
                modified_elements.append(element)
            # Skip other table elements as they're handled with the first element
        
        self.logger.info(f"Applied corrections: {corrections_applied}")
        return modified_elements, corrections_applied
    
    def _analyze_tables(self, elements: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Analyze all tables in the elements and compute their hashes.
        
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
            info["hash"] = self._generate_table_hash(info["elements"])
        
        return table_info
    
    def _generate_table_hash(self, table_elements: List[Dict[str, Any]]) -> str:
        """Generate content-based hash for table elements."""
        content = []
        for element in sorted(table_elements, key=lambda x: x.get('Path', '')):
            text = element.get('Text', '').strip()
            if text:
                content.append(text)
        
        content_str = '|'.join(content)
        return hashlib.sha256(content_str.encode('utf-8')).hexdigest()[:16]
    
    def _reject_table(self, elements: List[Dict[str, Any]], table_id: str, 
                     indices: List[int]) -> List[Dict[str, Any]]:
        """
        Remove TableID from all elements of a table to convert them to regular paragraphs.
        """
        rejected_elements = []
        for idx in indices:
            element = elements[idx].copy()
            if "attributes" in element and "TableID" in element["attributes"]:
                element["attributes"] = element["attributes"].copy()
                del element["attributes"]["TableID"]
            rejected_elements.append(element)
        return rejected_elements
    
    def _get_table_elements(self, elements: List[Dict[str, Any]], indices: List[int]) -> List[Dict[str, Any]]:
        """Get table elements by their indices."""
        return [elements[idx] for idx in indices]
    
    def _edit_table(self, elements: List[Dict[str, Any]], table_id: str,
                   indices: List[int], corrected_structure: List[List[str]]) -> List[Dict[str, Any]]:
        """
        Apply edits to a table based on corrected structure.
        
        This is a complex operation that needs to map the corrected structure
        back to the element format. For now, this is a simplified implementation.
        """
        # Get original elements
        table_elements = self._get_table_elements(elements, indices)
        
        # Create a mapping of cell positions to corrected text
        correction_map = self._create_correction_map(table_elements, corrected_structure)
        
        # Apply corrections
        edited_elements = []
        for element in table_elements:
            element_copy = element.copy()
            
            # Check if this element's text should be corrected
            path = element.get("Path", "")
            text = element.get("Text", "")
            
            if text and path in correction_map:
                element_copy["Text"] = correction_map[path]
            
            edited_elements.append(element_copy)
        
        return edited_elements
    
    def _create_correction_map(self, table_elements: List[Dict[str, Any]], 
                              corrected_structure: List[List[str]]) -> Dict[str, str]:
        """
        Create a mapping from element paths to corrected text.
        
        This is a simplified implementation. In practice, this would need
        more sophisticated logic to properly map table structure to elements.
        """
        correction_map = {}
        
        # Extract the table structure from elements
        rows = {}
        for element in table_elements:
            path = element.get("Path", "")
            text = element.get("Text", "")
            
            # Parse row and cell information from path
            import re
            row_match = re.search(r"/TR\[(\d+)\]", path)
            cell_match = re.search(r"/T[HD]\[(\d+)\]", path)
            
            if row_match and cell_match and text:
                row_idx = int(row_match.group(1)) - 1  # Convert to 0-based
                cell_idx = int(cell_match.group(1)) - 1
                
                if row_idx not in rows:
                    rows[row_idx] = {}
                rows[row_idx][cell_idx] = {"path": path, "text": text}
        
        # Map corrected structure to paths
        for row_idx, row_data in enumerate(corrected_structure):
            if row_idx in rows:
                for cell_idx, corrected_text in enumerate(row_data):
                    if cell_idx in rows[row_idx]:
                        original_path = rows[row_idx][cell_idx]["path"]
                        original_text = rows[row_idx][cell_idx]["text"]
                        
                        if corrected_text != original_text:
                            correction_map[original_path] = corrected_text
        
        return correction_map
    
    def _merge_tables(self, elements: List[Dict[str, Any]], source_table_id: str,
                     source_hash: str, target_hash: str, table_info: Dict[str, Any],
                     all_corrections: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Merge two tables based on correction instructions.
        
        Combines rows from source table into target table.
        """
        # Find target table by hash
        target_table_id = None
        for tid, info in table_info.items():
            if info.get("hash") == target_hash:
                target_table_id = tid
                break
        
        if target_table_id is None:
            self.logger.error(f"Target table with hash {target_hash} not found for merge")
            # Return source table unchanged
            source_indices = table_info.get(source_table_id, {}).get("indices", [])
            return self._get_table_elements(elements, source_indices)
        
        # Get elements for both tables
        source_indices = table_info.get(source_table_id, {}).get("indices", [])
        target_indices = table_info.get(target_table_id, {}).get("indices", [])
        
        source_elements = self._get_table_elements(elements, source_indices)
        target_elements = self._get_table_elements(elements, target_indices)
        
        # Find the maximum row number in target table
        max_target_row = 0
        for elem in target_elements:
            path = elem.get("Path", "")
            import re
            row_match = re.search(r"/TR\[(\d+)\]", path)
            if row_match:
                row_num = int(row_match.group(1))
                max_target_row = max(max_target_row, row_num)
        
        # Merge source rows into target
        merged_elements = []
        
        # First, add all target elements
        merged_elements.extend(target_elements)
        
        # Then, add source elements with updated paths and TableID
        for elem in source_elements:
            elem_copy = elem.copy()
            
            # Update TableID to target
            if "attributes" in elem_copy:
                elem_copy["attributes"] = elem_copy["attributes"].copy()
                elem_copy["attributes"]["TableID"] = target_table_id
            
            # Update path to continue row numbering from target
            path = elem_copy.get("Path", "")
            row_match = re.search(r"/TR\[(\d+)\]", path)
            
            if row_match:
                old_row_num = int(row_match.group(1))
                new_row_num = old_row_num + max_target_row
                
                # Replace row number in path
                new_path = re.sub(
                    r"/TR\[\d+\]",
                    f"/TR[{new_row_num}]",
                    path
                )
                elem_copy["Path"] = new_path
            
            merged_elements.append(elem_copy)
        
        self.logger.info(f"Merged table {source_table_id} (hash: {source_hash}) into table {target_table_id} (hash: {target_hash})")
        return merged_elements


def integrate_corrections_with_json_to_html(elements: List[Dict[str, Any]], 
                                           law_id: str, version: str,
                                           folder: str = "zhlex_files") -> List[Dict[str, Any]]:
    """
    Convenience function to apply corrections to elements.
    
    Args:
        elements: List of elements from JSON
        law_id: Law identifier
        version: Version number
        folder: Folder containing the law data
        
    Returns:
        Modified elements with corrections applied
    """
    applier = CorrectionApplier()
    modified_elements, _ = applier.apply_corrections(elements, law_id, version, folder)
    return modified_elements