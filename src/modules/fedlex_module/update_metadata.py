#!/usr/bin/env python3
"""Main orchestrator for updating Fedlex metadata.

This refactored module coordinates the various components of the Fedlex
processing pipeline to discover new versions, download missing files,
update metadata, and maintain version relationships.

Functions:
    main(): Main orchestration function for the complete pipeline

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import time
from pathlib import Path
from typing import Dict, List

from . import fedlex_config as config
from .sparql_client import SPARQLClient
from .file_downloader import FileDownloader
from .category_assigner import CategoryAssigner
from .version_manager import VersionManager
from .metadata_updater import MetadataUpdater
from .fedlex_utils import find_metadata_files, group_by_sr_number

# Configure logging
from src.utils.logging_utils import get_module_logger
logger = get_module_logger(__name__)


def process_batch_versions(sparql_client: SPARQLClient, 
                          file_downloader: FileDownloader,
                          sr_batch: List[str],
                          aufhebungsdatum_cache: Dict[str, str]) -> Dict[str, int]:
    """Process a batch of SR numbers for version discovery and downloading.
    
    Args:
        sparql_client: SPARQL client instance
        file_downloader: File downloader instance
        sr_batch: List of SR numbers to process
        aufhebungsdatum_cache: Cache of repeal dates
        
    Returns:
        Dictionary mapping SR numbers to download counts
    """
    # Get aufhebungsdatum for laws not in cache
    needing_aufhebung = [sr for sr in sr_batch if sr not in aufhebungsdatum_cache]
    if needing_aufhebung:
        logger.info(f"Fetching aufhebungsdatum for {len(needing_aufhebung)} laws...")
        aufhebung_data = sparql_client.get_aufhebungsdatum_batch(needing_aufhebung)
        aufhebungsdatum_cache.update(aufhebung_data)
    
    # Get all versions for the batch
    versions_map = sparql_client.get_all_versions_batch(sr_batch)
    
    if not versions_map:
        logger.warning(f"No version data returned for batch starting with {sr_batch[0]}")
        return {sr: 0 for sr in sr_batch}
    
    # Download missing versions
    download_results = file_downloader.download_batch(
        versions_map, config.BASE_FILES_DIR, aufhebungsdatum_cache
    )
    
    return download_results


def main():
    """Main orchestration function for the Fedlex metadata update pipeline."""
    start_time = time.time()
    logger.info("--- Starting Refactored Fedlex Data Processing Pipeline ---")
    
    # Ensure directories exist
    config.ensure_directories()
    
    # Initialize components
    sparql_client = SPARQLClient()
    file_downloader = FileDownloader()
    category_assigner = CategoryAssigner()
    version_manager = VersionManager()
    metadata_updater = MetadataUpdater(category_assigner)
    
    try:
        # --- Phase 1: Version Discovery and Download ---
        logger.info("--- Phase 1: Discovering and downloading new versions ---")
        
        # Find existing laws
        existing_files = find_metadata_files(config.BASE_FILES_DIR)
        law_groups = group_by_sr_number(existing_files)
        all_sr_numbers = sorted(list(law_groups.keys()))
        
        logger.info(f"Found {len(all_sr_numbers)} existing law groups")
        
        if len(all_sr_numbers) == 0:
            logger.warning("No existing laws found. Pipeline requires existing laws to check for updates.")
            return
        
        # Process in batches
        aufhebungsdatum_cache = {}
        total_downloaded = 0
        num_batches = (len(all_sr_numbers) + config.SPARQL_BATCH_SIZE - 1) // config.SPARQL_BATCH_SIZE
        
        for i in range(0, len(all_sr_numbers), config.SPARQL_BATCH_SIZE):
            batch_start = time.time()
            batch_srs = all_sr_numbers[i:i + config.SPARQL_BATCH_SIZE]
            batch_num = i // config.SPARQL_BATCH_SIZE + 1
            
            logger.info(f"Processing batch {batch_num}/{num_batches} "
                       f"({len(batch_srs)} laws)...")
            
            # Process batch
            download_results = process_batch_versions(
                sparql_client, file_downloader, batch_srs, aufhebungsdatum_cache
            )
            
            batch_downloads = sum(download_results.values())
            total_downloaded += batch_downloads
            
            batch_duration = time.time() - batch_start
            logger.info(f"Batch {batch_num} complete: {batch_downloads} files downloaded "
                       f"in {batch_duration:.2f}s")
        
        logger.info(f"Phase 1 complete: {total_downloaded} new files downloaded")
        
        # --- Phase 2: Metadata Updates ---
        logger.info("--- Phase 2: Updating metadata for all files ---")
        
        # Rescan for all metadata files (including newly downloaded)
        all_files = find_metadata_files(config.BASE_FILES_DIR)
        logger.info(f"Found {len(all_files)} total metadata files")
        
        # Process metadata updates in batches
        updated_count = 0
        for i in range(0, len(all_files), config.SPARQL_BATCH_SIZE):
            batch_files = all_files[i:i + config.SPARQL_BATCH_SIZE]
            batch_num = i // config.SPARQL_BATCH_SIZE + 1
            num_file_batches = (len(all_files) + config.SPARQL_BATCH_SIZE - 1) // config.SPARQL_BATCH_SIZE
            
            logger.info(f"Updating metadata batch {batch_num}/{num_file_batches} "
                       f"({len(batch_files)} files)...")
            
            updated_srs = metadata_updater.update_metadata_batch(
                batch_files, aufhebungsdatum_cache
            )
            updated_count += len(updated_srs)
        
        logger.info(f"Phase 2 complete: metadata updated for {updated_count} laws")
        
        # --- Phase 3: Version Linking ---
        logger.info("--- Phase 3: Updating version relationships ---")
        
        groups_processed, files_updated = version_manager.update_all_version_links()
        
        logger.info(f"Phase 3 complete: {groups_processed} groups processed, "
                   f"{files_updated} files updated with version links")
        
        # --- Summary ---
        total_duration = time.time() - start_time
        logger.info(f"--- Pipeline completed successfully in {total_duration:.2f}s ---")
        logger.info(f"Summary: {total_downloaded} files downloaded, "
                   f"{updated_count} laws updated, {files_updated} version links updated")
        
    except Exception as e:
        logger.error(f"Pipeline failed with error: {e}", exc_info=True)
        raise
    
    finally:
        # Clean up resources
        sparql_client.close()
        file_downloader.close()


if __name__ == "__main__":
    main()