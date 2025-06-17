"""
Module for generating HTML diffs between consecutive versions of laws.
Uses the htmldiff library to create diffs, then applies proper styling and structure.

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import os
import logging
import json
from bs4 import BeautifulSoup
import htmldiff.lib as diff_lib
import shutil
import concurrent.futures
from tqdm import tqdm

# Set up logging
logger = logging.getLogger(__name__)


def find_consecutive_versions(collection_data_path):
    """
    Read the collection data and find consecutive versions of each law.
    Limited to only the 3 most recent versions to reduce processing time.

    Args:
        collection_data_path: Path to the collection metadata JSON file

    Returns:
        A dictionary mapping law ordnungsnummer to a list of version pairs
        Each pair is (newer_version, older_version)
    """
    try:
        with open(collection_data_path, "r", encoding="utf-8") as f:
            collection_data = json.load(f)
    except Exception as e:
        logger.error(f"Error reading collection data from {collection_data_path}: {e}")
        return {}

    # Dictionary to store version pairs for each law
    law_versions = {}

    # Counters for logging
    total_full_version_pairs = 0
    total_limited_version_pairs = 0
    laws_with_reduced_pairs = 0

    for law in collection_data:
        ordnungsnummer = law.get("ordnungsnummer")
        if not ordnungsnummer:
            continue

        versions = law.get("versions", [])
        if not versions:
            continue

        # Sort versions by nachtragsnummer
        try:
            # First try to sort by numeric_nachtragsnummer_float if available
            if any("numeric_nachtragsnummer_float" in v for v in versions):
                sorted_versions = sorted(
                    versions,
                    key=lambda v: v.get("numeric_nachtragsnummer_float", 0),
                    reverse=False,
                )  # Ascending order (oldest first)
            # Fall back to sorting by nachtragsnummer
            else:
                sorted_versions = sorted(
                    versions, key=lambda v: v.get("nachtragsnummer", ""), reverse=False
                )
        except Exception as e:
            logger.error(f"Error sorting versions for {ordnungsnummer}: {e}")
            continue

        # Count all possible version pairs (before limiting)
        all_version_pairs = []
        for i in range(1, len(sorted_versions)):
            older_version = sorted_versions[i - 1]
            newer_version = sorted_versions[i]
            all_version_pairs.append(
                (
                    newer_version.get("nachtragsnummer"),
                    older_version.get("nachtragsnummer"),
                )
            )

        total_full_version_pairs += len(all_version_pairs)

        # Limit to the 3 most recent versions to reduce processing time
        # For diffing only the latest version (newest compared to previous):
        # recent_versions = sorted_versions[-2:] if len(sorted_versions) >= 2 else sorted_versions
        # Current setting - diff the 3 most recent versions (2 comparisons):
        # recent_versions = sorted_versions[-3:] if len(sorted_versions) >= 3 else sorted_versions
        # For diffing all versions (no limit):
        # recent_versions = sorted_versions  # No slicing means use all versions
        recent_versions = (
            sorted_versions[-3:] if len(sorted_versions) >= 3 else sorted_versions
        )

        # Create pairs of consecutive versions from the recent versions only
        version_pairs = []
        for i in range(1, len(recent_versions)):
            older_version = recent_versions[i - 1]
            newer_version = recent_versions[i]
            version_pairs.append(
                (
                    newer_version.get("nachtragsnummer"),
                    older_version.get("nachtragsnummer"),
                )
            )

        total_limited_version_pairs += len(version_pairs)

        # Count laws where we reduced the number of pairs
        if len(version_pairs) < len(all_version_pairs):
            laws_with_reduced_pairs += 1

        if version_pairs:
            law_versions[ordnungsnummer] = version_pairs

    # Log the reduction stats
    diff_reduction = total_full_version_pairs - total_limited_version_pairs
    percentage = (
        (diff_reduction / total_full_version_pairs * 100)
        if total_full_version_pairs > 0
        else 0
    )

    logger.info(f"Diff reduction statistics:")
    logger.info(f"  - Total laws with version pairs: {len(law_versions)}")
    logger.info(f"  - Laws with reduced version pairs: {laws_with_reduced_pairs}")
    logger.info(f"  - Original diff pairs: {total_full_version_pairs}")
    logger.info(f"  - Limited diff pairs: {total_limited_version_pairs}")
    logger.info(f"  - Reduction: {diff_reduction} diffs ({percentage:.1f}%)")

    return law_versions


def generate_diff(html1_path, html2_path, accurate_mode=True):
    try:
        # Read files - but extract only the law content div directly with regex
        with open(html1_path, "r", encoding="utf-8") as f:
            html1 = f.read()
        with open(html2_path, "r", encoding="utf-8") as f:
            html2 = f.read()

        # Extract only the content div using regex (much faster than BeautifulSoup)
        import re

        content_pattern = re.compile(r'<div id="source-text".*?>(.*?)</div>', re.DOTALL)

        match1 = content_pattern.search(html1)
        match2 = content_pattern.search(html2)

        if not match1 or not match2:
            # Fall back to BeautifulSoup if regex doesn't match
            soup1 = BeautifulSoup(html1, "html.parser")
            soup2 = BeautifulSoup(html2, "html.parser")
            law_div1 = soup1.find("div", id="source-text")
            law_div2 = soup2.find("div", id="source-text")
            law_html1 = str(law_div1)
            law_html2 = str(law_div2)
        else:
            law_html1 = match1.group(1)
            law_html2 = match2.group(1)

        # Generate the diff
        diffed_html = diff_lib.diff_strings(law_html1, law_html2, accurate_mode)
        return diffed_html
    except Exception as e:
        logger.error(f"Error generating diff: {e}")
        return None


def generate_law_diffs(args):
    """
    Generate diffs for all consecutive versions of a law.
    This function is designed to be called from both sequential and parallel processors.

    Args:
        args: Tuple containing (ordnungsnummer, version_pairs, collection_path, diff_path, law_origin)

    Returns:
        Number of successfully generated diffs
    """
    ordnungsnummer, version_pairs, collection_path, diff_path, law_origin = args

    success_count = 0
    for newer_version, older_version in version_pairs:
        try:
            # Construct file paths
            html1_path = os.path.join(
                collection_path, f"{ordnungsnummer}-{older_version}.html"
            )
            html2_path = os.path.join(
                collection_path, f"{ordnungsnummer}-{newer_version}.html"
            )
            output_path = os.path.join(
                diff_path, f"{ordnungsnummer}-{older_version}-diff-{newer_version}.html"
            )

            # Skip if both input files don't exist
            if not (os.path.exists(html1_path) and os.path.exists(html2_path)):
                logger.warning(
                    f"Skipping diff for {ordnungsnummer} ({older_version} -> {newer_version}): Input files missing"
                )
                continue

            # Generate diff
            diffed_html = generate_diff(html1_path, html2_path, accurate_mode=True)

            if diffed_html:
                # Create diff directory if it doesn't exist
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                # Extract title from newer version
                with open(html2_path, "r", encoding="utf-8") as f:
                    newer_soup = BeautifulSoup(f.read(), "html.parser")
                    erlasstitel = ""
                    title_tag = newer_soup.title
                    if title_tag:
                        erlasstitel = title_tag.string

                # Create minimal HTML structure for diff file
                diff_soup = BeautifulSoup("<!DOCTYPE html>", "html.parser")

                # Create html element
                html_tag = diff_soup.new_tag("html")
                diff_soup.append(html_tag)

                # Create minimal head with only charset and title
                head = diff_soup.new_tag("head")
                html_tag.append(head)

                # Add charset meta
                charset_meta = diff_soup.new_tag("meta", charset="utf-8")
                head.append(charset_meta)

                # Add title
                title = diff_soup.new_tag("title")
                title.string = f"Diff: {erlasstitel} ({ordnungsnummer}-{older_version} → {newer_version})"
                head.append(title)

                # Create body
                body = diff_soup.new_tag("body")
                html_tag.append(body)

                # Create main-container div
                main_container = diff_soup.new_tag("div", **{"class": "main-container"})
                body.append(main_container)

                # Create content div
                content_div = diff_soup.new_tag("div", **{"class": "content"})
                main_container.append(content_div)

                # Add heading
                h1 = diff_soup.new_tag("h1")
                h1.string = f"Änderungen: {erlasstitel}"
                content_div.append(h1)

                # Add subheading with version info
                subheading = diff_soup.new_tag("h2")
                subheading.string = f"Version {older_version} → {newer_version}"
                content_div.append(subheading)

                # Add explanation of diff colors
                explanation = diff_soup.new_tag(
                    "div",
                    **{
                        "class": "diff-explanation",
                        "style": "margin-bottom: 20px; padding: 10px; border: 1px solid #ccc;",
                    },
                )
                explanation.string = "Änderungen: "

                # Add color examples
                insert_example = diff_soup.new_tag(
                    "span",
                    **{
                        "class": "insert",
                        "style": "background-color: #AFA; padding: 2px 5px;",
                    },
                )
                insert_example.string = "Grün = hinzugefügt"
                explanation.append(insert_example)

                explanation.append(" | ")

                delete_example = diff_soup.new_tag(
                    "span",
                    **{
                        "class": "delete",
                        "style": "background-color: #F88; text-decoration: line-through; padding: 2px 5px;",
                    },
                )
                delete_example.string = "Rot = entfernt"
                explanation.append(delete_example)

                content_div.append(explanation)

                # Create law div
                law_div = diff_soup.new_tag("div", id="law")
                content_div.append(law_div)

                # Create source-text div and add diffed content
                source_div = diff_soup.new_tag(
                    "div", id="source-text", **{"class": "pdf-source"}
                )
                law_div.append(source_div)

                # Add the diffed HTML content
                diff_content = BeautifulSoup(diffed_html, "html.parser")
                source_div.append(diff_content)

                # Save the diff file
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(str(diff_soup))

                success_count += 1
                logger.info(
                    f"Generated diff for {ordnungsnummer} ({older_version} -> {newer_version})"
                )

        except Exception as e:
            logger.error(
                f"Error generating diff for {ordnungsnummer} ({older_version} -> {newer_version}): {e}"
            )

    return success_count


def process_all_diffs_concurrently(
    collection_data_path, collection_path, diff_path, law_origin, max_workers=None
):
    """
    Process diffs in parallel using ProcessPoolExecutor.

    Args:
        collection_data_path: Path to the collection metadata JSON
        collection_path: Path to the HTML files
        diff_path: Path to store the diffs
        law_origin: Origin of the laws ('zh' or 'ch')
        max_workers: Maximum number of worker processes

    Returns:
        Total number of successfully generated diffs
    """

    # Find consecutive versions
    law_versions = find_consecutive_versions(collection_data_path)

    # Create the diff directory
    os.makedirs(diff_path, exist_ok=True)

    # Count total diffs for better progress reporting
    total_diffs = sum(len(pairs) for pairs in law_versions.values())
    logger.info(f"Processing {total_diffs} diffs for {len(law_versions)} laws")

    # Process laws with less than 4 version pairs sequentially for efficiency
    small_law_results = []
    large_laws = {}

    for ordnungsnummer, version_pairs in law_versions.items():
        if len(version_pairs) <= 3:  # Process small laws directly
            count = generate_law_diffs(
                (ordnungsnummer, version_pairs, collection_path, diff_path, law_origin)
            )
            small_law_results.append(count)
        else:
            large_laws[ordnungsnummer] = version_pairs

    # Only use parallel processing for laws with many diffs
    if large_laws:
        # Prepare arguments for parallel processing
        process_args = [
            (ordnungsnummer, version_pairs, collection_path, diff_path, law_origin)
            for ordnungsnummer, version_pairs in large_laws.items()
        ]

        large_law_diffs = sum(len(pairs) for pairs in large_laws.values())

        # Process in parallel
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=max_workers
        ) as executor:
            # Map the generate_law_diffs function to complex laws and wrap with tqdm for progress bar
            results = list(
                tqdm(
                    executor.map(generate_law_diffs, process_args),
                    total=len(process_args),
                    desc=f"Processing {large_law_diffs} diffs for {len(large_laws)} complex laws ({law_origin})",
                )
            )
            large_law_results = results
    else:
        large_law_results = []

    # Calculate total success count
    total_success = sum(small_law_results) + sum(large_law_results)
    logger.info(
        f"Successfully generated {total_success} of {total_diffs} diffs for {law_origin}"
    )

    return total_success


def process_all_diffs_sequentially(
    collection_data_path, collection_path, diff_path, law_origin
):
    """
    Process diffs sequentially for easier debugging.

    Args:
        collection_data_path: Path to the collection metadata JSON
        collection_path: Path to the HTML files
        diff_path: Path to store the diffs
        law_origin: Origin of the laws ('zh' or 'ch')

    Returns:
        Total number of successfully generated diffs
    """
    # Find consecutive versions
    law_versions = find_consecutive_versions(collection_data_path)

    # Create the diff directory
    os.makedirs(diff_path, exist_ok=True)

    # Count total diffs for better progress reporting
    all_pairs = []
    for ordnungsnummer, version_pairs in law_versions.items():
        for pair in version_pairs:
            all_pairs.append((ordnungsnummer, pair))

    total_diffs = len(all_pairs)
    logger.info(
        f"Processing {total_diffs} diffs for {len(law_versions)} laws sequentially"
    )

    # Process each diff with a progress bar
    total_success = 0

    for i, (ordnungsnummer, pair) in enumerate(
        tqdm(all_pairs, desc=f"Processing {law_origin} diffs")
    ):
        version_pairs = [
            pair
        ]  # Just process one pair at a time for better progress reporting
        success_count = generate_law_diffs(
            (ordnungsnummer, version_pairs, collection_path, diff_path, law_origin)
        )
        total_success += success_count

    logger.info(
        f"Successfully generated {total_success} of {total_diffs} diffs for {law_origin}"
    )
    return total_success


def main(
    collection_data_path,
    collection_path,
    diff_path,
    law_origin,
    processing_mode,
    max_workers=None,
):
    """
    Main entry point for generating diffs for a collection of laws.

    Args:
        collection_data_path: Path to the collection metadata JSON
        collection_path: Path to the HTML files
        diff_path: Path to store the diffs
        law_origin: Origin of the laws ('zh' or 'ch')
        processing_mode: 'concurrent' or 'sequential'
        max_workers: Maximum number of worker processes (for concurrent mode)

    Returns:
        Total number of successfully generated diffs
    """
    logger.info(f"Generating diffs for {law_origin} laws ({processing_mode} mode)")

    # Process either sequentially or concurrently based on the mode
    if processing_mode == "concurrent":
        return process_all_diffs_concurrently(
            collection_data_path, collection_path, diff_path, law_origin, max_workers
        )
    else:
        return process_all_diffs_sequentially(
            collection_data_path, collection_path, diff_path, law_origin
        )
