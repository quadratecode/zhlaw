# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

import fitz
import re
import json
import logging
import random

# Get logger from main module
logger = logging.getLogger(__name__)

# Module-level constants for default values and magic numbers
MM_TO_POINTS = 2.83465  # 1 mm ≈ 2.83465 points
DEFAULT_PAGE_HEIGHT = 595.0
DEBUG_DRAWING_COLOR = (1, 0, 0)  # Red color for debug drawing
DEBUG_DRAWING_WIDTH = 1.5
DPI_DEFAULT = 300


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------
def get_vertical_span(element):
    """
    Returns the top and bottom vertical positions of an element.
    Uses 'CharBounds' if available; otherwise, uses 'Bounds'.
    """
    if "CharBounds" in element and element["CharBounds"]:
        top = min(bounds[1] for bounds in element["CharBounds"])
        bottom = max(bounds[3] for bounds in element["CharBounds"])
    else:
        top = element["Bounds"][1]
        bottom = element["Bounds"][3]
    return top, bottom


def expand_rect(rect, margin):
    """
    Expands a given fitz.Rect by a margin on all sides.
    """
    return fitz.Rect(
        rect.x0 - margin,
        rect.y0 - margin,
        rect.x1 + margin,
        rect.y1 + margin,
    )


def try_split_provision(elements, i):
    """
    Splits an element if its text matches a provision pattern.
    Returns True if a split occurred.
    """
    text = elements[i]["Text"].strip()
    match = re.match(r"^(§ \d+[a-zA-Z]?\.)(.*)$", text)
    if match:
        before, after = match.groups()
        if after:
            new_element = elements[i].copy()
            new_element["Text"] = after.strip()
            elements[i]["Text"] = before
            bounds_key = "CharBounds" if "CharBounds" in elements[i] else "Bounds"
            new_element[bounds_key] = elements[i].get(bounds_key, [])
            elements.insert(i + 1, new_element)
        return True
    return False


def try_merge_comma(elements, i):
    """
    Merges elements if the current element contains a comma (",").
    Returns True if a merge occurred.
    """
    text = elements[i]["Text"].strip()

    # Check if this is a comma and there are elements before and after it
    if text == "," and i > 0 and i < len(elements) - 1:
        # Get the next element's text and strip whitespace
        next_text = elements[i + 1]["Text"].strip()

        # Define a pattern for enumeration markers (single character or roman numeral followed by period)
        # This pattern matches patterns like "a.", "b.", "I.", "IV.", "1.", etc.
        enum_pattern = re.compile(r"^([IVXLCDM]+|[a-zA-Z0-9])\.(\s.*)?$")

        # If the next element starts with a single character/roman numeral followed by a period, don't merge
        if enum_pattern.match(next_text):
            return False

        # If we get here, proceed with the merge as before
        bounds_key = "CharBounds" if "CharBounds" in elements[i - 1] else "Bounds"
        elements[i - 1]["Text"] += ", " + elements[i + 1]["Text"]
        elements[i - 1][bounds_key] += elements[i + 1].get(bounds_key, [])
        del elements[i : i + 2]
        return True

    return False


def try_merge_section(elements, i):
    """
    Merges elements if the current element is a section sign ("§").
    Returns True if a merge occurred.
    """
    text = elements[i]["Text"].strip()
    if text == "§" and i < len(elements) - 1:
        bounds_key = "CharBounds" if "CharBounds" in elements[i] else "Bounds"
        elements[i + 1]["Text"] = "§ " + elements[i + 1]["Text"]
        elements[i + 1][bounds_key] = elements[i].get(bounds_key, []) + elements[
            i + 1
        ].get(bounds_key, [])
        del elements[i]
        return True
    return False


# -----------------------------------------------------------------------------
# Core Functions
# -----------------------------------------------------------------------------
def flatten_elements(elements):
    """
    Unnests 'Kids' from elements and adds them as top-level elements.
    """
    flat_list = []
    for element in elements:
        # Append the parent element first before its children
        flat_list.append(element)
        if "Kids" in element:
            kids = element.pop("Kids")
            # Recursively flatten the kids and extend them right after the parent
            flat_list.extend(flatten_elements(kids))
    return flat_list


