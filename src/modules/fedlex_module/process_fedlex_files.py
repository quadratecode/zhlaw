#!/usr/bin/env python3
"""
Script: process_fedlex_files.py

Processes raw Fedlex HTML files ("*-raw.html") found recursively under INPUT_DIR.
Performs extensive cleanup and restructuring:
  - Removes head content, comments, processing instructions.
  - Renames/restructures elements (e.g., #lawcontent -> #law > #source-text).
  - Unwraps unnecessary containers.
  - Cleans up footnote links and structure.
  - Transforms heading elements (h6.heading) into marginalia or provision paragraphs.
  - Assigns sequential IDs to provisions (p.provision) and subprovisions (p.subprovision)
    using the format "seq-{seq_num}-prov-{prov_id}" and
    "seq-{seq_num}-prov-{prov_id}-sub-{subprov_num}{prov_suffix}".
  - Converts definition lists (<dl>) into paragraphs (<p class="enum">).
  - Wraps annex content found after specific headings into <details id="annex">.
  - Performs final cleanup, keeping only essential classes (marginalia, provision,
    subprovision, enum, footnote, footnote-ref, pdf-source).
  - Saves the processed HTML next to the original with "-merged.html" suffix.
  - Attempts to hyperlink provisions/subprovisions if the corresponding module is available.

Usage:
    python process_fedlex_files.py [--folder {fedlex_files,test_files}] [--mode {concurrent,sequential}]

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

# Standard library imports
import os
import re
import glob
import json  # For potential metadata handling
import argparse
import concurrent.futures
from tqdm import tqdm

# Third-party imports
try:
    from bs4 import BeautifulSoup, Comment, formatter, NavigableString, Tag
except ImportError:
    print("Error: BeautifulSoup4 library not found.")
    print("Please install it: pip install beautifulsoup4 lxml")
    exit(1)

# --- Provision/Subprovision Numbering Regex ---
NUMBER_LETTER_PATTERN = re.compile(r"[^\d]*(\d+)([a-zA-Z]*)[.\s]?")
SUBPROVISION_PATTERN = re.compile(r"^\s*(\d+|[a-zA-Z])([a-zA-Z]*)\s*[.)]?\s")

# --- Global tracker for provision sequences ---
provision_sequences = {}

# --- Annex Keywords ---
ANNEX_KEYWORDS = ["anhang", "anhänge", "verzeichnis"]  # Case-insensitive check


# --- Hyperlink function placeholder ---
def hyperlink_provisions_and_subprovisions(soup):
    """Placeholder function for hyperlinking."""
    # print("Skipping hyperlinking (function not available or import failed).")
    return soup


def remove_empty_tags(soup_obj):
    """
    Iterates through the BeautifulSoup object and removes tags that are empty
    (i.e., no non-whitespace text content) and have no attributes,
    unless they are essential structural tags or <hr>.
    Returns the number of tags removed in one pass.
    """
    to_remove = []
    for tag in soup_obj.find_all(True):  # Find all tags
        if tag.name in ["html", "body", "head", "hr"]:
            continue
        has_content = bool(tag.get_text(strip=True))
        has_attrs = bool(tag.attrs)
        has_element_children = bool(
            tag.find(lambda t: isinstance(t, Tag) and t.name != "br", recursive=False)
        )  # Ignore <br> for emptiness check

        if not has_content and not has_attrs and not has_element_children:
            is_truly_empty = True
            for child in tag.contents:
                if isinstance(child, Tag):
                    is_truly_empty = False
                    break
                if isinstance(child, NavigableString) and child.strip():
                    is_truly_empty = False
                    break
            if is_truly_empty:
                to_remove.append(tag)

    count = 0
    for tag in to_remove:
        if tag.parent:
            tag.decompose()
            count += 1
    return count


def transform_headings(soup):
    """
    Transforms <h6 class="heading"> elements based on their content structure.
    Extracts numbering and heading text, replacing the original h6 with
    a <p class="provision"> for numbering and inserting a new h6 (later marginalia) for text.
    """
    h6_tags = soup.find_all("h6", class_="heading")

    for h6 in h6_tags:
        top_children = list(h6.children)
        a_tags = [
            child
            for child in top_children
            if isinstance(child, Tag) and child.name == "a"
        ]

        if not a_tags:
            continue  # Skip if no anchor found within h6.heading

        heading_text = ""
        numbering_fragments = []

        if len(a_tags) > 1:
            heading_anchor = a_tags[-1]
            heading_text = heading_anchor.get_text(strip=True)
            for child in top_children:
                if child == heading_anchor:
                    break
                if isinstance(child, Tag):
                    if child.name in ("a", "b", "i"):
                        numbering_fragments.append(child.get_text(strip=False))
                    elif child.name == "sup":
                        numbering_fragments.append(str(child))
                    else:
                        numbering_fragments.append(child.get_text(strip=False))
                elif isinstance(child, NavigableString):
                    numbering_fragments.append(str(child))
        else:  # Single <a> tag case
            anchor = a_tags[0]
            for child in anchor.children:
                if isinstance(child, Tag):
                    if child.name in (
                        "b",
                        "i",
                        "sup",
                    ):  # b, i, sup inside anchor -> numbering
                        numbering_fragments.append(
                            str(child)
                            if child.name == "sup"
                            else child.get_text(strip=False)
                        )
                    else:  # Other tags inside anchor -> heading
                        heading_text += child.get_text(strip=False)
                elif isinstance(
                    child, NavigableString
                ):  # Text inside anchor -> heading
                    heading_text += str(child)
            heading_text = heading_text.strip()

            # Fallback: Check text *after* the anchor if heading is still empty
            if not heading_text:
                after_anchor_text = ""
                start_collecting = False
                for node in top_children:
                    if node == anchor:
                        start_collecting = True
                        continue
                    if start_collecting:
                        after_anchor_text += (
                            str(node)
                            if isinstance(node, NavigableString)
                            else node.get_text(strip=False)
                        )
                heading_text = after_anchor_text.strip()

            # Fallback: If still no heading text, use anchor content as numbering
            if not numbering_fragments and not heading_text:
                numbering_fragments.append(anchor.get_text(strip=False))

        numbering_html = "".join(numbering_fragments).strip()

        # Create new elements only if content exists
        new_h6 = None
        if heading_text:
            new_h6 = soup.new_tag("h6", attrs={"class": ["heading"], "role": "heading"})
            new_h6.string = heading_text

        new_p = None
        if numbering_html:
            new_p = soup.new_tag("p", attrs={"class": ["provision"]})
            # Parse and append numbering HTML content safely
            numbering_soup = BeautifulSoup(
                f"<body>{numbering_html}</body>", "html.parser"
            )
            if numbering_soup.body:
                for elem in list(numbering_soup.body.contents):
                    new_p.append(elem.extract())

        # Replace original h6
        if new_h6:
            h6.insert_before(new_h6)
        if new_p:
            h6.replace_with(new_p)
        elif h6.parent:
            h6.decompose()  # Remove original if not replaced


def wrap_annex_content(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Finds the first heading (h1-h6) indicating an annex (by keyword in text
    or '#annex' in a link fragment/href) and wraps subsequent content
    up to the footnote line into <details id="annex"><summary>Anhänge</summary>...</details>.
    """
    start_heading: Tag = None
    keywords_lower = [k.lower() for k in ANNEX_KEYWORDS]

    # Iterate through all heading levels
    for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        # 1. Check heading text content for keywords
        heading_text_lower = heading.get_text().lower()
        if any(keyword in heading_text_lower for keyword in keywords_lower):
            start_heading = heading
            break  # Found based on text

        # 2. Check links within the heading for #annex fragment
        found_in_link = False
        for a_tag in heading.find_all("a", href=True):
            href = a_tag.get("href", "")
            fragment = a_tag.get("fragment", "")  # Check fragment attribute too
            if "#annex" in href or "#annex" in fragment:
                start_heading = heading
                found_in_link = True
                break  # Found based on link
        if found_in_link:
            break  # Exit outer loop as well

    # If no annex heading was found, return the soup as is
    if not start_heading:
        return soup

    print("  -> Found annex starting point, wrapping content...")

    # Create the <details> and <summary> elements
    details_tag = soup.new_tag("details", id="annex")
    summary_tag = soup.new_tag("summary")
    summary_tag.string = "Anhänge"  # Fixed summary text
    details_tag.append(summary_tag)

    # Insert the <details> tag right before the identified starting heading
    start_heading.insert_before(details_tag)

    # Move the start_heading and all subsequent siblings into the <details> tag,
    # stopping before the footnote line (<hr id="footnote-line">).
    current_element = start_heading  # Start with the heading itself
    while current_element:
        next_element = current_element.next_sibling  # Get next before moving current

        # Check if the current element is the footnote separator
        is_footnote_line = (
            isinstance(current_element, Tag)
            and current_element.name == "hr"
            and current_element.get("id") == "footnote-line"
        )

        if is_footnote_line:
            break  # Stop moving elements

        # Extract the current element and append it to the <details> tag
        details_tag.append(current_element.extract())

        # Move to the next element
        current_element = next_element

    return soup


