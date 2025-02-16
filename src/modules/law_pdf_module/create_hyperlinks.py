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
    """
    Processes <p> elements in a BeautifulSoup object to identify:
      1. 'provisions' with IDs in the format 'provision-<number>[optional_letter]'.
      2. 'subprovisions' which are paragraphs containing only a single numeric string.

    For each 'provision' paragraph found:
      - We capture its numeric part (and optional letter).
      - Update 'last_provision_id' so subsequent 'subprovisions' can reference it.

    For each 'subprovision':
      - We assign the class 'subprovision'.
      - Set an ID like 'provision-<provision_id>-subprovision-<number>'.

    Returns:
        The modified soup object.
    """

    # Keep track of the last seen provision ID to anchor subprovisions
    last_provision_id = None

    # Look through all <p> tags that:
    # 1) Do NOT have data-text-color="LinkBlue"
    # 2) Have a numeric data-font-size > 5
    # 3) Does not have data-sup-type="SquareCubic"
    for paragraph in soup.find_all(
        "p",
        attrs={
            "data-text-color": lambda x: x != "LinkBlue",
            "data-sup-type": lambda x: x != "SquareCubic",
            "data-font-size": lambda x: (
                x is not None and x.replace(".", "", 1).isdigit() and float(x) > 5
            ),
        },
    ):
        # Extract the visible text from the paragraph, stripping leading/trailing whitespace
        text = paragraph.get_text(strip=True)

        # Check if the paragraph has an ID of the form:
        # "provision-<number>" or "provision-<number>_<letter>"
        provision_match = re.match(
            r"^provision-(\d+)(?:_([a-zA-Z]))?", paragraph.get("id", "")
        )
        if provision_match:
            # If we match, we capture the numeric part (num) and an optional letter
            num, letter = provision_match.groups()
            # Build the last_provision_id as "number-letter" if letter exists, else just "number"
            last_provision_id = f"{num}{f'-{letter}' if letter else ''}"

        # If the paragraph text consists solely of digits or digits followed by specific strings (e.g., "7bis", "10ter", etc.),
        # we treat it as a subprovision of the last known provision.
        subprovision_pattern = re.compile(
            r"^(\d+)(bis|ter|quater|quinquies|sexies|septies|octies)?$", re.IGNORECASE
        )
        if subprovision_pattern.match(text):
            # Mark it with the CSS class "subprovision"
            paragraph["class"] = ["subprovision"]

            # Only assign an ID if we actually have a parent provision identified
            if last_provision_id:
                subprov_match = subprovision_pattern.match(text)
                subprovision_number = subprov_match.group(1)
                suffix = subprov_match.group(2) if subprov_match.group(2) else ""
                # Set the ID in the format: provision-<provision_id>-subprovision-<digits><suffix>
                paragraph["id"] = (
                    f"provision-{last_provision_id}-subprovision-{subprovision_number}{suffix.lower()}"
                )

    # Return the modified soup object
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
    letter_pattern = re.compile(r"^[a-zA-Z]\.$")
    # Pattern to match single or double digits followed by a period
    number_pattern = re.compile(r"^\d{1,2}\.$")
    # Pattern to match "–" at the beginning of th string followed by a space
    dash_pattern = re.compile(r"–")

    paragraphs = [
        p
        for p in soup.find_all("p")
        if not p.find_parent(["h1", "h2", "h3", "h4", "h5", "h6"])
        and "marginalia" not in p.get("class", [])
    ]

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
        elif number_pattern.match(text):
            # Add 'enum-ziff' class to the paragraph
            if "enum-ziff" not in existing_classes:
                paragraph["class"] = existing_classes + ["enum-ziff"]
        elif dash_pattern.match(text):
            # Add 'enum-ziff' class to the paragraph
            if "enum-dash" not in existing_classes:
                paragraph["class"] = existing_classes + ["enum-dash"]
        else:
            continue

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


def contains_number_but_no_letter(text):
    # Check if text contains a number and no alphabet letters
    return bool(re.search(r"\d", text)) and not bool(re.search(r"[a-zA-Z]", text))


import re


