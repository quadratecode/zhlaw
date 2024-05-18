# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

import json
import re
from bs4 import BeautifulSoup, NavigableString
import logging

# Get logger from main module
logger = logging.getLogger(__name__)


def read_json_file(json_file_path):
    with open(json_file_path, "r") as file:
        return json.load(file)


def assign_footnote_ids(soup):
    # Find all paragraphs with 'footnote' class
    footnote_paragraphs = soup.find_all("p", class_="footnote")

    for p in footnote_paragraphs:
        if p.sup:
            # Extract the number from the <sup> tag
            footnote_number = p.sup.get_text().strip()
            # Assign an id based on the footnote number
            p["id"] = f"footnote-{footnote_number}"

    return soup


def refine_footnotes(soup):
    # Get all paragraphs with 'footnote' class and reverse the list to process from bottom to top
    footnote_paragraphs = soup.find_all("p", class_="footnote")[::-1]
    remove_class = False
    for p in footnote_paragraphs:
        if p.sup and p.sup.get_text().strip() == "1":
            remove_class = (
                True  # Start removing the class after the first <sup>1</sup> is found
            )
            continue
        if remove_class:
            p["class"].remove("footnote")  # Remove the 'footnote' class
            if not p[
                "class"
            ]:  # If there are no more classes left, remove the attribute
                del p["class"]
    return soup


def find_subprovisions(soup):
    # Initialize a variable to keep track of the last provision number
    last_provision_id = None

    # Iterate through all paragraph elements in the soup object
    for paragraph in soup.find_all(
        "p",
        attrs={
            "data-text-color": lambda x: x != "LinkBlue",
            "data-font-size": lambda x: x is not None
            and x.replace(".", "", 1).isdigit()
            and float(x) > 5,
        },
    ):
        text = paragraph.get_text(strip=True)

        # Check if paragraph is a provision and capture its number and possible letter
        provision_match = re.match(
            r"^provision-(\d+)(?:_([a-zA-Z]))?", paragraph.get("id", "")
        )
        if provision_match:
            # Construct the provision id from captured groups
            num, letter = provision_match.groups()
            last_provision_id = f"{num}{f'-{letter}' if letter else ''}"

        # Check if paragraph contains only a superscript number
        if re.match(r"^\d+$", text):
            paragraph["class"] = ["subprovision"]
            # Check if we have a valid last_provision_id to reference
            if last_provision_id:
                subprovision_number = re.match(r"^(\d+)", text).group(1)
                paragraph["id"] = (
                    f"provision-{last_provision_id}-subprovision-{subprovision_number}"
                )

    return soup


def merge_footnotes(soup):
    # Find all paragraphs with 'footnote' class
    footnote_paragraphs = soup.find_all("p", class_="footnote")
    new_paragraphs = []
    current_text = []
    sup_number = None  # Initialize to None or a suitable default

    for p in footnote_paragraphs:
        if p.sup:  # If a <sup> tag is found, start a new paragraph
            if current_text:  # If there's existing text, save the previous paragraph
                new_paragraphs.append((sup_number, " ".join(current_text)))
                current_text = []
            sup_number = p.sup.extract().get_text()  # Extract the <sup> text

        current_text.append(
            p.get_text()
        )  # Append current paragraph's text to the text list

    # Append the last set of accumulated text to the new paragraphs
    if current_text:
        new_paragraphs.append((sup_number, " ".join(current_text)))

    # Clear existing footnotes
    for p in footnote_paragraphs:
        p.decompose()

    # Create new merged paragraphs
    for sup_num, text in new_paragraphs:
        new_p = soup.new_tag("p", **{"class": "footnote"})
        new_p.append(soup.new_tag("sup"))
        new_p.sup.string = str(sup_num)
        new_p.append(text)
        source_div = soup.find("div", id="source-text")
        source_div.append(new_p)

    return soup


