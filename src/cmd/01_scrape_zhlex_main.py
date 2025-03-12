# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

# Import custom modules
from src.modules.general_module import call_adobe_api

from src.modules.law_pdf_module import crop_pdf

from src.modules.zhlex_module import scrape_collection
from src.modules.zhlex_module import download_collection
from src.modules.zhlex_module import update_metadata
from src.modules.dataset_generator_module import convert_csv

# Import external modules
import arrow
import logging
import glob
import json
from tqdm import tqdm

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

    logging.info("Starting scraping laws")
    scrape_collection.main("data/zhlex/zhlex_data")
    logging.info("Finished scraping laws")

    logging.info("Starting downloading laws")
    download_collection.main("data/zhlex/zhlex_files")
    logging.info("Finished downloading laws")

    logging.info("Loading laws index")
    pdf_files = glob.glob("data/zhlex/zhlex_files/**/**/*-original.pdf", recursive=True)
    # Remove duplicates found from different junctions
    pdf_files = list(set(pdf_files))
    if not pdf_files:
        logging.info("No PDF files found. Exiting.")
        return

    for pdf_file in tqdm(pdf_files):
        original_pdf_path = pdf_file
        modified_pdf_path = pdf_file.replace("-original.pdf", "-modified.pdf")
        marginalia_pdf_path = pdf_file.replace("-original.pdf", "-marginalia.pdf")
        metadata_file = pdf_file.replace("-original.pdf", "-metadata.json")

        try:
            with open(metadata_file, "r") as f:
                metadata = json.load(f)

            # TODO: Replacing this by checking for the existence of files instead would be more robust
            # However, there are downstream dependencies (all operations with "doc_info")
            # Due to inocorrect operation on live data, all timestamps before 20250308 have been set reset to this date
            if metadata["process_steps"]["crop_pdf"] == "":
                logging.info(f"Cropping PDF: {pdf_file}")
                crop_pdf.main(original_pdf_path, modified_pdf_path, marginalia_pdf_path)
                logging.info(f"Finished cropping PDF: {pdf_file}")
                metadata["process_steps"]["crop_pdf"] = timestamp

            if metadata["process_steps"]["call_api_law"] == "":
                logging.info(f"Extracting text law: {pdf_file}")
                call_adobe_api.main(modified_pdf_path, pdf_file)
                logging.info(f"Finished extracting text law: {pdf_file}")
                metadata["process_steps"]["call_api_law"] = timestamp

            if metadata["process_steps"]["call_api_marginalia"] == "":
                logging.info(f"Extracting text marginalia: {pdf_file}")
                call_adobe_api.main(marginalia_pdf_path, pdf_file)
                logging.info(f"Finished extracting text marginalia: {pdf_file}")
                metadata["process_steps"]["call_api_marginalia"] = timestamp

            # Save the updated metadata
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=4, ensure_ascii=False)

        except Exception as e:
            # Break if error occured in adobe api module (likely: limiit reached)
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

    # Update source metadata for all laws
    processed_data = "data/zhlex/zhlex_data/zhlex_data_processed.json"
    logging.info("Updating metadata for all laws")
    update_metadata.main("data/zhlex/zhlex_files", processed_data)
    logging.info("Finished updating metadata for all laws")

    # Save relevant keys from processed data to CSV
    logging.info("Saving processed data to CSV")
    convert_csv.main(processed_data)
    logging.info("Finished saving processed data to CSV")

    logging.info(f"Finished scraping laws with {error_counter} errors")


if __name__ == "__main__":
    main()