def find_footnotes(soup):
    # Pattern for OS match: "OS" followed by a number, a comma, and a second number.
    # (Whitespace is allowed between parts; this search is case-sensitive.)
    os_pattern = re.compile(r"OS\s*\d+\s*,\s*\d+")

    # Pattern for annex match: look for any of the target words (case-insensitive).
    annex_pattern = re.compile(
        r"Anhang|Anhänge|Verzeichnis|Verzeichnisse", re.IGNORECASE
    )

    # Define heading tags.
    heading_tags = ["h1", "h2", "h3", "h4", "h5", "h6"]

    # 1. Get all headings in document order.
    all_headings = soup.find_all(heading_tags)

    # 2. Find the first heading that contains one of the annex strings.
    annex_match = None
    for h in all_headings:
        if annex_pattern.search(h.get_text()):
            annex_match = h
            break

    # 3. Find the very last heading in the document.
    last_heading = all_headings[-1] if all_headings else None

    # 4. If an annex_match was found, record the last heading occurring before it.
    last_heading_before_annex = None
    if annex_match:
        for h in all_headings:
            if h == annex_match:
                break
            last_heading_before_annex = h

    # 5. Find the first OS match in paragraphs with font_size < 9.
    os_match = None
    all_paragraphs = soup.find_all("p")
    for p in all_paragraphs:
        try:
            font_size = float(p.get("data-font-size", 0))
        except ValueError:
            font_size = 0
        if font_size < 9:
            if os_pattern.search(p.get_text()):
                os_match = p
                break

    # 6. Determine the region in which to consider paragraphs as possible footnotes.
    # Default: only paragraphs after the last heading.
    region = "after_last_heading"
    if os_match and annex_match:
        # If os_match appears before annex_match, the annex is at the document’s end.
        if os_match in annex_match.find_all_previous():
            region = "between_last_heading_before_annex_and_annex_match"
        else:
            region = "after_last_heading"
    # If either os_match or annex_match is missing, region remains "after_last_heading".

    # 7. Process paragraphs that fall within the defined region.
    for p in all_paragraphs:
        # Region filtering:
        if region == "after_last_heading":
            # If there's a last heading, consider only paragraphs coming after it.
            if last_heading is not None and last_heading not in p.find_all_previous():
                continue
        elif region == "between_last_heading_before_annex_and_annex_match":
            # Consider only paragraphs after last_heading_before_annex...
            if (
                last_heading_before_annex is not None
                and last_heading_before_annex not in p.find_all_previous()
            ):
                continue
            # ...and before annex_match.
            if annex_match is not None and annex_match not in p.find_all_next():
                continue

        # 8. Get the font size from the "data-font-size" attribute (default to 0 if missing).
        try:
            font_size = float(p.get("data-font-size", 0))
        except ValueError:
            font_size = 0

        # 9. Check for a <sup> tag with a number (and no letter).
        has_sup = False
        if p.find("sup") and contains_number_but_no_letter(p.get_text()):
            has_sup = True

        # 10. Apply the footnote logic if the paragraph does not have the "provision", "subprovision", or "marginalia" class:
        #    - If the paragraph’s font size is below 9 (when not superscript)
        #    - Or below 5 (when it has a <sup> tag),
        # then mark it as a footnote.
        if ((font_size < 9 and not has_sup) or (font_size < 5 and has_sup)) and not any(
            cls in p.get("class", [])
            for cls in ["provision", "subprovision", "marginalia"]
        ):
            p["class"] = ["footnote"]

    return soup


def handle_footnotes_refs(soup):
    # Step 1: Identify all footnote references in the body text
    footnote_refs = []
    footnote_refs = soup.find_all(
        lambda tag: tag.name in ["h1", "h2", "h3", "h4", "h5", "h6", "p"]
        and tag.get("data-text-color") == "LinkBlue"
        and "provision"
        not in tag.get("class", [])  # Exclude sup numbers from provisions
        and not re.search(
            r"\d+\.", tag.get_text(strip=True)
        )  # and does not contain a number followed by a period, so that Ziff-numbers are excluded
    )

    for ref in footnote_refs:
        text = ref.get_text(strip=True)
        footnote_nums = re.findall(r"\d+", text)
        ref.clear()
        for num in footnote_nums:
            # Create the <sup> tag to enclose everything
            sup_tag = soup.new_tag("sup", **{"class": "footnote-ref"})

            # Create a hyperlink with square brackets and the number inside
            a_tag = soup.new_tag("a", href="#footnote-line")
            a_tag.append(f"[{num}]")  # Add the number inside the square brackets

            # Add the <a> tag inside the <sup> tag
            sup_tag.append(a_tag)

            # Add the <sup> tag to the reference
            ref.append(sup_tag)

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

    # Find footnote refs
    soup = handle_footnotes_refs(soup)

    # Hyperlink provisons and subprovisions
    soup = hyperlink_provisions_and_subprovisions(soup)

    # Merge numbered paragraphs
    soup = merge_numbered_paragraphs(soup)

    # Update HTML file with hyperlinks
    soup = update_html_with_hyperlinks(hyperlinks, soup)

    # Save the updated HTML content back to the same file
    with open(merged_html_law, "w", encoding="utf-8") as file:
        file.write(str(soup))


if __name__ == "__main__":
    main()
