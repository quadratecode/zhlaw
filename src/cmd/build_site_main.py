# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

from src.modules.site_generator_module import build_zhlaw
from src.modules.site_generator_module import process_old_html
from src.modules.site_generator_module import create_placeholders

from src.modules.dataset_generator_module import build_dataset

# Import external modules
import logging
import glob
import json
from tqdm import tqdm
import shutil
import os
import arrow
from bs4 import BeautifulSoup
import subprocess

# Set up logging
logging.basicConfig(
    filename="logs/process.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S %p",
)

static_path = "public/"
collection_path = "public/col/"
placeholder_dir = "data/zhlex/placeholders"

# Delete folders before new generation
if os.path.exists(collection_path):
    shutil.rmtree(static_path)
    shutil.rmtree(placeholder_dir)


def main():

    # Initialize error counter
    error_counter = 0

    # Timestamp
    timestamp = arrow.now().format("YYYYMMDD-HHmmss")

    logging.info("Loading laws index")
    # Load HTML generated from PDF
    html_files = glob.glob(
        "data/zhlex/zhlex_files/**/**/*-merged.html",
        recursive=True,
    )
    # Load original HTML files
    html_files += glob.glob(
        "data/zhlex/zhlex_files/**/**/*-original.html",
        recursive=True,
    )
    # Load all files from src/static_files ending in .html
    html_files += glob.glob(
        "src/static_files/html/*.html",
        recursive=True,
    )
    # Remove duplicates found from different junctions
    html_files = list(set(html_files))
    if not html_files:
        logging.info("No PDF files found. Exiting.")
        return

    for html_file in tqdm(html_files):
        # Define metadata file path
        if html_file.endswith("-original.html"):
            metadata_file = html_file.replace("-original.html", "-metadata.json")
            sfx = "-original"
            type = "old_html"
        elif html_file.endswith("-merged.html"):
            metadata_file = html_file.replace("-merged.html", "-metadata.json")
            sfx = "-merged"
            type = "new_html"
        else:
            type = "site_element"

        try:
            if type == "old_html":
                with open(metadata_file, "r", encoding="utf-8") as file:
                    metadata = json.load(file)
                with open(
                    html_file, "r", encoding="iso-8859-1"
                ) as file:  # Changed encoding to iso-8859-1
                    soup = BeautifulSoup(file, "html.parser")
                # Process old HTML only for these files
                soup = process_old_html.main(soup)
            elif type == "new_html":
                with open(metadata_file, "r", encoding="utf-8") as file:
                    metadata = json.load(file)
                with open(html_file, "r", encoding="utf-8") as file:
                    soup = BeautifulSoup(file, "html.parser")
            else:
                # Emtpy metadata for site elements
                metadata = {}
                with open(html_file, "r", encoding="utf-8") as file:
                    soup = BeautifulSoup(file, "html.parser")

            # Build ZHLaw
            logging.info(f"Inserting InfoBox: {html_file}")
            doc_info = metadata.get("doc_info", {})
            soup = build_zhlaw.main(soup, html_file, doc_info, type)
            logging.info(f"Finished inserting InfoBox: {html_file}")

            # See if paths exist, if not create them
            if not os.path.exists(collection_path):
                os.makedirs(collection_path)
            if not os.path.exists(static_path):
                os.makedirs(static_path)
            if type != "site_element":
                # Write metadata file
                logging.info(f"Writing metadata file: {metadata_file}")
                with open(metadata_file, "w", encoding="utf-8") as file:
                    json.dump(metadata, file, indent=4, ensure_ascii=False)
                logging.info(f"Finished writing metadata file: {metadata_file}")
                # Split the path from the filename
                head, tail = os.path.split(html_file)
                # Remove the '-merged' suffix from the filename
                new_tail = tail.replace(sfx, "")
                # Combine the path with the new filename
                # Copy the file to the new location with the updated filename
                new_file_path = collection_path + new_tail
            else:
                new_file_path = static_path + os.path.basename(html_file)
            with open(new_file_path, "w", encoding="utf-8") as file:
                # Add doc type to the beginning of the file
                file.write("<!DOCTYPE html>\n")
                file.write(str(soup.prettify()))
            logging.info(f"Finished writing new file: {new_file_path}")

        except Exception as e:
            logging.error(
                f"Error during in {__file__}: {e} at {timestamp}", exc_info=True
            )
            error_counter += 1
            continue

    # Load collection data
    with open(
        "data/zhlex/zhlex_data/zhlex_data_processed.json", "r", encoding="utf-8"
    ) as file:
        zhlex_data_processed = json.load(file)

    # Build dataset (placed here to not include placeholders)
    logging.info("Building dataset")
    build_dataset.main(collection_path, zhlex_data_processed)
    logging.info("Finished building dataset")

    # Load all files from public ending in .html
    public_html_files = glob.glob(
        "public/col/*.html",
        recursive=True,
    )

    # Create placeholders
    logging.info("Creating placeholders")
    create_placeholders.main(zhlex_data_processed, public_html_files, placeholder_dir)
    logging.info("Finished creating placeholders")

    # Copy placeholder files
    shutil.copytree(
        "data/zhlex/placeholders",
        collection_path,
        dirs_exist_ok=True,
    )

    # Copy markup files
    shutil.copytree(
        "src/static_files/markup/",
        static_path,
        dirs_exist_ok=True,
    )

    # Run "npx pagefind --site /home/rdm/github/zhlaw/public/" to build search index
    # Requires pagefind: https://github.com/CloudCannon/pagefind
    logging.info("Building search index")
    subprocess.run(["npx", "pagefind", "--site", static_path])
    logging.info("Finished building search index")


if __name__ == "__main__":
    main()
