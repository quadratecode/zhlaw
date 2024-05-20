import os
import shutil
from zipfile import ZipFile
from bs4 import BeautifulSoup, NavigableString
import urllib.parse
import tqdm
import markdownify

import logging

# Get logger from main module
logger = logging.getLogger(__name__)


def wrap_text(tag, prefix, suffix):
    for content in tag.contents:
        if isinstance(content, NavigableString):
            content.replace_with(NavigableString(prefix + content + suffix))
        else:
            wrap_text(content, prefix, suffix)


def convert_links_to_absolute(soup, base_url, current_file):
    for tag in soup.find_all(["a", "link", "script", "img"]):
        attr = "href" if tag.name in ["a", "link"] else "src"
        if tag.has_attr(attr):
            url = tag[attr]
            parsed_url = urllib.parse.urlparse(url)
            if not parsed_url.netloc and not url.startswith(
                "#"
            ):  # Check if the URL is relative and not a fragment
                absolute_url = urllib.parse.urljoin(base_url, url)
                tag[attr] = absolute_url
            elif url.startswith("#"):  # Handle fragment identifiers
                absolute_url = urllib.parse.urljoin(base_url + current_file, url)
                tag[attr] = absolute_url


def process_html_files(source_dir, dest_dir_html, dest_dir_md, base_url):
    # Ensure the destination directories exist
    os.makedirs(dest_dir_html, exist_ok=True)
    os.makedirs(dest_dir_md, exist_ok=True)

    in_force_dir_html = os.path.join(dest_dir_html, "in_force")
    not_in_force_dir_html = os.path.join(dest_dir_html, "not_in_force")
    in_force_dir_md = os.path.join(dest_dir_md, "in_force")
    not_in_force_dir_md = os.path.join(dest_dir_md, "not_in_force")

    os.makedirs(in_force_dir_html, exist_ok=True)
    os.makedirs(not_in_force_dir_html, exist_ok=True)
    os.makedirs(in_force_dir_md, exist_ok=True)
    os.makedirs(not_in_force_dir_md, exist_ok=True)

    for filename in tqdm.tqdm(os.listdir(source_dir)):
        if filename.endswith(".html"):
            file_path = os.path.join(source_dir, filename)
            with open(file_path, "r", encoding="utf-8") as file:
                soup = BeautifulSoup(file, "html.parser")

                # Remove unwanted elements
                soup.find("div", {"id": "page-header"}).decompose()
                soup.find("div", {"id": "page-footer"}).decompose()
                soup.find("div", {"class": "nav-buttons"}).decompose()

                # Convert relative links to absolute, including handling fragments
                convert_links_to_absolute(soup, base_url, filename)

                # Find the div with id 'law'
                law_div = soup.find("div", id="law")
                if law_div:
                    td = law_div.find(
                        "td", attrs={"data-pagefind-filter": "Text in Kraft"}
                    )
                    if td and td.get_text().strip() == "Ja":
                        target_dir_html = in_force_dir_html
                        target_dir_md = in_force_dir_md
                    else:
                        target_dir_html = not_in_force_dir_html
                        target_dir_md = not_in_force_dir_md

                    # Write the processed HTML to the correct subdirectory
                    new_file_path_html = os.path.join(target_dir_html, filename)
                    with open(new_file_path_html, "w", encoding="utf-8") as new_file:
                        new_file.write(str(soup))

                    # Extract content from div with id 'source-text' and process it for markdown
                    source_text_div = soup.find("div", id="source-text")
                    if source_text_div:
                        # Remove unwanted elements
                        for element in source_text_div.find_all(
                            class_=["footnote-number", "footnote"]
                        ):
                            element.decompose()

                        # Modify the HTML to apply markdown-specific formatting
                        for provision in source_text_div.find_all(class_="provision"):
                            wrap_text(provision, "{", "}")
                        for subprovision in source_text_div.find_all(
                            class_="subprovision"
                        ):
                            wrap_text(subprovision, "[", "]")
                        for enum_paragraph in source_text_div.find_all(
                            class_=["enum-lit", "enum-ziff"]
                        ):
                            wrap_text(enum_paragraph, "| ", "")

                        # Convert elements to markdown
                        markdown_content = markdownify.markdownify(
                            str(source_text_div), heading_style="ATX"
                        )
                        markdown_content = process_markdown(markdown_content)

                        # Write the markdown content to the correct subdirectory
                        new_file_path_md = os.path.join(
                            target_dir_md, filename.replace(".html", ".md")
                        )
                        with open(
                            new_file_path_md, "w", encoding="utf-8"
                        ) as new_file_md:
                            new_file_md.write(markdown_content)


def process_markdown(md):
    lines = md.split("\n")
    processed_lines = []

    for line in lines:
        # Clean up any other tags that may have been missed
        line = BeautifulSoup(line, "html.parser").get_text()
        processed_lines.append(line)

    # Join lines back into a single string
    cleaned_md = "\n".join(processed_lines)
    cleaned_md = cleaned_md.replace("\n\n", "\n").strip()  # Remove extra newlines
    return cleaned_md


def create_zip_file(source_dir, zip_file_path):
    with ZipFile(zip_file_path, "w") as zipf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                zipf.write(
                    os.path.join(root, file),
                    os.path.relpath(
                        os.path.join(root, file), os.path.join(source_dir, "..")
                    ),
                )


def main(collection_path, zhlex_data_processed):
    base_url = "https://www.zhlaw.ch/col-zh/"
    destination_dir_archive_html = "public/data"
    destination_dir_archive_md = "public/collection-md"
    destination_dir_json = "public/collection-metadata.json"
    zhlex_data_processed = "data/zhlex/zhlex_data/zhlex_data_processed.json"

    zip_file_path_html = "public/col-zh-html.zip"
    zip_file_path_md = "public/col-zh-md.zip"

    process_html_files(
        collection_path,
        destination_dir_archive_html,
        destination_dir_archive_md,
        base_url,
    )
    create_zip_file(destination_dir_archive_html, zip_file_path_html)
    create_zip_file(destination_dir_archive_md, zip_file_path_md)
    logger.info("Processing complete and zip files created.")

    shutil.copy(zhlex_data_processed, destination_dir_json)
    shutil.rmtree(destination_dir_archive_html)
    shutil.rmtree(destination_dir_archive_md)


if __name__ == "__main__":
    main()
