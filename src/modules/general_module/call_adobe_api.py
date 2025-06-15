# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

import os
import zipfile
import json
import logging
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

# Import configuration
from src.config import Environment
from src.constants import Messages

# Get logger from main module
logger = logging.getLogger(__name__)


def setup_adobe_credentials(credentials_file):
    with open(credentials_file, "r") as file:
        credentials_data = json.load(file)
    client_id = credentials_data["client_credentials"]["client_id"]
    client_secret = credentials_data["client_credentials"]["client_secret"]

    credentials = (
        Credentials.service_principal_credentials_builder()
        .with_client_id(client_id)
        .with_client_secret(client_secret)
        .build()
    )
    return ExecutionContext.create(credentials)


def extract_pdf_to_json(pdf_path, output_zip):
    credentials_path = str(Environment.get_adobe_credentials_path())
    execution_context = setup_adobe_credentials(credentials_path)
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
    result = extract_pdf_operation.execute(execution_context)
    result.save_as(output_zip)
    return output_zip


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

        logging.info(f"Processed and saved JSON data for {zip_file}")
    except Exception as e:
        logging.error(f"Error processing {zip_file}: {e}")


def main(pdf_path, original_pdf_file):

    # Check if the json file already exists
    # Avoid api calls for the same file
    json_file = pdf_path.replace(".pdf", ".json")
    if os.path.exists(json_file):
        logging.info(f"JSON file already exists for {pdf_path}")
        return

    # Extract text from the PDF
    zip_file = pdf_path.replace(".pdf", ".zip")
    extract_pdf_to_json(pdf_path, zip_file)

    # Parse the extracted data, save to same folder
    parse_extracted_data(zip_file, os.path.dirname(original_pdf_file))

    # Delete zip file
    os.remove(zip_file)


if __name__ == "__main__":
    main()
