import os
import json
import re
from bs4 import BeautifulSoup
from markdownify import markdownify as md
import zipfile
from pathlib import Path
import yaml
import logging
import concurrent.futures
from tqdm import tqdm

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def is_ascii_art_or_noise(line):
    """
    Check if a line appears to be ASCII art or noise.
    Returns True if the line should be removed.
    """
    # Strip whitespace first
    stripped = line.strip()
    if not stripped:
        return True

    # Define special characters commonly found in ASCII art/noise
    special_chars = set("·•.:-_=|/\\[](){}♦◊,'\"`~!@#$%^&*+<>?;")

    # Count special characters
    special_count = sum(1 for char in stripped if char in special_chars)

    # If more than 30% of the line consists of special characters, consider it noise
    if len(stripped) > 0:
        special_ratio = special_count / len(stripped)
        return special_ratio > 0.3

    return True


def read_file_with_fallback_encoding(file_path):
    """
    Try to read file with different encodings
    """
    encodings = ["utf-8", "iso-8859-1", "cp1252", "latin1"]

    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                return f.read(), encoding
        except UnicodeDecodeError:
            continue

    raise UnicodeDecodeError(
        f"Could not decode file {file_path} with any of the attempted encodings"
    )


def sanitize_headings(soup):
    """
    Find any heading tags beyond h6 and convert them to h6.
    This handles malformed HTML that might contain h7, h8, etc.
    """
    for tag in soup.find_all(
        lambda tag: tag.name and tag.name.startswith("h") and tag.name[1:].isdigit()
    ):
        level = int(tag.name[1:])
        if level > 6:
            new_tag = soup.new_tag("h6")
            new_tag.extend(tag.contents)
            tag.replace_with(new_tag)


def flatten_dict(d, parent_key="", sep="_"):
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict) and k != "versions":
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            if k != "versions":
                items.append((new_key, v))
    return dict(items)


def convert_html_to_md(html_content, metadata, ordnungsnummer, nachtragsnummer):
    """
    Convert HTML content to Markdown with specific transformations.
    """
    # Parse HTML
    soup = BeautifulSoup(html_content, "html.parser")

    # Sanitize any invalid heading tags first
    sanitize_headings(soup)

    # 1. Remove footnote references
    for footnote_ref in soup.find_all(class_="footnote-ref"):
        footnote_ref.decompose()

    # 2. Remove footnote definitions
    for footnote in soup.find_all(class_="footnote"):
        footnote.decompose()

    # Remove element with id "footnote-line"
    footnote_line = soup.find(id="footnote-line")
    if footnote_line:
        footnote_line.decompose()

    # Remove element with id "annex"
    annex = soup.find(id="annex")
    if annex:
        annex.decompose()

    # 3. Convert dynamic hyperlinks
    base_url = f"https://www.zhlaw.ch/col-zh/{ordnungsnummer}-{nachtragsnummer}.html"
    for link in soup.find_all("a", href=True):
        if link["href"].startswith("#"):
            link["href"] = f"{base_url}{link['href']}"

    # Process marginalia and other elements (remaining conversion logic stays the same)
    # ... (keep all the existing conversion logic)

    # Generate markdown content
    md_content = md(str(soup), heading_style="ATX")

    # Clean up content (keeping existing cleanup logic)
    md_content = re.sub(r"\n{3,}", "\n\n", md_content)
    cleaned_lines = [
        line
        for line in md_content.splitlines()
        if line.strip() != "" and line.strip() != "---"
    ]
    md_content = "\n\n".join(cleaned_lines)

    # Add YAML frontmatter
    frontmatter = {}
    if "doc_info" in metadata:
        flat_metadata = flatten_dict(metadata["doc_info"])
        frontmatter.update(flat_metadata)

    yaml_frontmatter = yaml.dump(frontmatter, allow_unicode=True, sort_keys=False)
    final_content = f"---\n{yaml_frontmatter}---\n\n{md_content.strip()}\n"

    return final_content


