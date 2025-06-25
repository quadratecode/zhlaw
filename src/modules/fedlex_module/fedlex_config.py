"""Configuration settings for the Fedlex module.

This module centralizes all configuration parameters used across the Fedlex
processing pipeline, including API endpoints, timeouts, file paths, and
processing parameters.

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import os
from pathlib import Path

# --- SPARQL Configuration ---
SPARQL_ENDPOINT = "https://fedlex.data.admin.ch/sparqlendpoint"
SPARQL_TIMEOUT = 60  # Timeout for SPARQL requests in seconds
SPARQL_MAX_RETRIES = 3  # Maximum number of retry attempts for failed requests
SPARQL_BATCH_SIZE = 20  # Number of SR notations to process in a single batch
SPARQL_DELAY_BETWEEN_REQUESTS = 0.5  # Delay between SPARQL requests in seconds

# --- File Download Configuration ---
DOWNLOAD_TIMEOUT = 60  # Timeout for file downloads in seconds
DOWNLOAD_MAX_RETRIES = 3  # Maximum retries for failed downloads
DOWNLOAD_DELAY_BETWEEN_FILES = 0.1  # Delay between file downloads
DOWNLOAD_BATCH_DELAY = 0.2  # Additional delay between batches

# --- Directory Structure ---
# Determine project root relative to this config file
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DATA_ROOT = PROJECT_ROOT / "data" / "fedlex"
BASE_FILES_DIR = DATA_ROOT / "fedlex_files"
BASE_DATA_DIR = DATA_ROOT / "fedlex_data"
HIERARCHY_FILE = BASE_DATA_DIR / "fedlex_cc_folders_hierarchy.json"

# --- File Naming Patterns ---
RAW_HTML_FILENAME_PATTERN = "{sr}-{date}-raw.html"
METADATA_FILENAME_PATTERN = "{sr}-{date}-metadata.json"
MERGED_HTML_FILENAME_PATTERN = "{sr}-{date}-merged.html"

# --- Date Format ---
DATE_FORMAT = "YYYYMMDD"  # Standard date format used throughout the system

# --- Logging Configuration ---
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL = "INFO"

# --- Processing Parameters ---
CONCURRENT_WORKERS = 4  # Number of concurrent workers for parallel processing
MEMORY_LIMIT_MB = 1024  # Memory limit for processing large files

# --- SPARQL Query Templates ---
# These are partial templates that can be customized by the sparql_client
SPARQL_HEADERS = {
    "Accept": "application/sparql-results+json"
}

# --- URL Patterns ---
# Pattern to extract public URL from filestore URL
FILESTORE_URL_PATTERN = r"https://fedlex\.data\.admin\.ch/filestore/fedlex\.data\.admin\.ch(/eli/cc/\d+/[^/]+)/\d+/([^/]+)/html/.*\.html$"
PUBLIC_URL_TEMPLATE = "https://www.fedlex.admin.ch{path}/{lang}"

# --- Validation Patterns ---
SR_NUMBER_PATTERN = r"^[0-9.]+$"  # Pattern for valid SR numbers
DATE_FOLDER_PATTERN = r"\d{8}"  # Pattern for date folders (YYYYMMDD)

# --- Default Metadata Structure ---
DEFAULT_METADATA = {
    "doc_info": {
        "law_page_url": "",
        "law_text_url": "",
        "law_text_redirect": "",
        "nachtragsnummer": "",
        "numeric_nachtragsnummer": None,
        "erlassdatum": "",
        "inkraftsetzungsdatum": "",
        "publikationsdatum": "",
        "aufhebungsdatum": "",
        "in_force": False,
        "bandnummer": "",
        "hinweise": "",
        "erlasstitel": "",
        "ordnungsnummer": "",
        "kurztitel": "",
        "abkuerzung": "",
        "category": {
            "folder": None,
            "section": None,
            "subsection": None
        },
        "dynamic_source": "",
        "zhlaw_url_dynamic": "",
        "versions": {
            "older_versions": [],
            "newer_versions": []
        }
    },
    "process_steps": {
        "download": "",
        "process": ""
    }
}

# --- Category Assignment Configuration ---
INTERNATIONAL_LAW_PREFIX = "0."  # Prefix for international law SR numbers
CATEGORY_BRANCH_INTERNATIONAL = "A"
CATEGORY_BRANCH_NATIONAL = "B"

def get_file_path(sr_number: str, date: str, file_type: str) -> Path:
    """Generate file path for a given SR number, date, and file type.
    
    Args:
        sr_number: The SR notation (e.g., "101.1")
        date: The date in YYYYMMDD format
        file_type: One of "raw", "metadata", or "merged"
        
    Returns:
        Path object for the file
    """
    version_dir = BASE_FILES_DIR / sr_number / date
    
    if file_type == "raw":
        filename = RAW_HTML_FILENAME_PATTERN.format(sr=sr_number, date=date)
    elif file_type == "metadata":
        filename = METADATA_FILENAME_PATTERN.format(sr=sr_number, date=date)
    elif file_type == "merged":
        filename = MERGED_HTML_FILENAME_PATTERN.format(sr=sr_number, date=date)
    else:
        raise ValueError(f"Unknown file type: {file_type}")
    
    return version_dir / filename

def ensure_directories():
    """Ensure all required directories exist."""
    BASE_FILES_DIR.mkdir(parents=True, exist_ok=True)
    BASE_DATA_DIR.mkdir(parents=True, exist_ok=True)