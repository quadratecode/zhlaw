"""Metadata updater for Fedlex law files.

This module handles updating existing metadata files with additional information
such as dynamic URLs, aufhebungsdatum, in_force status, and categories.

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import json
from pathlib import Path
from typing import List, Dict, Set, Optional
import arrow

from . import fedlex_config as config
from .fedlex_utils import (
    load_json_file, save_json_file, extract_public_url,
    format_date, is_law_repealed
)
from .category_assigner import CategoryAssigner

from src.utils.logging_utils import get_module_logger
logger = get_module_logger(__name__)


class MetadataUpdater:
    """Updates metadata files with enriched information."""
    
    def __init__(self, category_assigner: Optional[CategoryAssigner] = None):
        """Initialize the metadata updater.
        
        Args:
            category_assigner: CategoryAssigner instance or None
        """
        self.category_assigner = category_assigner or CategoryAssigner()
    
    def update_dynamic_source(self, metadata: Dict) -> bool:
        """Update dynamic source URL in metadata.
        
        Args:
            metadata: Metadata dictionary
            
        Returns:
            True if updated
        """
        doc_info = metadata.get("doc_info", {})
        law_text_url = doc_info.get("law_text_url", "")
        current_source = doc_info.get("dynamic_source", "")
        
        new_source = extract_public_url(law_text_url)
        
        if current_source != new_source:
            doc_info["dynamic_source"] = new_source
            return True
        
        return False
    
    def update_aufhebungsdatum(self, metadata: Dict, 
                              aufhebungsdatum_cache: Dict[str, str]) -> bool:
        """Update aufhebungsdatum and in_force status.
        
        Args:
            metadata: Metadata dictionary
            aufhebungsdatum_cache: Cache of repeal dates by SR number
            
        Returns:
            True if updated
        """
        doc_info = metadata.get("doc_info", {})
        sr_number = doc_info.get("ordnungsnummer", "")
        
        if not sr_number:
            return False
        
        # Get values from cache
        auf_raw = aufhebungsdatum_cache.get(sr_number, "")
        auf_formatted = format_date(auf_raw)
        expected_in_force = not is_law_repealed(auf_formatted)
        
        # Get current values
        current_auf = doc_info.get("aufhebungsdatum", "")
        current_in_force = doc_info.get("in_force")
        
        # Check if update needed
        updated = False
        if current_auf != auf_formatted:
            doc_info["aufhebungsdatum"] = auf_formatted
            updated = True
        
        if current_in_force != expected_in_force:
            doc_info["in_force"] = expected_in_force
            updated = True
        
        return updated
    
    def update_process_timestamp(self, metadata: Dict):
        """Update process timestamp in metadata.
        
        Args:
            metadata: Metadata dictionary
        """
        if "process_steps" not in metadata or not isinstance(metadata.get("process_steps"), dict):
            logger.warning("Initializing missing 'process_steps' structure")
            metadata["process_steps"] = {
                "download": "",
                "process": arrow.now().format("YYYYMMDD-HHmmss")
            }
        else:
            metadata["process_steps"]["process"] = arrow.now().format("YYYYMMDD-HHmmss")
            # Ensure download exists
            if "download" not in metadata["process_steps"]:
                metadata["process_steps"]["download"] = ""
    
    def update_metadata_file(self, file_path: Path, 
                           aufhebungsdatum_cache: Dict[str, str]) -> Optional[str]:
        """Update a single metadata file.
        
        Args:
            file_path: Path to metadata file
            aufhebungsdatum_cache: Cache of repeal dates
            
        Returns:
            SR number if file was updated, None otherwise
        """
        # Load metadata
        metadata = load_json_file(file_path)
        if not metadata:
            return None
        
        doc_info = metadata.get("doc_info")
        if not isinstance(doc_info, dict):
            logger.error(f"Invalid metadata structure in {file_path}")
            return None
        
        sr_number = doc_info.get("ordnungsnummer", "")
        if not sr_number:
            logger.warning(f"Missing ordnungsnummer in {file_path}")
            return None
        
        # Track changes
        change_reasons = []
        
        # Update dynamic source
        if self.update_dynamic_source(metadata):
            change_reasons.append("dynamic_source")
        
        # Update aufhebungsdatum
        if self.update_aufhebungsdatum(metadata, aufhebungsdatum_cache):
            change_reasons.append("aufhebungsdatum/in_force")
        
        # Update category
        if self.category_assigner.update_metadata_category(metadata):
            change_reasons.append("category")
        
        # Save if changed
        if change_reasons:
            logger.info(f"Updating {file_path}: {', '.join(change_reasons)}")
            self.update_process_timestamp(metadata)
            
            if save_json_file(metadata, file_path):
                return sr_number
            else:
                logger.error(f"Failed to save updated metadata to {file_path}")
                return None
        
        return None
    
    def update_metadata_batch(self, file_paths: List[Path],
                            aufhebungsdatum_cache: Dict[str, str]) -> Set[str]:
        """Update a batch of metadata files.
        
        Args:
            file_paths: List of metadata file paths
            aufhebungsdatum_cache: Cache of repeal dates
            
        Returns:
            Set of SR numbers that were updated
        """
        updated_srs = set()
        
        for file_path in file_paths:
            sr_number = self.update_metadata_file(file_path, aufhebungsdatum_cache)
            if sr_number:
                updated_srs.add(sr_number)
        
        if updated_srs:
            logger.info(f"Updated {len(updated_srs)} unique SR numbers in batch")
        
        return updated_srs
    
    def update_existing_aufhebungsdatum(self, sr_number: str, base_dir: Path,
                                      aufhebungsdatum: str) -> bool:
        """Update aufhebungsdatum in all existing metadata files for an SR number.
        
        This is used when a law is repealed after versions were already downloaded.
        
        Args:
            sr_number: SR notation
            base_dir: Base directory containing law files
            aufhebungsdatum: Formatted repeal date
            
        Returns:
            True if any files were updated
        """
        sr_dir = base_dir / sr_number
        if not sr_dir.exists():
            return False
        
        updated = False
        auf_formatted = format_date(aufhebungsdatum)
        expected_in_force = not is_law_repealed(auf_formatted)
        
        # Find all metadata files for this SR
        for date_dir in sr_dir.iterdir():
            if not date_dir.is_dir():
                continue
            
            metadata_file = date_dir / f"{sr_number}-{date_dir.name}-metadata.json"
            if not metadata_file.exists():
                continue
            
            # Load and check metadata
            metadata = load_json_file(metadata_file)
            if not metadata:
                continue
            
            doc_info = metadata.get("doc_info", {})
            current_auf = doc_info.get("aufhebungsdatum", "")
            current_in_force = doc_info.get("in_force")
            
            # Update if needed
            if current_auf != auf_formatted or current_in_force != expected_in_force:
                doc_info["aufhebungsdatum"] = auf_formatted
                doc_info["in_force"] = expected_in_force
                
                if save_json_file(metadata, metadata_file):
                    updated = True
                    logger.debug(f"Updated aufhebungsdatum in {metadata_file}")
        
        return updated