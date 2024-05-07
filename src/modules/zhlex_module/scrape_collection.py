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

# Configure logging
logger = logging.getLogger(__name__)

BASE_URL = "https://www.zh.ch"

ORIG_DATE_FORMAT = "DD.MM.YYYY"
NEW_DATE_FORMAT = "YYYYMMDD"


def scrape_laws(folder):
    if not os.path.exists(folder):
        os.makedirs(folder)

    all_laws = []
    page = 0

    while True:
        time.sleep(0.5)
        url = f"{BASE_URL}/de/politik-staat/gesetze-beschluesse/gesetzessammlung/_jcr_content/main/lawcollectionsearch_312548694.zhweb-zhlex-ls.zhweb-cache.json?includeRepealedEnactments=on&page={page}"

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

    # Replace referenceNumber with ordnungsnummer
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


def process_laws(folder):
    processed_laws_path = os.path.join(folder, "zhlex_data_processed.json")
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
        if "Nachtrag" not in law["erlasstitel"]:
            erlasstitel = law["erlasstitel"]
        else:
            pass
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

        # Fetch versions and other details
        versions = []  # This will hold version data for the current law
        law_page_url = BASE_URL + law["link"]
        try:
            response = requests.get(law_page_url, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            version_items = soup.select("ul.atm-list li.atm-list__item a")
            versions = []

            for item in version_items:
                version_law_page_url = BASE_URL + item["href"]
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
                    erlassdatum = arrow.get(erlassdatum, ORIG_DATE_FORMAT).format(
                        NEW_DATE_FORMAT
                    )
                if inkraftsetzungsdatum != "-":
                    inkraftsetzungsdatum = arrow.get(
                        inkraftsetzungsdatum, ORIG_DATE_FORMAT
                    ).format(NEW_DATE_FORMAT)
                if aufhebungsdatum != "-":
                    in_force_status = False
                    aufhebungsdatum = arrow.get(
                        aufhebungsdatum, ORIG_DATE_FORMAT
                    ).format(NEW_DATE_FORMAT)
                else:
                    in_force_status = True
                if publikationsdatum != "-":
                    publikationsdatum = arrow.get(
                        publikationsdatum, ORIG_DATE_FORMAT
                    ).format(NEW_DATE_FORMAT)

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

                version_data = {
                    "law_page_url": version_law_page_url,
                    "law_text_url": law_text_url,
                    "law_text_redirect": law_text_redirect,
                    "nachtragsnummer": nachtragsnummer,
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

        law_data["versions"] = versions
        law_data["erlasstitel"] = erlasstitel

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
