import os
import json
import re
from bs4 import BeautifulSoup
from markdownify import markdownify as md
import zipfile
from pathlib import Path
import yaml
import logging

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
    # Find all elements whose names start with 'h' followed by a number
    for tag in soup.find_all(
        lambda tag: tag.name and tag.name.startswith("h") and tag.name[1:].isdigit()
    ):
        level = int(tag.name[1:])
        if level > 6:
            # Create new h6 tag
            new_tag = soup.new_tag("h6")
            # Copy contents instead of just string
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

    # 3. Convert dynamic hyperlinks
    base_url = f"https://www.zhlaw.ch/col-zh/{ordnungsnummer}-{nachtragsnummer}.html"
    for link in soup.find_all("a", href=True):
        if link["href"].startswith("#"):
            link["href"] = f"{base_url}{link['href']}"

    # 4. Process marginalia (before provisions to avoid interference)
    for marginalia in soup.find_all(class_="marginalia"):
        marginalia_text = marginalia.get_text(strip=True)
        new_tag = soup.new_tag("strong")
        new_tag.string = marginalia_text
        marginalia.clear()
        marginalia.append(new_tag)

    # 5. Format enumeration elements
    for enum in soup.find_all(class_=["enum-ziff", "enum-ziffer", "enum-lit"]):
        enum_text = enum.get_text(strip=True)
        new_tag = soup.new_tag("p")
        new_tag.string = f"| {enum_text}"
        enum.replace_with(new_tag)

    # 6. Wrap provisions in curly brackets and create links
    for provision in soup.find_all(class_="provision"):
        provision_id = provision.get("id", "")
        provision_text = provision.get_text(strip=True)
        new_text = f"[{{{provision_text}}}]({base_url}#{provision_id})"
        provision.string = new_text
        # Add consistent spacing
        provision.append(soup.new_string("\n\n"))

    # 7. Wrap subprovisions in code brackets and create links
    for subprovision in soup.find_all(class_="subprovision"):
        subprovision_id = subprovision.get("id", "")
        subprovision_text = subprovision.get_text(strip=True)
        # Extract number from superscript if present
        number = subprovision.find("sup")
        number_text = number.get_text(strip=True) if number else subprovision_text
        new_text = f"[<{number_text}>]({base_url}#{subprovision_id})"
        subprovision.string = new_text
        # Add consistent spacing
        subprovision.append(soup.new_string("\n\n"))

    # 8. Set up custom markdownify conversion
    def convert_tag(tag, content):
        # Handle headings
        if tag.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            level = int(tag.name[1])
            return f"{'#' * level} {content}\n\n"

        # Handle strong tags (for marginalia)
        if tag.name == "strong":
            return f"**{content}**"

        # Default handling with consistent spacing
        return f"{content}\n\n"

    # Generate markdown content
    md_content = md(str(soup), heading_style="ATX", convert_tag=convert_tag)

    # Clean up multiple consecutive newlines and single whitespace lines
    md_content = re.sub(
        r"\n{3,}", "\n\n", md_content
    )  # First clean up multiple newlines

    # Clean up lines containing only whitespace and remove trailing horizontal rules
    cleaned_lines = [
        line
        for line in md_content.splitlines()
        if line.strip() != "" and line.strip() != "---"
    ]
    md_content = "\n\n".join(cleaned_lines)

    # 9. Add YAML frontmatter
    frontmatter = {}
    if "doc_info" in metadata:
        # Flatten and filter out versions
        flat_metadata = flatten_dict(metadata["doc_info"])
        frontmatter.update(flat_metadata)

    # Convert frontmatter to YAML and combine with content
    yaml_frontmatter = yaml.dump(frontmatter, allow_unicode=True, sort_keys=False)
    final_content = f"---\n{yaml_frontmatter}---\n\n{md_content.strip()}\n"

    return final_content


def process_files(base_path):
    try:
        # Create output directory for zip file
        output_dir = Path(base_path).parent / "public"
        output_dir.mkdir(exist_ok=True)

        processed_files = 0
        zhlex_files_dir = Path(base_path) / "zhlex" / "zhlex_files"
        logger.info(f"Looking for files in: {zhlex_files_dir}")

        with zipfile.ZipFile(output_dir / "col-zh-md.zip", "w") as zipf:
            for root, dirs, files in os.walk(zhlex_files_dir):
                root_path = Path(root)
                html_files = [
                    f for f in files if f.endswith(("-original.html", "-merged.html"))
                ]

                if not html_files:
                    continue

                logger.info(f"Found target HTML files in {root_path}: {html_files}")

                for html_file in html_files:
                    try:
                        file_path = root_path / html_file
                        parts = html_file.split("-")

                        if len(parts) < 2:
                            logger.warning(
                                f"Skipping {html_file}: Invalid filename format"
                            )
                            continue

                        ordnungsnummer = parts[0]
                        nachtragsnummer = parts[1]
                        metadata_file = (
                            root_path
                            / f"{ordnungsnummer}-{nachtragsnummer}-metadata.json"
                        )

                        if not metadata_file.exists():
                            logger.warning(f"Metadata file not found for {html_file}")
                            continue

                        logger.info(
                            f"Processing {html_file} with metadata from {metadata_file}"
                        )

                        # Try to read the HTML file with different encodings
                        try:
                            html_content, encoding = read_file_with_fallback_encoding(
                                file_path
                            )
                            logger.info(
                                f"Successfully read {html_file} with {encoding} encoding"
                            )
                        except UnicodeDecodeError as e:
                            logger.error(f"Could not decode {html_file}: {e}")
                            continue

                        # Read metadata file (should be UTF-8)
                        with open(metadata_file, "r", encoding="utf-8") as f:
                            metadata = json.load(f)

                        # Convert to markdown
                        md_content = convert_html_to_md(
                            html_content, metadata, ordnungsnummer, nachtragsnummer
                        )

                        # Save markdown file
                        md_file = file_path.with_suffix(".md")
                        with open(md_file, "w", encoding="utf-8") as f:
                            f.write(md_content)

                        # Add to zip file
                        relative_path = md_file.relative_to(zhlex_files_dir)
                        zipf.write(md_file, str(relative_path))
                        processed_files += 1
                        logger.info(f"Successfully processed {html_file}")

                    except Exception as e:
                        logger.error(f"Error processing file {html_file}: {e}")
                        continue

        logger.info(f"Processing complete. Processed {processed_files} files.")

    except Exception as e:
        logger.error(f"Error in process_files: {e}")
        raise


if __name__ == "__main__":
    # Use the base path of your project
    base_path = "/home/rdm/github/zhlaw/data"
    process_files(base_path)
