# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

import requests
from bs4 import BeautifulSoup
import json
import logging
import arrow
from time import sleep
import traceback
import os

# Import configuration
from src.config import URLs, APIConfig
from src.constants import Language

# Setup logging
logger = logging.getLogger(__name__)


def get_ablaufschritte(kr_nr, vorlagen_nr):
    # Check if kr_nr is an empty string or None
    if not kr_nr:
        affair_nr = vorlagen_nr
    else:
        affair_nr = kr_nr

    # Wrap the kr_nr in double quotes
    affair_nr_encoded = f'"{affair_nr}"'

    # Parameters
    params_vorlagen = {
        "q": f"krnr any {affair_nr_encoded} sortby beginn_start/sort.descending",
        # Number of fetched entries, max is 1k
        "m": str(APIConfig.KRZH_FETCH_LIMIT),
        # Language
        "l": Language.DE + "-CH",
    }

    # Make a request
    response = requests.get(URLs.KRZH_GESCHAEFT_API, params=params_vorlagen)
    response.raise_for_status()  # Raise an exception for HTTP errors

    # Parse the XML with BeautifulSoup
    soup = BeautifulSoup(response.content, "lxml")

    # Find all "ablaufschritt" tags
    ablaufschritte = soup.find_all("ablaufschritt")

    # From the matches, extract ""AblaufschrittTyp" and "text"
    ablaufschritte_data = []
    for ablaufschritt in ablaufschritte:
        ablaufschritttyp = ablaufschritt.find("ablaufschritttyp")
        text = ablaufschritt.find("text")
        if ablaufschritttyp and text:
            try:
                # Only try to parse if text.text exists and is not empty
                if text.text and text.text.strip():
                    date_formatted = arrow.get(text.text, "DD.MM.YYYY").format(
                        "YYYYMMDD"
                    )
                    ablaufschritte_data.append(
                        {
                            "affair_step_type": ablaufschritttyp.text,
                            "affair_step_date": date_formatted,
                        }
                    )
                else:
                    # Skip steps with empty dates
                    continue
            except arrow.parser.ParserError:
                # Log the error and skip this step
                logging.warning(
                    f"Error parsing date '{text.text}' for step type '{ablaufschritttyp.text}'"
                )
                continue

    return ablaufschritte_data


# Main function to scrape data from the krzh dispatch
def main(folder):
    # Parameters for the API call
    params_dispatch = {
        # Entries younger than 2040-01-01 to catch latest entries
        "q": 'datum_start < "2040-01-01 00:00:00" sortBy datum_start/sort.descending',
        # Number of fetched entries, max is 1k
        "m": str(APIConfig.KRZH_FETCH_LIMIT),
        # Language
        "l": Language.DE + "-CH",
    }

    # Create file path
    file_path = os.path.join(folder, "krzh_dispatch_data.json")

    # Load already scraped entries
    try:
        with open(file_path, "r") as f:
            existing_data = json.load(f)
            stored_mails = [
                arrow.get(entry["krzh_dispatch_date"]) for entry in existing_data
            ]
    # If the entry doesn't exist, create an empty list
    except FileNotFoundError:
        existing_data = []
        stored_mails = []

    def parse_and_download(xml_data):
        soup = BeautifulSoup(xml_data, "lxml-xml")
        # Find all krzh entries, each entry contains multiple affairs
        dispatchs = soup.find_all("KRVersand")
        krversand_data = []

        for dispatch in dispatchs:
            # Get the date of the dispatch
            krversand_date = arrow.get(
                dispatch.Datum.contents[-1].text,
                ["YYYY-MM-DD", "DD.MM.YYYY", "YYYYMMDD"],
            )

            # Skip if the entry already exists
            if krversand_date in stored_mails:
                continue

            # Get all affairs from the dispatch, find_all is case sensitive
            affairs = [
                geschaeft
                for geschaeft in dispatch.find_all("Geschaeft")
                if geschaeft.find("Geschaeft") is not None
            ]

            entries = []
            # Loop through all affairs
            for affair in affairs:
                affair_type = affair.Geschaeftsart.text
                title = affair.Titel.text
                position = affair.parent
                # Get OBJ_GUID of affair
                affair_guid = affair.next.attrs["OBJ_GUID"]
                # Get the vorlage_nr
                vorlage_nr = affair.VorlagenNr.text
                # Get the KRNr
                kr_nr = affair.KRNr.text
                # Get the last document and its last version
                documents = position.find_all("Dokument")
                try:
                    last_document = documents[0]
                    edoc_id = last_document.eDocument["ID"]
                    versions = last_document.find_all("Version")
                    last_version = versions[-1]["Nr"]
                except Exception as e:
                    logging.error(f"Error getting edoc_id or last_version: {e}")
                    continue

                # Construct the pdf url
                krzh_pdf_url = f"https://parlzhcdws.cmicloud.ch/parlzh1/cdws/Files/{edoc_id}/{last_version}/pdf"

                # Construct the url from affair_guid
                krzh_affair_url = f"https://www.kantonsrat.zh.ch/geschaefte/geschaeft/?id={affair_guid}"

                ablaufschritte = get_ablaufschritte(kr_nr, vorlage_nr)

                # Sort the ablaufschritte by decreasing date
                ablaufschritte.sort(key=lambda x: x["affair_step_date"], reverse=True)

                # Append the data to the entries list
                data = {
                    "title": title,
                    "affair_type": affair_type,
                    "krzh_pdf_url": krzh_pdf_url,
                    "pdf_orientation": "",
                    "vorlagen_nr": vorlage_nr,
                    "kr_nr": kr_nr,
                    "affair_guid": affair_guid,
                    "krzh_affair_url": krzh_affair_url,
                    "affair_nr": "",
                    "affair_steps": ablaufschritte,
                    "changes": {},
                }
                entries.append(data)

            # Append the data to the krversand_data list
            krversand_dict = {
                "krzh_dispatch_date": krversand_date.format("YYYYMMDD"),
                "affairs": entries,
            }
            krversand_data.append(krversand_dict)

        # Sort the data by decreasing date
        krversand_data.sort(key=lambda x: x["krzh_dispatch_date"], reverse=True)

        # Prepend the new data to the existing data
        for item in reversed(krversand_data):
            existing_data.insert(0, item)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=4, ensure_ascii=False)

    try:
        response = requests.get(URLs.KRZH_VERSAND_API, params=params_dispatch)
        sleep(APIConfig.WEB_REQUEST_DELAY)
        if response.status_code == 200:
            logging.info(f"API call successful. Parsing and downloading PDFs.")
            parse_and_download(response.content)
        else:
            logging.error(f"API call failed with status code {response.status_code}")
    except Exception as e:
        logging.error(f"Error during API call: {e}\n{traceback.format_exc()}")


if __name__ == "__main__":
    main()