def process_single_html_file(args):
    """
    Process a single HTML file and convert it to Markdown.

    Args:
        args: A tuple containing:
            - file_path: Path to the HTML file
            - root_path: Root directory path
            - html_file: Name of the HTML file
            - temp_md_dir: Directory to store temporary MD files

    Returns:
        tuple: (success, new_filename) indicating if processing was successful
               and the name of the generated file
    """
    file_path, root_path, html_file, temp_md_dir = args

    try:
        parts = html_file.split("-")

        if len(parts) < 2:
            logger.warning(f"Skipping {html_file}: Invalid filename format")
            return False, None

        ordnungsnummer = parts[0]
        nachtragsnummer = parts[1]

        # Create simplified filename (remove -original or -merged suffix)
        new_filename = f"{ordnungsnummer}-{nachtragsnummer}.md"

        metadata_file = root_path / f"{ordnungsnummer}-{nachtragsnummer}-metadata.json"

        if not metadata_file.exists():
            logger.warning(f"Metadata file not found for {html_file}")
            return False, None

        # Read and convert content
        html_content, encoding = read_file_with_fallback_encoding(file_path)
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        md_content = convert_html_to_md(
            html_content, metadata, ordnungsnummer, nachtragsnummer
        )

        # Save to temporary directory with flattened structure
        md_file = temp_md_dir / new_filename
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        logger.info(f"Successfully processed {html_file} -> {new_filename}")
        return True, new_filename

    except Exception as e:
        logger.error(f"Error processing file {html_file}: {e}")
        return False, None


def main(source_path, output_dir, processing_mode="sequential", max_workers=None):
    """
    Process HTML files to convert them to Markdown and create a zip file.

    Args:
        source_path: Path to the source directory containing HTML files
        output_dir: Path to the output directory where the zip file will be created
        processing_mode: 'sequential' or 'concurrent' processing mode
        max_workers: Maximum number of worker processes for concurrent mode
    """
    try:
        source_path = Path(source_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)

        logger.info(f"Looking for files in: {source_path}")

        # Create a temporary directory for MD files before zipping
        temp_md_dir = output_dir / "temp_md"
        temp_md_dir.mkdir(exist_ok=True)

        # Collect all HTML files to process
        all_html_files = []
        for root, dirs, files in os.walk(source_path):
            root_path = Path(root)
            html_files = [
                f for f in files if f.endswith(("-original.html", "-merged.html"))
            ]

            if not html_files:
                continue

            logger.info(
                f"Found target HTML files in {root_path}: {len(html_files)} files"
            )

            for html_file in html_files:
                file_path = root_path / html_file
                all_html_files.append((file_path, root_path, html_file, temp_md_dir))

        # Process files either sequentially or concurrently
        processed_files = 0
        successful_filenames = []

        if processing_mode.lower() == "concurrent" and len(all_html_files) > 0:
            logger.info(f"Processing {len(all_html_files)} files concurrently")
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=max_workers
            ) as executor:
                # Map the process function to all files and wrap with tqdm for progress bar
                results = list(
                    tqdm(
                        executor.map(process_single_html_file, all_html_files),
                        total=len(all_html_files),
                        desc="Converting HTML to Markdown",
                    )
                )

                # Count successful files and collect filenames
                for success, filename in results:
                    if success and filename:
                        processed_files += 1
                        successful_filenames.append(filename)
        else:
            logger.info(f"Processing {len(all_html_files)} files sequentially")
            for args in tqdm(all_html_files, desc="Converting HTML to Markdown"):
                success, filename = process_single_html_file(args)
                if success and filename:
                    processed_files += 1
                    successful_filenames.append(filename)

        # Create the zip file with all successfully processed files
        with zipfile.ZipFile(output_dir / "col-zh-md.zip", "w") as zipf:
            for filename in successful_filenames:
                md_file = temp_md_dir / filename
                zipf.write(md_file, filename)

        # Clean up temporary directory
        import shutil

        shutil.rmtree(temp_md_dir)

        logger.info(f"Processing complete. Processed {processed_files} files.")

    except Exception as e:
        logger.error(f"Error in process_files: {e}")
        raise


if __name__ == "__main__":
    source_path = "data/zhlex/zhlex_files"
    output_dir = "public"
    main(source_path, output_dir)
