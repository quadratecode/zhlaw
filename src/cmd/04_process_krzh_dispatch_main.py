# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

# Import custom modules
from src.modules.krzh_dispatch_module import scrape_dispatch
from src.modules.krzh_dispatch_module import download_entries
from src.modules.krzh_dispatch_module import call_openai_api
from src.modules.site_generator_module import build_zhlaw
from src.modules.site_generator_module import build_dispatch

# Import external modules
import arrow
import logging
import glob
import json
from tqdm import tqdm
from bs4 import BeautifulSoup
import shutil

# Set up logging
logging.basicConfig(
    filename="logs/process.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S %p",
)


def main():

    # Initialize error counter
    error_counter = 0

    # Timestamp
    timestamp = arrow.now().format("YYYYMMDD-HHmmss")

    logging.info("Starting scraping krzh dispatch")
    scrape_dispatch.main("data/krzh_dispatch/krzh_dispatch_data")
    logging.info("Finished scraping krzh dispatch")

    logging.info("Starting downloading krzh dispatch")
    download_entries.main("data/krzh_dispatch/krzh_dispatch_data")
    logging.info("Finished downloading krzh dispatch")

    logging.info("Loading krzh dispatch index")
    pdf_files = glob.glob(
        "data/krzh_dispatch/krzh_dispatch_files/**/**/*-original.pdf", recursive=True
    )
    # Remove duplicates found from different junctions
    pdf_files = list(set(pdf_files))
    if not pdf_files:
        logging.info("No PDF files found. Exiting.")
        return

    for pdf_file in tqdm(pdf_files):
        original_pdf_path = pdf_file
        metadata_file = pdf_file.replace("-original.pdf", "-metadata.json")

        try:
            with open(metadata_file, "r") as f:
                metadata = json.load(f)

            # Check if the affair type is one of the targeted types
            affair_type_lower = metadata["doc_info"]["affair_type"].lower()
            is_target_type = (
                "vorlage" in affair_type_lower
                or "einzelinitiative" in affair_type_lower
                or "behördeninitiative" in affair_type_lower
                or "parlamentarische initiative" in affair_type_lower
            )

            # Process only target types with OpenAI
            if is_target_type:
                try:
                    if (
                        metadata["process_steps"]["call_ai"] == ""
                        and metadata["doc_info"]["ai_changes"] != ""
                    ):
                        logging.info(f"Calling GPT Assistant: {pdf_file}")
                        call_openai_api.main(original_pdf_path, metadata)
                        logging.info(f"Finished calling GPT Assistant: {pdf_file}")
                        metadata["process_steps"]["call_ai"] = timestamp
                # Ignore error code 400
                except Exception as e:
                    if "400" in str(e):
                        logging.error(
                            f"Error during in {__file__}: {e} at {timestamp}",
                            exc_info=True,
                        )
                        metadata["doc_info"]["ai_changes"] = "{error: too many tokens}"
                        metadata["process_steps"]["call_ai"] = timestamp
                    else:
                        logging.error(
                            f"Error during in {__file__}: {e} at {timestamp}",
                            exc_info=True,
                        )
                        error_counter += 1
                        continue

            # Save the updated metadata
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=4, ensure_ascii=False)

            # Add certain metadata back to krzh_dispatch_data.json under the correct entry
            krzh_dispatch_data_path = (
                "data/krzh_dispatch/krzh_dispatch_data/krzh_dispatch_data.json"
            )
            with open(krzh_dispatch_data_path, "r") as f:
                krzh_dispatch_data = json.load(f)

            for krzh_dispatch in krzh_dispatch_data:
                if (
                    krzh_dispatch["krzh_dispatch_date"]
                    == metadata["doc_info"]["krzh_dispatch_date"]
                ):
                    for affair in krzh_dispatch["affairs"]:
                        if (
                            affair["vorlagen_nr"] == metadata["doc_info"]["affair_nr"]
                            or affair["kr_nr"].replace("/", ".")
                            == metadata["doc_info"]["affair_nr"]
                        ):
                            affair["affair_nr"] = metadata["doc_info"]["affair_nr"]
                            # Add changes if key exists
                            if "changes" in metadata["doc_info"]:
                                affair["changes"] = metadata["doc_info"]["changes"]
                            if "ai_changes" in metadata["doc_info"]:
                                affair["ai_changes"] = metadata["doc_info"][
                                    "ai_changes"
                                ]
                            break

            with open(krzh_dispatch_data_path, "w") as f:
                json.dump(krzh_dispatch_data, f, indent=4, ensure_ascii=False)

        except Exception as e:
            # Break if error occurred in adobe api module
            if "quota" in str(e):
                logging.error(
                    f"Error during in {__file__}: {e} at {timestamp}", exc_info=True
                )
                break

            # Else, continue with next file
            else:
                logging.error(
                    f"Error during in {__file__}: {e} at {timestamp}", exc_info=True
                )
                error_counter += 1
                continue

    logging.info(f"Finished scraping krzh dispatch with {str(error_counter)} errors")

    # Build page from kzrh_dispatch_data.json
    logging.info("Building page")
    html_file_path = "data/krzh_dispatch/krzh_dispatch_site/dispatch.html"
    logging.info(f"Starting page build")
    with open(krzh_dispatch_data_path, "r") as f:
        krzh_dispatch_data = json.load(f)

    # Build core of dispatch page
    with open(html_file_path, "w") as f:
        f.write(build_dispatch.main(krzh_dispatch_data))

    # Process the HTML with BeautifulSoup and additional functions
    with open(html_file_path, "r") as file:
        soup = BeautifulSoup(file, "html.parser")

    soup = build_zhlaw.insert_header(soup)
    soup = build_zhlaw.insert_footer(soup)

    # Write the modified HTML back to the file
    with open(html_file_path, "w") as f:
        f.write(str(soup))
    logging.info("Finished page build")

    # Copy html file to public
    logging.info("Copying html file to public")
    shutil.copy(html_file_path, "public/dispatch.html")


if __name__ == "__main__":
    main()
