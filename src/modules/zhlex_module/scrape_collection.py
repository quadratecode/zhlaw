# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

import sys
import arrow
from tqdm import tqdm
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
import requests
import json
import os
from bs4 import BeautifulSoup

# Import configuration
from src.config import URLs, APIConfig, DateFormats, DataPaths
from src.constants import Messages

# Import utilities
from src.utils.file_utils import FileOperations, read_json, write_json, ensure_directory
from src.utils.http_utils import HTTPClient, WebScraper
from src.utils.html_utils import HTMLProcessor
from src.logging_config import get_logger
from src.exceptions import ScrapingException, FileProcessingException

# Configure logging
logger = get_logger(__name__)


def scrape_laws(folder: str) -> None:
    """Scrape all laws from ZH-Lex API and save to JSON."""
    folder_path = Path(folder)
    ensure_directory(folder_path)

    all_laws = []
    page = 0

    with WebScraper() as scraper:
        while True:
            url = f"{URLs.ZHLEX_API}?includeRepealedEnactments=on&page={page}"
            
            try:
                logger.info(f"Fetching page {page} from ZH-Lex API")
                laws_data = scraper.fetch_json(url)
                laws = laws_data.get("data", [])
                
                if not laws:
                    logger.info(f"No more laws found. Total pages: {page}")
                    break
                    
                all_laws.extend(laws)
                logger.debug(f"Found {len(laws)} laws on page {page}")
                
            except ScrapingException as e:
                # Check if this is likely the end of pagination
                if page > 0 and all_laws:
                    logger.info(f"Reached end of pagination at page {page}. Total laws collected: {len(all_laws)}")
                    break
                else:
                    logger.error(f"Failed to fetch page {page}: {e}")
                    sys.exit(1)
            
            page += 1

    # Transform law data structure
    for law in all_laws:
        law["ordnungsnummer"] = law.pop("referenceNumber")
        law["erlasstitel"] = law.pop("enactmentTitle").strip()

    # Save raw data
    output_path = folder_path / "zhlex_data_raw.json"
    write_json(output_path, all_laws)
    logger.info(f"Saved {len(all_laws)} laws to {output_path}")


def extract_data(soup: Any, term: str) -> Optional[str]:
    """Extract data from definition list by term."""
    dt = soup.find("dt", text=term)
    if dt and dt.find_next_sibling("dd"):
        return dt.find_next_sibling("dd").get_text().strip()
    return None


def get_redirected_url(html_content: str, base_url: str = "http://www2.zhlex.zh.ch") -> Optional[str]:
    """
    Extracts and constructs the absolute redirect URL from the HTML content.

    Args:
        html_content: The HTML content to extract the redirect URL from.
        base_url: The base URL to prepend to the relative URL.

    Returns:
        The absolute redirect URL if found, None otherwise.
    """
    html_processor = HTMLProcessor()
    soup = html_processor.parse_html(html_content)
    
    script_tag = soup.find("script")
    if script_tag and "window.location" in script_tag.text:
        redirect_path = script_tag.text.split('"')[1]
        if not redirect_path.startswith(("http://", "https://")):
            redirect_path = base_url + redirect_path
        return redirect_path
    return None


def extract_nachtragsnummer(link: str) -> str:
    """
    Extract the nachtragsnummer (amendment number) from a URL.
    
    The nachtragsnummer is expected to be after the last '-' and before '.html'
    in the URL. For example, from 'erlass-131_1-2020_01_01-118.html', 
    this would extract '118'.
    
    Args:
        link: URL containing the nachtragsnummer
        
    Returns:
        The extracted nachtragsnummer or "000" if not found
    """
    parts = link.rsplit("-", 1)  # Split from the right to get the last part
    if len(parts) > 1:
        nachtragsnummer_part = parts[1]
        nachtragsnummer = nachtragsnummer_part.split(".")[0]
        return nachtragsnummer
    return "000"  # Default nachtragsnummer if not found in the URL


