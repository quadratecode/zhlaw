#!/usr/bin/env python3
"""
Script: process_fedlex_files.py

This script processes all HTML files that were previously scraped and stored under
"data/fedlex/fedlex_files". It looks for files whose names end with "-raw.html" and outputs
a modified version right next to them (in the same folder) with the suffix "-merged.html".

Processing steps include:
  - Parsing the HTML.
  - Removing content from the <head> tag.
  - Removing processing instructions and HTML comments.
  - Renaming and restructuring specific elements (for example, converting <div id="lawcontent">
    to <div id="law"> and wrapping its inner content in a new <div class="pdf-source" id="source-text">).
  - Unwrapping, deleting, or modifying various elements as described in the inline comments.
  - A series of cleanups including footnote cleanup, heading-level scaling, converting nested definition lists,
    and more.
  - Finally, the script pretty prints the final HTML (using 4 spaces per indent level).

Additionally:
  - A function returning classes to remove is provided (fill in the list as needed).
  - If the processed HTML contains an element with class "erlasstitel", the metadata JSON file (in the same folder,
    with "-metadata.json" replacing "-raw.html") is updated accordingly.

Usage:
    python process_fedlex_files.py
"""

import os
import re
import glob
from bs4 import BeautifulSoup, Comment, formatter, NavigableString, Tag
from src.modules.law_pdf_module.create_hyperlinks import (
    hyperlink_provisions_and_subprovisions,
)

# Define the base input directory (the raw files are stored here in subfolders)
INPUT_DIR = os.path.join("data", "fedlex", "fedlex_files")


def get_classes_to_remove():
    """
    Return a list of class names (or patterns) that should be removed from the document.
    This configuration removes any elements with classes starting with "absatz".
    """
    # Use a compiled regular expression to match classes that start with "absatz"
    return [re.compile(r"^absatz")]


def remove_elements_with_classes(soup, classes):
    """
    Remove all elements that have any class matching any pattern in the given list.
    The element with class "erlasstitel" is not removed so that its content
    can be used to update the metadata.
    """
    for pattern in classes:
        for tag in soup.find_all(class_=pattern):
            # Preserve elements that have the class "erlasstitel" among others
            if tag.has_attr("class") and any(
                cls == "erlasstitel" for cls in tag["class"]
            ):
                continue
            tag.decompose()


def remove_empty_tags(soup_obj):
    """
    Iterates through the BeautifulSoup object and removes tags that are empty (i.e. no non-whitespace text)
    and have no attributes.
    Returns the number of tags removed.
    """
    to_remove = []
    for tag in soup_obj.find_all():
        if tag.name in ["html", "body"]:
            continue
        if not tag.get_text(strip=True) and not tag.attrs:
            to_remove.append(tag)
    for tag in to_remove:
        tag.decompose()
    return len(to_remove)


