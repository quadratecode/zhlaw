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

# Import configuration and error handling
from src.config import DataPaths, LogConfig, FilePatterns, ProcessingSteps, DateFormats
from src.constants import Messages, RESET_DATE_COMMENT
from src.logging_config import setup_logging, get_logger, OperationLogger
from src.exceptions import (
    FileProcessingException, JSONParsingException, QuotaExceededException,
    PDFProcessingException, MetadataException
)

# Import external modules
import arrow
import glob
import json
from tqdm import tqdm
from pathlib import Path

# Set up logging using the new centralized system
setup_logging()


def main():
    # Get logger for this module
    logger = get_logger(__name__)
    
    # Initialize error counter
    error_counter = 0

    # Timestamp
    timestamp = arrow.now().format(DateFormats.TIMESTAMP)

    # Use operation logger for the entire scraping process
    with OperationLogger("ZH-Lex Scraping Pipeline") as op_logger:
        # Scrape laws from website
        try:
            op_logger.log_info("Starting scraping laws from ZH website")
            scrape_collection.main(str(DataPaths.ZHLEX_DATA))
            op_logger.log_info("Finished scraping laws")
        except Exception as e:
            op_logger.log_error(f"Failed to scrape laws: {e}")
            raise

        # Download law files
        try:
            op_logger.log_info("Starting downloading law files")
            download_collection.main(str(DataPaths.ZHLEX_FILES))
            op_logger.log_info("Finished downloading laws")
        except Exception as e:
            op_logger.log_error(f"Failed to download laws: {e}")
            raise

        # Load and process PDF files
        op_logger.log_info("Loading laws index")
        pdf_pattern = str(DataPaths.ZHLEX_FILES / "**" / "**" / f"*{FilePatterns.ORIGINAL_PDF}")
        pdf_files = glob.glob(pdf_pattern, recursive=True)
        # Remove duplicates found from different junctions
        pdf_files = list(set(pdf_files))
        if not pdf_files:
            op_logger.log_warning("No PDF files found. Exiting.")
            return
        
        op_logger.log_info(f"Found {len(pdf_files)} PDF files to process")

        # Process each PDF file
        for pdf_file in tqdm(pdf_files, desc="Processing PDFs"):
            pdf_path = Path(pdf_file)
            original_pdf_path = pdf_file
            modified_pdf_path = pdf_file.replace(FilePatterns.ORIGINAL_PDF, FilePatterns.MODIFIED_PDF)
            marginalia_pdf_path = pdf_file.replace(FilePatterns.ORIGINAL_PDF, FilePatterns.MARGINALIA_PDF)
            metadata_file = pdf_file.replace(FilePatterns.ORIGINAL_PDF, FilePatterns.METADATA_JSON)

            try:
                # Load metadata
                try:
                    with open(metadata_file, "r") as f:
                        metadata = json.load(f)
                except FileNotFoundError:
                    logger.warning(f"Metadata file not found for {pdf_path.name}, skipping")
                    continue
                except json.JSONDecodeError as e:
                    raise JSONParsingException(metadata_file, e)

                # Process PDF cropping if not done
                if metadata["process_steps"].get(ProcessingSteps.CROP_PDF, "") == "":
                    try:
                        logger.debug(f"Cropping PDF: {pdf_path.name}")
                        crop_pdf.main(original_pdf_path, modified_pdf_path, marginalia_pdf_path)
                        metadata["process_steps"][ProcessingSteps.CROP_PDF] = timestamp
                        logger.info(f"Successfully cropped PDF: {pdf_path.name}")
                    except Exception as e:
                        raise PDFProcessingException(pdf_path, "crop", e)

                # Extract text from main PDF if not done
                if metadata["process_steps"].get(ProcessingSteps.CALL_API_LAW, "") == "":
                    try:
                        logger.debug(f"Extracting text from law PDF: {pdf_path.name}")
                        call_adobe_api.main(modified_pdf_path, pdf_file)
                        metadata["process_steps"][ProcessingSteps.CALL_API_LAW] = timestamp
                        logger.info(f"Successfully extracted text from law PDF: {pdf_path.name}")
                    except Exception as e:
                        if "quota" in str(e).lower():
                            raise QuotaExceededException("Adobe API", {"file": pdf_path.name})
                        raise PDFProcessingException(pdf_path, "extract text (law)", e)

                # Extract text from marginalia PDF if not done
                if metadata["process_steps"].get(ProcessingSteps.CALL_API_MARGINALIA, "") == "":
                    try:
                        logger.debug(f"Extracting text from marginalia PDF: {pdf_path.name}")
                        call_adobe_api.main(marginalia_pdf_path, pdf_file)
                        metadata["process_steps"][ProcessingSteps.CALL_API_MARGINALIA] = timestamp
                        logger.info(f"Successfully extracted text from marginalia PDF: {pdf_path.name}")
                    except Exception as e:
                        if "quota" in str(e).lower():
                            raise QuotaExceededException("Adobe API", {"file": pdf_path.name})
                        raise PDFProcessingException(pdf_path, "extract text (marginalia)", e)

                # Save the updated metadata
                try:
                    with open(metadata_file, "w") as f:
                        json.dump(metadata, f, indent=4, ensure_ascii=False)
                except Exception as e:
                    raise MetadataException("save", Path(metadata_file), {"error": str(e)})

            except QuotaExceededException as e:
                op_logger.log_error(f"API quota exceeded: {e}")
                logger.error(f"Stopping processing due to quota limit")
                break
                
            except (FileProcessingException, JSONParsingException, PDFProcessingException, MetadataException) as e:
                op_logger.log_error(f"Error processing {pdf_path.name}: {e}")
                error_counter += 1
                continue
                
            except Exception as e:
                # Unexpected error
                op_logger.log_error(f"Unexpected error processing {pdf_path.name}: {e}")
                logger.exception(f"Unexpected error for file: {pdf_file}")
                error_counter += 1
                continue

        # Update source metadata for all laws
        processed_data = str(DataPaths.ZHLEX_DATA / "zhlex_data_processed.json")
        try:
            op_logger.log_info("Updating metadata for all laws")
            update_metadata.main(str(DataPaths.ZHLEX_FILES), processed_data)
            op_logger.log_info("Finished updating metadata for all laws")
        except Exception as e:
            op_logger.log_error(f"Failed to update metadata: {e}")
            raise

        # Save relevant keys from processed data to CSV
        try:
            op_logger.log_info("Saving processed data to CSV")
            convert_csv.main(processed_data)
            op_logger.log_info("Finished saving processed data to CSV")
        except Exception as e:
            op_logger.log_error(f"Failed to convert to CSV: {e}")
            raise

        # Log final summary
        if error_counter > 0:
            op_logger.log_warning(f"Completed with {error_counter} errors")
        else:
            op_logger.log_info("Completed successfully with no errors")


if __name__ == "__main__":
    main()
