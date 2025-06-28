#!/usr/bin/env python3
"""
ZH-Lex PDF Processing Pipeline - Main Entry Point

This module processes ZH-Lex law PDF files that have been scraped and downloaded:
1. Extends metadata with color and style information from PDFs
2. Converts JSON data from Adobe Extract API to structured HTML
3. Processes and merges marginalia (side notes and references)
4. Matches marginalia with corresponding law text
5. Creates hyperlinks between cross-references
6. Cleans and finalizes HTML output

Usage:
    python -m src.cmd.02_process_zhlex_main [options]

Options:
    --folder: Choose folder to process (zhlex_files or test_files)
    --mode: Processing mode (concurrent or sequential)

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

# Import custom modules
from src.modules.general_module import clean_html, json_to_html
from src.modules.law_pdf_module import (
    extend_metadata,
    merge_marginalia,
    match_marginalia,
    create_hyperlinks,
)

# Import configuration
from src.config import DataPaths, LogConfig, FilePatterns, ProcessingSteps, DateFormats
from src.constants import Messages

# Import logging utilities
from src.utils.logging_decorators import configure_logging
from src.utils.logging_utils import get_module_logger

# Import external modules
import arrow
import logging
import glob
import json
from tqdm import tqdm
import argparse
import sys
import concurrent.futures
from pathlib import Path

# Get logger for this module
logger = get_module_logger(__name__)


def generate_file_paths(pdf_file: str) -> dict:
    """
    Given an original PDF file path, generate and return a dictionary of derived file paths.
    """
    return {
        "original_pdf_path": pdf_file,
        "json_file_law": pdf_file.replace(FilePatterns.ORIGINAL_PDF, "-modified.json"),
        "json_file_law_updated": pdf_file.replace(
            FilePatterns.ORIGINAL_PDF, "-modified-updated.json"
        ),
        "modified_pdf_path": pdf_file.replace(FilePatterns.ORIGINAL_PDF, FilePatterns.MODIFIED_PDF),
        "json_file_marginalia": pdf_file.replace(FilePatterns.ORIGINAL_PDF, "-marginalia.json"),
        "json_file_marginalia_updated": pdf_file.replace(
            FilePatterns.ORIGINAL_PDF, "-marginalia-updated.json"
        ),
        "modified_pdf_path_marginalia": pdf_file.replace(
            FilePatterns.ORIGINAL_PDF, FilePatterns.MARGINALIA_PDF
        ),
        "metadata_file": pdf_file.replace("-original.pdf", "-metadata.json"),
        "html_file_law": pdf_file.replace("-original.pdf", "-modified.html"),
        "html_file_marginalia": pdf_file.replace("-original.pdf", "-marginalia.html"),
        "merged_html_law": pdf_file.replace("-original.pdf", "-merged.html"),
    }


def read_metadata(metadata_file: str) -> dict:
    """Reads and returns the metadata from a JSON file."""
    with open(metadata_file, "r") as f:
        return json.load(f)


def write_metadata(metadata_file: str, metadata: dict) -> None:
    """Writes the updated metadata back to the JSON file."""
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)


def process_pdf_file(pdf_file: str) -> bool:
    """
    Process a single PDF file by:
      - Extending metadata (extracting color) for law and marginalia PDFs.
      - Converting JSON to HTML for both law and marginalia.
      - Merging marginalia, matching them with the law,
        creating hyperlinks, and cleaning the final HTML.
      - Updating metadata with a processing timestamp.
    Returns True if processing succeeded; otherwise, False.
    """
    paths = generate_file_paths(pdf_file)
    try:
        metadata = read_metadata(paths["metadata_file"])

        logger.info(f"Extracting color for law: {pdf_file}")
        extend_metadata.main(
            paths["original_pdf_path"],
            paths["modified_pdf_path"],
            paths["json_file_law"],
            paths["json_file_law_updated"],
        )
        logger.info(f"Finished extracting color for law: {pdf_file}")

        logger.info(f"Extracting color for marginalia: {pdf_file}")
        extend_metadata.main(
            paths["original_pdf_path"],
            paths["modified_pdf_path_marginalia"],
            paths["json_file_marginalia"],
            paths["json_file_marginalia_updated"],
        )
        logger.info(f"Finished extracting color for marginalia: {pdf_file}")

        logger.info(f"Converting law JSON to HTML: {pdf_file}")
        json_to_html.main(
            paths["json_file_law_updated"],
            metadata,
            paths["html_file_law"],
            marginalia=False,
        )
        logger.info(f"Finished converting law JSON to HTML: {pdf_file}")

        logger.info(f"Converting marginalia JSON to HTML: {pdf_file}")
        json_to_html.main(
            paths["json_file_marginalia_updated"],
            metadata,
            paths["html_file_marginalia"],
            marginalia=True,
        )
        logger.info(f"Finished converting marginalia JSON to HTML: {pdf_file}")

        logger.info(f"Merging marginalia: {pdf_file}")
        merge_marginalia.main(paths["html_file_marginalia"])
        logger.info(f"Finished merging marginalia: {pdf_file}")

        logger.info(f"Matching marginalia: {pdf_file}")
        match_marginalia.main(
            paths["html_file_law"],
            paths["html_file_marginalia"],
            paths["merged_html_law"],
        )
        logger.info(f"Finished matching marginalia: {pdf_file}")

        logger.info(f"Creating hyperlinks: {pdf_file}")
        create_hyperlinks.main(paths["merged_html_law"], paths["json_file_law_updated"])
        logger.info(f"Finished creating hyperlinks: {pdf_file}")

        logger.info(f"Cleaning HTML: {pdf_file}")
        clean_html.main(paths["merged_html_law"])
        logger.info(f"Finished cleaning HTML: {pdf_file}")

        # Add processing timestamp to metadata
        timestamp = arrow.now().format("YYYYMMDD-HHmmss")
        metadata.setdefault("process_steps", {})["generate_html"] = timestamp
        write_metadata(paths["metadata_file"], metadata)
        return True
    except Exception as e:
        timestamp = arrow.now().format("YYYYMMDD-HHmmss")
        logger.error(f"Error in {__file__}: {e} at {timestamp}", exc_info=True)
        return False


def process_files_concurrently(pdf_files):
    """Process files in parallel using ProcessPoolExecutor"""
    error_counter = 0
    with concurrent.futures.ProcessPoolExecutor() as executor:
        # Map the process_pdf_file function to all pdf_files and wrap with tqdm for progress bar
        results = list(
            tqdm(executor.map(process_pdf_file, pdf_files), total=len(pdf_files))
        )

    error_counter = results.count(False)
    return error_counter


def process_files_sequentially(pdf_files):
    """Process files sequentially for easier debugging"""
    error_counter = 0
    for pdf_file in tqdm(pdf_files):
        success = process_pdf_file(pdf_file)
        if not success:
            error_counter += 1

    return error_counter


@configure_logging()
def main(folder: str, concurrent_mode: bool) -> None:
    """
    Process all PDF files in the specified folder.

    Args:
        folder: The folder to process (zhlex_files or zhlex_files_test)
        concurrent_mode: If True, process files in parallel; otherwise, sequentially
    """
    logger.info("Loading laws index")
    pdf_files = glob.glob(f"data/zhlex/{folder}/**/**/*-original.pdf", recursive=True)
    pdf_files = list(set(pdf_files))
    if not pdf_files:
        logger.info("No PDF files found. Exiting.")
        return

    logger.info(
        f"Processing using {'concurrent' if concurrent_mode else 'sequential'} mode"
    )

    if concurrent_mode:
        error_counter = process_files_concurrently(pdf_files)
    else:
        error_counter = process_files_sequentially(pdf_files)

    logger.info(f"Finished processing HTML with {error_counter} errors")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process PDF files")
    parser.add_argument(
        "--folder",
        type=str,
        default="zhlex_files_test",
        choices=["zhlex_files", "zhlex_files_test"],
        help="Folder to process",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="concurrent",
        choices=["concurrent", "sequential"],
        help="Processing mode: concurrent (parallel) or sequential (for debugging)",
    )
    args = parser.parse_args()

    concurrent_mode = args.mode == "concurrent"
    main(args.folder, concurrent_mode)
