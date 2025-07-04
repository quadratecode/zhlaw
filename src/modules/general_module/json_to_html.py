"""
Module for converting Adobe Extract API JSON output to structured HTML.

This module provides functionality to:
- Parse JSON data from Adobe Extract API
- Convert text elements to semantic HTML
- Detect and handle provisions, headings, and tables
- Process text formatting (superscript, subscript, fractions)
- Handle marginalia and annotations
- Generate well-structured HTML with metadata attributes

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import json
import re
from bs4 import BeautifulSoup, NavigableString
from pathlib import Path

from src.utils.logging_utils import get_module_logger
from src.modules.manual_review_module.correction_applier import CorrectionApplier

# Get logger for this module
logger = get_module_logger(__name__)

# Module-level constants for default values
DEFAULT_FONT_WEIGHT = 400
DEFAULT_TEXT_SIZE = 12

# Pre-compiled regular expressions for efficiency
PROVISION_PATTERN = re.compile(
    r"^(§\s*\d+\s*[a-zA-Z]?\s*\.)|^(art\.\s*\d+\s*[a-zA-Z]?)", re.IGNORECASE
)
NUMBER_LETTER_PATTERN = re.compile(r"(\d+)\s*([a-zA-Z]*)")
SUPER_SCRIPT_PATTERN = re.compile(r"^\s*<sup>\s*\d+\s*</sup>\s*$", re.IGNORECASE)
provision_sequences = {}


def reset_provision_sequences():
    global provision_sequences
    provision_sequences = {}


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
    Builds an HTML table from a group of elements with the same TableID using improved positioning logic.

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

    # 1. First pass: Extract row information and organize by row/cell
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
        cell_index = int(cell_index_str) if cell_index_str else 1

        # Get positional data from element
        bounds = element.get("Bounds", [])
        char_bounds = element.get("CharBounds", [])

        if char_bounds:
            left = min(bounds[0] for bounds in char_bounds)
            top = min(bounds[1] for bounds in char_bounds)
            right = max(bounds[2] for bounds in char_bounds)
            bottom = max(bounds[3] for bounds in char_bounds)
        elif bounds:
            left, top, right, bottom = bounds
        else:
            left = top = right = bottom = 0

        positional_data = {"left": left, "top": top, "right": right, "bottom": bottom}

        # Create a unique cell identifier
        cell_key = f"{row_index}_{cell_tag}_{cell_index}"

        # Initialize cell if not exists
        if cell_key not in rows[row_index]["cells"]:
            rows[row_index]["cells"][cell_key] = {
                "tag": cell_tag,
                "content": [],
                "attributes": {},
                "position": cell_index,
                "positional_data": positional_data,
                "metadata": {
                    "page": element.get("Page", 0),
                    "font_weight": element.get("Font", {}).get("weight", 400),
                    "font_size": element.get("TextSize", 12),
                    "font_family": element.get("Font", {}).get("family_name", ""),
                    "text_color": element.get("attributes", {}).get("TextColor", ""),
                    "num_type": element.get("attributes", {}).get("NumType", ""),
                },
            }

        # Add text content - handle special characters conversion
        if "Text" in element:
            text = element.get("Text", "").strip()

            # Process special characters based on attributes (same logic as process_element)
            fraction_type = element.get("attributes", {}).get("Fraction", "")
            text_position = element.get("attributes", {}).get("TextPosition", "")

            # Apply special character conversion
            # Store original text and formatted text
            content_item = {
                "raw_text": text,
                "text": text,  # Will be updated based on conversion rules
                "element_id": element.get("unique_element_id", ""),
                "metadata": {
                    "page": element.get("Page", 0),
                    "font_weight": element.get("Font", {}).get("weight", 400),
                    "font_size": element.get("TextSize", 12),
                    "font_family": element.get("Font", {}).get("family_name", ""),
                    "text_color": element.get("attributes", {}).get("TextColor", ""),
                    "num_type": element.get("attributes", {}).get("NumType", ""),
                },
                "positional_data": positional_data,
                "attributes": element.get("attributes", {}),
                "special_format": None,  # Track what special formatting we applied
            }

            # Apply special character conversion rules
            if fraction_type == "Numerator":
                content_item["special_format"] = "numerator"
                content_item["text"] = f"<numerator>{text}</numerator>"
            elif fraction_type == "SLASH":
                content_item["special_format"] = "frasl"
                content_item["text"] = "&frasl;"
            elif fraction_type == "Denominator":
                content_item["special_format"] = "denominator"
                content_item["text"] = f"<denominator>{text}</denominator>"
            elif text_position == "Sup":
                content_item["special_format"] = "sup"
                content_item["text"] = f"<sup>{text}</sup>"
            elif text_position == "Sub":
                content_item["special_format"] = "sub"
                content_item["text"] = f"<sub>{text}</sub>"

            # Add to content list
            rows[row_index]["cells"][cell_key]["content"].append(content_item)

        # Store cell element attributes if this is the actual cell element
        if re.search(rf"/{cell_tag}(?:\[\d+\])?$", path):
            for attr_name, attr_value in element.get("attributes", {}).items():
                if attr_name != "TableID":
                    rows[row_index]["cells"][cell_key]["attributes"][
                        attr_name
                    ] = attr_value

    # If no rows were found, return an empty table
    if not rows:
        return table

    # Find the first row (header row)
    first_row_index = min(rows.keys())
    header_row = rows[first_row_index]

    # 2. Determine column boundaries based on header cells' left positions
    column_starts = []
    right_most_boundary = 0

    # Extract left-most positions from header cells
    for cell_key, cell_data in header_row["cells"].items():
        column_starts.append(cell_data["positional_data"]["left"])

    # Sort column starts
    column_starts = sorted(column_starts)

    # Find the right-most boundary from all cells in the table
    for row_index, row_data in rows.items():
        for cell_key, cell_data in row_data["cells"].items():
            right_boundary = cell_data["positional_data"]["right"]
            right_most_boundary = max(right_most_boundary, right_boundary)

    # Create column ranges based on header cells' left positions and the right-most boundary
    column_ranges = []
    for i, left_pos in enumerate(column_starts):
        # The right boundary is either the next column start or the right-most value
        right_pos = (
            column_starts[i + 1] if i + 1 < len(column_starts) else right_most_boundary
        )
        center_pos = (left_pos + right_pos) / 2
        column_ranges.append(
            {"left": left_pos, "right": right_pos, "center": center_pos}
        )

    # 3. Create thead and tbody
    thead = soup.new_tag("thead")
    tbody = soup.new_tag("tbody")

    # Determine if first row is a header row
    is_header_row = any(
        cell["tag"] == "TH"
        for cell in rows.get(first_row_index, {}).get("cells", {}).values()
    )

    # 4. Generate the rows
    for row_index in sorted(rows.keys()):
        row_data = rows[row_index]
        tr = soup.new_tag("tr")

        # Add row attributes if any
        for attr_name, attr_value in row_data.get("attributes", {}).items():
            tr[attr_name] = attr_value

        # Organize cells by column
        cells_by_column = {}

        for cell_key, cell_data in row_data["cells"].items():
            cell_left = cell_data["positional_data"]["left"]
            cell_right = cell_data["positional_data"]["right"]
            cell_center = (cell_left + cell_right) / 2

            # Find the column with the most overlap
            max_overlap = 0
            best_column_index = None

            for col_idx, col_range in enumerate(column_ranges):
                # Calculate overlap between cell and column range
                overlap_start = max(cell_left, col_range["left"])
                overlap_end = min(cell_right, col_range["right"])

                if overlap_end > overlap_start:  # There is overlap
                    overlap_amount = overlap_end - overlap_start
                    cell_width = cell_right - cell_left

                    # Calculate overlap percentage relative to cell width
                    overlap_percentage = (
                        overlap_amount / cell_width if cell_width > 0 else 0
                    )

                    if overlap_percentage > max_overlap:
                        max_overlap = overlap_percentage
                        best_column_index = col_idx

            # If no overlap found, assign to nearest column based on center point
            if best_column_index is None:
                min_distance = float("inf")
                for col_idx, col_range in enumerate(column_ranges):
                    distance = abs(cell_center - col_range["center"])
                    if distance < min_distance:
                        min_distance = distance
                        best_column_index = col_idx

            # Assign cell to column
            if best_column_index is not None:
                if best_column_index not in cells_by_column:
                    cells_by_column[best_column_index] = []
                cells_by_column[best_column_index].append(cell_data)

        # Create a cell for each column range
        for col_idx, col_range in enumerate(column_ranges):
            # Get cells for this column (may be multiple or none)
            column_cells = cells_by_column.get(col_idx, [])

            # Create appropriate tag (th for header row, td for other rows)
            is_header = row_index == first_row_index and is_header_row
            tag_name = "th" if is_header else "td"
            cell_element = soup.new_tag(tag_name)

            # Add cells to this column
            for cell_data in column_cells:
                # Add metadata attributes to the cell element
                for meta_key, meta_value in cell_data["metadata"].items():
                    if meta_value:
                        cell_element[f"data-{meta_key.replace('_', '-')}"] = str(
                            meta_value
                        )

                # Add positional data to the cell
                positional_data = cell_data["positional_data"]
                cell_element["data-vertical-position-left"] = str(
                    positional_data["left"]
                )
                cell_element["data-vertical-position-top"] = str(positional_data["top"])
                cell_element["data-vertical-position-right"] = str(
                    positional_data["right"]
                )
                cell_element["data-vertical-position-bottom"] = str(
                    positional_data["bottom"]
                )

                # Add any cell-level attributes
                for attr_key, attr_value in cell_data.get("attributes", {}).items():
                    cell_element[attr_key] = attr_value

                # Process content, preserving exact order
                # Process each content item in its original order
                i = 0
                while i < len(cell_data.get("content", [])):
                    content_item = cell_data["content"][i]

                    if not isinstance(content_item, dict):
                        # Legacy format (plain text)
                        span = soup.new_tag("span")
                        span.string = str(content_item)
                        cell_element.append(span)
                        i += 1
                        continue

                    # Get special format and raw text
                    special_format = content_item.get("special_format")
                    text = content_item.get("raw_text", "")

                    # Check if this could be the start of a fraction sequence
                    if special_format == "numerator" and i + 2 < len(
                        cell_data["content"]
                    ):
                        # Check if the next two items complete a fraction
                        next_item = cell_data["content"][i + 1]
                        next_next_item = cell_data["content"][i + 2]

                        if (
                            isinstance(next_item, dict)
                            and isinstance(next_next_item, dict)
                            and next_item.get("special_format") == "frasl"
                            and next_next_item.get("special_format") == "denominator"
                        ):

                            # We have a complete fraction - create the elements
                            num_element = soup.new_tag("numerator")
                            num_element.string = text

                            # Add metadata to numerator element
                            for meta_key, meta_value in content_item.get(
                                "metadata", {}
                            ).items():
                                if meta_value:
                                    num_element[
                                        f"data-{meta_key.replace('_', '-')}"
                                    ] = str(meta_value)

                            denom_element = soup.new_tag("denominator")
                            denom_element.string = next_next_item.get("raw_text", "")

                            # Add metadata to denominator element
                            for meta_key, meta_value in next_next_item.get(
                                "metadata", {}
                            ).items():
                                if meta_value:
                                    denom_element[
                                        f"data-{meta_key.replace('_', '-')}"
                                    ] = str(meta_value)

                            # Add the complete fraction
                            cell_element.append(num_element)
                            cell_element.append("\u2044")  # Unicode fraction slash
                            cell_element.append(denom_element)

                            # Skip the fraction components we just processed
                            i += 3
                            continue

                    # Handle other special formats
                    if special_format == "sup":
                        element_span = soup.new_tag("sup")
                        element_span.string = text
                    elif special_format == "sub":
                        element_span = soup.new_tag("sub")
                        element_span.string = text
                    elif special_format == "numerator":
                        element_span = soup.new_tag("numerator")
                        element_span.string = text
                    elif special_format == "denominator":
                        element_span = soup.new_tag("denominator")
                        element_span.string = text
                    elif special_format == "frasl":
                        # Just add the fraction slash character
                        cell_element.append("\u2044")
                        i += 1
                        continue
                    else:
                        # Regular span
                        element_span = soup.new_tag("span")
                        element_span.string = text

                    # Add metadata and positional data
                    for meta_key, meta_value in content_item.get(
                        "metadata", {}
                    ).items():
                        if meta_value:
                            element_span[f"data-{meta_key.replace('_', '-')}"] = str(
                                meta_value
                            )

                    pos_data = content_item.get("positional_data", {})
                    if pos_data:
                        element_span["data-vertical-position-left"] = str(
                            pos_data["left"]
                        )
                        element_span["data-vertical-position-top"] = str(
                            pos_data["top"]
                        )
                        element_span["data-vertical-position-right"] = str(
                            pos_data["right"]
                        )
                        element_span["data-vertical-position-bottom"] = str(
                            pos_data["bottom"]
                        )

                    # Add page count
                    element_span["data-page-count"] = str(
                        content_item.get("metadata", {}).get("page", 0)
                    )

                    # Add element ID for reference
                    if content_item.get("element_id"):
                        element_span["data-element-id"] = content_item["element_id"]

                    # Add to cell
                    cell_element.append(element_span)

                    # Add spaces between elements for readability in the output
                    if i < len(cell_data.get("content", [])) - 1:
                        cell_element.append(" ")

                    # Move to next content item
                    i += 1

            # Add the cell to the row with table ID
            cell_element["law-data-table-id"] = str(table_id)
            tr.append(cell_element)

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
    # TODO: Check if this can be removed due to manipulating the elements in extend_metadata.py
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

    # Check if the element is part of a fraction
    fraction_type = element.get("attributes", {}).get("Fraction", "")
    if fraction_type == "Numerator":
        text = f"<numerator>{text}</numerator>"
    elif fraction_type == "SLASH":
        text = "\u2044"
    elif fraction_type == "Denominator":
        text = f"<denominator>{text}</denominator>"
    # Only process superscript/subscript if not part of a fraction
    elif element.get("attributes", {}).get("TextPosition", "") == "Sup":
        text = f"<sup>{text}</sup>"
    elif element.get("attributes", {}).get("TextPosition", "") == "Sub":
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

    # Global tracking of provision sequences
    global provision_sequences

    if is_provision:
        # Extract number/letter information for provisions
        number_letter_match = NUMBER_LETTER_PATTERN.search(text)
        if number_letter_match:
            number = number_letter_match.group(1)
            letter = number_letter_match.group(2) or ""

            # Create base provision identifier (without dashes for letter/word suffixes)
            prov_id = f"{number}{letter}"

            # Track sequence number
            if prov_id not in provision_sequences:
                provision_sequences[prov_id] = 0
            seq_num = provision_sequences[prov_id]

            # Format ID with sequence, provision, and no subprovision part yet
            provision_attr = f' class="provision" id="seq-{seq_num}-prov-{prov_id}"'

            # Increment for next occurrence
            provision_sequences[prov_id] += 1

        # Remove text color data for provisions
        text_color_data = ""
    else:
        # Set text color if available
        text_color = element.get("attributes", {}).get("TextColor", "")
        text_color_data = f"data-text-color='{text_color}'" if text_color else ""

    # Sup type attribute if available
    num_type = element.get("attributes", {}).get("NumType", "")
    num_type_data = f"data-num-type='{num_type}'" if num_type else ""

    # Determine the HTML tag using the helper function
    tag = determine_tag(is_provision, heading_level, text, index, last_special_index)

    # Construct the final HTML element with attributes
    content = (
        f"<{tag} {positional_data} {font_data} data-page-count='{page}' "
        f"{provision_attr} {text_color_data} {num_type_data}>{text}</{tag}>"
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
    reset_provision_sequences()
    json_data = read_json(json_file_law_updated)
    
    # Extract law_id and version from file path
    file_path = Path(json_file_law_updated)
    law_id = None
    version = None
    folder = "zhlex_files"  # Default folder
    
    # Try to extract from path structure: .../zhlex_files/170.4/118/170.4-118-modified-updated.json
    try:
        if "zhlex_files_test" in str(file_path):
            folder = "zhlex_files_test"
        elif "zhlex_files" in str(file_path):
            folder = "zhlex_files"
            
        # Extract law_id and version from path
        parts = file_path.parts
        for i, part in enumerate(parts):
            if part in ["zhlex_files", "zhlex_files_test"]:
                if i + 2 < len(parts):
                    law_id = parts[i + 1]  # e.g., "170.4"
                    version = parts[i + 2]  # e.g., "118"
                break
    except Exception as e:
        logger.warning(f"Could not extract law_id and version from path: {e}")
    
    # Apply corrections if law_id and version are available
    if law_id and version and json_data:
        logger.info(f"Applying corrections for law {law_id} version {version}")
        correction_applier = CorrectionApplier(base_path="data/zhlex")
        elements = json_data.get("elements", [])
        
        # Apply corrections
        corrected_elements, corrections_info = correction_applier.apply_corrections(
            elements, law_id, version, folder
        )
        
        # Update json_data with corrected elements
        json_data["elements"] = corrected_elements
        
        if corrections_info:
            logger.info(f"Corrections applied: {corrections_info}")
    
    # Get title from metadata doc_info
    erlasstitel = metadata["doc_info"]["erlasstitel"]
    html_content = convert_to_html(json_data, erlasstitel, marginalia)
    # Write the html content to a file
    with open(html_file, "w", encoding="utf-8") as file:
        file.write(str(html_content))


if __name__ == "__main__":
    # TODO: Allow command-line arguments
    pass
