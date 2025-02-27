# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

import json
import logging
import re
from bs4 import BeautifulSoup, NavigableString

# Get logger from main module
logger = logging.getLogger(__name__)

# Module-level constants for default values
DEFAULT_FONT_WEIGHT = 400
DEFAULT_TEXT_SIZE = 12

# Pre-compiled regular expressions for efficiency
PROVISION_PATTERN = re.compile(
    r"^(§\s*\d+\s*[a-zA-Z]?\s*\.)|^(art\.\s*\d+\s*[a-zA-Z]?)", re.IGNORECASE
)
NUMBER_LETTER_PATTERN = re.compile(r"(\d+)\s*([a-zA-Z]?)")
SUPER_SCRIPT_PATTERN = re.compile(r"^\s*<sup>\s*\d+\s*</sup>\s*$", re.IGNORECASE)


def read_json(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception as e:
        # Use the module logger for consistent logging
        logger.error(f"Error reading file {file_path}: {e}")
        return None


def get_positional_data(element):
    """
    Calculate and return positional data attributes as a formatted string.
    Uses 'CharBounds' if available, otherwise uses 'Bounds', else defaults to 0.
    """
    char_bounds = element.get("CharBounds", [])
    bounds = element.get("Bounds", [])
    if char_bounds:
        left = char_bounds[0][0]
        top = char_bounds[0][1]
        right = char_bounds[-1][2]
        bottom = char_bounds[-1][3]
    elif bounds:
        left, top, right, bottom = bounds
    else:
        left = top = right = bottom = 0
    return (
        f"data-vertical-position-left='{left}' "
        f"data-vertical-position-top='{top}' "
        f"data-vertical-position-bottom='{bottom}' "
        f"data-vertical-position-right='{right}'"
    )


def determine_tag(is_provision, heading_level, text, index, last_special_index):
    """
    Determine the HTML tag to use based on whether the element is a provision,
    its heading level, and special conditions related to content.
    """
    if is_provision:
        return "p"
    # Check for special conversion condition after the last target element
    if heading_level and (
        last_special_index != -1
        and index > last_special_index
        and (
            ("gesetz" in text.lower() or "verordnung" in text.lower())
            and "vom" in text.lower()
        )
    ):
        return "p"
    return f"h{heading_level}" if heading_level else "p"


def convert_to_html(json_data, erlasstitel, marginalia):
    """
    Converts JSON data to HTML format.
    """
    # Wrap the content in div law (will later contain law text and meta data)
    # and div source-text (will only contain the law text)
    html_content = f"""
    <html>
        <head>
        </head>
        <body>
            <div id='law'>
                <div id='source-text' class='pdf-source'>
    """

    font_variants = analyze_font_variants(json_data)
    elements = json_data.get("elements", [])

    # Pre-scan to find the last index where the text contains target keywords
    last_special_index = -1
    for i, element in enumerate(elements):
        text_lower = element.get("Text", "").lower()
        if "schlussbestimmung" in text_lower or "übergangsbestimmung" in text_lower:
            last_special_index = i

    # Process each element, passing its index and the last special index
    for i, element in enumerate(elements):
        html_content += process_element(
            element, font_variants, marginalia, i, last_special_index
        )

    html_content += """
                </div>
            </div>
        </body>
    </html>
    """
    return post_process_html(html_content)


def process_element(element, font_variants, marginalia, index, last_special_index):
    """
    Process an element and return the corresponding HTML content.
    """
    # Clean and prepare text
    text = element.get("Text", "").replace("\n", " ").strip()
    page = element.get("Page", 0)

    # Use helper function to calculate positional data
    positional_data = get_positional_data(element)

    # Check if the text is a superscript
    is_superscript = element.get("attributes", {}).get("TextPosition", "") == "Sup"
    if is_superscript:
        text = f"<sup>{text}</sup>"

    font_info = element.get("Font", {})
    font_weight = font_info.get("weight", DEFAULT_FONT_WEIGHT)
    font_size = element.get("TextSize", DEFAULT_TEXT_SIZE)
    font_fam = font_info.get("family_name", "")
    font_data = f"data-font-weight='{font_weight}' data-font-size='{font_size}' data-font-family='{font_fam}'"

    # Determine heading level based on font variants
    heading_level = assign_heading_level(font_variants, font_weight, font_size)

    # Determine if the text qualifies as a provision based on pattern and length
    is_provision = PROVISION_PATTERN.match(text) and len(text) <= 20
    provision_attr = ' class="provision"' if is_provision else ""

    if is_provision:
        # Extract number/letter information for provisions
        number_letter_match = NUMBER_LETTER_PATTERN.search(text)
        if number_letter_match:
            number = number_letter_match.group(1)
            letter = number_letter_match.group(2)
            data_provision_number = f"{number}-{letter}" if letter else number
            provision_attr = (
                f' class="provision" id="provision-{data_provision_number}"'
            )
        # Remove text color data for provisions
        text_color_data = ""
    else:
        # Set text color if available
        text_color = element.get("attributes", {}).get("TextColor", "")
        text_color_data = f"data-text-color='{text_color}'" if text_color else ""

    # Sup type attribute if available
    sup_type = element.get("attributes", {}).get("SupType", "")
    sup_type_data = f"data-sup-type='{sup_type}'" if sup_type else ""

    # Determine the HTML tag using the helper function
    tag = determine_tag(is_provision, heading_level, text, index, last_special_index)

    # Construct the final HTML element with attributes
    content = (
        f"<{tag} {positional_data} {font_data} data-page-count='{page}' "
        f"{provision_attr} {text_color_data} {sup_type_data}>{text}</{tag}>"
    )
    return content


def post_process_html(html_content):
    """
    Post-processes the HTML content to clean up paragraphs and merge specific ones.
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # Loop 1: Clean paragraphs and merge those that contain only "-"
    for p in list(soup.find_all("p")):
        # Remove empty paragraphs
        if not p.get_text(strip=True):
            p.decompose()
            continue

        # Clean text nodes by replacing multiple spaces with a single space
        for content in p.contents:
            if isinstance(content, NavigableString):
                cleaned_text = re.sub(r"\s+", " ", content.strip())
                content.replace_with(cleaned_text)

        # Merge paragraphs that only contain "-"
        if p.get_text(strip=True) == "-":
            prev_sibling = p.find_previous_sibling("p")
            next_sibling = p.find_next_sibling("p")
            if prev_sibling and next_sibling:
                prev_text = prev_sibling.get_text(strip=True)
                next_text = next_sibling.get_text(strip=True)
                # Merge contents
                merged_content = f"{prev_text}{next_text}"
                prev_sibling.string = merged_content

                # Update vertical position attributes from the next paragraph
                bottom_position_next = next_sibling.get("data-vertical-position-bottom")
                right_position_next = next_sibling.get("data-vertical-position-right")
                if bottom_position_next:
                    prev_sibling["data-vertical-position-bottom"] = bottom_position_next
                if right_position_next:
                    prev_sibling["data-vertical-position-right"] = right_position_next

                # Remove the '-' paragraph and the next sibling
                p.decompose()
                next_sibling.decompose()

    # Loop 2: Merge paragraphs ending with "-" with the next paragraph if it starts with a lowercase letter
    for p in list(soup.find_all("p")):
        if p.get_text(strip=True).endswith("-"):
            next_sibling = p.find_next_sibling("p")
            if next_sibling:
                next_text = next_sibling.get_text(strip=True)
                if next_text and next_text[0].islower():
                    merged_content = f"{p.get_text(strip=True)}{next_text}"
                    p.string = merged_content
                    bottom_position_next = next_sibling.get(
                        "data-vertical-position-bottom"
                    )
                    if bottom_position_next:
                        p["data-vertical-position-bottom"] = bottom_position_next
                    next_sibling.decompose()

    # Loop 3: Merge paragraphs enclosed in parentheses
    for p in list(soup.find_all("p")):
        prev_sibling = p.find_previous_sibling("p")
        next_sibling = p.find_next_sibling("p")
        if prev_sibling and next_sibling:
            prev_text = prev_sibling.get_text(strip=True)
            next_text = next_sibling.get_text(strip=True)
            if prev_text == "(" and next_text == ")":
                merged_content = f"({p.get_text(strip=True)})"
                prev_sibling.string = merged_content
                bottom_position_next = next_sibling.get("data-vertical-position-bottom")
                right_position_next = next_sibling.get("data-vertical-position-right")
                if bottom_position_next and right_position_next:
                    prev_sibling["data-vertical-position-bottom"] = bottom_position_next
                    prev_sibling["data-vertical-position-right"] = right_position_next
                p.decompose()
                next_sibling.decompose()

    # Loop 4: Process superscript number paragraphs merging with following provision paragraphs
    p_tags = list(soup.find_all("p"))
    for i, p in enumerate(p_tags):
        # Check if the current paragraph is a superscript number paragraph
        if SUPER_SCRIPT_PATTERN.fullmatch(str(p)) and i + 1 < len(p_tags):
            next_p = p_tags[i + 1]
            # If the next paragraph has class "provision", remove it from that paragraph
            if "provision" in next_p.get("class", []):
                next_p["class"].remove("provision")
                if "data-provision-number" in next_p.attrs:
                    del next_p["data-provision-number"]

    return soup


def analyze_font_variants(json_data):
    """
    Analyzes font variants from the JSON data.
    """
    font_variants = set()
    for element in json_data.get("elements", []):
        font_info = element.get("Font", {})
        font_weight = font_info.get("weight", DEFAULT_FONT_WEIGHT)
        font_size = element.get("TextSize", DEFAULT_TEXT_SIZE)
        if font_weight > DEFAULT_FONT_WEIGHT:
            font_variants.add((font_weight, font_size))
    # Sort by weight first and size second (larger and heavier first)
    return sorted(font_variants, key=lambda x: (x[0], x[1]), reverse=True)


def assign_heading_level(font_variants, font_weight, font_size):
    """
    Assigns a heading level based on font variants.
    """
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
    # TODO: Allow command-line arguments
    pass