def process_html(html_content):
    """
    Processes the HTML string: cleans, restructures, assigns IDs, wraps annex, formats.
    Returns the transformed, pretty-printed HTML string.
    """
    global provision_sequences
    provision_sequences = {}

    soup = BeautifulSoup(html_content, "lxml")

    # 1. Empty <head>
    if soup.head:
        soup.head.clear()

    # 2. Remove PIs and Comments
    for pi in soup.find_all(
        string=lambda text: isinstance(text, Comment) and text.startswith("?")
    ):
        pi.extract()
    for string in soup.find_all(string=True):
        if re.match(r"^\s*<\?.*?\?>\s*$", str(string), re.DOTALL):
            string.extract()
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    # 4. Rename #lawcontent -> #law
    law_content_div = soup.find("div", id="lawcontent")
    if law_content_div:
        law_content_div["id"] = "law"
        law_content_div.name = "div"

    # 5. Wrap #law content in #source-text.pdf-source
    law_div = soup.find("div", id="law")
    if law_div:
        wrapper = soup.new_tag(
            "div", attrs={"class": ["pdf-source"], "id": "source-text"}
        )
        for child in list(law_div.children):
            wrapper.append(child.extract())
        law_div.append(wrapper)

    # 6. Unwrap containers
    selectors_to_unwrap = [
        "div#preface",
        "div#preamble",
        "main#maintext",
        "section",
        "div.collapseable",
        "article",
        "inl",
        "heading-info",
        "tmp\\:heading",
    ]
    for selector in selectors_to_unwrap:
        for tag in soup.select(selector):
            if tag and tag.parent:
                tag.unwrap()
    for tag in soup.find_all(attrs={"name": True}):
        if tag and tag.parent:
            tag.unwrap()

    # 7. Remove specific classes (e.g., absatz, srnummer)
    for tag in soup.find_all(class_="absatz"):
        tag["class"].remove("absatz")
        if not tag["class"]:
            del tag["class"]
    for tag in soup.find_all(class_="srnummer"):
        tag.decompose()

    # 8. Delete <br> tags
    for br in soup.find_all("br"):
        br.decompose()

    # 9. Delete icon spans
    for span in soup.find_all("span", class_=["display-icon", "external-link-icon"]):
        span.decompose()

    # 10. Modify footnote links (#fn-* -> #footnote-line)
    for a_tag in soup.find_all("a", href=lambda href: href and href.startswith("#fn-")):
        original_text = a_tag.get_text(strip=True)
        a_tag.string = f"[{original_text}]"
        a_tag["href"] = "#footnote-line"
        a_tag.attrs.pop("id", None)
        parent = a_tag.parent
        while parent and parent.name == "span":
            next_parent = parent.parent
            parent.unwrap()
            parent = next_parent
        sup_parent = a_tag.find_parent("sup")
        if sup_parent:
            sup_classes = sup_parent.get("class", [])
            if "footnote-ref" not in sup_classes:
                sup_classes.append("footnote-ref")
            sup_parent["class"] = sup_classes

    # 11. Process <p> starting with plain <sup> -> create p.subprovision
    for p_tag in soup.find_all("p"):
        if p_tag.find_parent("div", class_="footnotes"):
            continue
        first_element_child = next(
            (c for c in p_tag.contents if isinstance(c, Tag)), None
        )
        if (
            first_element_child
            and first_element_child.name == "sup"
            and not first_element_child.find("a")
        ):
            new_p_subprovision = soup.new_tag("p", attrs={"class": ["subprovision"]})
            sup_marker = first_element_child.extract()
            new_p_subprovision.append(sup_marker)
            p_tag.insert_before(new_p_subprovision)

    # 12. Transform h6.heading -> h6 + p.provision
    transform_headings(soup)

    # --- Assign Provision/Subprovision IDs ---
    last_prov_details = None
    all_paragraphs = soup.find_all("p")
    for p_tag in all_paragraphs:
        p_classes = p_tag.get("class", [])
        p_text_content = p_tag.get_text(" ", strip=True)
        is_provision = "provision" in p_classes
        is_subprovision = "subprovision" in p_classes

        if is_provision:
            number_letter_match = NUMBER_LETTER_PATTERN.search(p_text_content)
            if number_letter_match:
                number, letter = (
                    number_letter_match.group(1),
                    number_letter_match.group(2) or "",
                )
                prov_id_part = f"{number}{letter}"
                seq_num = provision_sequences.get(prov_id_part, 0)
                provision_sequences[prov_id_part] = seq_num + 1
                p_tag["id"] = f"seq-{seq_num}-prov-{prov_id_part}"
                last_prov_details = {
                    "seq_num": seq_num,
                    "num": number,
                    "suffix": letter,
                }
            else:
                last_prov_details = None  # Reset if pattern fails
        elif is_subprovision and last_prov_details:
            subprov_match = SUBPROVISION_PATTERN.match(p_text_content)
            if subprov_match:
                sub_marker = subprov_match.group(1)
                prov_suffix = last_prov_details["suffix"]
                p_tag["id"] = (
                    f"seq-{last_prov_details['seq_num']}"
                    f"-prov-{last_prov_details['num']}{prov_suffix}"
                    f"-sub-{sub_marker}{prov_suffix.lower()}"
                )
    # --- End ID Assignment ---

    # 12.7 Hyperlink provisions (optional)
    try:
        soup = hyperlink_provisions_and_subprovisions(soup)
    except Exception as e:
        print(f"  *** WARNING: Error during hyperlinking: {e}")

    # 13. Convert remaining h6.heading -> p.marginalia
    for h6_tag in soup.find_all("h6", class_="heading", attrs={"role": "heading"}):
        h6_tag.name = "p"
        h6_tag["class"] = ["marginalia"]
        h6_tag.attrs.pop("role", None)

    # 14. Remove empty tags (first pass)
    # --- MODIFIED: Changed to standard while loop ---
    while True:
        removed_count = remove_empty_tags(soup)
        if removed_count == 0:
            break
    # --- END MODIFICATION ---

    # 15. Move footnotes to end, add <hr id="footnote-line">
    footnotes_container = soup.new_tag("div")
    hr_separator_needed = False
    for fn_div in soup.find_all("div", class_="footnotes"):
        for p_tag in fn_div.find_all("p"):
            original_id = p_tag.attrs.pop("id", None)
            if original_id and original_id.startswith("fn-"):
                hr_separator_needed = True
            p_classes = p_tag.get("class", [])
            if "footnote" not in p_classes:
                p_classes.append("footnote")
            p_tag["class"] = p_classes
            footnotes_container.append(p_tag.extract())
        fn_div.decompose()
    if soup.body and hr_separator_needed:
        hr_tag = soup.new_tag("hr", id="footnote-line")
        soup.body.append(hr_tag)
        for footnote_p in list(footnotes_container.contents):
            soup.body.append(footnote_p.extract())

    # --- Reparse before final structural changes and cleanup ---
    temp_html_str = str(soup)
    temp_html_str = re.sub(
        r"<\?del-struct abstand\d+pt\??>", "", temp_html_str
    )  # Final PI check
    additional_soup = BeautifulSoup(temp_html_str, "lxml")

    # 16.5 Additional cleanup: Unwrap b, i; remove role=heading; unwrap internal links
    for tag_name in ["b", "i"]:
        for tag in additional_soup.find_all(tag_name):
            if tag and tag.parent:
                tag.unwrap()
    for tag in additional_soup.find_all(attrs={"role": "heading"}):
        del tag["role"]
    for a_tag in additional_soup.find_all("a", href=True):
        href = a_tag["href"]
        if (
            href.startswith("#")
            and href != "#footnote-line"
            and not href.startswith("#seq-")
        ):
            if a_tag.parent:
                a_tag.unwrap()

    # 16.6 Scale heading levels (aria-level -> h(N+1))
    for tag in additional_soup.find_all(attrs={"aria-level": True}):
        try:
            level_int = int(tag["aria-level"])
            new_level = min(level_int + 1, 6)
            tag.name = f"h{new_level}"
            del tag["aria-level"]
        except (ValueError, TypeError):
            continue

    # 16.7 Convert DL -> p.enum
    def get_level_class(level):
        mapping = {
            1: "first",
            2: "second",
            3: "third",
            4: "fourth",
            5: "fifth",
            6: "sixth",
        }
        return f"{mapping.get(level, str(level))}-level"

    def convert_dl_recursive(dl_element, level, soup_instance):
        processed_paragraphs = []
        items = [
            c
            for c in dl_element.contents
            if isinstance(c, Tag) and c.name in ["dt", "dd"]
        ]
        i = 0
        while i < len(items):
            if items[i].name != "dt":
                i += 1
                continue
            dt_tag = items[i]
            dd_tag = (
                items[i + 1]
                if i + 1 < len(items) and items[i + 1].name == "dd"
                else None
            )
            if dd_tag:
                nested_items = []
                for nested_dl in dd_tag.find_all("dl", recursive=False):
                    nested_items.extend(
                        convert_dl_recursive(nested_dl, level + 1, soup_instance)
                    )
                    nested_dl.decompose()
                dt_text = dt_tag.get_text(" ", strip=True)
                dd_text = dd_tag.get_text(" ", strip=True)
                combined = dt_text + (" " + dd_text if dd_text else "")
                new_p = soup_instance.new_tag(
                    "p", attrs={"class": ["enum", get_level_class(level)]}
                )
                new_p.string = combined.strip()
                processed_paragraphs.append(new_p)
                processed_paragraphs.extend(nested_items)
                i += 2
            else:  # dt without dd
                dt_text = dt_tag.get_text(" ", strip=True)
                if dt_text:
                    new_p = soup_instance.new_tag(
                        "p", attrs={"class": ["enum", get_level_class(level)]}
                    )
                    new_p.string = dt_text.strip()
                    processed_paragraphs.append(new_p)
                i += 1
        return processed_paragraphs

    for top_dl in additional_soup.find_all("dl"):
        if not top_dl.find_parent("dl"):
            converted_ps = convert_dl_recursive(top_dl, 1, additional_soup)
            for p_item in converted_ps:
                top_dl.insert_before(p_item)
            top_dl.decompose()

    # --- NEW: Wrap Annex Content ---
    additional_soup = wrap_annex_content(additional_soup)
    # --- END NEW ---

    # 16.8 Remove table border attribute
    for table in additional_soup.find_all("table", border=True):
        del table["border"]

    # 16.9 Final Class Cleanup
    allowed_classes = {
        "marginalia",
        "provision",
        "subprovision",
        "enum",
        "footnote",
        "footnote-ref",
        "pdf-source",
    }
    for i in range(1, 11):
        allowed_classes.add(get_level_class(i))  # Add enum level classes
    for tag in additional_soup.find_all(True):
        if tag.has_attr("class"):
            kept_classes = [
                cls for cls in tag.get("class", []) if cls in allowed_classes
            ]
            if kept_classes:
                tag["class"] = kept_classes
            else:
                del tag["class"]

    # 17. Final pass: Remove empty tags
    final_html_string = str(additional_soup)
    final_soup = BeautifulSoup(final_html_string, "lxml")
    # --- MODIFIED: Changed to standard while loop ---
    while True:
        removed_count = remove_empty_tags(final_soup)
        if removed_count == 0:
            break
    # --- END MODIFICATION ---

    # 18. Pretty print final HTML
    pretty_html = final_soup.prettify(formatter=formatter.HTMLFormatter(indent=4))
    pretty_html = "\n".join(line for line in pretty_html.splitlines() if line.strip())

    return pretty_html


