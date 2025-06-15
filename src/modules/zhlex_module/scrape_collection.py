# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

import requests
import sys
import os
import time
import logging
from bs4 import BeautifulSoup
import json
import arrow
from tqdm import tqdm
import re
from pathlib import Path

# Import configuration
from src.config import URLs, APIConfig, DateFormats
from src.constants import Messages

# Configure logging
logger = logging.getLogger(__name__)


def scrape_laws(folder):
    if not os.path.exists(folder):
        os.makedirs(folder)

    all_laws = []
    page = 0

    while True:
        time.sleep(APIConfig.WEB_REQUEST_DELAY)
        url = f"{URLs.ZHLEX_API}?includeRepealedEnactments=on&page={page}"

        try:
            # Request from CH-IP
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()

            if response.text:
                laws = response.json().get("data", [])
                if not laws:
                    break
                all_laws.extend(laws)
            else:
                break
        except Exception as e:
            logger.error(f"Error occurred while processing page {page}: {e}")
            # Exit script
            sys.exit(0)

        page += 1

    # Replace referenceNumber with ordnungsnummer and enactmentTitle with erlasstitel
    for law in all_laws:
        law["ordnungsnummer"] = law.pop("referenceNumber")
        law["erlasstitel"] = law.pop("enactmentTitle").strip()

    with open(
        os.path.join(folder, "zhlex_data_raw.json"), "w", encoding="utf-8"
    ) as file:
        json.dump(all_laws, file, indent=4, ensure_ascii=False)


def extract_data(soup, term):
    dt = soup.find("dt", text=term)
    if dt and dt.find_next_sibling("dd"):
        return dt.find_next_sibling("dd").get_text().strip()
    return None


def get_redirected_url(html_content, base_url="http://www2.zhlex.zh.ch"):
    """
    Extracts and constructs the absolute redirect URL from the HTML content.

    Args:
        html_content (str): The HTML content to extract the redirect URL from.
        base_url (str): The base URL to prepend to the relative URL.

    Returns:
        str or None: The absolute redirect URL if found, None otherwise.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    script_tag = soup.find("script")
    if script_tag and "window.location" in script_tag.text:
        redirect_path = script_tag.text.split('"')[1]
        if not redirect_path.startswith(("http://", "https://")):
            redirect_path = base_url + redirect_path
        return redirect_path
    return None


def extract_nachtragsnummer(link):
    """
    Extracts the nachtragsnummer from the given link.
    Assumes the nachtragsnummer is after the last '-' and before '.html'
    """
    parts = link.rsplit("-", 1)  # Split from the right to get the last part
    if len(parts) > 1:
        nachtragsnummer_part = parts[1]
        nachtragsnummer = nachtragsnummer_part.split(".")[0]
        return nachtragsnummer
    return "000"  # Default nachtragsnummer if not found in the URL


# Function to replace "-" with an empty string ""
def replace_dash_with_empty_string(value):
    if isinstance(value, dict):
        for key, val in value.items():
            value[key] = replace_dash_with_empty_string(val)
    elif isinstance(value, list):
        for i in range(len(value)):
            value[i] = replace_dash_with_empty_string(value[i])
    elif value == "-":
        return ""
    return value


def load_hierarchy():
    # Load the hierarchy JSON file
    with open(
        "data/zhlex/zhlex_data/zhlex_cc_folders_hierarchy.json", "r", encoding="utf-8"
    ) as file:
        hierarchy = json.load(file)
    return hierarchy


def find_category_by_ordnungsnummer(hierarchy, ordnungsnummer):
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


def process_laws(folder):
    processed_laws_path = os.path.join(folder, "zhlex_data_processed.json")
    hierarchy = load_hierarchy()  # Load the hierarchy once here

    # Load existing processed laws if the file exists
    if os.path.exists(processed_laws_path):
        with open(processed_laws_path, "r", encoding="utf-8") as file:
            processed_laws = json.load(file)
    else:
        processed_laws = []

    # Transform processed_laws to a dict for quick access
    laws_dict = {law["ordnungsnummer"]: law for law in processed_laws}

    with open(
        os.path.join(folder, "zhlex_data_raw.json"), "r", encoding="utf-8"
    ) as file:
        new_laws = json.load(file)

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
    with open(processed_laws_path, "w", encoding="utf-8") as file:
        json.dump(processed_laws, file, indent=4, ensure_ascii=False)


def main(folder):
    scrape_laws(folder)
    process_laws(folder)


if __name__ == "__main__":
    main()