def assign_unique_ids(elements):
    """
    Assigns a unique 20-digit random string ID to each element.
    """
    for element in elements:
        unique_id = "".join(str(random.randint(0, 9)) for _ in range(20))
        element["unique_element_id"] = unique_id
    return elements


def remove_header_footer(elements, header_mm=21, footer_mm=21):
    """
    Removes elements that fall within the header or footer zones.
    """
    header_height = header_mm * MM_TO_POINTS
    footer_height = footer_mm * MM_TO_POINTS

    filtered_elements = []
    for element in elements:
        page_height = element["page_height"]
        top, bottom = get_vertical_span(element)

        # Define header and footer zones
        header_zone = (0, header_height)
        footer_zone = (page_height - footer_height, page_height)

        # If the element is not fully in the header or footer zones, keep it
        if not (bottom <= header_zone[1] or top >= footer_zone[0]):
            filtered_elements.append(element)

    return filtered_elements


def add_page_heights_to_elements(document_path, elements):
    """
    Adds the height of each page to the elements based on their page number.
    """
    doc = fitz.open(document_path)  # Open the PDF file
    page_heights = [page.rect.height for page in doc]  # List of heights for each page

    for element in elements:
        if "Page" in element:
            page_index = element["Page"]
            if page_index < len(page_heights):
                element["page_height"] = page_heights[page_index]
            else:
                logger.warning(
                    f"Page index {page_index} out of range for document with {len(page_heights)} pages."
                )
        else:
            logger.warning("Element missing 'Page' key; cannot assign page height.")

    doc.close()  # Close the document to free resources
    return elements


def merge_and_split_elements(elements):
    """
    Merges and splits elements based on specific text patterns.
    """
    i = 0
    while i < len(elements):
        # Try to split provision elements
        if try_split_provision(elements, i):
            i += 1
            continue

        # Try to merge comma elements
        if try_merge_comma(elements, i):
            continue

        # Try to merge section sign elements
        if try_merge_section(elements, i):
            continue

        i += 1  # Normal increment
    return elements


def extract_hyperlinks(pdf_path):
    """
    Extracts external hyperlinks from the PDF document.
    """
    doc = fitz.open(pdf_path)
    text_with_links = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        links = page.get_links()  # Get links

        for link in links:
            if "uri" in link:
                link_rect = fitz.Rect(link["from"])
                x = 0.02  # Padding value to expand the rect
                expanded_rect = expand_rect(link_rect, x)
                link_text = page.get_textbox(expanded_rect)
                if "\n" in link_text:
                    link_text = link_text.split("\n")[0]
                text_with_links.append(
                    {
                        "page_number": page_num,
                        "text": link_text.strip(),
                        "uri": link["uri"],
                    }
                )

    # Filter out links whose text does not contain any digits
    text_with_links = [
        link for link in text_with_links if any(char.isdigit() for char in link["text"])
    ]

    # Clean up link text by removing brackets, semicolons, and trailing dots
    for link in text_with_links:
        link["text"] = re.sub(r"[();]", "", link["text"]).strip()
        link["text"] = re.sub(r"\.$", "", link["text"])

    doc.close()
    return text_with_links


def del_empty_elements(elements):
    """
    Deletes elements with no text.
    """
    return [element for element in elements if element.get("Text", "")]


def convert_bounds_to_pymupdf(elements):
    """
    Converts coordinate bounds from the API format (origin at bottom-left)
    to PyMuPDF format (origin at top-left) using page height metadata.
    """
    converted_elements = []

    def convert(bounds, page_height):
        left, bottom, right, top = bounds
        x0 = left
        y1 = page_height - bottom
        x1 = right
        y0 = page_height - top
        return (x0, y0, x1, y1)

    for element in elements:
        page_height = element.get("page_height", DEFAULT_PAGE_HEIGHT)
        if "page_height" not in element:
            logger.warning("Element missing 'page_height' key; defaulting to 595.0")
        converted_element = element.copy()  # Shallow copy to preserve data
        if "Bounds" in element:
            converted_element["Bounds"] = convert(element["Bounds"], page_height)
        if "CharBounds" in element:
            converted_element["CharBounds"] = [
                convert(bounds, page_height) for bounds in element["CharBounds"]
            ]
        converted_elements.append(converted_element)

    return converted_elements


