"""
Module for extracting text and structure from PDF files using Adobe Extract API.

This module provides functionality to:
- Set up Adobe API credentials
- Extract text, tables, and structural elements from PDFs
- Convert extracted data to JSON format
- Handle API quotas and errors gracefully

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import os
import zipfile
import json
import shutil
from pathlib import Path
from adobe.pdfservices.operation.auth.credentials import Credentials
from adobe.pdfservices.operation.execution_context import ExecutionContext
from adobe.pdfservices.operation.io.file_ref import FileRef
from adobe.pdfservices.operation.pdfops.extract_pdf_operation import ExtractPDFOperation
from adobe.pdfservices.operation.pdfops.options.extractpdf.extract_pdf_options import (
    ExtractPDFOptions,
)
from adobe.pdfservices.operation.pdfops.options.extractpdf.extract_element_type import (
    ExtractElementType,
)
from adobe.pdfservices.operation.pdfops.options.extractpdf.extract_renditions_element_type import (
    ExtractRenditionsElementType,
)
from adobe.pdfservices.operation.pdfops.options.extractpdf.table_structure_type import (
    TableStructureType,
)

# Import configuration and error handling
from src.config import Environment
from src.constants import Messages
from src.logging_config import get_logger
from src.exceptions import (
    AdobeAPIException, FileProcessingException, 
    MissingCredentialsException, QuotaExceededException
)

# Get logger for this module
from src.utils.logging_utils import get_module_logger
logger = get_module_logger(__name__)


def setup_adobe_credentials(credentials_file):
    """Set up Adobe API credentials from file."""
    try:
        with open(credentials_file, "r") as file:
            credentials_data = json.load(file)
    except FileNotFoundError:
        raise MissingCredentialsException("Adobe API", {
            "file": credentials_file,
            "message": "Credentials file not found. Please ensure credentials.json exists."
        })
    except json.JSONDecodeError as e:
        raise AdobeAPIException("parse credentials", {
            "file": credentials_file,
            "error": str(e)
        })
    
    try:
        client_id = credentials_data["client_credentials"]["client_id"]
        client_secret = credentials_data["client_credentials"]["client_secret"]
    except KeyError as e:
        raise AdobeAPIException("read credentials", {
            "missing_field": str(e),
            "message": "Invalid credentials file format"
        })

    credentials = (
        Credentials.service_principal_credentials_builder()
        .with_client_id(client_id)
        .with_client_secret(client_secret)
        .build()
    )
    return ExecutionContext.create(credentials)


def extract_pdf_to_json(pdf_path, output_zip):
    """Extract text and structure from PDF using Adobe API."""
    credentials_path = str(Environment.get_adobe_credentials_path())
    
    try:
        execution_context = setup_adobe_credentials(credentials_path)
    except Exception as e:
        logger.error(f"Failed to set up Adobe credentials: {e}")
        raise
    
    try:
        extract_pdf_operation = ExtractPDFOperation.create_new()
        source = FileRef.create_from_local_file(pdf_path)
        extract_pdf_operation.set_input(source)
        
        extract_pdf_options = (
            ExtractPDFOptions.builder()
            .with_element_to_extract(ExtractElementType.TABLES)
            .with_table_structure_format(TableStructureType.CSV)
            .with_element_to_extract(ExtractElementType.TEXT)
            .with_get_char_info(True)
            .with_include_styling_info(True)
            .build()
        )
        extract_pdf_operation.set_options(extract_pdf_options)
        
        logger.debug(f"Executing Adobe API extraction for: {pdf_path}")
        result = extract_pdf_operation.execute(execution_context)
        result.save_as(output_zip)
        
        return output_zip
        
    except Exception as e:
        # Check for quota exceeded error
        error_msg = str(e).lower()
        if "quota" in error_msg or "limit" in error_msg or "exceeded" in error_msg:
            raise QuotaExceededException("Adobe API", {
                "file": pdf_path,
                "error": str(e)
            })
        
        # Other Adobe API errors
        raise AdobeAPIException("extract PDF", {
            "file": pdf_path,
            "error": str(e),
            "error_type": type(e).__name__
        })


def parse_extracted_data(zip_file, output_folder):
    try:
        # Extract the zip file
        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            zip_ref.extractall(output_folder)
        # Rename the extracted json file
        json_file = zip_file.replace(".zip", ".json")
        os.rename(os.path.join(output_folder, "structuredData.json"), json_file)

        # If a tables folder exists, combine any csv files into one
        # Rename the combined csv file to the same name as the json file
        csv_file = zip_file.replace(".zip", ".csv")
        tables_folder = os.path.join(output_folder, "tables")
        if os.path.exists(tables_folder):
            csv_files = [
                os.path.join(tables_folder, f)
                for f in os.listdir(tables_folder)
                if f.endswith(".csv")
            ]
            with open(csv_file, "w") as outfile:
                for fname in csv_files:
                    with open(fname) as infile:
                        outfile.write(infile.read())
            # Remove the tables folder using shutil (safer than os.system)
            shutil.rmtree(tables_folder)

        logger.info(f"Processed and saved JSON data for {zip_file}")
    except FileNotFoundError as e:
        raise FileProcessingException(Path(zip_file), "extract zip", e)
    except Exception as e:
        raise FileProcessingException(Path(zip_file), "parse extracted data", e)


def main(pdf_path, original_pdf_file):
    """Main function to process a PDF file through Adobe API."""
    pdf_path_obj = Path(pdf_path)
    
    # Check if the json file already exists
    json_file = pdf_path.replace(".pdf", ".json")
    if os.path.exists(json_file):
        logger.info(f"JSON file already exists for {pdf_path_obj.name}, skipping")
        return

    zip_file = pdf_path.replace(".pdf", ".zip")
    
    try:
        # Extract text from the PDF
        logger.info(f"Starting Adobe API extraction for: {pdf_path_obj.name}")
        extract_pdf_to_json(pdf_path, zip_file)
        
        # Parse the extracted data, save to same folder
        logger.info(f"Parsing extracted data for: {pdf_path_obj.name}")
        parse_extracted_data(zip_file, os.path.dirname(original_pdf_file))
        
        logger.info(f"Successfully processed: {pdf_path_obj.name}")
        
    finally:
        # Always try to clean up the zip file
        if os.path.exists(zip_file):
            try:
                os.remove(zip_file)
                logger.debug(f"Cleaned up zip file: {zip_file}")
            except Exception as e:
                logger.warning(f"Failed to remove zip file {zip_file}: {e}")


if __name__ == "__main__":
    main()