def replace_dash_with_empty_string(value: Any) -> Any:
    """
    Recursively replace all "-" values with empty strings in a data structure.
    
    This function traverses dictionaries and lists, replacing any standalone
    "-" values with empty strings. This is commonly used to clean up data
    where "-" represents missing or null values.
    
    Args:
        value: The value to process (can be dict, list, or any other type)
        
    Returns:
        The processed value with "-" replaced by ""
    """
    if isinstance(value, dict):
        for key, val in value.items():
            value[key] = replace_dash_with_empty_string(val)
    elif isinstance(value, list):
        for i in range(len(value)):
            value[i] = replace_dash_with_empty_string(value[i])
    elif value == "-":
        return ""
    return value


def load_hierarchy() -> Dict[str, Any]:
    """
    Load the law category hierarchy from JSON file.
    
    Returns:
        Dictionary containing the hierarchy structure
        
    Raises:
        FileProcessingException: If the hierarchy file cannot be loaded
    """
    hierarchy_path = DataPaths.ZHLEX_DATA / "zhlex_cc_folders_hierarchy.json"
    try:
        return read_json(hierarchy_path)
    except Exception as e:
        raise FileProcessingException(
            hierarchy_path,
            "load hierarchy",
            e
        )


def find_category_by_ordnungsnummer(
    hierarchy: Dict[str, Any], 
    ordnungsnummer: str
) -> Optional[str]:
    """
    The function uses the first group of the ordnungsnummer (e.g. for "131.1" it uses "131")
    and searches in folder keys, then inside each folder's "sections", and then inside any "subsections."

    Returns a structured category object of the form:
       { "folder": { "id": ..., "name": ... },
         "section": { "id": ..., "name": ... } or None,
         "subsection": { "id": ..., "name": ... } or None }
    """
    # Extract the first group, e.g. "131" from "131.1"
    ordnungsnummer_first_group = ordnungsnummer.split(".")[0]

    def search_hierarchy(level, target):
        """
        Recursively search through the given dictionary (level) for a key that matches target.
        This function first checks the current level’s keys (which may be folder IDs, section IDs,
        or subsection IDs). Then it explicitly looks into any "sections" and "subsections" objects.

        Returns a dictionary of the form:
           { "folder": { "id": <folder_key>, "name": <folder_name> },
             "section": { "id": <section_key>, "name": <section_name> } or None,
             "subsection": { "id": <subsection_key>, "name": <subsection_name> } or None }
        if a match is found; otherwise returns None.
        """
        # First, check for an exact key match at this level.
        if target in level:
            # We assume that if the match is at the top level, it is a folder match.
            value = level[target]
            if isinstance(value, dict):
                return {
                    "folder": {"id": target, "name": value.get("name", "")},
                    "section": None,
                    "subsection": None,
                }
            else:
                return {
                    "folder": {"id": target, "name": value},
                    "section": None,
                    "subsection": None,
                }

        # Next, iterate through the keys at this level.
        for key, value in level.items():
            if isinstance(value, dict):
                # If there is a "sections" key, try to match the target in it.
                if "sections" in value and isinstance(value["sections"], dict):
                    sections = value["sections"]
                    if target in sections:
                        section_data = sections[target]
                        folder = {"id": key, "name": value.get("name", "")}
                        if isinstance(section_data, dict):
                            return {
                                "folder": folder,
                                "section": {
                                    "id": target,
                                    "name": section_data.get("name", ""),
                                },
                                "subsection": None,
                            }
                        else:
                            return {
                                "folder": folder,
                                "section": {"id": target, "name": section_data},
                                "subsection": None,
                            }
                    # Otherwise, search in each section’s "subsections" (if available).
                    for sec_key, sec_value in value["sections"].items():
                        if (
                            sec_value
                            and isinstance(sec_value, dict)
                            and "subsections" in sec_value
                            and isinstance(sec_value["subsections"], dict)
                        ):
                            subsections = sec_value["subsections"]
                            if target in subsections:
                                folder = {"id": key, "name": value.get("name", "")}
                                section = {
                                    "id": sec_key,
                                    "name": sec_value.get("name", ""),
                                }
                                sub_data = subsections[target]
                                return {
                                    "folder": folder,
                                    "section": section,
                                    "subsection": {
                                        "id": target,
                                        "name": sub_data.get("name", ""),
                                    },
                                }
                # Additionally, search recursively in any nested dictionaries
                # (for example, in case a folder’s value contains additional nested keys).
                for nested_key in ["sections", "subsections"]:
                    if nested_key in value and isinstance(value[nested_key], dict):
                        result = search_hierarchy(value[nested_key], target)
                        if result:
                            # If we haven't yet recorded a folder, use the current one.
                            if result["folder"] is None:
                                result["folder"] = {
                                    "id": key,
                                    "name": value.get("name", ""),
                                }
                            return result
        return None

    # 1. First, attempt using the full first group (e.g. "131").
    category = search_hierarchy(hierarchy, ordnungsnummer_first_group)
    if category:
        return category

    # 2. If no direct match, try with the first two digits (e.g. "13" for "131") if possible.
    if len(ordnungsnummer_first_group) >= 2:
        target = ordnungsnummer_first_group[:2]
        category = search_hierarchy(hierarchy, target)
        if category:
            return category

    # 3. Otherwise, return none if no match is found.
    return {
        "folder": None,
        "section": None,
        "subsection": None,
    }


