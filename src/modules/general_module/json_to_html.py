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


def identify_and_build_tables(elements, soup):
    """
    Identifies table elements and builds HTML tables.

    Args:
        elements: List of elements from the JSON data
        soup: BeautifulSoup object for creating HTML elements

    Returns:
        A dictionary mapping table IDs to their HTML table elements and information for insertion
    """
    # Step 1: Group elements by TableID
    table_groups = {}

    # First, identify all TableIDs and group elements
    for element in elements:
        table_id = element.get("attributes", {}).get("TableID")
        if table_id is not None:
            if table_id not in table_groups:
                table_groups[table_id] = []

            # Add element to its group
            table_groups[table_id].append(element)

    # Step 2: Build HTML tables and determine insertion points
    tables = {}
    for table_id, group_elements in table_groups.items():
        # Find the first element index for this table ID (for insertion point)
        first_element_index = None
        for i, element in enumerate(elements):
            if element.get("attributes", {}).get("TableID") == table_id:
                first_element_index = i
                break

        # Build the table
        table = build_table(group_elements, soup, table_id)
        if table:
            tables[table_id] = {"table": table, "insertion_index": first_element_index}

    return tables


def build_table(elements, soup, table_id):
    """
    Builds an HTML table from a group of elements with the same TableID.

    Args:
        elements: List of elements belonging to the same table
        soup: BeautifulSoup object for creating HTML elements
        table_id: ID of the table

    Returns:
        BeautifulSoup Tag representing the HTML table
    """
    # Create the HTML table element with appropriate classes and data attributes
    table = soup.new_tag(
        "table", **{"class": "data-table", "data-table-id": str(table_id)}
    )

    # Extract table structure by organizing elements by TR (row), then TH/TD (cell)
    rows = {}

    # Create a unique cell identifier using the full path up to TD/TH part
    for element in elements:
        path = element.get("Path", "")

        # Extract row information
        row_match = re.search(r"/TR(?:\[(\d+)\])?", path)
        if not row_match:
            continue

        row_index = int(row_match.group(1)) if row_match.group(1) else 1

        # Initialize row if not exists
        if row_index not in rows:
            rows[row_index] = {"cells": {}, "attributes": {}}

        # If this is the TR element itself, store its attributes
        if re.search(r"/TR(?:\[\d+\])?$", path):
            for attr_name, attr_value in element.get("attributes", {}).items():
                if attr_name != "TableID":
                    rows[row_index]["attributes"][attr_name] = attr_value
            rows[row_index]["row_path"] = path  # Store the row path
            continue

        # Extract cell information - include full path up to TH/TD for unique identification
        cell_match = re.search(r"(.*?/(?:TH|TD)(?:\[(\d+)\])?)(?:/|$)", path)
        if not cell_match:
            continue

        # Use the full cell path as the identifier
        cell_path = cell_match.group(1)
        cell_type = "TH" if "/TH" in cell_path else "TD"
        cell_index = int(cell_match.group(2)) if cell_match.group(2) else 1

        # Create a compound key that includes both path and index
        cell_key = f"{cell_path}_{cell_index}"

        # Initialize cell if not exists
        if cell_key not in rows[row_index]["cells"]:
            rows[row_index]["cells"][cell_key] = {
                "type": cell_type,
                "content": [],
                "attributes": {},
                "cell_element": None,
                "index": cell_index,  # Store the index for sorting
                "path": cell_path,  # Store the cell path
            }

        # Store element if it's a direct child of the cell (like P)
        if "/P" in path or "/Sub" in path:
            content_copy = element.copy()
            content_copy["original_path"] = path  # Store the original path
            rows[row_index]["cells"][cell_key]["content"].append(content_copy)

        # Store cell element if this is the actual cell element
        elif path == cell_path:
            rows[row_index]["cells"][cell_key]["cell_element"] = element
            for attr_name, attr_value in element.get("attributes", {}).items():
                # Skip TableID since we already used it
                if attr_name != "TableID":
                    rows[row_index]["cells"][cell_key]["attributes"][
                        attr_name
                    ] = attr_value

    # Create thead and tbody sections
    thead = soup.new_tag("thead")
    tbody = soup.new_tag("tbody")
    has_header = False

    # Sort rows by row index for proper order
    for row_index in sorted(rows.keys()):
        row_data = rows[row_index]
        tr = soup.new_tag("tr")

        # Add row attributes if available
        for attr_name, attr_value in row_data.get("attributes", {}).items():
            tr[attr_name] = attr_value

        # Add row path for debugging
        if "row_path" in row_data:
            tr["data-original-path"] = row_data["row_path"]

        # Sort cells by their original index for proper order
        has_th_in_row = False

        # Group cells by their index and sort
        cell_groups = {}
        for cell_key, cell_data in row_data["cells"].items():
            cell_index = cell_data["index"]
            if cell_index not in cell_groups:
                cell_groups[cell_index] = []
            cell_groups[cell_index].append((cell_key, cell_data))

        # Process cells in order of their index
        for index in sorted(cell_groups.keys()):
            for cell_key, cell_data in cell_groups[index]:
                # Create TH or TD element
                cell = soup.new_tag(cell_data["type"].lower())

                # Mark if this row has any TH cells
                if cell_data["type"] == "TH":
                    has_th_in_row = True

                # Add cell attributes if available
                for attr_name, attr_value in cell_data.get("attributes", {}).items():
                    cell[attr_name] = attr_value

                # Add TableID attribute
                cell["data-table-id"] = str(table_id)

                # Add cell path for debugging
                if "path" in cell_data:
                    cell["data-original-path"] = cell_data["path"]

                # Add positional data and other metadata from cell element if available
                cell_element = cell_data.get("cell_element")
                if cell_element:
                    # Add positional data if the get_positional_data function is available
                    if "get_positional_data" in globals():
                        positional_data = get_positional_data(cell_element)
                        # Extract positional data attributes
                        for attr_name, attr_value in [
                            attr.split("='")
                            for attr in positional_data.split()
                            if "=" in attr
                        ]:
                            attr_value = attr_value.rstrip("'")
                            cell[attr_name] = attr_value

                    # Add page count
                    if "Page" in cell_element:
                        cell["data-page-count"] = str(cell_element["Page"])

                    # Add font information
                    font_info = cell_element.get("Font", {})
                    if font_info:
                        cell["data-font-weight"] = str(font_info.get("weight", 400))
                        cell["data-font-family"] = font_info.get("family_name", "")

                    # Add text size
                    if "TextSize" in cell_element:
                        cell["data-font-size"] = str(cell_element["TextSize"])

                    # Add text color if available in attributes
                    text_color = cell_element.get("attributes", {}).get("TextColor", "")
                    if text_color:
                        cell["data-text-color"] = text_color

                # Process cell content without wrapping in paragraphs
                for content_element in cell_data["content"]:
                    text = content_element.get("Text", "").strip()

                    # Check for special elements like superscripts
                    if (
                        "attributes" in content_element
                        and content_element["attributes"].get("TextPosition") == "Sup"
                    ):
                        sup = soup.new_tag("sup")
                        sup.string = text

                        # Add original path to sup for debugging
                        if "original_path" in content_element:
                            sup["data-original-path"] = content_element["original_path"]

                        # Add metadata to sup if available
                        if "Font" in content_element:
                            sup["data-font-weight"] = str(
                                content_element["Font"].get("weight", 400)
                            )
                            sup["data-font-family"] = content_element["Font"].get(
                                "family_name", ""
                            )
                        if "TextSize" in content_element:
                            sup["data-font-size"] = str(content_element["TextSize"])
                        if (
                            "attributes" in content_element
                            and "TextColor" in content_element["attributes"]
                        ):
                            sup["data-text-color"] = content_element["attributes"][
                                "TextColor"
                            ]

                        cell.append(sup)
                    else:
                        # For normal text, check if we need to add a debug container
                        if "original_path" in content_element:
                            # Create a span with the path for debugging
                            span = soup.new_tag("span")
                            span["data-original-path"] = content_element[
                                "original_path"
                            ]
                            span.string = text

                            # If the cell already has content, add a space before
                            if (
                                len(cell.contents) > 0
                                and not cell.contents[-1].name == "sup"
                            ):
                                cell.append(" ")

                            cell.append(span)
                        else:
                            # For normal text, just append directly to the cell
                            if (
                                len(cell.contents) > 0
                                and not cell.contents[-1].name == "sup"
                            ):
                                cell.append(" ")
                            cell.append(text)

                        # Add metadata to the cell from the content element
                        if (
                            not cell.get("data-font-weight")
                            and "Font" in content_element
                        ):
                            cell["data-font-weight"] = str(
                                content_element["Font"].get("weight", 400)
                            )
                            cell["data-font-family"] = content_element["Font"].get(
                                "family_name", ""
                            )
                        if (
                            not cell.get("data-font-size")
                            and "TextSize" in content_element
                        ):
                            cell["data-font-size"] = str(content_element["TextSize"])
                        if (
                            not cell.get("data-text-color")
                            and "attributes" in content_element
                            and "TextColor" in content_element["attributes"]
                        ):
                            cell["data-text-color"] = content_element["attributes"][
                                "TextColor"
                            ]
                        if (
                            not cell.get("data-page-count")
                            and "Page" in content_element
                        ):
                            cell["data-page-count"] = str(content_element["Page"])

                tr.append(cell)

        # If this row has TH cells, consider it a header row
        if has_th_in_row:
            has_header = True
            thead.append(tr)
        else:
            tbody.append(tr)

    # Add the table paths to the root table element
    table["data-table-id"] = str(table_id)

    # Only add thead if there are header rows
    if has_header:
        table.append(thead)

    # Always add tbody
    table.append(tbody)

    return table


