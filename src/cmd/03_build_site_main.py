# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

import logging
import glob
import json
from tqdm import tqdm
import shutil
import os
import arrow
from bs4 import BeautifulSoup
import subprocess
import argparse
import concurrent.futures

# Local imports
from src.modules.site_generator_module import build_zhlaw
from src.modules.site_generator_module import process_old_html
from src.modules.site_generator_module import create_placeholders
from src.modules.site_generator_module import generate_index
from src.modules.site_generator_module.create_sitemap import SitemapGenerator
from src.modules.dataset_generator_module import build_markdown
from src.modules.site_generator_module import html_diff

# Set up logging
logging.basicConfig(
    filename="logs/process.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S %p",
)

# Global variables for paths - will be set in main()
STATIC_PATH = None
COLLECTION_PATH_ZH = None
COLLECTION_PATH_CH = None


# -------------------------------------------------------------------------
# File Processing Functions
# -------------------------------------------------------------------------
def process_html_file(args):
    """
    Process a single HTML file and return success/error status.
    This function is designed to be callable by both sequential and parallel processors.
    """
    html_file, collection_data_path, collection_path, law_origin = args

    # Skip diff files
    if "-diff-" in html_file:
        return True  # Return success without processing

    # Identify what type of file we have
    if html_file.endswith("-original.html"):
        metadata_file = html_file.replace("-original.html", "-metadata.json")
        sfx = "-original"
        file_type = "old_html"
    elif html_file.endswith("-merged.html"):
        metadata_file = html_file.replace("-merged.html", "-metadata.json")
        sfx = "-merged"
        file_type = "new_html"
    else:
        # Likely a static site element
        file_type = "site_element"
        metadata_file = None

    try:
        if file_type in ["old_html", "new_html"]:
            # Load metadata
            with open(metadata_file, "r", encoding="utf-8") as file:
                metadata = json.load(file)

            # Load HTML
            if file_type == "old_html":
                # Older HTML might be iso-8859-1 encoded
                with open(html_file, "r", encoding="iso-8859-1") as file:
                    soup = BeautifulSoup(file, "html.parser")
                soup = process_old_html.main(soup)
            else:
                # Merged HTML is usually UTF-8
                with open(html_file, "r", encoding="utf-8") as file:
                    soup = BeautifulSoup(file, "html.parser")

        else:
            # For site elements
            metadata = {}
            with open(html_file, "r", encoding="utf-8") as file:
                soup = BeautifulSoup(file, "html.parser")

        # Insert InfoBox and other final touches
        doc_info = metadata.get("doc_info", {})
        soup = build_zhlaw.main(
            soup, html_file, doc_info, file_type, law_origin=law_origin
        )

        # Create output folders if needed
        if not os.path.exists(collection_path):
            os.makedirs(collection_path)

        # Update metadata file if relevant
        if file_type in ["old_html", "new_html"]:
            with open(metadata_file, "w", encoding="utf-8") as file:
                json.dump(metadata, file, indent=4, ensure_ascii=False)

            # Derive new filename (remove "-original" or "-merged" suffix)
            _, tail = os.path.split(html_file)
            new_tail = tail.replace(sfx, "")
            new_file_path = os.path.join(collection_path, new_tail)
        else:
            # For site elements, store in STATIC_PATH
            if not os.path.exists(STATIC_PATH):
                os.makedirs(STATIC_PATH)
            new_file_path = os.path.join(STATIC_PATH, os.path.basename(html_file))

        # Write final HTML
        with open(new_file_path, "w", encoding="utf-8") as file:
            file.write("<!DOCTYPE html>\n")
            file.write(str(soup))

        return True
    except Exception as e:
        logging.error(
            f"Error processing {html_file}: {e}",
            exc_info=True,
        )
        return False


def process_html_files_sequentially(
    html_files, collection_data_path, collection_path, law_origin
):
    """
    Process HTML files sequentially for easier debugging.
    """
    error_counter = 0
    for html_file in tqdm(
        html_files, desc=f"Processing {law_origin} files sequentially"
    ):
        success = process_html_file(
            (html_file, collection_data_path, collection_path, law_origin)
        )
        if not success:
            error_counter += 1

    return error_counter


