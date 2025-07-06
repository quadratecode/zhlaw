"""
Constants module for ZHLaw processing system.

This module contains string constants, enums, and other immutable values
used throughout the application.

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

from enum import Enum
from typing import Final


# Collection types
class CollectionType(str, Enum):
    """Types of law collections."""

    ZHLEX = "zhlex"
    FEDLEX = "fedlex"
    CH = "ch"
    ZH = "zh"


# Processing status
class ProcessingStatus(str, Enum):
    """Status values for processing steps."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# Document types
class DocumentType(str, Enum):
    """Types of legal documents."""

    LAW = "law"
    ORDINANCE = "ordinance"
    DISPATCH = "dispatch"
    INITIATIVE = "initiative"
    AMENDMENT = "amendment"


# File types
class FileType(str, Enum):
    """Supported file types."""

    PDF = "pdf"
    HTML = "html"
    JSON = "json"
    XML = "xml"
    TXT = "txt"


# Language codes
class Language(str, Enum):
    """Supported languages."""

    DE = "de"
    FR = "fr"
    IT = "it"
    EN = "en"


# Common string constants
class Messages:
    """Common messages and strings."""

    # Error messages
    ERROR_FILE_NOT_FOUND: Final = "File not found: {}"
    ERROR_API_FAILURE: Final = "API request failed: {}"
    ERROR_INVALID_JSON: Final = "Invalid JSON data: {}"
    ERROR_PROCESSING_FAILED: Final = "Processing failed for: {}"

    # Success messages
    SUCCESS_FILE_CREATED: Final = "Successfully created: {}"
    SUCCESS_PROCESSING_COMPLETE: Final = "Processing completed for: {}"
    SUCCESS_API_CALL: Final = "API call successful: {}"

    # Info messages
    INFO_PROCESSING_START: Final = "Starting processing for: {}"
    INFO_SKIPPING_FILE: Final = "Skipping already processed file: {}"
    INFO_RETRY_ATTEMPT: Final = "Retry attempt {} of {}"


# HTML/CSS classes and IDs
class HTMLClasses:
    """HTML CSS class names."""

    CONTAINER: Final = "container"
    CONTENT: Final = "content"
    NAVIGATION: Final = "navigation"
    ARTICLE: Final = "article"
    SECTION: Final = "section"
    HEADER: Final = "header"
    FOOTER: Final = "footer"

    # Law-specific classes
    LAW_TITLE: Final = "law-title"
    LAW_CONTENT: Final = "law-content"
    LAW_METADATA: Final = "law-metadata"
    LAW_VERSION: Final = "law-version"

    # Component classes
    BUTTON: Final = "btn"
    BUTTON_PRIMARY: Final = "btn-primary"
    BUTTON_SECONDARY: Final = "btn-secondary"
    LINK: Final = "link"
    ACTIVE: Final = "active"


# Data attributes
class DataAttributes:
    """HTML data attributes."""

    LAW_ID: Final = "data-law-id"
    VERSION: Final = "data-version"
    DATE: Final = "data-date"
    TYPE: Final = "data-type"
    STATUS: Final = "data-status"


# Metadata keys
class MetadataKeys:
    """JSON metadata field names."""

    # Basic metadata
    ID: Final = "id"
    TITLE: Final = "title"
    SHORT_TITLE: Final = "short_title"
    ABBREVIATION: Final = "abbreviation"
    TYPE: Final = "type"
    STATUS: Final = "status"

    # Dates
    DATE_CREATED: Final = "date_created"
    DATE_MODIFIED: Final = "date_modified"
    DATE_PUBLISHED: Final = "date_published"
    DATE_EFFECTIVE: Final = "date_effective"

    # Processing metadata
    PROCESSING_STEPS: Final = "processing_steps"
    PROCESSING_ERRORS: Final = "processing_errors"
    PROCESSING_TIMESTAMP: Final = "processing_timestamp"

    # Version metadata
    VERSION: Final = "version"
    VERSION_HISTORY: Final = "version_history"
    PREVIOUS_VERSION: Final = "previous_version"
    NEXT_VERSION: Final = "next_version"

    # Content metadata
    CONTENT_HASH: Final = "content_hash"
    WORD_COUNT: Final = "word_count"
    PAGE_COUNT: Final = "page_count"

    # References
    REFERENCES: Final = "references"
    REFERENCED_BY: Final = "referenced_by"
    RELATED_DOCUMENTS: Final = "related_documents"


