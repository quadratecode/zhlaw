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


# Function to unnest 'Kids' and add them as top-level elements
def flatten_elements(elements):
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
    for element in elements:
        # Generate a random string of 20 digits
        unique_id = "".join(str(random.randint(0, 9)) for _ in range(20))
        element["unique_element_id"] = unique_id
    return elements


def remove_header_footer(elements, header_mm=21, footer_mm=21):
    mm_to_points = 2.83465  # 1 mm is approximately 2.83465 points

    def get_vertical_span(element):
        if "CharBounds" in element:
            top = min(bounds[1] for bounds in element["CharBounds"])
            bottom = max(bounds[3] for bounds in element["CharBounds"])
        else:
            top = element["Bounds"][1]
            bottom = element["Bounds"][3]
        return top, bottom

    header_height = header_mm * mm_to_points
    footer_height = footer_mm * mm_to_points

    filtered_elements = []
    for element in elements:
        page_height = element["page_height"]
        vertical_span = get_vertical_span(element)

        # Define header and footer zones
        header_zone = (0, header_height)
        footer_zone = (page_height - footer_height, page_height)

        # Check if element is in the header or footer zone
        if not (
            vertical_span[1] <= header_zone[1] or vertical_span[0] >= footer_zone[0]
        ):
            filtered_elements.append(element)

    return filtered_elements


def add_page_heights_to_elements(document_path, elements):
    """
    Adds the height of each page to the elements based on their page number.

    Args:
    document_path (str): Path to the PDF document.
    elements (list of dict): A list of dictionaries, each expected to contain at least a 'Page' key that indexes the page number.

    Returns:
    list of dict: The updated list of elements, each now including a 'PageHeight' key.
    """
    doc = fitz.open(document_path)  # Open the PDF file
    page_heights = [page.rect.height for page in doc]  # List of heights for each page

    for element in elements:
        if "Page" in element:
            page_index = element["Page"]
            if page_index < len(page_heights):
                element["page_height"] = page_heights[
                    page_index
                ]  # Add page height to the element
            else:
                print(
                    f"Warning: Page index {page_index} out of range for document with {len(page_heights)} pages."
                )
        else:
            print("Warning: Element missing 'Page' key, cannot assign page height.")

    doc.close()  # Close the document to free resources
    return elements


def merge_and_split_elements(elements):
    i = 0
    while i < len(elements):
        text = elements[i]["Text"].strip()

        # Check for § followed by a number, optional single letter, and period
        match = re.match(r"^(§ \d+[a-zA-Z]?\.)(.*)$", text)
        if match:
            before, after = match.groups()
            if after:
                new_element = elements[i].copy()
                new_element["Text"] = after.strip()
                elements[i]["Text"] = before

                # Choose between CharBounds and Bounds
                bounds_key = "CharBounds" if "CharBounds" in elements[i] else "Bounds"
                new_element[bounds_key] = elements[i].get(bounds_key, [])

                elements.insert(i + 1, new_element)
            i += 1  # Move to the next element (new or existing)
            continue  # Skip the rest of the loop and continue with the new i

        if text == "-":
            if i > 0 and i < len(elements) - 1:
                bounds_key = (
                    "CharBounds" if "CharBounds" in elements[i - 1] else "Bounds"
                )
                elements[i - 1]["Text"] += elements[i + 1]["Text"]
                elements[i - 1][bounds_key] += elements[i + 1].get(bounds_key, [])
                del elements[i : i + 2]  # Remove current and next element efficiently
                continue  # Skip increment since we've changed the list size

        elif text == ",":
            if i > 0 and i < len(elements) - 1:
                bounds_key = (
                    "CharBounds" if "CharBounds" in elements[i - 1] else "Bounds"
                )
                elements[i - 1]["Text"] += ", " + elements[i + 1]["Text"]
                elements[i - 1][bounds_key] += elements[i + 1].get(bounds_key, [])
                del elements[i : i + 2]
                continue

        elif text == "§":
            if i < len(elements) - 1:
                bounds_key = "CharBounds" if "CharBounds" in elements[i] else "Bounds"
                elements[i + 1]["Text"] = "§ " + elements[i + 1]["Text"]
                elements[i + 1][bounds_key] = elements[i].get(
                    bounds_key, []
                ) + elements[i + 1].get(bounds_key, [])
                del elements[i]
                continue  # Adjusted for the case where the next element is modified

        i += 1  # Normal increment to move to the next element

    return elements


