"""
Validation Module for Table Corrections

Provides robust validation and error handling for table correction data.
"""

import json
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path
import logging


class CorrectionValidator:
    """Validates table correction data for consistency and correctness."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def validate_correction_file(self, correction_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate a complete correction file structure.
        
        Args:
            correction_data: The correction data to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check required top-level fields
        required_fields = ['law_id', 'reviewed_at', 'reviewer', 'status', 'tables']
        for field in required_fields:
            if field not in correction_data:
                errors.append(f"Missing required field: {field}")
        
        # Validate law_id
        if 'law_id' in correction_data:
            if not isinstance(correction_data['law_id'], str) or not correction_data['law_id']:
                errors.append("law_id must be a non-empty string")
        
        # Validate status
        if 'status' in correction_data:
            valid_statuses = ['completed', 'in_progress', 'not_started']
            if correction_data['status'] not in valid_statuses:
                errors.append(f"Invalid status: {correction_data['status']}. Must be one of {valid_statuses}")
        
        # Validate tables
        if 'tables' in correction_data:
            if not isinstance(correction_data['tables'], dict):
                errors.append("tables must be a dictionary")
            else:
                # Validate each table
                for table_hash, table_data in correction_data['tables'].items():
                    table_errors = self._validate_table_correction(table_hash, table_data)
                    errors.extend(table_errors)
        
        return len(errors) == 0, errors
    
    def _validate_table_correction(self, table_hash: str, table_data: Dict[str, Any]) -> List[str]:
        """
        Validate a single table correction.
        
        Args:
            table_hash: The table hash
            table_data: The table correction data
            
        Returns:
            List of validation errors
        """
        errors = []
        prefix = f"Table {table_hash}: "
        
        # Check required fields
        required_fields = ['hash', 'status', 'found_in_versions', 'pages']
        for field in required_fields:
            if field not in table_data:
                errors.append(f"{prefix}Missing required field: {field}")
        
        # Validate hash matches
        if 'hash' in table_data and table_data['hash'] != table_hash:
            errors.append(f"{prefix}Hash mismatch: key={table_hash}, data={table_data['hash']}")
        
        # Validate status
        if 'status' in table_data:
            # New status system
            new_valid_statuses = ['undefined', 'confirmed_without_changes', 'confirmed_with_changes', 'rejected']
            # Legacy status system (for backward compatibility)
            legacy_valid_statuses = ['confirmed', 'rejected', 'edited', 'pending']
            
            status = table_data['status']
            is_valid_status = (
                status in new_valid_statuses or 
                status in legacy_valid_statuses or 
                status.startswith('merged_with_')
            )
            
            if not is_valid_status:
                errors.append(f"{prefix}Invalid status: {status}. Must be one of {new_valid_statuses + legacy_valid_statuses} or 'merged_with_*'")
        
        # Validate status-specific requirements
        status = table_data.get('status', '')
        
        # New status system validation
        if status == 'confirmed_with_changes':
            if 'corrected_structure' not in table_data:
                errors.append(f"{prefix}Status 'confirmed_with_changes' requires corrected_structure")
            if 'original_structure' not in table_data:
                errors.append(f"{prefix}Status 'confirmed_with_changes' requires original_structure")
                
        elif status == 'confirmed_without_changes':
            if 'corrected_structure' in table_data:
                # Check if corrected_structure is actually different from original
                original = table_data.get('original_structure', [])
                corrected = table_data.get('corrected_structure', [])
                if original != corrected:
                    errors.append(f"{prefix}Status 'confirmed_without_changes' should not have different corrected_structure")
            if 'original_structure' not in table_data:
                errors.append(f"{prefix}Status 'confirmed_without_changes' requires original_structure")
                
        # Legacy status system validation (for backward compatibility)
        elif status == 'edited':
            if 'corrected_structure' not in table_data:
                errors.append(f"{prefix}Legacy status 'edited' requires corrected_structure")
            if 'original_structure' not in table_data:
                errors.append(f"{prefix}Legacy status 'edited' requires original_structure")
                
        # Validate structure consistency when both exist
        if 'original_structure' in table_data and 'corrected_structure' in table_data:
            orig_structure = table_data.get('original_structure', [])
            corr_structure = table_data.get('corrected_structure', [])
            
            if orig_structure and corr_structure:
                orig_rows = len(orig_structure)
                corr_rows = len(corr_structure)
                
                # For now, we allow different row counts (e.g., splitting rows)
                # but validate that both are valid table structures
                orig_valid, orig_errors = self.validate_table_structure(orig_structure)
                corr_valid, corr_errors = self.validate_table_structure(corr_structure)
                
                if not orig_valid:
                    errors.extend([f"{prefix}Invalid original_structure: {err}" for err in orig_errors])
                if not corr_valid:
                    errors.extend([f"{prefix}Invalid corrected_structure: {err}" for err in corr_errors])
        
        # Validate merged tables
        if table_data.get('status', '').startswith('merged_with_'):
            target_hash = table_data['status'].replace('merged_with_', '')
            if not target_hash:
                errors.append(f"{prefix}Invalid merge target in status")
        
        # Validate found_in_versions
        if 'found_in_versions' in table_data:
            if not isinstance(table_data['found_in_versions'], list):
                errors.append(f"{prefix}found_in_versions must be a list")
            elif not table_data['found_in_versions']:
                errors.append(f"{prefix}found_in_versions cannot be empty")
        
        # Validate pages structure
        if 'pages' in table_data:
            if not isinstance(table_data['pages'], dict):
                errors.append(f"{prefix}pages must be a dictionary")
            else:
                # Check pages match found_in_versions
                if 'found_in_versions' in table_data:
                    for version in table_data['found_in_versions']:
                        if version not in table_data['pages']:
                            errors.append(f"{prefix}Missing page info for version {version}")
        
        return errors
    
    def validate_table_structure(self, structure: List[List[str]]) -> Tuple[bool, List[str]]:
        """
        Validate a table structure (2D array).
        
        Args:
            structure: The table structure to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        if not isinstance(structure, list):
            errors.append("Table structure must be a list")
            return False, errors
        
        if not structure:
            errors.append("Table structure cannot be empty")
            return False, errors
        
        # Check each row
        column_counts = []
        for i, row in enumerate(structure):
            if not isinstance(row, list):
                errors.append(f"Row {i} must be a list")
                continue
            
            column_counts.append(len(row))
            
            # Check each cell
            for j, cell in enumerate(row):
                if not isinstance(cell, str):
                    errors.append(f"Cell [{i}][{j}] must be a string")
        
        # Check for consistent column count
        if column_counts and len(set(column_counts)) > 1:
            errors.append(f"Inconsistent column counts: {column_counts}")
        
        return len(errors) == 0, errors
    
    def validate_correction_compatibility(self, original_elements: List[Dict[str, Any]], 
                                        correction_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate that corrections are compatible with the original elements.
        
        Args:
            original_elements: Original elements from JSON
            correction_data: Correction data to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Extract table IDs from original elements
        original_table_ids = set()
        for element in original_elements:
            table_id = element.get('attributes', {}).get('TableID')
            if table_id is not None:
                original_table_ids.add(table_id)
        
        # Check if corrections reference non-existent tables
        # This would require computing hashes of original tables
        # For now, just check basic compatibility
        
        if not original_table_ids and correction_data.get('tables'):
            errors.append("Corrections exist but no tables found in original elements")
        
        return len(errors) == 0, errors
    
    def sanitize_correction_data(self, correction_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize correction data by removing invalid entries and fixing common issues.
        
        Args:
            correction_data: The correction data to sanitize
            
        Returns:
            Sanitized correction data
        """
        sanitized = correction_data.copy()
        
        # Ensure all required fields exist
        if 'tables' not in sanitized:
            sanitized['tables'] = {}
        
        # Sanitize each table
        tables_to_remove = []
        for table_hash, table_data in sanitized['tables'].items():
            # Fix common issues
            if 'status' not in table_data:
                table_data['status'] = 'pending'
            
            # Remove invalid tables
            if not isinstance(table_data, dict):
                tables_to_remove.append(table_hash)
                continue
            
            # Ensure required fields
            if 'hash' not in table_data:
                table_data['hash'] = table_hash
            
            if 'found_in_versions' not in table_data:
                table_data['found_in_versions'] = []
            
            if 'pages' not in table_data:
                table_data['pages'] = {}
        
        # Remove invalid tables
        for table_hash in tables_to_remove:
            del sanitized['tables'][table_hash]
            self.logger.warning(f"Removed invalid table: {table_hash}")
        
        return sanitized


class CorrectionSafetyChecker:
    """Checks corrections for safety before applying them."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def is_safe_to_apply(self, elements: List[Dict[str, Any]], 
                        corrections: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Check if corrections are safe to apply to elements.
        
        Args:
            elements: Original elements
            corrections: Corrections to apply
            
        Returns:
            Tuple of (is_safe, list_of_warnings)
        """
        warnings = []
        
        # Check for potential data loss
        table_count = sum(1 for e in elements if e.get('attributes', {}).get('TableID') is not None)
        rejected_count = sum(1 for t in corrections.get('tables', {}).values() 
                           if t.get('status') == 'rejected')
        
        if rejected_count > 0:
            warnings.append(f"{rejected_count} tables will be converted to paragraphs")
        
        if rejected_count == table_count and table_count > 0:
            warnings.append("WARNING: All tables will be rejected!")
        
        # Check for merge operations
        merge_count = sum(1 for t in corrections.get('tables', {}).values()
                         if t.get('status', '').startswith('merged_with_'))
        if merge_count > 0:
            warnings.append(f"{merge_count} tables will be merged")
        
        # Always consider it safe but return warnings
        return True, warnings


def validate_json_file(file_path: str) -> Tuple[bool, List[str]]:
    """
    Validate a JSON file can be loaded and parsed.
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, dict):
            errors.append("JSON root must be a dictionary")
            
    except FileNotFoundError:
        errors.append(f"File not found: {file_path}")
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON: {e}")
    except Exception as e:
        errors.append(f"Error reading file: {e}")
    
    return len(errors) == 0, errors