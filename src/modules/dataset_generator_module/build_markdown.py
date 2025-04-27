import os
import json
import re
from bs4 import BeautifulSoup, NavigableString, Tag
from markdownify import markdownify as md
import zipfile
from pathlib import Path
import yaml
import logging
import concurrent.futures
from tqdm import tqdm
from urllib.parse import urljoin

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
        # Avoid division by zero for very short lines that might be just special chars
        if len(stripped) <= 3 and special_count == len(stripped):
            return True
        special_ratio = special_count / len(stripped)
        # Adjusted threshold to avoid removing legitimate short lines with some symbols
        return special_ratio > 0.5 and len(stripped) > 5

    return True  # Treat empty stripped lines as removable noise


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
    This handles malformed HTML that might contain h6, h7, h8, etc.
    """
    for tag in soup.find_all(
        lambda tag: tag.name and tag.name.startswith("h") and tag.name[1:].isdigit()
    ):
        level = int(tag.name[1:])
        if level > 5:
            new_tag = soup.new_tag("h5")
            # Safely extend contents, handling NavigableStrings
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
        if (
            isinstance(v, dict) and k != "versions"
        ):  # Exclude 'versions' key from flattening further
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            # Only add if key is not 'versions'
            if k != "versions":
                items.append((new_key, v))
            elif (
                parent_key == "" and k == "versions"
            ):  # Keep top-level 'versions' as is
                items.append((k, v))

    return dict(items)


def convert_html_to_md(html_content, metadata, ordnungsnummer, nachtragsnummer):
    """
    Convert HTML content to Markdown with specific transformations.
    """
    # Parse HTML
    soup = BeautifulSoup(html_content, "html.parser")

    # Base URL for resolving relative links
    base_url = f"https://www.zhlaw.ch/col-zh/{ordnungsnummer}-{nachtragsnummer}.html"

    # 1. Sanitize headings to cap at h5
    sanitize_headings(soup)

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
    # We modify the link *inside* the provision tag for markdownify to handle
    for provision in soup.find_all("p", class_="provision"):
        link = provision.find("a", href=True)
        if link:
            provision_text = link.get_text(strip=True)
            href = link.get("href", "")
            absolute_url = urljoin(
                base_url, href
            )  # Use urljoin for robust URL creation

            # Modify the link text directly
            link.string = f"<{provision_text}>"
            # Update the href to be absolute
            link["href"] = absolute_url
            # Ensure the provision tag itself is kept, markdownify will handle the <p> and <a>
        else:
            # If no link, wrap the text in <> and keep the paragraph
            provision_text = provision.get_text(strip=True)
            provision.string = f"<{provision_text}>"

    # 7. Process subprovisions (class="subprovision-container")
    # We find the number, find the associated text, combine them into "[N] Text", and replace the container
    for container in soup.find_all("div", class_="subprovision-container"):
        subprovision_p = container.find("p", class_="subprovision")
        subprovision_number = ""
        if subprovision_p:
            sup_elem = subprovision_p.find("sup")
            if sup_elem:
                subprovision_number = sup_elem.get_text(strip=True)
            else:
                # Fallback if no sup tag, try getting number from link or text
                link_in_sub = subprovision_p.find("a")
                if link_in_sub:
                    subprovision_number = link_in_sub.get_text(strip=True)
                else:  # Last resort: get text directly from subprovision paragraph
                    subprovision_number = subprovision_p.get_text(strip=True)

            # Try to find the content paragraph - typically the next <p> sibling of subprovision_p *within* the container
            content_paragraph = None
            # Correctly find the next paragraph sibling *after* subprovision_p
            current = subprovision_p.next_sibling
            while current:
                if (
                    isinstance(current, Tag)
                    and current.name == "p"
                    and "subprovision" not in current.get("class", [])
                ):
                    content_paragraph = current
                    break
                current = current.next_sibling

            if content_paragraph and subprovision_number:
                content_text = content_paragraph.get_text(strip=True)
                # Create the combined text line "[N] Text..."
                combined_text = f"[{subprovision_number}] {content_text}"

                # Create a new paragraph tag to hold the combined text
                new_p = soup.new_tag("p")
                new_p.string = combined_text

                # Replace the entire container with the new paragraph
                container.replace_with(new_p)
                # Decompose the original subprovision and content paragraphs as they are now replaced
                subprovision_p.decompose()
                content_paragraph.decompose()  # Decompose the original content paragraph too

            elif subprovision_p:
                # If content paragraph not found but subprovision existed, remove the subprovision paragraph
                # This prevents leaving orphaned subprovision numbers if structure is unexpected
                subprovision_p.decompose()

    # 8. Remove all *other* links (non-provision links) AFTER processing provisions
    for link in soup.find_all("a", href=True):
        # Check if this link is the one we modified inside a provision paragraph
        parent_p = link.find_parent("p", class_="provision")
        if parent_p:
            # This is a provision link we want to keep, so skip it
            continue
        # Otherwise, replace the link with its text content
        link.replace_with(link.get_text())

    # 9. Convert elements with class "marginalia" to h6
    for marginalia in soup.find_all(class_="marginalia"):
        # Find the relevant text content, handling potential nested tags if any
        marginalia_text = marginalia.get_text(strip=True)
        if marginalia_text:  # Only create h6 if there's text
            h6 = soup.new_tag("h6")
            h6.string = marginalia_text
            marginalia.replace_with(h6)
        else:
            marginalia.decompose()  # Remove empty marginalia tags

    # 10. Generate markdown content using markdownify
    # Configure markdownify to handle links correctly and use ATX headings
    md_content = md(str(soup), heading_style="ATX", links="inline")

    # 11. Clean up markdown content
    # Remove excessive newlines initially
    md_content = re.sub(r"\n{3,}", "\n\n", md_content)

    # Filter out empty lines, standalone '---' lines, and potential noise/ASCII art
    cleaned_lines = []
    for line in md_content.splitlines():
        stripped_line = line.strip()
        if stripped_line == "":
            continue  # Skip empty lines
        # Refined '---' removal: Remove only if it's truly standalone
        if stripped_line == "---" and line == "---":
            # Let's keep '---' for now, markdownify might produce them intentionally as rules
            # If they become problematic, uncomment the next line
            # continue
            pass
        if is_ascii_art_or_noise(line):
            logger.debug(f"Removing noise line: {line}")
            continue  # Skip noise lines
        cleaned_lines.append(line)  # Keep the original line

    md_content = "\n".join(cleaned_lines)  # Re-join with single newlines first

    # ---- POST-PROCESSING FOR DESIRED FORMATTING ----

    # Split subprovisions "[N] Text" into "[N]\nText"
    # Applies to lines starting exactly with [N] followed by a space
    md_content = re.sub(r"^(\[\d+\]) (.*)$", r"\1\n\2", md_content, flags=re.MULTILINE)

    # Ensure a blank line before all headings (h1-h6 / #-######)
    # Add a newline before *every* line starting with #
    md_content = re.sub(r"^(#+ .*)$", r"\n\1", md_content, flags=re.MULTILINE)

    # Consolidate multiple blank lines into a single blank line
    md_content = re.sub(r"\n{3,}", "\n\n", md_content)

    # Final strip of leading/trailing whitespace (removes added newline if heading was first)
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
    final_content = (
        f"---\n{yaml_frontmatter}---\n\n{md_content}\n"  # Ensure final newline
    )

    return final_content


# =====================================================
#  process_single_html_file and main functions
#  (remain the same as the previous version)
# =====================================================
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
        # Extract ordnungsnummer and nachtragsnummer from the filename
        # Handles cases like '131.1-118-original.html' or '211.11-5-merged.html'
        match = re.match(r"([\d\.]+)-([\d]+)(?:-original|-merged)?\.html", html_file)
        if not match:
            logger.warning(
                f"Skipping {html_file}: Could not parse ordnungsnummer/nachtragsnummer from filename."
            )
            return False, None

        ordnungsnummer = match.group(1)
        nachtragsnummer = match.group(2)

        # Create simplified filename
        new_filename = f"{ordnungsnummer}-{nachtragsnummer}.md"

        metadata_filename = f"{ordnungsnummer}-{nachtragsnummer}-metadata.json"
        metadata_file = root_path / metadata_filename

        if not metadata_file.exists():
            logger.warning(
                f"Metadata file '{metadata_filename}' not found for {html_file} in {root_path}"
            )
            # Attempt to find metadata in parent directory as a fallback
            parent_metadata_file = root_path.parent / metadata_filename
            if parent_metadata_file.exists():
                metadata_file = parent_metadata_file
                logger.info(f"Found metadata in parent directory: {metadata_file}")
            else:
                logger.warning(
                    f"Metadata file not found in parent directory either for {html_file}. Skipping."
                )
                return False, None

        # Read and convert content
        html_content, encoding = read_file_with_fallback_encoding(file_path)
        logger.debug(f"Read {html_file} with encoding {encoding}")

        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        md_content = convert_html_to_md(
            html_content, metadata, ordnungsnummer, nachtragsnummer
        )

        # Save to temporary directory with flattened structure
        md_file = temp_md_dir / new_filename
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        # logger.info(f"Successfully processed {html_file} -> {new_filename}")
        return True, new_filename

    except FileNotFoundError as e:
        logger.error(f"File not found error processing {html_file}: {e}")
        return False, None
    except UnicodeDecodeError as e:
        logger.error(f"Encoding error processing file {html_file}: {e}")
        return False, None
    except Exception as e:
        logger.error(
            f"Error processing file {html_file}: {e}", exc_info=True
        )  # Log traceback
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
        output_dir.mkdir(parents=True, exist_ok=True)  # Ensure parent dirs exist

        logger.info(f"Source directory: {source_path.resolve()}")
        logger.info(f"Output directory: {output_dir.resolve()}")

        # Create a temporary directory for MD files before zipping
        temp_md_dir = output_dir / "temp_md"
        if temp_md_dir.exists():
            import shutil

            shutil.rmtree(temp_md_dir)  # Clean up previous runs
        temp_md_dir.mkdir(exist_ok=True)

        # Collect all HTML files to process
        all_html_files_args = []
        logger.info(f"Walking through {source_path} to find HTML files...")
        found_count = 0
        skipped_count = 0
        target_suffixes = ("-original.html", "-merged.html")

        for root, dirs, files in os.walk(source_path):
            root_path = Path(root)
            for filename in files:
                if filename.endswith(target_suffixes):
                    # Check if a corresponding metadata file exists
                    match = re.match(
                        r"([\d\.]+)-([\d]+)(?:-original|-merged)?\.html", filename
                    )
                    if match:
                        ordnungsnummer = match.group(1)
                        nachtragsnummer = match.group(2)
                        metadata_filename = (
                            f"{ordnungsnummer}-{nachtragsnummer}-metadata.json"
                        )
                        metadata_file = root_path / metadata_filename
                        parent_metadata_file = (
                            root_path.parent / metadata_filename
                        )  # Check parent too

                        if metadata_file.exists() or parent_metadata_file.exists():
                            file_path = root_path / filename
                            all_html_files_args.append(
                                (file_path, root_path, filename, temp_md_dir)
                            )
                            found_count += 1
                        else:
                            logger.debug(
                                f"Skipping {filename}: Metadata file '{metadata_filename}' not found in {root_path} or its parent."
                            )
                            skipped_count += 1
                    else:
                        logger.debug(
                            f"Skipping {filename}: Filename format doesn't match expected pattern."
                        )
                        skipped_count += 1

        if not all_html_files_args:
            logger.warning(
                "No target HTML files with corresponding metadata found. Exiting."
            )
            # Clean up empty temp dir
            if temp_md_dir.exists():
                try:
                    temp_md_dir.rmdir()  # Remove if empty
                except OSError:
                    pass  # Ignore if not empty for some reason
            return

        logger.info(
            f"Found {found_count} target HTML files with metadata to process. Skipped {skipped_count} files."
        )

        # Process files either sequentially or concurrently
        processed_files_count = 0
        successful_filenames = []
        failed_files = []

        # Determine actual number of workers
        effective_max_workers = None
        if processing_mode.lower() == "concurrent":
            if max_workers is None:
                # Default to number of CPUs if not specified
                effective_max_workers = os.cpu_count()
                logger.info(f"Using default max_workers: {effective_max_workers}")
            else:
                effective_max_workers = max_workers

        if processing_mode.lower() == "concurrent" and len(all_html_files_args) > 0:
            logger.info(
                f"Processing {len(all_html_files_args)} files concurrently using up to {effective_max_workers} workers..."
            )
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=effective_max_workers
            ) as executor:
                # Map the process function to all files and wrap with tqdm for progress bar
                futures = {
                    executor.submit(process_single_html_file, args): args
                    for args in all_html_files_args
                }
                results = {}
                for future in tqdm(
                    concurrent.futures.as_completed(futures),
                    total=len(all_html_files_args),
                    desc="Converting HTML to Markdown",
                ):
                    args = futures[future]
                    html_filename = args[2]  # Get original filename for logging
                    try:
                        success, result_filename = future.result()
                        results[html_filename] = (success, result_filename)
                    except Exception as exc:
                        logger.error(
                            f"Concurrent task for {html_filename} generated an exception: {exc}",
                            exc_info=True,
                        )
                        results[html_filename] = (False, None)

                # Collect results
                for html_filename, (success, md_filename) in results.items():
                    if success and md_filename:
                        processed_files_count += 1
                        successful_filenames.append(md_filename)
                    else:
                        failed_files.append(html_filename)

        else:
            logger.info(f"Processing {len(all_html_files_args)} files sequentially...")
            for args in tqdm(all_html_files_args, desc="Converting HTML to Markdown"):
                html_filename = args[2]
                success, md_filename = process_single_html_file(args)
                if success and md_filename:
                    processed_files_count += 1
                    successful_filenames.append(md_filename)
                else:
                    failed_files.append(html_filename)

        logger.info(
            f"Finished processing. Successfully converted: {processed_files_count}, Failed: {len(failed_files)}"
        )
        if failed_files:
            logger.warning(f"Failed files: {', '.join(failed_files)}")

        # Create the zip file only if there are successful files
        zip_file_path = output_dir / "col-zh-md.zip"
        if successful_filenames:
            logger.info(f"Creating zip file: {zip_file_path}")
            # Sort filenames for consistent zip archive contents
            successful_filenames.sort()
            with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for filename in tqdm(successful_filenames, desc="Zipping files"):
                    md_file = temp_md_dir / filename
                    if md_file.exists():
                        zipf.write(md_file, filename)
                    else:
                        logger.warning(
                            f"Markdown file {filename} not found in temp directory for zipping."
                        )
            logger.info(
                f"Zip file created successfully with {len(successful_filenames)} files."
            )
        else:
            logger.warning(
                "No files were successfully processed, zip file will not be created."
            )
            if zip_file_path.exists():
                logger.info(
                    f"Removing potentially empty or outdated zip file: {zip_file_path}"
                )
                zip_file_path.unlink()

        # Clean up temporary directory
        if temp_md_dir.exists():
            logger.info(f"Cleaning up temporary directory: {temp_md_dir}")
            import shutil

            shutil.rmtree(temp_md_dir)

        logger.info("Processing complete.")

    except Exception as e:
        logger.error(f"An critical error occurred in main function: {e}", exc_info=True)
        # Optionally clean up temp dir even on error
        if "temp_md_dir" in locals() and temp_md_dir.exists():
            try:
                import shutil

                shutil.rmtree(temp_md_dir)
            except Exception as cleanup_e:
                logger.error(f"Error during cleanup after main error: {cleanup_e}")
        raise


if __name__ == "__main__":
    # Example usage:
    # Assumes script is run from a directory where 'data/zhlex/zhlex_files' and 'public' are relative paths
    # Adjust these paths as necessary for your directory structure.
    current_dir = Path(__file__).parent if "__file__" in locals() else Path.cwd()
    source_path_rel = "data/zhlex/zhlex_files"
    output_dir_rel = "public"

    # Resolve paths relative to the script or current working directory
    source_path_abs = (current_dir / source_path_rel).resolve()
    output_dir_abs = (current_dir / output_dir_rel).resolve()

    print(f"Source Path (resolved): {source_path_abs}")
    print(f"Output Path (resolved): {output_dir_abs}")

    # --- Configuration ---
    # Set processing mode: 'sequential' or 'concurrent'
    processing_mode = "concurrent"
    # Set max_workers=None to use os.cpu_count() for concurrent mode, or specify a number.
    max_workers = None  # Use None for default cpu count or set an integer e.g. 4

    # Set logging level (e.g., logging.DEBUG, logging.INFO, logging.WARNING)
    logging.getLogger().setLevel(logging.INFO)
    # logging.getLogger().setLevel(logging.DEBUG) # Uncomment for more detailed logs
    # --- End Configuration ---

    # Check if source directory exists before running
    if not source_path_abs.is_dir():
        print(f"ERROR: Source directory not found: {source_path_abs}")
        print(
            "Please ensure the 'source_path_rel' variable points to the correct location relative to the script."
        )
    else:
        main(
            source_path_abs,
            output_dir_abs,
            processing_mode=processing_mode,
            max_workers=max_workers,
        )