# Regular expressions patterns
class Patterns:
    """Common regex patterns."""

    DATE_DD_MM_YYYY: Final = r"\d{2}\.\d{2}\.\d{4}"
    DATE_YYYY_MM_DD: Final = r"\d{4}-\d{2}-\d{2}"
    LAW_NUMBER: Final = r"\d{3}\.\d{1,3}"
    ARTICLE_NUMBER: Final = r"Art\.\s*\d+[a-z]?"
    PARAGRAPH_NUMBER: Final = r"§\s*\d+"
    URL: Final = (
        r"https?://[\w\.-]+(?:\.[\w\.-]+)+[\w\-\._~:/?#[\]@!\$&'\(\)\*\+,;=.]+$"
    )

    # Enumeration patterns
    # Basic components for building enumeration patterns
    ROMAN_NUMERALS: Final = r"[IVXLCDM]+"  # Roman numerals
    SINGLE_LETTER: Final = r"[a-zA-Z]"  # Single letter
    NUMBERS: Final = r"\d+"  # One or more digits

    # Complete enumeration markers (just the marker, no following text)
    ENUM_LETTER_PERIOD: Final = r"^[a-zA-Z]\.$"  # a., b., etc.
    ENUM_NUMBER_PERIOD: Final = r"^\d+\.$"  # 1., 2., 12., etc.
    ENUM_ROMAN_PERIOD: Final = r"^[IVXLCDM]+\.$"  # I., II., III., etc.
    ENUM_ROMAN_SMALL_PERIOD: Final = r"^[ivxlcdm]+\.$"  # i., ii., iii., etc.
    ENUM_LETTER_PAREN: Final = r"^[a-zA-Z]\)$"  # a), b), etc.
    ENUM_NUMBER_PAREN: Final = r"^\d+\)$"  # 1), 2), etc.
    ENUM_ROMAN_PAREN: Final = r"^[IVXLCDM]+\)$"  # I), II), etc.

    # Combined pattern for any enumeration marker (capturing groups)
    ENUM_MARKER: Final = r"^([IVXLCDM]+|[a-zA-Z]|\d+)[\.\)]$"

    # Enumeration patterns with optional following text
    ENUM_WITH_TEXT: Final = r"^([IVXLCDM]+|[a-zA-Z]|\d+)[\.\)](\s.*)?$"

    # Pattern for splitting text containing "wenn" followed by enumeration
    WENN_ENUM_SPLIT: Final = r"^(.*?)(wenn)\s+([IVXLCDM]+|[a-zA-Z]|\d+)[\.\)](.*)$"

    # Subprovision pattern (numbers with optional suffixes)
    SUBPROVISION: Final = r"^(\d+)(bis|ter|quater|quinquies|sexies|septies|octies)?$"


# Special date constant
RESET_DATE_COMMENT: Final = (
    "Due to incorrect operation on live data, all timestamps before 20250308 have been reset"
)


# MIME types
class MimeTypes:
    """MIME type constants."""

    PDF: Final = "application/pdf"
    JSON: Final = "application/json"
    HTML: Final = "text/html"
    XML: Final = "text/xml"
    TEXT: Final = "text/plain"


# HTTP status codes
class HTTPStatus:
    """Common HTTP status codes."""

    OK: Final = 200
    CREATED: Final = 201
    BAD_REQUEST: Final = 400
    UNAUTHORIZED: Final = 401
    FORBIDDEN: Final = 403
    NOT_FOUND: Final = 404
    INTERNAL_ERROR: Final = 500
    SERVICE_UNAVAILABLE: Final = 503


# Encoding
DEFAULT_ENCODING: Final = "utf-8"


# Size limits (in bytes)
class SizeLimits:
    """File and content size limits."""

    MAX_FILE_SIZE: Final = 100 * 1024 * 1024  # 100 MB
    MAX_JSON_SIZE: Final = 10 * 1024 * 1024  # 10 MB
    MAX_LOG_SIZE: Final = 50 * 1024 * 1024  # 50 MB


# Cache settings
class CacheSettings:
    """Cache configuration constants."""

    DEFAULT_TTL: Final = 3600  # 1 hour in seconds
    MAX_CACHE_SIZE: Final = 1000  # Maximum number of items
    CACHE_VERSION: Final = "1.0"