def convert_to_html(json_data, erlasstitel, marginalia):
    """
    Converts JSON data to HTML format.
    """
    # Create BeautifulSoup instance for table creation
    soup_helper = BeautifulSoup("", "html.parser")

    # Find font variants and get elements
    font_variants = analyze_font_variants(json_data)
    elements = json_data.get("elements", [])

    # Pre-scan to find the last index where the text contains target keywords
    last_special_index = -1
    for i, element in enumerate(elements):
        text_lower = element.get("Text", "").lower()
        if "schlussbestimmung" in text_lower or "übergangsbestimmung" in text_lower:
            last_special_index = i

    # Step 1: Group elements by TableID
    table_groups = {}
    first_table_indices = {}

    # First pass - identify table elements and first occurrences
    for i, element in enumerate(elements):
        table_id = element.get("attributes", {}).get("TableID")
        if table_id is not None:
            # Add element to its table group
            if table_id not in table_groups:
                table_groups[table_id] = []
                first_table_indices[table_id] = i  # Record first occurrence
            table_groups[table_id].append(element)

    # Step 2: Build table HTML strings
    table_html = {}
    for table_id, group_elements in table_groups.items():
        table = build_table(group_elements, soup_helper, table_id)
        if table:
            table_html[table_id] = str(table)

    # Step 3: Process elements in sequence, inserting tables where needed
    processed_elements = set()
    inserted_tables = set()

    # Mark all elements belonging to tables
    for element in elements:
        table_id = element.get("attributes", {}).get("TableID")
        if table_id is not None:
            processed_elements.add(element.get("unique_element_id", ""))

    # Generate HTML content section
    html_content = f"""
    <html>
        <head>
        </head>
        <body>
            <div id='law'>
                <div id='source-text' class='pdf-source'>
    """

    # Process elements and insert tables
    for i, element in enumerate(elements):
        # Check if this is a position where we should insert a table
        for table_id, index in first_table_indices.items():
            if i == index and table_id not in inserted_tables:
                html_content += table_html[table_id]
                inserted_tables.add(table_id)

        # Skip elements that are part of tables (already processed)
        if element.get("unique_element_id", "") in processed_elements:
            continue

        # Process regular element
        html_content += process_element(
            element, font_variants, marginalia, i, last_special_index
        )

    # Complete the HTML structure
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

    # Check if the text is a subscript
    is_subscript = element.get("attributes", {}).get("TextPosition", "") == "Sub"
    if is_subscript:
        text = f"<sub>{text}</sub>"

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
