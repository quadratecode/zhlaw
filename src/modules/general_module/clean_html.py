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
    Merges consecutive paragraphs that contain only punctuation characters (excluding "...")
    with the previous paragraph.
    """
    paragraphs = soup.find_all("p")
    i = 1
    while i < len(paragraphs):
        current_paragraph = paragraphs[i]
        previous_paragraph = paragraphs[i - 1]

        current_text = (
            current_paragraph.get_text(strip=True) if current_paragraph else ""
        )

        if (
            current_text
            and all(char in string.punctuation for char in current_text)
            and "..." not in current_text
        ):
            preserved_content = current_paragraph.encode_contents()
            previous_paragraph.append(BeautifulSoup(preserved_content, "html.parser"))
            current_paragraph.decompose()
            paragraphs = soup.find_all("p")
        else:
            i += 1

    return soup


def assign_enum_level(soup):
    """
    Assigns enumeration levels to paragraphs with enum classes.

    For paragraphs with a class starting with "enum-":
      - If the enum class is "enum-lit", assign "first-level".
      - Otherwise (e.g. "enum-ziff" or "enum-dash"):
          - If the previous enum paragraph exists and its enum class is the same,
            continue using its level.
          - Otherwise, assign "second-level".
    """
    paragraphs = soup.find_all("p")
    prev_enum = None  # Will store a tuple (enum_class, level) for the last encountered enum paragraph

    for p in paragraphs:
        classes = p.get("class", [])
        # Look for an enum class in the paragraph's classes.
        enum_classes = [cls for cls in classes if cls.startswith("enum-")]
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
                # If no previous enum paragraph, default to second-level
                current_level = "second-level"
            else:
                prev_enum_class, prev_level = prev_enum
                if prev_enum_class == current_enum:
                    # If the same enum type continues, keep the same level.
                    current_level = prev_level
                else:
                    # Otherwise, assign second-level.
                    current_level = "second-level"

        # Append the level to the paragraph's class list.
        # (This preserves the original enum class and any other classes.)
        p["class"].append(current_level)

        # Update the previous enum info.
        prev_enum = (current_enum, current_level)

    return soup


def add_footnote_line_and_class(soup):
    """
    Inserts a horizontal line before the first footnote paragraph and gives it an id
    so that it can later serve as a marker.
    """
    footnote_paragraphs = soup.find_all("p", class_="footnote")
    if footnote_paragraphs:
        first_footnote = footnote_paragraphs[0]
        hr_tag = soup.new_tag(
            "hr", style="border: 0; border-top: 2px solid #ccc; margin-top: 20px;"
        )
        first_footnote.insert_before(hr_tag)
        hr_tag["id"] = "footnote-line"
    return soup


def merge_enum_paragraphs(soup):
    """
    Merges paragraphs with the 'enum' class with the immediately following paragraph,
    preserving all HTML tags.
    """
    pattern = re.compile(r"enum-(lit|ziff|dash)")

    def match_classes(tag):
        if tag.name == "p" and tag.has_attr("class"):
            return any(pattern.match(cls) for cls in tag["class"])
        return False

    enum_paragraphs = soup.find_all(match_classes)
    for enum_p in enum_paragraphs:
        next_p = enum_p.find_next_sibling("p")
        if next_p:
            for element in next_p.contents:
                enum_p.append(" ")  # Insert a space before appending the next element
                enum_p.append(element)
            next_p.decompose()
    return soup


def merge_other_conditions(soup):
    """
    Merges paragraphs based on specific starting characters or lowercase letters,
    preserving all HTML tags. Merging is not allowed if the current paragraph has a class,
    or if the previous paragraph has a class of 'marginalia', 'provision', or 'subprovision'.
    """
    paragraphs = soup.find_all("p")
    to_remove = []
    excluded_classes = {"marginalia", "provision", "subprovision"}
    merged = True

    while merged:
        merged = False
        paragraphs = soup.find_all("p")  # Refresh list after each iteration
        to_remove.clear()
        for i in range(1, len(paragraphs)):
            current_p = paragraphs[i]
            prev_p = paragraphs[i - 1]
            if not current_p.has_attr("class") and not (
                prev_p.has_attr("class")
                and any(cls in excluded_classes for cls in prev_p["class"])
            ):
                first_char = (
                    current_p.text.lstrip()[0] if current_p.text.lstrip() else ""
                )
                last_char_prev_p = (
                    prev_p.text.rstrip()[-1] if prev_p.text.rstrip() else ""
                )
                if first_char in ".,;()?:" or (
                    first_char.islower() and last_char_prev_p.islower()
                ):
                    for element in current_p.contents:
                        prev_p.append(element.extract())
                    to_remove.append(current_p)
                    merged = True
        for p in to_remove:
            p.decompose()
    return soup


def wrap_annex(soup):
    """
    Scans the document for the first heading (h1–h6) whose text contains any of the keywords:
    "Verzeichnis", "Anhänge", or "Anhang". From that heading onward,
    all elements (up to the element with id "footnote-line", if it exists) are wrapped into a
    <details> element with id "annex". A fixed <summary> element is created with the text
    "Anhänge und Verzeichnisse", and at the top of the details block a new paragraph
    with id "annex-info" and text "annex_callout" is inserted.
    """
    keywords = ["Anhang", "Anhänge", "Verzeichnis"]
    headings = soup.find_all(re.compile("^h[1-6]$"))
    start_heading = None
    for heading in headings:
        if any(keyword in heading.get_text() for keyword in keywords):
            start_heading = heading
            break

    if not start_heading:
        return soup

    # Create the <details> element with the desired id.
    details = soup.new_tag("details", id="annex")
    # Create the fixed <summary> element.
    summary = soup.new_tag("summary")
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


def remove_unwanted_attributes(soup):
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
    for attr in unwanted_attributes:
        tags = soup.find_all(attrs={attr: True})
        for tag in tags:
            del tag[attr]
    return soup


def main(html_file):
    with open(html_file, "r", encoding="utf-8") as file:
        soup = BeautifulSoup(file, "html.parser")

    # Process the HTML with the various functions.
    soup = remove_unwanted_attributes(soup)
    soup = merge_punctuation(soup)
    soup = merge_enum_paragraphs(soup)
    soup = assign_enum_level(soup)
    soup = merge_other_conditions(soup)
    soup = reduce_whitespace(soup)
    soup = add_footnote_line_and_class(soup)
    soup = wrap_annex(soup)

    # Save the updated HTML content back to the same file.
    with open(html_file, "w", encoding="utf-8") as file:
        file.write(str(soup))


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        print("Usage: python script.py <html_file>")
