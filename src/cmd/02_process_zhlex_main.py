# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

# Import custom modules
from src.modules.general_module import clean_html, json_to_html
from src.modules.law_pdf_module import (
    extend_metadata,
    merge_marginalia,
    match_marginalia,
    create_hyperlinks,
)

# Import external modules
import arrow
import logging
import glob
import json
from tqdm import tqdm
import argparse
import sys
import concurrent.futures

# Set up logging
logging.basicConfig(
    filename="logs/process.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S %p",
)


def generate_file_paths(pdf_file: str) -> dict:
    """
    Given an original PDF file path, generate and return a dictionary of derived file paths.
    """
    return {
        "original_pdf_path": pdf_file,
        "json_file_law": pdf_file.replace("-original.pdf", "-modified.json"),
        "json_file_law_updated": pdf_file.replace(
            "-original.pdf", "-modified-updated.json"
        ),
        "modified_pdf_path": pdf_file.replace("-original.pdf", "-modified.pdf"),
        "json_file_marginalia": pdf_file.replace("-original.pdf", "-marginalia.json"),
        "json_file_marginalia_updated": pdf_file.replace(
            "-original.pdf", "-marginalia-updated.json"
        ),
        "modified_pdf_path_marginalia": pdf_file.replace(
            "-original.pdf", "-marginalia.pdf"
        ),
        "metadata_file": pdf_file.replace("-original.pdf", "-metadata.json"),
        "html_file_law": pdf_file.replace("-original.pdf", "-modified.html"),
        "html_file_marginalia": pdf_file.replace("-original.pdf", "-marginalia.html"),
        "merged_html_law": pdf_file.replace("-original.pdf", "-merged.html"),
    }


def read_metadata(metadata_file: str) -> dict:
    """Reads and returns the metadata from a JSON file."""
    with open(metadata_file, "r") as f:
        return json.load(f)


def write_metadata(metadata_file: str, metadata: dict) -> None:
    """Writes the updated metadata back to the JSON file."""
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)


def process_pdf_file(pdf_file: str) -> bool:
    """
    Process a single PDF file by:
      - Extending metadata (extracting color) for law and marginalia PDFs.
      - Converting JSON to HTML for both law and marginalia.
      - Merging marginalia, matching them with the law,
        creating hyperlinks, and cleaning the final HTML.
      - Updating metadata with a processing timestamp.
    Returns True if processing succeeded; otherwise, False.
    """
    paths = generate_file_paths(pdf_file)
    try:
        metadata = read_metadata(paths["metadata_file"])

        logging.info(f"Extracting color for law: {pdf_file}")
        extend_metadata.main(
            paths["original_pdf_path"],
            paths["modified_pdf_path"],
            paths["json_file_law"],
            paths["json_file_law_updated"],
        )
        logging.info(f"Finished extracting color for law: {pdf_file}")

        logging.info(f"Extracting color for marginalia: {pdf_file}")
        extend_metadata.main(
            paths["original_pdf_path"],
            paths["modified_pdf_path_marginalia"],
            paths["json_file_marginalia"],
            paths["json_file_marginalia_updated"],
        )
        logging.info(f"Finished extracting color for marginalia: {pdf_file}")

        logging.info(f"Converting law JSON to HTML: {pdf_file}")
        json_to_html.main(
            paths["json_file_law_updated"],
            metadata,
            paths["html_file_law"],
            marginalia=False,
        )
        logging.info(f"Finished converting law JSON to HTML: {pdf_file}")

        logging.info(f"Converting marginalia JSON to HTML: {pdf_file}")
        json_to_html.main(
            paths["json_file_marginalia_updated"],
            metadata,
            paths["html_file_marginalia"],
            marginalia=True,
        )
        logging.info(f"Finished converting marginalia JSON to HTML: {pdf_file}")

        logging.info(f"Merging marginalia: {pdf_file}")
        merge_marginalia.main(paths["html_file_marginalia"])
        logging.info(f"Finished merging marginalia: {pdf_file}")

        logging.info(f"Matching marginalia: {pdf_file}")
        match_marginalia.main(
            paths["html_file_law"],
            paths["html_file_marginalia"],
            paths["merged_html_law"],
        )
        logging.info(f"Finished matching marginalia: {pdf_file}")

        logging.info(f"Creating hyperlinks: {pdf_file}")
        create_hyperlinks.main(paths["merged_html_law"], paths["json_file_law_updated"])
        logging.info(f"Finished creating hyperlinks: {pdf_file}")

        logging.info(f"Cleaning HTML: {pdf_file}")
        clean_html.main(paths["merged_html_law"])
        logging.info(f"Finished cleaning HTML: {pdf_file}")

        # Add processing timestamp to metadata
        timestamp = arrow.now().format("YYYYMMDD-HHmmss")
        metadata.setdefault("process_steps", {})["generate_html"] = timestamp
        write_metadata(paths["metadata_file"], metadata)
        return True
    except Exception as e:
        timestamp = arrow.now().format("YYYYMMDD-HHmmss")
        logging.error(f"Error in {__file__}: {e} at {timestamp}", exc_info=True)
        return False


def main(folder: str) -> None:
    """
    Process all PDF files in the specified folder in parallel.
    """
    logging.info("Loading laws index")
    pdf_files = glob.glob(f"data/zhlex/{folder}/**/**/*-original.pdf", recursive=True)
    pdf_files = list(set(pdf_files))
    if not pdf_files:
        logging.info("No PDF files found. Exiting.")
        return

    error_counter = 0
    # Using ProcessPoolExecutor for CPU-bound tasks
    with concurrent.futures.ProcessPoolExecutor() as executor:
        # Map the process_pdf_file function to all pdf_files and wrap with tqdm for progress bar
        results = list(
            tqdm(executor.map(process_pdf_file, pdf_files), total=len(pdf_files))
        )

    error_counter = results.count(False)
    logging.info(f"Finished processing HTML with {error_counter} errors")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process PDF files")
    parser.add_argument(
        "--folder",
        type=str,
        default="test_files",
        choices=["zhlex_files", "test_files"],
        help="Folder to process",
    )
    args = parser.parse_args()
    main(args.folder)
