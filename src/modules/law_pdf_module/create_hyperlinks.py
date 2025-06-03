# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

import json
import re
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup, NavigableString, Tag
import logging

# Get logger from main module
logger = logging.getLogger(__name__)

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
        # Check if paragraph has an ID of the form "seq-X-prov-Y"
        provision_match = re.match(
            r"^seq-(\d+)-prov-(\d+)([a-zA-Z]*|[a-zA-Z]+er)$", paragraph.get("id", "")
        )
        if provision_match:
            seq_num, num, suffix = provision_match.groups()
            last_provision_id = f"{seq_num}-prov-{num}{suffix}"

        # If text matches subprovision pattern, mark it as subprovision
        if SUBPROVISION_PATTERN.match(text):
            paragraph["class"] = ["subprovision"]
            if last_provision_id:
                subprov_match = SUBPROVISION_PATTERN.match(text)
                subprovision_number = subprov_match.group(1)
                suffix = subprov_match.group(2) if subprov_match.group(2) else ""
                # Format without dash between number and word suffix
                paragraph["id"] = (
                    f"seq-{seq_num}-prov-{num}{suffix}-sub-{subprovision_number}{suffix.lower()}"
                )

    return soup


def merge_footnotes(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Merge footnotes by combining adjacent paragraphs with the 'footnote' class.
    The <sup> text from the first encountered footnote starts a new merged paragraph.
    """
    footnote_paragraphs: List[Tag] = soup.find_all("p", class_="footnote")
    new_paragraphs: List[tuple] = []
    current_text_parts: List[str] = []
    sup_number: Optional[str] = None

    for p in footnote_paragraphs:
        if p.sup:
            if current_text_parts:
                new_paragraphs.append((sup_number, " ".join(current_text_parts)))
                current_text_parts = []
            sup_number = p.sup.extract().get_text()
        current_text_parts.append(p.get_text())

    if current_text_parts:
        new_paragraphs.append((sup_number, " ".join(current_text_parts)))

    # Remove existing footnote paragraphs from the document
    for p in footnote_paragraphs:
        p.decompose()

    # Create new merged footnote paragraphs and append them to the source-text div
    source_div: Optional[Tag] = soup.find("div", id="source-text")
    if not source_div:
        logger.warning(
            "No div with id 'source-text' found; merged footnotes will not be appended."
        )
    for sup_num, text in new_paragraphs:
        new_p: Tag = soup.new_tag("p", **{"class": "footnote"})
        sup_tag: Tag = soup.new_tag("sup")
        sup_tag.string = str(sup_num)
        new_p.append(sup_tag)
        new_p.append(text)
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
                new_text: str = re.sub(
                    regex,
                    f'<a href="{link_uri}">{link_text}</a>',
                    text_element,
                    flags=re.IGNORECASE,
                )
                new_soup: BeautifulSoup = BeautifulSoup(new_text, "html.parser")
                text_element.replace_with(new_soup)
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


def handle_footnotes_refs(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Process the body text to replace footnote reference numbers with <sup> tags containing hyperlinks.
    Excludes elements that already contain Ziff-number patterns.
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
            sup_tag = soup.new_tag("sup", **{"class": "footnote-ref"})
            a_tag = soup.new_tag("a", href="#footnote-line")
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
    soup = merge_footnotes(soup)
    soup = handle_footnotes_refs(soup)
    soup = hyperlink_provisions_and_subprovisions(soup)
    soup = merge_numbered_paragraphs(soup)
    soup = update_html_with_hyperlinks(hyperlinks, soup)

    with open(merged_html_law, "w", encoding="utf-8") as file:
        file.write(str(soup))


if __name__ == "__main__":
    # TODO: Allow command-line arguments
    pass
