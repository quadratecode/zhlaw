# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

import json
import logging
from bs4 import BeautifulSoup, NavigableString
import re

# Get logger from main module
logger = logging.getLogger(__name__)


def read_json(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception as e:
        logging.error(f"Error reading file {file_path}: {e}")
        return None


def convert_to_html(json_data, erlasstitel, marginalia):
    """
    Converts JSON data to HTML format.

    Args:
        json_data (dict): The JSON data to be converted.
        erlasstitel (str): The title of the HTML document.

    Returns:
        str: The HTML content.

    Raises:
        None
    """
    # Wrap the content in div law (will later contain law text and meta data) and div source-text (will only contain the law text)
    html_content = f"""
    <html>
        <head>
        </head>
        <body>
            <div id='law'>
                <div id='source-text' class='pdf-source'>
    """

    font_variants = analyze_font_variants(json_data)

    for element in json_data.get("elements", []):
        html_content += process_element(element, font_variants, marginalia)

    html_content += """
    </div>
        </div>
            </body>
                </html>
    """
    return post_process_html(html_content)


def process_element(element, font_variants, marginalia):
    """
    Process an element and return the corresponding HTML content.

    Args:
        element (dict): The element to process.
        font_variants (list): List of font variants.

    Returns:
        str: The HTML content generated from the element.
    """
    content = ""
    text = (
        element.get("Text", "").replace("\n", " ").strip()
    )  # Replace line breaks and strip white space
    page = element.get("Page", 0)

    # This code block retrieves the character bounds from the element dictionary and calculates the vertical position data.
    # It extracts the top, bottom, left, and right coordinates of the first and last characters in the element.
    # The extracted coordinates are then used to create a string of data attributes that represent the vertical position of the entire element.
    # The data attributes include the left, top, bottom, and right coordinates of the element.
    char_bounds = element.get("CharBounds", [])
    bounds = element.get("Bounds", [])
    positional_data = ""
    if char_bounds:
        left_first_char = char_bounds[0][0]
        top_first_char = char_bounds[0][1]
        right_last_char = char_bounds[-1][2]
        bottom_last_char = char_bounds[-1][3]
    elif bounds:
        left_first_char = bounds[0]  # Left edge of the Bounds
        top_first_char = bounds[1]  # Top edge of the Bounds
        right_last_char = bounds[2]  # Right edge of the Bounds
        bottom_last_char = bounds[3]  # Bottom edge of the Bounds
    else:
        left_first_char = 0
        top_first_char = 0
        right_last_char = 0
        bottom_last_char = 0
    positional_data = f"data-vertical-position-left='{left_first_char}' data-vertical-position-top='{top_first_char}' data-vertical-position-bottom='{bottom_last_char}' data-vertical-position-right='{right_last_char}'"

    # Check if the text is a superscript
    is_superscript = element.get("attributes", {}).get("TextPosition", "") == "Sup"
    if is_superscript:
        # Wrap the text in <sup> tags
        text = f"<sup>{text}</sup>"

    font_info = element.get("Font", {})
    font_weight = font_info.get("weight", 400)
    font_size = element.get("TextSize", 12)
    font_fam = font_info.get("family_name", "")

    font_data = f"data-font-weight='{font_weight}' data-font-size='{font_size}' data-font-family='{font_fam}'"

    # Determine if the text is a heading
    heading_level = assign_heading_level(font_variants, font_weight, font_size)

    # Check if the text color is LinkBlue
    text_color = element.get("attributes", {}).get("TextColor", "")
    text_color_data = f"data-text-color='{text_color}'" if text_color else ""

    # Regular expression to match "art. NUMBER" or "§ NUMBER" as the whole paragraph content
    provision_pattern = re.compile(
        r"^(§\s*\d+\s*[a-zA-Z]?\s*\.)|^(art\.\s*\d+\s*[a-zA-Z]?)", re.IGNORECASE
    )

    # Second pattern: Extract the number and any following single letters
    number_letter_pattern = re.compile(r"(\d+)\s*([a-zA-Z]?)")

    # Check if text matches the provision pattern and is within 20 characters
    # Charcter limit needed to exclude paragraphs starting with reference
    is_provision = provision_pattern.match(text) and len(text) <= 20
    tag = "p"
    provision_attr = ' class="provision"' if is_provision else ""

    if is_provision:
        # Extract the first occurrence of number and letter using the second pattern
        number_letter_match = number_letter_pattern.search(text)
        if number_letter_match:
            number = number_letter_match.group(1)
            letter = number_letter_match.group(2)
            data_provision_number = f"{number}-{letter}" if letter else number
            provision_attr = (
                f' class="provision" id="provision-{data_provision_number}"'
            )
        # Remmove LinkBlue color from provisions
        text_color_data = ""
    else:
        # Ensure that provisions are not headings
        if heading_level and not is_provision:
            tag = f"h{heading_level}"

    content = f"<{tag} {positional_data} {font_data} data-page-count='{page}' {provision_attr} {text_color_data}>{text}</{tag}>"

    return content


def post_process_html(html_content):
    soup = BeautifulSoup(html_content, "html.parser")

    for p in soup.find_all("p"):
        # Remove empty paragraphs
        if not p.get_text(strip=True):
            p.decompose()
            continue

        # Clean and update text nodes
        for content in p.contents:
            if isinstance(content, NavigableString):
                cleaned_text = re.sub(r"\s+", " ", content.strip())
                content.replace_with(cleaned_text)

        # Remove paragraphs with only "-", merge preceding and following paragraphs
        if p.get_text(strip=True) == "-":
            prev_sibling = p.find_previous_sibling("p")
            next_sibling = p.find_next_sibling("p")

            if prev_sibling and next_sibling:
                prev_text = prev_sibling.get_text(strip=True)
                next_text = next_sibling.get_text(strip=True)

                # Merge contents
                merged_content = f"{prev_text}{next_text}"
                prev_sibling.string = merged_content

                # Update vertical position bottom and right data attributes from the next paragraph
                bottom_position_next = next_sibling.get("data-vertical-position-bottom")
                right_position_next = next_sibling.get("data-vertical-position-right")
                if bottom_position_next:
                    prev_sibling["data-vertical-position-bottom"] = bottom_position_next
                if right_position_next:
                    prev_sibling["data-vertical-position-right"] = right_position_next

                # Remove the '-' paragraph and the original next sibling
                p.decompose()
                next_sibling.decompose()

    for p in soup.find_all("p"):
        # If paragraph ends with "-", and the next paragraph starts with a lowercase letter, merge them
        if p.get_text(strip=True).endswith("-"):
            next_sibling = p.find_next_sibling("p")
            if next_sibling:
                next_text = next_sibling.get_text(strip=True)
                if next_text and next_text[0].islower():
                    # Merge contents
                    merged_content = f"{p.get_text(strip=True)}{next_text}"
                    p.string = merged_content

                    # Update vertical position bottom data attribute from the next paragraph
                    bottom_position_next = next_sibling.get(
                        "data-vertical-position-bottom"
                    )
                    if bottom_position_next:
                        p["data-vertical-position-bottom"] = bottom_position_next

                    # Remove the original next sibling
                    next_sibling.decompose()

    for p in soup.find_all("p"):
        prev_sibling = p.find_previous_sibling("p")
        next_sibling = p.find_next_sibling("p")

        # Check if the current paragraph is enclosed in parentheses
        if prev_sibling and next_sibling:
            prev_text = prev_sibling.get_text(strip=True)
            next_text = next_sibling.get_text(strip=True)
            if prev_text == "(" and next_text == ")":
                # Merge contents
                merged_content = f"({p.get_text(strip=True)})"
                prev_sibling.string = merged_content

                # Update vertical position bottom data attribute from the next paragraph
                bottom_position_next = next_sibling.get("data-vertical-position-bottom")
                right_position_next = next_sibling.get("data-vertical-position-right")
                if bottom_position_next and right_position_next:
                    prev_sibling["data-vertical-position-bottom"] = bottom_position_next
                    prev_sibling["data-vertical-position-right"] = right_position_next

                # Remove the original current and next sibling
                p.decompose()
                next_sibling.decompose()

    # Regular expression to match a paragraph with only a single superscript number
    superscript_pattern = re.compile(r"^\s*<sup>\s*\d+\s*</sup>\s*$", re.IGNORECASE)

    for i, p in enumerate(soup.find_all("p")):
        # Check if the current paragraph is a superscript number paragraph
        if superscript_pattern.fullmatch(str(p)) and i + 1 < len(soup.find_all("p")):
            # Get the next paragraph
            next_p = soup.find_all("p")[i + 1]
            # Check if the next paragraph has class "provision"
            if "provision" in next_p.get("class", []):
                # Remove the "provision" class and "data-provision-number" attribute
                next_p["class"].remove("provision")
                del next_p["data-provision-number"]

    return soup


def analyze_font_variants(json_data):
    font_variants = set()

    for element in json_data.get("elements", []):
        font_info = element.get("Font", {})
        font_weight = font_info.get("weight", 400)
        font_size = element.get("TextSize", 12)

        if font_weight > 400:
            font_variants.add((font_weight, font_size))

    # Sort by weight first and size second (larger and heavier first)
    return sorted(font_variants, key=lambda x: (x[0], x[1]), reverse=True)


def assign_heading_level(font_variants, font_weight, font_size):
    for i, (weight, size) in enumerate(font_variants):
        if font_weight == weight and font_size >= size:
            return i + 1  # Heading levels start from 1 (H1)
    return None


def main(json_file_law_updated, metadata, html_file, marginalia):
    json_data = read_json(json_file_law_updated)
    # Get title from metadata doc_info
    erlasstitel = metadata["doc_info"]["erlasstitel"]
    html_content = convert_to_html(json_data, erlasstitel, marginalia)

    # Write the html content to a file
    with open(html_file, "w", encoding="utf-8") as file:
        file.write(str(html_content))


if __name__ == "__main__":
    main()