def find_enumerations(soup):
    """
    Identifies enumeration paragraphs that contain a single or double letter followed by a period,
    or a number followed by a period, while ignoring any superscript text such as footnotes.
    Assigns the class 'enum-lit' to letter matches and 'enum-ziff' to number matches.
    Additionally, assigns 'first-level' and 'second-level' classes based on their order.

    Args:
        soup (BeautifulSoup): The BeautifulSoup object representing the HTML document.

    Returns:
        BeautifulSoup: The modified BeautifulSoup object with enumeration paragraphs marked.
    """
    # Pattern to match single or double letters followed by a period
    letter_pattern = re.compile(r"^[a-zA-Z]{1,2}\.$")
    # Pattern to match single or double digits followed by a period
    number_pattern = re.compile(r"^\d{1,2}\.$")

    paragraphs = soup.find_all("p")
    previous_enum_type = None
    current_level_class = "first-level"

    for paragraph in paragraphs:
        # Extract all text nodes directly under the paragraph element, ignoring any text within <sup> tags
        text_parts = [text for text in paragraph.find_all(text=True, recursive=False)]
        text = "".join(
            text_parts
        ).strip()  # Join all direct text nodes and strip whitespace

        existing_classes = paragraph.get("class", [])
        if letter_pattern.match(text):
            # Add 'enum-lit' class to the paragraph
            if "enum-lit" not in existing_classes:
                paragraph["class"] = existing_classes + ["enum-lit"]
            current_enum_type = "enum-lit"
        elif number_pattern.match(text):
            # Add 'enum-ziff' class to the paragraph
            if "enum-ziff" not in existing_classes:
                paragraph["class"] = existing_classes + ["enum-ziff"]
            current_enum_type = "enum-ziff"
        else:
            continue

        # Assign 'first-level' or 'second-level' class
        if previous_enum_type is None or previous_enum_type == current_enum_type:
            paragraph["class"] = paragraph.get("class", []) + [current_level_class]
        else:
            # Switch level class and apply to current paragraph
            current_level_class = (
                "second-level"
                if current_level_class == "first-level"
                else "first-level"
            )
            paragraph["class"] = paragraph.get("class", []) + [current_level_class]

        previous_enum_type = current_enum_type

    return soup


def update_html_with_hyperlinks(hyperlinks, soup):
    """
    Updates the HTML with hyperlinks based on the provided list of hyperlinks.

    Args:
        hyperlinks (list): A list of dictionaries representing the hyperlinks. Each dictionary should have
                           'text' and 'uri' keys representing the hyperlink text and URI respectively.
        soup (BeautifulSoup): The BeautifulSoup object representing the HTML.

    Returns:
        BeautifulSoup: The updated BeautifulSoup object with hyperlinks inserted.
    """
    for link in hyperlinks:
        link_text = link.get("text")
        link_uri = link.get("uri")
        escaped_link_text = re.escape(
            link_text
        )  # Escape to handle special regex characters in link_text
        regex = (
            rf"\b{escaped_link_text}\b"  # Use word boundaries to match whole words only
        )

        # Find all text containing the hyperlink text and replace it
        text_elements = soup.find_all(text=re.compile(regex))
        for text_element in text_elements:
            # Check if the text is already inside an <a> tag
            if text_element.parent.name != "a":
                new_text = re.sub(
                    regex,
                    f'<a href="{link_uri}">{link_text}</a>',
                    text_element,
                    flags=re.IGNORECASE,
                )
                new_soup = BeautifulSoup(new_text, "html.parser")
                text_element.replace_with(new_soup)
            else:
                # If already in an <a> tag, update the href if necessary
                text_element.parent["href"] = link_uri

    # Cleanup nested <a> tags if they exist
    for a_tag in soup.find_all("a"):
        inner_a_tags = a_tag.find_all("a")
        for inner_a in inner_a_tags:
            inner_a.unwrap()

    return soup


def merge_numbered_paragraphs(soup):
    # Iterate over all paragraphs
    paragraphs = soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6"])
    for current_paragraph in paragraphs:
        # Get the previous sibling that is either a paragraph or a heading
        previous_sibling = current_paragraph.find_previous_sibling(
            ["p", "h1", "h2", "h3", "h4", "h5", "h6"]
        )

        # Continue only if there is a previous sibling and the current paragraph matches the pattern
        if (
            previous_sibling
            and current_paragraph.get_text(strip=True).startswith("[")
            and current_paragraph.get_text(strip=True).endswith("]")
        ):
            # Preserve the contents of the current paragraph (with superscript, hyperlinks, and attributes)
            preserved_content = current_paragraph.encode_contents()

            # Append the preserved content to the previous sibling
            if isinstance(previous_sibling, NavigableString):
                # Convert NavigableString to Tag if necessary
                previous_sibling = soup.new_tag(previous_sibling)
            previous_sibling.append(BeautifulSoup(preserved_content, "html.parser"))

            # Remove the current paragraph
            current_paragraph.decompose()

    return soup


