"""Version management for Fedlex laws.

This module handles version linking, finding missing versions, and updating
version relationships between different versions of the same law.

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import logging
import json
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
import re

from . import fedlex_config as config
from .fedlex_models import VersionSummary, VersionLinks, LawMetadata
from .fedlex_utils import (
    load_json_file, save_json_file, group_by_sr_number,
    find_metadata_files, parse_numeric_date
)

logger = logging.getLogger(__name__)


class VersionManager:
    """Manages version relationships and updates for Fedlex laws."""
    
    def __init__(self, base_dir: Path = config.BASE_FILES_DIR):
        """Initialize the version manager.
        
        Args:
            base_dir: Base directory containing law files
        """
        self.base_dir = base_dir
    
    def extract_version_summary(self, doc_info: Dict) -> VersionSummary:
        """Extract version summary from document info.
        
        Args:
            doc_info: Document info dictionary
            
        Returns:
            VersionSummary object
        """
        # Extract relevant fields
        summary_data = {
            "law_page_url": doc_info.get("law_page_url", ""),
            "law_text_url": doc_info.get("law_text_url", ""),
            "nachtragsnummer": doc_info.get("nachtragsnummer", ""),
            "numeric_nachtragsnummer": doc_info.get("numeric_nachtragsnummer"),
            "erlassdatum": doc_info.get("erlassdatum", ""),
            "inkraftsetzungsdatum": doc_info.get("inkraftsetzungsdatum", ""),
            "publikationsdatum": doc_info.get("publikationsdatum", ""),
            "aufhebungsdatum": doc_info.get("aufhebungsdatum", ""),
            "in_force": doc_info.get("in_force", False)
        }
        
        # Ensure numeric_nachtragsnummer is float or None
        try:
            if summary_data["numeric_nachtragsnummer"] is not None:
                summary_data["numeric_nachtragsnummer"] = float(
                    summary_data["numeric_nachtragsnummer"]
                )
        except (ValueError, TypeError):
            summary_data["numeric_nachtragsnummer"] = None
        
        return VersionSummary(**summary_data)
    
    def get_existing_versions(self, sr_number: str) -> Set[str]:
        """Get set of existing version dates for an SR number.
        
        Args:
            sr_number: SR notation
            
        Returns:
            Set of date strings (YYYYMMDD format)
        """
        sr_dir = self.base_dir / sr_number
        existing_dates = set()
        
        if sr_dir.exists() and sr_dir.is_dir():
            try:
                for date_dir in sr_dir.iterdir():
                    if (date_dir.is_dir() and 
                        re.fullmatch(config.DATE_FOLDER_PATTERN, date_dir.name)):
                        existing_dates.add(date_dir.name)
            except OSError as e:
                logger.error(f"Error listing directories in {sr_dir}: {e}")
        
        return existing_dates
    
    def update_version_links_for_group(self, file_paths: List[Path]) -> int:
        """Update older/newer version links for a group of files.
        
        Args:
            file_paths: List of metadata file paths for same SR number
            
        Returns:
            Number of files updated
        """
        if len(file_paths) <= 1:
            # Ensure single file has proper version structure
            if len(file_paths) == 1:
                self._ensure_version_structure(file_paths[0])
            return 0
        
        # Load all versions
        loaded_versions = []
        sr_number = None
        
        for file_path in file_paths:
            # Extract SR number from first valid path
            if not sr_number:
                match = re.search(r"([0-9.]+)-\d{8}-metadata\.json$", file_path.name)
                if match:
                    sr_number = match.group(1)
            
            # Load metadata
            data = load_json_file(file_path)
            if not data:
                continue
            
            doc_info = data.get("doc_info", {})
            if not isinstance(doc_info, dict):
                logger.warning(f"Invalid doc_info structure in {file_path}")
                continue
            
            # Get sort key
            num_n = doc_info.get("numeric_nachtragsnummer")
            try:
                sort_key = float(num_n) if num_n is not None else float("inf")
            except (ValueError, TypeError):
                sort_key = float("inf")
                logger.warning(f"Invalid numeric_nachtragsnummer '{num_n}' in {file_path}")
            
            # Extract version summary
            version_summary = self.extract_version_summary(doc_info)
            
            loaded_versions.append({
                "file_path": file_path,
                "full_data": data,
                "doc_info": doc_info,
                "sort_key": sort_key,
                "summary": version_summary
            })
        
        if not loaded_versions:
            logger.error(f"No valid version data loaded for {sr_number or 'unknown'}")
            return 0
        
        # Sort versions by date
        loaded_versions.sort(key=lambda x: (x["sort_key"], str(x["file_path"])))
        
        # Update version links
        update_count = 0
        for i, current in enumerate(loaded_versions):
            if current["sort_key"] == float("inf"):
                # Skip invalid versions
                current["doc_info"]["versions"] = {
                    "older_versions": [],
                    "newer_versions": []
                }
                current["needs_save"] = True
                continue
            
            older_versions = []
            newer_versions = []
            
            # Compare with other versions
            for j, other in enumerate(loaded_versions):
                if i == j or other["sort_key"] == float("inf"):
                    continue
                
                if other["sort_key"] < current["sort_key"]:
                    older_versions.append(other["summary"])
                elif other["sort_key"] > current["sort_key"]:
                    newer_versions.append(other["summary"])
            
            # Sort lists
            older_versions.sort(
                key=lambda x: x.numeric_nachtragsnummer or -1,
                reverse=True
            )
            newer_versions.sort(
                key=lambda x: x.numeric_nachtragsnummer or float("inf")
            )
            
            # Check if update needed
            new_versions = VersionLinks(
                older_versions=older_versions,
                newer_versions=newer_versions
            )
            
            old_versions_str = json.dumps(
                current["doc_info"].get("versions", {}),
                sort_keys=True
            )
            new_versions_str = json.dumps(new_versions.dict(), sort_keys=True)
            
            if old_versions_str != new_versions_str:
                current["doc_info"]["versions"] = new_versions.dict()
                current["needs_save"] = True
                update_count += 1
            else:
                current["needs_save"] = False
        
        # Save updated files
        if update_count > 0:
            logger.info(f"Updating version links in {update_count} files for {sr_number}")
            for version_info in loaded_versions:
                if version_info.get("needs_save"):
                    save_json_file(version_info["full_data"], version_info["file_path"])
        
        return update_count
    
    def _ensure_version_structure(self, file_path: Path):
        """Ensure a single file has proper version structure.
        
        Args:
            file_path: Path to metadata file
        """
        data = load_json_file(file_path)
        if not data:
            return
        
        doc_info = data.get("doc_info", {})
        versions_node = doc_info.get("versions")
        
        if (not isinstance(versions_node, dict) or
            "older_versions" not in versions_node or
            "newer_versions" not in versions_node):
            
            doc_info["versions"] = {
                "older_versions": [],
                "newer_versions": []
            }
            save_json_file(data, file_path)
    
    def update_all_version_links(self) -> Tuple[int, int]:
        """Update version links for all laws in the base directory.
        
        Returns:
            Tuple of (number of groups processed, total files updated)
        """
        # Find all metadata files
        all_files = find_metadata_files(self.base_dir)
        
        # Group by SR number
        groups = group_by_sr_number(all_files)
        
        logger.info(f"Found {len(groups)} law groups with {len(all_files)} total files")
        
        groups_processed = 0
        total_updated = 0
        
        for sr_number, file_paths in groups.items():
            groups_processed += 1
            
            # Log progress periodically
            if groups_processed % 50 == 0 or groups_processed == len(groups):
                logger.info(f"Processing version links: {groups_processed}/{len(groups)} "
                           f"(current: {sr_number})")
            
            # Update links for this group
            updated = self.update_version_links_for_group(file_paths)
            total_updated += updated
        
        logger.info(f"Version linking complete: {groups_processed} groups processed, "
                   f"{total_updated} files updated")
        
        return groups_processed, total_updated
    
    def find_missing_versions(self, all_versions: List[Dict], 
                             existing_dates: Set[str]) -> List[Dict]:
        """Find versions that exist in SPARQL but not locally.
        
        Args:
            all_versions: All versions from SPARQL query
            existing_dates: Set of dates already downloaded
            
        Returns:
            List of missing versions
        """
        missing = []
        seen_dates = set()
        
        for version in all_versions:
            date_str = version.get("date_applicability", "")
            
            if (date_str and 
                date_str not in existing_dates and 
                date_str not in seen_dates and
                version.get("file_url")):
                
                missing.append(version)
                seen_dates.add(date_str)
        
        return missing