def process_laws(folder: str) -> None:
    """Process all scraped laws and add metadata.
    
    Args:
        folder: Path to the data folder
    """
    processed_laws_path = Path(folder) / "zhlex_data_processed.json"
    hierarchy = load_hierarchy()  # Load the hierarchy once here

    # Load existing processed laws if the file exists
    if processed_laws_path.exists():
        processed_laws = read_json(processed_laws_path)
    else:
        processed_laws = []

    # Transform processed_laws to a dict for quick access
    laws_dict = {law["ordnungsnummer"]: law for law in processed_laws}

    raw_laws_path = Path(folder) / "zhlex_data_raw.json"
    new_laws = read_json(raw_laws_path)

    for law in tqdm(new_laws, desc="Processing laws"):
        ordnungsnummer = law["ordnungsnummer"]
        nachtragsnummer = extract_nachtragsnummer(law["link"])

        if ordnungsnummer in laws_dict and any(
            version["nachtragsnummer"] == nachtragsnummer
            for version in laws_dict[ordnungsnummer].get("versions", [])
        ):
            continue  # Skip if this version already processed

        # Prepare law data excluding certain keys
        law_data = {
            key: law[key]
            for key in law
            if key not in ["enactmentDate", "withdrawalDate", "link"]
        }

        # Add dynamic URL as "dynamic_source"
        dynamic_source = (
            f"http://www.zhlex.zh.ch/Erlass.html?Open&Ordnr={ordnungsnummer}"
        )
        law_data["dynamic_source"] = dynamic_source

        # Add a dynamic zhlaw URL as "zhlaw_url_dynamic"
        # Pattern: zhalw.ch/col-zh/{ordnungsnummer}
        zhlaw_url_dynamic = f"https://www.zhlaw.ch/col-zh/{ordnungsnummer}"
        law_data["zhlaw_url_dynamic"] = zhlaw_url_dynamic

        # Find and add category based on the ordnungsnummer, passing hierarchy
        category = find_category_by_ordnungsnummer(hierarchy, ordnungsnummer)
        law_data["category"] = category

        # Fetch versions and other details
        versions = []  # This will hold version data for the current law
        highest_nachtragsnummer = -1
        highest_nachtragsnummer_erlasstitel = None
        highest_nachtragsnummer_abbreviation = None

        law_page_url = URLs.ZH_BASE + law["link"]
        try:
            response = requests.get(law_page_url, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            version_items = soup.select("ul.atm-list li.atm-list__item a")
            versions = []

            for item in version_items:
                version_law_page_url = URLs.ZH_BASE + item["href"]
                nachtragsnummer = item.input["value"]

                version_response = requests.get(
                    version_law_page_url, headers={"User-Agent": "Mozilla/5.0"}
                )
                version_response.raise_for_status()
                version_soup = BeautifulSoup(version_response.content, "html.parser")

                erlassdatum = extract_data(version_soup, "Erlassdatum")
                inkraftsetzungsdatum = extract_data(
                    version_soup, "Inkraftsetzungsdatum"
                )
                aufhebungsdatum = extract_data(version_soup, "Aufhebungsdatum")
                publikationsdatum = extract_data(version_soup, "Publikationsdatum")

                # Convert all dates that are not "-" to YYYYMMDD
                if erlassdatum != "-":
                    erlassdatum = arrow.get(erlassdatum, DateFormats.ORIGINAL).format(
                        DateFormats.STANDARD
                    )
                if inkraftsetzungsdatum != "-":
                    inkraftsetzungsdatum = arrow.get(
                        inkraftsetzungsdatum, DateFormats.ORIGINAL
                    ).format(DateFormats.STANDARD)
                if aufhebungsdatum != "-":
                    in_force_status = False
                    aufhebungsdatum = arrow.get(
                        aufhebungsdatum, DateFormats.ORIGINAL
                    ).format(DateFormats.STANDARD)
                else:
                    in_force_status = True
                if publikationsdatum != "-":
                    publikationsdatum = arrow.get(
                        publikationsdatum, DateFormats.ORIGINAL
                    ).format(DateFormats.STANDARD)

                # Extract PDF URL
                pdf_link_tag = version_soup.find(
                    "a", class_="atm-linklist_item--download"
                )
                law_text_url = pdf_link_tag["href"] if pdf_link_tag else None

                # Get redirect URL
                law_text_redirect = None
                if law_text_url:
                    try:
                        response = requests.get(
                            law_text_url, headers={"User-Agent": "Mozilla/5.0"}
                        )
                        response.raise_for_status()
                        law_text_redirect = get_redirected_url(response.text)
                    except Exception as e:
                        logger.error(f"Error fetching {law_text_url}: {e}")

                # Fetch the erlasstitel for this version
                version_erlasstitel = law.get("erlasstitel", "").strip()

                try:
                    numeric_nachtragsnummer = float(nachtragsnummer)
                except:
                    # Convert any letters in the nachtragsnummer to numbers (e.g. "066a" -> 066a.1, "066b" -> 066b.2, etc.)
                    # Match digits followed by letters in nachtragsnummer
                    match = re.match(r"(\d+)([a-zA-Z]+)$", nachtragsnummer)
                    if match:
                        number_part = match.group(1)
                        letter_part = match.group(2)

                        # Convert each letter to its corresponding number (a=1, b=2, ..., z=26)
                        letter_numbers = "".join(
                            str(ord(char.lower()) - ord("a") + 1)
                            for char in letter_part
                        )

                        # Combine the numeric and letter parts to form a float (e.g., "066a" -> 66.1)
                        numeric_nachtragsnummer = float(
                            f"{number_part}.{letter_numbers}"
                        )
                    else:
                        # Handle cases where nachtragsnummer doesn't match the expected format
                        raise ValueError("Invalid nachtragsnummer format")

                # Check if this erlasstitel does not contain "Nachtrag" and has a higher nachtragsnummer
                if (
                    "Nachtrag" not in version_erlasstitel
                    and numeric_nachtragsnummer > highest_nachtragsnummer
                ):
                    highest_nachtragsnummer = numeric_nachtragsnummer
                    highest_nachtragsnummer_erlasstitel = version_erlasstitel

                # Check for any string within parentheses
                abkuerzung_match = re.search(r"\(([^\)]*)\)", version_erlasstitel)

                if abkuerzung_match:
                    parentheses_content = abkuerzung_match.group(1).strip()

                    # Only proceed if parentheses_content is not an empty string
                    if parentheses_content:
                        # Split by comma if present
                        if "," in parentheses_content:
                            # Assign first group to kurztitel and second group to abbreviation
                            kurztitel, abkuerzung = map(
                                str.strip, parentheses_content.split(",", 1)
                            )
                            highest_nachtragsnummer_kurztitel = kurztitel
                            highest_nachtragsnummer_abbreviation = abkuerzung
                        else:
                            # Check if parentheses_content contains any of the specific substrings
                            substrings = [
                                "verordnung",
                                "gesetz",
                                "reglement",
                                "konkordat",
                                "abkommen",
                                "vereinbarung",
                                "vertrag",
                                "weisung",
                                "konzession",
                                "ordnung",
                            ]

                            # If content contains any of the substrings, assign it to kurztitel, otherwise to abbreviation
                            if any(
                                substring in parentheses_content.lower()
                                for substring in substrings
                            ):
                                highest_nachtragsnummer_kurztitel = parentheses_content
                                highest_nachtragsnummer_abbreviation = ""
                            else:
                                highest_nachtragsnummer_abbreviation = (
                                    parentheses_content
                                )
                                highest_nachtragsnummer_kurztitel = ""

                        # If kurztitel exists, check if it contains any capital letters; if not, empty it
                        if highest_nachtragsnummer_kurztitel and not any(
                            char.isupper() for char in highest_nachtragsnummer_kurztitel
                        ):
                            highest_nachtragsnummer_kurztitel = ""
                else:
                    highest_nachtragsnummer_abbreviation = ""
                    highest_nachtragsnummer_kurztitel = ""

                version_data = {
                    "law_page_url": version_law_page_url,
                    "law_text_url": law_text_url,
                    "law_text_redirect": law_text_redirect,
                    "nachtragsnummer": nachtragsnummer,
                    "numeric_nachtragsnummer": numeric_nachtragsnummer,
                    "erlassdatum": erlassdatum,
                    "inkraftsetzungsdatum": inkraftsetzungsdatum,
                    "publikationsdatum": publikationsdatum,
                    "aufhebungsdatum": aufhebungsdatum,
                    "in_force": in_force_status,
                    "bandnummer": extract_data(version_soup, "Bandnummer"),
                    "hinweise": extract_data(version_soup, "Hinweise"),
                }
                versions.append(version_data)

        except Exception as e:
            logger.error(f"Error fetching {law_page_url}: {e}")

        # If we found a version with the highest nachtragsnummer, use its erlasstitel and abbreviation
        if highest_nachtragsnummer_erlasstitel:
            law_data["erlasstitel"] = highest_nachtragsnummer_erlasstitel
            law_data["abkuerzung"] = highest_nachtragsnummer_abbreviation
            law_data["kurztitel"] = highest_nachtragsnummer_kurztitel
        else:
            law_data["erlasstitel"] = law.get("erlasstitel", "").strip()
            law_data["abkuerzung"] = ""
            law_data["kurztitel"] = ""

        law_data["versions"] = versions

        if ordnungsnummer in laws_dict:
            # If law exists, just append the new versions to it
            laws_dict[ordnungsnummer]["versions"].extend(versions)
        else:
            # Add the new law to laws_dict
            laws_dict[ordnungsnummer] = law_data

    # Convert laws_dict back to list
    processed_laws = list(laws_dict.values())

    # Replace "-" with an empty string ""
    processed_laws = replace_dash_with_empty_string(processed_laws)

    # Save updated processed laws
    write_json(processed_laws_path, processed_laws)


def main(folder: str) -> None:
    """Main entry point for scraping collection.
    
    Args:
        folder: Path to the data folder
    """
    scrape_laws(folder)
    process_laws(folder)


if __name__ == "__main__":
    # Default to standard data folder if run directly
    main(str(DataPaths.ZHLEX_DATA))