def sort_elements(elements, margin_ratio=0.005):
    """
    Sorts elements first by page order, then clusters them by vertical positions,
    and finally orders them left-to-right within clusters.
    """

    def get_midpoint(top, bottom):
        return (top + bottom) / 2.0

    def get_first_horizontal_position(element):
        if "CharBounds" in element and element["CharBounds"]:
            return element["CharBounds"][0][0]
        else:
            return element["Bounds"][0]

    # Group elements by page
    pages = {}
    for e in elements:
        pages.setdefault(e["Page"], []).append(e)

    sorted_result = []
    for page_no in sorted(pages.keys()):
        page_elems = pages[page_no]
        page_height = page_elems[0]["page_height"]
        margin = page_height * margin_ratio

        # Create clusters based on vertical proximity
        clusters = []
        for elem in page_elems:
            top, bottom = get_vertical_span(elem)
            midpoint = get_midpoint(top, bottom)
            placed = False
            for cluster in clusters:
                c_top, c_bottom = cluster["span"]
                c_midpoint = get_midpoint(c_top, c_bottom)
                if abs(c_midpoint - midpoint) <= margin:
                    cluster["elements"].append(elem)
                    cluster["span"] = (min(c_top, top), max(c_bottom, bottom))
                    placed = True
                    break
            if not placed:
                clusters.append({"elements": [elem], "span": (top, bottom)})

        # Sort clusters by their vertical midpoint
        clusters.sort(key=lambda c: get_midpoint(c["span"][0], c["span"][1]))
        # Within each cluster, sort left-to-right
        for cluster in clusters:
            cluster["elements"].sort(key=get_first_horizontal_position)
            sorted_result.extend(cluster["elements"])

    return sorted_result


def mark_non_subprovision_elements(elements):
    """
    Marks elements that should not be treated as subprovisions:
    1. Square/cubic meters (m²/m³)
    2. All subscript elements
    Adds the attribute "NumType": "NoSubprovision" to these elements.
    """
    for i, element in enumerate(elements):
        # Case 1: Superscript numbers (2,3) following 'm' - likely square/cubic meters
        if (
            element.get("attributes", {}).get("TextPosition") == "Sup"
            and element.get("attributes", {}).get("TextColor") != "LinkBlue"
            and element.get("TextSize", 0) > 5
            and element.get("TextSize", 0) < 9
            and any(char in element.get("Text", "") for char in ["2", "3"])
            and i > 0
            and elements[i - 1].get("Text", "").endswith("m")
        ):
            if "attributes" not in element:
                element["attributes"] = {}
            element["attributes"]["NumType"] = "NoSubprovision"

        # Case 2: All subscript elements should not be treated as subprovisions
        elif element.get("attributes", {}).get("TextPosition") == "Sub":
            if "attributes" not in element:
                element["attributes"] = {}
            element["attributes"]["NumType"] = "NoSubprovision"

    return elements


def check_blue_color(document_path, elements, margin=5, dpi=DPI_DEFAULT):
    """
    Checks for blue color within the bounds of text elements in a PDF document.
    """
    doc = fitz.open(document_path)
    zoom = dpi / 72  # Calculate zoom factor
    mat = fitz.Matrix(zoom, zoom)

    for element in elements:
        page = doc.load_page(element["Page"])
        # Process only elements that contain digits and no letters
        if re.search(r"\d", element.get("Text", "")) and not re.search(
            r"[a-zA-Z]", element.get("Text", "")
        ):
            bounds_list = element.get("CharBounds", [element["Bounds"]])
            found_blue = False

            for bounds in bounds_list:
                rect = fitz.Rect(*bounds)
                expanded_rect = expand_rect(rect, margin)
                # Draw debug rectangle on the page
                page.draw_rect(
                    expanded_rect, color=DEBUG_DRAWING_COLOR, width=DEBUG_DRAWING_WIDTH
                )
                clip_pix = page.get_pixmap(clip=expanded_rect, matrix=mat)
                img = clip_pix.samples

                # Check pixel data for blue dominance
                for i in range(0, len(img), 3):
                    r, g, b = img[i], img[i + 1], img[i + 2]
                    if b > r and b > g and b > 100:
                        found_blue = True
                        break
                if found_blue:
                    break

            if found_blue:
                if "attributes" not in element:
                    element["attributes"] = {}
                element["attributes"]["TextColor"] = "LinkBlue"

    doc.close()
    return elements


