"""Converts processed law HTML files to Markdown format for dataset distribution.

This module processes HTML law texts and converts them to clean Markdown format,
suitable for machine learning datasets and text analysis. It handles special
law formatting, removes noise, and creates structured output with YAML frontmatter.

The generated markdown files are stored persistently in a 'md-files/zh' directory
within the output directory. Files are regenerated completely on each run.

Functions:
    is_ascii_art_or_noise(text): Detects ASCII art or formatting noise
    read_file_with_fallback_encoding(file_path): Reads files with encoding detection
    sanitize_headings(text): Cleans up heading formatting
    flatten_dict(d, parent_key, sep): Flattens nested dictionaries
    convert_html_to_markdown(html_content, metadata): Main conversion function
    build_markdown_dataset(input_dir, output_dir): Processes all law files

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import os
import json
import re
from bs4 import BeautifulSoup, NavigableString, Tag
from markdownify import markdownify as md
import zipfile
from pathlib import Path
import yaml
import concurrent.futures
# from tqdm import tqdm  # Replaced with progress_utils
from src.utils.progress_utils import progress_manager, track_concurrent_futures
from urllib.parse import urljoin
import sys
from src.utils.logging_utils import get_module_logger

# Set up logging
logger = get_module_logger(__name__)


def is_ascii_art_or_noise(line):
    """
    Check if a line appears to be ASCII art or noise.
    Returns True if the line should be removed.
    """
    stripped = line.strip()
    if not stripped:
        return True
    special_chars = set("·•.:-_=|/\\[](){}♦◊,'\"`~!@#$%^&*+<>?;")
    special_count = sum(1 for char in stripped if char in special_chars)
    if len(stripped) > 0:
        if len(stripped) <= 3 and special_count == len(stripped):
            return True
        special_ratio = special_count / len(stripped)
        return special_ratio > 0.5 and len(stripped) > 5
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
    Find any heading tags beyond h5 and convert them to h5.
    """
    for tag in soup.find_all(
        lambda tag: tag.name and tag.name.startswith("h") and tag.name[1:].isdigit()
    ):
        level = int(tag.name[1:])
        if level > 5:
            new_tag = soup.new_tag("h5")
            for content in tag.contents:
                new_tag.append(
                    content.extract()
                    if isinstance(content, Tag)
                    else NavigableString(str(content))
                )
            tag.replace_with(new_tag)


