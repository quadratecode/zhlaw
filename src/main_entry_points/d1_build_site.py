#!/usr/bin/env python3
"""
Static Site Generation Pipeline - Main Entry Point

This module generates the static website from processed law data:
1. Generates index pages for law collections
2. Processes HTML files from ZH-Lex and/or FedLex collections
3. Creates placeholder pages for missing documents
4. Builds markdown dataset for processed collections
5. Generates anchor maps for cross-referencing
6. Creates sitemaps for SEO
7. Copies static assets and deploys search functionality

Usage:
    python -m src.cmd.d1_build_site_main [options]

Options:
    --folder: Choose collections to build (zhlex_files, ch_files, all_files, test_files)
    --db-build: Build markdown dataset (yes/no)
    --placeholders: Create placeholder pages (yes/no)
    --mode: Processing mode (concurrent or sequential)
    --workers: Number of worker processes for concurrent mode

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import glob
import json

# from tqdm import tqdm  # Replaced with progress_utils
from src.utils.progress_utils import progress_manager, track_concurrent_futures
import shutil
import os
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
from src.modules.site_generator_module import generate_anchor_maps
from src.modules.general_module.asset_versioning import (
    AssetVersionManager,
    create_htaccess_rules,
)

# Import logging utilities
from src.utils.logging_decorators import configure_logging
from src.utils.logging_utils import get_module_logger

# Get logger for this module
logger = get_module_logger(__name__)

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
    html_file, collection_data_path, collection_path, law_origin, minify_output = args

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

        # Apply manual table corrections BEFORE marginalia processing (NEW)
        if file_type in ["old_html", "new_html"]:
            from src.modules.site_generator_module.build_correction_applier import (
                BuildCorrectionApplier, 
                extract_law_id_version_from_path, 
                folder_from_path
            )
            
            law_id, version = extract_law_id_version_from_path(html_file)
            if law_id and version:
                folder = folder_from_path(html_file)
                # Select base path based on law origin
                base_path = "data/zhlex" if law_origin == "zh" else "data/fedlex"
                correction_applier = BuildCorrectionApplier(base_path=base_path) 
                soup = correction_applier.apply_corrections_to_html(
                    soup, law_id, version, folder
                )
                logger.info(f"Applied manual table corrections for {law_id} v{version}")

        # Insert InfoBox and other final touches
        doc_info = metadata.get("doc_info", {})
        soup = build_zhlaw.main(
            soup, html_file, doc_info, file_type, law_origin=law_origin
        )

        # Create output folders if needed
        if not os.path.exists(collection_path):
            os.makedirs(collection_path, exist_ok=True)

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

        # Write final HTML with optional minification
        from src.utils.html_utils import write_html
        write_html(soup, new_file_path, encoding="utf-8", add_doctype=True, minify=minify_output)

        return True
    except Exception as e:
        logger.error(
            f"Error processing {html_file}: {e}",
            exc_info=True,
        )
        return False


def process_html_files_sequentially(
    html_files, collection_data_path, collection_path, law_origin, minify_output=True
):
    """
    Process HTML files sequentially for easier debugging.
    """
    error_counter = 0

    with progress_manager() as pm:
        counter = pm.create_counter(
            total=len(html_files),
            desc=f"Processing {len(html_files)} {law_origin} files sequentially",
            unit="files",
        )

        for html_file in html_files:
            success = process_html_file(
                (html_file, collection_data_path, collection_path, law_origin, minify_output)
            )
            if not success:
                error_counter += 1
            counter.update()

    return error_counter


def process_html_files_concurrently(
    html_files, collection_data_path, collection_path, law_origin, max_workers=None, minify_output=True
):
    """
    Process HTML files in parallel using ProcessPoolExecutor.
    """
    error_counter = 0
    # Create a list of argument tuples for the process_html_file function
    process_args = [
        (html_file, collection_data_path, collection_path, law_origin, minify_output)
        for html_file in html_files
    ]

    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        futures = [executor.submit(process_html_file, args) for args in process_args]

        # Track progress with enlighten-compatible progress bar
        results = []
        for future in track_concurrent_futures(
            futures,
            desc=f"Processing {len(process_args)} {law_origin} files concurrently",
            unit="files",
        ):
            results.append(future.result())

        # Count the number of failures
        error_counter = results.count(False)

    return error_counter


@configure_logging()
def main(
    folder_choice,
    dataset_trigger,
    placeholders_trigger,
    processing_mode,
    max_workers=None,
    minify_output=True,
):
    """
    Depending on `folder_choice`:
     - "all_test_files": process test files for both fedlex and zhlex
     - "fedlex_test_files": process test files only for fedlex
     - "zhlex_test_files": process test files only for zhlex
     - "all_main_files": process all files in both fedlex_files and zhlex_files
     - "zhlex_main_files": process all files in zhlex_files
     - "fedlex_main_files": process all files in fedlex_files
    """
    global STATIC_PATH, COLLECTION_PATH_ZH, COLLECTION_PATH_CH

    # Show the selected processing mode
    logger.info(f"Using processing mode: {processing_mode}")

    # Define the collection data paths
    COLLECTION_DATA_ZH = "data/zhlex/zhlex_data/zhlex_data_processed.json"
    COLLECTION_DATA_CH = "data/fedlex/fedlex_data/fedlex_data_processed.json"
    PLACEHOLDER_DIR_ZH = "data/zhlex/placeholders"  # Used only for ZH-Lex

    # Set the output directory based on folder_choice
    test_folders = ["all_test_files", "fedlex_test_files", "zhlex_test_files"]
    if folder_choice in test_folders:
        STATIC_PATH = "public_test/"
        COLLECTION_PATH_ZH = f"{STATIC_PATH}col-zh/"
        COLLECTION_PATH_CH = f"{STATIC_PATH}col-ch/"
        logger.info(f"Using test output directory: {STATIC_PATH}")
    else:
        STATIC_PATH = "public/"
        COLLECTION_PATH_ZH = f"{STATIC_PATH}col-zh/"
        COLLECTION_PATH_CH = f"{STATIC_PATH}col-ch/"
        logger.info(f"Using standard output directory: {STATIC_PATH}")

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
    ch_folder = None

    if folder_choice == "zhlex_main_files":
        process_zh = True
        zh_folder = "zhlex_files"
    elif folder_choice == "zhlex_test_files":
        process_zh = True
        zh_folder = "zhlex_files_test"
    elif folder_choice == "fedlex_main_files":
        process_ch = True
        ch_folder = "fedlex_files"
    elif folder_choice == "fedlex_test_files":
        process_ch = True
        ch_folder = "fedlex_files_test"
    elif folder_choice == "all_main_files":
        process_zh = True
        zh_folder = "zhlex_files"
        process_ch = True
        ch_folder = "fedlex_files"
    elif folder_choice == "all_test_files":
        process_zh = True
        zh_folder = "zhlex_files_test"
        process_ch = True
        ch_folder = "fedlex_files_test"

    # -------------------------------------------------------------------------
    # 1) Process static assets with versioning (before anything else)
    # -------------------------------------------------------------------------
    logger.info("Processing static assets with versioning")

    # Initialize asset version manager
    asset_manager = AssetVersionManager(
        source_dir="src/static_files/markup/", output_dir=STATIC_PATH, minify_assets=minify_output
    )

    # Process versionable assets (CSS, JS)
    version_map = asset_manager.process_versionable_assets()

    # Process non-versionable assets (images, fonts, etc.)
    non_versionable = asset_manager.process_non_versionable_assets()

    # Save version map for template processing
    asset_manager.save_version_map()

    # Set version map in build_zhlaw module for HTML processing
    build_zhlaw.set_version_map(version_map)

    # Create .htaccess with caching rules
    create_htaccess_rules(STATIC_PATH, version_map, non_versionable)

    logger.info(
        f"Processed {len(version_map)} versioned assets and {len(non_versionable)} non-versioned assets"
    )

    # -------------------------------------------------------------------------
    # 2) Process markdown content to HTML
    # -------------------------------------------------------------------------
    logger.info("Processing markdown content files")
    from src.modules.static_content_module.markdown_processor import MarkdownProcessor

    markdown_processor = MarkdownProcessor()
    markdown_content_dir = "src/static_files/content"
    markdown_output_dir = "src/static_files/html"

    # Only process if markdown content directory exists
    if os.path.exists(markdown_content_dir):
        markdown_processor.process_content_directory(
            markdown_content_dir, markdown_output_dir
        )
        logger.info("Finished processing markdown content files")
    else:
        logger.info("No markdown content directory found, skipping markdown processing")

    # -------------------------------------------------------------------------
    # 3) Generate index page
    # -------------------------------------------------------------------------
    if process_zh:
        # Generate full ZH index with systematic overview
        logger.info("Generating ZH index")
        generate_index.main(
            COLLECTION_DATA_ZH,
            "src/static_files/html/index.html",  # Template
            version_map=version_map,  # Pass version map for CSS versioning
        )
        logger.info("Finished generating ZH index")
    elif process_ch:
        # Generate minimal index for FedLex-only builds
        logger.info("Generating minimal index for FedLex")
        generate_index.generate_minimal_index(
            "src/static_files/html/index.html", version_map=version_map
        )
        logger.info("Finished generating minimal index")

    # -------------------------------------------------------------------------
    # 4) Process ZH-Lex HTML files (if requested)
    # -------------------------------------------------------------------------
    if process_zh and zh_folder:
        logger.info(f"Loading ZH-Lex HTML files from '{zh_folder}'")

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
            logger.info("No ZH-Lex files found. Proceeding anyway...")
        else:
            # Process files in chosen mode
            if processing_mode == "concurrent":
                error_counter_zh = process_html_files_concurrently(
                    html_files_zh,
                    COLLECTION_DATA_ZH,
                    COLLECTION_PATH_ZH,
                    law_origin="zh",
                    max_workers=max_workers,
                    minify_output=minify_output,
                )
            else:
                error_counter_zh = process_html_files_sequentially(
                    html_files_zh,
                    COLLECTION_DATA_ZH,
                    COLLECTION_PATH_ZH,
                    law_origin="zh",
                    minify_output=minify_output,
                )

            logger.info(f"ZH-Lex: encountered {error_counter_zh} errors.")

    # -------------------------------------------------------------------------
    # 5) Process FedLex HTML files (if requested)
    # -------------------------------------------------------------------------
    if process_ch and ch_folder:
        logger.info(f"Loading FedLex HTML files from '{ch_folder}'")

        html_files_ch_merged = glob.glob(
            f"data/fedlex/{ch_folder}/**/**/*-merged.html",
            recursive=True,
        )
        html_files_ch_orig = glob.glob(
            f"data/fedlex/{ch_folder}/**/**/*-original.html",
            recursive=True,
        )
        # Include site elements if not already processed by ZH
        if not process_zh:
            html_site_elements = glob.glob(
                "src/static_files/html/*.html",
                recursive=True,
            )
            html_files_ch = list(
                set(html_files_ch_merged + html_files_ch_orig + html_site_elements)
            )
        else:
            html_files_ch = list(set(html_files_ch_merged + html_files_ch_orig))

        if not html_files_ch:
            logger.info("No FedLex files found. Proceeding anyway...")
        else:
            # Process files in chosen mode
            if processing_mode == "concurrent":
                error_counter_ch = process_html_files_concurrently(
                    html_files_ch,
                    COLLECTION_DATA_CH,
                    COLLECTION_PATH_CH,
                    law_origin="ch",
                    max_workers=max_workers,
                    minify_output=minify_output,
                )
            else:
                error_counter_ch = process_html_files_sequentially(
                    html_files_ch,
                    COLLECTION_DATA_CH,
                    COLLECTION_PATH_CH,
                    law_origin="ch",
                    minify_output=minify_output,
                )

            logger.info(f"FedLex: encountered {error_counter_ch} errors.")

    # -------------------------------------------------------------------------
    # 6) Build MD datasets if requested (for whichever we processed)
    # -------------------------------------------------------------------------
    if dataset_trigger.lower() == "yes":
        if process_zh and zh_folder:
            logger.info(f"Building dataset for ZH-Lex (folder: {zh_folder})")
            build_markdown.main(
                f"data/zhlex/{zh_folder}",
                processing_mode=processing_mode,
                max_workers=max_workers,
                output_dir=STATIC_PATH,
            )
            logger.info("Finished building dataset for ZH-Lex")

        if process_ch and ch_folder:
            logger.info(f"Building dataset for FedLex (folder: {ch_folder}) ...")
            build_markdown.main(
                f"data/fedlex/{ch_folder}",
                processing_mode=processing_mode,
                max_workers=max_workers,
                output_dir=STATIC_PATH,
            )
            logger.info("Finished building dataset for FedLex")

    # -------------------------------------------------------------------------
    # 7) Create placeholders for ZH-Lex only if requested
    # -------------------------------------------------------------------------
    if placeholders_trigger.lower() == "yes" and process_zh:
        # Load ZH data
        with open(COLLECTION_DATA_ZH, "r", encoding="utf-8") as file:
            zhlex_data_processed = json.load(file)

        # Filter out versions that meet the filtering criteria to prevent placeholder generation
        zhlex_data_filtered = build_zhlaw.filter_law_versions(zhlex_data_processed)
        logger.info(f"Filtered ZH data for placeholders: {len(zhlex_data_processed)} -> {len(zhlex_data_filtered)} laws")

        # Collect all ZH public HTML files
        public_html_files_zh = glob.glob(
            os.path.join(COLLECTION_PATH_ZH, "*.html"),
            recursive=True,
        )

        logger.info("Creating placeholders for ZH-Lex")
        create_placeholders.main(
            zhlex_data_filtered, public_html_files_zh, PLACEHOLDER_DIR_ZH
        )
        logger.info("Finished creating placeholders for ZH-Lex")

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
    #     logger.info("Generating diffs for ZH-Lex")
    #     zh_diff_path = os.path.join(STATIC_PATH, "col-zh/diff")
    #     zh_diff_count = html_diff.main(
    #         COLLECTION_DATA_ZH,
    #         COLLECTION_PATH_ZH,
    #         zh_diff_path,
    #         law_origin="zh",
    #         processing_mode=processing_mode,
    #         max_workers=max_workers,
    #     )
    #     logger.info(f"Generated {zh_diff_count} diffs for ZH-Lex")

    # if process_ch:
    #     logger.info("Generating diffs for FedLex")
    #     ch_diff_path = os.path.join(STATIC_PATH, "col-ch/diff")
    #     ch_diff_count = html_diff.main(
    #         COLLECTION_DATA_CH,
    #         COLLECTION_PATH_CH,
    #         ch_diff_path,
    #         law_origin="ch",
    #         processing_mode=processing_mode,
    #         max_workers=max_workers,
    #     )
    #     logger.info(f"Generated {ch_diff_count} diffs for FedLex")

    # -------------------------------------------------------------------------
    # 8) Copy server scripts for local development
    # -------------------------------------------------------------------------
    # Copy router.php and unified redirect scripts for local development
    shutil.copy(
        "src/server_scripts/router.php",
        STATIC_PATH,
    )
    shutil.copy(
        "src/server_scripts/unified-redirect.php",
        STATIC_PATH,
    )
    shutil.copy(
        "src/server_scripts/unified-redirect-latest.php",
        STATIC_PATH,
    )

    # If ZH was processed, copy metadata for ZH
    if process_zh:
        shutil.copy(
            COLLECTION_DATA_ZH,
            os.path.join(STATIC_PATH, "collection-metadata-zh.json"),
        )

    # If FedLex was processed, copy metadata for CH
    if process_ch:
        shutil.copy(
            COLLECTION_DATA_CH,
            os.path.join(STATIC_PATH, "collection-metadata-ch.json"),
        )

    # -------------------------------------------------------------------------
    # 9) Generate anchor maps for processed collections
    # -------------------------------------------------------------------------
    if process_zh:
        logger.info("Generating anchor maps for ZH collection")
        # Load ZH collection data for anchor map generation
        with open(COLLECTION_DATA_ZH, "r", encoding="utf-8") as file:
            zh_collection_data = json.load(file)
        generate_anchor_maps.generate_anchor_maps_for_collection(
            STATIC_PATH,
            "col-zh",
            zh_collection_data,
            concurrent=(processing_mode == "concurrent"),
            max_workers=max_workers,
        )
        logger.info("Finished generating anchor maps for ZH collection")

    if process_ch:
        logger.info("Generating anchor maps for CH collection")
        # Load CH collection data for anchor map generation
        with open(COLLECTION_DATA_CH, "r", encoding="utf-8") as file:
            ch_collection_data = json.load(file)
        generate_anchor_maps.generate_anchor_maps_for_collection(
            STATIC_PATH,
            "col-ch",
            ch_collection_data,
            concurrent=(processing_mode == "concurrent"),
            max_workers=max_workers,
        )
        logger.info("Finished generating anchor maps for CH collection")

    # Generate anchor maps index for quick select
    logger.info("Generating anchor maps index")
    generate_anchor_maps.generate_anchor_maps_index(STATIC_PATH)
    logger.info("Finished generating anchor maps index")

    # -------------------------------------------------------------------------
    # 10) Generate a sitemap (covering everything under public/)
    # -------------------------------------------------------------------------
    logger.info("Generating sitemap")
    site_url = "https://zhlaw.ch"
    test_folders = ["all_test_files", "fedlex_test_files", "zhlex_test_files"]
    if folder_choice in test_folders:
        site_url = "https://test.zhlaw.ch"  # Use a different URL for test site
    generator = SitemapGenerator(site_url, STATIC_PATH)
    generator.save_sitemap(f"{STATIC_PATH}sitemap.xml")
    logger.info("Finished generating sitemap")

    # -------------------------------------------------------------------------
    # 11) Build Pagefind search index (covering everything in public/)
    # -------------------------------------------------------------------------
    logger.info("Building search index")
    subprocess.run(["npx", "pagefind", "--site", STATIC_PATH])
    logger.info("Finished building search index")

    # -------------------------------------------------------------------------
    # 12) Start PHP development server
    # -------------------------------------------------------------------------
    logger.info("Starting PHP development server at http://localhost:8000")
    logger.info("Press Ctrl+C to stop the server")
    os.chdir(STATIC_PATH)
    subprocess.run(["php", "-S", "localhost:8000", "router.php"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate static website from processed law collections"
    )
    
    # Standardized arguments (7 total)
    parser.add_argument(
        "--target",
        type=str,
        default="all_files",
        choices=[
            "all_files_test",
            "fedlex_files_test", 
            "zhlex_files_test",
            "all_files",
            "zhlex_files",
            "fedlex_files",
        ],
        help=(
            "Target collection(s) to build: "
            "'all_files_test' (test files for both), "
            "'fedlex_files_test' (fedlex test only), "
            "'zhlex_files_test' (zhlex test only), "
            "'all_files' (both collections), "
            "'zhlex_files' (zhlex only), "
            "'fedlex_files' (fedlex only) - default: all_files"
        ),
    )
    
    parser.add_argument(
        "--build-dataset",
        action="store_true",
        default=True,
        help="Build markdown dataset for processed collections (default: enabled)"
    )
    parser.add_argument(
        "--no-build-dataset",
        dest="build_dataset",
        action="store_false",
        help="Disable dataset building"
    )
    
    parser.add_argument(
        "--create-placeholders",
        action="store_true",
        default=True,
        help="Create placeholder pages for missing documents (ZH-Lex only, default: enabled)"
    )
    parser.add_argument(
        "--no-placeholders",
        dest="create_placeholders",
        action="store_false",
        help="Disable placeholder creation"
    )
    
    parser.add_argument(
        "--mode",
        choices=["concurrent", "sequential"],
        default="concurrent",
        help="Processing mode: concurrent (parallel) or sequential (for debugging) - default: concurrent"
    )
    
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of worker processes for concurrent mode (default: auto-detect)"
    )
    
    parser.add_argument(
        "--no-minify",
        action="store_true",
        help="Disable minification for debugging (pretty-print HTML and CSS)"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        default="info",
        help="Logging level - default: info"
    )
    args = parser.parse_args()
    
    # Map new target names to old folder names for backward compatibility
    target_map = {
        "all_files_test": "all_test_files",
        "fedlex_files_test": "fedlex_test_files",
        "zhlex_files_test": "zhlex_test_files", 
        "all_files": "all_main_files",
        "zhlex_files": "zhlex_main_files",
        "fedlex_files": "fedlex_main_files"
    }
    
    # Convert boolean flags to old yes/no format for compatibility
    db_build = "yes" if args.build_dataset else "no"
    placeholders = "yes" if args.create_placeholders else "no"
    minify_output = not args.no_minify  # Invert the logic
    
    # Setup logging (though main() might override this)
    import logging
    log_level_map = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR
    }
    logging.basicConfig(level=log_level_map[args.log_level])

    logger.info(f"Script arguments: {args}")
    main(target_map[args.target], db_build, placeholders, args.mode, args.workers, minify_output)
