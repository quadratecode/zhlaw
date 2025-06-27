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
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from .date_utils import parse_date_safe, convert_boolean_safe, safe_float_conversion, safe_int_conversion

logger = logging.getLogger(__name__)


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
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            
            if not line:
                if current_content:
                    current_content.append("")  # Preserve blank lines within provisions
                continue
            
            # Check if this is a provision number (bold number on its own line)
            provision_match = re.match(r'^\*\*(\d+[a-z]?)\*\*$', line)
            if provision_match:
                # Save previous provision if exists
                if current_provision:
                    provisions.append(_finalize_provision(current_provision, current_content, sequence - 1))
                
                # Start new provision
                provision_number = provision_match.group(1)
                current_provision = {
                    'provision_number': provision_number,
                    'line_number': line_num
                }
                current_content = []
                sequence += 1
                logger.debug(f"Found provision {provision_number} at line {line_num}")
                continue
            
            # Check for marginalia (h6 headings)
            marginalia_match = re.match(r'^#{6}\s+(.+)$', line)
            if marginalia_match:
                # Save previous provision if exists
                if current_provision:
                    provisions.append(_finalize_provision(current_provision, current_content, sequence - 1))
                
                # Create marginalia provision
                marginalia_text = marginalia_match.group(1)
                marginalia_provision = {
                    'provision_number': f"marginalia_{sequence}",
                    'provision_markdown': f"###### {marginalia_text}",
                    'provision_sequence': sequence,
                    'provision_hyperlink': extract_hyperlinks(marginalia_text),
                    'is_marginalia': True
                }
                provisions.append(marginalia_provision)
                current_provision = None
                current_content = []
                sequence += 1
                logger.debug(f"Found marginalia at line {line_num}: {marginalia_text[:50]}...")
                continue
            
            # Add line to current provision content
            if current_content or line:  # Don't start with empty lines
                current_content.append(line)
        
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
        provision_data: Partial provision data
        content_lines: List of content lines
        sequence: Sequence number
        
    Returns:
        Complete provision dictionary
    """
    # Combine content lines
    provision_text = '\n'.join(content_lines).strip()
    
    # Extract hyperlinks
    hyperlinks = extract_hyperlinks(provision_text)
    
    return {
        'provision_number': provision_data['provision_number'],
        'provision_markdown': provision_text,
        'provision_sequence': sequence,
        'provision_hyperlink': hyperlinks,
        'is_marginalia': False
    }


def extract_hyperlinks(text: str) -> Optional[str]:
    """Extract hyperlinks from text content.
    
    Args:
        text: Text content to search for hyperlinks
        
    Returns:
        JSON string of hyperlinks or None if none found
    """
    try:
        # Find markdown links [text](url)
        md_links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', text)
        
        # Find provision links ⟨text⟩
        provision_links = re.findall(r'⟨([^⟩]+)⟩', text)
        
        links = []
        
        # Add markdown links
        for link_text, url in md_links:
            links.append({
                'type': 'markdown',
                'text': link_text,
                'url': url
            })
        
        # Add provision links
        for link_text in provision_links:
            links.append({
                'type': 'provision',
                'text': link_text
            })
        
        if links:
            import json
            return json.dumps(links)
        
        return None
        
    except Exception as e:
        logger.warning(f"Error extracting hyperlinks: {e}")
        return None


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