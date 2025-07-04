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
    
    def _normalize_status(self, correction: Dict[str, Any]) -> str:
        """
        Normalize legacy status values to the new status system.
        
        New status system:
        - undefined: User must make a selection
        - confirmed_without_changes: Table is correctly converted, no editing needed
        - confirmed_with_changes: Table is a table, but edits are needed
        - rejected: Table is not a table and should not be treated as such
        
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
                self.logger.info(f"Migrating legacy status 'confirmed' to 'confirmed_with_changes' for table {correction.get('hash', 'unknown')}")
                return "confirmed_with_changes"
            else:
                self.logger.info(f"Migrating legacy status 'confirmed' to 'confirmed_without_changes' for table {correction.get('hash', 'unknown')}")
                return "confirmed_without_changes"
                
        elif status == "edited":
            self.logger.info(f"Migrating legacy status 'edited' to 'confirmed_with_changes' for table {correction.get('hash', 'unknown')}")
            return "confirmed_with_changes"
        
        # Unknown status, default to undefined
        self.logger.warning(f"Unknown status '{status}' for table {correction.get('hash', 'unknown')}, defaulting to 'undefined'")
        return "undefined"
    
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
            "undefined": 0,
            "confirmed_without_changes": 0,
            "confirmed_with_changes": 0,
            "rejected": 0,
            "merged": 0,
            # Keep legacy counters for backward compatibility reporting
            "legacy_confirmed": 0,
            "legacy_edited": 0
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
                    original_status = correction.get("status", "undefined")
                    normalized_status = self._normalize_status(correction)
                    
                    # Track legacy statuses for reporting
                    if original_status == "confirmed":
                        corrections_applied["legacy_confirmed"] += 1
                    elif original_status == "edited":
                        corrections_applied["legacy_edited"] += 1
                    
                    if normalized_status == "undefined":
                        # No decision made, keep original table structure
                        corrections_applied["undefined"] += 1
                        modified_elements.extend(
                            self._get_table_elements(elements, table_info[table_id]["indices"])
                        )
                        processed_table_ids.add(table_id)
                        self.logger.debug(f"Table {table_hash} has undefined status, keeping original structure")
                        
                    elif normalized_status == "confirmed_without_changes":
                        # Table is correct as-is, keep original structure
                        corrections_applied["confirmed_without_changes"] += 1
                        modified_elements.extend(
                            self._get_table_elements(elements, table_info[table_id]["indices"])
                        )
                        processed_table_ids.add(table_id)
                        self.logger.debug(f"Table {table_hash} confirmed without changes")
                        
                    elif normalized_status == "confirmed_with_changes":
                        # Table structure needs corrections, apply them
                        corrections_applied["confirmed_with_changes"] += 1
                        corrected_structure = correction.get("corrected_structure", [])
                        if corrected_structure:
                            modified_elements.extend(
                                self._edit_table(elements, table_id, table_info[table_id]["indices"],
                                               corrected_structure)
                            )
                            self.logger.debug(f"Table {table_hash} confirmed with changes applied")
                        else:
                            self.logger.warning(f"Table {table_hash} marked as 'confirmed_with_changes' but no corrected_structure found, keeping original")
                            modified_elements.extend(
                                self._get_table_elements(elements, table_info[table_id]["indices"])
                            )
                        processed_table_ids.add(table_id)
                        
                    elif normalized_status == "rejected":
                        # Not a table, convert to regular paragraphs
                        corrections_applied["rejected"] += 1
                        modified_elements.extend(
                            self._reject_table(elements, table_id, table_info[table_id]["indices"])
                        )
                        processed_table_ids.add(table_id)
                        self.logger.debug(f"Table {table_hash} rejected and converted to paragraphs")
                        
                    elif normalized_status.startswith("merged_with_"):
                        # Handle table merging (unchanged logic)
                        corrections_applied["merged"] += 1
                        target_hash = normalized_status.replace("merged_with_", "")
                        
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
                                self.logger.debug(f"Table {table_hash} merged with {target_hash}")
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
                        # Unknown status, default to keeping original
                        self.logger.warning(f"Unknown normalized status '{normalized_status}' for table {table_hash}, keeping original")
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
        
        This method reconstructs the entire table structure based on the corrected
        structure, creating new elements as needed.
        """
        if not corrected_structure:
            # No corrected structure, return original elements
            return self._get_table_elements(elements, indices)
        
        # Get all table elements
        table_elements = self._get_table_elements(elements, indices)
        if not table_elements:
            return []
        
        # Analyze original table structure to get column positions
        column_bounds = self._analyze_column_positions(table_elements)
        
        # Find a suitable template element (prefer header elements)
        template_element = None
        for elem in table_elements:
            if "/TH" in elem.get("Path", ""):
                template_element = elem.copy()
                break
        if template_element is None:
            template_element = table_elements[0].copy()
        
        # Reconstruct the table with corrected structure
        edited_elements = []
        
        for row_idx, row in enumerate(corrected_structure):
            for col_idx, cell_text in enumerate(row):
                # Create element for this cell
                element = {}
                
                # Copy basic structure from template
                for key in template_element:
                    if key not in ["Text", "Path", "Bounds", "CharBounds"]:
                        element[key] = template_element[key]
                
                # Set the text content - preserve empty strings for empty cells
                element["Text"] = cell_text
                
                # Update the path to reflect the correct position
                # Use 1-based indexing for consistency with Adobe Extract format
                if row_idx == 0:
                    # Header row
                    element["Path"] = f"//Document/Table/TR/TH[{col_idx + 1}]/P"
                else:
                    # Data row
                    element["Path"] = f"//Document/Table/TR[{row_idx + 1}]/TD[{col_idx + 1}]/P"
                
                # Ensure TableID is preserved
                if "attributes" not in element:
                    element["attributes"] = {}
                element["attributes"]["TableID"] = table_id
                
                # Set bounds based on column positions
                if "Bounds" in template_element and col_idx < len(column_bounds):
                    # Use the analyzed column positions
                    col_info = column_bounds[col_idx]
                    
                    # Get row height from template or calculate
                    if len(template_element["Bounds"]) >= 4:
                        _, template_y, _, template_y2 = template_element["Bounds"][:4]
                        row_height = abs(template_y2 - template_y)
                        
                        # Calculate Y position based on row
                        y1 = template_y + (row_idx * row_height * 1.1)  # 1.1 for spacing
                        y2 = y1 + row_height
                        
                        # Use column bounds for X positions
                        element["Bounds"] = [col_info["left"], y1, col_info["right"], y2]
                        
                        # Copy additional bounds data if present
                        if len(template_element["Bounds"]) > 4:
                            element["Bounds"].extend(template_element["Bounds"][4:])
                
                edited_elements.append(element)
        
        self.logger.debug(f"Reconstructed table {table_id}: {len(table_elements)} -> {len(edited_elements)} elements")
        return edited_elements
    
    def _analyze_column_positions(self, table_elements: List[Dict[str, Any]]) -> List[Dict[str, float]]:
        """
        Analyze the original table elements to determine column positions.
        
        Returns a list of column bounds info: [{"left": x1, "right": x2}, ...]
        """
        # Find header row elements to determine columns
        header_elements = []
        for elem in table_elements:
            if "/TH" in elem.get("Path", "") and "Bounds" in elem:
                header_elements.append(elem)
        
        # If no headers found, use first row elements
        if not header_elements:
            # Find elements from first row
            import re
            min_row = float('inf')
            for elem in table_elements:
                match = re.search(r"/TR\[?(\d+)\]?", elem.get("Path", ""))
                if match:
                    row_num = int(match.group(1))
                    min_row = min(min_row, row_num)
            
            for elem in table_elements:
                if f"/TR[{min_row}]" in elem.get("Path", "") or f"/TR/{min_row}" in elem.get("Path", ""):
                    header_elements.append(elem)
        
        # Sort by X position
        header_elements.sort(key=lambda e: e.get("Bounds", [0])[0])
        
        # Extract column bounds
        column_bounds = []
        for elem in header_elements:
            if "Bounds" in elem and len(elem["Bounds"]) >= 4:
                x1, _, x2, _ = elem["Bounds"][:4]
                column_bounds.append({"left": x1, "right": x2})
        
        # If we couldn't determine columns, create default positions
        if not column_bounds:
            # Assume 2 columns with equal width
            default_left = 50
            default_width = 250
            column_bounds = [
                {"left": default_left, "right": default_left + default_width},
                {"left": default_left + default_width + 10, "right": default_left + 2 * default_width + 10}
            ]
        
        return column_bounds
    
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