# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

import os
import shutil
from zipfile import ZipFile
from bs4 import BeautifulSoup
import urllib.parse
import tqdm

import logging


# Get logger from main module
logger = logging.getLogger(__name__)


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


def process_html_files(source_dir, dest_dir, base_url):
    # Ensure the destination directory exists
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)

    # Paths for subfolders
    in_force_dir = os.path.join(dest_dir, "in_force")
    not_in_force_dir = os.path.join(dest_dir, "not_in_force")

    # Ensure subdirectories exist
    os.makedirs(in_force_dir, exist_ok=True)
    os.makedirs(not_in_force_dir, exist_ok=True)

    # Process each HTML file in the source directory
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
                    # Check for <td> with the specified data attribute
                    td = law_div.find(
                        "td", attrs={"data-pagefind-filter": "Text in Kraft"}
                    )
                    if td and td.get_text().strip() == "Ja":
                        target_dir = in_force_dir
                    else:
                        target_dir = not_in_force_dir

                    # Write the processed HTML to the correct subdirectory
                    new_file_path = os.path.join(target_dir, filename)
                    with open(new_file_path, "w", encoding="utf-8") as new_file:
                        new_file.write(str(soup))


def create_zip_file(source_dir, zip_file_path):
    with ZipFile(zip_file_path, "w") as zipf:
        # Zip the directory structure
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                zipf.write(
                    os.path.join(root, file),
                    os.path.relpath(
                        os.path.join(root, file), os.path.join(source_dir, "..")
                    ),
                )


def main():
    base_url = "https://www.zhlaw.ch/col/"
    source_html_dir = "public/col/"
    destination_dir_archive = "public/data"
    destination_dir_json = "public/collection-metadata.json"
    json_file_path = "data/zhlex/zhlex_data/zhlex_data_processed.json"

    zip_file_path = "public/collection-html.zip"
    process_html_files(source_html_dir, destination_dir_archive, base_url)
    create_zip_file(destination_dir_archive, zip_file_path)
    logger.info("Processing complete and zip file created.")

    # Copy JSON file to root
    shutil.copy(json_file_path, destination_dir_json)

    # Remove the processed HTML files
    shutil.rmtree(destination_dir_archive)


if __name__ == "__main__":
    main()
