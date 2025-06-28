#!/usr/bin/env python3
"""
Fedlex Scraping Pipeline - Main Entry Point

This module orchestrates the complete Fedlex law scraping and processing pipeline:
1. Scrapes federal law metadata from Fedlex SPARQL endpoint
2. Downloads missing law versions and files
3. Updates metadata with version relationships and categorization
4. Maintains comprehensive version tracking across all federal laws

Usage:
    python -m src.cmd.b1_scrape_fedlex

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import time
from pathlib import Path

# Import fedlex module functions
from src.modules.fedlex_module.scrape_collection_fedlex_sparql import main as scrape_main
from src.modules.fedlex_module.update_metadata import main as update_metadata_main

# Import logging utilities
from src.utils.logging_decorators import configure_logging
from src.utils.logging_utils import get_module_logger, OperationLogger

# Get logger for this module
logger = get_module_logger(__name__)


@configure_logging()
def main() -> None:
    """
    Main entry point for the Fedlex scraping pipeline.
    
    Orchestrates the complete process of scraping, downloading, and processing
    Fedlex federal law documents. Tracks errors and provides detailed logging.
    """
    start_time = time.time()
    
    # Use operation logger for the entire scraping process
    with OperationLogger("Fedlex Scraping Pipeline") as op_logger:
        try:
            # Phase 1: Scrape current laws from Fedlex SPARQL endpoint
            op_logger.log_info("--- Phase 1: Scraping current laws from Fedlex ---")
            op_logger.log_info("Starting scraping of current federal laws")
            scrape_main()
            op_logger.log_info("Finished scraping current federal laws")
            
            # Phase 2: Update metadata and discover new versions
            op_logger.log_info("--- Phase 2: Updating metadata and discovering versions ---")
            op_logger.log_info("Starting metadata update and version discovery")
            update_metadata_main()
            op_logger.log_info("Finished metadata update and version discovery")
            
            # Log final summary
            total_duration = time.time() - start_time
            op_logger.log_info(f"--- Pipeline completed successfully in {total_duration:.2f}s ---")
            op_logger.log_info("Fedlex scraping and metadata update pipeline completed")
            
        except Exception as e:
            op_logger.log_error(f"Pipeline failed with error: {e}")
            logger.exception("Fedlex scraping pipeline failed")
            raise


if __name__ == "__main__":
    main()