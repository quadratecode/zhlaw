"""Markdown parser for extracting structured data from legal text files.

This module parses markdown files with YAML frontmatter to extract legal data
including metadata, full text, and individual provisions. It handles the specific
formatting used in Swiss legal texts.

Functions:
    parse_markdown_file(file_path): Parse a single markdown file
    extract_provisions(markdown_content): Extract individual provisions
    parse_yaml_frontmatter(content): Parse YAML metadata
    extract_hyperlinks(text): Extract provision hyperlinks

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import re
import yaml
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from .date_utils import parse_date_safe, convert_boolean_safe, safe_float_conversion, safe_int_conversion

from src.utils.logging_utils import get_module_logger
logger = get_module_logger(__name__)


class MarkdownParseError(Exception):
    """Custom exception for markdown parsing errors."""
    pass


def parse_markdown_file(file_path: Path) -> Dict[str, Any]:
    """Parse a markdown file and extract all structured data.
    
    Args:
        file_path: Path to the markdown file
        
    Returns:
        Dictionary containing parsed data with keys:
        - metadata: YAML frontmatter data
        - full_text: Complete markdown content after frontmatter
        - provisions: List of individual provisions
        - file_info: File metadata (name, size, etc.)
        
    Raises:
        MarkdownParseError: If file cannot be parsed
    """
    try:
        logger.debug(f"Parsing markdown file: {file_path}")
        
        # Read file content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract YAML frontmatter and markdown content
        frontmatter, markdown_content = parse_yaml_frontmatter(content)
        
        # Extract provisions from markdown content
        provisions = extract_provisions(markdown_content, file_path.stem)
        
        # Parse filename to get ordnungsnummer and nachtragsnummer
        filename_parts = parse_filename(file_path.name)
        
        return {
            'metadata': frontmatter,
            'full_text': markdown_content,
            'provisions': provisions,
            'file_info': {
                'filename': file_path.name,
                'size': file_path.stat().st_size,
                'ordnungsnummer': filename_parts.get('ordnungsnummer'),
                'nachtragsnummer': filename_parts.get('nachtragsnummer')
            }
        }
        
    except Exception as e:
        logger.error(f"Error parsing markdown file {file_path}: {e}")
        raise MarkdownParseError(f"Could not parse {file_path}: {e}")


def parse_yaml_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """Parse YAML frontmatter from markdown content.
    
    Args:
        content: Full markdown file content
        
    Returns:
        Tuple of (frontmatter_dict, remaining_markdown_content)
        
    Raises:
        MarkdownParseError: If frontmatter cannot be parsed
    """
    try:
        # Check for YAML frontmatter delimiters
        if not content.startswith('---'):
            raise MarkdownParseError("No YAML frontmatter found")
        
        # Find the end of frontmatter
        parts = content.split('---', 2)
        if len(parts) < 3:
            raise MarkdownParseError("Malformed YAML frontmatter")
        
        yaml_content = parts[1].strip()
        markdown_content = parts[2].strip()
        
        # Parse YAML
        frontmatter = yaml.safe_load(yaml_content)
        if frontmatter is None:
            frontmatter = {}
        
        logger.debug(f"Parsed frontmatter with {len(frontmatter)} fields")
        return frontmatter, markdown_content
        
    except yaml.YAMLError as e:
        logger.error(f"YAML parsing error: {e}")
        raise MarkdownParseError(f"Invalid YAML frontmatter: {e}")
    except Exception as e:
        logger.error(f"Frontmatter parsing error: {e}")
        raise MarkdownParseError(f"Could not parse frontmatter: {e}")


def extract_provisions(markdown_content: str, filename_stem: str) -> List[Dict[str, Any]]:
    """Extract individual provisions from markdown content.
    
    Provisions start with patterns like:
    - [⟨§ 1.⟩](URL) for sections
    - [⟨Art. 1⟩](URL) for articles
    
    If marginalia (h6 headings) appear immediately before a provision,
    they are included as part of that provision.
    
    Args:
        markdown_content: Markdown text content
        filename_stem: Filename without extension for logging
        
    Returns:
        List of provision dictionaries with keys:
        - provision_number: The provision number (e.g., "1", "5a")
        - provision_markdown: The provision text content
        - provision_sequence: Sequential number in document
        - provision_hyperlink: Any hyperlinks in the provision
    """
    provisions = []
    sequence = 1
    
    try:
        # Split content into lines for processing
        lines = markdown_content.split('\n')
        current_provision = None
        current_content = []
        pending_marginalia = None  # Store marginalia that may belong to next provision
        
        for line_num, line in enumerate(lines, 1):
            original_line = line
            line = line.strip()
            
            if not line:
                if current_content or pending_marginalia:
                    current_content.append("")  # Preserve blank lines within provisions
                continue
            
            # Check for provision patterns: [⟨§ number.⟩](URL) or [⟨Art. number⟩](URL)
            # First check for sections: [⟨§ X.⟩] where X can be '4', '4a', '4 a', etc.
            section_match = re.search(r'\[⟨§\s*(\d+(?:\s*[a-z])*)\s*\.?⟩\]', line)
            # Then check for articles: [⟨Art. X⟩] where X can be '1', '1a', etc.
            article_match = re.search(r'\[⟨Art\.\s*(\d+[a-z]*)⟩\]', line)
            
            provision_match = section_match or article_match
            if provision_match:
                # Save previous provision if exists
                if current_provision:
                    provisions.append(_finalize_provision(current_provision, current_content, sequence - 1))
                
                # Extract provision number and type
                if section_match:
                    provision_number = section_match.group(1).strip()
                    provision_type = "section"
                else:  # article_match
                    provision_number = article_match.group(1).strip()
                    provision_type = "article"
                
                # Start new provision
                current_provision = {
                    'provision_number': provision_number,
                    'provision_type': provision_type,
                    'line_number': line_num
                }
                
                # Include pending marginalia if it exists
                current_content = []
                if pending_marginalia:
                    current_content.append(pending_marginalia)
                    pending_marginalia = None
                
                # Add the provision line itself
                current_content.append(original_line)
                sequence += 1
                logger.debug(f"Found {provision_type} {provision_number} at line {line_num}")
                continue
            
            # Check for any heading (h1-h6)
            heading_match = re.match(r'^#{1,6}\s+(.+)$', line)
            if heading_match:
                heading_level = len(re.match(r'^#+', line).group(0))
                heading_text = heading_match.group(1)
                marginalia_line = original_line
                
                # For h6 headings, check if this is marginalia for the next provision
                if heading_level == 6:
                    # Check if next non-empty line contains a provision
                    next_provision_found = False
                    for next_line_num in range(line_num + 1, len(lines) + 1):
                        if next_line_num > len(lines):
                            break
                        next_line = lines[next_line_num - 1].strip()
                        if not next_line:
                            continue
                        # Check if next line is a provision (section or article)
                        if (re.search(r'\[⟨§\s*\d+(?:\s*[a-z])*\s*\.?⟩\]', next_line) or 
                            re.search(r'\[⟨Art\.\s*\d+[a-z]*⟩\]', next_line)):
                            next_provision_found = True
                            break
                        else:
                            # If next non-empty line is not a provision, break
                            break
                    
                    if next_provision_found:
                        # This h6 is marginalia for the next provision
                        # Save current provision if exists (marginalia marks end of previous provision)
                        if current_provision:
                            provisions.append(_finalize_provision(current_provision, current_content, sequence - 1))
                            current_provision = None
                            current_content = []
                        
                        # Store marginalia to be included with next provision
                        pending_marginalia = marginalia_line
                        logger.debug(f"Found marginalia for next provision at line {line_num}: {marginalia_line[:50]}...")
                        continue
                
                # All other headings (h1-h5 and h6 that don't precede provisions) end the current provision
                if current_provision:
                    provisions.append(_finalize_provision(current_provision, current_content, sequence - 1))
                    current_provision = None
                    current_content = []
                
                # Clear pending marginalia as we hit a heading that ends provisions
                pending_marginalia = None
                logger.debug(f"Found heading (h{heading_level}) that ends provision at line {line_num}: {heading_text[:50]}...")
                continue
            
            # Add line to current provision content
            if current_provision and (current_content or line):
                current_content.append(original_line)
        
        # Don't forget the last provision
        if current_provision:
            provisions.append(_finalize_provision(current_provision, current_content, sequence - 1))
        
        logger.info(f"Extracted {len(provisions)} provisions from {filename_stem}")
        return provisions
        
    except Exception as e:
        logger.error(f"Error extracting provisions from {filename_stem}: {e}")
        return []


def _finalize_provision(provision_data: Dict[str, Any], content_lines: List[str], sequence: int) -> Dict[str, Any]:
    """Finalize a provision by combining content and extracting hyperlinks.
    
    Args:
        provision_data: Partial provision data containing provision_number and provision_type
        content_lines: List of content lines
        sequence: Sequence number
        
    Returns:
        Complete provision dictionary
    """
    # Combine content lines
    provision_text = '\n'.join(content_lines).strip()
    
    # Extract static and dynamic hyperlinks
    static_url, dynamic_url = extract_hyperlinks(provision_text)
    
    return {
        'provision_number': provision_data['provision_number'],
        'provision_type': provision_data.get('provision_type', 'unknown'),
        'provision_markdown': provision_text,
        'provision_sequence': sequence,
        'provision_hyperlink_static': static_url,
        'provision_hyperlink_dynamic': dynamic_url,
        'is_marginalia': False
    }


def extract_hyperlinks(text: str) -> tuple[Optional[str], Optional[str]]:
    """Extract static and dynamic hyperlinks from text content.
    
    Args:
        text: Text content to search for hyperlinks
        
    Returns:
        Tuple of (static_url, dynamic_url) where:
        - static_url: The original URL from the markdown link
        - dynamic_url: The URL converted to use "latest" version
        
    Example:
        Input: "[⟨§ 1.⟩](https://www.zhlaw.ch/col-zh/722.1-085.html#seq-0-prov-1)"
        Output: ("https://www.zhlaw.ch/col-zh/722.1-085.html#seq-0-prov-1", 
                "https://www.zhlaw.ch/col-zh/722.1/latest#seq-0-prov-1")
    """
    try:
        # Find markdown links [text](url) - looking specifically for provision links
        provision_md_links = re.findall(r'\[⟨[^⟩]+⟩\]\(([^)]+)\)', text)
        
        if not provision_md_links:
            return None, None
        
        # Take the first provision link found (should typically be only one per provision)
        static_url = provision_md_links[0]
        
        # Convert static URL to dynamic URL
        # Pattern: https://www.zhlaw.ch/col-zh/722.1-085.html#seq-0-prov-1
        # Target:  https://www.zhlaw.ch/col-zh/722.1/latest#seq-0-prov-1
        dynamic_url = _convert_to_dynamic_url(static_url)
        
        return static_url, dynamic_url
        
    except Exception as e:
        logger.warning(f"Error extracting hyperlinks: {e}")
        return None, None


def _convert_to_dynamic_url(static_url: str) -> Optional[str]:
    """Convert a static URL to a dynamic URL using 'latest' version.
    
    Args:
        static_url: Static URL like "https://www.zhlaw.ch/col-zh/722.1-085.html#seq-0-prov-1"
        
    Returns:
        Dynamic URL like "https://www.zhlaw.ch/col-zh/722.1/latest#seq-0-prov-1"
    """
    try:
        # Match pattern: https://www.zhlaw.ch/col-zh/ORDNUNGSNUMMER-NACHTRAGSNUMMER.html#anchor
        match = re.match(r'(https://www\.zhlaw\.ch/col-zh/)([^-]+)-[^.]+\.html(#.+)?', static_url)
        
        if match:
            base_url = match.group(1)
            ordnungsnummer = match.group(2)
            anchor = match.group(3) or ""
            
            # Construct dynamic URL
            dynamic_url = f"{base_url}{ordnungsnummer}/latest{anchor}"
            return dynamic_url
        
        # If pattern doesn't match, return the original URL
        logger.warning(f"Could not convert static URL to dynamic: {static_url}")
        return static_url
        
    except Exception as e:
        logger.warning(f"Error converting URL to dynamic: {e}")
        return static_url


def parse_filename(filename: str) -> Dict[str, str]:
    """Parse filename to extract ordnungsnummer and nachtragsnummer.
    
    Args:
        filename: Markdown filename (e.g., "131.1-118.md")
        
    Returns:
        Dictionary with ordnungsnummer and nachtragsnummer
    """
    try:
        # Remove .md extension
        basename = filename.replace('.md', '')
        
        # Split on last hyphen
        if '-' in basename:
            parts = basename.rsplit('-', 1)
            return {
                'ordnungsnummer': parts[0],
                'nachtragsnummer': parts[1]
            }
        else:
            logger.warning(f"Could not parse filename: {filename}")
            return {}
            
    except Exception as e:
        logger.error(f"Error parsing filename {filename}: {e}")
        return {}


def extract_law_data(parsed_data: Dict[str, Any], collection: str) -> Dict[str, Any]:
    """Extract law table data from parsed markdown.
    
    Args:
        parsed_data: Parsed markdown data
        collection: Collection identifier (e.g., "zh", "ch")
        
    Returns:
        Dictionary with law table fields
    """
    metadata = parsed_data.get('metadata', {})
    file_info = parsed_data.get('file_info', {})
    
    ordnungsnummer = metadata.get('ordnungsnummer', file_info.get('ordnungsnummer', ''))
    col_ordnungsnummer = f"{collection}_{ordnungsnummer}"
    
    return {
        'collection': collection,
        'ordnungsnummer': ordnungsnummer,
        'col_ordnungsnummer': col_ordnungsnummer,
        'erlasstitel': metadata.get('erlasstitel'),
        'abkuerzung': metadata.get('abkuerzung'),
        'kurztitel': metadata.get('kurztitel'),
        'category_folder_id': safe_int_conversion(metadata.get('category_folder_id')),
        'category_folder_name': metadata.get('category_folder_name'),
        'category_section_id': safe_int_conversion(metadata.get('category_section_id')),
        'category_section_name': metadata.get('category_section_name'),
        'category_subsection_id': safe_int_conversion(metadata.get('category_subsection_id')),
        'category_subsection_name': metadata.get('category_subsection_name'),
        'dynamic_source': metadata.get('dynamic_source'),
        'zhlaw_url_dynamic': metadata.get('zhlaw_url_dynamic')
    }


def extract_version_data(parsed_data: Dict[str, Any], collection: str) -> Dict[str, Any]:
    """Extract version table data from parsed markdown.
    
    Args:
        parsed_data: Parsed markdown data
        collection: Collection identifier (e.g., "zh", "ch")
        
    Returns:
        Dictionary with version table fields
    """
    metadata = parsed_data.get('metadata', {})
    file_info = parsed_data.get('file_info', {})
    
    ordnungsnummer = metadata.get('ordnungsnummer', file_info.get('ordnungsnummer', ''))
    nachtragsnummer = metadata.get('nachtragsnummer', file_info.get('nachtragsnummer', ''))
    
    col_ordnungsnummer = f"{collection}_{ordnungsnummer}"
    col_ordnungsnummer_nachtragsnummer = f"{collection}_{ordnungsnummer}_{nachtragsnummer}"
    
    return {
        'collection': collection,
        'col_ordnungsnummer': col_ordnungsnummer,
        'nachtragsnummer': nachtragsnummer,
        'col_ordnungsnummer_nachtragsnummer': col_ordnungsnummer_nachtragsnummer,
        'numeric_nachtragsnummer': safe_float_conversion(metadata.get('numeric_nachtragsnummer')),
        'erlassdatum': parse_date_safe(metadata.get('erlassdatum', ''), 'erlassdatum'),
        'in_force': convert_boolean_safe(metadata.get('in_force')),
        'inkraftsetzungsdatum': parse_date_safe(metadata.get('inkraftsetzungsdatum', ''), 'inkraftsetzungsdatum'),
        'aufhebungsdatum': parse_date_safe(metadata.get('aufhebungsdatum', ''), 'aufhebungsdatum'),
        'law_page_url': metadata.get('law_page_url'),
        'law_text_redirect': metadata.get('law_text_redirect'),
        'law_text_url': metadata.get('law_text_url'),
        'publikationsdatum': parse_date_safe(metadata.get('publikationsdatum', ''), 'publikationsdatum'),
        'full_version_text_markdown': parsed_data.get('full_text', '')
    }