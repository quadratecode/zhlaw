"""Category assignment for Fedlex laws based on SR numbers.

This module handles the assignment of hierarchical categories (folder, section,
subsection) to laws based on their SR numbers and a predefined hierarchy.

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import logging
import re
from typing import Optional, Tuple, Dict, Any
from pathlib import Path

from . import fedlex_config as config
from .fedlex_models import CategoryInfo, Category
from .fedlex_utils import load_json_file, is_international_law

logger = logging.getLogger(__name__)


class CategoryAssigner:
    """Assigns hierarchical categories to laws based on SR numbers."""
    
    def __init__(self, hierarchy_file: Path = config.HIERARCHY_FILE):
        """Initialize the category assigner.
        
        Args:
            hierarchy_file: Path to the hierarchy JSON file
        """
        self.hierarchy = self._load_hierarchy(hierarchy_file)
        self.hierarchy_loaded = self.hierarchy is not None
    
    def _load_hierarchy(self, hierarchy_file: Path) -> Optional[Dict[str, Any]]:
        """Load the category hierarchy from JSON file.
        
        Args:
            hierarchy_file: Path to hierarchy JSON file
            
        Returns:
            Hierarchy dictionary or None if failed
        """
        hierarchy = load_json_file(hierarchy_file)
        if hierarchy:
            logger.info("Successfully loaded category hierarchy")
        else:
            logger.error(f"Failed to load hierarchy from {hierarchy_file}")
        return hierarchy
    
    def derive_category_codes(self, sr_number: str) -> Tuple[str, str, Optional[str]]:
        """Derive folder, section, and subsection codes from SR number.
        
        Args:
            sr_number: SR notation (e.g., "101.1" or "0.123.456")
            
        Returns:
            Tuple of (folder_code, section_code, subsection_code)
        """
        folder_code = ""
        section_code = ""
        subsection_code = None
        
        if not sr_number or not re.match(config.SR_NUMBER_PATTERN, sr_number.strip()):
            logger.debug(f"Invalid SR number format: {sr_number}")
            return folder_code, section_code, subsection_code
        
        sr_number = sr_number.strip()
        is_intl = is_international_law(sr_number)
        
        if is_intl:
            # International law format: 0.XXX.YYY...
            parts = sr_number.split(".")
            if len(parts) >= 2 and parts[0] == "0" and parts[1].isdigit():
                digits = parts[1]
                num_digits = len(digits)
                
                if num_digits >= 1:
                    folder_code = f"0.{digits[0]}"
                if num_digits >= 2:
                    section_code = f"0.{digits[:2]}"
                if num_digits >= 3:
                    subsection_code = f"0.{digits[:3]}"
                
                # Prevent self-assignment
                if sr_number == folder_code:
                    section_code, subsection_code = "", None
                elif sr_number == section_code:
                    subsection_code = None
        else:
            # National law format: XXX.YYY...
            parts = sr_number.split(".")
            main_part = parts[0]
            
            if main_part.isdigit():
                num_digits = len(main_part)
                
                if num_digits >= 1:
                    folder_code = main_part[0]
                if num_digits >= 2:
                    section_code = main_part[:2]
                if num_digits >= 3:
                    subsection_code = main_part[:3]
                
                # Prevent self-assignment
                if sr_number == folder_code:
                    section_code, subsection_code = "", None
                elif sr_number == section_code:
                    subsection_code = None
                
                # Special case for exactly 3 digits
                if subsection_code == section_code and len(parts) == 1 and num_digits == 3:
                    subsection_code = None
        
        # Final safety check
        if subsection_code == section_code:
            subsection_code = None
        
        return folder_code, section_code, subsection_code
    
    def _find_category_details(self, code: str, level_dict: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict]]:
        """Look up category details in hierarchy.
        
        Args:
            code: Category code to find
            level_dict: Dictionary to search in
            
        Returns:
            Tuple of (name, item_dict) or (None, None)
        """
        if not isinstance(level_dict, dict) or not code:
            return None, None
        
        code_str = str(code).strip()
        if not code_str:
            return None, None
        
        item = level_dict.get(code_str)
        
        if item is None:
            logger.debug(f"Code '{code_str}' not found in keys: {list(level_dict.keys())}")
            return None, None
        
        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip(), item
            else:
                logger.debug(f"Found item for '{code_str}', but name is invalid: '{name}'")
                return None, None
        else:
            logger.debug(f"Found item for '{code_str}', but it's not a dictionary")
            return None, None
    
    def assign_category(self, sr_number: str) -> CategoryInfo:
        """Assign category information to a law based on SR number.
        
        Args:
            sr_number: SR notation
            
        Returns:
            CategoryInfo object with assigned categories
        """
        category_info = CategoryInfo()
        
        if not self.hierarchy_loaded or not sr_number:
            return category_info
        
        # Determine branch and derive codes
        is_intl = is_international_law(sr_number)
        branch = config.CATEGORY_BRANCH_INTERNATIONAL if is_intl else config.CATEGORY_BRANCH_NATIONAL
        folder_code, section_code, subsection_code = self.derive_category_codes(sr_number)
        
        logger.debug(f"Assigning category for {sr_number}: "
                    f"Codes=(F:'{folder_code}', S:'{section_code}', SS:'{subsection_code}') "
                    f"Branch='{branch}'")
        
        # Get folders dictionary for the branch
        folder_dict = self.hierarchy.get(branch, {}).get("folders")
        if not isinstance(folder_dict, dict):
            logger.debug(f"Branch '{branch}' has no 'folders' dictionary")
            return category_info
        
        # Find folder
        folder_name, folder_item = self._find_category_details(folder_code, folder_dict)
        if not folder_name or not folder_item:
            logger.debug(f"Folder '{folder_code}' not found")
            return category_info
        
        category_info.folder = Category(id=folder_code, name=folder_name)
        logger.debug(f"Found folder: {category_info.folder}")
        
        # Look for sections
        section_dict = folder_item.get("sections")
        subsection_dict = None
        
        if not isinstance(section_dict, dict):
            # Check for direct subsections
            logger.debug(f"Folder '{folder_code}' has no 'sections' dict")
            direct_subsection_dict = folder_item.get("subsections")
            if isinstance(direct_subsection_dict, dict):
                logger.debug(f"Folder '{folder_code}' has direct subsections")
                subsection_dict = direct_subsection_dict
                section_code = None  # Skip section level
            else:
                logger.debug(f"Folder '{folder_code}' has no valid sections or subsections")
                return category_info
        
        # Find section if applicable
        if section_code and isinstance(section_dict, dict):
            section_name, section_item = self._find_category_details(section_code, section_dict)
            
            if section_name and section_item:
                category_info.section = Category(id=section_code, name=section_name)
                logger.debug(f"Found section: {category_info.section}")
                
                # Prepare for subsection search
                subsection_dict = section_item.get("subsections")
                if not isinstance(subsection_dict, dict):
                    logger.debug(f"Section '{section_code}' has no 'subsections' dict")
                    subsection_dict = None
            else:
                logger.debug(f"Section '{section_code}' not found")
                return category_info
        
        # Find subsection if applicable
        if subsection_code and isinstance(subsection_dict, dict):
            subsection_name, _ = self._find_category_details(subsection_code, subsection_dict)
            
            if subsection_name:
                category_info.subsection = Category(id=subsection_code, name=subsection_name)
                logger.debug(f"Found subsection: {category_info.subsection}")
            else:
                logger.debug(f"Subsection '{subsection_code}' not found")
        
        return category_info
    
    def update_metadata_category(self, metadata: Dict[str, Any]) -> bool:
        """Update category in metadata dictionary.
        
        Args:
            metadata: Metadata dictionary to update
            
        Returns:
            True if category was updated
        """
        doc_info = metadata.get("doc_info", {})
        sr_number = doc_info.get("ordnungsnummer", "")
        
        if not sr_number:
            return False
        
        # Get current category
        old_category = doc_info.get("category", {})
        
        # Assign new category
        new_category_info = self.assign_category(sr_number)
        new_category = new_category_info.dict()
        
        # Update if changed
        doc_info["category"] = new_category
        
        # Check if actually changed
        return old_category != new_category