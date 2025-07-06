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

from bs4 import BeautifulSoup
import re
from typing import Any, Dict, List
from src.constants import Patterns

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
MERGE_VERTICAL_THRESHOLD: int = 5  # Vertical threshold for grouping paragraphs

# Compile all enumeration patterns from constants
ENUM_PATTERNS = [
    re.compile(Patterns.ENUM_LETTER_PERIOD),
    re.compile(Patterns.ENUM_NUMBER_PERIOD),
    re.compile(Patterns.ENUM_ROMAN_PERIOD),
    re.compile(Patterns.ENUM_ROMAN_SMALL_PERIOD),
    re.compile(Patterns.ENUM_LETTER_PAREN),
    re.compile(Patterns.ENUM_NUMBER_PAREN),
    re.compile(Patterns.ENUM_ROMAN_PAREN)
]

# Pattern to find enum markers anywhere in text (not anchored to start)
# Uses word boundaries to ensure matches are standalone words, not substrings
ENUM_SPLIT_PATTERN = re.compile(r"(?<!\w)([IVXLCDM]+|[ivxlcdm]+|[a-zA-Z]|\d+)[\.\)](\s+)")


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------
def clean_text(text: str) -> str:
    """
    Clean text by removing hyphenation patterns.
    Removes hyphens between lowercase letters (e.g., "Justiz-verwaltung" -> "Justizverwaltung").
    Also removes hyphens at word boundaries when not followed by "und" or "oder".

    :param text: Text to clean.
    :return: Cleaned text.
    """
    # Remove hyphens between lowercase letters
    text = re.sub(r"([a-z])-([a-z])", r"\1\2", text)
    
    # Remove hyphenation where word ends with hyphen but is not followed by "und" or "oder"
    # Pattern: word- space(s) lowercase_word (but not "und" or "oder")
    text = re.sub(r"(\w)-\s+(?!(?:und|oder)\b)([a-z]\w*)", r"\1\2", text)
    
    return text


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
    try:
        if p is None or not hasattr(p, "get") or not hasattr(p, "attrs"):
            return None

        return {
            "element": p,
            "page": int(p.get(DATA_PAGE_COUNT) or 0),
            "bottom": float(p.get(DATA_VERTICAL_POSITION_BOTTOM) or 0),
            "top": float(p.get(DATA_VERTICAL_POSITION_TOP) or 0),
            "left": float(p.get(DATA_VERTICAL_POSITION_LEFT) or 0),
            "right": float(p.get(DATA_VERTICAL_POSITION_RIGHT) or 0),
        }
    except (AttributeError, TypeError, ValueError):
        return None


# -----------------------------------------------------------------------------
# Container Functions
# -----------------------------------------------------------------------------
def create_marginalia_container(soup: BeautifulSoup, paragraphs: List[Any]) -> Any:
    """
    Creates a marginalia container div that wraps the given paragraphs
    and combines their positional data.

    :param soup: BeautifulSoup object for creating new elements
    :param paragraphs: List of paragraph elements to wrap
    :return: Container div with combined positional data
    """
    if not paragraphs:
        return None

    # Create the container div
    container = soup.new_tag("div", **{"class": "marginalia-container"})

    # Calculate combined positional data
    page_numbers = set()
    top_positions = []
    bottom_positions = []
    left_positions = []
    right_positions = []

    for p in paragraphs:
        page_numbers.add(int(p.get(DATA_PAGE_COUNT)))
        top_positions.append(float(p.get(DATA_VERTICAL_POSITION_TOP)))
        bottom_positions.append(float(p.get(DATA_VERTICAL_POSITION_BOTTOM)))
        left_positions.append(float(p.get(DATA_VERTICAL_POSITION_LEFT)))
        right_positions.append(float(p.get(DATA_VERTICAL_POSITION_RIGHT)))

    # Use the page from the first paragraph (should all be the same page)
    container[DATA_PAGE_COUNT] = str(list(page_numbers)[0])

    # Combined bounds: minimum top, maximum bottom, minimum left, maximum right
    container[DATA_VERTICAL_POSITION_TOP] = str(min(top_positions))
    container[DATA_VERTICAL_POSITION_BOTTOM] = str(max(bottom_positions))
    container[DATA_VERTICAL_POSITION_LEFT] = str(min(left_positions))
    container[DATA_VERTICAL_POSITION_RIGHT] = str(max(right_positions))

    return container


def group_paragraphs_by_proximity(
    paragraphs: List[Any], vertical_threshold: float
) -> List[List[Any]]:
    """
    Groups paragraphs by vertical proximity only.

    :param paragraphs: List of paragraph elements
    :param vertical_threshold: Maximum vertical distance for grouping
    :return: List of groups, each group is a list of paragraphs
    """
    if not paragraphs:
        return []

    # Sort paragraphs by page and vertical position
    sorted_paragraphs = []
    for p in paragraphs:
        data = extract_positional_data(p)
        if data:
            sorted_paragraphs.append(data)

    if not sorted_paragraphs:
        return []

    sorted_paragraphs.sort(key=lambda x: (x["page"], x["top"]))

    groups = []
    current_group = [sorted_paragraphs[0]["element"]]

    for i in range(1, len(sorted_paragraphs)):
        current = sorted_paragraphs[i]
        previous = sorted_paragraphs[i - 1]

        # Check if they should be grouped using adjacency logic
        if are_paragraphs_adjacent(previous, current, vertical_threshold):
            current_group.append(current["element"])
        else:
            # Start new group
            groups.append(current_group)
            current_group = [current["element"]]

    # Add last group
    groups.append(current_group)
    return groups


