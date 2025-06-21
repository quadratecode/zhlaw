"""
Generate anchor maps for laws to enable dynamic linking to the latest version of provisions.

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
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
        # Nachtragsnummer can contain letters (e.g., 066a)
        self.law_file_pattern = re.compile(r'^([\d.]+)-(\d+[a-zA-Z]*)\.html$')
        
        # Pattern to extract provision/subprovision from anchor IDs
        self.anchor_pattern = re.compile(r'seq-\d+-prov-(\d+[a-z]?)(?:-sub-(\d+))?')
        
        # Create metadata lookup dictionary if collection data provided
        self.metadata_lookup = {}
        if collection_data:
            for law in collection_data:
                self.metadata_lookup[law['ordnungsnummer']] = {
                    'title': law.get('erlasstitel', ''),
                    'abbreviation': law.get('abkuerzung', ''),
                    'kurztitel': law.get('kurztitel', '')
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
    
    def _group_laws_by_ordnungsnummer(self) -> Dict[str, List[Tuple[str, float, str]]]:
        """
        Group law files by ordnungsnummer.
        
        Returns:
            Dictionary mapping ordnungsnummer to list of (filename, numeric_nachtragsnummer, original_nachtragsnummer) tuples
        """
        laws_by_ordnungsnummer = defaultdict(list)
        
        if not self.collection_dir.exists():
            return {}
        
        for file_path in self.collection_dir.glob("*.html"):
            match = self.law_file_pattern.match(file_path.name)
            if match:
                ordnungsnummer = match.group(1)
                nachtragsnummer = match.group(2)  # Keep as string to preserve format
                
                # Convert to numeric value for sorting/comparison
                try:
                    numeric_nachtragsnummer = float(nachtragsnummer)
                except:
                    # Convert any letters in the nachtragsnummer to numbers (e.g. "066a" -> 066.1, "066b" -> 066.2, etc.)
                    # Match digits followed by letters in nachtragsnummer
                    match_letter = re.match(r"(\d+)([a-zA-Z]+)$", nachtragsnummer)
                    if match_letter:
                        number_part = match_letter.group(1)
                        letter_part = match_letter.group(2)

                        # Convert each letter to its corresponding number (a=1, b=2, ..., z=26)
                        letter_numbers = "".join(
                            str(ord(char.lower()) - ord("a") + 1)
                            for char in letter_part
                        )

                        # Combine the numeric and letter parts to form a float (e.g., "066a" -> 66.1)
                        numeric_nachtragsnummer = float(
                            f"{number_part}.{letter_numbers}"
                        )
                    else:
                        # Handle cases where nachtragsnummer doesn't match the expected format
                        logger.error(f"Invalid nachtragsnummer format: {nachtragsnummer}")
                        continue
                
                laws_by_ordnungsnummer[ordnungsnummer].append((file_path.name, numeric_nachtragsnummer, nachtragsnummer))
        
        # Sort by numeric_nachtragsnummer for each ordnungsnummer
        for ordnungsnummer in laws_by_ordnungsnummer:
            laws_by_ordnungsnummer[ordnungsnummer].sort(key=lambda x: x[1])
        
        return dict(laws_by_ordnungsnummer)
    
    def _generate_map_for_law(self, ordnungsnummer: str, files: List[Tuple[str, float, str]]) -> None:
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
                "kurztitel": law_metadata.get('kurztitel', ''),
                "provision_type": "",
                "latest_version": ""
            },
            "provisions": {}
        }
        
        # Find the latest version (highest nachtragsnummer)
        if not files:
            return
            
        latest_filename, latest_numeric_nachtragsnummer, latest_original_nachtragsnummer = max(files, key=lambda x: x[1])
        latest_file_path = self.collection_dir / latest_filename
        
        # Store the latest version in metadata using the original string format
        anchor_map["metadata"]["latest_version"] = latest_original_nachtragsnummer
        
        # Process only the latest version to get provision type and provisions
        try:
            self._process_law_file(latest_file_path, anchor_map)
        except Exception as e:
            logger.error(f"Error processing latest version {latest_file_path}: {e}")
        
        # Save the anchor map
        map_file = self.anchor_maps_dir / f"{ordnungsnummer}-map.json"
        with open(map_file, 'w', encoding='utf-8') as f:
            json.dump(anchor_map, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"Generated anchor map for {ordnungsnummer}")
    
    def _process_law_file(self, file_path: Path, anchor_map: Dict) -> None:
        """
        Process a single law file and update the anchor map.
        
        Args:
            file_path: Path to the HTML file
            anchor_map: The anchor map to update
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
        
        # Extract provision type from the HTML (title/abbreviation already set from collection data)
        if not anchor_map["metadata"]["provision_type"]:
            self._extract_provision_type(soup, anchor_map["metadata"])
        
        # Find all provision and subprovision anchors
        provisions = anchor_map["provisions"]
        
        # Track the highest sequence number for each provision
        prov_sequences = {}  # prov_num -> max_seq
        subprov_sequences = {}  # (prov_num, sub_num) -> max_seq
        
        # Updated pattern to capture sequence number
        seq_anchor_pattern = re.compile(r'seq-(\d+)-prov-(\d+[a-z]?)(?:-sub-(\d+))?')
        
        # Process all elements with provision/subprovision IDs
        for element in soup.find_all(id=seq_anchor_pattern):
            anchor_id = element.get('id', '')
            match = seq_anchor_pattern.match(anchor_id)
            if not match:
                continue
            
            seq_num = int(match.group(1))
            prov_num = match.group(2)
            sub_num = match.group(3)
            
            if sub_num:
                # Track max sequence for this subprovision
                key = (prov_num, sub_num)
                if key not in subprov_sequences or seq_num > subprov_sequences[key]:
                    subprov_sequences[key] = seq_num
            else:
                # Track max sequence for this provision
                if prov_num not in prov_sequences or seq_num > prov_sequences[prov_num]:
                    prov_sequences[prov_num] = seq_num
        
        # Now update the provisions structure with sequence counts
        for prov_num, max_seq in prov_sequences.items():
            if prov_num not in provisions:
                provisions[prov_num] = {
                    "sequences": max_seq + 1,  # Convert to count (0-based to 1-based)
                    "subprovisions": {}
                }
            else:
                provisions[prov_num]["sequences"] = max_seq + 1
        
        # Update subprovisions with sequence counts
        for (prov_num, sub_num), max_seq in subprov_sequences.items():
            if prov_num not in provisions:
                provisions[prov_num] = {
                    "sequences": 0,
                    "subprovisions": {}
                }
            
            if "subprovisions" not in provisions[prov_num]:
                provisions[prov_num]["subprovisions"] = {}
            
            provisions[prov_num]["subprovisions"][sub_num] = {
                "sequences": max_seq + 1  # Convert to count
            }
    
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