def process_single_file(file_path):
    """
    Process a single raw HTML file and save the result as a merged HTML file.
    For use with concurrent and sequential processing.
    """
    print(f"Processing: {file_path}")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_content = f.read()
        processed_html_content = process_html(raw_content)
        output_filepath = file_path.replace("-raw.html", "-merged.html")
        with open(output_filepath, "w", encoding="utf-8") as out_f:
            out_f.write(processed_html_content)
        print(f"  -> Saved: {output_filepath}")
        return True
    except Exception as e:
        print(f"  *** ERROR processing {file_path}: {e}")
        return False


def process_files_concurrently(raw_files, max_workers=None):
    """
    Process files concurrently using ProcessPoolExecutor.
    """
    if not raw_files:
        print("No files to process.")
        return 0, 0

    print(f"Processing {len(raw_files)} files concurrently...")
    processed_count, error_count = 0, 0

    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {
            executor.submit(process_single_file, file): file for file in raw_files
        }

        for future in tqdm(
            concurrent.futures.as_completed(future_to_file),
            total=len(raw_files),
            desc="Processing",
        ):
            file = future_to_file[future]
            try:
                if future.result():
                    processed_count += 1
                else:
                    error_count += 1
            except Exception as e:
                print(f"Exception processing {file}: {e}")
                error_count += 1

    return processed_count, error_count


