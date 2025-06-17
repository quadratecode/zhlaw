"""Module for merging marginalia paragraphs in legal HTML documents.

This module processes HTML documents to intelligently merge marginalia (side notes) that
have been split across multiple paragraphs during PDF extraction. It uses positional data
and text patterns to determine which paragraphs should be merged together.

Key features:
- Merges adjacent marginalia paragraphs based on positional data
- Handles split text from hyphenation at line breaks
- Preserves numbered lists and enumeration patterns
- Removes empty or superscript-only paragraphs
- Maintains proper spacing and text flow
- Uses configurable thresholds for adjacency detection

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

from bs4 import BeautifulSoup, NavigableString
import re
from typing import Any, Dict

# -----------------------------------------------------------------------------
# Module-Level Constants
# -----------------------------------------------------------------------------
DATA_PAGE_COUNT = "data-page-count"
DATA_VERTICAL_POSITION_BOTTOM = "data-vertical-position-bottom"
DATA_VERTICAL_POSITION_TOP = "data-vertical-position-top"
DATA_VERTICAL_POSITION_LEFT = "data-vertical-position-left"
DATA_VERTICAL_POSITION_RIGHT = "data-vertical-position-right"

DEFAULT_VERTICAL_THRESHOLD: int = 10  # Used in are_paragraphs_adjacent
FLOAT_COMPARE_THRESHOLD: float = 0.1  # For small floating point differences
MERGE_VERTICAL_THRESHOLD: int = 2  # Vertical threshold for merging paragraphs

# Precompiled regex pattern to check for numbered paragraphs (Roman, Arabic, or single letter)
COMBINED_PATTERN = re.compile(r"^(?:[IVXLC]+\.)|^(?:\d+\.)|^(?:[a-zA-Z]\.)")


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------
def clean_text(text: str) -> str:
    """
    Clean text by removing specific patterns like "- " for hyphenation.

    :param text: Text to clean.
    :return: Cleaned text.
    """
    return text.replace("- ", "")


def should_remove_paragraph(p: Any) -> bool:
    """
    Determine if a paragraph should be removed based on:
    1. Being empty.
    2. Containing only superscript text.

    :param p: BeautifulSoup paragraph element.
    :return: True if the paragraph should be removed, False otherwise.
    """
    # Remove if paragraph is empty.
    if not p.get_text().strip():
        return True

    # Remove if paragraph contains only superscript content.
    sup_tags = p.find_all("sup")
    if sup_tags and len(p.get_text().strip()) == len(
        "".join(sup.get_text() for sup in sup_tags)
    ):
        return True

    return False


def is_numbered_paragraph(text: str) -> bool:
    """
    Check if the text starts with a roman numeral, arabic numeral, or a letter followed by a period.

    :param text: Text to check.
    :return: True if text matches the pattern, False otherwise.
    """
    text = text.strip()
    return bool(COMBINED_PATTERN.match(text))


def are_paragraphs_adjacent(
    p1: Dict[str, float],
    p2: Dict[str, float],
    vertical_threshold: float = DEFAULT_VERTICAL_THRESHOLD,
) -> bool:
    """
    Check if two paragraphs should be considered adjacent based on their positional data.

    :param p1: Positional data of the first paragraph.
    :param p2: Positional data of the second paragraph.
    :param vertical_threshold: Maximum vertical distance to consider paragraphs adjacent.
    :return: True if paragraphs are adjacent, False otherwise.
    """
    if p1["page"] != p2["page"]:
        return False

    # Check if paragraphs start at almost the same vertical position.
    if abs(p1["top"] - p2["top"]) < FLOAT_COMPARE_THRESHOLD:
        return True

    # Check if the vertical gap is within the threshold.
    if abs(p2["top"] - p1["bottom"]) < vertical_threshold:
        return True

    return False


def extract_positional_data(p: Any) -> Dict[str, float]:
    """
    Extract positional attributes from a BeautifulSoup paragraph tag.

    :param p: BeautifulSoup paragraph element.
    :return: Dictionary with positional data.
    """
    return {
        "element": p,
        "page": int(p.get(DATA_PAGE_COUNT)),
        "bottom": float(p.get(DATA_VERTICAL_POSITION_BOTTOM)),
        "top": float(p.get(DATA_VERTICAL_POSITION_TOP)),
        "left": float(p.get(DATA_VERTICAL_POSITION_LEFT)),
        "right": float(p.get(DATA_VERTICAL_POSITION_RIGHT)),
    }


# -----------------------------------------------------------------------------
# Core Functionality
# -----------------------------------------------------------------------------
def merge_paragraphs(
    soup: BeautifulSoup, vertical_threshold: float = MERGE_VERTICAL_THRESHOLD
) -> BeautifulSoup:
    """
    Merge paragraphs in the BeautifulSoup object that are on the same page and
    whose vertical distance is less than the specified threshold. A space is added
    between merged paragraphs and a line break is appended.

    :param soup: BeautifulSoup object containing paragraph elements.
    :param vertical_threshold: The vertical distance threshold for merging.
    :return: Modified BeautifulSoup object with merged paragraphs.
    """
    # Remove paragraphs that meet the removal criteria.
    paragraphs = soup.find_all("p")
    for p in paragraphs:
        if should_remove_paragraph(p):
            p.decompose()

    # Retrieve remaining paragraphs.
    paragraphs = soup.find_all("p")
    current_paragraph = None

    for p in paragraphs:
        data = extract_positional_data(p)
        current_text = data["element"].get_text().strip()

        # Start a new current paragraph if none exists or if the paragraph starts with a numbered pattern.
        if not current_paragraph or is_numbered_paragraph(current_text):
            current_paragraph = data
            continue

        # If paragraphs are adjacent, merge the current paragraph with the new one.
        if are_paragraphs_adjacent(current_paragraph, data, vertical_threshold):
            next_text = clean_text(data["element"].get_text())
            # Append a space, the cleaned text, and a line break to the current paragraph.
            current_paragraph["element"].append(" ")
            current_paragraph["element"].append(NavigableString(next_text))
            current_paragraph["element"].append(soup.new_tag("br"))
            # Update the bottom position of the current paragraph.
            current_paragraph["bottom"] = data["bottom"]
            # Remove the merged paragraph from the soup.
            data["element"].decompose()
        else:
            # Move to the new paragraph if not adjacent.
            current_paragraph = data

    return soup


def main(html_file_marginalia: str) -> None:
    """
    Read, process, and save the HTML file by merging adjacent paragraphs.

    :param html_file_marginalia: Path to the HTML file.
    """
    with open(html_file_marginalia, "r", encoding="utf-8") as file:
        soup = BeautifulSoup(file, "html.parser")

    merged_paragraphs = merge_paragraphs(soup)

    with open(html_file_marginalia, "w", encoding="utf-8") as file:
        file.write(str(merged_paragraphs))


if __name__ == "__main__":
    # TODO: Allow command-line arguments
    pass
