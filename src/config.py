"""
Configuration module for ZHLaw processing system.

This module centralizes all configuration values, paths, and constants
used throughout the application. It supports environment variables for
sensitive data and deployment-specific settings.
"""

import os
from pathlib import Path
from typing import Dict, Any

# Base paths
BASE_DIR = Path(__file__).parent.parent
SRC_DIR = BASE_DIR / "src"
DATA_DIR = BASE_DIR / "data"
PUBLIC_DIR = BASE_DIR / "public"
PUBLIC_TEST_DIR = BASE_DIR / "public_test"
LOGS_DIR = BASE_DIR / "logs"

# Ensure logs directory exists
LOGS_DIR.mkdir(exist_ok=True)

# Data subdirectories
class DataPaths:
    """Centralized data directory paths."""
    # ZH-Lex paths
    ZHLEX_BASE = DATA_DIR / "zhlex"
    ZHLEX_DATA = ZHLEX_BASE / "zhlex_data"
    ZHLEX_FILES = ZHLEX_BASE / "zhlex_files"
    ZHLEX_TEST_FILES = ZHLEX_BASE / "test_files"
    ZHLEX_PLACEHOLDERS = ZHLEX_BASE / "placeholders"
    
    # FedLex paths
    FEDLEX_BASE = DATA_DIR / "fedlex"
    FEDLEX_DATA = FEDLEX_BASE / "fedlex_data"
    FEDLEX_FILES = FEDLEX_BASE / "fedlex_files"
    
    # KRZH Dispatch paths
    KRZH_BASE = DATA_DIR / "krzh_dispatch"
    KRZH_DATA = KRZH_BASE / "krzh_dispatch_data"
    KRZH_FILES = KRZH_BASE / "krzh_dispatch_files"
    KRZH_SITE = KRZH_BASE / "krzh_dispatch_site"

# Static file paths
class StaticPaths:
    """Static resource paths."""
    HTML_TEMPLATES = SRC_DIR / "static_files" / "html"
    MARKUP_DIR = SRC_DIR / "static_files" / "markup"
    SERVER_SCRIPTS = SRC_DIR / "server_scripts"

# Output paths
class OutputPaths:
    """Output directory paths."""
    COL_ZH = "col-zh"
    COL_CH = "col-ch"
    DISPATCH_HTML = "dispatch.html"
    DISPATCH_FEED = "dispatch-feed.xml"

# External URLs
class URLs:
    """External service URLs."""
    # ZH.ch URLs
    ZH_BASE = "https://www.zh.ch"
    ZHLEX_API = "https://www.zh.ch/de/politik-staat/gesetze-beschluesse/gesetzessammlung/_jcr_content/main/lawcollectionsearch_312548694.zhweb-zhlex-ls.zhweb-cache.json"
    
    # KRZH Dispatch URLs
    KRZH_VERSAND_API = "https://parlzhcdws.cmicloud.ch/parlzh1/cdws/Index/KRVERSAND/searchdetails"
    KRZH_GESCHAEFT_API = "https://parlzhcdws.cmicloud.ch/parlzh5/cdws/Index/GESCHAEFT/searchdetails"
    
    # FedLex URLs
    FEDLEX_SPARQL = "https://fedlex.data.admin.ch/sparqlendpoint"
    
    # Site URLs
    SITE_PROD = "https://zhlaw.ch"
    SITE_TEST = "https://test.zhlaw.ch"
    SITE_WWW = "https://www.zhlaw.ch"

# API Configuration
class APIConfig:
    """API-related configuration."""
    # Request limits and timeouts
    KRZH_FETCH_LIMIT = 20
    SPARQL_BATCH_SIZE = 20
    REQUEST_TIMEOUT = 60  # seconds
    MAX_RETRIES = 3
    
    # Delays between requests
    WEB_REQUEST_DELAY = 0.5  # seconds
    SPARQL_REQUEST_DELAY = 0.5  # seconds
    OPENAI_POLL_DELAY = 2  # seconds
    
    # Processing limits
    KRZH_MAX_ENTRIES = 1000
    DEFAULT_LINE_LIMIT = 2000
    MAX_LINE_LENGTH = 2000
    MAX_OUTPUT_LENGTH = 30000
    
    # OpenAI settings
    OPENAI_MODEL = "gpt-4o"
    OPENAI_FILE_PURPOSE = "user_data"
    OPENAI_ASSISTANT_NAME = "Law Change Analyzer"