def process_files_sequentially(raw_files):
    """
    Process files sequentially one at a time.
    """
    if not raw_files:
        print("No files to process.")
        return 0, 0

    print(f"Processing {len(raw_files)} files sequentially...")
    processed_count, error_count = 0, 0

    for file_path in tqdm(raw_files, desc="Processing"):
        try:
            if process_single_file(file_path):
                processed_count += 1
            else:
                error_count += 1
        except Exception as e:
            print(f"Exception processing {file_path}: {e}")
            error_count += 1

    return processed_count, error_count


def process_files(input_dir, mode="sequential", max_workers=None):
    """
    Find and process all "*-raw.html" files, saving as "*-merged.html".
    """
    pattern = os.path.join(input_dir, "**", "*-raw.html")
    raw_files = list(glob.iglob(pattern, recursive=True))

    if not raw_files:
        print(f"No '*-raw.html' files found in {input_dir} or its subdirectories.")
        return

    print(f"Found {len(raw_files)} raw HTML files to process...")

    if mode == "concurrent":
        processed_count, error_count = process_files_concurrently(
            raw_files, max_workers
        )
    else:  # sequential mode
        processed_count, error_count = process_files_sequentially(raw_files)

    print(
        "-" * 30
        + f"\nProcessing complete.\n  Processed: {processed_count}\n  Errors: {error_count}\n"
        + "-" * 30
    )


