"""
Module for cleaning and post-processing HTML files generated from law PDFs.

This module provides functionality to:
- Clean up whitespace and formatting issues
- Merge fragmented elements (punctuation, fractions, enumerations)
- Handle footnotes and annotations
- Wrap annexes in semantic containers
- Remove unwanted attributes from HTML elements
- Normalize heading structures

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

from bs4 import BeautifulSoup, NavigableString, Tag
import string
import re
from typing import List
import sys

# -----------------------------------------------------------------------------
# Module-Level Constants
# -----------------------------------------------------------------------------
FOOTNOTE_CLASS = "footnote"
ENUM_PREFIX = "enum-"
EXCLUDED_MERGE_CLASSES = {"marginalia", "provision", "subprovision"}
FOOTNOTE_LINE_ID = "footnote-line"
ANNEX_KEYWORDS = ["Anhang", "Anhänge"]


# -----------------------------------------------------------------------------
# Functions
# -----------------------------------------------------------------------------
def reduce_whitespace(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Clean up extra whitespace in each text node of <p> tags without stripping leading/trailing spaces.
    """
    elements: List[Tag] = soup.find_all("p")
    for element in elements:
        # Process each direct string child of the paragraph
        for content in element.contents:
            if isinstance(content, NavigableString) and content.string is not None:
                # Replace multiple whitespace with a single space.
                cleaned_text = re.sub(r"\s+", " ", content.string)
                content.replace_with(cleaned_text)
    return soup