# File naming conventions
class FilePatterns:
    """File naming patterns and suffixes."""
    ORIGINAL_PDF = "-original.pdf"
    MODIFIED_PDF = "-modified.pdf"
    MARGINALIA_PDF = "-marginalia.pdf"
    METADATA_JSON = "-metadata.json"
    MERGED_HTML = "-merged.html"
    DIFF_PREFIX = "-diff-"

# Processing steps
class ProcessingSteps:
    """Processing pipeline step identifiers."""
    CROP_PDF = "crop_pdf"
    CALL_API_LAW = "call_api_law"
    CALL_API_MARGINALIA = "call_api_marginalia"
    GENERATE_HTML = "generate_html"
    CALL_AI = "call_ai"

# Date formats
class DateFormats:
    """Date formatting patterns."""
    ORIGINAL = "DD.MM.YYYY"
    STANDARD = "YYYYMMDD"
    TIMESTAMP = "YYYYMMDD-HHmmss"

# Priority configurations
AFFAIR_TYPE_PRIORITIES: Dict[str, int] = {
    "vorlage": 1,
    "einzelinitiative": 2,
    "behördeninitiative": 3,
    "parlamentarische initiative": 4,
}
DEFAULT_PRIORITY = 5
NO_TYPE_PRIORITY = 6

# Style constants
class StyleConstants:
    """UI styling constants."""
    DEFAULT_FONT_WEIGHT = 400
    DEFAULT_TEXT_SIZE = 12

# Environment variables
class Environment:
    """Environment variable configuration."""
    @staticmethod
    def get_openai_key() -> str:
        """Get OpenAI API key from environment."""
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        return key
    
    @staticmethod
    def get_adobe_credentials_path() -> Path:
        """Get Adobe credentials file path."""
        default_path = BASE_DIR / "credentials.json"
        custom_path = os.environ.get("ADOBE_CREDENTIALS_PATH")
        return Path(custom_path) if custom_path else default_path

# Logging configuration
class LogConfig:
    """Logging configuration."""
    LOG_FILE = LOGS_DIR / "process.log"
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    DEFAULT_LEVEL = "INFO"

# Command-line tools
class Tools:
    """External command-line tools."""
    NPX = "npx"
    PAGEFIND = "pagefind"

# Build options
class BuildOptions:
    """Site building options."""
    FOLDER_CHOICES = ["zhlex_files", "ch_files", "all_files", "test_files"]
    DB_BUILD_CHOICES = ["yes", "no"]
    PLACEHOLDER_CHOICES = ["yes", "no"]

# Helper function to get appropriate paths based on environment
def get_output_dir(test_mode: bool = False) -> Path:
    """Get the appropriate output directory based on mode."""
    return PUBLIC_TEST_DIR if test_mode else PUBLIC_DIR

def get_site_url(test_mode: bool = False) -> str:
    """Get the appropriate site URL based on mode."""
    return URLs.SITE_TEST if test_mode else URLs.SITE_PROD

# Validation function
def validate_config() -> None:
    """Validate that required directories and files exist."""
    required_dirs = [
        DATA_DIR,
        SRC_DIR,
        LOGS_DIR,
    ]
    
    for dir_path in required_dirs:
        if not dir_path.exists():
            raise FileNotFoundError(f"Required directory not found: {dir_path}")
    
    # Check for Adobe credentials if needed
    adobe_creds = Environment.get_adobe_credentials_path()
    if not adobe_creds.exists():
        print(f"Warning: Adobe credentials file not found at {adobe_creds}")

# Initialize configuration on import
if __name__ != "__main__":
    validate_config()