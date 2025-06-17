"""
Custom exception classes for ZHLaw processing system.

This module defines specific exception types for different error scenarios,
making error handling more precise and informative.

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

from typing import Optional, Dict, Any
from pathlib import Path


class ZHLawException(Exception):
    """Base exception class for all ZHLaw-specific exceptions."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
    
    def __str__(self):
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message


# Data Processing Exceptions

class DataProcessingException(ZHLawException):
    """Base exception for data processing errors."""
    pass


class FileProcessingException(DataProcessingException):
    """Exception raised when file processing fails."""
    
    def __init__(self, file_path: Path, operation: str, original_error: Optional[Exception] = None):
        self.file_path = file_path
        self.operation = operation
        self.original_error = original_error
        
        message = f"Failed to {operation} file: {file_path}"
        details = {
            "file": str(file_path),
            "operation": operation,
        }
        if original_error:
            details["error"] = str(original_error)
            details["error_type"] = type(original_error).__name__
        
        super().__init__(message, details)


class PDFProcessingException(FileProcessingException):
    """Exception raised when PDF processing fails."""
    
    def __init__(self, pdf_path: Path, operation: str, original_error: Optional[Exception] = None):
        super().__init__(pdf_path, f"process PDF ({operation})", original_error)


class JSONParsingException(DataProcessingException):
    """Exception raised when JSON parsing fails."""
    
    def __init__(self, source: str, original_error: Optional[Exception] = None):
        message = f"Failed to parse JSON from: {source}"
        details = {"source": source}
        if original_error:
            details["error"] = str(original_error)
        super().__init__(message, details)


class MetadataException(DataProcessingException):
    """Exception raised when metadata operations fail."""
    
    def __init__(self, operation: str, metadata_path: Optional[Path] = None, details: Optional[Dict] = None):
        message = f"Metadata operation failed: {operation}"
        error_details = {"operation": operation}
        if metadata_path:
            error_details["path"] = str(metadata_path)
        if details:
            error_details.update(details)
        super().__init__(message, error_details)


# API and Network Exceptions

class APIException(ZHLawException):
    """Base exception for API-related errors."""
    pass


class AdobeAPIException(APIException):
    """Exception raised when Adobe API operations fail."""
    
    def __init__(self, operation: str, details: Optional[Dict[str, Any]] = None):
        message = f"Adobe API operation failed: {operation}"
        super().__init__(message, details)


class OpenAIAPIException(APIException):
    """Exception raised when OpenAI API operations fail."""
    
    def __init__(self, operation: str, model: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        message = f"OpenAI API operation failed: {operation}"
        error_details = details or {}
        if model:
            error_details["model"] = model
        super().__init__(message, error_details)


class NetworkException(APIException):
    """Exception raised for network-related errors."""
    
    def __init__(self, url: str, status_code: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        message = f"Network request failed: {url}"
        error_details = {"url": url}
        if status_code:
            error_details["status_code"] = status_code
        if details:
            error_details.update(details)
        super().__init__(message, error_details)


class ScrapingException(NetworkException):
    """Exception raised when web scraping fails."""
    
    def __init__(self, url: str, reason: str, details: Optional[Dict[str, Any]] = None):
        error_details = details or {}
        error_details["reason"] = reason
        super().__init__(url, details=error_details)


# Configuration and Setup Exceptions

class ConfigurationException(ZHLawException):
    """Exception raised for configuration-related errors."""
    pass


class MissingCredentialsException(ConfigurationException):
    """Exception raised when required credentials are missing."""
    
    def __init__(self, credential_type: str, details: Optional[Dict[str, Any]] = None):
        message = f"Missing required credentials: {credential_type}"
        super().__init__(message, details)


class InvalidConfigurationException(ConfigurationException):
    """Exception raised when configuration values are invalid."""
    
    def __init__(self, config_key: str, reason: str, details: Optional[Dict[str, Any]] = None):
        message = f"Invalid configuration for '{config_key}': {reason}"
        error_details = {"config_key": config_key, "reason": reason}
        if details:
            error_details.update(details)
        super().__init__(message, error_details)


# Processing Pipeline Exceptions

class PipelineException(ZHLawException):
    """Base exception for processing pipeline errors."""
    pass


class StepAlreadyCompletedException(PipelineException):
    """Exception raised when trying to run an already completed step."""
    
    def __init__(self, step_name: str, completed_at: str):
        message = f"Processing step '{step_name}' already completed at {completed_at}"
        details = {"step": step_name, "completed_at": completed_at}
        super().__init__(message, details)


class DependencyException(PipelineException):
    """Exception raised when a required dependency is missing."""
    
    def __init__(self, dependent_step: str, required_step: str, details: Optional[Dict[str, Any]] = None):
        message = f"Step '{dependent_step}' requires '{required_step}' to be completed first"
        error_details = {
            "dependent_step": dependent_step,
            "required_step": required_step
        }
        if details:
            error_details.update(details)
        super().__init__(message, error_details)


class QuotaExceededException(APIException):
    """Exception raised when API quota is exceeded."""
    
    def __init__(self, service: str, details: Optional[Dict[str, Any]] = None):
        message = f"Quota exceeded for service: {service}"
        error_details = {"service": service}
        if details:
            error_details.update(details)
        super().__init__(message, error_details)


# Validation Exceptions

class ValidationException(ZHLawException):
    """Base exception for validation errors."""
    pass


class DateFormatException(ValidationException):
    """Exception raised when date format is invalid."""
    
    def __init__(self, date_string: str, expected_format: str, details: Optional[Dict[str, Any]] = None):
        message = f"Invalid date format: '{date_string}' (expected: {expected_format})"
        error_details = {
            "date_string": date_string,
            "expected_format": expected_format
        }
        if details:
            error_details.update(details)
        super().__init__(message, error_details)


class DocumentStructureException(ValidationException):
    """Exception raised when document structure is invalid."""
    
    def __init__(self, document_id: str, issue: str, details: Optional[Dict[str, Any]] = None):
        message = f"Invalid document structure for '{document_id}': {issue}"
        error_details = {
            "document_id": document_id,
            "issue": issue
        }
        if details:
            error_details.update(details)
        super().__init__(message, error_details)


# Utility function for re-raising with context
def raise_with_context(new_exception: ZHLawException, original_exception: Exception):
    """
    Raise a new exception while preserving the original exception context.
    
    Args:
        new_exception: The new exception to raise
        original_exception: The original exception that caused this error
    """
    # Python 3 exception chaining
    raise new_exception from original_exception