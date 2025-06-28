"""File downloader for Fedlex HTML and metadata files.

This module handles downloading HTML files from Fedlex URLs and creating
corresponding metadata files, with retry logic and error handling.

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import time
from pathlib import Path
from typing import Optional, List, Dict
import requests
import arrow

from . import fedlex_config as config
from .fedlex_models import LawVersion, LawMetadata, DownloadResult
from .fedlex_utils import retry_on_failure, save_json_file

from src.utils.logging_utils import get_module_logger
logger = get_module_logger(__name__)


class FileDownloader:
    """Handles downloading of Fedlex HTML files and metadata creation."""
    
    def __init__(self):
        """Initialize the file downloader."""
        self.session = requests.Session()
    
    def download_html(self, url: str, output_path: Path) -> DownloadResult:
        """Download HTML content from URL with retry logic.
        
        Args:
            url: URL to download from
            output_path: Path to save the HTML file
            
        Returns:
            DownloadResult with success status
        """
        @retry_on_failure(
            max_retries=config.DOWNLOAD_MAX_RETRIES,
            delay=0.5,
            backoff=2.0
        )
        def _download():
            response = self.session.get(url, timeout=config.DOWNLOAD_TIMEOUT)
            
            if response.status_code == 200:
                response.encoding = response.apparent_encoding
                content = response.text
                
                if not content or content.isspace():
                    raise ValueError(f"Empty content received from {url}")
                
                # Ensure directory exists
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Write content
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                return DownloadResult(success=True, file_path=str(output_path))
            else:
                raise requests.HTTPError(f"HTTP {response.status_code} for {url}")
        
        try:
            result = _download()
            logger.info(f"Successfully downloaded HTML to {output_path}")
            return result
        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            return DownloadResult(success=False, error=str(e))
    
    def create_metadata(self, version: LawVersion, metadata_path: Path,
                       aufhebungsdatum: str = "") -> bool:
        """Create metadata JSON file for a law version.
        
        Args:
            version: LawVersion object with data
            metadata_path: Path to save metadata file
            aufhebungsdatum: Repeal date if known
            
        Returns:
            True if successful
        """
        try:
            # Create metadata from version
            metadata = version.to_metadata()
            
            # Update with additional information
            metadata.doc_info.aufhebungsdatum = aufhebungsdatum
            metadata.doc_info.in_force = not bool(aufhebungsdatum)
            metadata.process_steps.download = arrow.now().format("YYYYMMDD-HHmmss")
            
            # Save to file
            return save_json_file(metadata.dict(), metadata_path)
            
        except Exception as e:
            logger.error(f"Failed to create metadata at {metadata_path}: {e}")
            return False
    
    def download_version(self, version: LawVersion, base_dir: Path,
                        aufhebungsdatum: str = "") -> DownloadResult:
        """Download a complete law version (HTML + metadata).
        
        Args:
            version: LawVersion to download
            base_dir: Base directory for files
            aufhebungsdatum: Repeal date if known
            
        Returns:
            DownloadResult with status
        """
        # Generate file paths
        html_path = config.get_file_path(
            version.sr_number,
            version.date_applicability,
            "raw"
        )
        metadata_path = config.get_file_path(
            version.sr_number,
            version.date_applicability,
            "metadata"
        )
        
        # Check if files already exist
        if html_path.exists() and metadata_path.exists():
            logger.debug(f"Files already exist for {version.sr_number} "
                        f"version {version.date_applicability}")
            return DownloadResult(success=True, file_path=str(html_path))
        
        # Download HTML
        html_result = self.download_html(version.file_url, html_path)
        if not html_result.success:
            return html_result
        
        # Create metadata
        if not self.create_metadata(version, metadata_path, aufhebungsdatum):
            # Clean up HTML if metadata creation failed
            if html_path.exists():
                html_path.unlink()
            return DownloadResult(
                success=False,
                error="Failed to create metadata file"
            )
        
        # Add delay between downloads
        time.sleep(config.DOWNLOAD_DELAY_BETWEEN_FILES)
        
        return DownloadResult(success=True, file_path=str(html_path))
    
    def download_missing_versions(self, versions: List[LawVersion],
                                 existing_dates: set, base_dir: Path,
                                 aufhebungsdatum: str = "") -> int:
        """Download versions that don't exist locally.
        
        Args:
            versions: List of all versions from SPARQL
            existing_dates: Set of dates already downloaded
            base_dir: Base directory for files
            aufhebungsdatum: Repeal date if known
            
        Returns:
            Number of successfully downloaded versions
        """
        success_count = 0
        missing_versions = [
            v for v in versions
            if v.date_applicability and v.date_applicability not in existing_dates
        ]
        
        if not missing_versions:
            return 0
        
        logger.info(f"Downloading {len(missing_versions)} missing versions for "
                   f"{versions[0].sr_number if versions else 'unknown'}")
        
        for version in missing_versions:
            result = self.download_version(version, base_dir, aufhebungsdatum)
            if result.success:
                success_count += 1
            else:
                logger.warning(f"Failed to download version {version.date_applicability}: "
                             f"{result.error}")
        
        return success_count
    
    def download_batch(self, versions_map: Dict[str, List[LawVersion]],
                      base_dir: Path, aufhebungsdatum_cache: Dict[str, str]) -> Dict[str, int]:
        """Download missing versions for a batch of SR numbers.
        
        Args:
            versions_map: Map of SR numbers to their versions
            base_dir: Base directory for files
            aufhebungsdatum_cache: Cache of repeal dates
            
        Returns:
            Map of SR numbers to download counts
        """
        results = {}
        
        for sr_number, versions in versions_map.items():
            # Find existing versions
            sr_dir = base_dir / sr_number
            existing_dates = set()
            
            if sr_dir.exists():
                for date_dir in sr_dir.iterdir():
                    if date_dir.is_dir() and date_dir.name.isdigit():
                        existing_dates.add(date_dir.name)
            
            # Download missing versions
            aufhebungsdatum = aufhebungsdatum_cache.get(sr_number, "")
            count = self.download_missing_versions(
                versions, existing_dates, base_dir, aufhebungsdatum
            )
            results[sr_number] = count
            
            if count > 0:
                logger.info(f"Downloaded {count} versions for {sr_number}")
        
        # Add delay between batches
        time.sleep(config.DOWNLOAD_BATCH_DELAY)
        
        return results
    
    def close(self):
        """Close the session."""
        self.session.close()