def hyperlink_provisions_and_subprovisions(soup):
    """
    Wraps all provisions and subprovisions in 'a' tags to make them directly linkable, while ensuring not to nest existing 'a' tags
    or improperly handle nested <sup> tags. This function will separate <sup> tags from the hyperlink if they contain references like footnotes.

    Args:
        soup (BeautifulSoup): The BeautifulSoup object representing the HTML document.

    Returns:
        BeautifulSoup: The modified BeautifulSoup object where provisions and subprovisions are hyperlinked without nested links.
    """
    # Select all paragraphs with class 'provision' or 'subprovision' that have an ID
    for paragraph in soup.find_all("p", class_=["provision", "subprovision"], id=True):
        new_contents = []
        link_content = []

        for content in paragraph.contents:
            if content.name == "a":
                # If there's accumulated linkable content, wrap it before handling the existing 'a'
                if link_content:
                    new_link = soup.new_tag("a", href=f"#{paragraph['id']}")
                    new_link.extend(link_content)
                    new_contents.append(new_link)
                    link_content = []
                new_contents.append(content)
            elif content.name == "sup" and content.find("a"):
                # Handle 'sup' tags separately if they contain links, such as footnotes
                if link_content:
                    new_link = soup.new_tag("a", href=f"#{paragraph['id']}")
                    new_link.extend(link_content)
                    new_contents.append(new_link)
                    link_content = []
                new_contents.append(content)
            else:
                # Accumulate text and other tags that will be part of the main provision link
                link_content.append(content)

        # Wrap any remaining content in a new link
        if link_content:
            new_link = soup.new_tag("a", href=f"#{paragraph['id']}")
            new_link.extend(link_content)
            new_contents.append(new_link)

        # Clear the paragraph and re-add processed contents
        paragraph.clear()
        for content in new_contents:
            paragraph.append(content)

    return soup


def remove_arrows_from_body_footnotes(soup):

    # Find all 'a' tags with href matching the pattern and containing the arrow
    all_arrows = soup.find_all(
        "a", href=re.compile(r"#footnote-\d+-ref-\d+"), string="↩"
    )

    # Group arrows by their 'href' attribute
    arrows_by_href = {}
    for arrow in all_arrows:
        href = arrow["href"]
        if href not in arrows_by_href:
            arrows_by_href[href] = []
        arrows_by_href[href].append(arrow)

    # Keep only the last arrow for each href
    for href, arrows in arrows_by_href.items():
        for arrow in arrows[:-1]:  # Remove all but the last arrow
            arrow.decompose()

    return soup


def contains_number_but_no_letter(text):
    # Check if text contains a number and no alphabet letters
    return bool(re.search(r"\d", text)) and not bool(re.search(r"[a-zA-Z]", text))


def find_footnotes(soup):
    # Exclude these classes from the search
    excluded_classes = ["provision", "subprovision", "enum", "marginalia"]

    # Find all paragraph elements
    paragraphs = soup.find_all("p")

    # Filter paragraphs that do not have excluded classes and are not under any headings
    results = [
        p
        for p in paragraphs
        if not p.find_parent(["h1", "h2", "h3", "h4", "h5", "h6"])
        and not any(cls in p.get("class", []) for cls in excluded_classes)
    ]

    for paragraph in results:
        # Get font data attributes from data-font-size and data-font-family
        font_size = float(paragraph.get("data-font-size", 0))
        # Check if paragraph contains sup tag with a number
        if paragraph.find("sup") and contains_number_but_no_letter(
            paragraph.get_text()
        ):
            has_sup = True
        else:
            has_sup = False

        # Check if font size is below 9pt (non superscript) or below 5pt (superscript)
        # Give class "footnote" to the paragraph
        # Font family not relevant since some footnotes are in a different font
        if (font_size < 9 and not has_sup) or (font_size < 5 and has_sup):
            paragraph["class"] = ["footnote"]

    return soup


