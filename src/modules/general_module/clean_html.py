# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

from bs4 import BeautifulSoup, NavigableString
import string
import re


def reduce_whitespace(soup):
    elements = soup.find_all("p")
    for element in elements:
        # Process each direct string child of the paragraph
        for content in element.contents:
            if isinstance(content, NavigableString):
                # Clean up spaces in the text node directly without stripping leading/trailing spaces
                cleaned_text = re.sub(r"\s+", " ", content.string)
                content.replace_with(cleaned_text)

    return soup


def merge_punctuation(soup):
    """
    Merges consecutive paragraphs that contain only punctuation characters (excluding "...") with the previous paragraph.

    Args:
        soup (BeautifulSoup): The BeautifulSoup object representing the HTML document.

    Returns:
        BeautifulSoup: The modified BeautifulSoup object with merged paragraphs.
    """
    paragraphs = soup.find_all("p")
    i = 1
    while i < len(paragraphs):
        current_paragraph = paragraphs[i]
        previous_paragraph = paragraphs[i - 1]

        current_text = (
            current_paragraph.get_text(strip=True) if current_paragraph else ""
        )

        # Check if the current paragraph contains only punctuation ("..." excluded for revised paragraphs)
        if (
            current_text
            and all(char in string.punctuation for char in current_text)
            and "..." not in current_text
        ):
            # Merge the current paragraph with the previous one
            preserved_content = current_paragraph.encode_contents()
            previous_paragraph.append(BeautifulSoup(preserved_content, "html.parser"))

            # Remove the current paragraph
            current_paragraph.decompose()

            # Update the paragraphs list as the structure has changed
            paragraphs = soup.find_all("p")
        else:
            i += 1

    return soup


def add_footnote_line_and_class(soup):
    """
    Insert a vertical line above the first footnote occurrence and assign the class 'footnote'
    to all paragraphs with an id matching 'footnote-<number>'.

    Args:
        soup (BeautifulSoup): The BeautifulSoup object representing the HTML document.

    Returns:
        BeautifulSoup: The modified BeautifulSoup object with footnotes styled.
    """
    # Find all paragraphs with class footnote
    footnote_paragraphs = soup.find_all("p", class_="footnote")

    if footnote_paragraphs:
        # Insert a vertical line (hr tag) before the first footnote
        first_footnote = footnote_paragraphs[0]
        hr_tag = soup.new_tag(
            "hr", style="border: 0; border-top: 2px solid #ccc; margin-top: 20px;"
        )
        first_footnote.insert_before(hr_tag)

    return soup


def remove_unwanted_attributes(soup):
    # Define the positional data attributes to remove
    unwanted_attributes = [
        "data-vertical-position-bottom",
        "data-vertical-position-top",
        "data-vertical-position-left",
        "data-vertical-position-right",
        "data-page-count",
        "data-font-family",
        "data-font-size",
        "data-font-weight",
    ]

    # Find all tags that have any of the positional data attributes
    for attr in unwanted_attributes:
        tags = soup.find_all(attrs={attr: True})
        for tag in tags:
            del tag[attr]

    return soup


def merge_enum_paragraphs(soup):
    """
    Merges paragraphs with the 'enum' class with the immediately following paragraph, preserving all HTML tags.

    Args:
        soup (BeautifulSoup): The BeautifulSoup object representing the HTML document.

    Returns:
        BeautifulSoup: The modified BeautifulSoup object with merged paragraphs.
    """
    # Define the pattern to match classes
    pattern = re.compile(r"enum-(lit|ziff)")

    # Custom function to filter paragraphs based on the class pattern
    def match_classes(tag):
        if tag.name == "p" and tag.has_attr("class"):
            return any(pattern.match(cls) for cls in tag["class"])
        return False

    # Find all paragraphs that match the custom filter
    enum_paragraphs = soup.find_all(match_classes)

    for enum_p in enum_paragraphs:
        # Find the next sibling that is a paragraph
        next_p = enum_p.find_next_sibling("p")
        if next_p:
            # Move all elements from the next paragraph to the enum paragraph
            for element in next_p.contents:
                enum_p.append(" ")  # Insert a space before appending the next element
                enum_p.append(element)
            # Remove the now empty next paragraph
            next_p.decompose()

    return soup


def merge_other_conditions(soup):
    """
    Merges paragraphs based on specific starting characters or lowercase letters,
    preserving all HTML tags and ignoring paragraphs with a class.

    Args:
        soup (BeautifulSoup): The BeautifulSoup object representing the HTML document.

    Returns:
        BeautifulSoup: The modified BeautifulSoup object with merged paragraphs.
    """
    paragraphs = soup.find_all("p")
    to_remove = []

    for i in range(1, len(paragraphs)):
        current_p = paragraphs[i]
        prev_p = paragraphs[i - 1]

        # Check if the current paragraph should merge with the previous one
        if not current_p.has_attr("class"):
            first_char = current_p.text.lstrip()[0] if current_p.text.lstrip() else ""
            if first_char in ".,;()?":
                # Move all child elements from the current paragraph to the previous paragraph
                for element in current_p.contents:
                    prev_p.append(element.extract())
                to_remove.append(current_p)

    # Clean up: remove any tagged paragraphs that are now empty and detached
    for p in to_remove:
        p.decompose()

    return soup


def main(html_file):

    with open(html_file, "r") as file:
        soup = BeautifulSoup(file, "html.parser")

    # Remove unwanted attributes
    soup = remove_unwanted_attributes(soup)

    # Merge punctuation
    soup = merge_punctuation(soup)

    # Merge enum paragraphs
    soup = merge_enum_paragraphs(soup)

    # Merge other conditions
    soup = merge_other_conditions(soup)

    # Reduce two or more whitespace characters to a single space
    soup = reduce_whitespace(soup)

    # Add footnote line and class
    soup = add_footnote_line_and_class(soup)

    # Save the updated HTML content back to the same file
    with open(html_file, "w", encoding="utf-8") as file:
        file.write(str(soup))


if __name__ == "__main__":
    main()
