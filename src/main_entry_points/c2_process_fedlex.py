#!/usr/bin/env python3
"""
Fedlex File Processing Pipeline - Main Entry Point

This module processes Fedlex federal law HTML files that have been scraped and downloaded:
1. Converts raw HTML files to structured, clean HTML format
2. Removes unnecessary elements, comments, and processing instructions
3. Restructures elements for consistent formatting across the site
4. Assigns sequential IDs to provisions and subprovisions
5. Creates hyperlinks between cross-references
6. Wraps annex content and handles footnotes appropriately

Usage:
    python -m src.cmd.c2_process_fedlex [options]

Options:
    --folder: Choose folder to process (fedlex_files or fedlex_files_test)
    --mode: Processing mode (concurrent or sequential)
    --workers: Number of worker processes for concurrent mode

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import argparse
import time
from pathlib import Path

# Import fedlex processing module
from src.modules.fedlex_module.process_fedlex_files import main as process_files_main

# Import logging utilities
from src.utils.logging_decorators import configure_logging
from src.utils.logging_utils import get_module_logger, OperationLogger

# Get logger for this module
logger = get_module_logger(__name__)


@configure_logging()
def main(folder: str, mode: str, workers: int = None) -> None:
    """
    Process all Fedlex HTML files in the specified folder.

    Args:
        folder: The folder to process ('fedlex_files' or 'fedlex_files_test')
        mode: Processing mode ('concurrent' or 'sequential')
        workers: Number of worker processes for concurrent mode (None for auto)
    """
    start_time = time.time()
    
    # Determine input directory
    if folder == "fedlex_files_test":
        input_dir = Path("data/fedlex/fedlex_files_test")
    else:  # fedlex_files (default)
        input_dir = Path("data/fedlex/fedlex_files")
    
    # Use operation logger for the entire processing pipeline
    with OperationLogger("Fedlex File Processing Pipeline") as op_logger:
        try:
            op_logger.log_info(f"Starting Fedlex file processing")
            op_logger.log_info(f"Input directory: {input_dir}")
            op_logger.log_info(f"Processing mode: {mode}")
            if mode == "concurrent" and workers:
                op_logger.log_info(f"Worker processes: {workers}")
            
            # Check if directory exists
            if not input_dir.exists():
                op_logger.log_error(f"Input directory not found: {input_dir}")
                logger.error(f"Input directory not found: {input_dir}")
                return
            
            # Call the fedlex processing function
            # Note: The process_fedlex_files module handles its own argument parsing
            # We need to temporarily modify sys.argv to pass arguments to the module
            import sys
            original_argv = sys.argv.copy()
            
            try:
                # Construct arguments for the fedlex processing module
                new_argv = [
                    "process_fedlex_files.py",
                    "--folder", folder,
                    "--mode", mode
                ]
                if workers and mode == "concurrent":
                    new_argv.extend(["--workers", str(workers)])
                
                # Temporarily replace sys.argv
                sys.argv = new_argv
                
                # Call the processing function
                process_files_main()
                
                op_logger.log_info("Fedlex file processing completed successfully")
                
            finally:
                # Restore original argv
                sys.argv = original_argv
            
            # Log final summary
            total_duration = time.time() - start_time
            op_logger.log_info(f"--- Processing completed in {total_duration:.2f}s ---")
            
        except Exception as e:
            op_logger.log_error(f"Processing failed with error: {e}")
            logger.exception("Fedlex file processing pipeline failed")
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process Fedlex HTML files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process test files sequentially (for debugging)
  python -m src.cmd.b2_process_fedlex --folder fedlex_files_test --mode sequential

  # Process all files with parallel processing
  python -m src.cmd.b2_process_fedlex --folder fedlex_files --mode concurrent

  # Process with specific number of workers
  python -m src.cmd.b2_process_fedlex --folder fedlex_files --mode concurrent --workers 4
        """)
    
    parser.add_argument(
        "--folder",
        type=str,
        default="fedlex_files_test",
        choices=["fedlex_files", "fedlex_files_test"],
        help="Folder to process (default: fedlex_files_test)"
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="sequential",
        choices=["concurrent", "sequential"],
        help="Processing mode: concurrent (parallel) or sequential (default, for debugging)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of worker processes for concurrent mode (default: auto-detected)"
    )
    
    args = parser.parse_args()
    main(args.folder, args.mode, args.workers)
