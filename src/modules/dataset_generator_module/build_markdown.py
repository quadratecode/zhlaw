# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

import os
import shutil
import json
from zipfile import ZipFile
from bs4 import BeautifulSoup, NavigableString, Tag
import urllib.parse
import markdownify
import yaml
import logging
from tqdm import tqdm  # Imported tqdm
import re  # Imported regex for post-processing

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def wrap_text(tag, prefix, suffix):
    """
    Wrap the text content of a tag with prefix and suffix.
    Skips wrapping if the text is only whitespace.
    """
    if tag.string and not tag.string.isspace():
        # Wrap only if the string is not just whitespace
        tag.string.replace_with(f"{prefix}{tag.string}{suffix}")
    else:
        for content in tag.contents:
            if isinstance(content, NavigableString):
                if not content.isspace():
                    content.replace_with(f"{prefix}{content}{suffix}")
            elif isinstance(content, Tag):
                wrap_text(content, prefix, suffix)


def convert_links_to_absolute(soup, base_url, current_file):
    for tag in soup.find_all(["a", "link", "script", "img"]):
        attr = "href" if tag.name in ["a", "link"] else "src"
        if tag.has_attr(attr):
            url = tag[attr]
            parsed_url = urllib.parse.urlparse(url)
            if not parsed_url.netloc and not url.startswith("#"):  # Relative URL
                # Extract ordnungsnummer and nachtragsnummer from the filename
                parts = url.split("-")
                if len(parts) >= 2:
                    ordnungsnummer = parts[0]
                    nachtragsnummer = parts[1].split(".")[0]
                    absolute_url = f"{base_url}{ordnungsnummer}-{nachtragsnummer}.html"
                    tag[attr] = absolute_url
                else:
                    tag[attr] = urllib.parse.urljoin(base_url, url)
            elif url.startswith("#"):  # Handle fragment identifiers
                # Extract ordnungsnummer and nachtragsnummer from current_file
                parts = current_file.split("-")
                if len(parts) >= 2:
                    ordnungsnummer = parts[0]
                    nachtragsnummer = parts[1].split(".")[0]
                    absolute_url = (
                        f"{base_url}{ordnungsnummer}-{nachtragsnummer}.html{url}"
                    )
                    tag[attr] = absolute_url
                else:
                    absolute_url = urllib.parse.urljoin(base_url + current_file, url)
                    tag[attr] = absolute_url


def process_footnotes(soup):
    """
    Process footnote markers and definitions.
    - Merge footnote markers that are in separate <p> tags into the previous <p>.
    - Collect footnote definitions from <p class="footnote"> and convert them to Markdown links.

    Returns:
        footnote_texts (list): List of footnote definitions in Markdown format.
    """
    footnote_definitions = {}

    # Step 1: Merge footnote markers into previous paragraphs
    # Find all <p> tags that contain only <sup>n</sup>
    footnote_marker_ps = soup.find_all("p")
    for p in footnote_marker_ps:
        # Check if the paragraph contains only a <sup> tag
        if len(p.contents) == 1 and p.sup:
            n = p.sup.get_text().strip()
            if n and n.isdigit():
                footnote_mark = f"[^{n}]"
                # Append as plain text
                footnote_marker = NavigableString(footnote_mark)
                # Append to previous <p>
                prev_p = p.find_previous_sibling("p")
                if prev_p:
                    prev_p.append(footnote_marker)
                else:
                    logger.warning(
                        f"No preceding <p> found for footnote marker [{n}]. Skipping."
                    )
                # Remove the footnote marker <p>
                p.decompose()
            else:
                logger.warning(
                    f"Invalid or missing footnote number in <sup>: '{n}'. Skipping this footnote marker."
                )

    # Step 2: Extract footnote definitions from <p class="footnote">
    footnote_p_tags = soup.find_all("p", class_="footnote")
    for footnote_p in footnote_p_tags:
        sup = footnote_p.find("sup")
        if sup:
            n = sup.get_text().strip()
            if n and n.isdigit():
                # Remove the <sup> tag from the footnote definition
                sup.decompose()
                # Get the footnote content with inner HTML to preserve links
                content_html = footnote_p.decode_contents().strip()
                # Convert HTML links to Markdown links
                content_md = convert_html_links_to_markdown(content_html)
                footnote_definitions[n] = content_md
                # Remove the footnote <p>
                footnote_p.decompose()
            else:
                logger.warning(
                    f"Invalid or missing footnote number in <sup>: '{n}'. Skipping this footnote definition."
                )
        else:
            logger.warning(
                "No <sup> tag found within <p class='footnote'>. Skipping this footnote definition."
            )

    # Step 3: Create footnote_texts in sorted order
    footnote_texts = []
    # Sort footnotes by numerical order, ensuring keys are valid integers
    sorted_keys = sorted(
        [k for k in footnote_definitions.keys() if k.isdigit()], key=lambda x: int(x)
    )

    for n in sorted_keys:
        content = footnote_definitions[n]
        footnote_texts.append(f"[^{n}]: {content}")

    # Debug log
    logger.debug(f"Footnote definitions: {footnote_definitions}")
    logger.debug(f"Footnote texts: {footnote_texts}")

    return footnote_texts


