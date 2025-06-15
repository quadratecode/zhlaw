"""
Type definitions for ZHLaw processing system.

This module provides type aliases and TypedDict definitions for complex
data structures used throughout the codebase.
"""

from typing import (
    TypedDict, Dict, List, Optional, Union, Any, Literal, 
    Callable, Protocol, runtime_checkable
)
from pathlib import Path
from datetime import datetime


# Basic type aliases
JSONDict = Dict[str, Any]
FilePath = Union[str, Path]
ProcessingStep = str
Timestamp = str


# Law data structures
class LawMetadata(TypedDict, total=False):
    """Type definition for law metadata."""
    id: str
    ordnungsnummer: str
    erlasstitel: str
    short_title: Optional[str]
    abbreviation: Optional[str]
    category: Optional[str]
    type: Optional[str]
    status: str
    in_force: bool
    date_created: str
    date_modified: str
    date_published: str
    date_effective: str
    version: str
    version_history: List[str]
    references: List[str]
    referenced_by: List[str]


class ProcessingSteps(TypedDict, total=False):
    """Type definition for processing step timestamps."""
    crop_pdf: str
    call_api_law: str
    call_api_marginalia: str
    generate_html: str
    call_ai: str
    merge_marginalia: str
    create_hyperlinks: str


class DocumentInfo(TypedDict, total=False):
    """Type definition for document information."""
    title: str
    ordnungsnummer: str
    abbreviation: Optional[str]
    type: str
    status: str
    version: str
    url: Optional[str]
    pdf_url: Optional[str]
    metadata_path: str
    
    
class MetadataDocument(TypedDict):
    """Complete metadata document structure."""
    doc_info: DocumentInfo
    process_steps: ProcessingSteps
    processing_errors: Optional[List[str]]
    last_updated: str


# Dispatch data structures
class AffairInfo(TypedDict, total=False):
    """Type definition for parliamentary affair information."""
    kr_nr: str
    vorlagen_nr: str
    title: str
    affair_type: str
    affair_status: str
    pdf_url: str
    pdf_path: Optional[str]
    affair_steps: List[Dict[str, str]]
    last_affair_step_date: str
    last_affair_step_type: str
    regex_changes: Dict[str, List[str]]
    ai_changes: Dict[str, List[str]]


class DispatchData(TypedDict):
    """Type definition for dispatch data."""
    krzh_dispatch_date: str
    affairs: List[AffairInfo]


# HTML structures
class HTMLElement(TypedDict, total=False):
    """Type definition for HTML element data."""
    tag: str
    content: Optional[str]
    attributes: Dict[str, str]
    classes: List[str]
    children: List['HTMLElement']


# API response types
class AdobeAPIResponse(TypedDict):
    """Type definition for Adobe API response."""
    elements: List[JSONDict]
    pages: List[JSONDict]
    metadata: JSONDict


class OpenAIResponse(TypedDict):
    """Type definition for OpenAI API response."""
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]
    model: str


# Processing results
class ProcessingResult(TypedDict):
    """Type definition for processing results."""
    success: bool
    message: str
    data: Optional[Any]
    error: Optional[str]
    processing_time: Optional[float]


class BatchProcessingResult(TypedDict):
    """Type definition for batch processing results."""
    total: int
    success: int
    failed: int
    errors: List[Dict[str, str]]
    results: List[ProcessingResult]


# Callback types
ProgressCallback = Callable[[int, int], None]
ErrorCallback = Callable[[Exception], None]
TransformCallback = Callable[[JSONDict], JSONDict]


# Protocol definitions for duck typing
@runtime_checkable
class Processor(Protocol):
    """Protocol for processor classes."""
    
    def process(self, *args: Any, **kwargs: Any) -> Any:
        """Process method that all processors must implement."""
        ...
    
    def get_statistics(self) -> Dict[str, int]:
        """Get processing statistics."""
        ...


@runtime_checkable
class DataLoader(Protocol):
    """Protocol for data loader classes."""
    
    def load(self, path: FilePath) -> JSONDict:
        """Load data from a file."""
        ...
    
    def save(self, data: JSONDict, path: FilePath) -> None:
        """Save data to a file."""
        ...


# Configuration types
ConfigValue = Union[str, int, float, bool, List[str], Dict[str, Any]]
ConfigDict = Dict[str, ConfigValue]


# Search and indexing types
class SearchResult(TypedDict):
    """Type definition for search results."""
    id: str
    title: str
    snippet: str
    score: float
    url: str
    metadata: Dict[str, Any]


class IndexEntry(TypedDict):
    """Type definition for search index entries."""
    id: str
    title: str
    content: str
    url: str
    type: str
    date: str
    metadata: JSONDict


# Status types
ProcessingStatus = Literal["pending", "in_progress", "completed", "failed", "skipped"]
DocumentStatus = Literal["draft", "published", "archived", "deprecated"]
AffairStatus = Literal["pending", "in_committee", "approved", "rejected", "withdrawn"]


# Type guards
def is_metadata_document(obj: Any) -> bool:
    """Check if object is a valid MetadataDocument."""
    return (
        isinstance(obj, dict) and
        "doc_info" in obj and
        "process_steps" in obj and
        isinstance(obj.get("doc_info"), dict) and
        isinstance(obj.get("process_steps"), dict)
    )


def is_law_metadata(obj: Any) -> bool:
    """Check if object is valid LawMetadata."""
    return (
        isinstance(obj, dict) and
        "ordnungsnummer" in obj and
        "erlasstitel" in obj
    )


# Utility type for version comparison
class Version(TypedDict):
    """Type definition for version information."""
    number: str
    date: str
    changes: List[str]
    is_current: bool