def transform_headings(soup):
    """
    Transforms <h6 class="heading"> elements by:
      - extracting 'numbering' (from <b>/<i>/<sup> or from the first anchor(s))
      - extracting heading text (either from the last anchor if multiple <a> exist,
        or from non-<b>/<i>/<sup> text if only one <a> exists)
      - converting the original <h6> into a <p class="provision" ...> for the numbering
      - inserting a new <h6 ...> above it for the heading text
      - preserving <sup> tags (with their inner <a> if any)
      - unwrapping <a>, <b>, and <i> into plain text
    """

    # Find all <h6 class="heading"> elements
    h6_tags = soup.find_all("h6", class_="heading")

    for h6 in h6_tags:
        # Grab all *direct* children so we can see if there are multiple <a> at the top level
        top_children = list(h6.children)
        # Filter just <a> tags in the top level
        a_tags = [child for child in top_children if child.name == "a"]

        if not a_tags:
            # No anchors found; skip or handle differently if needed
            continue

        # --- 1) Compute the provision ID from the first anchor (#art_... => provision-...)
        first_a = a_tags[0]
        href = first_a.get("href", "")
        match = re.match(r"#art_(.*)", href)
        provision_id = None
        if match:
            # e.g. #art_29_a -> "29_a" -> "29-a" -> "provision-29-a"
            raw_id_part = match.group(1).replace("_", "-")
            provision_id = f"provision-{raw_id_part}"

        # We'll define placeholders for heading text and numbering text (HTML)
        heading_text = ""
        numbering_fragments = []  # we will build HTML strings, preserving <sup>

        # --- 2) Different logic if multiple <a> or single <a>
        if len(a_tags) > 1:
            # Case: More than one <a> tag
            #  - The last <a> is heading text
            #  - Everything else (anchors + any intervening sup or text) is numbering
            heading_anchor = a_tags[-1]  # last anchor
            heading_text = heading_anchor.get_text(strip=True)

            # Gather everything from the start up until that last anchor into numbering
            for child in top_children:
                if child == heading_anchor:
                    # stop before last anchor (that anchor is heading text)
                    break

                if child.name in ("a", "b", "i"):
                    # unwrap to plain text
                    numbering_fragments.append(child.get_text(strip=False))
                elif child.name == "sup":
                    # keep <sup> as is
                    numbering_fragments.append(str(child))
                elif isinstance(child, NavigableString):
                    # direct text
                    numbering_fragments.append(child)
                else:
                    # fallback for any other tags
                    numbering_fragments.append(child.get_text(strip=False))

        else:
            # Case: Exactly one <a> tag
            anchor = a_tags[0]

            # We want to separate out the text inside that anchor into:
            #   - text in <b>, <i>, <sup> => numbering
            #   - everything else => heading text
            for child in anchor.children:
                if child.name in ("b", "i", "a"):
                    # unwrap these into numbering
                    numbering_fragments.append(child.get_text(strip=False))
                elif child.name == "sup":
                    # keep <sup> as is in numbering
                    numbering_fragments.append(str(child))
                elif isinstance(child, NavigableString):
                    # plain text -> heading
                    heading_text += child
                else:
                    # fallback if there's any other tag we haven't handled
                    heading_text += child.get_text(strip=False)

            # Be tidy
            heading_text = heading_text.strip()

        # Build the final numbering string (HTML)
        numbering_html = "".join(numbering_fragments).strip()

        # --- 3) Create the new <h6> for the heading text
        new_h6 = soup.new_tag("h6", attrs={"class": "heading", "role": "heading"})
        new_h6.string = heading_text

        # --- 4) Create the new <p class="provision"> for the numbering
        new_p = soup.new_tag("p", attrs={"class": "provision"})
        if provision_id:
            new_p["id"] = provision_id

        # Because numbering_html may contain <sup> tags (which we want to keep),
        # we parse it as HTML and then move its children into new_p
        numbering_soup = BeautifulSoup(numbering_html, "html.parser")
        for elem in numbering_soup.contents:
            new_p.append(elem)

        # --- 5) Insert the new heading above, replace the old h6 with the new p
        h6.insert_before(new_h6)
        h6.replace_with(new_p)


