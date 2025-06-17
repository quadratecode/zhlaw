"""Module for matching and positioning marginalia in legal HTML documents.

This module processes HTML documents to properly position marginalia (side notes) relative
to their associated provisions. It calculates vertical overlap between marginalia and main
text elements, adjusts positioning, and merges marginalia HTML with the main document.

Key features:
- Calculates vertical overlap between marginalia and provisions
- Adjusts marginalia positioning to align with appropriate provisions
- Sorts paragraphs by page and vertical position
- Merges separate marginalia HTML files with main document HTML
- Maintains proper document structure and flow

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

from bs4 import BeautifulSoup, NavigableString
import re
import logging

# Get logger from main module
logger = logging.getLogger(__name__)


def calculate_overlap(mod_pos, marg_pos):

    # Unpack positions
    mod_top, mod_bottom = mod_pos
    marg_top, marg_bottom = marg_pos

    # Calculate the maximum of the top values and the minimum of the bottom values
    top_max = max(mod_top, marg_top)
    bottom_min = min(mod_bottom, marg_bottom)

    # If the maximum top value is less than the minimum bottom value, there is overlap
    if top_max < bottom_min:
        # The overlap is the difference between the bottom_min and top_max
        return bottom_min - top_max
    else:
        # No overlap
        return 0


def is_target_paragraph(paragraph):
    # Check if the next sibling paragraph is a "provision"
    return (
        paragraph and paragraph.get("class") and "provision" in paragraph.get("class")
    )


def adjust_marginalia_position(soup):
    # Adjust the position of each marginalia in the HTML.
    marginalia_tags = soup.find_all("p", class_="marginalia")

    # Continue if a marginalia tag is found
    if marginalia_tags:
        for marginalia in marginalia_tags:
            next_sibling = marginalia.find_next_sibling()
            previous_sibling = marginalia.find_previous_sibling()
            iteration_count = 0

            while (
                next_sibling
                and not is_target_paragraph(next_sibling)
                and iteration_count < 50
            ):
                if previous_sibling:
                    previous_sibling.insert_before(marginalia)
                next_sibling = marginalia.find_next_sibling()
                previous_sibling = marginalia.find_previous_sibling()
                iteration_count += 1

    return soup


def sort_paragraphs(soup):
    # Sort the paragraphs by page and vertical position
    paragraphs = soup.find_all("p", {"data-page-count": True})
    paragraphs.sort(
        key=lambda p: (
            int(p["data-page-count"]),
            float(p["data-vertical-position-top"]),
        )
    )

    # Reorder the paragraphs in the HTML
    for p in paragraphs:
        p.extract()
        soup.body.append(p)

    return soup


def merge_html(modified_path, marginalia_path):
    # Read and parse the HTML files
    with open(modified_path, "r", encoding="utf-8") as file:
        soup_modified = BeautifulSoup(file, "html.parser")
    with open(marginalia_path, "r", encoding="utf-8") as file:
        soup_marginalia = BeautifulSoup(file, "html.parser")

    # Iterate through each paragraph in the marginalia which contain data attributes
    marg_paragraphs = soup_marginalia.find_all(
        "p",
        {
            "data-page-count": True,
            "data-vertical-position-top": True,
            "data-vertical-position-bottom": True,
        },
    )
    for marg_p in marg_paragraphs:
        marg_page = marg_p["data-page-count"]
        marg_pos = (
            float(marg_p["data-vertical-position-top"]),
            float(marg_p["data-vertical-position-bottom"]),
        )

        # Find the corresponding paragraph in the modified HTML
        best_overlap = 0
        best_mod_p = None
        for mod_p in soup_modified.find_all("p", {"data-page-count": marg_page}):
            mod_pos = (
                float(mod_p["data-vertical-position-top"]),
                float(mod_p["data-vertical-position-bottom"]),
            )
            overlap = calculate_overlap(mod_pos, marg_pos)
            if overlap > best_overlap:
                best_overlap = overlap
                best_mod_p = mod_p

        # Insert the marginalia as a paragraph with the class "marginalia"
        if best_mod_p:
            marginalia_tag = soup_modified.new_tag("p", attrs={"class": "marginalia"})
            marginalia_tag.string = marg_p.get_text(strip=True)
            best_mod_p.insert_before(marginalia_tag)

    # Adjust the positions of the marginalia elements (this function needs to be defined based on how you want to adjust positions)
    adjust_marginalia_position(soup_modified)

    return str(soup_modified)


def clean_html(soup: BeautifulSoup) -> None:
    """
    Not sure about the original motivation behind this function -> Check for removal
    Currently requires a lot of exclusions and fine tuning just to wrap numbers in <sup> tags (reason unknown)
    """
    for element in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6"]):
        # Process text nodes individually rather than using element.string
        for content in list(element.contents):
            if isinstance(content, NavigableString):
                # Strip whitespace from direct text nodes only
                content.replace_with(content.strip())

        # Check if the element contains only a single number and doesn't have sup or sub tags
        if (
            element.get_text(strip=True).isdigit()
            and not element.find("sup")
            and not element.find("sub")
            # and does not have <numerator> or <denominator> tags
            and not element.find("numerator")
            and not element.find("denominator")
        ):
            # Save the text of the element
            element_text = element.get_text(strip=True)
            # Clear element without losing structure
            element.clear()
            # Create and append new sup tag
            sup_tag = soup.new_tag("sup")
            sup_tag.string = element_text
            element.append(sup_tag)
        else:
            # Process each text node within element
            for content in element.contents:
                if isinstance(content, NavigableString):
                    # Remove dashes between lowercase letters
                    cleaned_text = re.sub(r"(?<=[a-z])-(?=[a-z])", "", content)
                    content.replace_with(cleaned_text)

    return soup


def main(html_file_law, html_file_marginalia, merged_html_law):

    merged_html = merge_html(html_file_law, html_file_marginalia)
    soup = BeautifulSoup(merged_html, "html.parser")
    soup = clean_html(soup)

    with open(merged_html_law, "w", encoding="utf-8") as file:
        file.write(str(soup))
    logging.info(f"Saved merged HTML to {merged_html_law}")


if __name__ == "__main__":
    main()
