"""
Module for generating HTML diffs between consecutive versions of laws.
Uses the htmldiff library to create diffs, then applies proper styling and structure.
"""

import os
import logging
import json
from bs4 import BeautifulSoup
import htmldiff.lib as diff_lib
import shutil

# Set up logging
logger = logging.getLogger(__name__)


def find_consecutive_versions(collection_data_path):
    """
    Read the collection data and find consecutive versions of each law.

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

        # Create pairs of consecutive versions
        version_pairs = []
        for i in range(1, len(sorted_versions)):
            older_version = sorted_versions[i - 1]
            newer_version = sorted_versions[i]
            version_pairs.append(
                (
                    newer_version.get("nachtragsnummer"),
                    older_version.get("nachtragsnummer"),
                )
            )

        if version_pairs:
            law_versions[ordnungsnummer] = version_pairs

    return law_versions


def generate_diff(html1_path, html2_path, accurate_mode=True):
    """
    Generate a diff between two HTML files using the htmldiff library.

    Args:
        html1_path: Path to the older HTML file
        html2_path: Path to the newer HTML file
        accurate_mode: Whether to use accurate mode in htmldiff

    Returns:
        The diffed HTML as a string, or None if an error occurred
    """
    try:
        # Extract just the content part from both HTML files
        with open(html1_path, "r", encoding="utf-8") as f:
            html1 = f.read()

        with open(html2_path, "r", encoding="utf-8") as f:
            html2 = f.read()

        # Extract the law content only (between certain div tags)
        soup1 = BeautifulSoup(html1, "html.parser")
        soup2 = BeautifulSoup(html2, "html.parser")

        # Find the law content divs
        law_div1 = soup1.find("div", id="source-text")
        law_div2 = soup2.find("div", id="source-text")

        if not law_div1 or not law_div2:
            logger.error(
                f"Could not find source-text content in {html1_path} or {html2_path}"
            )
            return None

        # Get just the content of the law divs
        law_html1 = str(law_div1)
        law_html2 = str(law_div2)

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

                # Start with a copy of the newer version's HTML
                shutil.copy(html2_path, output_path)

                # Open the copy and replace content
                with open(output_path, "r", encoding="utf-8") as f:
                    html = f.read()

                soup = BeautifulSoup(html, "html.parser")

                # Update the title
                title_tag = soup.title
                if title_tag:
                    erlasstitel = title_tag.string
                    title_tag.string = f"Diff: {erlasstitel} ({ordnungsnummer}-{older_version} → {newer_version})"

                # Replace the source-text content with the diffed content
                source_text_div = soup.find("div", id="source-text")
                if source_text_div:
                    # First, add an explanation of the diff colors above the source text
                    explanation = soup.new_tag(
                        "div",
                        **{
                            "class": "diff-explanation",
                            "style": "margin-bottom: 20px; padding: 10px; border: 1px solid #ccc;",
                        },
                    )
                    explanation.string = "Änderungen: "

                    # Add color examples
                    insert_example = soup.new_tag(
                        "span",
                        **{
                            "class": "insert",
                            "style": "background-color: #AFA; padding: 2px 5px;",
                        },
                    )
                    insert_example.string = "Grün = hinzugefügt"
                    explanation.append(insert_example)

                    explanation.append(" | ")

                    delete_example = soup.new_tag(
                        "span",
                        **{
                            "class": "delete",
                            "style": "background-color: #F88; text-decoration: line-through; padding: 2px 5px;",
                        },
                    )
                    delete_example.string = "Rot = entfernt"
                    explanation.append(delete_example)

                    # Add a header with version info
                    content_div = soup.find("div", **{"class": "content"})
                    if content_div:
                        # Insert after the first h1 if it exists
                        h1 = content_div.find("h1")
                        if h1:
                            # Update the heading text
                            h1.string = f"Änderungen: {h1.get_text()}"

                            # Add a subheading with version info
                            subheading = soup.new_tag("h2")
                            subheading.string = (
                                f"Version {older_version} → {newer_version}"
                            )
                            h1.insert_after(subheading)
                            subheading.insert_after(explanation)
                        else:
                            # If no h1, just add at the top of content
                            content_div.insert(0, explanation)

                    # Replace the source-text with diffed content
                    source_text_div.clear()
                    diff_soup = BeautifulSoup(diffed_html, "html.parser")
                    source_text_div.append(diff_soup)

                # Save the modified file
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(str(soup))

                success_count += 1
                logger.info(
                    f"Generated diff for {ordnungsnummer} ({older_version} -> {newer_version})"
                )

        except Exception as e:
            logger.error(
                f"Error generating diff for {ordnungsnummer} ({older_version} -> {newer_version}): {e}"
            )

    return success_count


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

    # Process each law
    total_success = 0
    for ordnungsnummer, version_pairs in law_versions.items():
        success_count = generate_law_diffs(
            (ordnungsnummer, version_pairs, collection_path, diff_path, law_origin)
        )
        total_success += success_count

    return total_success


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
    import concurrent.futures
    from tqdm import tqdm

    # Find consecutive versions
    law_versions = find_consecutive_versions(collection_data_path)

    # Create the diff directory
    os.makedirs(diff_path, exist_ok=True)

    # Prepare arguments for parallel processing
    process_args = [
        (ordnungsnummer, version_pairs, collection_path, diff_path, law_origin)
        for ordnungsnummer, version_pairs in law_versions.items()
    ]

    # Process in parallel
    total_success = 0
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Map the generate_law_diffs function to all laws and wrap with tqdm for progress bar
        results = list(
            tqdm(
                executor.map(generate_law_diffs, process_args),
                total=len(process_args),
                desc=f"Processing {law_origin} diffs concurrently",
            )
        )

        # Sum up the number of successful diffs
        total_success = sum(results)

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
