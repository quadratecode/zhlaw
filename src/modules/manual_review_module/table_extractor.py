"""
Table Extractor Module

Extracts and deduplicates tables across all versions of a law for manual review.
"""

import json
import hashlib
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import logging


class LawTableExtractor:
    """Extracts unique tables from all versions of a law for manual review."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def extract_tables_from_version(self, law_id: str, version: str, base_path: str) -> Dict[str, Any]:
        """
        Extract all tables from a specific version of a law.
        
        Args:
            law_id: The law identifier (e.g., "170.4")
            version: The version identifier (e.g., "118")
            base_path: Base path to the law files (e.g., "data/zhlex/zhlex_files_test")
            
        Returns:
            Dictionary of tables with their metadata (version-specific)
        """
        json_path = self._get_version_json_path(law_id, version, base_path)
        
        if not json_path or not Path(json_path).exists():
            self.logger.warning(f"JSON file not found for law {law_id} version {version}")
            return {}
        
        try:
            tables = self.extract_tables_from_json(json_path)
            version_tables = {}
            
            for table_id, table_data in tables.items():
                # Generate simple hash for this specific table
                table_hash = self.generate_table_hash(table_data['elements'])
                
                version_tables[table_hash] = {
                    'hash': table_hash,
                    'table_id': table_id,
                    'version': version,
                    'pages': table_data['pages'],
                    'pdf_path': self.get_pdf_path(json_path),
                    'source_link': self.get_source_link(json_path),
                    'original_structure': self.elements_to_table_structure(table_data['elements'])
                }
                
        except Exception as e:
            self.logger.error(f"Error processing law {law_id} version {version}: {e}")
            return {}
        
        return version_tables
    
    def _get_version_json_path(self, law_id: str, version: str, base_path: str) -> Optional[str]:
        """
        Get the JSON file path for a specific law version.
        
        Args:
            law_id: The law identifier
            version: The version identifier
            base_path: Base path to search in
            
        Returns:
            Path to the JSON file or None if not found
        """
        law_path = Path(base_path) / law_id / version
        
        if not law_path.exists():
            return None
            
        json_pattern = f"{law_id}-{version}-modified-updated.json"
        json_path = law_path / json_pattern
        
        if json_path.exists():
            return str(json_path)
        return None
    
    def find_law_versions(self, law_id: str, base_path: str) -> Dict[str, str]:
        """
        Find all versions of a law and their JSON file paths.
        
        Args:
            law_id: The law identifier
            base_path: Base path to search in
            
        Returns:
            Dictionary mapping version numbers to JSON file paths
        """
        law_path = Path(base_path) / law_id
        versions = {}
        
        if not law_path.exists():
            self.logger.warning(f"Law path does not exist: {law_path}")
            return versions
            
        for version_dir in law_path.iterdir():
            if version_dir.is_dir():
                # Look for modified-updated JSON file
                json_pattern = f"{law_id}-{version_dir.name}-modified-updated.json"
                json_path = version_dir / json_pattern
                
                if json_path.exists():
                    versions[version_dir.name] = str(json_path)
                    
        return versions
    
    def extract_tables_from_json(self, json_path: str) -> Dict[str, Dict[str, Any]]:
        """
        Extract table data from a JSON file.
        
        Args:
            json_path: Path to the JSON file
            
        Returns:
            Dictionary mapping table IDs to table data
        """
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self.logger.error(f"Error reading JSON file {json_path}: {e}")
            return {}
        
        tables = {}
        elements = data.get('elements', [])
        
        # Group elements by TableID
        table_elements = {}
        for element in elements:
            table_id = element.get('attributes', {}).get('TableID')
            if table_id is not None:
                if table_id not in table_elements:
                    table_elements[table_id] = []
                table_elements[table_id].append(element)
        
        # Process each table
        for table_id, elements_list in table_elements.items():
            pages = self.extract_page_numbers(elements_list)
            tables[table_id] = {
                'elements': elements_list,
                'pages': pages
            }
            
        return tables
    
    def extract_page_numbers(self, elements: List[Dict[str, Any]]) -> List[int]:
        """
        Extract page numbers from table elements.
        
        Args:
            elements: List of table elements
            
        Returns:
            List of unique page numbers
        """
        pages = set()
        for element in elements:
            page = element.get('Page')
            if page is not None:
                pages.add(page)
        return sorted(list(pages))
    
    def generate_table_hash(self, table_elements: List[Dict[str, Any]]) -> str:
        """
        Generate hash based ONLY on text content, not metadata.
        
        Args:
            table_elements: List of table elements
            
        Returns:
            Hash string (16 characters)
        """
        content = []
        for element in sorted(table_elements, key=lambda x: x.get('Path', '')):
            text = element.get('Text', '').strip()
            if text:
                content.append(text)
        
        content_str = '|'.join(content)
        return hashlib.sha256(content_str.encode('utf-8')).hexdigest()[:16]
    
    def elements_to_table_structure(self, elements: List[Dict[str, Any]]) -> List[List[str]]:
        """
        Convert table elements to a 2D array structure using Path information.
        
        Args:
            elements: List of table elements
            
        Returns:
            2D array representing the table structure
        """
        import re
        
        # Group elements by table row and cell
        table_cells = {}
        
        for element in elements:
            path = element.get('Path', '')
            text = element.get('Text', '').strip()
            
            if not text:
                continue
                
            # Extract row and cell indices from path
            # Path format: //Document/.../Table/TR[n]/TH[m]/... or //Document/.../Table/TR/TD[m]/...
            tr_match = re.search(r'/TR(?:\[(\d+)\])?', path)
            th_td_match = re.search(r'/T[HD](?:\[(\d+)\])?', path)
            
            if tr_match:
                # Row index (1-based in path, convert to 0-based)
                row_idx = int(tr_match.group(1)) - 1 if tr_match.group(1) else 0
                
                # Column index (1-based in path, convert to 0-based)
                col_idx = int(th_td_match.group(1)) - 1 if th_td_match and th_td_match.group(1) else 0
                
                if row_idx not in table_cells:
                    table_cells[row_idx] = {}
                if col_idx not in table_cells[row_idx]:
                    table_cells[row_idx][col_idx] = []
                    
                table_cells[row_idx][col_idx].append(text)
        
        # If path parsing didn't work, fall back to coordinate-based approach with better scaling
        if not table_cells:
            self.logger.warning("Path-based extraction failed, falling back to coordinate-based approach")
            return self._fallback_coordinate_based_structure(elements)
        
        # Build 2D array from grouped cells
        if not table_cells:
            return []
            
        max_row = max(table_cells.keys())
        max_col = max(max(row_cells.keys()) for row_cells in table_cells.values()) if table_cells else 0
        
        table_structure = []
        for row in range(max_row + 1):
            row_data = []
            for col in range(max_col + 1):
                if row in table_cells and col in table_cells[row]:
                    cell_text = ' '.join(table_cells[row][col]).strip()
                    row_data.append(cell_text)
                else:
                    row_data.append('')
            table_structure.append(row_data)
        
        return table_structure
    
    def _fallback_coordinate_based_structure(self, elements: List[Dict[str, Any]]) -> List[List[str]]:
        """
        Fallback method using coordinate-based clustering for table structure.
        
        Args:
            elements: List of table elements
            
        Returns:
            2D array representing the table structure
        """
        text_elements = [e for e in elements if e.get('Text', '').strip()]
        if not text_elements:
            return []
        
        # Extract Y coordinates and cluster them into rows
        y_coords = [e.get('Bounds', [0, 0, 0, 0])[1] for e in text_elements]
        y_coords = sorted(set(y_coords))
        
        # Group elements by Y coordinate (with tolerance)
        tolerance = 5.0  # Points tolerance for same row
        row_groups = []
        
        for y in y_coords:
            elements_in_row = [e for e in text_elements 
                             if abs(e.get('Bounds', [0, 0, 0, 0])[1] - y) <= tolerance]
            if elements_in_row:
                # Sort by X coordinate within the row
                elements_in_row.sort(key=lambda e: e.get('Bounds', [0, 0, 0, 0])[0])
                row_groups.append(elements_in_row)
        
        # Convert to 2D structure
        table_structure = []
        max_cols = max(len(row) for row in row_groups) if row_groups else 0
        
        for row_elements in row_groups:
            row_data = []
            for i in range(max_cols):
                if i < len(row_elements):
                    row_data.append(row_elements[i].get('Text', '').strip())
                else:
                    row_data.append('')
            table_structure.append(row_data)
        
        return table_structure
    
    def get_pdf_path(self, json_path: str) -> str:
        """
        Get the corresponding PDF path for a JSON file.
        
        Args:
            json_path: Path to the JSON file
            
        Returns:
            Path to the corresponding PDF file
        """
        json_path_obj = Path(json_path)
        json_name = json_path_obj.name
        
        # Convert from JSON name to PDF name
        # e.g., "170.4-118-modified-updated.json" -> "170.4-118-original.pdf"
        pdf_name = json_name.replace('-modified-updated.json', '-original.pdf')
        pdf_path = json_path_obj.parent / pdf_name
        
        return str(pdf_path)
    
    def get_source_link(self, json_path: str) -> str:
        """
        Get the source link from metadata.json file.
        
        Args:
            json_path: Path to the JSON file
            
        Returns:
            Source link URL or empty string if not found
        """
        json_path_obj = Path(json_path)
        json_name = json_path_obj.name
        
        # Extract law_id and version from filename
        # e.g., "170.4-118-modified-updated.json" -> law_id="170.4", version="118"
        parts = json_name.split('-')
        if len(parts) >= 2:
            law_id = parts[0]
            version = parts[1]
            metadata_filename = f"{law_id}-{version}-metadata.json"
        else:
            # Fallback to simple metadata.json if pattern doesn't match
            metadata_filename = 'metadata.json'
        
        metadata_path = json_path_obj.parent / metadata_filename
        
        if not metadata_path.exists():
            self.logger.warning(f"Metadata file not found: {metadata_path}")
            return ""
        
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            # Try to get the source URL from metadata
            doc_info = metadata.get('doc_info', {})
            # Prefer law_page_url, fallback to law_text_url
            source_link = doc_info.get('law_page_url', '') or doc_info.get('law_text_url', '')
            return source_link
            
        except Exception as e:
            self.logger.error(f"Error reading metadata file {metadata_path}: {e}")
            return ""
    
    def get_laws_in_folder(self, folder_path: str) -> List[str]:
        """
        Get all law IDs in a folder.
        
        Args:
            folder_path: Path to the folder containing laws
            
        Returns:
            List of law IDs
        """
        folder_path_obj = Path(folder_path)
        laws = []
        
        if not folder_path_obj.exists():
            self.logger.warning(f"Folder does not exist: {folder_path}")
            return laws
            
        for item in folder_path_obj.iterdir():
            if item.is_dir():
                laws.append(item.name)
                
        return sorted(laws)
    
    def extract_unique_tables_from_law(self, law_id: str, base_path: str) -> Dict[str, Any]:
        """
        DEPRECATED: Legacy method for backward compatibility.
        Extract all unique tables across all versions of a law.
        
        This method is kept for backward compatibility but should be replaced
        with extract_tables_from_version() for per-version processing.
        
        Args:
            law_id: The law identifier (e.g., "170.4")
            base_path: Base path to the law files (e.g., "data/zhlex/zhlex_files_test")
            
        Returns:
            Dictionary of unique tables with their metadata
        """
        versions = self.find_law_versions(law_id, base_path)
        unique_tables = {}
        
        for version, json_path in versions.items():
            try:
                tables = self.extract_tables_from_json(json_path)
                
                for table_id, table_data in tables.items():
                    # Generate content-only hash
                    table_hash = self.generate_table_hash(table_data['elements'])
                    
                    if table_hash not in unique_tables:
                        unique_tables[table_hash] = {
                            'hash': table_hash,
                            'found_in_versions': [version],
                            'pages': {version: table_data['pages']},
                            'pdf_paths': {version: self.get_pdf_path(json_path)},
                            'source_links': {version: self.get_source_link(json_path)},
                            'original_structure': self.elements_to_table_structure(table_data['elements'])
                        }
                    else:
                        # Add version to existing table
                        unique_tables[table_hash]['found_in_versions'].append(version)
                        unique_tables[table_hash]['pages'][version] = table_data['pages']
                        unique_tables[table_hash]['pdf_paths'][version] = self.get_pdf_path(json_path)
                        unique_tables[table_hash]['source_links'][version] = self.get_source_link(json_path)
                        
            except Exception as e:
                self.logger.error(f"Error processing version {version} of law {law_id}: {e}")
                continue
        
        return unique_tables