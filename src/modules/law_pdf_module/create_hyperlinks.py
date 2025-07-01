"""Module for creating hyperlinks in legal HTML documents.

This module processes HTML documents to identify and create hyperlinks for legal references,
including provisions, subprovisions, footnotes, and cross-references. It handles various
patterns of legal citations and creates proper anchor links within the document structure.

Key features:
- Identifies provisions and subprovisions with proper ID assignment
- Processes footnotes and creates bidirectional links
- Handles cross-references to other legal texts
- Manages table of contents and structural elements
- Refines document structure for proper navigation

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import json
import re
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup, NavigableString, Tag

# Get logger from main module
from src.utils.logging_utils import get_module_logger
logger = get_module_logger(__name__)

# -----------------------------------------------------------------------------
# Module-Level Precompiled Regex Patterns and Constants
# -----------------------------------------------------------------------------
SUBPROVISION_PATTERN = re.compile(
    r"^(\d+)(bis|ter|quater|quinquies|sexies|septies|octies)?$", re.IGNORECASE
)
LETTER_ENUM_PATTERN = re.compile(r"^[a-zA-Z]\.$")
NUMBER_ENUM_PATTERN = re.compile(r"^\d{1,2}\.$")
DASH_ENUM_PATTERN = re.compile(r"–")
OS_PATTERN = re.compile(r"OS\s*\d+\s*,\s*\d+")
ANNEX_PATTERN = re.compile(r"Anhang|Anhänge", re.IGNORECASE)
FOOTNOTE_REF_NUM_PATTERN = re.compile(r"\d+")
ZIFF_PATTERN = re.compile(r"\d+\.")


# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------
def read_json_file(json_file_path: str) -> Any:
    with open(json_file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def add_class(tag: Tag, class_name: str) -> None:
    """Add a CSS class to a tag if not already present."""
    classes = tag.get("class", [])
    if class_name not in classes:
        tag["class"] = classes + [class_name]


def remove_class(tag: Tag, class_name: str) -> None:
    """Remove a CSS class from a tag if present."""
    classes = tag.get("class", [])
    if class_name in classes:
        classes.remove(class_name)
        if classes:
            tag["class"] = classes
        else:
            del tag["class"]


def contains_number_but_no_letter(text: str) -> bool:
    """Return True if text contains a digit and no alphabetical characters."""
    return bool(re.search(r"\d", text)) and not bool(re.search(r"[a-zA-Z]", text))


# -----------------------------------------------------------------------------
# Core Processing Functions
# -----------------------------------------------------------------------------
def refine_footnotes(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Refine footnotes by removing the 'footnote' class from paragraphs
    following the first occurrence of a <sup> with "1".
    Processes paragraphs from bottom to top.
    """
    footnote_paragraphs: List[Tag] = soup.find_all("p", class_="footnote")[::-1]
    remove_class_flag = False
    for p in footnote_paragraphs:
        if p.sup and p.sup.get_text().strip() == "1":
            remove_class_flag = True  # Start removal after encountering <sup>1</sup>
            continue
        if remove_class_flag:
            remove_class(p, "footnote")
    return soup