def merge_punctuation(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Merges consecutive paragraphs that contain only punctuation characters (excluding "...")
    with the previous paragraph.
    """
    paragraphs: List[Tag] = soup.find_all("p")
    i: int = 1
    while i < len(paragraphs):
        current_paragraph: Tag = paragraphs[i]
        previous_paragraph: Tag = paragraphs[i - 1]

        current_text: str = (
            current_paragraph.get_text(strip=True) if current_paragraph else ""
        )

        if (
            current_text
            and all(char in string.punctuation for char in current_text)
            and "..." not in current_text
        ):
            preserved_content = current_paragraph.decode_contents()
            # Check if the content appears to contain markup
            if "<" in preserved_content and ">" in preserved_content:
                new_content = BeautifulSoup(preserved_content, "html.parser")
                previous_paragraph.append(new_content)
            else:
                previous_paragraph.append(NavigableString(preserved_content))
            current_paragraph.decompose()
            paragraphs = soup.find_all("p")
        else:
            i += 1

    return soup


def assign_enum_level(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Assigns enumeration levels to paragraphs with enum classes.

    For paragraphs with a class starting with "enum-":
      - The first enum type encountered after a non-enum paragraph establishes the first level.
      - Subsequent different types are considered second level.
    """
    paragraphs: List[Tag] = soup.find_all("p")
    first_level_type = None

    for p in paragraphs:
        classes: List[str] = p.get("class", [])
        enum_classes = [cls for cls in classes if cls.startswith(ENUM_PREFIX)]

        if not enum_classes:
            # Not an enum paragraph, so reset for the next list
            first_level_type = None
            continue

        current_enum_type = enum_classes[0]

        if first_level_type is None:
            first_level_type = current_enum_type

        if current_enum_type == first_level_type:
            level_class = "first-level"
        else:
            level_class = "second-level"

        if level_class not in classes:
            p.attrs.setdefault("class", []).append(level_class)

    return soup


def add_footnote_line_and_class(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Inserts a horizontal line before the first footnote paragraph and gives it an id
    so that it can later serve as a marker.
    TODO: Move style to CSS file.
    """
    footnote_paragraphs: List[Tag] = soup.find_all("p", class_=FOOTNOTE_CLASS)
    if footnote_paragraphs:
        first_footnote: Tag = footnote_paragraphs[0]
        hr_tag: Tag = soup.new_tag(
            "hr", style="border: 0; border-top: 2px solid #ccc; margin-top: 20px;"
        )
        first_footnote.insert_before(hr_tag)
        hr_tag["id"] = FOOTNOTE_LINE_ID
    return soup


def merge_enum_paragraphs(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Merges paragraphs with the 'enum' class with the immediately following paragraph,
    preserving all HTML tags.
    """
    pattern = re.compile(r"enum-(lit|ziff|dash)")

    def match_classes(tag: Tag) -> bool:
        if tag.name == "p" and tag.has_attr("class"):
            return any(pattern.match(cls) for cls in tag["class"])
        return False

    enum_paragraphs: List[Tag] = soup.find_all(match_classes)
    for enum_p in enum_paragraphs:
        next_p = enum_p.find_next_sibling("p")
        if next_p:
            for element in next_p.contents:
                enum_p.append(" ")  # Insert a space before appending the next element
                enum_p.append(element)
            next_p.decompose()
    return soup


def remove_whitespace_around_subsup(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Removes whitespace between regular text and superscript/subscript elements.
    Preserves or adds whitespace after a sub/sup element if it's followed by normal text.
    Works on paragraphs and table cells without a class attribute.
    Args:
        soup: BeautifulSoup object containing the HTML to process

    Returns:
        Modified BeautifulSoup object
    """
    # Process all sup and sub tags directly
    for tag in soup.find_all(["sup", "sub"]):
        # Check if the tag is in a suitable parent
        parent = tag.parent
        if not parent or parent.name not in ["p", "td", "th"] or parent.get("class"):
            continue

        # Remove whitespace before the tag
        prev = tag.previous_sibling
        while prev and isinstance(prev, NavigableString) and prev.strip() == "":
            # Store the previous sibling before removing
            temp = prev.previous_sibling
            prev.extract()
            prev = temp

        # Check if the previous sibling ends with whitespace
        if prev and isinstance(prev, NavigableString) and str(prev).endswith(" "):
            prev.replace_with(str(prev).rstrip())

        # Handle whitespace after the tag
        next_sib = tag.next_sibling

        # Check if there's any content after this tag
        has_content_after = False
        temp_next = next_sib
        while temp_next:
            if isinstance(temp_next, NavigableString):
                if temp_next.strip():
                    has_content_after = True
                    break
            elif temp_next.name not in ["sup", "sub"]:
                has_content_after = True
                break
            temp_next = temp_next.next_sibling

        if has_content_after:
            # There is normal text after this tag - we need to ensure there's exactly one space

            # First, remove any empty whitespace nodes
            while (
                next_sib
                and isinstance(next_sib, NavigableString)
                and next_sib.strip() == ""
            ):
                temp = next_sib.next_sibling
                next_sib.extract()
                next_sib = temp

            # If next sibling exists and is text
            if next_sib and isinstance(next_sib, NavigableString):
                # If it starts with whitespace, leave it
                if str(next_sib).lstrip() != str(next_sib):
                    pass  # Keep existing whitespace
                else:
                    # No whitespace - insert a space
                    tag.insert_after(" ")
            else:
                # No immediate text node - insert a space
                tag.insert_after(" ")
        else:
            # No normal text after, just other sub/sup tags or nothing
            # We can remove whitespace here
            while (
                next_sib
                and isinstance(next_sib, NavigableString)
                and next_sib.strip() == ""
            ):
                temp = next_sib.next_sibling
                next_sib.extract()
                next_sib = temp

    return soup


def merge_other_conditions(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Merges consecutive paragraph (<p>) elements based on specific conditions.
    Processes one merge at a time to handle complex chains correctly.
    """
    excluded_classes = {"marginalia", "provision", "subprovision"}
    barrier_tags = {"h1", "h2", "h3", "h4", "h5", "h6", "table"}
    merge_chars = ".,;()?:-"  # Added dash to the merge characters

    changes_made = True
    while changes_made:
        # Reset the flag
        changes_made = False

        # Get fresh list of paragraphs after any DOM changes
        paragraphs = soup.find_all("p")

        # Examine consecutive paragraph pairs
        for i in range(1, len(paragraphs)):
            current_p = paragraphs[i]
            prev_p = paragraphs[i - 1]

            # Skip if classes prevent merging
            if current_p.has_attr("class") or (
                prev_p.has_attr("class")
                and any(cls in excluded_classes for cls in prev_p["class"])
            ):
                continue

            # Check for barriers between paragraphs
            barrier_found = False
            element = prev_p.find_next()
            while element and element != current_p:
                if element.name in barrier_tags:
                    barrier_found = True
                    break
                element = element.find_next()

            if barrier_found:
                continue

            # Get text for character checks
            current_text = current_p.get_text(strip=True)
            prev_text = prev_p.get_text(strip=True)

            if not current_text or not prev_text:
                continue

            first_char = current_text[0]
            last_char_prev = prev_text[-1]

            # Check if paragraph starts with sup or sub tag
            starts_with_sup_sub = False
            if current_p.contents and current_p.contents[0].name in ["sup", "sub"]:
                starts_with_sup_sub = True

            # Check merge conditions (added the sup/sub condition)
            if (
                first_char in merge_chars
                or (first_char.islower() and last_char_prev.islower())
                or starts_with_sup_sub
            ):

                # Add space before merging
                prev_p.append(" ")

                # Move all content from current paragraph to previous paragraph
                for element in list(current_p.contents):
                    prev_p.append(element.extract())

                # Remove the now-empty paragraph
                current_p.decompose()

                # Mark that we made a change and break to restart with fresh paragraphs
                changes_made = True
                break

    return soup


# -----------------------------------------------------------------------------
# Fraction Processing
# -----------------------------------------------------------------------------
def merge_fractions(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Merges fraction components (numerator, slash, denominator) into a single paragraph.
    Looks for paragraphs containing <numerator> tags followed by paragraphs with
    either &frasl; entity or the Unicode fraction slash character ⁄, followed by
    paragraphs with <denominator> tags, and combines them into a single paragraph.
    """
    # Find all paragraphs that contain numerator tags
    paragraphs = soup.find_all("p")
    i = 0

    while i < len(paragraphs) - 2:  # Need at least 3 elements for a complete fraction
        current_p = paragraphs[i]
        numerator_tag = current_p.find("numerator")

        if numerator_tag:
            # Check if the next paragraph contains the fraction slash (either entity or Unicode char)
            next_p = paragraphs[i + 1]
            next_p_text = next_p.get_text()
            is_fraction_slash = (
                "&frasl;" in str(next_p) or "⁄" in next_p_text or "/" in next_p_text
            )

            if is_fraction_slash:
                # Check if the next paragraph after that contains a denominator
                next_next_p = paragraphs[i + 2]
                denominator_tag = next_next_p.find("denominator")

                if denominator_tag:
                    # We found a complete fraction pattern, merge them

                    # Extract the content from all three paragraphs
                    numerator_content = str(numerator_tag)
                    slash_content = "&frasl;"  # Always use the HTML entity in output
                    denominator_content = str(denominator_tag)

                    # Create a new paragraph with the merged content
                    merged_content = (
                        f"{numerator_content}{slash_content}{denominator_content}"
                    )

                    # Clear the current paragraph and add the merged content
                    current_p.clear()
                    current_p.append(BeautifulSoup(merged_content, "html.parser"))

                    # Remove the now-merged paragraphs
                    next_p.decompose()
                    next_next_p.decompose()

                    # Update paragraph list since we've modified the DOM
                    paragraphs = soup.find_all("p")
                    continue

        i += 1

    return soup


def merge_isolated_elements(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Merges isolated elements (sub/sup tags or fractions) with their adjacent paragraphs.

    Handles two cases:
    1. Paragraphs containing a single sub/sup tag without any classes
    2. Paragraphs containing only a fraction (numerator + fraction slash + denominator)

    Inserts spaces between the merged elements to maintain readability.

    Examples:
    <p>Text before</p>
    <p><sup>2</sup></p>
    <p>Text after</p>

    Becomes:
    <p>Text before <sup>2</sup> Text after</p>

    <p>Text before</p>
    <p><numerator>1</numerator>⁄<denominator>1020</denominator></p>
    <p>Text after</p>

    Becomes:
    <p>Text before <numerator>1</numerator>⁄<denominator>1020</denominator> Text after</p>

    Args:
        soup: BeautifulSoup object containing the HTML to process

    Returns:
        Modified BeautifulSoup object with merged paragraphs
    """
    changes_made = True
    while changes_made:
        changes_made = False

        # Get a fresh list of paragraphs after any DOM changes
        paragraphs = soup.find_all("p")

        for i in range(len(paragraphs)):
            # Safety check in case list length changed
            if i >= len(paragraphs):
                break

            p = paragraphs[i]

            # Get all non-whitespace content nodes
            content_nodes = []
            for child in p.children:
                if isinstance(child, NavigableString):
                    if child.strip():  # If non-empty after stripping
                        content_nodes.append(child)
                else:
                    content_nodes.append(child)

            # Case 1: Check for isolated sub/sup tags
            if (
                len(content_nodes) == 1
                and content_nodes[0].name in ["sub", "sup"]
                and not content_nodes[0].get("class")
            ):

                isolated_element = content_nodes[0]
                merge_with_adjacent_paragraphs(p, isolated_element, soup)
                changes_made = True
                break

            # Case 2: Check for isolated fractions
            elif is_isolated_fraction(content_nodes):
                # For fractions, we want to extract the entire paragraph content
                # to preserve the structure of numerator, slash, and denominator
                merge_with_adjacent_paragraphs(p, p, soup, extract_children=False)
                changes_made = True
                break

    return soup


def merge_consecutive_h1_headings(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Merges the first instance of consecutive h1 headings (2 or more) in the document.
    Consecutive means the h1 elements are adjacent with no other elements between them.
    Preserves any child tags within the merged headings.
    """
    # Find all h1 elements
    h1_elements = soup.find_all("h1")

    # Check if we have at least two h1 elements
    if len(h1_elements) < 2:
        return soup

    # Find the first set of consecutive h1 elements
    for i, h1 in enumerate(h1_elements[:-1]):
        current_h1 = h1
        next_sibling = current_h1.next_sibling

        # Skip any whitespace or empty text nodes
        while (
            next_sibling
            and isinstance(next_sibling, NavigableString)
            and not next_sibling.strip()
        ):
            next_sibling = next_sibling.next_sibling

        # Check if the next sibling is an h1 element
        if next_sibling and next_sibling.name == "h1":
            # We found consecutive h1 elements
            # First, add a space to the first h1
            current_h1.append(" ")

            # Move all contents from the second h1 to the first h1
            while next_sibling.contents:
                current_h1.append(next_sibling.contents[0])

            # Remove the second h1
            next_sibling.decompose()

            # Check if there are more consecutive h1 elements
            continue_merging = True
            while continue_merging:
                next_sibling = current_h1.next_sibling

                # Skip any whitespace or empty text nodes
                while (
                    next_sibling
                    and isinstance(next_sibling, NavigableString)
                    and not next_sibling.strip()
                ):
                    next_sibling = next_sibling.next_sibling

                if next_sibling and next_sibling.name == "h1":
                    # Add a space before appending content
                    current_h1.append(" ")

                    # Move all contents from the next h1 to the first h1
                    while next_sibling.contents:
                        current_h1.append(next_sibling.contents[0])

                    # Remove the next h1
                    next_sibling.decompose()
                else:
                    # No more consecutive h1 elements
                    continue_merging = False

            # We've merged the first set of consecutive h1 elements, so we're done
            break

    return soup


def is_isolated_fraction(content_nodes):
    """
    Check if the content nodes represent an isolated fraction.
    A fraction consists of a numerator tag, a fraction slash, and a denominator tag.

    Args:
        content_nodes: List of content nodes from a paragraph

    Returns:
        True if the nodes represent an isolated fraction, False otherwise
    """
    if len(content_nodes) < 3:
        return False

    # Look for numerator and denominator tags
    has_numerator = any(
        getattr(node, "name", "") == "numerator" for node in content_nodes
    )
    has_denominator = any(
        getattr(node, "name", "") == "denominator" for node in content_nodes
    )

    # Look for fraction slash (could be ⁄, / or &frasl;)
    has_slash = any(
        (isinstance(node, NavigableString) and ("/" in node or "⁄" in node))
        or (
            not isinstance(node, NavigableString)
            and ("/" in node.get_text() or "⁄" in node.get_text())
        )
        for node in content_nodes
    )

    # Check if there's nothing else in the paragraph except the fraction components
    total_nodes = len(content_nodes)
    fraction_nodes = sum([has_numerator, has_denominator, has_slash])

    # It's a fraction if we have all components and not much else
    return (
        has_numerator
        and has_denominator
        and has_slash
        and (total_nodes <= fraction_nodes + 1)
    )


def merge_with_adjacent_paragraphs(p, element_to_merge, soup, extract_children=True):
    """
    Merges an element with its adjacent paragraphs.

    Args:
        p: The paragraph containing the element
        element_to_merge: The element to merge (either a tag or the whole paragraph)
        soup: The BeautifulSoup object
        extract_children: If True, extract children. If False, use the element as-is

    Returns:
        None (modifies the soup in-place)
    """
    # Find adjacent paragraphs
    prev_p = p.find_previous("p")
    next_p = p.find_next("p")

    # Handle the three cases
    if prev_p and next_p:
        # We have both previous and next paragraphs

        # First extract the element if needed
        if extract_children:
            element_to_merge.extract()

        # Add to previous paragraph with spaces
        prev_p.append(" ")
        if extract_children:
            prev_p.append(element_to_merge)
        else:
            # Copy all children to preserve structure
            for child in list(p.children):
                prev_p.append(child.extract())

        prev_p.append(" ")

        # Add content from next paragraph
        for child in list(next_p.children):
            prev_p.append(child.extract())

        # Remove empty paragraphs
        p.decompose()
        next_p.decompose()

    elif prev_p:
        # Only have previous paragraph
        prev_p.append(" ")

        if extract_children:
            element_to_merge.extract()
            prev_p.append(element_to_merge)
        else:
            # Copy all children
            for child in list(p.children):
                prev_p.append(child.extract())

        p.decompose()

    elif next_p:
        # Only have next paragraph
        # Insert at the beginning of next paragraph
        if extract_children:
            element_to_merge.extract()
            next_p.insert(0, element_to_merge)
        else:
            # Copy all children in reverse order to preserve original order
            children = list(p.children)
            for child in reversed(children):
                next_p.insert(0, child.extract())

        next_p.insert(1, " ")
        p.decompose()


def wrap_annex(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Scans the document for the first heading (h1–h6) whose text contains any of the keywords:
    "Verzeichnis", "Anhänge", or "Anhang". From that heading onward,
    all elements (up to the element with id "footnote-line", if it exists) are wrapped into a
    <details> element with id "annex". A fixed <summary> element is created with the text
    "Anhänge".
    """
    keywords = ANNEX_KEYWORDS
    headings: List[Tag] = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    start_heading: Tag = None  # type: ignore
    for heading in headings:
        if any(keyword.lower() in heading.get_text().lower() for keyword in keywords):
            start_heading = heading
            break

    if not start_heading:
        return soup

    details: Tag = soup.new_tag("details", id="annex")
    summary: Tag = soup.new_tag("summary")
    summary.string = "Anhänge"
    details.append(summary)

    # Insert the details element in place of the start_heading.
    start_heading.insert_before(details)

    # Move the start_heading and all subsequent siblings (until the element with id "footnote-line")
    # into the <details> element.
    current = details.next_sibling
    while current:
        # Stop if we reach an element with id "footnote-line"
        if (
            getattr(current, "name", None) is not None
            and current.get("id") == "footnote-line"
        ):
            break
        next_node = current.next_sibling
        details.append(current.extract())
        current = next_node

    return soup


def remove_unwanted_attributes(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Removes a predefined list of data attributes from all tags.
    """
    unwanted_attributes = [
        "data-vertical-position-bottom",
        "data-vertical-position-top",
        "data-vertical-position-left",
        "data-vertical-position-right",
        "data-page-count",
        "data-font-family",
        "data-font-size",
        "data-font-weight",
        "law-data-table",
        "data-num-type",
        "data-page",
        "data-element-id",
        "law-data-table-id",
    ]
    for attr in unwanted_attributes:
        tags: List[Tag] = soup.find_all(attrs={attr: True})
        for tag in tags:
            del tag[attr]
    return soup


def main(html_file: str) -> None:
    with open(html_file, "r", encoding="utf-8") as file:
        soup: BeautifulSoup = BeautifulSoup(file, "html.parser")

    # Process the HTML with the various functions.
    soup = add_footnote_line_and_class(soup)
    soup = wrap_annex(soup)
    soup = remove_unwanted_attributes(soup)
    soup = merge_fractions(soup)
    soup = merge_punctuation(soup)
    soup = merge_enum_paragraphs(soup)
    soup = merge_consecutive_h1_headings(soup)
    soup = assign_enum_level(soup)
    soup = merge_other_conditions(soup)
    soup = merge_isolated_elements(soup)
    soup = reduce_whitespace(soup)
    soup = remove_whitespace_around_subsup(soup)

    with open(html_file, "w", encoding="utf-8") as file:
        file.write(str(soup))


if __name__ == "__main__":
    # TODO: Allow command-line arguments
    pass
