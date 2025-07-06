"""
Correction Manager Module

Manages JSON-based table corrections for laws.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import logging

from src.modules.manual_review_module.validation import CorrectionValidator, CorrectionSafetyChecker


class CorrectionManager:
    """Manages table corrections for laws."""
    
    def __init__(self, base_path: str = "data/zhlex"):
        self.base_path = Path(base_path)
        self.logger = logging.getLogger(__name__)
        self.validator = CorrectionValidator()
        self.safety_checker = CorrectionSafetyChecker()
    
    def get_correction_file_path(self, law_id: str, version: str = None, folder: str = "zhlex_files_test") -> Path:
        """
        Get the path to a law's correction file.
        
        Args:
            law_id: The law identifier
            version: The version identifier (if None, uses legacy law-level path)
            folder: The folder name (zhlex_files_test or zhlex_files)
            
        Returns:
            Path to the correction file
        """
        if version is None:
            # Legacy path for backward compatibility
            return self.base_path / folder / law_id / f"{law_id}-table-corrections.json"
        else:
            # New per-version path
            return self.base_path / folder / law_id / version / f"{law_id}-{version}-table-corrections.json"
    
    def save_corrections(self, law_id: str, corrections: Dict[str, Any], version: str = None, folder: str = "zhlex_files_test") -> bool:
        """
        Save corrections for a law with validation.
        
        Args:
            law_id: The law identifier
            corrections: Dictionary of corrections
            version: The version identifier (if None, uses legacy law-level path)
            folder: The folder name
            
        Returns:
            True if successful, False otherwise
        """
        try:
            correction_file = self.get_correction_file_path(law_id, version, folder)
            
            # Ensure directory exists
            correction_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Prepare correction data
            correction_data = {
                "law_id": law_id,
                "reviewed_at": datetime.now().isoformat(),
                "reviewer": "user",
                "status": "completed",
                "tables": corrections
            }
            
            # Validate before saving
            is_valid, errors = self.validator.validate_correction_file(correction_data)
            if not is_valid:
                self.logger.error(f"Validation failed for law {law_id}: {errors}")
                # Try to sanitize the data
                self.logger.info("Attempting to sanitize correction data...")
                correction_data = self.validator.sanitize_correction_data(correction_data)
                
                # Re-validate
                is_valid, errors = self.validator.validate_correction_file(correction_data)
                if not is_valid:
                    self.logger.error(f"Sanitization failed. Cannot save corrections: {errors}")
                    return False
                else:
                    self.logger.info("Data sanitized successfully")
            
            # Save to file
            with open(correction_file, 'w', encoding='utf-8') as f:
                json.dump(correction_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Saved corrections for law {law_id} to {correction_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving corrections for law {law_id}: {e}")
            return False
    
    def get_corrections(self, law_id: str, version: str = None, folder: str = "zhlex_files_test") -> Optional[Dict[str, Any]]:
        """
        Get corrections for a law.
        
        Args:
            law_id: The law identifier
            version: The version identifier (if None, uses legacy law-level path)
            folder: The folder name
            
        Returns:
            Dictionary of corrections or None if not found
        """
        try:
            correction_file = self.get_correction_file_path(law_id, version, folder)
            
            if not correction_file.exists():
                return None
                
            with open(correction_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            return data
            
        except Exception as e:
            self.logger.error(f"Error reading corrections for law {law_id}: {e}")
            return None
    
    def is_law_completed(self, law_id: str, version: str = None, folder: str = "zhlex_files_test") -> bool:
        """
        Check if a law has been completed (has corrections).
        
        Args:
            law_id: The law identifier
            version: The version identifier (if None, uses legacy law-level path)
            folder: The folder name
            
        Returns:
            True if the law has been reviewed and completed
        """
        corrections = self.get_corrections(law_id, version, folder)
        return corrections is not None and corrections.get("status") == "completed"
    
    def validate_law_completion(self, law_id: str, folder: str = "zhlex_files_test") -> Tuple[bool, List[str]]:
        """
        Validate that all tables in a law have been properly decided.
        
        A law is considered complete only when ALL extracted tables have a status of:
        - confirmed_without_changes
        - confirmed_with_changes  
        - rejected
        - merged_with_* (any merge status)
        
        Tables with "undefined" status prevent completion.
        
        Args:
            law_id: The law identifier
            folder: The folder name
            
        Returns:
            Tuple of (is_complete, list_of_undecided_table_hashes)
        """
        from src.modules.manual_review_module.table_extractor import LawTableExtractor
        
        try:
            # Get all extracted tables for this law
            extractor = LawTableExtractor()
            folder_path = self.base_path / folder
            unique_tables = extractor.extract_unique_tables_from_law(law_id, str(folder_path))
            
            if not unique_tables:
                # No tables to review, law is complete
                return True, []
            
            # Get corrections for this law (legacy law-level corrections)
            corrections = self.get_corrections(law_id, None, folder)
            if not corrections:
                # No corrections exist, all tables are undecided
                return False, list(unique_tables.keys())
            
            tables_corrections = corrections.get("tables", {})
            undecided_tables = []
            
            # Check each extracted table
            for table_hash in unique_tables.keys():
                if table_hash not in tables_corrections:
                    # Table has no correction entry - undecided
                    undecided_tables.append(table_hash)
                else:
                    table_status = tables_corrections[table_hash].get("status", "undefined")
                    
                    # Check if status is a valid completion status
                    if table_status == "undefined":
                        undecided_tables.append(table_hash)
                    elif table_status in ["confirmed_without_changes", "confirmed_with_changes", "rejected"]:
                        # Valid completion status
                        continue
                    elif table_status.startswith("merged"):
                        # Merged tables count as processed
                        continue
                    else:
                        # Unknown/invalid status - treat as undecided
                        undecided_tables.append(table_hash)
                        self.logger.warning(f"Unknown table status '{table_status}' for table {table_hash} in law {law_id}")
            
            is_complete = len(undecided_tables) == 0
            return is_complete, undecided_tables
            
        except Exception as e:
            self.logger.error(f"Error validating completion for law {law_id}: {e}")
            return False, []
    
    def is_law_fully_completed(self, law_id: str, folder: str = "zhlex_files_test") -> bool:
        """
        Enhanced completion check that validates all tables have been decided.
        
        Args:
            law_id: The law identifier
            folder: The folder name
            
        Returns:
            True if the law is fully completed with all tables decided
        """
        is_complete, undecided_tables = self.validate_law_completion(law_id, folder)
        return is_complete
    
    def update_corrections_with_new_tables(self, law_id: str, folder: str = "zhlex_files_test") -> bool:
        """
        Update existing corrections to include any new tables discovered during extraction.
        New tables are added with "undefined" status, preserving existing corrections.
        
        Args:
            law_id: The law identifier
            folder: The folder name
            
        Returns:
            True if corrections were updated, False otherwise
        """
        from src.modules.manual_review_module.table_extractor import LawTableExtractor
        
        try:
            # Get all currently extracted tables
            extractor = LawTableExtractor()
            folder_path = self.base_path / folder
            unique_tables = extractor.extract_unique_tables_from_law(law_id, str(folder_path))
            
            if not unique_tables:
                # No tables found, nothing to update
                return True
            
            # Get existing corrections (legacy law-level)
            existing_corrections = self.get_corrections(law_id, None, folder)
            
            if not existing_corrections:
                # No existing corrections - let normal review process handle this
                self.logger.info(f"No existing corrections for law {law_id}, skipping update")
                return True
            
            existing_tables = existing_corrections.get("tables", {})
            new_tables_added = False
            
            # Check for new tables that don't have corrections yet
            for table_hash, table_data in unique_tables.items():
                if table_hash not in existing_tables:
                    # This is a new table - add it with undefined status
                    existing_tables[table_hash] = {
                        "hash": table_hash,
                        "status": "undefined",
                        "found_in_versions": table_data["found_in_versions"],
                        "pages": table_data["pages"],
                        "pdf_paths": table_data["pdf_paths"],
                        "source_links": table_data.get("source_links", {}),
                        "original_structure": table_data["original_structure"],
                        "added_date": datetime.now().isoformat(),
                        "reason": "Newly discovered table"
                    }
                    new_tables_added = True
                    self.logger.info(f"🆕 Added new table {table_hash[:8]}... to corrections for law {law_id} (preserving existing corrections)")
            
            # Save updated corrections if new tables were added
            if new_tables_added:
                success = self.save_corrections(law_id, existing_tables, folder)
                if success:
                    self.logger.info(f"Successfully updated corrections for law {law_id} with new tables")
                    return True
                else:
                    self.logger.error(f"Failed to save updated corrections for law {law_id}")
                    return False
            else:
                # No new tables found
                self.logger.debug(f"No new tables found for law {law_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error updating corrections for law {law_id}: {e}")
            return False
    
    def get_correction_status(self, law_id: str, folder: str = "zhlex_files_test") -> str:
        """
        Get the correction status for a law.
        
        Args:
            law_id: The law identifier
            folder: The folder name
            
        Returns:
            Status string: "not_started", "in_progress", "completed", or "error"
        """
        try:
            corrections = self.get_corrections(law_id, None, folder)
            if corrections is None:
                return "not_started"
                
            return corrections.get("status", "error")
        except Exception as e:
            self.logger.error(f"Error getting status for law {law_id}: {e}")
            return "error"
    
    def migrate_correction_file(self, law_id: str, folder: str = "zhlex_files_test") -> bool:
        """
        Migrate a correction file from legacy status system to new status system.
        
        Args:
            law_id: The law identifier
            folder: The folder name
            
        Returns:
            True if migration was successful or not needed, False if failed
        """
        try:
            corrections = self.get_corrections(law_id, None, folder)
            if not corrections:
                return True  # No file to migrate
            
            migrated = False
            tables = corrections.get("tables", {})
            
            for table_hash, table_data in tables.items():
                old_status = table_data.get("status", "")
                new_status = self._migrate_table_status(table_data)
                
                if new_status != old_status:
                    table_data["status"] = new_status
                    migrated = True
                    self.logger.info(f"Migrated table {table_hash} from '{old_status}' to '{new_status}'")
            
            if migrated:
                # Save the migrated file
                success = self.save_corrections(law_id, tables, folder)
                if success:
                    self.logger.info(f"Successfully migrated correction file for law {law_id}")
                    return True
                else:
                    self.logger.error(f"Failed to save migrated correction file for law {law_id}")
                    return False
            else:
                self.logger.debug(f"No migration needed for law {law_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error migrating correction file for law {law_id}: {e}")
            return False
    
    def _migrate_table_status(self, table_data: Dict[str, Any]) -> str:
        """
        Migrate a single table's status from legacy to new system.
        
        Args:
            table_data: The table correction data
            
        Returns:
            The new status string
        """
        status = table_data.get("status", "undefined")
        
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
                "corrected_structure" in table_data and 
                table_data["corrected_structure"] != table_data.get("original_structure", [])
            )
            if has_corrections:
                return "confirmed_with_changes"
            else:
                return "confirmed_without_changes"
                
        elif status == "edited":
            return "confirmed_with_changes"
        
        # Unknown status, default to undefined
        return "undefined"
    
    def get_progress_summary(self, folder: str = "zhlex_files_test") -> Dict[str, Any]:
        """
        Get a summary of correction progress for a folder.
        
        Args:
            folder: The folder name
            
        Returns:
            Dictionary containing progress statistics
        """
        folder_path = self.base_path / folder
        
        if not folder_path.exists():
            return {"error": f"Folder {folder} does not exist"}
        
        laws = [item.name for item in folder_path.iterdir() if item.is_dir()]
        
        progress = {
            "total_laws": len(laws),
            "completed": 0,
            "not_started": 0,
            "in_progress": 0,
            "error": 0,
            "laws_by_status": {
                "completed": [],
                "not_started": [],
                "in_progress": [],
                "error": []
            }
        }
        
        for law_id in laws:
            status = self.get_correction_status(law_id, folder)
            progress[status] += 1
            progress["laws_by_status"][status].append(law_id)
        
        return progress
    
    def apply_corrections_to_elements(self, elements: List[Dict[str, Any]], law_id: str, 
                                      version: str, folder: str = "zhlex_files_test") -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Apply corrections to table elements during build process with validation.
        
        Args:
            elements: List of elements from the JSON file
            law_id: The law identifier
            version: The version number
            folder: The folder name
            
        Returns:
            Tuple of (modified_elements, application_info)
        """
        application_info = {
            "tables_found": 0,
            "corrections_applied": 0,
            "errors": [],
            "warnings": []
        }
        
        try:
            corrections = self.get_corrections(law_id, None, folder)
            if not corrections:
                return elements, application_info  # No corrections available
            
            # Validate corrections before applying
            is_valid, errors = self.validator.validate_correction_file(corrections)
            if not is_valid:
                self.logger.error(f"Invalid corrections for law {law_id}: {errors}")
                application_info["errors"].extend(errors)
                return elements, application_info
            
            # Check safety
            is_safe, warnings = self.safety_checker.is_safe_to_apply(elements, corrections)
            if warnings:
                self.logger.warning(f"Safety warnings for law {law_id}: {warnings}")
                application_info["warnings"].extend(warnings)
            
            corrected_elements = []
            processed_table_ids = set()
            
            for element in elements:
                table_id = element.get("attributes", {}).get("TableID")
                
                if table_id is not None:
                    application_info["tables_found"] += 1
                    
                    # Skip if already processed
                    if table_id in processed_table_ids:
                        continue
                    
                    # Find all elements belonging to this table
                    table_elements = [e for e in elements if e.get("attributes", {}).get("TableID") == table_id]
                    
                    # Generate hash for this table
                    table_hash = self._generate_table_hash(table_elements)
                    
                    # Check for corrections
                    if table_hash in corrections.get('tables', {}):
                        correction = corrections['tables'][table_hash]
                        application_info["corrections_applied"] += 1
                        
                        if correction['status'] == 'rejected':
                            # Remove TableID to convert to paragraphs
                            for elem in table_elements:
                                elem_copy = elem.copy()
                                if 'attributes' in elem_copy and 'TableID' in elem_copy['attributes']:
                                    elem_copy['attributes'] = elem_copy['attributes'].copy()
                                    del elem_copy['attributes']['TableID']
                                corrected_elements.append(elem_copy)
                            
                        elif correction['status'] == 'confirmed':
                            # Keep as is
                            corrected_elements.extend(table_elements)
                            
                        elif correction['status'] == 'edited':
                            # Apply corrections from corrected_structure
                            edited_elements = self._apply_table_edits_to_elements(
                                table_elements, correction.get('corrected_structure', [])
                            )
                            corrected_elements.extend(edited_elements)
                            
                        elif correction['status'].startswith('merged_with_'):
                            # Handle merged tables - for now, keep as-is
                            corrected_elements.extend(table_elements)
                            application_info["warnings"].append(
                                f"Table merge not fully implemented for table {table_hash}"
                            )
                            
                        else:
                            # Unknown status, keep as-is
                            corrected_elements.extend(table_elements)
                            application_info["warnings"].append(
                                f"Unknown status '{correction['status']}' for table {table_hash}"
                            )
                        
                        processed_table_ids.add(table_id)
                    else:
                        # No correction for this table, keep as-is
                        corrected_elements.extend(table_elements)
                        processed_table_ids.add(table_id)
                else:
                    # Not a table element, keep as-is
                    corrected_elements.append(element)
            
            return corrected_elements, application_info
            
        except Exception as e:
            self.logger.error(f"Error applying corrections for law {law_id}: {e}")
            application_info["errors"].append(str(e))
            return elements, application_info
    
    def _generate_table_hash(self, table_elements: List[Dict[str, Any]]) -> str:
        """Generate hash for table elements (simplified version)."""
        import hashlib
        
        content = []
        for element in sorted(table_elements, key=lambda x: x.get('Path', '')):
            text = element.get('Text', '').strip()
            if text:
                content.append(text)
        
        content_str = '|'.join(content)
        return hashlib.sha256(content_str.encode('utf-8')).hexdigest()[:16]
    
    def _apply_table_edits_to_elements(self, table_elements: List[Dict[str, Any]], 
                                       corrected_structure: List[List[str]]) -> List[Dict[str, Any]]:
        """
        Apply table edits to a list of table elements.
        
        Args:
            table_elements: List of elements belonging to the table
            corrected_structure: The corrected 2D table structure
            
        Returns:
            List of edited elements
        """
        # Create a mapping from structure position to element
        position_to_element = {}
        
        # First, organize elements by their position in the table
        for element in table_elements:
            path = element.get('Path', '')
            # Extract row and cell information from path
            import re
            row_match = re.search(r'/TR\[(\d+)\]', path)
            cell_match = re.search(r'/T[HD]\[(\d+)\]', path)
            
            if row_match and cell_match and element.get('Text'):
                row_idx = int(row_match.group(1)) - 1  # Convert to 0-based
                cell_idx = int(cell_match.group(1)) - 1
                position_to_element[(row_idx, cell_idx)] = element
        
        # Apply corrections
        edited_elements = []
        for element in table_elements:
            element_copy = element.copy()
            
            # Find position of this element
            path = element.get('Path', '')
            row_match = re.search(r'/TR\[(\d+)\]', path)
            cell_match = re.search(r'/T[HD]\[(\d+)\]', path)
            
            if row_match and cell_match and element.get('Text'):
                row_idx = int(row_match.group(1)) - 1
                cell_idx = int(cell_match.group(1)) - 1
                
                # Check if we have a correction for this position
                if (row_idx < len(corrected_structure) and 
                    cell_idx < len(corrected_structure[row_idx])):
                    corrected_text = corrected_structure[row_idx][cell_idx]
                    if corrected_text != element['Text']:
                        element_copy['Text'] = corrected_text
                        self.logger.debug(f"Applied correction: '{element['Text']}' -> '{corrected_text}'")
            
            edited_elements.append(element_copy)
        
        return edited_elements
    
    def create_correction_file_for_version(self, law_id: str, version: str, tables: Dict[str, Any], folder: str = "zhlex_files_test") -> bool:
        """
        Create a new correction file for a specific version with tables in undefined status.
        
        Args:
            law_id: The law identifier
            version: The version identifier
            tables: Dictionary of extracted tables
            folder: The folder name
            
        Returns:
            True if successful, False otherwise
        """
        correction_file_path = self.get_correction_file_path(law_id, version, folder)
        
        # Don't overwrite existing correction files
        if correction_file_path.exists():
            self.logger.info(f"Correction file already exists for {law_id} version {version}, skipping creation")
            return True
        
        # Prepare tables with undefined status
        correction_tables = {}
        for table_hash, table_data in tables.items():
            correction_tables[table_hash] = {
                "hash": table_hash,
                "status": "undefined",
                "found_in_versions": [version],  # Must be a list for validation
                "pages": {version: table_data.get("pages", [])},  # Must be a dict with version keys
                "pdf_paths": {version: table_data.get("pdf_path", "")},
                "source_links": {version: table_data.get("source_link", "")},
                "original_structure": table_data.get("original_structure", []),
                "table_id": table_data.get("table_id"),
                "created_date": datetime.now().isoformat()
            }
        
        # Save correction file
        success = self.save_corrections(law_id, correction_tables, version, folder)
        if success:
            self.logger.info(f"Created correction file for {law_id} version {version} with {len(correction_tables)} tables")
        
        return success
    
    def delete_corrections(self, law_id: str, version: str = None, folder: str = "zhlex_files_test") -> bool:
        """
        Delete corrections for a law.
        
        Args:
            law_id: The law identifier
            version: The version identifier (if None, uses legacy law-level path)
            folder: The folder name
            
        Returns:
            True if successful, False otherwise
        """
        try:
            correction_file = self.get_correction_file_path(law_id, version, folder)
            
            if correction_file.exists():
                correction_file.unlink()
                self.logger.info(f"Deleted corrections for law {law_id}")
                return True
            else:
                self.logger.warning(f"No corrections found for law {law_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error deleting corrections for law {law_id}: {e}")
            return False
    
    def get_all_versions_with_corrections(self, folder: str = "zhlex_files_test") -> List[Tuple[str, str]]:
        """
        Get a list of all law versions that have correction files.
        
        Args:
            folder: The folder name
            
        Returns:
            List of tuples (law_id, version) that have corrections
        """
        folder_path = self.base_path / folder
        versions_with_corrections = []
        
        if not folder_path.exists():
            return versions_with_corrections
        
        # Look for all per-version correction files
        for law_dir in folder_path.iterdir():
            if law_dir.is_dir():
                for version_dir in law_dir.iterdir():
                    if version_dir.is_dir():
                        correction_file = version_dir / f"{law_dir.name}-{version_dir.name}-table-corrections.json"
                        if correction_file.exists():
                            versions_with_corrections.append((law_dir.name, version_dir.name))
        
        return sorted(versions_with_corrections)
    
    def get_all_laws_with_corrections(self, folder: str = "zhlex_files_test") -> List[str]:
        """
        Get a list of all laws that have correction files.
        
        Args:
            folder: The folder name
            
        Returns:
            List of law IDs that have corrections
        """
        folder_path = self.base_path / folder
        laws_with_corrections = []
        
        if not folder_path.exists():
            return laws_with_corrections
        
        # Look for legacy correction files AND new per-version files
        for law_dir in folder_path.iterdir():
            if law_dir.is_dir():
                # Check for legacy correction file
                legacy_correction_file = law_dir / f"{law_dir.name}-table-corrections.json"
                if legacy_correction_file.exists():
                    laws_with_corrections.append(law_dir.name)
                else:
                    # Check for any per-version correction files
                    has_version_corrections = False
                    for version_dir in law_dir.iterdir():
                        if version_dir.is_dir():
                            version_correction_file = version_dir / f"{law_dir.name}-{version_dir.name}-table-corrections.json"
                            if version_correction_file.exists():
                                has_version_corrections = True
                                break
                    if has_version_corrections:
                        laws_with_corrections.append(law_dir.name)
        
        return sorted(laws_with_corrections)
    
    def reset_all_corrections(self, folder: str = "zhlex_files_test") -> dict:
        """
        Reset all corrections in a folder, including per-version correction files.
        
        Args:
            folder: The folder name
            
        Returns:
            Dictionary with reset results
        """
        # Get all law IDs with any type of correction files
        laws_with_corrections = self.get_all_laws_with_corrections(folder)
        
        # Also get all per-version correction files
        versions_with_corrections = self.get_all_versions_with_corrections(folder)
        
        results = {
            "total_found": len(laws_with_corrections),
            "per_version_files_found": len(versions_with_corrections),
            "successfully_reset": 0,
            "failed": 0,
            "failed_laws": [],
            "reset_laws": []
        }
        
        # Track all files deleted for better reporting
        files_deleted = 0
        
        for law_id in laws_with_corrections:
            try:
                law_reset_success = True
                
                # Delete legacy law-level correction file if it exists
                legacy_success = self.delete_corrections(law_id, None, folder)
                if legacy_success:
                    files_deleted += 1
                
                # Delete all per-version correction files for this law
                law_versions = [v for l, v in versions_with_corrections if l == law_id]
                for version in law_versions:
                    version_success = self.delete_corrections(law_id, version, folder)
                    if version_success:
                        files_deleted += 1
                    else:
                        law_reset_success = False
                
                if law_reset_success or legacy_success or law_versions:
                    results["successfully_reset"] += 1
                    results["reset_laws"].append(law_id)
                else:
                    results["failed"] += 1
                    results["failed_laws"].append(law_id)
                    
            except Exception as e:
                results["failed"] += 1
                results["failed_laws"].append(law_id)
                self.logger.error(f"Error resetting corrections for {law_id}: {e}")
        
        results["files_deleted"] = files_deleted
        return results
    
    def reset_law_corrections(self, law_id: str, folder: str = "zhlex_files_test") -> dict:
        """
        Reset all corrections for a specific law (both legacy and per-version files).
        
        Args:
            law_id: The law identifier
            folder: The folder name
            
        Returns:
            Dictionary with reset results
        """
        results = {
            "law_id": law_id,
            "files_deleted": 0,
            "legacy_file_deleted": False,
            "version_files_deleted": 0,
            "success": False
        }
        
        try:
            # Delete legacy law-level correction file if it exists
            legacy_success = self.delete_corrections(law_id, None, folder)
            if legacy_success:
                results["files_deleted"] += 1
                results["legacy_file_deleted"] = True
            
            # Get all per-version correction files for this law
            all_versions = self.get_all_versions_with_corrections(folder)
            law_versions = [v for l, v in all_versions if l == law_id]
            
            # Delete all per-version correction files for this law
            for version in law_versions:
                version_success = self.delete_corrections(law_id, version, folder)
                if version_success:
                    results["files_deleted"] += 1
                    results["version_files_deleted"] += 1
            
            results["success"] = results["files_deleted"] > 0
            
        except Exception as e:
            self.logger.error(f"Error resetting corrections for law {law_id}: {e}")
            results["error"] = str(e)
        
        return results