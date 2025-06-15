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

# Import configuration
from src.config import DataPaths, LogConfig, FilePatterns, ProcessingSteps, DateFormats
from src.constants import Messages, RESET_DATE_COMMENT

# Import external modules
import arrow
import logging
import glob
import json
from tqdm import tqdm
from pathlib import Path

# Set up logging
logging.basicConfig(
    filename=str(LogConfig.LOG_FILE),
    level=logging.INFO,
    format=LogConfig.LOG_FORMAT,
    datefmt=LogConfig.LOG_DATE_FORMAT,
)


def main():

    # Initialize error counter
    error_counter = 0

    # Timestamp
    timestamp = arrow.now().format(DateFormats.TIMESTAMP)

    logging.info("Starting scraping laws")
    scrape_collection.main(str(DataPaths.ZHLEX_DATA))
    logging.info("Finished scraping laws")

    logging.info("Starting downloading laws")
    download_collection.main(str(DataPaths.ZHLEX_FILES))
    logging.info("Finished downloading laws")

    logging.info("Loading laws index")
    pdf_pattern = str(DataPaths.ZHLEX_FILES / "**" / "**" / f"*{FilePatterns.ORIGINAL_PDF}")
    pdf_files = glob.glob(pdf_pattern, recursive=True)
    # Remove duplicates found from different junctions
    pdf_files = list(set(pdf_files))
    if not pdf_files:
        logging.info("No PDF files found. Exiting.")
        return

    for pdf_file in tqdm(pdf_files):
        original_pdf_path = pdf_file
        modified_pdf_path = pdf_file.replace(FilePatterns.ORIGINAL_PDF, FilePatterns.MODIFIED_PDF)
        marginalia_pdf_path = pdf_file.replace(FilePatterns.ORIGINAL_PDF, FilePatterns.MARGINALIA_PDF)
        metadata_file = pdf_file.replace(FilePatterns.ORIGINAL_PDF, FilePatterns.METADATA_JSON)

        try:
            with open(metadata_file, "r") as f:
                metadata = json.load(f)

            # TODO: Replacing this by checking for the existence of files instead would be more robust
            # However, there are downstream dependencies (all operations with "doc_info")
            # Note: RESET_DATE_COMMENT
            if metadata["process_steps"][ProcessingSteps.CROP_PDF] == "":
                logging.info(f"Cropping PDF: {pdf_file}")
                crop_pdf.main(original_pdf_path, modified_pdf_path, marginalia_pdf_path)
                logging.info(f"Finished cropping PDF: {pdf_file}")
                metadata["process_steps"][ProcessingSteps.CROP_PDF] = timestamp

            if metadata["process_steps"][ProcessingSteps.CALL_API_LAW] == "":
                logging.info(f"Extracting text law: {pdf_file}")
                call_adobe_api.main(modified_pdf_path, pdf_file)
                logging.info(f"Finished extracting text law: {pdf_file}")
                metadata["process_steps"][ProcessingSteps.CALL_API_LAW] = timestamp

            if metadata["process_steps"][ProcessingSteps.CALL_API_MARGINALIA] == "":
                logging.info(f"Extracting text marginalia: {pdf_file}")
                call_adobe_api.main(marginalia_pdf_path, pdf_file)
                logging.info(f"Finished extracting text marginalia: {pdf_file}")
                metadata["process_steps"][ProcessingSteps.CALL_API_MARGINALIA] = timestamp

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
    processed_data = str(DataPaths.ZHLEX_DATA / "zhlex_data_processed.json")
    logging.info("Updating metadata for all laws")
    update_metadata.main(str(DataPaths.ZHLEX_FILES), processed_data)
    logging.info("Finished updating metadata for all laws")

    # Save relevant keys from processed data to CSV
    logging.info("Saving processed data to CSV")
    convert_csv.main(processed_data)
    logging.info("Finished saving processed data to CSV")

    logging.info(f"Finished scraping laws with {error_counter} errors")


if __name__ == "__main__":
    main()