def map_tables_to_elements(elements):
    """
    Maps table elements to their corresponding CSV file IDs.
    Adds a 'TableID' attribute to elements that belong to a table.

    Args:
        elements: List of elements from the JSON data

    Returns:
        The modified list of elements with table mappings added
    """
    # Step 1: Find all elements with filePaths referencing CSV files
    table_maps = []
    for element in elements:
        if "filePaths" in element:
            table_path = element.get("Path", "")

            # For each file path that references a CSV
            for file_path in element["filePaths"]:
                if file_path.startswith("tables/fileoutpart") and file_path.endswith(
                    ".csv"
                ):
                    # Extract the table ID from the filename (e.g., "tables/fileoutpart1.csv" -> 1)
                    try:
                        table_id = int(
                            file_path.replace("tables/fileoutpart", "").replace(
                                ".csv", ""
                            )
                        )
                        table_maps.append({"path": table_path, "id": table_id})
                        logger.info(
                            f"Found table with path '{table_path}' mapped to CSV ID {table_id}"
                        )
                    except ValueError:
                        logger.warning(
                            f"Could not extract table ID from file path: {file_path}"
                        )

    logger.info(f"Found {len(table_maps)} table elements with CSV files")

    # Step 2: Mark all elements that belong to any table with the corresponding TableID
    marked_count = 0
    for element in elements:
        element_path = element.get("Path", "")

        # Find if this element belongs to any table
        for table_map in table_maps:
            table_path = table_map["path"]

            # Check if this element's path is or starts with the table path
            # This includes the table element itself and any child elements
            if element_path == table_path or element_path.startswith(table_path + "/"):
                # Add or update the attributes dictionary with TableID
                if "attributes" not in element:
                    element["attributes"] = {}
                element["attributes"]["TableID"] = table_map["id"]
                marked_count += 1
                break

    logger.info(f"Marked {marked_count} elements with TableID attributes")
    return elements