def process_html(html):
    """
    Processes the HTML string and returns the transformed, pretty-printed HTML.
    """
    # Use the fast lxml parser
    soup = BeautifulSoup(html, "lxml")

    # 1. Empty the <head> tag.
    if soup.head:
        soup.head.clear()

    # 2. Remove processing instructions like <?del-struct abstand18pt> (with or without trailing "?")
    for string in soup.find_all(string=True):
        text = string.strip()
        if re.match(r"<\?del-struct abstand\d+pt\??>", text):
            string.extract()

    # 3. Remove all HTML comments.
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    # 4. Rename <div id="lawcontent"> to <div id="law">
    law_div = soup.find("div", id="lawcontent")
    if law_div:
        law_div["id"] = "law"

    # 5. Wrap inner content of <div id="law"> in a new <div class="pdf-source" id="source-text">
    law_div = soup.find("div", id="law")
    if law_div:
        wrapper = soup.new_tag("div", **{"class": "pdf-source", "id": "source-text"})
        wrapper.extend(law_div.contents)
        law_div.clear()
        law_div.append(wrapper)

    # 6. Unwrap selected elements.
    selectors_to_unwrap = [
        "div#preface",
        "div#preamble",
        "main#maintext",
        "section",
        "div.collapseable",
        "article",
        "inl",
        "heading-info",
        "tmp\\:heading",  # Escaped colon for tag "tmp:heading"
    ]
    for selector in selectors_to_unwrap:
        for tag in soup.select(selector):
            tag.unwrap()
    # Also unwrap any element with a "name" attribute.
    for tag in soup.find_all(attrs={"name": True}):
        tag.unwrap()

    # 7. Remove class "absatz" from any element.
    for tag in soup.find_all(attrs={"class": True}):
        classes = tag.get("class")
        if "absatz" in classes:
            new_classes = [cls for cls in classes if cls != "absatz"]
            if new_classes:
                tag["class"] = new_classes
            else:
                del tag["class"]

    # 7.5 Remove elements with class "srnummer"
    for tag in soup.find_all(class_="srnummer"):
        tag.decompose()

    # 8. Delete any <br> tags.
    for br in soup.find_all("br"):
        br.decompose()

    # 9. Delete <span class="display-icon"> and <span class="external-link-icon"> elements.
    for span in soup.find_all("span", class_="display-icon"):
        span.decompose()
    for span in soup.find_all("span", class_="external-link-icon"):
        span.decompose()

    # 10. Modify hyperlinks: any <a> with href starting with "#fn-" gets href="#footnote-line" and no id.
    for a in soup.find_all("a", href=True):
        if a["href"].startswith("#fn-"):
            # 1. Modify the href
            a["href"] = "#footnote-line"
            # 2. Remove any 'id' attribute if present
            a.attrs.pop("id", None)
            # 3. Wrap the content of the <a> in square brackets
            original_text = a.get_text(strip=True)
            a.string = f"[{original_text}]"

            # 4. Unwrap parent <span> elements
            #   We'll look *up* the tree and unwrap any <span>
            #   If you only want to remove the *immediate* parent span, you can do that instead.
            for parent in a.parents:
                if parent.name == "span":
                    parent.unwrap()
                # We stop once we reach the <body> or None
                # (or any container beyond which we don't expect the chain to continue)
                if parent.name in ("body", "[document]"):
                    break

            # 5. Give the parent <sup> a class "footnote-ref"
            sup_parent = a.find_parent("sup")
            if sup_parent:
                sup_parent["class"] = sup_parent.get("class", []) + ["footnote-ref"]

    # 11. Process <p> tags that start with a <sup> tag (without an <a> inside)
    #     but only if the <p> is NOT inside a <div class="footnotes">.
    for p in soup.find_all("p"):
        if p.find_parent("div", class_="footnotes"):
            continue
        if p.contents and getattr(p.contents[0], "name", None) == "sup":
            sup_tag = p.contents[0]
            if not sup_tag.find("a"):
                new_p = soup.new_tag("p", **{"class": "subprovision"})
                sup_tag.extract()
                new_p.append(sup_tag)
                p.insert_before(new_p)

    # 12. Transform headings
    transform_headings(soup)

    # Assign subprovision id
    last_provision_id = None
    # Iterate over all paragraphs in document order
    for p in soup.find_all("p"):
        # 1) If this paragraph's ID looks like a main provision (e.g. provision-64-a)
        #    and not a subprovision ID, record it as the current "last_provision_id".
        pid = p.get("id", "")
        if pid.startswith("provision-") and "-subprovision-" not in pid:
            # Example: pid = "provision-64-a" -> last_provision_id = "64-a"
            last_provision_id = pid.replace("provision-", "", 1)

        # 2) If the paragraph is a 'subprovision'...
        if "subprovision" in p.get("class", []):
            # Look for a <sup> tag containing only digits
            sup_tag = p.find("sup")
            if sup_tag:
                sup_text = sup_tag.get_text(strip=True)
                if re.match(r"^\d+$", sup_text) and last_provision_id:
                    # Construct a new ID: provision-<last_provision_id>-subprovision-<sup_number>
                    p["id"] = f"provision-{last_provision_id}-subprovision-{sup_text}"

    # 12.7 Hyperlink provisions and suprovisions
    soup = hyperlink_provisions_and_subprovisions(soup)

    # 13. Convert all remaining <h6 class="heading" role="heading"> to <p class="marginalia">.
    for h6 in soup.find_all("h6", class_="heading", attrs={"role": "heading"}):
        h6.name = "p"
        h6["class"] = "marginalia"

    # 7.6 Remove elements with classes specified by get_classes_to_remove()
    remove_elements_with_classes(soup, get_classes_to_remove())

    # 14. Remove all empty tags (except <html> and <body>).
    while remove_empty_tags(soup) > 0:
        pass

    # 15. Move all <div class="footnotes"> to the end of <body>.
    footnotes_list = []
    for fn in soup.find_all("div", class_="footnotes"):
        fn.extract()
        footnotes_list.append(fn)
    if soup.body:
        hr_tag = soup.new_tag("hr", id="footnote-line")
        soup.body.append(hr_tag)
        for fn in footnotes_list:
            soup.body.append(fn)

    # 15.5. Process footnotes:
    # Unwrap any remaining <div class="footnotes"> and for each footnote <p> with an id starting with "fn-",
    # remove its id and add the class "footnote".
    for div in soup.find_all("div", class_="footnotes"):
        div.unwrap()
    for p in soup.find_all("p"):
        if p.has_attr("id") and p["id"].startswith("fn-"):
            del p["id"]
            existing = p.get("class", [])
            if "footnote" not in existing:
                existing.append("footnote")
            p["class"] = existing

    # 16. Final cleanup: remove any leftover processing instructions.
    final_html = str(soup)
    final_html = re.sub(r"<\?del-struct abstand\d+pt\??>", "", final_html)

    # 16.5 Additional cleanup:
    #      - Unwrap all <b> and <i> tags.
    #      - Remove any role="heading" attribute.
    #      - Unwrap all <a> tags linking to an id (href starting with "#"),
    #        except those with href="#footnote-line" or links to ids starting with "provision".
    additional_soup = BeautifulSoup(final_html, "lxml")
    for tag in additional_soup.find_all("b"):
        tag.unwrap()
    for tag in additional_soup.find_all("i"):
        tag.unwrap()
    for tag in additional_soup.find_all(attrs={"role": True}):
        if tag.get("role") == "heading":
            del tag["role"]
    for a in additional_soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("#") and href != "#footnote-line" and not href.startswith("#provision"):
            a.unwrap()

    # 16.6 Scale down heading levels based on aria-level.
    for tag in additional_soup.find_all(attrs={"aria-level": True}):
        try:
            level_int = int(tag["aria-level"])
        except ValueError:
            continue
        new_level = level_int + 1
        if new_level > 6:
            new_level = 6
        tag.name = "h" + str(new_level)
        del tag["aria-level"]
        if tag.has_attr("class"):
            new_classes = [cls for cls in tag["class"] if cls != "heading"]
            if new_classes:
                tag["class"] = new_classes
            else:
                del tag["class"]

    # 16.7 Convert <dl> elements to <p> elements with enumeration.
    #      Each <dt>/<dd> pair is replaced by a <p class="enum [level-class]"> element,
    #      where the level-class is "first-level", "second-level", etc. according to nesting.
    def level_to_string(level):
        mapping = {
            1: "first-level",
            2: "second-level",
            3: "third-level",
            4: "fourth-level",
            5: "fifth-level",
            6: "sixth-level",
        }
        return mapping.get(level, f"{level}th-level")

    def convert_dl(dl, level):
        new_elements = []
        # Get only the dt and dd tag children (skip whitespace and other nodes)
        items = [
            child
            for child in dl.contents
            if getattr(child, "name", None) in ["dt", "dd"]
        ]
        i = 0
        while i < len(items):
            # Expect a dt followed by a dd.
            if items[i].name != "dt":
                i += 1
                continue
            dt_tag = items[i]
            dd_tag = (
                items[i + 1]
                if i + 1 < len(items) and items[i + 1].name == "dd"
                else None
            )
            if dd_tag is None:
                i += 1
                continue
            dt_text = dt_tag.get_text(" ", strip=True)
            # Process any nested <dl> elements inside the dd tag recursively.
            nested_elements = []
            for nested_dl in dd_tag.find_all("dl"):
                nested_elements.extend(convert_dl(nested_dl, level + 1))
                nested_dl.decompose()
            dd_text = dd_tag.get_text(" ", strip=True)
            combined_text = dt_text + (" " + dd_text if dd_text else "")
            new_p = additional_soup.new_tag("p")
            new_p["class"] = ["enum", level_to_string(level)]
            new_p.string = combined_text
            new_elements.append(new_p)
            # Append any nested items immediately after.
            new_elements.extend(nested_elements)
            i += 2
        return new_elements

    # Process top-level <dl> elements (those not nested inside another <dl>)
    for dl in additional_soup.find_all("dl"):
        if not dl.find_parent("dl"):
            new_ps = convert_dl(dl, 1)
            for new_p in new_ps:
                dl.insert_before(new_p)
            dl.decompose()

    # 16.8 Remove border attribute from <table> elements.
    for table in additional_soup.find_all("table"):
        if table.has_attr("border"):
            del table["border"]

    # 16.9 Remove any class that starts with "man-"
    for tag in additional_soup.find_all(attrs={"class": True}):
        new_classes = [
            cls for cls in tag.get("class", []) if not cls.startswith("man-")
        ]
        if new_classes:
            tag["class"] = new_classes
        else:
            del tag["class"]

    # Update the final HTML after the <dl> conversion and additional cleanup.
    final_html = str(additional_soup)

    # 17. Final pass: Remove any empty elements that may have been re-introduced.
    final_soup = BeautifulSoup(final_html, "lxml")
    while remove_empty_tags(final_soup) > 0:
        pass
    final_html = str(final_soup)

    # 18. Pretty print the HTML using 4 spaces for indentation.
    custom_formatter = formatter.HTMLFormatter(indent=4)
    pretty_html = BeautifulSoup(final_html, "lxml").prettify(formatter=custom_formatter)
    # Remove any empty lines.
    pretty_html = "\n".join(line for line in pretty_html.splitlines() if line.strip())
    return pretty_html


def process_files():
    """
    Loops over all raw HTML files under the INPUT_DIR (recursively),
    processes each file, and saves the modified HTML right next to the raw file,
    replacing the "-raw.html" suffix with "-merged.html".
    Also updates the metadata file with any found erlasstitel.
    """
    # Use recursive glob to find all files ending with "-raw.html"
    pattern = os.path.join(INPUT_DIR, "**", "*-raw.html")
    for filepath in glob.iglob(pattern, recursive=True):
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Process/transform the HTML.
        processed_html = process_html(content)

        # Build the output filename by replacing "-raw.html" with "-merged.html"
        output_filepath = filepath.replace("-raw.html", "-merged.html")

        with open(output_filepath, "w", encoding="utf-8") as out_f:
            out_f.write(processed_html)

        print(f"Processed file {filepath} -> {output_filepath}")


def main():
    process_files()


if __name__ == "__main__":
    main()
