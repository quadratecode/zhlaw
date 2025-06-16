"""
Generate anchor maps for laws to enable dynamic linking to the latest version of provisions.
"""

import json
import os
import re
from pathlib import Path
from bs4 import BeautifulSoup
from typing import Dict, List, Set, Tuple, Optional
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

logger = logging.getLogger(__name__)


class AnchorMapGenerator:
    """Generate anchor maps for law collections."""
    
    def __init__(self, public_dir: str, collection: str, collection_data: Optional[List[Dict]] = None):
        """
        Initialize the anchor map generator.
        
        Args:
            public_dir: Path to the public directory
            collection: Collection name ('col-zh' or 'col-ch')
            collection_data: Optional collection metadata from processed JSON
        """
        self.public_dir = Path(public_dir)
        self.collection = collection
        self.collection_dir = self.public_dir / collection
        self.anchor_maps_dir = self.public_dir / "anchor-maps" / collection.replace("col-", "")
        
        # Ensure anchor maps directory exists
        self.anchor_maps_dir.mkdir(parents=True, exist_ok=True)
        
        # Pattern to match law files: ordnungsnummer-nachtragsnummer.html
        self.law_file_pattern = re.compile(r'^([\d.]+)-(\d+)\.html$')
        
        # Pattern to extract provision/subprovision from anchor IDs
        self.anchor_pattern = re.compile(r'seq-\d+-prov-(\d+[a-z]?)(?:-sub-(\d+))?')
        
        # Create metadata lookup dictionary if collection data provided
        self.metadata_lookup = {}
        if collection_data:
            for law in collection_data:
                self.metadata_lookup[law['ordnungsnummer']] = {
                    'title': law.get('erlasstitel', ''),
                    'abbreviation': law.get('abkuerzung', '')
                }
    
    def generate_all_maps(self, concurrent: bool = True, max_workers: int = 10) -> None:
        """
        Generate anchor maps for all laws in the collection.
        
        Args:
            concurrent: Whether to process laws concurrently
            max_workers: Maximum number of concurrent workers
        """
        # Group files by ordnungsnummer
        laws_by_ordnungsnummer = self._group_laws_by_ordnungsnummer()
        
        if not laws_by_ordnungsnummer:
            logger.warning(f"No law files found in {self.collection_dir}")
            return
        
        logger.info(f"Generating anchor maps for {len(laws_by_ordnungsnummer)} laws in {self.collection}")
        
        if concurrent:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(self._generate_map_for_law, ordnungsnummer, files): ordnungsnummer
                    for ordnungsnummer, files in laws_by_ordnungsnummer.items()
                }
                
                for future in as_completed(futures):
                    ordnungsnummer = futures[future]
                    try:
                        future.result()
                    except Exception as e:
                        logger.error(f"Error generating map for {ordnungsnummer}: {e}")
        else:
            for ordnungsnummer, files in laws_by_ordnungsnummer.items():
                try:
                    self._generate_map_for_law(ordnungsnummer, files)
                except Exception as e:
                    logger.error(f"Error generating map for {ordnungsnummer}: {e}")
    
    def _group_laws_by_ordnungsnummer(self) -> Dict[str, List[Tuple[str, int]]]:
        """
        Group law files by ordnungsnummer.
        
        Returns:
            Dictionary mapping ordnungsnummer to list of (filename, nachtragsnummer) tuples
        """
        laws_by_ordnungsnummer = defaultdict(list)
        
        if not self.collection_dir.exists():
            return {}
        
        for file_path in self.collection_dir.glob("*.html"):
            match = self.law_file_pattern.match(file_path.name)
            if match:
                ordnungsnummer = match.group(1)
                nachtragsnummer = int(match.group(2))
                laws_by_ordnungsnummer[ordnungsnummer].append((file_path.name, nachtragsnummer))
        
        # Sort by nachtragsnummer for each ordnungsnummer
        for ordnungsnummer in laws_by_ordnungsnummer:
            laws_by_ordnungsnummer[ordnungsnummer].sort(key=lambda x: x[1])
        
        return dict(laws_by_ordnungsnummer)
    
    def _generate_map_for_law(self, ordnungsnummer: str, files: List[Tuple[str, int]]) -> None:
        """
        Generate anchor map for a specific law.
        
        Args:
            ordnungsnummer: The law's ordnungsnummer
            files: List of (filename, nachtragsnummer) tuples for this law
        """
        # Get metadata from lookup if available
        law_metadata = self.metadata_lookup.get(ordnungsnummer, {})
        
        anchor_map = {
            "metadata": {
                "ordnungsnummer": ordnungsnummer,
                "title": law_metadata.get('title', ''),
                "abbreviation": law_metadata.get('abbreviation', ''),
                "provision_type": ""
            },
            "provisions": {}
        }
        
        # Process each version of the law
        for filename, nachtragsnummer in files:
            file_path = self.collection_dir / filename
            try:
                self._process_law_file(file_path, nachtragsnummer, anchor_map)
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
        
        # Save the anchor map
        map_file = self.anchor_maps_dir / f"{ordnungsnummer}-map.json"
        with open(map_file, 'w', encoding='utf-8') as f:
            json.dump(anchor_map, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"Generated anchor map for {ordnungsnummer}")
    
    def _process_law_file(self, file_path: Path, nachtragsnummer: int, anchor_map: Dict) -> None:
        """
        Process a single law file and update the anchor map.
        
        Args:
            file_path: Path to the HTML file
            nachtragsnummer: The version number of this law
            anchor_map: The anchor map to update
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
        
        # Extract provision type from the HTML (title/abbreviation already set from collection data)
        if not anchor_map["metadata"]["provision_type"]:
            self._extract_provision_type(soup, anchor_map["metadata"])
        
        # Find all provision and subprovision anchors
        provisions = anchor_map["provisions"]
        
        # Process all elements with provision/subprovision IDs
        for element in soup.find_all(id=self.anchor_pattern):
            anchor_id = element.get('id', '')
            match = self.anchor_pattern.match(anchor_id)
            if not match:
                continue
            
            prov_num = match.group(1)
            sub_num = match.group(2)
            
            version_str = str(nachtragsnummer)
            
            if sub_num:
                # Handle subprovision
                if prov_num not in provisions:
                    provisions[prov_num] = {
                        "latest_version": version_str,
                        "versions": [],
                        "subprovisions": {}
                    }
                
                if "subprovisions" not in provisions[prov_num]:
                    provisions[prov_num]["subprovisions"] = {}
                
                if sub_num not in provisions[prov_num]["subprovisions"]:
                    provisions[prov_num]["subprovisions"][sub_num] = {
                        "latest_version": version_str,
                        "versions": []
                    }
                
                sub_data = provisions[prov_num]["subprovisions"][sub_num]
                if version_str not in sub_data["versions"]:
                    sub_data["versions"].append(version_str)
                    sub_data["latest_version"] = version_str
            else:
                # Handle provision
                if prov_num not in provisions:
                    provisions[prov_num] = {
                        "latest_version": version_str,
                        "versions": [],
                        "subprovisions": {}
                    }
                
                prov_data = provisions[prov_num]
                if version_str not in prov_data["versions"]:
                    prov_data["versions"].append(version_str)
                    prov_data["latest_version"] = version_str
    
    def _extract_provision_type(self, soup: BeautifulSoup, metadata: Dict) -> None:
        """
        Extract provision type from the law HTML.
        
        Args:
            soup: BeautifulSoup object of the HTML
            metadata: Metadata dictionary to update
        """
        # Determine provision type by looking at provision links
        provision_link = soup.find('a', href=re.compile(r'#seq-\d+-prov-\d+'))
        if provision_link:
            link_text = provision_link.get_text(strip=True)
            if link_text.startswith('§'):
                metadata["provision_type"] = "§"
            elif link_text.startswith('Art.'):
                metadata["provision_type"] = "Art."
            else:
                # Default to § if unclear
                metadata["provision_type"] = "§"


def generate_anchor_maps_for_collection(public_dir: str, collection: str, 
                                      collection_data: Optional[List[Dict]] = None,
                                      concurrent: bool = True, max_workers: int = 10) -> None:
    """
    Generate anchor maps for a specific collection.
    
    Args:
        public_dir: Path to the public directory
        collection: Collection name ('col-zh' or 'col-ch')
        collection_data: Optional collection metadata from processed JSON
        concurrent: Whether to process laws concurrently
        max_workers: Maximum number of concurrent workers
    """
    generator = AnchorMapGenerator(public_dir, collection, collection_data)
    generator.generate_all_maps(concurrent, max_workers)


def generate_all_anchor_maps(public_dir: str, concurrent: bool = True, max_workers: int = 10) -> None:
    """
    Generate anchor maps for all collections.
    
    Args:
        public_dir: Path to the public directory
        concurrent: Whether to process laws concurrently
        max_workers: Maximum number of concurrent workers
    """
    for collection in ['col-zh', 'col-ch']:
        logger.info(f"Generating anchor maps for {collection}")
        generate_anchor_maps_for_collection(public_dir, collection, None, concurrent, max_workers)