def adjust_table_headers_with_section_sign(elements):
    """
    Identifies tables where the header row contains a § symbol and adjusts
    the table structure so that the second row becomes the new header row.

    Args:
        elements: List of elements from the JSON data

    Returns:
        The modified list of elements
    """
    # Step 1: Group elements by TableID and organize by row
    tables = {}

    for element in elements:
        table_id = element.get("attributes", {}).get("TableID")
        if table_id is None:
            continue

        path = element.get("Path", "")

        # Extract row information from the path
        row_match = re.search(r"/TR(?:\[(\d+)\])?", path)
        if not row_match:
            continue

        # Get row index (defaulting to 1 if not explicitly specified)
        row_index = int(row_match.group(1)) if row_match.group(1) else 1

        # Initialize table structure if needed
        if table_id not in tables:
            tables[table_id] = {}

        # Initialize row if needed
        if row_index not in tables[table_id]:
            tables[table_id][row_index] = []

        # Add element to its row
        tables[table_id][row_index].append(element)

    # Step 2: Identify tables with § in the header row
    tables_to_adjust = []

    for table_id, rows in tables.items():
        if 1 in rows:  # If table has a first row
            # Check if any element in the first row contains §
            for elem in rows[1]:
                if "§" in elem.get("Text", ""):
                    tables_to_adjust.append(table_id)
                    break

    # Step 3: Adjust identified tables
    for table_id in tables_to_adjust:
        rows = tables[table_id]
        logger.info(f"Adjusting table {table_id} - § found in header row")

        # Step 3a: Remove TableID from first row elements
        for elem in rows.get(1, []):
            if "attributes" in elem and "TableID" in elem["attributes"]:
                del elem["attributes"]["TableID"]

        # Step 3b: Convert second row to header row
        if 2 in rows:
            for elem in rows[2]:
                path = elem.get("Path", "")

                # Update row index in path (TR[2] -> TR or TR[1])
                if "/TR[2]/" in path:
                    new_path = path.replace("/TR[2]/", "/TR/")
                else:
                    # Fallback for other path patterns
                    new_path = re.sub(r"/TR(?:\[2\])?/", "/TR/", path)

                # Convert table cells from TD to TH if present
                if "/TD/" in new_path:
                    new_path = new_path.replace("/TD/", "/TH/")
                elif "/TD[" in new_path:
                    new_path = re.sub(r"/TD\[(\d+)\]/", r"/TH[\1]/", new_path)

                # Update the element's path
                elem["Path"] = new_path

        # Step 3c: Update subsequent rows (decrement row numbers)
        for row_index in sorted(rows.keys()):
            if row_index <= 2:  # Skip first two rows (already processed)
                continue

            for elem in rows[row_index]:
                path = elem.get("Path", "")

                # Decrement row index
                new_row_index = row_index - 1

                # Update path with new row index
                if f"/TR[{row_index}]/" in path:
                    new_path = path.replace(
                        f"/TR[{row_index}]/", f"/TR[{new_row_index}]/"
                    )
                    elem["Path"] = new_path

    return elements


def try_merge_dash_elements(elements, i):
    """
    Merges three consecutive elements when the middle one is a dash (possibly with whitespace)
    and all three have a font_weight above 400.
    Returns True if a merge occurred.
    """
    # Check if current element exists and we have enough elements to check the pattern
    if i < 0 or i >= len(elements) - 2:
        return False

    # Get the three consecutive elements
    first_element = elements[i]
    middle_element = elements[i + 1]
    last_element = elements[i + 2]

    # Check if all three elements have font_weight above 400
    first_weight = first_element.get("Font", {}).get("weight", 400)
    middle_weight = middle_element.get("Font", {}).get("weight", 400)
    last_weight = last_element.get("Font", {}).get("weight", 400)

    if first_weight <= 400 or middle_weight <= 400 or last_weight <= 400:
        return False

    # Check if the middle element is just a dash possibly with whitespace
    middle_text = middle_element.get("Text", "")
    # Strip and check if it's just a dash with possible whitespace
    if middle_text.strip() != "-":
        return False

    # Merge the elements by concatenating the text without the dash
    first_text = first_element.get("Text", "").rstrip()
    last_text = last_element.get("Text", "").lstrip()

    # Update the first element's text
    first_element["Text"] = first_text + last_text

    # Merge the CharBounds or Bounds
    bounds_key = "CharBounds" if "CharBounds" in first_element else "Bounds"
    if bounds_key in first_element and bounds_key in last_element:
        first_element[bounds_key] += last_element.get(bounds_key, [])

    # Delete the middle and last elements
    del elements[i + 1 : i + 3]

    return True


def merge_dash_elements(elements):
    """
    Merges three consecutive elements where the middle element is a dash (possibly with whitespace)
    and all three have a font_weight above 400.
    The dash and surrounding whitespace are removed.
    """
    i = 0
    while i < len(elements) - 2:  # We need at least 3 elements
        # Try to merge dash elements
        if try_merge_dash_elements(elements, i):
            continue  # Don't increment i as the array has changed

        i += 1  # Increment if no merge occurred

    return elements


