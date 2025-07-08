"""Module for generating enhanced XML sitemaps for the zhlaw website.

This module creates sitemap.xml files following the sitemap protocol with enhanced
features including:
- Metadata-aware lastmod dates (generation date for newest versions, publikationsdatum for older)
- Canonical URL references for law versions
- Language and description meta tags
- YAML frontmatter parsing for static content
- Special handling for index.html and dispatch.html
- Priority assignment based on law version status

The enhanced sitemap improves SEO and provides better metadata for search engines
while ensuring all law pages are properly discoverable and categorized.

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import os
import json
import re
from datetime import datetime
from urllib.parse import urljoin
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import yaml
from src.utils.logging_utils import get_module_logger
from .build_zhlaw import alphanum_key

# Get logger for this module
logger = get_module_logger(__name__)


def should_filter_version(version: Dict[str, Any], all_versions: List[Dict[str, Any]]) -> bool:
    """
    Determines if a version should be filtered out based on the criteria:
    1. Must be the highest numeric_nachtragsnummer of all versions
    2. "law_text_url" must be "null" or None
    3. "aufhebungsdatum" must contain a date
    4. "in_force" must be false
    
    Args:
        version: The version to check
        all_versions: All versions for this law (to determine if it's the highest)
    
    Returns:
        True if the version should be filtered out
    """
    # Sort versions by numeric_nachtragsnummer to find the highest
    sorted_versions = sorted(
        all_versions, key=lambda x: alphanum_key(x.get("nachtragsnummer", ""))
    )
    
    # Check if this is the highest version
    if not sorted_versions or version != sorted_versions[-1]:
        return False
    
    # Check all four conditions
    law_text_url_null = (
        version.get("law_text_url") == "null" or 
        version.get("law_text_url") is None
    )
    has_aufhebungsdatum = (
        version.get("aufhebungsdatum") and 
        version.get("aufhebungsdatum") != ""
    )
    not_in_force = version.get("in_force") is False
    
    return law_text_url_null and has_aufhebungsdatum and not_in_force


class SitemapGenerator:
    def __init__(self, domain, public_dir="public"):
        self.domain = domain.rstrip("/")
        self.public_dir = public_dir
        self.static_priorities = {
            "404.html": "0.1",
            "about.html": "0.5",
            "data.html": "0.8",
            "index.html": "1.0",
            "dispatch.html": "0.8",
            "privacy.html": "0.3",
        }
        
        # Load collection metadata
        self.zh_metadata = self._load_collection_metadata("zh")
        self.ch_metadata = self._load_collection_metadata("ch")
        
        # Build canonical URL mappings
        self.canonical_urls = self._build_canonical_urls()
        
        # Parse static content metadata
        self.static_content_metadata = self._parse_static_content_metadata()

    def _load_collection_metadata(self, collection_type: str) -> Optional[Dict]:
        """Load collection metadata from JSON files."""
        try:
            if collection_type == "zh":
                metadata_path = "data/zhlex/zhlex_data/zhlex_data_processed.json"
            elif collection_type == "ch":
                metadata_path = "data/fedlex/fedlex_data/fedlex_data_processed.json"
            else:
                return None
                
            if os.path.exists(metadata_path):
                with open(metadata_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load {collection_type} metadata: {e}")
        return None
    
    def _parse_static_content_metadata(self) -> Dict[str, Dict]:
        """Parse YAML frontmatter from static content files."""
        metadata = {}
        content_dir = Path("src/static_files/content")
        
        if not content_dir.exists():
            return metadata
            
        for md_file in content_dir.glob("*.md"):
            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    
                # Parse YAML frontmatter
                if content.startswith("---"):
                    try:
                        _, frontmatter, _ = content.split("---", 2)
                        yaml_data = yaml.safe_load(frontmatter)
                        
                        html_filename = md_file.stem + ".html"
                        metadata[html_filename] = yaml_data
                    except Exception as e:
                        logger.warning(f"Could not parse YAML frontmatter in {md_file}: {e}")
                        
            except Exception as e:
                logger.warning(f"Could not read {md_file}: {e}")
                
        return metadata
    
    def _build_canonical_urls(self) -> Dict[str, str]:
        """Build mapping of law files to their canonical URLs."""
        canonical_urls = {}
        
        # Process ZH laws
        if self.zh_metadata:
            for law in self.zh_metadata:
                ordnungsnummer = law.get("ordnungsnummer", "")
                versions = law.get("versions", [])
                
                # Find the latest version by numeric_nachtragsnummer, excluding filtered versions
                newest_version = None
                if versions:
                    # Filter out versions that should be excluded (using should_filter_version logic)
                    selectable_versions = []
                    for version in versions:
                        if not should_filter_version(version, versions):
                            selectable_versions.append(version)
                    
                    if selectable_versions:
                        try:
                            newest_version = max(selectable_versions, key=lambda v: v.get("numeric_nachtragsnummer", 0))
                        except (TypeError, ValueError):
                            # Fallback to last version in list if numeric comparison fails
                            newest_version = selectable_versions[-1]
                
                if newest_version and ordnungsnummer:
                    canonical_url = f"{self.domain}/col-zh/{ordnungsnummer}-{newest_version.get('nachtragsnummer', '')}.html"
                    
                    # Map all versions of this law to the canonical URL
                    for version in versions:
                        nachtragsnummer = version.get("nachtragsnummer", "")
                        if nachtragsnummer:
                            version_url = f"{self.domain}/col-zh/{ordnungsnummer}-{nachtragsnummer}.html"
                            canonical_urls[version_url] = canonical_url
        
        # Process CH laws (similar structure)
        if self.ch_metadata:
            for law in self.ch_metadata:
                ordnungsnummer = law.get("ordnungsnummer", "")
                versions = law.get("versions", [])
                
                # Find the latest version by numeric_nachtragsnummer, excluding filtered versions
                newest_version = None
                if versions:
                    # Filter out versions that should be excluded (using should_filter_version logic)
                    selectable_versions = []
                    for version in versions:
                        if not should_filter_version(version, versions):
                            selectable_versions.append(version)
                    
                    if selectable_versions:
                        try:
                            newest_version = max(selectable_versions, key=lambda v: v.get("numeric_nachtragsnummer", 0))
                        except (TypeError, ValueError):
                            # Fallback to last version in list if numeric comparison fails
                            newest_version = selectable_versions[-1]
                
                if newest_version and ordnungsnummer:
                    canonical_url = f"{self.domain}/col-ch/{ordnungsnummer}-{newest_version.get('nachtragsnummer', '')}.html"
                    
                    for version in versions:
                        nachtragsnummer = version.get("nachtragsnummer", "")
                        if nachtragsnummer:
                            version_url = f"{self.domain}/col-ch/{ordnungsnummer}-{nachtragsnummer}.html"
                            canonical_urls[version_url] = canonical_url
        
        return canonical_urls

    def get_last_modified(self, file_path: str, url: str) -> str:
        """Get last modified date based on file type and version status."""
        # Check if this is a law file
        law_metadata = self._get_law_metadata_from_url(url)
        if law_metadata:
            # Use generation date for newest version, publikationsdatum for older versions
            if law_metadata.get("in_force", False):
                # Newest version - use generation date
                process_steps = law_metadata.get("process_steps", {})
                generate_html_date = process_steps.get("generate_html")
                if generate_html_date:
                    try:
                        # Convert from format "20250628-094121" to "2025-06-28"
                        date_part = generate_html_date.split("-")[0]
                        if len(date_part) == 8:
                            return f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
                    except Exception:
                        pass
            else:
                # Older version - use publikationsdatum
                publikationsdatum = law_metadata.get("publikationsdatum")
                if publikationsdatum and len(publikationsdatum) == 8:
                    try:
                        return f"{publikationsdatum[:4]}-{publikationsdatum[4:6]}-{publikationsdatum[6:8]}"
                    except Exception:
                        pass
        
        # Fallback to file modification time
        timestamp = os.path.getmtime(file_path)
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
    
    def _get_law_metadata_from_url(self, url: str) -> Optional[Dict]:
        """Extract law metadata from URL by finding matching law and version."""
        # Parse URL to extract collection and filename
        if "/col-zh/" in url:
            collection = "zh"
            metadata_list = self.zh_metadata
        elif "/col-ch/" in url:
            collection = "ch"
            metadata_list = self.ch_metadata
        else:
            return None
            
        if not metadata_list:
            return None
            
        # Extract ordnungsnummer and nachtragsnummer from filename
        filename = url.split("/")[-1].replace(".html", "")
        match = re.match(r"(.+)-(\d+)$", filename)
        if not match:
            return None
            
        ordnungsnummer = match.group(1)
        nachtragsnummer = match.group(2)
        
        # Find the law and version
        for law in metadata_list:
            if law.get("ordnungsnummer") == ordnungsnummer:
                # Check current version
                if str(law.get("nachtragsnummer", "")) == nachtragsnummer:
                    return law
                    
                # Check versions list
                for version in law.get("versions", []):
                    if str(version.get("nachtragsnummer", "")) == nachtragsnummer:
                        # Return version data with process_steps from main law
                        version_data = version.copy()
                        version_data["process_steps"] = law.get("process_steps", {})
                        return version_data
        
        return None

    def parse_col_zh_filename(self, filename):
        match = re.match(r"(.+)-(\d+)", filename.replace(".html", ""))
        if match:
            ordnungsnummer = match.group(1)
            nachtragsnummer = int(match.group(2))
            return ordnungsnummer, nachtragsnummer
        return None, None

    def get_priority(self, root: str, file: str, url: str) -> str:
        """
        Determines the priority of a file based on its location, name, and metadata.

        Args:
            root: Directory containing the file
            file: Filename
            url: Full URL

        Returns:
            str: Priority value between 0.0 and 1.0
        """
        # Assign lowest priority (0.1) to diff files
        if "diff" in root:
            return "0.1"

        if "col-zh" in root or "col-ch" in root:
            law_metadata = self._get_law_metadata_from_url(url)
            if law_metadata:
                # Highest priority for laws currently in force
                return "1.0" if law_metadata.get("in_force", False) else "0.2"
            
            # Fallback to filename parsing
            ordnungsnummer, nachtragsnummer = self.parse_col_zh_filename(file)
            if ordnungsnummer is not None:
                # Group files by ordnungsnummer
                same_law_files = [
                    f for f in os.listdir(root) if f.startswith(f"{ordnungsnummer}-")
                ]
                if same_law_files:
                    max_number = max(
                        int(self.parse_col_zh_filename(f)[1] or 0)
                        for f in same_law_files
                        if self.parse_col_zh_filename(f)[1] is not None
                    )
                    return "1.0" if nachtragsnummer == max_number else "0.2"
                return "1.0"  # Single file case
            return "0.2"
        return self.static_priorities.get(file, "0.8")
    
    def get_language_and_description(self, file: str, url: str) -> Tuple[str, str]:
        """
        Get language and description meta tags for a page.
        
        Args:
            file: Filename
            url: Full URL
            
        Returns:
            Tuple of (language, description)
        """
        language = "de-CH"  # Default language
        
        # Special handling for specific pages
        if file == "index.html":
            description = "zhlaw.ch ist eine digitale, durchsuch- und verlinkbare Erlasssammlung (Kanton ZH). Massgebend sind die offiziellen Publikationen."
        elif file == "dispatch.html":
            description = "Feed der parlamentarischen Geschäfte des Kantons Zürich. Massgebend sind die offiziellen Publikationen."
        elif file in self.static_content_metadata:
            # Use YAML frontmatter
            metadata = self.static_content_metadata[file]
            description = metadata.get("description", metadata.get("title", ""))
        elif "/col-zh/" in url or "/col-ch/" in url:
            # Law files - use format "[Ordnungsnummer]-[Nachtragsnummer] ∗ [Erlasstitel]"
            law_metadata = self._get_law_metadata_from_url(url)
            if law_metadata:
                ordnungsnummer = law_metadata.get("ordnungsnummer", "")
                nachtragsnummer = law_metadata.get("nachtragsnummer", "")
                erlasstitel = law_metadata.get("erlasstitel", "")
                description = f"{ordnungsnummer}-{nachtragsnummer} ∗ {erlasstitel}"
            else:
                # Fallback to filename parsing
                filename = file.replace(".html", "")
                ordnungsnummer, nachtragsnummer = self.parse_col_zh_filename(file)
                if ordnungsnummer and nachtragsnummer:
                    description = f"{ordnungsnummer}-{nachtragsnummer} ∗ Gesetzestext"
                else:
                    description = "Gesetzestext"
        else:
            description = "zhlaw.ch - Digitale Erlasssammlung"
            
        return language, description
    
    def get_canonical_url(self, url: str) -> Optional[str]:
        """Get canonical URL for a page. Returns the canonical URL even if it's self-referencing."""
        return self.canonical_urls.get(url)
    
    def _sort_urls_by_law(self, urls: List[Dict]) -> List[Dict]:
        """
        Sort URLs to group same laws together with canonical version last.
        
        Args:
            urls: List of URL dictionaries
            
        Returns:
            Sorted list of URL dictionaries
        """
        # Separate law URLs from other URLs
        law_urls = []
        other_urls = []
        
        for url_data in urls:
            url = url_data["loc"]
            if "/col-zh/" in url or "/col-ch/" in url:
                law_urls.append(url_data)
            else:
                other_urls.append(url_data)
        
        # Group law URLs by ordnungsnummer
        law_groups = {}
        for url_data in law_urls:
            url = url_data["loc"]
            
            # Extract ordnungsnummer from URL
            filename = url.split("/")[-1].replace(".html", "")
            match = re.match(r"(.+)-(\d+)$", filename)
            
            if match:
                ordnungsnummer = match.group(1)
                nachtragsnummer = int(match.group(2))
                
                # Determine collection
                collection = "zh" if "/col-zh/" in url else "ch"
                group_key = f"{collection}:{ordnungsnummer}"
                
                if group_key not in law_groups:
                    law_groups[group_key] = []
                
                # Add metadata for sorting
                url_data["_ordnungsnummer"] = ordnungsnummer
                url_data["_nachtragsnummer"] = nachtragsnummer
                url_data["_collection"] = collection
                
                # Check if this is the canonical version
                law_metadata = self._get_law_metadata_from_url(url)
                url_data["_is_canonical"] = law_metadata.get("in_force", False) if law_metadata else False
                
                law_groups[group_key].append(url_data)
        
        # Sort within each group and collect results
        sorted_law_urls = []
        for group_key in sorted(law_groups.keys()):
            group = law_groups[group_key]
            
            # Sort by nachtragsnummer, with canonical version last
            group.sort(key=lambda x: (
                x["_is_canonical"],  # False comes before True
                x["_nachtragsnummer"]
            ))
            
            # Clean up temporary sorting metadata
            for url_data in group:
                for key in ["_ordnungsnummer", "_nachtragsnummer", "_collection", "_is_canonical"]:
                    url_data.pop(key, None)
            
            sorted_law_urls.extend(group)
        
        # Combine other URLs first, then sorted law URLs
        return other_urls + sorted_law_urls

    def generate_sitemap(self):
        urls = []

        for root, dirs, files in os.walk(self.public_dir):
            for file in files:
                if not file.endswith(".html"):
                    continue

                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, self.public_dir)
                url = urljoin(self.domain, relative_path)
                
                last_mod = self.get_last_modified(file_path, url)
                priority = self.get_priority(root, file, url)
                canonical_url = self.get_canonical_url(url)

                url_data = {
                    "loc": url,
                    "lastmod": last_mod,
                    "priority": priority,
                }
                
                if canonical_url:
                    url_data["canonical"] = canonical_url
                
                urls.append(url_data)

        # Sort URLs to group same laws together with canonical version last
        sorted_urls = self._sort_urls_by_law(urls)
        
        return self.create_sitemap_xml(sorted_urls)

    def create_sitemap_xml(self, urls):
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        xml += 'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'

        for url in urls:
            xml += "  <url>\n"
            xml += f'    <loc>{self._escape_xml(url["loc"])}</loc>\n'
            xml += f'    <lastmod>{url["lastmod"]}</lastmod>\n'
            xml += f'    <priority>{url["priority"]}</priority>\n'
            
            # Add canonical link if present
            if url.get("canonical"):
                xml += f'    <xhtml:link rel="canonical" href="{self._escape_xml(url["canonical"])}" />\n'
            
            xml += "  </url>\n"

        xml += "</urlset>"
        return xml
    
    def _escape_xml(self, text: str) -> str:
        """Escape special characters for XML."""
        return (text.replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;")
                   .replace('"', "&quot;")
                   .replace("'", "&#39;"))

    def save_sitemap(self, output_path="public/sitemap.xml"):
        try:
            sitemap_content = self.generate_sitemap()
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(sitemap_content)
            logger.info(f"Enhanced sitemap saved to {output_path}")
        except Exception as e:
            logger.error(f"Failed to generate sitemap: {e}")
            # Fallback to basic sitemap
            self._save_basic_sitemap(output_path)
    
    def _save_basic_sitemap(self, output_path: str):
        """Fallback to basic sitemap generation if enhanced version fails."""
        try:
            urls = []
            for root, dirs, files in os.walk(self.public_dir):
                for file in files:
                    if not file.endswith(".html"):
                        continue
                    
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, self.public_dir)
                    url = urljoin(self.domain, relative_path)
                    timestamp = os.path.getmtime(file_path)
                    last_mod = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
                    
                    urls.append({"loc": url, "lastmod": last_mod, "priority": "0.5"})
            
            xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
            xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            for url in urls:
                xml += "  <url>\n"
                xml += f'    <loc>{self._escape_xml(url["loc"])}</loc>\n'
                xml += f'    <lastmod>{url["lastmod"]}</lastmod>\n'
                xml += f'    <priority>{url["priority"]}</priority>\n'
                xml += "  </url>\n"
            xml += "</urlset>"
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(xml)
            logger.info(f"Basic sitemap saved to {output_path}")
        except Exception as e:
            logger.error(f"Failed to generate basic sitemap: {e}")


# Usage example
if __name__ == "__main__":
    generator = SitemapGenerator("https://www.zhlaw.ch")
    generator.save_sitemap()