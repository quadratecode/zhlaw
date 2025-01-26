# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

# Import custom modules
from src.modules.krzh_dispatch_module import scrape_dispatch
from src.modules.krzh_dispatch_module import download_entries
from src.modules.krzh_dispatch_module import extract_changes

from src.modules.general_module import call_adobe_api
from src.modules.krzh_dispatch_module import call_openai_api
from src.modules.general_module import json_to_html
from src.modules.general_module import clean_html

from src.modules.law_pdf_module import crop_pdf
from src.modules.law_pdf_module import extend_metadata
from src.modules.law_pdf_module import merge_marginalia
from src.modules.law_pdf_module import match_marginalia
from src.modules.law_pdf_module import create_hyperlinks

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
    logging.info("Starting scraping krzh dispatch")

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
        json_file_dispatch_original = pdf_file.replace(
            "-original.pdf", "-original.json"
        )
        json_file_dispatch_modified = pdf_file.replace(
            "-original.pdf", "-modified.json"
        )
        json_file_dispatch_updated = pdf_file.replace("-original.pdf", "-updated.json")
        modified_pdf_path = pdf_file.replace("-original.pdf", "-modified.pdf")
        marginalia_pdf_path = pdf_file.replace("-original.pdf", "-marginalia.pdf")
        json_file_marginalia = pdf_file.replace("-original.pdf", "-marginalia.json")
        metadata_file = pdf_file.replace("-original.pdf", "-metadata.json")
        html_file_dispatch = pdf_file.replace("-original.pdf", "-modified.html")
        html_file_marginalia = pdf_file.replace("-original.pdf", "-marginalia.html")
        merged_html_dispatch = pdf_file.replace("-original.pdf", "-merged.html")
        csv_file = pdf_file.replace(".pdf", ".csv")

        try:
            with open(metadata_file, "r") as f:
                metadata = json.load(f)

            # Define type of document
            if (
                metadata["doc_info"]["pdf_orientation"] == "landscape"
                and metadata["doc_info"]["affair_type"] == "Vorlage"
            ):
                vorlage_type = "vorlage_landscape"
            elif (
                metadata["doc_info"]["pdf_orientation"] == "portrait"
                and metadata["doc_info"]["affair_type"] == "Vorlage"
            ):
                vorlage_type = "vorlage_portrait"
            else:
                vorlage_type = "not_vorlage"

            # Define process steps for document type
            if vorlage_type == "not_vorlage" or vorlage_type == "vorlage_landscape":
                if metadata["process_steps"]["call_api_dispatch"] == "":
                    logging.info(f"Extracting text dispatch: {pdf_file}")
                    call_adobe_api.main(original_pdf_path, pdf_file)
                    metadata["process_steps"]["call_api_dispatch"] = timestamp

                if metadata["process_steps"]["json_to_html_dispatch"] == "":
                    logging.info(f"Converting to HTML: {pdf_file}")
                    json_to_html.main(
                        json_file_dispatch_original,
                        metadata,
                        html_file_dispatch,
                        marginalia=False,
                    )
                    logging.info(f"Finished converting to HTML: {pdf_file}")
                    metadata["process_steps"]["json_to_html_dispatch"] = timestamp

                if metadata["process_steps"]["clean_data"] == "":
                    logging.info(f"Cleaning data: {pdf_file}")
                    clean_html.main(html_file_dispatch)
                    logging.info(f"Finished cleaning data: {pdf_file}")
                    metadata["process_steps"]["clean_data"] = timestamp

                if vorlage_type == "not_vorlage":
                    # Clean html, send to GPT Assistant
                    try:
                        if metadata["process_steps"]["call_ai"] == "":
                            logging.info(f"Calling GPT Assistant: {pdf_file}")
                            call_openai_api.main(html_file_dispatch, metadata)
                            logging.info(f"Finished calling GPT Assistant: {pdf_file}")
                            metadata["process_steps"]["call_ai"] = timestamp
                    # Ignore error code 400
                    except Exception as e:
                        if "400" in str(e):
                            logging.error(
                                f"Error during in {__file__}: {e} at {timestamp}",
                                exc_info=True,
                            )
                            metadata["doc_info"][
                                "ai_changes"
                            ] = "{error: too many tokens}"
                            metadata["process_steps"]["call_ai"] = timestamp
                        else:
                            logging.error(
                                f"Error during in {__file__}: {e} at {timestamp}",
                                exc_info=True,
                            )
                            error_counter += 1
                            continue

                if vorlage_type == "vorlage_landscape":
                    clean_html.main(html_file_dispatch)
                    # Here use csv instead
                    if metadata["process_steps"]["call_ai"] == "":
                        logging.info(f"Calling GPT Assistant: {pdf_file}")
                        call_openai_api.main(csv_file, metadata)
                        logging.info(f"Finished calling GPT Assistant: {pdf_file}")
                        metadata["process_steps"]["call_ai"] = timestamp

            if vorlage_type == "vorlage_portrait":
                if metadata["process_steps"]["crop_pdf"] == "":
                    logging.info(f"Cropping PDF: {pdf_file}")
                    crop_pdf.main(
                        original_pdf_path, modified_pdf_path, marginalia_pdf_path
                    )
                    logging.info(f"Finished cropping PDF: {pdf_file}")
                    metadata["process_steps"]["crop_pdf"] = timestamp

                if metadata["process_steps"]["call_api_dispatch"] == "":
                    logging.info(f"Extracting text dispatch: {pdf_file}")
                    call_adobe_api.main(modified_pdf_path, pdf_file)
                    logging.info(f"Finished extracting text dispatch: {pdf_file}")
                    metadata["process_steps"]["call_api_dispatch"] = timestamp

                if metadata["process_steps"]["call_api_marginalia"] == "":
                    logging.info(f"Extracting text marginalia: {pdf_file}")
                    call_adobe_api.main(marginalia_pdf_path, pdf_file)
                    logging.info(f"Finished extracting text marginalia: {pdf_file}")
                    metadata["process_steps"]["call_api_marginalia"] = timestamp

                if metadata["process_steps"]["extract_color"] == "":
                    logging.info(f"Extracting color: {pdf_file}")
                    extend_metadata.main(
                        original_pdf_path,
                        modified_pdf_path,
                        json_file_dispatch_modified,
                        json_file_dispatch_updated,
                    )
                    logging.info(f"Finished extracting color: {pdf_file}")
                    metadata["process_steps"]["extract_color"] = timestamp

                if metadata["process_steps"]["json_to_html_dispatch"] == "":
                    logging.info(f"Converting to HTML: {pdf_file}")
                    json_to_html.main(
                        json_file_dispatch_updated,
                        metadata,
                        html_file_dispatch,
                        marginalia=False,
                    )
                    logging.info(f"Finished converting to HTML: {pdf_file}")
                    metadata["process_steps"]["json_to_html_dispatch"] = timestamp

                if metadata["process_steps"]["json_to_html_marginalia"] == "":
                    logging.info(f"Converting to HTML: {pdf_file}")
                    json_to_html.main(
                        json_file_marginalia,
                        metadata,
                        html_file_marginalia,
                        marginalia=True,
                    )
                    logging.info(f"Finished converting to HTML: {pdf_file}")
                    metadata["process_steps"]["json_to_html_marginalia"] = timestamp

                if metadata["process_steps"]["merge_marginalia"] == "":
                    logging.info(f"Merging marginalia: {pdf_file}")
                    merge_marginalia.main(html_file_marginalia)
                    logging.info(f"Finished merging marginalia: {pdf_file}")
                    metadata["process_steps"]["merge_marginalia"] = timestamp

                if metadata["process_steps"]["match_marginalia"] == "":
                    logging.info(f"Matching marginalia: {pdf_file}")
                    match_marginalia.main(
                        html_file_dispatch, html_file_marginalia, merged_html_dispatch
                    )
                    logging.info(f"Finished matching marginalia: {pdf_file}")
                    metadata["process_steps"]["match_marginalia"] = timestamp

                if metadata["process_steps"]["match_footnotes_and_links"] == "":
                    logging.info(f"Matching footnotes and links: {pdf_file}")
                    create_hyperlinks.main(
                        merged_html_dispatch, json_file_dispatch_updated
                    )
                    logging.info(f"Finished matching footnotes and links: {pdf_file}")
                    metadata["process_steps"]["match_footnotes_and_links"] = timestamp

                if metadata["process_steps"]["extract_changes"] == "":
                    logging.info(f"Extracting changes: {pdf_file}")
                    extract_changes.main(merged_html_dispatch, metadata)
                    logging.info(f"Finished extracting changes: {pdf_file}")
                    metadata["process_steps"]["extract_changes"] = timestamp

                # Clean html
                if metadata["process_steps"]["clean_data"] == "":
                    logging.info(f"Cleaning data: {pdf_file}")
                    clean_html.main(merged_html_dispatch)
                    logging.info(f"Finished cleaning data: {pdf_file}")
                    metadata["process_steps"]["clean_data"] = timestamp

                if metadata["process_steps"]["call_ai"] == "":
                    try:
                        logging.info(f"Calling GPT Assistant: {pdf_file}")
                        call_openai_api.main(merged_html_dispatch, metadata)
                        logging.info(f"Finished calling GPT Assistant: {pdf_file}")
                        metadata["process_steps"]["call_ai"] = timestamp
                        # Ignore error code 400
                    except Exception as e:
                        if "400" in str(e):
                            logging.error(
                                f"Error during in {__file__}: {e} at {timestamp}",
                                exc_info=True,
                            )
                            metadata["doc_info"][
                                "ai_changes"
                            ] = "{error: too many tokens}"
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
            # An entry is correct if krzh_dispatch_date from both files are the same and
            # if the affair_nr from metadata corresponds to either vorlagen_nr or kr_nr from krzh_dispatch_data.json
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
                            or affair["kr_nr"].replace("/", "-")
                            == metadata["doc_info"]["affair_nr"]
                        ):
                            affair["pdf_orientation"] = metadata["doc_info"][
                                "pdf_orientation"
                            ]
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
            # Break if error occured in adobe api module
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