def main():
    """
    Main execution: parses arguments, checks directory, imports optional components, runs processing.
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Process Fedlex raw HTML files to merged HTML."
    )
    parser.add_argument(
        "--folder",
        type=str,
        default="fedlex_files",
        choices=["fedlex_files", "test_files"],
        help="Folder to process: 'fedlex_files' (default) or 'test_files'",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="sequential",
        choices=["concurrent", "sequential"],
        help="Processing mode: 'concurrent' (parallel) or 'sequential' (default, for debugging)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of worker processes for concurrent mode (default: auto)",
    )
    args = parser.parse_args()

    # Set input directory based on folder argument
    if args.folder == "test_files":
        input_dir = os.path.join("data", "fedlex", "test_files_fedlex")
    else:  # fedlex_files (default)
        input_dir = os.path.join("data", "fedlex", "fedlex_files")

    print(f"Processing folder: {args.folder} ({input_dir})")
    print(
        f"Processing mode: {args.mode}"
        + (
            f" with {args.workers} workers"
            if args.mode == "concurrent" and args.workers
            else ""
        )
    )

    if not os.path.isdir(input_dir):
        print(f"Error: Input directory not found: {input_dir}")
        return

    # --- Optional Import: Hyperlinking Function ---
    try:
        from importlib import import_module

        module_path = "src.modules.law_pdf_module.create_hyperlinks"
        module = import_module(module_path)
        hyperlink_func = getattr(module, "hyperlink_provisions_and_subprovisions", None)
        if hyperlink_func:
            globals()["hyperlink_provisions_and_subprovisions"] = hyperlink_func
            print("Successfully imported hyperlinking function.")
        else:
            print(
                f"Warning: Function 'hyperlink_provisions_and_subprovisions' not found in {module_path}."
            )
    except ImportError:
        print(f"Warning: Could not import hyperlinking module: {module_path}")
    except Exception as import_e:
        print(f"Warning: Error during hyperlinking import: {import_e}")
    # --- End Optional Import ---

    process_files(input_dir, args.mode, args.workers)


# --- Script Execution ---
if __name__ == "__main__":
    main()