def extract_hyperlinks(pdf_path):
    doc = fitz.open(pdf_path)
    text_with_links = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        links = page.get_links()  # Get links

        # Process each link
        for link in links:
            # "uri" key indicates an external hyperlink
            if "uri" in link:
                link_rect = fitz.Rect(link["from"])
                x = 0.02  # Padding value to expand the rect and capture surrounding text (0.5 has prooven too much)
                expanded_rect = link_rect + (-x, -x, x, x)
                link_text = page.get_textbox(
                    expanded_rect
                )  # Get text within the expanded rect

                # Discard any text after a newline character
                if "\n" in link_text:
                    link_text = link_text.split("\n")[0]

                text_with_links.append(
                    {
                        "page_number": page_num,
                        "text": link_text.strip(),
                        "uri": link["uri"],
                    }
                )

    # Discard any links where text does not contain a number
    # Some footnotes stretch over multiple lines, which leads to inaccurate matches (e.g. for "ABl")
    text_with_links = [
        link for link in text_with_links if any(char.isdigit() for char in link["text"])
    ]

    # Remove any brackets or semi-colons from the text, strip whitespace
    # Remove any trailing dots
    for link in text_with_links:
        link["text"] = re.sub(r"[();]", "", link["text"]).strip()
        link["text"] = re.sub(r"\.$", "", link["text"])

    return text_with_links


def del_empty_elements(elements):
    """
    Deletes elements with no text.
    """
    return [element for element in elements if element.get("Text", "")]


def convert_bounds_to_pymupdf(elements):
    """
    Converts coordinate bounds from API format (origin at bottom-left) to PyMuPDF format (origin at top-left) for given elements,
    while preserving all other data in the elements. This version uses page height stored in each element's metadata.
    Converts original order of left, bottom, right, top to PyMuPDF of left, top, right, bottom.

    Args:
    elements (list of dict): A list of dictionaries, each of which may contain keys 'CharBounds' and 'Bounds', and should contain 'PageHeight'
    indicating the height of the page to which the element belongs.

    Returns:
    list of dict: A list of dictionaries with all original data and bounds converted to the PyMuPDF coordinate system (x0, y0, x1, y1).
    """
    converted_elements = []  # List to hold all converted elements

    def convert(bounds, page_height):
        left, bottom, right, top = bounds
        x0 = left
        y1 = page_height - bottom
        x1 = right
        y0 = page_height - top
        return (x0, y0, x1, y1)

    for element in elements:
        if "page_height" in element:
            page_height = element["page_height"]
            converted_element = (
                element.copy()
            )  # Make a shallow copy of the element to preserve all existing data
            if "Bounds" in element:
                converted_element["Bounds"] = convert(element["Bounds"], page_height)
            if "CharBounds" in element:
                converted_element["CharBounds"] = [
                    convert(bounds, page_height) for bounds in element["CharBounds"]
                ]
            converted_elements.append(
                converted_element
            )  # Add the converted element to the list
        else:
            print("Warning: Element missing 'page_height' key, cannot convert bounds.")
            converted_elements.append(
                element
            )  # Optionally handle or skip elements without page height

    return converted_elements


def sort_elements(elements, margin_ratio=0.005):
    def get_vertical_span(element):
        if "CharBounds" in element:
            top = min(bounds[1] for bounds in element["CharBounds"])
            bottom = max(bounds[3] for bounds in element["CharBounds"])
        else:
            top = element["Bounds"][1]
            bottom = element["Bounds"][3]
        return top, bottom

    def get_midpoint(element, vertical_span):
        return (vertical_span[0] + vertical_span[1]) / 2

    def get_first_horizontal_position(element):
        if "CharBounds" in element:
            return element["CharBounds"][0][0]  # First tuple, first element (min_x)
        else:
            return element["Bounds"][0]  # min_x of the Bounds

    # Group elements by page number
    elements_by_page = {}
    for element in elements:
        page = element["Page"]
        if page not in elements_by_page:
            elements_by_page[page] = []
        elements_by_page[page].append(element)

    sorted_elements = []
    for page in sorted(elements_by_page.keys()):
        page_elements = elements_by_page[page]
        clusters = []
        page_height = page_elements[0][
            "page_height"
        ]  # Assuming all elements have the same page_height attribute
        margin = page_height * margin_ratio

        # Form clusters based on overlapping vertical spans
        for element in page_elements:
            placed = False
            vertical_span = get_vertical_span(element)
            midpoint = get_midpoint(element, vertical_span)
            for cluster in clusters:
                cluster_midpoint = get_midpoint(cluster["elements"][0], cluster["span"])
                if abs(cluster_midpoint - midpoint) <= margin:
                    # Midpoints are within margin
                    cluster["elements"].append(element)
                    cluster["span"] = (
                        min(cluster["span"][0], vertical_span[0]),
                        max(cluster["span"][1], vertical_span[1]),
                    )
                    placed = True
                    break
            if not placed:
                clusters.append({"elements": [element], "span": vertical_span})

        # Sort elements in each cluster by the first horizontal position
        for cluster in clusters:
            sorted_cluster = sorted(
                cluster["elements"], key=get_first_horizontal_position
            )
            sorted_elements.extend(sorted_cluster)

    return sorted_elements