def find_subprovisions(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Process <p> elements to identify provisions and subprovisions.
    Subprovisions (paragraphs with only a numeric string or with suffixes)
    are marked with class 'subprovision' and assigned an ID referencing the last provision.
    """
    last_provision_id: Optional[str] = None

    # Filter paragraphs based on specific attribute conditions.
    for paragraph in soup.find_all(
        "p",
        attrs={
            "data-text-color": lambda x: x != "LinkBlue",
            "data-num-type": lambda x: x != "NoSubprovision",
            "data-font-size": lambda x: (
                x is not None and x.replace(".", "", 1).isdigit() and float(x) > 5
            ),
        },
    ):
        text: str = paragraph.get_text(strip=True)

        # When we find a paragraph that is a provision, we store its ID.
        # This check is simpler and more robust than trying to re-parse the ID.
        if "provision" in paragraph.get("class", []):
            current_id = paragraph.get("id")
            if current_id:  # Make sure it has an ID
                last_provision_id = current_id

        # If text matches subprovision pattern, mark it as subprovision
        if SUBPROVISION_PATTERN.match(text):
            paragraph["class"] = ["subprovision"]
            if last_provision_id:
                subprov_match = SUBPROVISION_PATTERN.match(text)
                if subprov_match:
                    subprovision_number = subprov_match.group(1)
                    subprov_suffix = (
                        subprov_match.group(2) if subprov_match.group(2) else ""
                    )

                    # Construct the new ID by simply appending to the last known provision ID.
                    paragraph["id"] = (
                        f"{last_provision_id}-sub-{subprovision_number}{subprov_suffix.lower()}"
                    )

    return soup


def count_footnote_numbers(soup: BeautifulSoup) -> Dict[str, int]:
    """Counts occurrences of each footnote number before they are merged."""
    counts = {}
    footnote_paragraphs: List[Tag] = soup.find_all("p", class_="footnote")
    for p in footnote_paragraphs:
        if p.sup:
            num = p.sup.get_text(strip=True)
            if num.isdigit():
                counts[num] = counts.get(num, 0) + 1
    return counts


def normalize_footnote_text(text: str) -> str:
    """
    Normalize spacing in footnote text by removing extra spaces around punctuation.
    """
    import re
    
    # Remove extra spaces inside parentheses (keep space before opening paren for readability)
    text = re.sub(r'\(\s+', '(', text)  # Remove space after opening paren
    text = re.sub(r'\s+\)', ')', text)  # Remove space before closing paren
    
    # Remove extra spaces before semicolons and ensure single space after
    text = re.sub(r'\s*;\s*', '; ', text)
    
    # Remove extra spaces before commas and ensure single space after
    text = re.sub(r'\s*,\s*', ', ', text)
    
    # Clean up multiple spaces but preserve single spaces
    text = re.sub(r'\s{2,}', ' ', text)
    
    # Handle periods: ensure single space after periods (except at end)
    text = re.sub(r'\.\s{2,}', '. ', text)
    text = re.sub(r'\.$', '.', text)  # Clean final period
    
    return text.strip()


def merge_footnotes(soup: BeautifulSoup, seq_counter: Dict[str, int]) -> BeautifulSoup:
    """
    Merge footnotes by combining adjacent paragraphs with the 'footnote' class.
    The <sup> text from the first encountered footnote starts a new merged paragraph.
    A unique, sequential ID is assigned, and the number is made into a clickable anchor.
    """
    footnote_paragraphs: List[Tag] = soup.find_all("p", class_="footnote")
    new_paragraphs: List[tuple] = []
    current_text_parts: List[str] = []
    sup_number: Optional[str] = None

    for p in footnote_paragraphs:
        if p.sup:
            if current_text_parts:
                # Join and normalize the text before creating paragraph
                merged_text = " ".join(current_text_parts)
                normalized_text = normalize_footnote_text(merged_text)
                new_paragraphs.append((sup_number, normalized_text))
            current_text_parts = []
            sup_number = p.sup.extract().get_text(strip=True)
        # Strip whitespace from individual text parts to prevent accumulation
        current_text_parts.append(p.get_text().strip())

    if current_text_parts:
        # Join and normalize the final text
        merged_text = " ".join(current_text_parts)
        normalized_text = normalize_footnote_text(merged_text)
        new_paragraphs.append((sup_number, normalized_text))

    for p in footnote_paragraphs:
        p.decompose()

    source_div: Optional[Tag] = soup.find("div", id="source-text")
    if not source_div:
        logger.warning(
            "No div with id 'source-text' found; merged footnotes will not be appended."
        )

    for sup_num, text in new_paragraphs:
        if not sup_num or not sup_num.isdigit():
            continue

        new_p: Tag = soup.new_tag("p", **{"class": "footnote"})

        # Assign a unique, sequential ID
        seq = seq_counter.get(sup_num, 0)
        id_str = f"seq-{seq}-ftn-{sup_num}"
        new_p["id"] = id_str
        seq_counter[sup_num] = seq + 1

        # Create the <sup> tag with a self-referencing anchor
        sup_tag: Tag = soup.new_tag("sup")
        a_tag = soup.new_tag("a", href=f"#{id_str}")
        # MODIFICATION: Wrap number in square brackets
        a_tag.string = f"[{sup_num}]"
        sup_tag.append(a_tag)
        new_p.append(sup_tag)

        # Wrap the text content in a span for styling
        content_span = soup.new_tag("span", attrs={"class": "footnote-content"})
        content_span.string = " " + text.strip()
        new_p.append(content_span)

        if source_div:
            source_div.append(new_p)

    return soup


def find_enumerations(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Identify enumeration paragraphs (single letters, numbers, or dashes) and assign
    appropriate classes such as 'enum-lit', 'enum-ziff', or 'enum-dash'.
    """
    paragraphs: List[Tag] = [
        p
        for p in soup.find_all("p")
        if not p.find_parent(["h1", "h2", "h3", "h4", "h5", "h6"])
        and "marginalia" not in p.get("class", [])
    ]

    for paragraph in paragraphs:
        # Extract direct text nodes, ignoring text within <sup> tags.
        text_parts: List[str] = [
            t for t in paragraph.find_all(text=True, recursive=False)
        ]
        text: str = "".join(text_parts).strip()
        existing_classes: List[str] = paragraph.get("class", [])

        if LETTER_ENUM_PATTERN.match(text):
            if "enum-lit" not in existing_classes:
                paragraph["class"] = existing_classes + ["enum-lit"]
        elif NUMBER_ENUM_PATTERN.match(text):
            if "enum-ziff" not in existing_classes:
                paragraph["class"] = existing_classes + ["enum-ziff"]
        elif DASH_ENUM_PATTERN.match(text):
            if "enum-dash" not in existing_classes:
                paragraph["class"] = existing_classes + ["enum-dash"]
    return soup


def update_html_with_hyperlinks(
    hyperlinks: List[Dict[str, str]], soup: BeautifulSoup
) -> BeautifulSoup:
    """
    Insert hyperlinks into the HTML by finding text nodes that match the hyperlink text.
    If the text is not already inside an <a> tag, it wraps it with one.
    """
    for link in hyperlinks:
        link_text: str = link.get("text", "")
        link_uri: str = link.get("uri", "")
        escaped_link_text: str = re.escape(link_text)
        regex = rf"\b{escaped_link_text}\b"

        text_elements = soup.find_all(text=re.compile(regex))
        for text_element in text_elements:
            if text_element.parent.name != "a":
                # Find all matches in the text
                text_str = str(text_element)
                matches = list(re.finditer(regex, text_str, flags=re.IGNORECASE))
                
                if matches:
                    # Get the parent to insert new elements
                    parent = text_element.parent
                    
                    # Build list of new elements (text segments and links)
                    new_elements = []
                    last_end = 0
                    
                    for match in matches:
                        # Add text before match
                        if match.start() > last_end:
                            new_elements.append(NavigableString(text_str[last_end:match.start()]))
                        
                        # Create link element
                        a_tag = soup.new_tag("a", href=link_uri)
                        a_tag.string = match.group()
                        new_elements.append(a_tag)
                        
                        last_end = match.end()
                    
                    # Add remaining text after last match
                    if last_end < len(text_str):
                        new_elements.append(NavigableString(text_str[last_end:]))
                    
                    # Replace the original text element with new elements
                    for i, elem in enumerate(new_elements):
                        if i == 0:
                            text_element.replace_with(elem)
                        else:
                            # Insert after the previous element
                            new_elements[i-1].insert_after(elem)
            else:
                text_element.parent["href"] = link_uri

    # Cleanup nested <a> tags if any exist
    for a_tag in soup.find_all("a"):
        inner_a_tags = a_tag.find_all("a")
        for inner_a in inner_a_tags:
            inner_a.unwrap()

    return soup


def merge_numbered_paragraphs(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Merge numbered paragraphs by appending the content of a paragraph enclosed in brackets
    to its previous sibling (which is a paragraph or heading).
    """
    paragraphs: List[Tag] = soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6"])
    for current_paragraph in paragraphs:
        previous_sibling = current_paragraph.find_previous_sibling(
            ["p", "h1", "h2", "h3", "h4", "h5", "h6"]
        )
        if (
            previous_sibling
            and current_paragraph.get_text(strip=True).startswith("[")
            and current_paragraph.get_text(strip=True).endswith("]")
        ):
            preserved_content = current_paragraph.encode_contents()
            previous_sibling.append(BeautifulSoup(preserved_content, "html.parser"))
            current_paragraph.decompose()
    return soup


def hyperlink_provisions_and_subprovisions(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Wrap provisions and subprovisions (paragraphs with class 'provision' or 'subprovision' and an ID)
    in an <a> tag linking to their own ID, ensuring that nested <a> tags and <sup> tags are handled appropriately.
    """
    for paragraph in soup.find_all(
        "p",
        class_=lambda c: c and any(cls in c for cls in ["provision", "subprovision"]),
        id=True,
    ):
        new_contents: List[Any] = []
        link_content: List[Any] = []

        for content in paragraph.contents:
            if getattr(content, "name", None) == "a":
                if link_content:
                    new_link = soup.new_tag("a", href=f"#{paragraph['id']}")
                    new_link.extend(link_content)
                    new_contents.append(new_link)
                    link_content = []
                new_contents.append(content)
            elif getattr(content, "name", None) == "sup" and content.find("a"):
                if link_content:
                    new_link = soup.new_tag("a", href=f"#{paragraph['id']}")
                    new_link.extend(link_content)
                    new_contents.append(new_link)
                    link_content = []
                new_contents.append(content)
            else:
                link_content.append(content)

        if link_content:
            new_link = soup.new_tag("a", href=f"#{paragraph['id']}")
            new_link.extend(link_content)
            new_contents.append(new_link)

        paragraph.clear()
        for content in new_contents:
            paragraph.append(content)
    return soup


def find_footnotes(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Identify and mark paragraphs as footnotes based on text patterns and font size.
    Uses the presence of OS and annex headings to determine the region for footnotes.
    """
    all_headings: List[Tag] = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    annex_match: Optional[Tag] = next(
        (h for h in all_headings if ANNEX_PATTERN.search(h.get_text())), None
    )
    last_heading: Optional[Tag] = all_headings[-1] if all_headings else None
    last_heading_before_annex: Optional[Tag] = None
    if annex_match:
        for h in all_headings:
            if h == annex_match:
                break
            last_heading_before_annex = h

    os_match: Optional[Tag] = None
    all_paragraphs: List[Tag] = soup.find_all("p")
    for p in all_paragraphs:
        try:
            font_size = float(p.get("data-font-size", 0))
        except ValueError:
            font_size = 0
        if font_size < 9 and OS_PATTERN.search(p.get_text()):
            os_match = p
            break

    region: str = "after_last_heading"
    if os_match and annex_match:
        if os_match in annex_match.find_all_previous():
            region = "between_last_heading_before_annex_and_annex_match"
        else:
            region = "after_last_heading"

    for p in all_paragraphs:
        if region == "after_last_heading":
            if last_heading is not None and last_heading not in p.find_all_previous():
                continue
        elif region == "between_last_heading_before_annex_and_annex_match":
            if (
                last_heading_before_annex is not None
                and last_heading_before_annex not in p.find_all_previous()
            ):
                continue
            if annex_match is not None and annex_match not in p.find_all_next():
                continue

        try:
            font_size = float(p.get("data-font-size", 0))
        except ValueError:
            font_size = 0

        has_sup: bool = bool(
            p.find("sup") and contains_number_but_no_letter(p.get_text())
        )
        if ((font_size < 9 and not has_sup) or (font_size < 5 and has_sup)) and not any(
            cls in p.get("class", [])
            for cls in ["provision", "subprovision", "marginalia"]
        ):
            p["class"] = ["footnote"]

    return soup


def handle_footnotes_refs(
    soup: BeautifulSoup, footnote_counts: Dict[str, int]
) -> BeautifulSoup:
    """
    Process the body text to replace footnote reference numbers with <sup> tags
    containing hyperlinks. If a footnote number is not unique, it links to the
    general #footnote-line anchor.
    """
    footnote_refs = soup.find_all(
        lambda tag: tag.name in ["h1", "h2", "h3", "h4", "h5", "h6", "p"]
        and tag.get("data-text-color") == "LinkBlue"
        and ("provision" not in tag.get("class", []))
        and not ZIFF_PATTERN.search(tag.get_text(strip=True))
    )

    for ref in footnote_refs:
        text: str = ref.get_text(strip=True)
        footnote_nums = FOOTNOTE_REF_NUM_PATTERN.findall(text)
        ref.clear()
        for num in footnote_nums:
            count = footnote_counts.get(num, 0)

            # If the number appears more than once or not at all, link to the general line.
            if count != 1:
                href = "#footnote-line"
            # If it's unique, link to its specific ID.
            else:
                # The sequence number for a unique footnote will always be 0.
                href = f"#seq-0-ftn-{num}"

            sup_tag = soup.new_tag("sup", **{"class": "footnote-ref"})
            a_tag = soup.new_tag("a", href=href)
            a_tag.append(f"[{num}]")
            sup_tag.append(a_tag)
            ref.append(sup_tag)
    return soup


# -----------------------------------------------------------------------------
# Main Function
# -----------------------------------------------------------------------------
def main(merged_html_law: str, updated_json_file_law: str) -> None:
    """
    Process the merged HTML by:
      - Reading hyperlink data from JSON.
      - Finding subprovisions, enumerations, footnotes and refining them.
      - Merging footnotes and numbered paragraphs.
      - Hyperlinking provisions and subprovisions.
      - Inserting hyperlinks into the HTML.
    Finally, saves the updated HTML back to the same file.
    """
    json_data = read_json_file(updated_json_file_law)
    hyperlinks: List[Dict[str, str]] = json_data.get("extended_metadata", {}).get(
        "hyperlinks", []
    )

    with open(merged_html_law, "r", encoding="utf-8") as file:
        soup = BeautifulSoup(file, "html.parser")

    soup = find_subprovisions(soup)
    soup = find_enumerations(soup)
    soup = find_footnotes(soup)
    soup = refine_footnotes(soup)

    # New logic: Count footnotes first, then merge and link
    footnote_counts = count_footnote_numbers(soup)
    seq_counter = {}  # Initialize a fresh sequence counter for this run
    soup = merge_footnotes(soup, seq_counter)
    soup = handle_footnotes_refs(soup, footnote_counts)

    soup = hyperlink_provisions_and_subprovisions(soup)
    soup = merge_numbered_paragraphs(soup)
    soup = update_html_with_hyperlinks(hyperlinks, soup)

    from src.utils.html_utils import write_html
    write_html(soup, merged_html_law, encoding="utf-8", add_doctype=False, minify=True)


if __name__ == "__main__":
    # TODO: Allow command-line arguments
    pass
