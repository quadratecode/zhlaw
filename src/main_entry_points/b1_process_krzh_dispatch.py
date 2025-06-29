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
    python -m src.cmd.b1_process_krzh_dispatch_main

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
from src.modules.general_module.asset_versioning import AssetVersionManager

# Import external modules
import arrow
import logging
import glob
import json

# from tqdm import tqdm  # Replaced with progress_utils
from src.utils.progress_utils import progress_manager
from bs4 import BeautifulSoup
import os

# Import logging utilities
from src.utils.logging_decorators import configure_logging
from src.utils.logging_utils import get_module_logger

# Get logger for this module
logger = get_module_logger(__name__)

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
DISPATCH_HTML_FILE = "src/static_files/html/dispatch.html"
RSS_FEED_FILE = "src/static_files/html/dispatch-feed.xml"

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


# Get logger for this module
logger = get_module_logger(__name__)


@configure_logging()
@configure_logging()
def main():

    # Initialize error counter
    error_counter = 0

    # Timestamp
    timestamp = arrow.now().format("YYYYMMDD-HHmmss")

    logger.info("Starting scraping krzh dispatch")
    scrape_dispatch.main(DISPATCH_DATA_DIR)
    logger.info("Finished scraping krzh dispatch")

    logger.info("Starting downloading krzh dispatch")
    download_entries.main(DISPATCH_DATA_DIR)
    logger.info("Finished downloading krzh dispatch")

    logger.info("Loading krzh dispatch index")
    pdf_files = glob.glob(f"{DISPATCH_FILES_DIR}/**/**/*-original.pdf", recursive=True)
    # Remove duplicates found from different junctions
    pdf_files = list(set(pdf_files))
    if not pdf_files:
        logger.info("No PDF files found. Exiting.")
        return

    with progress_manager() as pm:
        counter = pm.create_counter(
            total=len(pdf_files),
            desc=f"Processing {len(pdf_files)} dispatch PDFs",
            unit="files",
        )

        for pdf_file in pdf_files:
            try:
                original_pdf_path = pdf_file
                metadata_file = pdf_file.replace("-original.pdf", "-metadata.json")

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
                            logger.info(f"Calling GPT Assistant: {pdf_file}")
                            call_openai_api.main(original_pdf_path, metadata)
                            logger.info(f"Finished calling GPT Assistant: {pdf_file}")
                            metadata["process_steps"]["call_ai"] = timestamp
                    # Ignore error code 400
                    except Exception as e:
                        if "400" in str(e):
                            logger.error(
                                f"Error during in {__file__}: {e} at {timestamp}",
                                exc_info=True,
                            )
                            metadata["doc_info"][
                                "ai_changes"
                            ] = "{error: too many tokens}"
                            metadata["process_steps"]["call_ai"] = timestamp
                        else:
                            logger.error(
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
                                affair["vorlagen_nr"]
                                == metadata["doc_info"]["affair_nr"]
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
                logger.error(
                    f"Error during in {__file__}: {e} at {timestamp}", exc_info=True
                )
                error_counter += 1
            finally:
                counter.update()

    logger.info(f"Finished scraping krzh dispatch with {str(error_counter)} errors")

    # Build page from kzrh_dispatch_data.json
    logger.info("Building page")
    html_file_path = DISPATCH_HTML_FILE
    os.makedirs(os.path.dirname(html_file_path), exist_ok=True)

    # Load asset version map if available
    logger.info("Loading asset version map")
    asset_manager = AssetVersionManager(
        source_dir="src/static_files/markup/", output_dir="public"
    )
    version_map = asset_manager.load_version_map()
    if version_map:
        build_zhlaw.set_version_map(version_map)
        logger.info(f"Loaded version map with {len(version_map)} entries")
    else:
        logger.warning(
            "No asset version map found - CSS versioning will not be applied"
        )

    logger.info(f"Starting page build")
    with open(DISPATCH_DATA_FILE, "r") as f:
        krzh_dispatch_data = json.load(f)

    # Sort dispatches by date and affairs by type before building the page
    logger.info("Sorting dispatch data for display")
    # Sort dispatches by date (newest first)
    krzh_dispatch_data = sort_dispatches(krzh_dispatch_data)
    # Sort affairs within each dispatch by affair_type
    for dispatch in krzh_dispatch_data:
        dispatch["affairs"] = sort_affairs(dispatch["affairs"])
    # Save the sorted data back to the file
    with open(DISPATCH_DATA_FILE, "w") as f:
        json.dump(krzh_dispatch_data, f, indent=4, ensure_ascii=False)
    logger.info("Saved sorted dispatch data")

    # Build core of dispatch page
    with open(html_file_path, "w") as f:
        f.write(build_dispatch.main(krzh_dispatch_data))

    # Process the HTML with BeautifulSoup and additional functions
    with open(html_file_path, "r") as file:
        soup = BeautifulSoup(file, "html.parser")

    # Update CSS references to use versioned assets
    soup = build_zhlaw.update_css_references_for_site_elements(soup)
    soup = build_zhlaw.insert_header(soup)
    soup = build_zhlaw.insert_footer(soup)

    # Write the modified HTML back to the file with pretty-printing
    from src.utils.html_utils import write_pretty_html
    write_pretty_html(soup, html_file_path, encoding="utf-8", add_doctype=False)
    logger.info("Finished page build")

    # Generate RSS feed
    logger.info("Generating RSS feed")
    rss_feed = build_rss.main(krzh_dispatch_data, site_url="https://www.zhlaw.ch")

    # Save RSS feed to static files directory
    with open(RSS_FEED_FILE, "w", encoding="utf-8") as f:
        f.write(rss_feed)
    logger.info(f"RSS feed saved to {RSS_FEED_FILE}")

    logger.info(
        "Dispatch files generated to src/static_files/html/ - will be included by site build process"
    )


if __name__ == "__main__":
    main()