def convert_html_links_to_markdown(html_content):
    """
    Convert HTML links within the content to Markdown links.

    Args:
        html_content (str): HTML string containing links.

    Returns:
        markdown_content (str): Markdown string with converted links.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    for a_tag in soup.find_all("a"):
        text = a_tag.get_text()
        href = a_tag.get("href", "")
        # Create Markdown link
        markdown_link = f"[{text}]({href})"
        a_tag.replace_with(markdown_link)
    # Replace multiple spaces and newlines
    markdown_content = " ".join(soup.stripped_strings)
    return markdown_content


def convert_marginalia_to_h6(soup):
    """
    Convert elements with class 'marginalia' to h6 tags.
    """
    for element in soup.find_all(class_="marginalia"):
        new_h6_tag = soup.new_tag("h6")
        new_h6_tag.string = element.get_text()
        element.replace_with(new_h6_tag)


def add_line_breaks(soup):
    """
    Add line breaks after certain elements to improve readability.
    Skip adding <br> after elements that end with footnote markers.
    """
    for tag in soup.find_all(["h6", "p"]):
        # Check if the last child is a footnote marker
        last_child = tag.contents[-1] if tag.contents else None
        if isinstance(last_child, NavigableString):
            if not last_child.strip().startswith("[^"):
                tag.append(soup.new_tag("br"))
        elif (
            isinstance(last_child, Tag)
            and last_child.name == "a"
            and last_child.get_text().startswith("[^")
        ):
            # If the last child is an <a> tag with a footnote marker, skip adding <br>
            continue
        else:
            tag.append(soup.new_tag("br"))


def process_markdown(md, footnote_texts):
    """
    Process the markdown content by cleaning and appending footnotes.
    Inserts a blank line between each footnote definition.
    """
    lines = md.split("\n")
    processed_lines = []
    previous_line_blank = False

    for line in lines:
        # Strip leading and trailing whitespace
        line = line.strip()
        if not line:
            if not previous_line_blank:
                processed_lines.append("")
                previous_line_blank = True
            continue
        previous_line_blank = False

        # **Remove or comment out the section that strips links**
        # This preserves the markdown links intact
        # if line.startswith("[") and "](https://" in line:
        #     # Extract the text inside the brackets
        #     line = line.split("]", 1)[0][1:]

        processed_lines.append(line)

    # Append footnotes at the end with a blank line between each
    if footnote_texts:
        processed_lines.append("")
        for footnote in footnote_texts:
            processed_lines.append(footnote)
            processed_lines.append("")  # Insert a blank line after each footnote

        # Remove the last blank line to prevent extra blank line at the end
        if processed_lines and processed_lines[-1] == "":
            processed_lines.pop()

    # Join lines back into a single string
    cleaned_md = "\n".join(processed_lines)

    # **Post-processing to fix footnote markers if necessary**
    # Replace any [[n]](URL) with [^n]
    # This is a workaround in case markdownify misinterprets [^n] as a link
    # Regex explanation:
    # \[\[(\d+)\]\]\(.*?\) matches [[n]](URL)
    # and replaces it with [^n]
    cleaned_md = re.sub(r"\[\[(\d+)\]\]\(.*?\)", r"[^\1]", cleaned_md)

    return cleaned_md


def create_zip_file(source_dir, zip_file_path):
    """
    Create a ZIP archive of the specified source directory.
    """
    with ZipFile(zip_file_path, "w") as zipf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                zipf.write(
                    os.path.join(root, file),
                    os.path.relpath(
                        os.path.join(root, file), os.path.join(source_dir, "..")
                    ),
                )


def process_html_files(source_dir, dest_dir_md, base_url):
    """
    Process HTML files: convert to Markdown, handle links, and organize based on metadata.
    """
    # Ensure the destination directories exist
    os.makedirs(dest_dir_md, exist_ok=True)

    in_force_dir_md = os.path.join(dest_dir_md, "in_force")
    not_in_force_dir_md = os.path.join(dest_dir_md, "not_in_force")

    os.makedirs(in_force_dir_md, exist_ok=True)
    os.makedirs(not_in_force_dir_md, exist_ok=True)

    # Collect all relevant files first
    all_files = []
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            if file.endswith("-merged.html") or file.endswith("-original.html"):
                all_files.append(os.path.join(root, file))

    # Wrap the file list with tqdm for a progress bar
    for file_path in tqdm(all_files, desc="Processing HTML Files", unit="file"):
        html_file_path = file_path
        # Corresponding metadata file
        base_filename = os.path.basename(file_path).rsplit("-", 1)[0]  # e.g., 101-000
        metadata_filename = f"{base_filename}-metadata.json"
        metadata_file_path = os.path.join(os.path.dirname(file_path), metadata_filename)

        if os.path.exists(metadata_file_path):
            # Process the pair
            # Read the HTML file with proper encoding handling
            with open(html_file_path, "rb") as html_file:
                content = html_file.read()
                try:
                    content_decoded = content.decode("utf-8")
                except UnicodeDecodeError:
                    content_decoded = content.decode("iso-8859-1")

            soup = BeautifulSoup(content_decoded, "html.parser")

            # Read the metadata
            with open(metadata_file_path, "r", encoding="utf-8") as metadata_file:
                metadata = json.load(metadata_file)

            # Exclude the key "process_steps" from metadata
            metadata = {k: v for k, v in metadata.items() if k != "process_steps"}

            # Remove 'versions' key from 'doc_info' in metadata
            if "doc_info" in metadata and "versions" in metadata["doc_info"]:
                del metadata["doc_info"]["versions"]

            # Flatten 'doc_info' into the top-level metadata
            if "doc_info" in metadata:
                doc_info = metadata.pop("doc_info")
                # Ensure no key conflicts when updating
                for key, value in doc_info.items():
                    if key not in metadata:
                        metadata[key] = value
                    else:
                        # Handle key conflict if necessary
                        logger.warning(
                            f"Key '{key}' in 'doc_info' conflicts with top-level key. Skipping."
                        )

            # Convert relative links to absolute, including handling fragments
            convert_links_to_absolute(soup, base_url, file_path)

            # Process footnotes: merge markers and collect definitions
            footnote_texts = process_footnotes(soup)

            # Convert marginalia to h6 tags
            convert_marginalia_to_h6(soup)

            # Wrap provisions in "{}"
            for provision in soup.find_all(class_="provision"):
                wrap_text(provision, "{", "}")

            # Wrap subprovisions in "<>"
            for subprovision in soup.find_all(class_="subprovision"):
                wrap_text(subprovision, "<", ">")

            # Start enum paragraphs with "| "
            for enum_paragraph in soup.find_all(class_=["enum-lit", "enum-ziff"]):
                wrap_text(enum_paragraph, "| ", "")

            # Add line breaks after certain tags to improve readability
            add_line_breaks(soup)

            # Convert elements to markdown with error handling
            try:
                markdown_content = markdownify.markdownify(
                    str(soup), heading_style="ATX", newline_style="NL"
                )
                markdown_content = process_markdown(markdown_content, footnote_texts)
            except RecursionError:
                logger.error(f"RecursionError: Skipping file {file_path}")
                continue

            # Include the metadata as YAML front matter in the markdown
            yaml_front_matter = yaml.dump(metadata, allow_unicode=True)
            markdown_with_front_matter = (
                f"---\n{yaml_front_matter}---\n\n{markdown_content}"
            )

            # Determine whether the law is in force
            in_force = metadata.get("in_force", False)

            # Determine the target directory
            target_dir_md = in_force_dir_md if in_force else not_in_force_dir_md

            # Write the markdown content to the correct subdirectory
            new_file_name_md = f"{base_filename}.md"
            new_file_path_md = os.path.join(target_dir_md, new_file_name_md)
            with open(new_file_path_md, "w", encoding="utf-8") as new_file_md:
                new_file_md.write(markdown_with_front_matter)

        else:
            logger.warning(f"Metadata file not found for {html_file_path}")


def main(collection_path):
    base_url = "https://www.zhlaw.ch/col-zh/"
    destination_dir_archive_md = "public/collection-md"
    destination_dir_json = "public/collection-metadata.json"
    zhlex_data_processed = "data/zhlex/zhlex_data/zhlex_data_processed.json"

    zip_file_path_md = "public/col-zh-md.zip"

    process_html_files(collection_path, destination_dir_archive_md, base_url)
    create_zip_file(destination_dir_archive_md, zip_file_path_md)
    logger.info("Processing complete and zip file created.")

    shutil.copy(zhlex_data_processed, destination_dir_json)
    shutil.rmtree(destination_dir_archive_md)


if __name__ == "__main__":
    main("data/zhlex/zhlex_files")
