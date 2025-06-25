"""Fedlex module for processing Swiss federal laws.

This module provides a refactored, modular approach to processing federal law
data from the Fedlex system. It includes components for SPARQL querying,
file downloading, metadata management, category assignment, and version linking.

Main Components:
- SPARQLClient: Query the Fedlex SPARQL endpoint
- FileDownloader: Download HTML files and create metadata
- CategoryAssigner: Assign hierarchical categories to laws
- VersionManager: Manage version relationships
- MetadataUpdater: Update metadata with enriched information

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

from .sparql_client import SPARQLClient
from .file_downloader import FileDownloader
from .category_assigner import CategoryAssigner
from .version_manager import VersionManager
from .metadata_updater import MetadataUpdater
from .fedlex_models import (
    LawVersion, LawMetadata, CategoryInfo, Category,
    VersionSummary, VersionLinks, ProcessingResult, DownloadResult
)
from . import fedlex_config
from . import fedlex_utils

__all__ = [
    'SPARQLClient',
    'FileDownloader', 
    'CategoryAssigner',
    'VersionManager',
    'MetadataUpdater',
    'LawVersion',
    'LawMetadata',
    'CategoryInfo',
    'Category',
    'VersionSummary',
    'VersionLinks',
    'ProcessingResult',
    'DownloadResult',
    'fedlex_config',
    'fedlex_utils'
]