def remove_section_elements_from_tables(elements):
    """
    Identifies elements within tables that start with the § symbol (ignoring whitespace)
    and removes the TableID attribute from them and all subsequent elements with the same TableID
    based on their position in the JSON array.

    Args:
        elements: List of elements from the JSON data

    Returns:
        The modified list of elements
    """
    logger.info("Checking for section symbols in tables...")
    tables_with_section = {}
    removed_count = 0

    # Step 1: Iterate through elements in order and find where § starts
    for i, element in enumerate(elements):
        table_id = element.get("attributes", {}).get("TableID")
        if table_id is None:
            continue

        text = element.get("Text", "").strip()
        if text.startswith("§"):
            if table_id not in tables_with_section:
                tables_with_section[table_id] = i
                logger.info(
                    f"Found § in table {table_id} at element position {i}, text: '{text}'"
                )

    # Step 2: Remove TableID from elements after the § position
    for i, element in enumerate(elements):
        table_id = element.get("attributes", {}).get("TableID")
        if table_id is None:
            continue

        if table_id in tables_with_section and i >= tables_with_section[table_id]:
            # Remove TableID from element's attributes
            if "attributes" in element and "TableID" in element["attributes"]:
                del element["attributes"]["TableID"]
                removed_count += 1

    if tables_with_section:
        logger.info(
            f"Removed TableID attribute from {removed_count} elements across {len(tables_with_section)} tables"
        )

    return elements


def identify_fractions(elements):
    """
    Identifies and marks fractions in the document. A fraction is identified as:
    1. An element with a small number (either with TextPosition:"Sup" or small TextSize or Path contains "/Reference")
    2. Followed by an element with only a slash "/"
    3. Followed by an element with a small number (either with TextPosition:"Sub" or small TextSize)

    When identified, these elements are modified:
    - "TextPosition" key is removed if present
    - "Fraction" key is added with values "Numerator", "SLASH", or "Denominator"

    Args:
        elements: List of elements to process

    Returns:
        The modified list of elements
    """
    # Find the common text size to use as reference for determining small text
    text_sizes = [elem.get("TextSize", 0) for elem in elements if "TextSize" in elem]
    if text_sizes:
        avg_text_size = sum(text_sizes) / len(text_sizes)
        # Small text threshold (70% of average size could be super/subscript)
        small_text_threshold = avg_text_size * 0.7
    else:
        small_text_threshold = 5.0  # Fallback value if no text sizes found

    i = 0
    while i < len(elements) - 2:  # Need at least 3 elements for a fraction
        # Check if current element could be a numerator
        current = elements[i]
        text_current = current.get("Text", "").strip()

        # Check various conditions that might indicate a numerator
        is_current_superscript = (
            current.get("attributes", {}).get("TextPosition") == "Sup"
        )
        is_small_text = current.get("TextSize", avg_text_size) < small_text_threshold

        # Is this likely a numerator?
        is_likely_numerator = text_current.isdigit() and (
            is_current_superscript or is_small_text
        )

        # Check if next element is a slash
        next_elem = elements[i + 1]
        text_next = next_elem.get("Text", "").strip()
        is_slash = text_next == "/"

        # Check if next-next element could be a denominator
        next_next_elem = elements[i + 2]
        text_next_next = next_next_elem.get("Text", "").strip()

        # Check various conditions that might indicate a denominator
        is_next_next_subscript = (
            next_next_elem.get("attributes", {}).get("TextPosition") == "Sub"
        )
        next_next_small_text = (
            next_next_elem.get("TextSize", avg_text_size) < small_text_threshold
        )
        has_style_span_path = "/StyleSpan" in next_next_elem.get("Path", "")

        # Is this likely a denominator?
        is_likely_denominator = text_next_next.isdigit() and (
            is_next_next_subscript or next_next_small_text or has_style_span_path
        )

        # If we've identified a likely fraction pattern
        if is_likely_numerator and is_slash and is_likely_denominator:
            # Modify the elements

            # First element (numerator)
            if "attributes" not in current:
                current["attributes"] = {}
            if "TextPosition" in current["attributes"]:
                del current["attributes"]["TextPosition"]
            current["attributes"]["Fraction"] = "Numerator"
            current["attributes"]["NumType"] = "NoSubprovision"

            # Second element (slash)
            if "attributes" not in next_elem:
                next_elem["attributes"] = {}
            next_elem["attributes"]["Fraction"] = "SLASH"

            # Third element (denominator)
            if "attributes" not in next_next_elem:
                next_next_elem["attributes"] = {}
            if "TextPosition" in next_next_elem["attributes"]:
                del next_next_elem["attributes"]["TextPosition"]
            next_next_elem["attributes"]["Fraction"] = "Denominator"
            current["attributes"]["NumType"] = "NoSubprovision"

            # Skip the elements we've processed
            i += 3
        else:
            # Move to next element
            i += 1

    return elements


