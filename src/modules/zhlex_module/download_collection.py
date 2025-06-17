"""Module for downloading legal text files from ZH-Lex.

This module downloads the actual PDF and HTML files for legal texts that have been
previously scraped from the ZH-Lex system. It creates a structured directory hierarchy
for organizing the downloaded files and generates metadata files for each version.

Key features:
- Downloads PDF and HTML files for each law version
- Creates organized directory structure by law number and version
- Generates metadata files with download timestamps
- Handles both direct URLs and redirected URLs
- Implements rate limiting to respect server resources
- Skips already downloaded files to support resumption

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import os
import requests
import json
import arrow
import logging
import time
from tqdm import tqdm

# Configure logging
logger = logging.getLogger(__name__)

timestamp = arrow.now().format("YYYYMMDD-HHmmss")


def download_law_text(url, law_dir, file_name):
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()

        # Save the file
        with open(law_dir, "wb") as file:
            file.write(response.content)

        return timestamp, file_name
    except Exception as e:
        logging.info(f"Error downloading {url}: {e}")
        return False, None


def create_metadata_file(metadata, file_path):
    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=4, ensure_ascii=False)


def main(folder):
    with open(
        os.path.join("data/zhlex/zhlex_data/zhlex_data_processed.json"),
        "r",
        encoding="utf-8",
    ) as file:
        laws = json.load(file)

    for law in tqdm(laws, desc="downloading laws"):
        for version in law.get("versions", []):

            erlasstitel = law.get("erlasstitel")
            kurztitel = law.get("kurztitel")
            abkuerzung = law.get("abkuerzung")
            ordnungsnummer = law["ordnungsnummer"]
            nachtragsnummer = version["nachtragsnummer"]
            law_dir = os.path.join(folder, ordnungsnummer, str(nachtragsnummer))

            os.makedirs(law_dir, exist_ok=True)

            if version.get("law_text_redirect") != None:
                law_text_url = version.get("law_text_redirect")
            elif version.get("law_text_url") != None:
                law_text_url = version.get("law_text_url")
            else:
                continue

            # Build file name
            if "pdf" in law_text_url:
                file_name = (
                    str(ordnungsnummer)
                    + "-"
                    + str(nachtragsnummer)
                    + "-original"
                    + ".pdf"
                )
            else:
                file_name = (
                    str(ordnungsnummer)
                    + "-"
                    + str(nachtragsnummer)
                    + "-original"
                    + ".html"
                )
            file_path = os.path.join(law_dir, file_name)

            if not os.path.exists(file_path):
                # Logging
                logger.info(f"Downloading {law_text_url} to {file_path}")
                success = download_law_text(law_text_url, file_path, file_name)
                time.sleep(1)

                metadata = {
                    "doc_info": {
                        "erlasstitel": erlasstitel,
                        "kurztitel": kurztitel,
                        "abkuerzung": abkuerzung,
                        "ordnungsnummer": ordnungsnummer,
                        **law.get("doc_info", {}),
                    },
                    "process_steps": {
                        "scrape_law": timestamp,
                        "crop_pdf": "",
                        "call_api_law": "",
                        "call_api_marginalia": "",
                        "generate_html": "",
                    },
                }

                # Replace file ending (.html or .pdf) with -metadata.json
                metadata_file_path = file_path.replace(
                    "-original.html", "-metadata.json"
                ).replace("-original.pdf", "-metadata.json")

                create_metadata_file(metadata, metadata_file_path)


if __name__ == "__main__":
    main("laws")
