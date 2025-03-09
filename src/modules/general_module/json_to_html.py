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


def merge_consecutive_tables_with_same_headers(soup):
    """
    Finds consecutive tables with identical headers and merges them.

    Args:
        soup: BeautifulSoup object containing the HTML

    Returns:
        Modified BeautifulSoup object with merged tables
    """
    tables = soup.find_all("table", class_="law-data-table")
    i = 0

    while i < len(tables) - 1:
        current_table = tables[i]
        next_table = tables[i + 1]

        # Extract headers from both tables
        current_headers = []
        next_headers = []

        current_thead = current_table.find("thead")
        next_thead = next_table.find("thead")

        if current_thead and next_thead:
            current_tr = current_thead.find("tr")
            next_tr = next_thead.find("tr")

            if current_tr and next_tr:
                current_headers = [
                    th.get_text(strip=True) for th in current_tr.find_all("th")
                ]
                next_headers = [
                    th.get_text(strip=True) for th in next_tr.find_all("th")
                ]

        # If headers match, merge tables
        if current_headers and current_headers == next_headers:
            # Get the tbody elements
            current_tbody = current_table.find("tbody")
            next_tbody = next_table.find("tbody")

            if current_tbody and next_tbody:
                # Move all rows from next table to current table
                for tr in next_tbody.find_all("tr"):
                    current_tbody.append(tr)

                # Remove the next table
                next_table.decompose()

                # Update tables list after removing one
                tables = soup.find_all("table", class_="law-data-table")

                # Don't increment i since we've removed a table
                continue

        # Move to next table
        i += 1

    return soup


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
    # Create the table element
    table = soup.new_tag(
        "table", **{"class": "law-data-table", "law-data-table-id": str(table_id)}
    )

    # 1. First pass: Extract table structure and organize by row/column
    rows = {}

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

        # If this is the TR element itself, store row attributes
        if re.search(r"/TR(?:\[\d+\])?$", path):
            for attr_name, attr_value in element.get("attributes", {}).items():
                if attr_name != "TableID":
                    rows[row_index]["attributes"][attr_name] = attr_value
            continue

        # Extract cell information - get tag and index
        cell_match = re.search(r"/(T[HD])(?:\[(\d+)\])?", path)
        if not cell_match:
            continue

        cell_tag = cell_match.group(1)  # "TH" or "TD"
        cell_index_str = cell_match.group(2)

        # Get positional data from element
        bounds = element.get("Bounds", [])
        char_bounds = element.get("CharBounds", [])

        if char_bounds:
            left = char_bounds[0][0]
            top = char_bounds[0][1]
            right = char_bounds[-1][2]
            bottom = char_bounds[-1][3]
        elif bounds:
            left, top, right, bottom = bounds
        else:
            left = top = right = bottom = 0

        positional_data = {"left": left, "top": top, "right": right, "bottom": bottom}

        # Create a unique cell identifier
        if cell_index_str:
            cell_index = int(cell_index_str)
        else:
            cell_index = 1  # default for cells without explicit index

        cell_key = f"{row_index}_{cell_tag}_{cell_index}"

        # Initialize cell if not exists
        if cell_key not in rows[row_index]["cells"]:
            rows[row_index]["cells"][cell_key] = {
                "type": cell_tag,
                "content": [],
                "tags": [],  # Store special tags like <sup>, <sub>
                "attributes": {},
                "position": cell_index,
                "positional_data": positional_data,
                "tag": cell_tag,
                "metadata": {
                    "page": element.get("Page", 0),
                    "font_weight": element.get("Font", {}).get("weight", 400),
                    "font_size": element.get("TextSize", 12),
                    "font_family": element.get("Font", {}).get("family_name", ""),
                    "text_color": element.get("attributes", {}).get("TextColor", ""),
                },
            }

        # Add text content
        if "Text" in element:
            # Determine if this is a special tag like sup or sub
            is_special_tag = False
            tag_type = None

            if element.get("attributes", {}).get("TextPosition") == "Sup":
                is_special_tag = True
                tag_type = "sup"
            elif element.get("attributes", {}).get("TextPosition") == "Sub":
                is_special_tag = True
                tag_type = "sub"

            if is_special_tag:
                # Store special tag with its text and attributes
                rows[row_index]["cells"][cell_key]["tags"].append(
                    {
                        "type": tag_type,
                        "text": element.get("Text", "").strip(),
                        "position": len(
                            rows[row_index]["cells"][cell_key]["content"]
                        ),  # Position relative to content
                        "metadata": {
                            "page": element.get("Page", 0),
                            "font_weight": element.get("Font", {}).get("weight", 400),
                            "font_size": element.get("TextSize", 12),
                            "font_family": element.get("Font", {}).get(
                                "family_name", ""
                            ),
                            "text_color": element.get("attributes", {}).get(
                                "TextColor", ""
                            ),
                        },
                    }
                )
            else:
                # Regular text content
                rows[row_index]["cells"][cell_key]["content"].append(
                    element.get("Text", "").strip()
                )

        # Store cell element attributes if this is the actual cell element
        if re.search(rf"/{cell_tag}(?:\[\d+\])?$", path):
            for attr_name, attr_value in element.get("attributes", {}).items():
                if attr_name != "TableID":
                    rows[row_index]["cells"][cell_key]["attributes"][
                        attr_name
                    ] = attr_value

    # Check if rows exist
    if not rows:
        # Return empty table if no rows found
        return table

    # Find the first row (header row)
    first_row_index = min(rows.keys())
    first_row = rows[first_row_index]

    # Sort header cells by horizontal position for column boundaries
    header_cells = sorted(
        first_row["cells"].values(), key=lambda c: c["positional_data"]["left"]
    )

    # Establish column boundaries based on header cells
    column_boundaries = []
    for i, cell in enumerate(header_cells):
        column_boundaries.append(
            {"index": i, "left_pos": cell["positional_data"]["left"], "cell_data": cell}
        )

    # Sort column boundaries by position
    column_boundaries = sorted(column_boundaries, key=lambda c: c["left_pos"])

    # Create thead and tbody
    thead = soup.new_tag("thead")
    tbody = soup.new_tag("tbody")

    # Extract column structure from first row
    is_header_row = any(cell["tag"] == "TH" for cell in first_row["cells"].values())

    # Generate the rows
    for row_index in sorted(rows.keys()):
        row_data = rows[row_index]
        tr = soup.new_tag("tr")

        # Add row attributes if any
        for attr_name, attr_value in row_data.get("attributes", {}).items():
            tr[attr_name] = attr_value

        # Create a dictionary of cells sorted by left position
        cells_by_position = {}
        for cell_key, cell_data in row_data["cells"].items():
            left_pos = cell_data["positional_data"]["left"]
            cells_by_position[left_pos] = cell_data

        # Create cells for each column boundary
        for i, boundary in enumerate(column_boundaries):
            boundary_pos = boundary["left_pos"]

            # Find the cell closest to this boundary
            closest_cell = None
            min_distance = float("inf")

            for pos, cell in cells_by_position.items():
                distance = abs(pos - boundary_pos)
                # Consider cells within a reasonable distance (tolerance)
                if (
                    distance < min_distance and distance < 20
                ):  # Use a reasonable tolerance
                    min_distance = distance
                    closest_cell = cell

            # Create the appropriate cell tag (th for header row, td otherwise)
            tag_name = "th" if row_index == first_row_index and is_header_row else "td"
            cell = soup.new_tag(tag_name)

            # If we found a cell close to this boundary, use its content/attributes
            if closest_cell:
                # Add standard position data attributes
                page = closest_cell["metadata"]["page"]
                left = closest_cell["positional_data"]["left"]
                top = closest_cell["positional_data"]["top"]
                right = closest_cell["positional_data"]["right"]
                bottom = closest_cell["positional_data"]["bottom"]

                # Add all metadata attributes as data attributes
                cell["data-page-count"] = str(page)
                cell["data-vertical-position-left"] = str(left)
                cell["data-vertical-position-top"] = str(top)
                cell["data-vertical-position-right"] = str(right)
                cell["data-vertical-position-bottom"] = str(bottom)
                cell["data-font-weight"] = str(closest_cell["metadata"]["font_weight"])
                cell["data-font-size"] = str(closest_cell["metadata"]["font_size"])
                cell["data-font-family"] = closest_cell["metadata"]["font_family"]
                if closest_cell["metadata"]["text_color"]:
                    cell["data-text-color"] = closest_cell["metadata"]["text_color"]

                # Add other cell attributes
                for attr_name, attr_value in closest_cell.get("attributes", {}).items():
                    cell[attr_name] = attr_value

                # Process regular content
                content_text = " ".join(closest_cell["content"])
                if content_text:
                    cell.append(content_text)

                # Process special tags (sup, sub, etc.)
                for tag_info in closest_cell["tags"]:
                    tag_type = tag_info["type"]
                    tag_element = soup.new_tag(tag_type)
                    tag_element.string = tag_info["text"]

                    # Add metadata to tag
                    for key, value in tag_info["metadata"].items():
                        if value and key in [
                            "font_weight",
                            "font_size",
                            "font_family",
                            "text_color",
                        ]:
                            tag_element[f"data-{key.replace('_', '-')}"] = str(value)

                    cell.append(tag_element)

            # Add the cell to the row
            cell["law-data-table-id"] = str(table_id)
            tr.append(cell)

        # Add the row to thead or tbody
        if row_index == first_row_index and is_header_row:
            thead.append(tr)
        else:
            tbody.append(tr)

    # Add sections to table
    if thead.contents:
        table.append(thead)
    if tbody.contents:
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

    # Final step: Merge consecutive tables with identical headers
    soup = merge_consecutive_tables_with_same_headers(soup)

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