def normalize_font_weight_after_final_provisions(elements):
    """
    Normalizes font weight for elements after final or transitional provisions.

    If an element contains "schlussbestimmung", "übergangsbestimmung", etc. (case insensitive),
    all subsequent elements that:
    1. Contain "gesetz" or "verordnung"
    2. Have a font weight above 400
    Will have their font weight reset to 400.

    Args:
        elements: List of elements to process

    Returns:
        The processed list of elements
    """
    # Flag to track if we've found a final provision element
    found_final_provision = False

    for i, element in enumerate(elements):
        text = element.get("Text", "").lower()

        # Check if this element contains any of the target phrases
        if (
            "schlussbestimmung" in text
            or "übergangsbestimmung" in text
            or "schlussbestimmungen" in text
            or "übergangsbestimmungen" in text
        ):
            found_final_provision = True
            continue

        # If we found a final provision, process subsequent elements
        if found_final_provision:
            text = element.get("Text", "").lower()

            # Check if this element contains "gesetz" or "verordnung"
            if "gesetz" in text or "verordnung" in text:
                # Get the current font weight
                font_weight = element.get("Font", {}).get("weight", 400)
                font_size = element.get("TextSize", 9.17999267578125)

                # If font weight is above 400 and font size smaller or eqal 12
                # reset font weight to 400
                if font_weight > 400 and font_size <= 9.2:
                    if "Font" not in element:
                        element["Font"] = {}

                    element["Font"]["weight"] = 400

                    # Log the change
                    logger.info(f"Reset font weight to 400 for element: {text[:30]}...")

    return elements


def main(original_pdf_path, modified_pdf_path, json_path, updated_json_path):
    """
    Extracts color information and hyperlinks from the PDF and updates the JSON data.
    """
    hyperlinks = extract_hyperlinks(original_pdf_path)

    with open(json_path, "r", encoding="utf-8") as file:
        json_data = json.load(file)

    elements = json_data["elements"]

    # Flatten elements
    elements = flatten_elements(elements)
    # Map tables to elements
    elements = map_tables_to_elements(elements)
    # Adjust tables with section signs in header
    elements = adjust_table_headers_with_section_sign(elements)
    # Remove elements with no text
    elements = del_empty_elements(elements)
    # Add page heights to elements
    elements = add_page_heights_to_elements(modified_pdf_path, elements)
    # Convert coordinates to PyMuPDF format
    elements = convert_bounds_to_pymupdf(elements)
    # Sort elements
    elements = sort_elements(elements)
    # Remove provisions from tables
    elements = remove_section_elements_from_tables(elements)
    # Assign unique IDs to elements
    elements = assign_unique_ids(elements)
    # Merge dash elements
    elements = merge_dash_elements(elements)
    # Normalize font weight after final provisions
    elements = normalize_font_weight_after_final_provisions(elements)
    # Remove header and footer elements
    elements = remove_header_footer(elements)
    # Check for blue color in elements
    elements = check_blue_color(modified_pdf_path, elements)
    # Mark square and cubic meters
    elements = mark_non_subprovision_elements(elements)
    # Check for fractions
    elements = identify_fractions(elements)
    # Add hyperlinks to extended_metadata
    if "extended_metadata" not in json_data:
        json_data["extended_metadata"] = {}
    json_data["extended_metadata"]["hyperlinks"] = hyperlinks
    # Merge and split elements
    elements = merge_and_split_elements(elements)
    # Update JSON data
    json_data["elements"] = elements

    with open(updated_json_path, "w", encoding="utf-8") as file:
        json.dump(json_data, file, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    # TODO: Allow command-line arguments
    pass