def flatten_dict(d, parent_key="", sep="_"):
    """
    Flatten a nested dictionary for YAML frontmatter.
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict) and k != "versions":
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            if k != "versions":
                items.append((new_key, v))
            elif parent_key == "" and k == "versions":
                items.append((k, v))
    return dict(items)


# --- [End of assumed helper functions] ---


def convert_html_to_md(html_content, metadata, ordnungsnummer, nachtragsnummer):
    """
    Convert HTML content to Markdown with specific transformations.
    """
    # Increase recursion limit temporarily for deeply nested HTML
    original_recursion_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(10000)

    try:
        # Parse HTML
        soup = BeautifulSoup(html_content, "html.parser")

        # Base URL for resolving relative links
        base_url = (
            f"https://www.zhlaw.ch/col-zh/{ordnungsnummer}-{nachtragsnummer}.html"
        )

        # 1. Sanitize headings to cap at h5
        sanitize_headings(soup)

        # 1.2 Flatten deeply nested font tags to prevent recursion issues
        def flatten_font_tags(soup):
            """Remove deeply nested font tags while preserving text content."""
            font_tags = soup.find_all("font")
            if len(font_tags) > 2000:  # Threshold for deeply nested structures
                logger.warning(
                    f"Found {len(font_tags)} font tags, flattening to prevent recursion"
                )
                for font_tag in font_tags:
                    font_tag.unwrap()

        flatten_font_tags(soup)

        # 1.5 Remove <b> and <strong> tags
        for bold_tag in soup.find_all(["b", "strong"]):
            bold_tag.unwrap()

        # 2. Remove footnote references
        for footnote_ref in soup.find_all(class_="footnote-ref"):
            footnote_ref.decompose()

        # 3. Remove footnote definitions
        for footnote in soup.find_all(class_="footnote"):
            footnote.decompose()

        # 4. Remove element with id "footnote-line"
        footnote_line = soup.find(id="footnote-line")
        if footnote_line:
            footnote_line.decompose()

        # 5. Remove element with id "annex"
        annex = soup.find(id="annex")
        if annex:
            annex.decompose()

        # 6. Process provisions (class="provision")
        # *** MODIFIED: Use ⟨⟩ instead of <> ***
        for provision in soup.find_all("p", class_="provision"):
            link = provision.find("a", href=True)
            if link:
                provision_text = link.get_text(strip=True)
                href = link.get("href", "")
                absolute_url = urljoin(base_url, href)
                # Use angle brackets ⟨⟩
                link.string = f"⟨{provision_text}⟩"
                link["href"] = absolute_url
            else:
                provision_text = provision.get_text(strip=True)
                # Use angle brackets ⟨⟩
                provision.string = f"⟨{provision_text}⟩"

        # 7. Process subprovisions (class="subprovision-container")
        containers_to_replace = []
        for container in soup.find_all("div", class_="subprovision-container"):
            subprovision_p = container.find("p", class_="subprovision")
            subprovision_number = ""
            content_paragraph_text = ""
            original_content_paragraph = None

            if subprovision_p:
                sup_elem = subprovision_p.find("sup")
                if sup_elem:
                    subprovision_number = sup_elem.get_text(strip=True)
                else:  # Fallback if no sup tag
                    link_in_sub = subprovision_p.find("a")
                    if link_in_sub:
                        subprovision_number = link_in_sub.get_text(strip=True)
                    else:
                        subprovision_number = subprovision_p.get_text(strip=True)

                current = subprovision_p.next_sibling
                while current:
                    if (
                        isinstance(current, Tag)
                        and current.name == "p"
                        and "subprovision" not in current.get("class", [])
                    ):
                        original_content_paragraph = current
                        content_paragraph_text = " ".join(
                            original_content_paragraph.get_text(strip=True).split()
                        )
                        break
                    current = current.next_sibling

            if subprovision_number and original_content_paragraph is not None:
                new_num_p = soup.new_tag("p")
                new_num_p.string = subprovision_number
                new_content_p = soup.new_tag("p")
                new_content_p.string = content_paragraph_text
                containers_to_replace.append((container, [new_num_p, new_content_p]))
            else:
                logger.warning(
                    f"Could not properly parse subprovision in container. Removing."
                )
                containers_to_replace.append((container, []))

        for container, replacements in containers_to_replace:
            if replacements:
                container.replace_with(*replacements)
            else:
                container.decompose()

        # 8. Remove all *other* links (non-provision links)
        for link in soup.find_all("a", href=True):
            parent_p = link.find_parent("p", class_="provision")
            if parent_p:
                continue
            link.replace_with(link.get_text())

        # 9. Convert elements with class "marginalia" to h6
        for marginalia in soup.find_all(class_="marginalia"):
            marginalia_text = " ".join(marginalia.get_text(strip=True).split())
            if marginalia_text:
                h6 = soup.new_tag("h6")
                h6.string = marginalia_text
                marginalia.replace_with(h6)
            else:
                marginalia.decompose()

        soup = BeautifulSoup(str(soup), "html.parser")

        # 10. Generate markdown content using markdownify
        md_content = md(str(soup), heading_style="ATX", links="inline")

        # 11. Clean up markdown content
        md_content = re.sub(r"\n{3,}", "\n\n", md_content)

        cleaned_lines = []
        for line in md_content.splitlines():
            line = re.sub(r"\s{2,}", " ", line)  # Collapse spaces first
            stripped_line = line.strip()
            if stripped_line == "":
                continue
            if is_ascii_art_or_noise(line):
                logger.debug(f"Removing noise line: {line}")
                continue
            cleaned_lines.append(line)

        md_content = "\n".join(cleaned_lines)

        # ---- POST-PROCESSING FOR DESIRED FORMATTING ----

        # Bold subprovision numbers
        md_content = re.sub(
            r"^(\d+)$(\n)(.*)$", r"**\1**\2\3", md_content, flags=re.MULTILINE
        )

        # Ensure blank line before headings
        md_content = re.sub(
            r"([^\n])\n(#+ .*)$", r"\1\n\n\2", md_content, flags=re.MULTILINE
        )
        md_content = re.sub(r"^(#+ .*)$", r"\n\1", md_content, flags=re.MULTILINE)

        # Consolidate multiple blank lines
        md_content = re.sub(r"\n{3,}", "\n\n", md_content)

        # Final strip
        md_content = md_content.strip()

        # ---- END POST-PROCESSING ----

        # 12. Add YAML frontmatter
        frontmatter = {}
        if "doc_info" in metadata:
            flat_metadata = flatten_dict(metadata["doc_info"])
            frontmatter.update(flat_metadata)

        yaml_frontmatter = yaml.dump(
            frontmatter, allow_unicode=True, sort_keys=False, default_flow_style=False
        )
        final_content = f"---\n{yaml_frontmatter}---\n\n{md_content}\n"

        return final_content

    except RecursionError as e:
        logger.error(
            f"Recursion error processing {ordnungsnummer}-{nachtragsnummer}: {e}"
        )
        # Return simplified markdown content
        text_content = BeautifulSoup(html_content, "html.parser").get_text()
        frontmatter = {}
        if "doc_info" in metadata:
            flat_metadata = flatten_dict(metadata["doc_info"])
            frontmatter.update(flat_metadata)
        yaml_frontmatter = yaml.dump(
            frontmatter, allow_unicode=True, sort_keys=False, default_flow_style=False
        )
        return f"---\n{yaml_frontmatter}---\n\n{text_content}\n"

    except Exception as e:
        logger.error(f"Error processing {ordnungsnummer}-{nachtragsnummer}: {e}")
        raise

    finally:
        # Reset recursion limit
        sys.setrecursionlimit(original_recursion_limit)


# =====================================================
#  process_single_html_file and main functions
#  (Remain unchanged - they just call the updated convert_html_to_md)
# =====================================================
def process_single_html_file(args):
    """Process a single HTML file and convert it to Markdown."""
    file_path, root_path, html_file, markdown_dataset_dir = args
    try:
        match = re.match(r"([\d\.]+)-([\d]+)(?:-original|-merged)?\.html", html_file)
        if not match:
            logger.warning(f"Skipping {html_file}: Bad filename format.")
            return False, None
        ordnungsnummer, nachtragsnummer = match.groups()
        new_filename = f"{ordnungsnummer}-{nachtragsnummer}.md"
        metadata_filename = f"{ordnungsnummer}-{nachtragsnummer}-metadata.json"
        metadata_file = root_path / metadata_filename
        if not metadata_file.exists():
            parent_metadata_file = root_path.parent / metadata_filename
            if parent_metadata_file.exists():
                metadata_file = parent_metadata_file
            else:
                logger.warning(f"Metadata missing for {html_file}. Skipping.")
                return False, None
        html_content, encoding = read_file_with_fallback_encoding(file_path)
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        md_content = convert_html_to_md(
            html_content, metadata, ordnungsnummer, nachtragsnummer
        )
        md_file = markdown_dataset_dir / new_filename
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md_content)
        return True, new_filename
    except Exception as e:
        logger.error(f"Error processing file {html_file}: {e}", exc_info=True)
        return False, None


def main(source_path, processing_mode="sequential", max_workers=None, output_dir=None):
    """Process HTML files to Markdown and create a zip file.
    
    The markdown files are stored persistently in 'datasets/md-files/zh/'.
    Existing files are cleared at the start of each run to ensure a clean build.
    The zip file is created in the specified output directory (or 'datasets/' if not specified).
    
    Args:
        source_path: Path to the source HTML files
        processing_mode: 'sequential' or 'concurrent'
        max_workers: Number of workers for concurrent processing
        output_dir: Output directory for zip file (defaults to 'datasets')
    """
    try:
        source_path = Path(source_path)
        # Markdown files always go to datasets/md-files/zh
        datasets_dir = Path("datasets")
        datasets_dir.mkdir(parents=True, exist_ok=True)
        markdown_dataset_dir = datasets_dir / "md-files" / "zh"
        
        # Zip file goes to output_dir (or datasets if not specified)
        zip_output_dir = Path(output_dir) if output_dir else datasets_dir
        zip_output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Source directory: {source_path.resolve()}")
        logger.info(f"Markdown files directory: {markdown_dataset_dir.resolve()}")
        logger.info(f"Zip output directory: {zip_output_dir.resolve()}")
        if markdown_dataset_dir.exists():
            import shutil

            shutil.rmtree(markdown_dataset_dir)
        markdown_dataset_dir.mkdir(parents=True, exist_ok=True)

        all_html_files_args = []
        found_count, skipped_count = 0, 0
        target_suffixes = ("-original.html", "-merged.html")
        for root, _, files in os.walk(source_path):
            root_path = Path(root)
            for filename in files:
                if filename.endswith(target_suffixes):
                    match = re.match(
                        r"([\d\.]+)-([\d]+)(?:-original|-merged)?\.html", filename
                    )
                    if match:
                        ordnungsnummer, nachtragsnummer = match.groups()
                        metadata_filename = (
                            f"{ordnungsnummer}-{nachtragsnummer}-metadata.json"
                        )
                        metadata_file = root_path / metadata_filename
                        parent_metadata_file = root_path.parent / metadata_filename
                        if metadata_file.exists() or parent_metadata_file.exists():
                            all_html_files_args.append(
                                (root_path / filename, root_path, filename, markdown_dataset_dir)
                            )
                            found_count += 1
                        else:
                            skipped_count += 1
                    else:
                        skipped_count += 1
                # else: skipped_count += 1 # Optional: count non-target files skipped

        if not all_html_files_args:
            logger.warning("No target HTML files with metadata found. Exiting.")
            if markdown_dataset_dir.exists():
                markdown_dataset_dir.rmdir()  # Try removing if empty
            return
        logger.info(
            f"Found {found_count} target HTML files. Skipped {skipped_count} other files."
        )

        processed_files_count = 0
        successful_filenames = []
        failed_files = []
        effective_max_workers = os.cpu_count() if max_workers is None else max_workers

        if processing_mode.lower() == "concurrent" and len(all_html_files_args) > 0:
            logger.info(
                f"Processing {len(all_html_files_args)} files concurrently (max_workers={effective_max_workers})..."
            )
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=effective_max_workers
            ) as executor:
                futures = {
                    executor.submit(process_single_html_file, args): args
                    for args in all_html_files_args
                }
                # Convert to list of futures for tracking
                futures_list = list(futures.keys())
                
                results = {}
                for future in track_concurrent_futures(
                    futures_list,
                    desc=f"Converting {len(all_html_files_args)} HTML files",
                    unit="files"
                ):
                    args = futures[future]
                    html_filename = args[2]
                    try:
                        results[html_filename] = future.result()
                    except Exception as exc:
                        logger.error(
                            f"Task for {html_filename} failed: {exc}", exc_info=True
                        )
                        results[html_filename] = (False, None)
                for html_filename, (success, md_filename) in results.items():
                    if success and md_filename:
                        processed_files_count += 1
                        successful_filenames.append(md_filename)
                    else:
                        failed_files.append(html_filename)
        else:
            logger.info(f"Processing {len(all_html_files_args)} files sequentially...")
            with progress_manager() as pm:
                counter = pm.create_counter(
                    total=len(all_html_files_args),
                    desc=f"Converting {len(all_html_files_args)} HTML files",
                    unit="files"
                )
                
                for args in all_html_files_args:
                    html_filename = args[2]
                    success, md_filename = process_single_html_file(args)
                    if success and md_filename:
                        processed_files_count += 1
                        successful_filenames.append(md_filename)
                    else:
                        failed_files.append(html_filename)
                    counter.update()

        logger.info(
            f"Finished. Success: {processed_files_count}, Failed: {len(failed_files)}"
        )
        if failed_files:
            logger.warning(f"Failed files: {', '.join(failed_files)}")

        zip_file_path = zip_output_dir / "col-zh-md.zip"
        if successful_filenames:
            logger.info(f"Creating zip file: {zip_file_path}")
            successful_filenames.sort()
            with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                with progress_manager() as pm:
                    counter = pm.create_counter(
                        total=len(successful_filenames),
                        desc=f"Zipping {len(successful_filenames)} files",
                        unit="files"
                    )
                    
                    for filename in successful_filenames:
                        md_file = markdown_dataset_dir / filename
                        if md_file.exists():
                            zipf.write(md_file, filename)
                        else:
                            logger.warning(f"MD file {filename} not found for zipping.")
                        counter.update()
            logger.info(f"Zip file created with {len(successful_filenames)} files.")
        else:
            logger.warning("No successful files, zip not created.")
            if zip_file_path.exists():
                zip_file_path.unlink()  # Remove old/empty zip

        logger.info(f"Markdown files preserved in: {markdown_dataset_dir}")
        logger.info("Processing complete.")
    except Exception as e:
        logger.error(f"Critical error in main: {e}", exc_info=True)
        if "markdown_dataset_dir" in locals() and markdown_dataset_dir.exists():
            # Do not remove on error - preserve for debugging
            logger.error(f"Error occurred, markdown files preserved in: {markdown_dataset_dir}")
        raise


if __name__ == "__main__":
    current_dir = Path(__file__).parent if "__file__" in locals() else Path.cwd()
    # --- USER CONFIGURATION ---
    source_path_rel = "data/zhlex/zhlex_files"
    processing_mode = "concurrent"
    max_workers = None
    log_level = "INFO"
    # --- END USER CONFIGURATION ---

    # Log level is handled by the logging configuration
    source_path_abs = (current_dir / source_path_rel).resolve()
    print(f"Source Path: {source_path_abs}")
    print(f"Processing Mode: {processing_mode}")
    if processing_mode == "concurrent":
        print(f"Max Workers: {max_workers or os.cpu_count()}")
    print(f"Log Level: {log_level}")

    if not source_path_abs.is_dir():
        print(f"\nERROR: Source directory not found: {source_path_abs}")
    else:
        main(
            source_path_abs,
            processing_mode=processing_mode,
            max_workers=max_workers,
        )
