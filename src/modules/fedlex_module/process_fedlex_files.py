#!/usr/bin/env python3
"""
Script: process_fedlex_files.py

This script processes all HTML files from "data/fedlex/fedlex_files_raw" and outputs them into
"data/fedlex/fedlex_files_processed" as follows:

- For each file:
  - Parses the HTML and extracts the srnummer from an element with class "srnummer".
  - Extracts the date from the filename (using Arrow to parse a YYYYMMDD string).
  - Transforms the HTML:
      * Empties the <head> tag.
      * Removes any processing instructions like <?del-struct abstand18pt> (with or without a trailing "?").
      * Deletes all HTML comments.
      * Renames <div id="lawcontent"> to <div id="law"> and wraps its inner content in a new 
        <div class="pdf-source" id="source-text">.
      * Unwraps the following tags: <div id="preface">, <div id="preamble">, <main id="maintext">, all 
        <section>, all <div class="collapseable">, all <article>, all <inl>, all <heading-info> and all 
        <tmp:heading> (escaped as "tmp\\:heading"), as well as any element that has a "name" attribute.
      * Removes the class "absatz" from any element.
      * Deletes any <br> tags.
      * Deletes <span class="display-icon"> and <span class="external-link-icon"> elements.
      * Modifies hyperlinks whose href begins with "#fn-" (sets href="#footnote-line" and removes the id).
      * For any <p> that starts with a <sup> tag (without an <a> inside) and not inside a <div class="footnotes">,
        moves that <sup> into a new paragraph (with class "subprovision") inserted before the original paragraph.
      * For any <h6 class="heading" role="heading"> that contains an <a> with a <b> element, extracts the text 
        from the <b>, unwraps the <a>, and then inserts a new paragraph with class "provision" (containing the 
        extracted text) immediately after. Then converts the <h6> into a <p> with class "marginalia".
      * Deletes all empty tags (except <html> and <body>).
      * Moves all <div class="footnotes"> to the end of <body> (after inserting a new <hr id="footnote-line">).
      * **Footnote cleanup:**
            - Unwraps any remaining <div class="footnotes">.
            - For each footnote <p> (i.e. those with an id beginning with "fn-"), removes its id and adds the class "footnote".
      * Performs a final cleanup of any leftover processing instructions.
      * **Additional cleanup (executed at the end):**
            - Unwraps all <b> and <i> tags.
            - Removes any role="heading" attributes.
            - Unwraps all <a> tags linking to an id (href starting with "#"), except those with href="#footnote-line".
            - Scales down heading levels according to aria-level (so that aria-level="1" becomes an h2, etc.).
      * **New step:** Converts nested definition lists (<dl>) into paragraphs (<p>) with enumeration.
            - Each <dt>/<dd> pair is replaced by a <p> element with class "enum" plus a second class indicating its level
              (e.g. "first-level" for top-level, "second-level" for nested lists, etc.).
            - The original <dt> and <dd> are unwrapped and any nested <dl> inside a <dd> is processed recursively.
      * **New step:** Remove the border attribute from <table> elements and remove any class starting with "man-".
      * Finally, deletes any empty elements that may remain.
      * Pretty prints the final HTML using 4 spaces per indent level (via bs4.formatter.HTMLFormatter)
        and removes any empty lines.
  - Creates an output folder structure based on the srnummer and date:
      data/fedlex/fedlex_files_processed/<srnummer>/<date>/
  - Writes the transformed HTML to a file named <srnummer>-<date>-merged.html in that folder.

Usage:
    python process_fedlex_files.py
"""

import os
import re
import glob
import arrow
from bs4 import BeautifulSoup, Comment, formatter

# Define input and output directories
INPUT_DIR = os.path.join("data", "fedlex", "fedlex_files_raw")
OUTPUT_DIR = os.path.join("data", "fedlex", "fedlex_files_processed")


def extract_srnummer(html_content):
    """
    Extracts the srnummer from the HTML content.
    Looks for the first element with class "srnummer" and returns its text.
    """
    soup = BeautifulSoup(html_content, "lxml")
    sr_elem = soup.find(class_="srnummer")
    if sr_elem:
        return sr_elem.get_text(strip=True)
    return None


def extract_date_from_filename(filename):
    """
    Extracts an 8-digit date from the filename and uses Arrow to parse it.
    Returns the date string in YYYYMMDD format.
    """
    match = re.search(r"(\d{8})", filename)
    if match:
        date_str = match.group(1)
        try:
            date_obj = arrow.get(date_str, "YYYYMMDD")
            return date_obj.format("YYYYMMDD")
        except arrow.parser.ParserError:
            return None
    return None


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
            a["href"] = "#footnote-line"
            a.attrs.pop("id", None)

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

    # 12. Process <h6 class="heading" role="heading"> tags that contain an <a> with a <b> element.
    for h6 in soup.find_all("h6", class_="heading", attrs={"role": "heading"}):
        a_tag = h6.find("a")
        if a_tag:
            b_tag = a_tag.find("b")
            if b_tag:
                provision_text = b_tag.get_text(strip=True)
                b_tag.extract()
                a_tag.unwrap()
                new_prov = soup.new_tag("p", **{"class": "provision"})
                new_prov.string = provision_text
                h6.insert_after(new_prov)

    # 13. Convert all remaining <h6 class="heading" role="heading"> to <p class="marginalia">.
    for h6 in soup.find_all("h6", class_="heading", attrs={"role": "heading"}):
        h6.name = "p"
        h6["class"] = "marginalia"

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
    #      - Unwrap all <a> tags linking to an id (href starting with "#"), except those with href="#footnote-line".
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
        if href.startswith("#") and href != "#footnote-line":
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
    # Ensure the output base directory exists.
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Process each HTML file in the input directory.
    for filepath in glob.iglob(os.path.join(INPUT_DIR, "*.html")):
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract srnummer.
        srnummer = extract_srnummer(content)
        if not srnummer:
            print(f"Warning: No srnummer found in file {filepath}. Skipping.")
            continue

        # Extract the date from the filename.
        basename = os.path.basename(filepath)
        name_without_ext, _ = os.path.splitext(basename)
        date = extract_date_from_filename(name_without_ext)
        if not date:
            print(f"Warning: No valid date found in filename {basename}. Skipping.")
            continue

        # Process/transform the HTML.
        processed_html = process_html(content)

        # Build the output folder structure.
        output_subdir = os.path.join(OUTPUT_DIR, srnummer, date)
        os.makedirs(output_subdir, exist_ok=True)

        # Construct the new filename.
        output_filename = f"{srnummer}-{date}-merged.html"
        output_filepath = os.path.join(output_subdir, output_filename)

        with open(output_filepath, "w", encoding="utf-8") as out_f:
            out_f.write(processed_html)

        print(f"Processed file {filepath} -> {output_filepath}")


def main():
    process_files()


if __name__ == "__main__":
    main()
