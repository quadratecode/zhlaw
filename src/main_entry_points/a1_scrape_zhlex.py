#!/usr/bin/env python3
"""
ZH-Lex Scraping Pipeline - Main Entry Point

This module orchestrates the complete ZH-Lex law scraping and processing pipeline:
1. Scrapes law metadata from the ZH website
2. Downloads PDF files for each law
3. Processes PDFs (cropping, text extraction)
4. Updates metadata with processing information
5. Exports data to CSV format

Usage:
    python -m src.cmd.a1_scrape_zhlex_main

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

from typing import List, Dict, Any, Optional
import arrow
import glob
import json
from tqdm import tqdm
from pathlib import Path

# Import custom modules
from src.modules.general_module import call_adobe_api
from src.modules.law_pdf_module import crop_pdf
from src.modules.zhlex_module import (
    scrape_collection,
    download_collection,
    update_metadata
)
from src.modules.dataset_generator_module import convert_csv

# Import configuration and error handling
from src.config import DataPaths, FilePatterns, ProcessingSteps, DateFormats
from src.constants import RESET_DATE_COMMENT
from src.logging_config import setup_logging, get_logger, OperationLogger
from src.exceptions import (
    FileProcessingException, JSONParsingException, QuotaExceededException,
    PDFProcessingException, MetadataException
)
from src.types import MetadataDocument, ProcessingResult

# Set up logging
setup_logging()
logger = get_logger(__name__)


def process_single_pdf(
    pdf_file: str,
    timestamp: str,
    op_logger: OperationLogger
) -> ProcessingResult:
    """
    Process a single PDF file through all pipeline steps.
    
    Args:
        pdf_file: Path to the original PDF file
        timestamp: Current timestamp for tracking
        op_logger: Operation logger instance
        
    Returns:
        ProcessingResult with success status and any error information
        
    Raises:
        QuotaExceededException: If API quota is exceeded (propagated to stop processing)
    """
    pdf_path = Path(pdf_file)
    
    # Generate all related file paths
    file_paths = {
        'original': pdf_file,
        'modified': pdf_file.replace(FilePatterns.ORIGINAL_PDF, FilePatterns.MODIFIED_PDF),
        'marginalia': pdf_file.replace(FilePatterns.ORIGINAL_PDF, FilePatterns.MARGINALIA_PDF),
        'metadata': pdf_file.replace(FilePatterns.ORIGINAL_PDF, FilePatterns.METADATA_JSON)
    }
    
    try:
        # Load metadata
        metadata = _load_metadata(file_paths['metadata'], pdf_path.name)
        if metadata is None:
            return ProcessingResult(
                success=False,
                message=f"Metadata not found for {pdf_path.name}",
                data=None,
                error="FileNotFoundError",
                processing_time=None
            )
        
        # Process each step if not already completed
        steps_completed = []
        
        # Step 1: Crop PDF
        if _process_crop_pdf(metadata, file_paths, timestamp, pdf_path):
            steps_completed.append(ProcessingSteps.CROP_PDF)
        
        # Step 2: Extract text from main PDF
        if _process_extract_law(metadata, file_paths, timestamp, pdf_path):
            steps_completed.append(ProcessingSteps.CALL_API_LAW)
        
        # Step 3: Extract text from marginalia PDF
        if _process_extract_marginalia(metadata, file_paths, timestamp, pdf_path):
            steps_completed.append(ProcessingSteps.CALL_API_MARGINALIA)
        
        # Save updated metadata if any steps were completed
        if steps_completed:
            _save_metadata(file_paths['metadata'], metadata, pdf_path)
        
        return ProcessingResult(
            success=True,
            message=f"Successfully processed {pdf_path.name}",
            data={'steps_completed': steps_completed},
            error=None,
            processing_time=None
        )
        
    except QuotaExceededException:
        # Re-raise quota exceptions to stop processing
        raise
        
    except (FileProcessingException, JSONParsingException, 
            PDFProcessingException, MetadataException) as e:
        op_logger.log_error(f"Error processing {pdf_path.name}: {e}")
        return ProcessingResult(
            success=False,
            message=f"Failed to process {pdf_path.name}",
            data=None,
            error=str(e),
            processing_time=None
        )
        
    except Exception as e:
        # Unexpected error
        op_logger.log_error(f"Unexpected error processing {pdf_path.name}: {e}")
        logger.exception(f"Unexpected error for file: {pdf_file}")
        return ProcessingResult(
            success=False,
            message=f"Unexpected error processing {pdf_path.name}",
            data=None,
            error=f"{type(e).__name__}: {str(e)}",
            processing_time=None
        )


def _load_metadata(metadata_file: str, pdf_name: str) -> Optional[MetadataDocument]:
    """Load metadata from JSON file with error handling."""
    try:
        with open(metadata_file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"Metadata file not found for {pdf_name}, skipping")
        return None
    except json.JSONDecodeError as e:
        raise JSONParsingException(metadata_file, e)


def _save_metadata(metadata_file: str, metadata: MetadataDocument, pdf_path: Path) -> None:
    """Save metadata to JSON file with error handling."""
    try:
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=4, ensure_ascii=False)
    except Exception as e:
        raise MetadataException("save", Path(metadata_file), {"error": str(e)})


def _process_crop_pdf(
    metadata: MetadataDocument,
    file_paths: Dict[str, str],
    timestamp: str,
    pdf_path: Path
) -> bool:
    """Process PDF cropping step if not already completed."""
    if metadata["process_steps"].get(ProcessingSteps.CROP_PDF, "") == "":
        try:
            logger.debug(f"Cropping PDF: {pdf_path.name}")
            crop_pdf.main(
                file_paths['original'],
                file_paths['modified'],
                file_paths['marginalia']
            )
            metadata["process_steps"][ProcessingSteps.CROP_PDF] = timestamp
            logger.info(f"Successfully cropped PDF: {pdf_path.name}")
            return True
        except Exception as e:
            raise PDFProcessingException(pdf_path, "crop", e)
    return False


def _process_extract_law(
    metadata: MetadataDocument,
    file_paths: Dict[str, str],
    timestamp: str,
    pdf_path: Path
) -> bool:
    """Process law text extraction step if not already completed."""
    if metadata["process_steps"].get(ProcessingSteps.CALL_API_LAW, "") == "":
        try:
            logger.debug(f"Extracting text from law PDF: {pdf_path.name}")
            call_adobe_api.main(file_paths['modified'], file_paths['original'])
            metadata["process_steps"][ProcessingSteps.CALL_API_LAW] = timestamp
            logger.info(f"Successfully extracted text from law PDF: {pdf_path.name}")
            return True
        except Exception as e:
            if "quota" in str(e).lower():
                raise QuotaExceededException("Adobe API", {"file": pdf_path.name})
            raise PDFProcessingException(pdf_path, "extract text (law)", e)
    return False


def _process_extract_marginalia(
    metadata: MetadataDocument,
    file_paths: Dict[str, str],
    timestamp: str,
    pdf_path: Path
) -> bool:
    """Process marginalia text extraction step if not already completed."""
    if metadata["process_steps"].get(ProcessingSteps.CALL_API_MARGINALIA, "") == "":
        try:
            logger.debug(f"Extracting text from marginalia PDF: {pdf_path.name}")
            call_adobe_api.main(file_paths['marginalia'], file_paths['original'])
            metadata["process_steps"][ProcessingSteps.CALL_API_MARGINALIA] = timestamp
            logger.info(f"Successfully extracted text from marginalia PDF: {pdf_path.name}")
            return True
        except Exception as e:
            if "quota" in str(e).lower():
                raise QuotaExceededException("Adobe API", {"file": pdf_path.name})
            raise PDFProcessingException(pdf_path, "extract text (marginalia)", e)
    return False


def main() -> None:
    """
    Main entry point for the ZH-Lex scraping pipeline.
    
    Orchestrates the complete process of scraping, downloading, and processing
    ZH-Lex law documents. Tracks errors and provides detailed logging.
    """
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
            try:
                result = process_single_pdf(pdf_file, timestamp, op_logger)
                if result['success']:
                    steps = result.get('data', {}).get('steps_completed', [])
                    if steps:
                        logger.debug(f"Completed steps for {Path(pdf_file).name}: {steps}")
                else:
                    error_counter += 1
                    
            except QuotaExceededException as e:
                op_logger.log_error(f"API quota exceeded: {e}")
                logger.error("Stopping processing due to quota limit")
                break

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
