# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

from bs4 import BeautifulSoup, NavigableString
import re


def clean_text(text):
    """
    Clean text by removing specific patterns like "- " for hyphenation.

    :param text: Text to clean
    :return: Cleaned text
    """
    return text.replace("- ", "")


def should_remove_paragraph(p):
    """
    Check if a paragraph should be removed based on criteria:
    1. Empty paragraphs
    2. Paragraphs containing only superscript

    :param p: BeautifulSoup paragraph element
    :return: Boolean indicating if paragraph should be removed
    """
    # Check if paragraph is empty
    if not p.get_text().strip():
        return True

    # Check if paragraph contains only superscript
    sup_tags = p.find_all("sup")
    if sup_tags and len(p.get_text().strip()) == len(
        "".join(sup.get_text() for sup in sup_tags)
    ):
        return True

    return False


def is_numbered_paragraph(text):
    """
    Check if paragraph starts with roman numeral, arabic numeral, or letter followed by period.

    :param text: Text to check
    :return: Boolean indicating if text matches the pattern
    """
    # Remove leading whitespace
    text = text.strip()

    # Roman numerals pattern (I. II. III. IV. V. etc.)
    roman_pattern = r"^[IVXLC]+\."

    # Arabic numerals pattern (1. 2. 3. etc.)
    arabic_pattern = r"^\d+\."

    # Single letter pattern (a. b. c. A. B. C. etc.)
    letter_pattern = r"^[a-zA-Z]\."

    # Combine patterns
    combined_pattern = f"({roman_pattern}|{arabic_pattern}|{letter_pattern})"

    return bool(re.match(combined_pattern, text))


def are_paragraphs_adjacent(p1, p2, vertical_threshold=10):
    """
    Check if two paragraphs should be considered adjacent based on their positions.

    :param p1: First paragraph data
    :param p2: Second paragraph data
    :param vertical_threshold: Maximum vertical distance to consider paragraphs adjacent
    :return: Boolean indicating if paragraphs should be merged
    """
    # Check if paragraphs are on the same page
    if p1["page"] != p2["page"]:
        return False

    # Check if paragraphs start at the same vertical position
    if (
        abs(p1["top"] - p2["top"]) < 0.1
    ):  # Small threshold for floating point comparison
        return True

    # Check if paragraphs are within vertical threshold
    if abs(p2["top"] - p1["bottom"]) < vertical_threshold:
        return True

    return False


def merge_paragraphs(soup, vertical_threshold=2):
    """
    Merge paragraphs in a BeautifulSoup object that are on the same page and whose vertical distance
    is less than the specified threshold. Adds an additional space between merged paragraphs.
    Updates their positional attributes and returns the modified soup.

    :param soup: BeautifulSoup object containing the paragraphs
    :param vertical_threshold: The vertical distance threshold for merging paragraphs
    :return: Modified BeautifulSoup object with merged paragraphs
    """
    # First, remove paragraphs that match removal criteria
    paragraphs = soup.find_all("p")
    for p in paragraphs:
        if should_remove_paragraph(p):
            p.decompose()

    # Get remaining paragraphs after removal
    paragraphs = soup.find_all("p")
    current_paragraph = None

    for p in paragraphs:
        # Extracting positional attributes
        data = {
            "element": p,
            "page": int(p["data-page-count"]),
            "bottom": float(p["data-vertical-position-bottom"]),
            "top": float(p["data-vertical-position-top"]),
            "left": float(p["data-vertical-position-left"]),
            "right": float(p["data-vertical-position-right"]),
        }

        # Get the text content
        current_text = data["element"].get_text().strip()

        # If there's no current paragraph or if current paragraph starts with a number/letter,
        # set it as the current paragraph and continue
        if not current_paragraph or is_numbered_paragraph(current_text):
            current_paragraph = data
            continue

        # Check if paragraphs should be merged
        if are_paragraphs_adjacent(current_paragraph, data, vertical_threshold):
            # Get the text from the next paragraph and clean it
            next_text = clean_text(data["element"].get_text())

            # Append the cleaned text, separated by a space, to the current paragraph
            current_paragraph["element"].append(
                " "
            )  # Add a space before appending text
            current_paragraph["element"].append(NavigableString(next_text))
            current_paragraph["element"].append(BeautifulSoup("<br/>", "html.parser"))

            # Update the bottom position
            current_paragraph["bottom"] = data["bottom"]

            # Remove the merged paragraph from the soup
            data["element"].decompose()
        else:
            # If paragraphs are not close enough, move to the new paragraph
            current_paragraph = data

    return soup


def main(html_file_marginalia):
    # Read and parse the HTML file
    with open(html_file_marginalia, "r", encoding="utf-8") as file:
        soup = BeautifulSoup(file, "html.parser")

    # Merge paragraphs
    merged_paragraphs = merge_paragraphs(soup)

    # Save to file
    with open(html_file_marginalia, "w", encoding="utf-8") as file:
        file.write(str(merged_paragraphs))


if __name__ == "__main__":
    main()
