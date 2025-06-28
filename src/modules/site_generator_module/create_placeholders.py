"""Module for creating placeholder HTML files for missing law documents.

This module generates placeholder HTML pages for law versions that exist in the
metadata but don't have corresponding HTML files (e.g., due to processing errors
or missing source documents). It:
- Identifies missing HTML files by comparing metadata with existing files
- Creates placeholder pages with appropriate messaging
- Processes placeholders through the standard build pipeline
- Ensures consistent formatting with regular law pages

Placeholder pages inform users that the text is unavailable and provide a link
to the original source for verification.

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import os
from bs4 import BeautifulSoup

from src.modules.site_generator_module import build_zhlaw
from src.utils.logging_utils import get_module_logger

# Get logger from main module
logger = get_module_logger(__name__)


def main(laws, html_files, placeholder_dir):
    """
    Processes the collection data and creates placeholder HTML files where necessary.
    :param laws: List of laws as JSON data.
    :param html_files: List of paths to existing HTML files.
    :param placeholder_dir: Directory where placeholder HTML files should be created.
    """
    # Convert paths to filenames for easier comparison
    existing_files = set(os.path.basename(file) for file in html_files)
    # Ensure the placeholder folder exists
    os.makedirs(placeholder_dir, exist_ok=True)
    # Process each law and its versions
    for law in laws:
        ordnungsnummer = law["ordnungsnummer"]
        erlasstitel = law["erlasstitel"]
        versions = law["versions"]
        for version in versions:
            nachtragsnummer = version["nachtragsnummer"]
            law_page_url = version.get("law_page_url", "")
            filename = f"{ordnungsnummer}-{nachtragsnummer}.html"
            in_force = version.get("in_force", False)
            # Add erlasstitel and ordnungsnummer to version
            version["erlasstitel"] = erlasstitel
            version["ordnungsnummer"] = ordnungsnummer
            # Check if HTML file exists in the provided list
            if filename not in existing_files:
                placeholder_path = os.path.join(placeholder_dir, filename)
                # File does not exist, create placeholder
                with open(placeholder_path, "w") as f:
                    f.write(
                        f"<html><body><div id='law'><div id='source-text'><h1>Kein Erlasstext vorhanden.</h1><p>Möglicherweise enthält diese Nachtragsnummer keinen Text oder es liegt ein Fehler in der automatisierten Verarbeitung vor. Bitte überprüfe die <a href='{law_page_url}'>Quelle</a> für mehr Informationen.</p></div></div></body></html>"
                    )
                logger.info(f"Created placeholder HTML file: {placeholder_path}")
                # Add to existing_files to prevent re-creation
                existing_files.add(filename)

                # Process the HTML with BeautifulSoup
                with open(placeholder_path, "r") as file:
                    soup = BeautifulSoup(file, "html.parser")

                # Create document info dictionary
                doc_info = {
                    "erlasstitel": erlasstitel,
                    "ordnungsnummer": ordnungsnummer,
                    "nachtragsnummer": nachtragsnummer,
                    "in_force": in_force,
                    "versions": versions,
                }
                doc_info.update(version)  # Add all other version info

                # Process the HTML using build_zhlaw's main function
                soup = build_zhlaw.main(
                    soup, placeholder_path, doc_info, "new_html", law_origin="zh"
                )

                # Write the modified HTML back to the file
                with open(placeholder_path, "w") as f:
                    f.write("<!DOCTYPE html>\n")
                    f.write(str(soup))
            else:
                logger.info(f"HTML file exists: {filename}")


if __name__ == "__main__":
    main()