def process_html_files_concurrently(
    html_files, collection_data_path, collection_path, law_origin, max_workers=None
):
    """
    Process HTML files in parallel using ProcessPoolExecutor.
    """
    error_counter = 0
    # Create a list of argument tuples for the process_html_file function
    process_args = [
        (html_file, collection_data_path, collection_path, law_origin)
        for html_file in html_files
    ]

    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Map the process function to all files and wrap with tqdm for progress bar
        results = list(
            tqdm(
                executor.map(process_html_file, process_args),
                total=len(process_args),
                desc=f"Processing {law_origin} files concurrently",
            )
        )

        # Count the number of failures
        error_counter = results.count(False)

    return error_counter


def main(
    folder_choice,
    dataset_trigger,
    placeholders_trigger,
    processing_mode,
    max_workers=None,
):
    """
    Depending on `folder_choice`:
     - "zhlex_files": process the main ZH-Lex folder (skip FedLex)
     - "ch_files": process only FedLex (skip ZH-Lex)
     - "all_files": process both ZH-Lex (zhlex_files) and FedLex
     - "test_files": process only ZH 'test_files' folder (skip FedLex)
    """
    global STATIC_PATH, COLLECTION_PATH_ZH, COLLECTION_PATH_CH

    # Show the selected processing mode
    logging.info(f"Using processing mode: {processing_mode}")

    # Define the collection data paths
    COLLECTION_DATA_ZH = "data/zhlex/zhlex_data/zhlex_data_processed.json"
    COLLECTION_DATA_CH = "data/fedlex/fedlex_data/fedlex_data_processed.json"
    PLACEHOLDER_DIR_ZH = "data/zhlex/placeholders"  # Used only for ZH-Lex

    # Set the output directory based on folder_choice
    if folder_choice == "test_files":
        STATIC_PATH = "public_test/"
        COLLECTION_PATH_ZH = f"{STATIC_PATH}col-zh/"
        COLLECTION_PATH_CH = f"{STATIC_PATH}col-ch/"
        logging.info(f"Using test output directory: {STATIC_PATH}")
    else:
        STATIC_PATH = "public/"
        COLLECTION_PATH_ZH = f"{STATIC_PATH}col-zh/"
        COLLECTION_PATH_CH = f"{STATIC_PATH}col-ch/"
        logging.info(f"Using standard output directory: {STATIC_PATH}")

    # Remove existing public folder to ensure a clean build
    if os.path.exists(STATIC_PATH):
        shutil.rmtree(STATIC_PATH)

    # Remove ZH placeholders if exist
    if os.path.exists(PLACEHOLDER_DIR_ZH):
        shutil.rmtree(PLACEHOLDER_DIR_ZH)

    # Decide whether to process ZH and/or CH based on the folder choice
    process_zh = False
    process_ch = False
    zh_folder = None

    if folder_choice == "zhlex_files":
        process_zh = True
        zh_folder = "zhlex_files"
    elif folder_choice == "test_files":
        process_zh = True
        zh_folder = "test_files"
    elif folder_choice == "ch_files":
        process_ch = True
    elif folder_choice == "all_files":
        process_zh = True
        zh_folder = "zhlex_files"
        process_ch = True

    # -------------------------------------------------------------------------
    # 1) Generate index (for ZH) if we are processing ZH
    # -------------------------------------------------------------------------
    if process_zh:
        logging.info("Generating ZH index")
        generate_index.main(
            COLLECTION_DATA_ZH,
            "src/static_files/html/index.html",  # Template
        )
        logging.info("Finished generating ZH index")

    # -------------------------------------------------------------------------
    # 2) Process ZH-Lex HTML files (if requested)
    # -------------------------------------------------------------------------
    if process_zh and zh_folder:
        logging.info(f"Loading ZH-Lex HTML files from '{zh_folder}'")

        html_files_zh_merged = glob.glob(
            f"data/zhlex/{zh_folder}/**/**/*-merged.html",
            recursive=True,
        )
        html_files_zh_orig = glob.glob(
            f"data/zhlex/{zh_folder}/**/**/*-original.html",
            recursive=True,
        )
        # Include site elements
        html_site_elements = glob.glob(
            "src/static_files/html/*.html",
            recursive=True,
        )
        # Combine
        html_files_zh = list(
            set(html_files_zh_merged + html_files_zh_orig + html_site_elements)
        )

        if not html_files_zh:
            logging.info("No ZH-Lex files found. Proceeding anyway...")
        else:
            # Process files in chosen mode
            if processing_mode == "concurrent":
                error_counter_zh = process_html_files_concurrently(
                    html_files_zh,
                    COLLECTION_DATA_ZH,
                    COLLECTION_PATH_ZH,
                    law_origin="zh",
                    max_workers=max_workers,
                )
            else:
                error_counter_zh = process_html_files_sequentially(
                    html_files_zh,
                    COLLECTION_DATA_ZH,
                    COLLECTION_PATH_ZH,
                    law_origin="zh",
                )

            logging.info(f"ZH-Lex: encountered {error_counter_zh} errors.")

    # -------------------------------------------------------------------------
    # 3) Process FedLex HTML files (if requested)
    # -------------------------------------------------------------------------
    if process_ch:
        logging.info("Loading FedLex HTML files")

        html_files_ch_merged = glob.glob(
            "data/fedlex/fedlex_files/**/**/*-merged.html",
            recursive=True,
        )
        html_files_ch_orig = glob.glob(
            "data/fedlex/fedlex_files/**/**/*-original.html",
            recursive=True,
        )
        html_files_ch = list(set(html_files_ch_merged + html_files_ch_orig))

        if not html_files_ch:
            logging.info("No FedLex files found. Proceeding anyway...")
        else:
            # Process files in chosen mode
            if processing_mode == "concurrent":
                error_counter_ch = process_html_files_concurrently(
                    html_files_ch,
                    COLLECTION_DATA_CH,
                    COLLECTION_PATH_CH,
                    law_origin="ch",
                    max_workers=max_workers,
                )
            else:
                error_counter_ch = process_html_files_sequentially(
                    html_files_ch,
                    COLLECTION_DATA_CH,
                    COLLECTION_PATH_CH,
                    law_origin="ch",
                )

            logging.info(f"FedLex: encountered {error_counter_ch} errors.")

    # -------------------------------------------------------------------------
    # 4) Build MD datasets if requested (for whichever we processed)
    # -------------------------------------------------------------------------
    if dataset_trigger.lower() == "yes":
        if process_zh and zh_folder:
            logging.info(f"Building dataset for ZH-Lex (folder: {zh_folder})")
            build_markdown.main(
                f"data/zhlex/{zh_folder}",
                STATIC_PATH,
                processing_mode=processing_mode,
                max_workers=max_workers,
            )
            logging.info("Finished building dataset for ZH-Lex")

        if process_ch:
            logging.info("Building dataset for FedLex ...")
            build_markdown.main(
                "data/fedlex/fedlex_files",
                STATIC_PATH,
                processing_mode=processing_mode,
                max_workers=max_workers,
            )
            logging.info("Finished building dataset for FedLex")

    # -------------------------------------------------------------------------
    # 5) Create placeholders for ZH-Lex only if requested
    # -------------------------------------------------------------------------
    if placeholders_trigger.lower() == "yes" and process_zh:
        # Load ZH data
        with open(COLLECTION_DATA_ZH, "r", encoding="utf-8") as file:
            zhlex_data_processed = json.load(file)

        # Collect all ZH public HTML files
        public_html_files_zh = glob.glob(
            os.path.join(COLLECTION_PATH_ZH, "*.html"),
            recursive=True,
        )

        logging.info("Creating placeholders for ZH-Lex")
        create_placeholders.main(
            zhlex_data_processed, public_html_files_zh, PLACEHOLDER_DIR_ZH
        )
        logging.info("Finished creating placeholders for ZH-Lex")

        # Copy placeholder files into the ZH collection
        if os.path.exists(PLACEHOLDER_DIR_ZH):
            shutil.copytree(
                PLACEHOLDER_DIR_ZH,
                COLLECTION_PATH_ZH,
                dirs_exist_ok=True,
            )

    # -------------------------------------------------------------------------
    # 5.5) Generate diffs for ZH-Lex and FedLex
    # TODO: Uncomment if diffs are needed (slow performance dramatically and uses more JS)
    # Dont forget to include version_comparison.js in build_zhlaw.py
    # -------------------------------------------------------------------------
    # if process_zh:
    #     logging.info("Generating diffs for ZH-Lex")
    #     zh_diff_path = os.path.join(STATIC_PATH, "col-zh/diff")
    #     zh_diff_count = html_diff.main(
    #         COLLECTION_DATA_ZH,
    #         COLLECTION_PATH_ZH,
    #         zh_diff_path,
    #         law_origin="zh",
    #         processing_mode=processing_mode,
    #         max_workers=max_workers,
    #     )
    #     logging.info(f"Generated {zh_diff_count} diffs for ZH-Lex")

    # if process_ch:
    #     logging.info("Generating diffs for FedLex")
    #     ch_diff_path = os.path.join(STATIC_PATH, "col-ch/diff")
    #     ch_diff_count = html_diff.main(
    #         COLLECTION_DATA_CH,
    #         COLLECTION_PATH_CH,
    #         ch_diff_path,
    #         law_origin="ch",
    #         processing_mode=processing_mode,
    #         max_workers=max_workers,
    #     )
    #     logging.info(f"Generated {ch_diff_count} diffs for FedLex")

    # -------------------------------------------------------------------------
    # 6) Copy static markup, server scripts, and relevant metadata JSON
    # -------------------------------------------------------------------------
    # Copy markup (CSS, JS, etc.) to public
    shutil.copytree(
        "src/static_files/markup/",
        STATIC_PATH,
        dirs_exist_ok=True,
    )

    # If ZH was processed, copy redirect script & metadata for ZH
    if process_zh:
        shutil.copy(
            "src/server_scripts/redirect.php",
            COLLECTION_PATH_ZH,
        )
        shutil.copy(
            COLLECTION_DATA_ZH,
            os.path.join(STATIC_PATH, "collection-metadata-zh.json"),
        )

    # If FedLex was processed, copy redirect script & metadata for CH
    if process_ch:
        shutil.copy(
            "src/server_scripts/redirect.php",
            COLLECTION_PATH_CH,
        )
        shutil.copy(
            COLLECTION_DATA_CH,
            os.path.join(STATIC_PATH, "collection-metadata-ch.json"),
        )

    # -------------------------------------------------------------------------
    # 7) Generate a sitemap (covering everything under public/)
    # -------------------------------------------------------------------------
    logging.info("Generating sitemap")
    site_url = "https://zhlaw.ch"
    if folder_choice == "test_files":
        site_url = "https://test.zhlaw.ch"  # Use a different URL for test site
    generator = SitemapGenerator(site_url, STATIC_PATH)
    generator.save_sitemap(f"{STATIC_PATH}sitemap.xml")
    logging.info("Finished generating sitemap")

    # -------------------------------------------------------------------------
    # 8) Build Pagefind search index (covering everything in public/)
    # -------------------------------------------------------------------------
    logging.info("Building search index")
    subprocess.run(["npx", "pagefind", "--site", STATIC_PATH, "--serve"])
    logging.info("Finished building search index")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process PDF -> HTML for multiple collections."
    )
    parser.add_argument(
        "--folder",
        type=str,
        default="all_files",
        choices=["zhlex_files", "ch_files", "all_files", "test_files"],
        help=(
            "Choose which collection(s) to build:\n"
            "'zhlex_files' (only ZH-Lex), "
            "'ch_files' (only FedLex), "
            "'all_files' (both), "
            "'test_files' (ZH test set only)."
        ),
    )
    parser.add_argument(
        "--db-build",
        type=str,
        default="yes",
        choices=["yes", "no"],
        help="Build dataset for processed collections",
    )
    parser.add_argument(
        "--placeholders",
        type=str,
        default="yes",
        choices=["yes", "no"],
        help="Create placeholders (ZH-Lex only).",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="concurrent",
        choices=["concurrent", "sequential"],
        help="Processing mode: concurrent (parallel) or sequential (for debugging)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of worker processes for concurrent mode (default: auto)",
    )
    args = parser.parse_args()

    logging.info(f"Script arguments: {args}")
    main(args.folder, args.db_build, args.placeholders, args.mode, args.workers)
