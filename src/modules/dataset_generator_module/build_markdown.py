# Imports and other functions (is_ascii_art_or_noise, read_file_with_fallback_encoding,
# sanitize_headings, flatten_dict) remain the same as the previous version.
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
    # Parse HTML
    soup = BeautifulSoup(html_content, "html.parser")

    # Base URL for resolving relative links
    base_url = f"https://www.zhlaw.ch/col-zh/{ordnungsnummer}-{nachtragsnummer}.html"

    # 1. Sanitize headings to cap at h5
    sanitize_headings(soup)

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


# =====================================================
#  process_single_html_file and main functions
#  (Remain unchanged - they just call the updated convert_html_to_md)
# =====================================================
def process_single_html_file(args):
    """Process a single HTML file and convert it to Markdown."""
    file_path, root_path, html_file, temp_md_dir = args
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
        md_file = temp_md_dir / new_filename
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md_content)
        return True, new_filename
    except Exception as e:
        logger.error(f"Error processing file {html_file}: {e}", exc_info=True)
        return False, None


def main(source_path, output_dir, processing_mode="sequential", max_workers=None):
    """Process HTML files to Markdown and create a zip file."""
    try:
        source_path = Path(source_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Source directory: {source_path.resolve()}")
        logger.info(f"Output directory: {output_dir.resolve()}")
        temp_md_dir = output_dir / "temp_md"
        if temp_md_dir.exists():
            import shutil

            shutil.rmtree(temp_md_dir)
        temp_md_dir.mkdir(exist_ok=True)

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
                                (root_path / filename, root_path, filename, temp_md_dir)
                            )
                            found_count += 1
                        else:
                            skipped_count += 1
                    else:
                        skipped_count += 1
                # else: skipped_count += 1 # Optional: count non-target files skipped

        if not all_html_files_args:
            logger.warning("No target HTML files with metadata found. Exiting.")
            if temp_md_dir.exists():
                temp_md_dir.rmdir()  # Try removing if empty
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
                results = {}
                for future in tqdm(
                    concurrent.futures.as_completed(futures),
                    total=len(all_html_files_args),
                    desc="Converting HTML",
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
            for args in tqdm(all_html_files_args, desc="Converting HTML"):
                html_filename = args[2]
                success, md_filename = process_single_html_file(args)
                if success and md_filename:
                    processed_files_count += 1
                    successful_filenames.append(md_filename)
                else:
                    failed_files.append(html_filename)

        logger.info(
            f"Finished. Success: {processed_files_count}, Failed: {len(failed_files)}"
        )
        if failed_files:
            logger.warning(f"Failed files: {', '.join(failed_files)}")

        zip_file_path = output_dir / "col-zh-md.zip"
        if successful_filenames:
            logger.info(f"Creating zip file: {zip_file_path}")
            successful_filenames.sort()
            with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for filename in tqdm(successful_filenames, desc="Zipping files"):
                    md_file = temp_md_dir / filename
                    if md_file.exists():
                        zipf.write(md_file, filename)
                    else:
                        logger.warning(f"MD file {filename} not found for zipping.")
            logger.info(f"Zip file created with {len(successful_filenames)} files.")
        else:
            logger.warning("No successful files, zip not created.")
            if zip_file_path.exists():
                zip_file_path.unlink()  # Remove old/empty zip

        if temp_md_dir.exists():
            logger.info(f"Cleaning up temp dir: {temp_md_dir}")
            import shutil

            shutil.rmtree(temp_md_dir)
        logger.info("Processing complete.")
    except Exception as e:
        logger.error(f"Critical error in main: {e}", exc_info=True)
        if "temp_md_dir" in locals() and temp_md_dir.exists():
            try:
                import shutil

                shutil.rmtree(temp_md_dir)
            except Exception as cleanup_e:
                logger.error(f"Cleanup failed: {cleanup_e}")
        raise


if __name__ == "__main__":
    current_dir = Path(__file__).parent if "__file__" in locals() else Path.cwd()
    # --- USER CONFIGURATION ---
    source_path_rel = "data/zhlex/zhlex_files"
    output_dir_rel = "public"
    processing_mode = "concurrent"
    max_workers = None
    log_level = logging.INFO
    # --- END USER CONFIGURATION ---

    logging.getLogger().setLevel(log_level)
    source_path_abs = (current_dir / source_path_rel).resolve()
    output_dir_abs = (current_dir / output_dir_rel).resolve()
    print(f"Source Path: {source_path_abs}")
    print(f"Output Path: {output_dir_abs}")
    print(f"Processing Mode: {processing_mode}")
    if processing_mode == "concurrent":
        print(f"Max Workers: {max_workers or os.cpu_count()}")
    print(f"Log Level: {logging.getLevelName(log_level)}")

    if not source_path_abs.is_dir():
        print(f"\nERROR: Source directory not found: {source_path_abs}")
    else:
        main(
            source_path_abs,
            output_dir_abs,
            processing_mode=processing_mode,
            max_workers=max_workers,
        )