def wrap_group_in_container(soup: BeautifulSoup, group: List[Any]) -> None:
    """
    Wraps a group of paragraphs in a marginalia-container div.

    :param soup: BeautifulSoup object
    :param group: List of paragraph elements to wrap
    """
    if not group:
        return

    container = create_marginalia_container(soup, group)
    if container:
        # Insert container before first paragraph
        group[0].insert_before(container)

        # Move all paragraphs into container
        for p in group:
            container.append(p)


def merge_paragraphs_with_smart_spacing(container: Any) -> None:
    """
    Merges all paragraphs within a container with smart spacing.
    Adds whitespace between merged elements EXCEPT if preceding paragraph ends with "-" 
    or following paragraph starts with "-".

    :param container: Container to process
    """
    paragraphs = container.find_all("p", recursive=False)
    if len(paragraphs) <= 1:
        return

    # Collect all text
    texts = []
    for p in paragraphs:
        texts.append(p.get_text())

    # Merge with smart spacing
    merged_text = texts[0]
    for i in range(1, len(texts)):
        current = texts[i]

        # Check if we need spacing - no space if preceding ends with "-" (with optional whitespace) 
        # or current starts with "-" (with optional whitespace)
        if merged_text.rstrip().endswith("-") or current.lstrip().startswith("-"):
            # No space needed - remove any existing whitespace and merge
            merged_text = merged_text.rstrip() + current.lstrip()
        else:
            # Add space
            merged_text += " " + current

    # Keep first paragraph, remove others
    first_p = paragraphs[0]
    for p in paragraphs[1:]:
        p.decompose()

    # Update first paragraph with merged text
    first_p.clear()
    first_p.string = merged_text


def split_paragraphs_with_enum(container: Any, soup: BeautifulSoup) -> None:
    """
    Splits paragraphs that contain enum patterns into separate paragraphs.
    Splits at any enum pattern that's not at the start of the paragraph (ignoring whitespace).
    Handles multiple consecutive splits within the same paragraph.

    :param container: Container to process
    :param soup: BeautifulSoup object for creating new elements
    """
    paragraphs = container.find_all("p", recursive=False)

    for p in paragraphs:
        text = p.get_text()

        # Find all enum pattern matches
        matches = list(ENUM_SPLIT_PATTERN.finditer(text))
        
        # Filter out matches that are at the start of the paragraph (ignoring whitespace)
        stripped_text = text.lstrip()
        text_start_offset = len(text) - len(stripped_text)
        
        split_matches = []
        for match in matches:
            # Check if match is at the start (accounting for leading whitespace)
            if match.start() > text_start_offset:
                split_matches.append(match)
        
        # Split at each match that's not at the start, working backwards to preserve positions
        if split_matches:
            current_p = p
            
            # Process matches in reverse order to maintain correct splitting positions
            for match in reversed(split_matches):
                current_text = current_p.get_text()
                
                # Split at the enum pattern (include the enum marker in the second part)
                before = current_text[:match.start()].rstrip()
                after = current_text[match.start():]

                if before:  # Only split if there's text before
                    # Update current paragraph with before text
                    current_p.clear()
                    current_p.string = before

                    # Create new paragraph with after text
                    new_p = soup.new_tag("p")
                    new_p.string = after
                    current_p.insert_after(new_p)
                    
                    # Continue with the new paragraph for potential further splits
                    current_p = new_p


def clean_hyphenation_in_container(container: Any) -> None:
    """
    Final hyphenation cleanup for all paragraphs in container.

    :param container: Container to process
    """
    paragraphs = container.find_all("p", recursive=False)
    for p in paragraphs:
        text = p.get_text()
        cleaned_text = clean_text(text)
        if text != cleaned_text:
            p.clear()
            p.string = cleaned_text


def ensure_marginalia_class(container: Any) -> None:
    """
    Ensures all paragraphs in container have .marginalia class.

    :param container: Container to process
    """
    paragraphs = container.find_all("p", recursive=False)
    for p in paragraphs:
        classes = p.get("class", [])
        if "marginalia" not in classes:
            classes.append("marginalia")
            p["class"] = classes


# -----------------------------------------------------------------------------
# Core Functionality
# -----------------------------------------------------------------------------
def merge_paragraphs(
    soup: BeautifulSoup, vertical_threshold: float = MERGE_VERTICAL_THRESHOLD
) -> BeautifulSoup:
    """
    Process marginalia using a clean, step-by-step approach:
    1. Remove bad paragraphs
    2. Group paragraphs by vertical proximity only
    3. Wrap all groups (and singles) in marginalia-container divs
    4. For each container: merge with smart spacing, split on enum, cleanup, ensure .marginalia class

    :param soup: BeautifulSoup object containing paragraph elements.
    :param vertical_threshold: The vertical distance threshold for grouping.
    :return: Modified BeautifulSoup object with marginalia containers.
    """
    # Step 1: Remove bad paragraphs
    paragraphs = soup.find_all("p")
    for p in paragraphs:
        if should_remove_paragraph(p):
            p.decompose()

    # Step 2: Group paragraphs by vertical proximity
    paragraphs = list(soup.find_all("p"))
    groups = group_paragraphs_by_proximity(paragraphs, vertical_threshold)

    # Step 3: Wrap all groups in containers
    for group in groups:
        wrap_group_in_container(soup, group)

    # Step 4: Process each container
    containers = soup.find_all("div", class_="marginalia-container")
    for container in containers:
        # Step 4a: Merge paragraphs with smart spacing
        merge_paragraphs_with_smart_spacing(container)

        # Step 4b: Split if enum pattern found
        split_paragraphs_with_enum(container, soup)

        # Step 4c: Final cleanup
        clean_hyphenation_in_container(container)

        # Step 4d: Ensure .marginalia class
        ensure_marginalia_class(container)

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