def check_blue_color(document_path, elements, margin=5, dpi=300):
    """
    Checks for blue color within the bounds of text elements in a PDF document, optionally expanding the check area by a margin.
    Creates a high-resolution image for each element showing the checked area with red boxes, saved as separate images.

    Args:
    document_path (str): Path to the PDF document.
    elements (list of dict): A list of dictionaries containing page, bounds data, and unique_element_id.
    margin (int, optional): Number of points to expand the bounds by on all sides. Default is 5.
    dpi (int, optional): Dots per inch for the output image resolution. Default is 300.

    Returns:
    list of dict: The elements list with added "attributes" key indicating the presence of blue color.
    """
    doc = fitz.open(document_path)  # Open the PDF file
    zoom = dpi / 72  # Calculate zoom based on the desired DPI
    mat = fitz.Matrix(zoom, zoom)  # Create a matrix for this zoom

    for element in elements:
        page = doc.load_page(element["Page"])  # Load the page

        # Define function to expand the bounds by the margin
        def expand_rect(rect, margin):
            return fitz.Rect(
                rect.x0 - margin,  # left
                rect.y0 - margin,  # top
                rect.x1 + margin,  # right
                rect.y1 + margin,  # bottom
            )

        if re.search(r"\d", element.get("Text", "")) and not re.search(
            r"[a-zA-Z]", element.get("Text", "")
        ):
            bounds_list = element.get("CharBounds", [element["Bounds"]])
            found_blue = False

            for bounds in bounds_list:
                rect = fitz.Rect(*bounds)  # Create a rect for the bounds
                expanded_rect = expand_rect(rect, margin)  # Expand the bounds by margin

                # Draw a red rectangle directly on the page
                page.draw_rect(expanded_rect, color=(1, 0, 0), width=1.5)

                clip_pix = page.get_pixmap(clip=expanded_rect, matrix=mat)
                img = clip_pix.samples

                # Check if any blue is present
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

            # Uncomment this block to visually track pdf scan for better debugging
            # # Annotate with unique element ID
            # text_spot = fitz.Point(rect.x0, rect.y0 - 10)
            # fontsize = 4 * zoom  # Scale fontsize based on DPI
            # page.insert_text(
            #     text_spot,
            #     element["unique_element_id"],
            #     color=(1, 0, 0),
            #     fontsize=fontsize,
            # )

            # # Generate a pixmap of the entire page to include the drawings
            # pix = page.get_pixmap(matrix=mat)
            # # Save the annotated page image for review
            # pix.save(
            #     f"{document_path}_annotated_element_{element['unique_element_id']}.png"
            # )  # Save the image

    doc.close()  # Always remember to close the document
    return elements


def main(original_pdf_path, modified_pdf_path, json_path, updated_json_path):
    """
    Extracts color information and hyperlinks from the PDF and updates the JSON data.
    """
    hyperlinks = extract_hyperlinks(original_pdf_path)

    with open(json_path, "r") as file:
        json_data = json.load(file)

    elements = json_data["elements"]

    # Flatten elements
    elements = flatten_elements(elements)

    # Remove elements with no text
    elements = del_empty_elements(elements)

    # Add page heights to elements
    elements = add_page_heights_to_elements(modified_pdf_path, elements)

    # Assign unique IDs to elements
    elements = assign_unique_ids(elements)

    # Convert coordinates to PyMuPDF format
    elements = convert_bounds_to_pymupdf(elements)

    # Sort elements
    elements = sort_elements(elements)

    # Remove headers and footers
    elements = remove_header_footer(elements)

    # Check for blue color in elements
    elements = check_blue_color(elements)

    # Add hyperlinks to extended_metadata
    if "extended_metadata" not in json_data:
        json_data["extended_metadata"] = {}
    json_data["extended_metadata"]["hyperlinks"] = hyperlinks

    # Merge / seperate elements
    elements = merge_and_split_elements(elements)

    with open(updated_json_path, "w") as file:
        json.dump(json_data, file, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    main()
