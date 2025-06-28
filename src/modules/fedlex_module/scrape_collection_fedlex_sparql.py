"""Scrapes federal law metadata from Fedlex SPARQL endpoint.

This module queries the Fedlex SPARQL endpoint to retrieve metadata about
Swiss federal laws in the Classified Compilation (SR). It fetches information
such as SR numbers, titles, abbreviations, and publication dates.

This module has been refactored to use the new modular components.

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import json
from pathlib import Path

from . import fedlex_config as config
from .sparql_client import SPARQLClient
from .file_downloader import FileDownloader
from .fedlex_utils import save_json_file

from src.utils.logging_utils import get_module_logger
logger = get_module_logger(__name__)


def main():
    """Main function to scrape current federal laws from Fedlex."""
    logger.info("Starting Fedlex scraping process...")
    
    # Ensure directories exist
    config.ensure_directories()
    
    # Initialize clients
    sparql_client = SPARQLClient()
    file_downloader = FileDownloader()
    
    try:
        # Get current laws from SPARQL
        logger.info("Querying current laws from Fedlex SPARQL endpoint...")
        current_laws = sparql_client.get_current_laws()
        
        if not current_laws:
            logger.error("No laws retrieved from SPARQL endpoint")
            return
        
        logger.info(f"Retrieved {len(current_laws)} current laws")
        
        # Save API response for reference
        response_file = config.BASE_DATA_DIR / "fedlex_response.json"
        api_data = {
            "timestamp": "query_timestamp_placeholder", 
            "count": len(current_laws),
            "laws": [law.dict() for law in current_laws]
        }
        save_json_file(api_data, response_file)
        logger.info(f"Saved API response to {response_file}")
        
        # Download laws
        downloaded_count = 0
        for law in current_laws:
            # Check if files already exist
            html_path = config.get_file_path(law.sr_number, law.date_applicability, "raw")
            metadata_path = config.get_file_path(law.sr_number, law.date_applicability, "metadata")
            
            if html_path.exists() and metadata_path.exists():
                logger.debug(f"Files already exist for {law.sr_number} "
                           f"(date: {law.date_applicability})")
                continue
            
            # Download version
            logger.info(f"Downloading {law.sr_number} (date: {law.date_applicability})...")
            result = file_downloader.download_version(
                law, config.BASE_FILES_DIR, law.aufhebungsdatum
            )
            
            if result.success:
                downloaded_count += 1
                logger.info(f"Successfully downloaded to {result.file_path}")
            else:
                logger.error(f"Failed to download {law.sr_number}: {result.error}")
        
        logger.info(f"Scraping complete: {downloaded_count} new files downloaded")
        
    except Exception as e:
        logger.error(f"Scraping failed: {e}", exc_info=True)
        raise
    
    finally:
        sparql_client.close()
        file_downloader.close()


if __name__ == "__main__":
    main()