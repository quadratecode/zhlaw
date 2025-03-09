# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

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
ANNEX_KEYWORDS = ["Anhang", "Anhänge", "Verzeichnis", "Verzeichnisse"]


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
      - If the enum class is "enum-lit", assign "first-level".
      - Otherwise (e.g. "enum-ziff" or "enum-dash"):
          - If the previous enum paragraph exists and its enum class is the same,
            continue using its level.
          - Otherwise, assign "second-level".
    """
    paragraphs: List[Tag] = soup.find_all("p")
    prev_enum = None  # Will store a tuple (enum_class, level) for the last encountered enum paragraph

    for p in paragraphs:
        classes: List[str] = p.get("class", [])
        # Look for an enum class in the paragraph's classes.
        enum_classes = [cls for cls in classes if cls.startswith(ENUM_PREFIX)]
        if not enum_classes:
            continue  # Skip paragraphs that do not have an enum class

        # Assume one enum class per paragraph.
        current_enum = enum_classes[0]

        if current_enum == "enum-lit":
            # Always assign first-level for "enum-lit"
            current_level = "first-level"
        else:
            # For non-"enum-lit", check the preceding enum paragraph.
            if prev_enum is None:
                current_level = "second-level"
            else:
                prev_enum_class, prev_level = prev_enum
                if prev_enum_class == current_enum:
                    current_level = prev_level
                else:
                    current_level = "second-level"

        # Append the level to the paragraph's class list using the tag's attribute dictionary.
        p.attrs.setdefault("class", []).append(current_level)

        # Update the previous enum info.
        prev_enum = (current_enum, current_level)

    return soup


def add_footnote_line_and_class(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Inserts a horizontal line before the first footnote paragraph and gives it an id
    so that it can later serve as a marker.
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


def merge_other_conditions(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Merges consecutive paragraph (<p>) elements in the BeautifulSoup object based on specific conditions.

    A paragraph will be merged with its immediately preceding paragraph if all of the following are true:
      - The current paragraph does not have a 'class' attribute.
      - The previous paragraph does not have a 'class' attribute containing any of the excluded classes:
        'marginalia', 'provision', or 'subprovision'.
      - There is no heading element (<h1> to <h6>) between the previous and current paragraphs.
      - Either the first non-whitespace character of the current paragraph is one of ".,;()?:"
        OR the first character is lowercase and the last non-whitespace character of the previous paragraph
        is also lowercase.

    When merging, all child elements of the current paragraph are moved into the previous paragraph,
    preserving the HTML structure. The current paragraph is then removed. This process repeats iteratively
    until no further merges can be made.
    """
    # Find all paragraph elements in the BeautifulSoup object.
    paragraphs: List[Tag] = soup.find_all("p")

    # List to store paragraphs that have been merged and need removal.
    to_remove: List[Tag] = []

    # Set of classes that, if present in a paragraph, prevent merging.
    excluded_classes = {"marginalia", "provision", "subprovision"}

    # Flag to track whether a merge occurred in the current iteration.
    merged: bool = True

    while merged:
        merged = False
        # Refresh the list of paragraphs, as the DOM may have changed after previous merges.
        paragraphs = soup.find_all("p")
        to_remove.clear()

        # Iterate over paragraphs starting from the second one.
        for i in range(1, len(paragraphs)):
            current_p: Tag = paragraphs[i]
            prev_p: Tag = paragraphs[i - 1]

            # Only consider merging if the current paragraph has no class, and
            # the previous paragraph does not have an excluded class.
            if not current_p.has_attr("class") and not (
                prev_p.has_attr("class")
                and any(cls in excluded_classes for cls in prev_p["class"])
            ):
                # Check if there's any heading element (<h1> through <h6>) or table between prev_p and current_p.
                barrier_found = False
                next_element = prev_p.find_next()
                while next_element is not None and next_element != current_p:
                    if next_element.name in {
                        "h1",
                        "h2",
                        "h3",
                        "h4",
                        "h5",
                        "h6",
                        "table",
                    }:
                        barrier_found = True
                        break
                    next_element = next_element.find_next()
                # If a heading or table is found between the paragraphs, skip merging for this pair.
                if barrier_found:
                    continue

                # Determine the first non-whitespace character of the current paragraph.
                first_char = (
                    current_p.text.lstrip()[0] if current_p.text.lstrip() else ""
                )
                # Determine the last non-whitespace character of the previous paragraph.
                last_char_prev_p = (
                    prev_p.text.rstrip()[-1] if prev_p.text.rstrip() else ""
                )

                # Check if merging should occur based on punctuation or lowercase conditions.
                if first_char in ".,;()?:" or (
                    first_char.islower() and last_char_prev_p.islower()
                ):
                    # Transfer all child elements from the current paragraph to the previous paragraph.
                    for element in current_p.contents:
                        prev_p.append(element.extract())
                    # Mark the current paragraph for removal.
                    to_remove.append(current_p)
                    merged = True

        # Remove all paragraphs that have been merged into the previous ones.
        for p in to_remove:
            p.decompose()

    # Return the modified BeautifulSoup object with merged paragraphs.
    return soup


def wrap_annex(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Scans the document for the first heading (h1–h6) whose text contains any of the keywords:
    "Verzeichnis", "Anhänge", or "Anhang". From that heading onward,
    all elements (up to the element with id "footnote-line", if it exists) are wrapped into a
    <details> element with id "annex". A fixed <summary> element is created with the text
    "Anhänge" and at the top of the details block a new paragraph
    with id "annex-info" and text "annex_callout" is inserted.
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
    soup = merge_punctuation(soup)
    soup = merge_enum_paragraphs(soup)
    soup = assign_enum_level(soup)
    soup = merge_other_conditions(soup)
    soup = reduce_whitespace(soup)

    with open(html_file, "w", encoding="utf-8") as file:
        file.write(str(soup))


if __name__ == "__main__":
    # TODO: Allow command-line arguments
    pass
