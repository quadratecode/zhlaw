#!/usr/bin/env python3
"""
Parliamentary Dispatch Processing Pipeline - Main Entry Point

This module processes parliamentary dispatches from the Kantonsrat Zürich:
1. Scrapes dispatch metadata from the parliamentary website
2. Downloads PDF files for each dispatch
3. Analyzes dispatch content using OpenAI to identify law changes
4. Generates HTML pages for each dispatch with change analysis
5. Builds an RSS feed for recent dispatches
6. Integrates processed dispatches into the static website

Usage:
    python -m src.cmd.04_process_krzh_dispatch_main

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

# Import custom modules
from src.modules.krzh_dispatch_module import scrape_dispatch
from src.modules.krzh_dispatch_module import download_entries
from src.modules.krzh_dispatch_module import call_openai_api
from src.modules.site_generator_module import build_zhlaw
from src.modules.site_generator_module import build_dispatch
from src.modules.krzh_dispatch_module import build_rss

# Import external modules
import arrow
import logging
import glob
import json
from tqdm import tqdm
from bs4 import BeautifulSoup
import shutil
import os

# -----------------------------------------------------------------------------
# Module-Level Constants
# -----------------------------------------------------------------------------
# Data directories
DATA_DIR = "data/krzh_dispatch"
DISPATCH_DATA_DIR = f"{DATA_DIR}/krzh_dispatch_data"
DISPATCH_FILES_DIR = f"{DATA_DIR}/krzh_dispatch_files"
DISPATCH_SITE_DIR = f"{DATA_DIR}/krzh_dispatch_site"

# Data files
DISPATCH_DATA_FILE = f"{DISPATCH_DATA_DIR}/krzh_dispatch_data.json"
DISPATCH_HTML_FILE = f"{DISPATCH_SITE_DIR}/dispatch.html"
PUBLIC_HTML_FILE = "public/dispatch.html"

# Affair type priorities (lower number = higher priority)
AFFAIR_TYPE_PRIORITIES = {
    "vorlage": 1,
    "einzelinitiative": 2,
    "behördeninitiative": 3,
    "parlamentarische initiative": 4,
}
DEFAULT_PRIORITY = 5  # For other types
NO_TYPE_PRIORITY = 6  # For no affair_type


# -----------------------------------------------------------------------------
# Sorting Functions
# -----------------------------------------------------------------------------
def sort_dispatches(dispatch_data):
    """
    Sort dispatches by date (newest first).

    Args:
        dispatch_data (list): List of dispatch data dictionaries

    Returns:
        list: Sorted dispatch data
    """
    # Sort by krzh_dispatch_date in descending order
    return sorted(dispatch_data, key=lambda x: x["krzh_dispatch_date"], reverse=True)


def sort_affairs(affairs):
    """
    Sort affairs by type according to priority order.

    Args:
        affairs (list): List of affair dictionaries

    Returns:
        list: Sorted affairs
    """

    def get_priority(affair):
        # Get affair type and convert to lowercase
        affair_type = affair.get("affair_type", "").lower()

        # Check each priority category
        for key, priority in AFFAIR_TYPE_PRIORITIES.items():
            if key in affair_type:
                return priority

        # If affair_type exists but doesn't match any priority category
        return DEFAULT_PRIORITY if affair_type else NO_TYPE_PRIORITY

    # Sort by priority (lower number = higher priority)
    return sorted(affairs, key=get_priority)


# Set up logging
logging.basicConfig(
    filename="logs/process.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S %p",
)


def main():

    # Initialize error counter
    error_counter = 0

    # Timestamp
    timestamp = arrow.now().format("YYYYMMDD-HHmmss")

    logging.info("Starting scraping krzh dispatch")
    scrape_dispatch.main(DISPATCH_DATA_DIR)
    logging.info("Finished scraping krzh dispatch")

    logging.info("Starting downloading krzh dispatch")
    download_entries.main(DISPATCH_DATA_DIR)
    logging.info("Finished downloading krzh dispatch")

    logging.info("Loading krzh dispatch index")
    pdf_files = glob.glob(f"{DISPATCH_FILES_DIR}/**/**/*-original.pdf", recursive=True)
    # Remove duplicates found from different junctions
    pdf_files = list(set(pdf_files))
    if not pdf_files:
        logging.info("No PDF files found. Exiting.")
        return

    for pdf_file in tqdm(pdf_files):
        original_pdf_path = pdf_file
        metadata_file = pdf_file.replace("-original.pdf", "-metadata.json")

        try:
            with open(metadata_file, "r") as f:
                metadata = json.load(f)

            # Check if the affair type is one of the targeted types
            affair_type_lower = metadata["doc_info"]["affair_type"].lower()
            is_target_type = (
                "vorlage" in affair_type_lower
                or "einzelinitiative" in affair_type_lower
                or "behördeninitiative" in affair_type_lower
                or "parlamentarische initiative" in affair_type_lower
            )

            # Process only target types with OpenAI
            if is_target_type:
                try:
                    if (
                        metadata["process_steps"]["call_ai"] == ""
                        and metadata["doc_info"]["ai_changes"] != ""
                    ):
                        logging.info(f"Calling GPT Assistant: {pdf_file}")
                        call_openai_api.main(original_pdf_path, metadata)
                        logging.info(f"Finished calling GPT Assistant: {pdf_file}")
                        metadata["process_steps"]["call_ai"] = timestamp
                # Ignore error code 400
                except Exception as e:
                    if "400" in str(e):
                        logging.error(
                            f"Error during in {__file__}: {e} at {timestamp}",
                            exc_info=True,
                        )
                        metadata["doc_info"]["ai_changes"] = "{error: too many tokens}"
                        metadata["process_steps"]["call_ai"] = timestamp
                    else:
                        logging.error(
                            f"Error during in {__file__}: {e} at {timestamp}",
                            exc_info=True,
                        )
                        error_counter += 1
                        continue

            # Save the updated metadata
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=4, ensure_ascii=False)

            # Add certain metadata back to krzh_dispatch_data.json under the correct entry
            krzh_dispatch_data_path = DISPATCH_DATA_FILE
            with open(krzh_dispatch_data_path, "r") as f:
                krzh_dispatch_data = json.load(f)

            for krzh_dispatch in krzh_dispatch_data:
                if (
                    krzh_dispatch["krzh_dispatch_date"]
                    == metadata["doc_info"]["krzh_dispatch_date"]
                ):
                    for affair in krzh_dispatch["affairs"]:
                        if (
                            affair["vorlagen_nr"] == metadata["doc_info"]["affair_nr"]
                            or affair["kr_nr"].replace("/", ".")
                            == metadata["doc_info"]["affair_nr"]
                        ):
                            affair["affair_nr"] = metadata["doc_info"]["affair_nr"]
                            # Add changes if key exists
                            if "changes" in metadata["doc_info"]:
                                affair["changes"] = metadata["doc_info"]["changes"]
                            if "ai_changes" in metadata["doc_info"]:
                                affair["ai_changes"] = metadata["doc_info"][
                                    "ai_changes"
                                ]
                            break

            with open(krzh_dispatch_data_path, "w") as f:
                json.dump(krzh_dispatch_data, f, indent=4, ensure_ascii=False)

        except Exception as e:
            logging.error(
                f"Error during in {__file__}: {e} at {timestamp}", exc_info=True
            )
            error_counter += 1
            continue

    logging.info(f"Finished scraping krzh dispatch with {str(error_counter)} errors")

    # Build page from kzrh_dispatch_data.json
    logging.info("Building page")
    html_file_path = DISPATCH_HTML_FILE
    os.makedirs(os.path.dirname(html_file_path), exist_ok=True)

    logging.info(f"Starting page build")
    with open(DISPATCH_DATA_FILE, "r") as f:
        krzh_dispatch_data = json.load(f)

    # Sort dispatches by date and affairs by type before building the page
    logging.info("Sorting dispatch data for display")
    # Sort dispatches by date (newest first)
    krzh_dispatch_data = sort_dispatches(krzh_dispatch_data)
    # Sort affairs within each dispatch by affair_type
    for dispatch in krzh_dispatch_data:
        dispatch["affairs"] = sort_affairs(dispatch["affairs"])
    # Save the sorted data back to the file
    with open(DISPATCH_DATA_FILE, "w") as f:
        json.dump(krzh_dispatch_data, f, indent=4, ensure_ascii=False)
    logging.info("Saved sorted dispatch data")

    # Build core of dispatch page
    with open(html_file_path, "w") as f:
        f.write(build_dispatch.main(krzh_dispatch_data))

    # Process the HTML with BeautifulSoup and additional functions
    with open(html_file_path, "r") as file:
        soup = BeautifulSoup(file, "html.parser")

    soup = build_zhlaw.insert_header(soup)
    soup = build_zhlaw.insert_footer(soup)

    # Write the modified HTML back to the file
    with open(html_file_path, "w") as f:
        f.write(str(soup))
    logging.info("Finished page build")

    # Generate RSS feed
    logging.info("Generating RSS feed")
    rss_feed = build_rss.main(krzh_dispatch_data, site_url="https://www.zhlaw.ch")

    # Save RSS feed to public directory
    rss_file_path = "public/dispatch-feed.xml"
    with open(rss_file_path, "w", encoding="utf-8") as f:
        f.write(rss_feed)
    logging.info(f"RSS feed saved to {rss_file_path}")

    # Copy html file to public
    logging.info("Copying html file to public")
    os.makedirs("public", exist_ok=True)
    shutil.copy(html_file_path, PUBLIC_HTML_FILE)


if __name__ == "__main__":
    main()
