"""
File operation utilities for ZHLaw processing system.

This module provides common file operations with consistent error handling
and logging, reducing code duplication across the codebase.
"""

import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional, List
import arrow

from src.logging_config import get_logger
from src.exceptions import (
    FileProcessingException, JSONParsingException, MetadataException
)
from src.constants import DEFAULT_ENCODING

logger = get_logger(__name__)


class FileOperations:
    """Centralized file operations with consistent error handling."""
    
    @staticmethod
    def read_json(file_path: Path, encoding: str = DEFAULT_ENCODING) -> Dict[str, Any]:
        """
        Read and parse a JSON file with proper error handling.
        
        Args:
            file_path: Path to the JSON file
            encoding: File encoding (default: utf-8)
            
        Returns:
            Parsed JSON data as dictionary
            
        Raises:
            FileProcessingException: If file cannot be read
            JSONParsingException: If JSON is invalid
        """
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                data = json.load(f)
            logger.debug(f"Successfully read JSON from: {file_path}")
            return data
        except FileNotFoundError as e:
            raise FileProcessingException(file_path, "read", e)
        except json.JSONDecodeError as e:
            raise JSONParsingException(str(file_path), e)
        except Exception as e:
            raise FileProcessingException(file_path, "read JSON", e)
    
    @staticmethod
    def write_json(
        file_path: Path, 
        data: Dict[str, Any], 
        encoding: str = DEFAULT_ENCODING,
        indent: int = 4,
        ensure_ascii: bool = False
    ) -> None:
        """
        Write data to a JSON file with proper error handling.
        
        Args:
            file_path: Path to write the JSON file
            data: Data to serialize as JSON
            encoding: File encoding (default: utf-8)
            indent: JSON indentation level
            ensure_ascii: Whether to escape non-ASCII characters
            
        Raises:
            FileProcessingException: If file cannot be written
        """
        try:
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding=encoding) as f:
                json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)
            logger.debug(f"Successfully wrote JSON to: {file_path}")
        except Exception as e:
            raise FileProcessingException(file_path, "write JSON", e)
    
    @staticmethod
    def ensure_directory(directory: Path) -> None:
        """
        Ensure a directory exists, creating it if necessary.
        
        Args:
            directory: Path to the directory
            
        Raises:
            FileProcessingException: If directory cannot be created
        """
        try:
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured directory exists: {directory}")
        except Exception as e:
            raise FileProcessingException(directory, "create directory", e)
    
    @staticmethod
    def safe_delete(file_path: Path, missing_ok: bool = True) -> bool:
        """
        Safely delete a file with proper error handling.
        
        Args:
            file_path: Path to the file to delete
            missing_ok: If True, don't raise error if file doesn't exist
            
        Returns:
            True if file was deleted, False if it didn't exist
            
        Raises:
            FileProcessingException: If file cannot be deleted
        """
        try:
            if file_path.is_dir():
                shutil.rmtree(file_path)
                logger.debug(f"Removed directory: {file_path}")
                return True
            else:
                file_path.unlink(missing_ok=missing_ok)
                logger.debug(f"Removed file: {file_path}")
                return True
        except FileNotFoundError:
            if not missing_ok:
                raise FileProcessingException(file_path, "delete", FileNotFoundError())
            return False
        except Exception as e:
            raise FileProcessingException(file_path, "delete", e)
    
    @staticmethod
    def file_exists(file_path: Path) -> bool:
        """
        Check if a file exists with logging.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if file exists, False otherwise
        """
        exists = file_path.exists()
        if not exists:
            logger.debug(f"File does not exist: {file_path}")
        return exists
    
    @staticmethod
    def copy_file(source: Path, destination: Path, overwrite: bool = False) -> None:
        """
        Copy a file with proper error handling.
        
        Args:
            source: Source file path
            destination: Destination file path
            overwrite: Whether to overwrite existing file
            
        Raises:
            FileProcessingException: If copy operation fails
        """
        try:
            if destination.exists() and not overwrite:
                raise FileProcessingException(
                    destination, 
                    "copy", 
                    FileExistsError("Destination already exists")
                )
            
            # Ensure destination directory exists
            destination.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.copy2(source, destination)
            logger.debug(f"Copied {source} to {destination}")
        except Exception as e:
            if not isinstance(e, FileProcessingException):
                raise FileProcessingException(source, f"copy to {destination}", e)
            raise


