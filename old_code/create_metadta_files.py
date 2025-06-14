#!/usr/bin/env python3
import os
import json
from bs4 import BeautifulSoup

# Base directory where the processed HTML files are located.
BASE_DIR = "data/fedlex/fedlex_files_processed"


def process_html_file(file_path):
    """
    Given a file path to an HTML file, extract the available metadata values.
    """
    # Read the HTML file
    with open(file_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    # Parse the HTML using BeautifulSoup
    soup = BeautifulSoup(html_content, "html.parser")

    # Extract the content of <h1 class="erlasstitel">
    erlasstitel_tag = soup.find("h1", class_="erlasstitel")
    erlasstitel = erlasstitel_tag.get_text(strip=True) if erlasstitel_tag else ""

    # Extract the content of <h2 class="erlasskurztitel">
    kurztitel_tag = soup.find("h2", class_="erlasskurztitel")
    kurztitel = kurztitel_tag.get_text(strip=True) if kurztitel_tag else ""

    # Extract the content of <p class="srnummer">
    srnummer_tag = soup.find("p", class_="srnummer")
    ordnungsnummer = srnummer_tag.get_text(strip=True) if srnummer_tag else ""

    # Extract the date from the filename.
    # Assume the filename has the form: <lawid>-<YYYYMMDD>-merged.html
    filename = os.path.basename(file_path)
    parts = filename.split("-")
    if len(parts) >= 3:
        date_part = parts[1]
    else:
        date_part = ""

    # Use the date for publikationsdatum, nachtragsnummer, and numeric_nachtragsnummer.
    publikationsdatum = date_part
    nachtragsnummer = date_part
    try:
        numeric_nachtragsnummer = float(date_part) if date_part else 0.0
    except ValueError:
        numeric_nachtragsnummer = 0.0

    # Build the metadata dictionary. Other fields are left as empty strings, False,
    # empty lists, or None as appropriate.
    metadata = {
        "doc_info": {
            "law_page_url": "",
            "law_text_url": "",
            "law_text_redirect": "",
            "nachtragsnummer": nachtragsnummer,
            "numeric_nachtragsnummer": numeric_nachtragsnummer,
            "erlassdatum": "",
            "inkraftsetzungsdatum": "",
            "publikationsdatum": publikationsdatum,
            "aufhebungsdatum": "",
            "in_force": False,
            "bandnummer": "",
            "hinweise": "",
            "erlasstitel": erlasstitel,
            "ordnungsnummer": ordnungsnummer,
            "kurztitel": kurztitel,
            "abkuerzung": "",
            "category": {
                "folder": {"id": 0, "name": ""},
                "section": {"id": 0, "name": ""},
                "subsection": None,
            },
            "dynamic_source": "",
            "zhlaw_url_dynamic": "",
            "versions": {"older_versions": [], "newer_versions": []},
        }
    }

    return metadata


def create_metadata_files():
    """
    Walk through BASE_DIR recursively. For every HTML file that ends with "-merged.html",
    extract the metadata and write out a JSON file with "-metadata.json" replacing the
    "-merged.html" suffix.
    """
    for root, dirs, files in os.walk(BASE_DIR):
        for file in files:
            if file.endswith("-merged.html"):
                html_filepath = os.path.join(root, file)
                print(f"Processing: {html_filepath}")

                # Extract metadata from the HTML file.
                metadata = process_html_file(html_filepath)

                # Create the output JSON filename.
                # For example, "0.974.222.3-20210701-merged.html" becomes "0.974.222.3-20210701-metadata.json"
                json_filename = file.replace("-merged.html", "-metadata.json")
                json_filepath = os.path.join(root, json_filename)

                # Write the metadata to the JSON file.
                with open(json_filepath, "w", encoding="utf-8") as json_file:
                    json.dump(metadata, json_file, ensure_ascii=False, indent=4)

                print(f"Created metadata file: {json_filepath}")


if __name__ == "__main__":
    create_metadata_files()