def remove_content_after_last_footnote(soup):
    # Find all footnotes using a likely common attribute such as a class or id pattern
    footnotes = soup.find_all("p", id=lambda x: x and x.startswith("footnote-"))
    if not footnotes:
        return soup  # No footnotes, return the original soup

    # Find the last footnote by checking the highest footnote number
    last_footnote = max(footnotes, key=lambda fn: int(fn["id"].split("-")[1]))

    # Find all siblings after the last footnote and remove them
    content_removed = False
    next_sib = last_footnote.find_next_sibling()
    while next_sib:
        next_sib.decompose()
        content_removed = True
        next_sib = last_footnote.find_next_sibling()

    # If content was removed, insert a warning paragraph
    if content_removed:
        warning_paragraph = soup.new_tag("p", **{"class": "missing-content"})
        warning_paragraph.string = (
            "Hinweis: Inhalt nach den Fussnoten automatisch entfernt."
        )
        last_footnote.insert_after(warning_paragraph)

    return soup


def hyperlink_footnotes(soup):

    # Step 1: Identify all footnote references in the body text
    footnote_refs = []
    potential_refs = soup.find_all(
        lambda tag: tag.name in ["h1", "h2", "h3", "h4", "h5", "h6", "p"]
        and tag.get("data-text-color") == "LinkBlue"
        and "provision"
        not in tag.get("class", [])  # Exclude sup numbers from provisions
    )

    for ref in potential_refs:
        if contains_number_but_no_letter(ref.get_text()):
            footnote_refs.append(ref)

    # Dictionary to track the number of references for each footnote
    ref_counters = {}

    # Step 2: Extract the footnote numbers and create hyperlinks
    for ref in footnote_refs:
        text = ref.get_text(strip=True)
        footnote_nums = re.findall(r"\d+", text)
        ref.clear()
        for num in footnote_nums:
            # Update counter for each footnote number
            ref_counters[num] = ref_counters.get(num, 0) + 1
            ref_id = f"footnote-{num}-ref-{ref_counters[num]}"
            # Create hyperlink for each footnote reference
            ref_link = soup.new_tag("a", href=f"#footnote-{num}", id=ref_id)
            ref_link.string = f"[{num}]"
            sup_tag = soup.new_tag("sup", **{"class": "footnote-number"})
            sup_tag.append(ref_link)
            ref.append(sup_tag)
            if num != footnote_nums[-1]:
                # Add comma separator for multiple footnotes
                comma_sup = soup.new_tag("sup")
                comma_sup.string = ", "
                ref.append(comma_sup)

    # Step 3: Link back from the footnote to the reference in the body text
    footnotes = soup.find_all(
        id=re.compile(r"footnote-\d+$")
    )  # Use word boundry to exclude references (e.g. footnote-1-ref-1)
    for note in footnotes:
        footnote_num = note["id"].split("-")[1]
        # Link back to all references for this footnote
        for i in range(1, ref_counters.get(footnote_num, 0) + 1):
            ref_id = f"footnote-{footnote_num}-ref-{i}"
            backlink = soup.new_tag("a", href=f"#{ref_id}")
            backlink.string = "↩"
            note.append(backlink)

    return soup


def main(merged_html_law, updated_json_file_law):

    # Read the JSON file to get hyperlink data
    json_data = read_json_file(updated_json_file_law)
    hyperlinks = json_data.get("extended_metadata", {}).get("hyperlinks", [])

    with open(merged_html_law, "r") as file:
        soup = BeautifulSoup(file, "html.parser")

    # Find subprovisions
    soup = find_subprovisions(soup)

    # Find enumerations
    soup = find_enumerations(soup)

    # Find footnotes
    soup = find_footnotes(soup)

    # Refine footnotes
    soup = refine_footnotes(soup)

    # Process footnotes
    soup = merge_footnotes(soup)

    # Assign footnote id
    soup = assign_footnote_ids(soup)

    # Hyperlink footnotes
    soup = hyperlink_footnotes(soup)

    # Remove arrows from body text footnotes
    soup = remove_arrows_from_body_footnotes(soup)

    # Hyperlink provisons and subprovisions
    soup = hyperlink_provisions_and_subprovisions(soup)

    # Merge numbered paragraphs
    soup = merge_numbered_paragraphs(soup)

    # Update HTML file with hyperlinks
    soup = update_html_with_hyperlinks(hyperlinks, soup)

    # Remove content after footnotes
    # Does no longer work with current logic
    # soup = remove_content_after_last_footnote(soup)

    # Save the updated HTML content back to the same file
    with open(merged_html_law, "w", encoding="utf-8") as file:
        file.write(str(soup))


if __name__ == "__main__":
    main()
