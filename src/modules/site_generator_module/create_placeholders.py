# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

import logging
import os
from bs4 import BeautifulSoup

from src.modules.site_generator_module import build_zhlaw

# Get logger from main module
logger = logging.getLogger(__name__)


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

            # Add erlasstitel and ordnugnsnummer to version
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

                # Process the HTML with BeautifulSoup and additional functions
                with open(placeholder_path, "r") as file:
                    soup = BeautifulSoup(file, "html.parser")

                # Modify HTML with various functions
                soup = build_zhlaw.modify_html(soup, erlasstitel)
                soup = build_zhlaw.insert_nav_buttons(soup)
                soup = build_zhlaw.insert_combined_table(
                    soup, version, in_force, ordnungsnummer, nachtragsnummer
                )
                soup = build_zhlaw.insert_versions_and_update_navigation(
                    soup, versions, ordnungsnummer, nachtragsnummer
                )
                soup = build_zhlaw.insert_header(soup)
                soup = build_zhlaw.insert_footer(soup)

                # Write the modified HTML back to the file
                with open(placeholder_path, "w") as f:
                    f.write("<!DOCTYPE html>\n")
                    f.write(str(soup.prettify()))

            else:
                logger.info(f"HTML file exists: {filename}")


if __name__ == "__main__":
    main()