class MetadataHandler:
    """Handle metadata file operations with standard structure."""
    
    @staticmethod
    def load_metadata(metadata_path: Path) -> Dict[str, Any]:
        """
        Load metadata from a JSON file.
        
        Args:
            metadata_path: Path to metadata file
            
        Returns:
            Metadata dictionary
            
        Raises:
            MetadataException: If metadata cannot be loaded
        """
        try:
            return FileOperations.read_json(metadata_path)
        except (FileProcessingException, JSONParsingException) as e:
            raise MetadataException("load", metadata_path, {"error": str(e)})
    
    @staticmethod
    def save_metadata(metadata_path: Path, metadata: Dict[str, Any]) -> None:
        """
        Save metadata to a JSON file.
        
        Args:
            metadata_path: Path to save metadata
            metadata: Metadata dictionary
            
        Raises:
            MetadataException: If metadata cannot be saved
        """
        try:
            FileOperations.write_json(metadata_path, metadata)
        except FileProcessingException as e:
            raise MetadataException("save", metadata_path, {"error": str(e)})
    
    @staticmethod
    def update_process_step(
        metadata_path: Path, 
        step_name: str, 
        timestamp: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update a processing step timestamp in metadata.
        
        Args:
            metadata_path: Path to metadata file
            step_name: Name of the processing step
            timestamp: Timestamp to set (uses current time if None)
            
        Returns:
            Updated metadata dictionary
            
        Raises:
            MetadataException: If update fails
        """
        try:
            metadata = MetadataHandler.load_metadata(metadata_path)
            
            # Ensure process_steps exists
            if "process_steps" not in metadata:
                metadata["process_steps"] = {}
            
            # Update timestamp
            if timestamp is None:
                timestamp = arrow.now().format("YYYYMMDD-HHmmss")
            
            metadata["process_steps"][step_name] = timestamp
            
            # Save updated metadata
            MetadataHandler.save_metadata(metadata_path, metadata)
            logger.info(f"Updated process step '{step_name}' in {metadata_path.name}")
            
            return metadata
            
        except MetadataException:
            raise
        except Exception as e:
            raise MetadataException(
                f"update process step '{step_name}'", 
                metadata_path, 
                {"error": str(e)}
            )
    
    @staticmethod
    def is_step_completed(metadata: Dict[str, Any], step_name: str) -> bool:
        """
        Check if a processing step has been completed.
        
        Args:
            metadata: Metadata dictionary
            step_name: Name of the processing step
            
        Returns:
            True if step is completed (has non-empty timestamp)
        """
        return bool(
            metadata.get("process_steps", {}).get(step_name, "").strip()
        )


class PathBuilder:
    """Build common file paths with consistent patterns."""
    
    @staticmethod
    def build_file_path(
        base_dir: Path, 
        *parts: str, 
        create_parent: bool = False
    ) -> Path:
        """
        Build a file path from parts with optional parent directory creation.
        
        Args:
            base_dir: Base directory
            *parts: Path components
            create_parent: Whether to create parent directories
            
        Returns:
            Complete file path
        """
        file_path = base_dir
        for part in parts:
            file_path = file_path / part
        
        if create_parent:
            file_path.parent.mkdir(parents=True, exist_ok=True)
        
        return file_path
    
    @staticmethod
    def get_metadata_path(file_path: Path, suffix: str = "-metadata.json") -> Path:
        """
        Get the metadata file path for a given file.
        
        Args:
            file_path: Original file path
            suffix: Metadata file suffix
            
        Returns:
            Path to metadata file
        """
        return file_path.with_suffix("").parent / f"{file_path.stem}{suffix}"
    
    @staticmethod
    def get_variant_paths(original_path: Path, variants: Dict[str, str]) -> Dict[str, Path]:
        """
        Generate variant file paths from an original path.
        
        Args:
            original_path: Original file path
            variants: Dict mapping variant names to suffixes
            
        Returns:
            Dict mapping variant names to paths
        """
        base = original_path.with_suffix("")
        return {
            name: base.parent / f"{base.name}{suffix}"
            for name, suffix in variants.items()
        }


# Convenience functions
def read_json(file_path: Path) -> Dict[str, Any]:
    """Convenience function to read JSON file."""
    return FileOperations.read_json(file_path)


def write_json(file_path: Path, data: Dict[str, Any]) -> None:
    """Convenience function to write JSON file."""
    FileOperations.write_json(file_path, data)


def ensure_directory(directory: Path) -> None:
    """Convenience function to ensure directory exists."""
    FileOperations.ensure_directory(directory)