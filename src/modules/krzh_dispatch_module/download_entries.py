# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

import os
import requests
import json
import arrow
import logging
import time

# Configure logging
logger = logging.getLogger(__name__)

timestamp = arrow.now().format("YYYYMMDD-HHmmss")


def download_dispatch_text(url, dispatch_dir, file_name):
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()

        # Save the file
        with open(dispatch_dir, "wb") as file:
            file.write(response.content)

        return timestamp, file_name
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return False, None


def create_metadata_file(metadata, file_path):
    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=4, ensure_ascii=False)


def main(folder):
    with open(
        os.path.join(folder, "krzh_dispatch_data.json"), "r", encoding="utf-8"
    ) as file:
        krversand_data = json.load(file)

    # Download all krzh PDFs in krzh_dispatch_date -> affairs -> krzh_pdf_url
    for krversand in krversand_data:
        for affair in krversand["affairs"]:
            krzh_pdf_url = affair["krzh_pdf_url"]
            kr_nr = affair["kr_nr"]
            vorlagen_nr = affair["vorlagen_nr"]
            # Get most recent affair_step
            if affair["affair_steps"]:
                affair_steps = affair["affair_steps"]
                last_affair_step_type = affair_steps[0]["affair_step_type"]
                last_affair_step_date = affair_steps[0]["affair_step_date"]
            else:
                affair_steps = ""
                last_affair_step_type = ""
                last_affair_step_date = ""
            krzh_dispatch_date = krversand["krzh_dispatch_date"]

            # Check if kr_nr is an empty string or None
            if not kr_nr:
                affair_nr = vorlagen_nr
            else:
                affair_nr = kr_nr

            # Replace "/" in affair_nr with "-"
            affair_nr = affair_nr.replace("/", ".")

            # Point to files subdirectory
            krzh_pdf_dir = os.path.join(
                "data/krzh_dispatch/krzh_dispatch_files",
                krzh_dispatch_date,
                affair_nr,
            )
            os.makedirs(krzh_pdf_dir, exist_ok=True)

            # Build file name
            file_name = (
                str(krzh_dispatch_date) + "-" + str(affair_nr) + "-original" + ".pdf"
            )
            file_path = os.path.join(krzh_pdf_dir, file_name)

            # Check if file already exists
            if not os.path.exists(file_path):
                # Logging
                logger.info(f"Downloading {krzh_pdf_url} to {file_path}")
                success, file_name = download_dispatch_text(
                    krzh_pdf_url, file_path, file_name
                )
                time.sleep(1)

                metadata = {
                    "doc_info": {
                        "erlasstitel": affair["title"],
                        "krzh_dispatch_date": krzh_dispatch_date,
                        "affair_type": affair["affair_type"],
                        "affair_nr": affair_nr,
                        "affair_guid": affair["affair_guid"],
                        "last_affair_step_date": last_affair_step_date,
                        "last_affair_step_type": last_affair_step_type,
                        "pdf_url": krzh_pdf_url,
                        "regex_changes": {},
                        "ai_changes": {},
                    },
                    "process_steps": {
                        "scrape_dispatch": success,
                        "call_ai": "",
                    },
                }

                # Replace file ending (*-original.html or *-original.pdf) with -metadata.json
                metadata_file_path = file_path.replace(
                    "-original.html", "-metadata.json"
                ).replace("-original.pdf", "-metadata.json")

                create_metadata_file(metadata, metadata_file_path)


if __name__ == "__main__":
    main()