def generate_anchor_maps_index(public_dir: str) -> None:
    """
    Generate an index file of all anchor maps for the quick select feature.
    
    Args:
        public_dir: Path to the public directory
    """
    public_path = Path(public_dir)
    index_data = {"laws": []}
    
    # Process both collections
    for collection_short in ['zh', 'ch']:
        anchor_maps_dir = public_path / "anchor-maps" / collection_short
        collection_full = f"col-{collection_short}"
        
        if not anchor_maps_dir.exists():
            logger.warning(f"Anchor maps directory {anchor_maps_dir} does not exist")
            continue
        
        # Read all anchor map files
        for map_file in anchor_maps_dir.glob("*-map.json"):
            try:
                with open(map_file, 'r', encoding='utf-8') as f:
                    anchor_map = json.load(f)
                
                metadata = anchor_map.get("metadata", {})
                
                # Add to index
                index_data["laws"].append({
                    "ordnungsnummer": metadata.get("ordnungsnummer", ""),
                    "title": metadata.get("title", ""),
                    "abbreviation": metadata.get("abbreviation", ""),
                    "kurztitel": metadata.get("kurztitel", ""),
                    "collection": collection_short
                })
            except Exception as e:
                logger.error(f"Error reading anchor map {map_file}: {e}")
    
    # Sort laws by ordnungsnummer within each collection
    index_data["laws"].sort(key=lambda x: (x["collection"], x["ordnungsnummer"]))
    
    # Save index file
    index_file = public_path / "anchor-maps-index.json"
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Generated anchor maps index with {len(index_data['laws'])} laws")