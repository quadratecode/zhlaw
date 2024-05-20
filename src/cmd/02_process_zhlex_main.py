# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

# Import custom modules
from src.modules.general_module import clean_html
from src.modules.general_module import json_to_html

from src.modules.law_pdf_module import extend_metadata
from src.modules.law_pdf_module import merge_marginalia
from src.modules.law_pdf_module import match_marginalia
from src.modules.law_pdf_module import create_hyperlinks


# Import external modules
import arrow
import logging
import glob
import json
from tqdm import tqdm
import argparse

# Set up logging
logging.basicConfig(
    filename="logs/process.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%m/%d/%Y %I:%M:%S %p",
)


def main(folder):

    # Initialize error counter
    error_counter = 0

    # Timestamp
    timestamp = arrow.now().format("YYYYMMDD-HHmmss")

    logging.info("Loading laws index")
    pdf_files = glob.glob(
        f"data/zhlex/{folder}/**/**/*-original.pdf",
        recursive=True,
    )
    # Remove duplicates found from different junctions
    pdf_files = list(set(pdf_files))
    if not pdf_files:
        logging.info("No PDF files found. Exiting.")
        return

    for pdf_file in tqdm(pdf_files):
        original_pdf_path = pdf_file
        json_file_law = pdf_file.replace("-original.pdf", "-modified.json")
        json_file_law_updated = pdf_file.replace(
            "-original.pdf", "-modified-updated.json"
        )
        modified_pdf_path = pdf_file.replace("-original.pdf", "-modified.pdf")
        json_file_marginalia = pdf_file.replace("-original.pdf", "-marginalia.json")
        json_file_marginalia_updated = pdf_file.replace(
            "-original.pdf", "-marginalia-updated.json"
        )
        modified_pdf_path_marginalia = pdf_file.replace(
            "-original.pdf", "-marginalia.pdf"
        )
        metadata_file = pdf_file.replace("-original.pdf", "-metadata.json")
        html_file_law = pdf_file.replace("-original.pdf", "-modified.html")
        html_file_marginalia = pdf_file.replace("-original.pdf", "-marginalia.html")
        merged_html_law = pdf_file.replace("-original.pdf", "-merged.html")

        try:
            with open(metadata_file, "r") as f:
                metadata = json.load(f)

            # Extract color from law PDF
            logging.info(f"Extracting color for law: {pdf_file}")
            extend_metadata.main(
                original_pdf_path,
                modified_pdf_path,
                json_file_law,
                json_file_law_updated,
            )
            logging.info(f"Finished extracting color for law: {pdf_file}")

            # Extract color from marginalia PDF
            logging.info(f"Extracting color for marginalia: {pdf_file}")
            extend_metadata.main(
                original_pdf_path,
                modified_pdf_path_marginalia,
                json_file_marginalia,
                json_file_marginalia_updated,
            )
            logging.info(f"Finished extracting color for marginalia: {pdf_file}")

            # Convert JSON to HTML
            logging.info(f"Converting to HTML: {pdf_file}")
            json_to_html.main(
                json_file_law_updated, metadata, html_file_law, marginalia=False
            )
            logging.info(f"Finished converting to HTML: {pdf_file}")

            # Converting marginalia to HTML
            logging.info(f"Converting to HTML: {pdf_file}")
            json_to_html.main(
                json_file_marginalia_updated,
                metadata,
                html_file_marginalia,
                marginalia=True,
            )
            logging.info(f"Finished converting to HTML: {pdf_file}")

            # Merge marginalia which belong togehter
            logging.info(f"Merging marginalia: {pdf_file}")
            merge_marginalia.main(html_file_marginalia)
            logging.info(f"Finished merging marginalia: {pdf_file}")

            # Match marginalia with the law
            logging.info(f"Matching marginalia: {pdf_file}")
            match_marginalia.main(html_file_law, html_file_marginalia, merged_html_law)
            logging.info(f"Finished matching marginalia: {pdf_file}")

            # Match footnotes and hyperlinks
            logging.info(f"Matching footnotes and links: {pdf_file}")
            create_hyperlinks.main(merged_html_law, json_file_law_updated)
            logging.info(f"Finished matching footnotes and links: {pdf_file}")

            # Final Clean-Up
            logging.info(f"Cleaning HTML: {pdf_file}")
            clean_html.main(merged_html_law)
            logging.info(f"Finished cleaning HTML: {pdf_file}")
            # Add timestamp to metadata
            metadata["process_steps"]["generate_html"] = timestamp

            # Save the updated metadata
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=4, ensure_ascii=False)

        except Exception as e:
            logging.error(
                f"Error during in {__file__}: {e} at {timestamp}", exc_info=True
            )
            error_counter += 1
            continue

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
