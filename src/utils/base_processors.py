"""
Base processor classes for ZHLaw processing system.

This module provides abstract base classes and common functionality
for different types of processors in the system.

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import arrow

from src.logging_config import get_logger, OperationLogger
from src.utils.file_utils import MetadataHandler, FileOperations
from src.exceptions import (
    PipelineException, DependencyException, StepAlreadyCompletedException
)
from src.constants import ProcessingStatus

logger = get_logger(__name__)


class BaseProcessor(ABC):
    """Abstract base class for all processors."""
    
    def __init__(self, name: str):
        """
        Initialize base processor.
        
        Args:
            name: Name of the processor
        """
        self.name = name
        self.logger = get_logger(self.__class__.__module__)
        self._error_count = 0
        self._success_count = 0
    
    @abstractmethod
    def process(self, *args, **kwargs) -> Any:
        """
        Main processing method to be implemented by subclasses.
        
        Returns:
            Processing result
        """
        pass
    
    def log_progress(self, current: int, total: int, item_name: str = "items"):
        """Log progress information."""
        percentage = (current / total * 100) if total > 0 else 0
        self.logger.info(
            f"{self.name}: {current}/{total} {item_name} ({percentage:.1f}%)"
        )
    
    def increment_success(self):
        """Increment success counter."""
        self._success_count += 1
    
    def increment_error(self):
        """Increment error counter."""
        self._error_count += 1
    
    def get_statistics(self) -> Dict[str, int]:
        """Get processing statistics."""
        return {
            "success": self._success_count,
            "errors": self._error_count,
            "total": self._success_count + self._error_count
        }


class FileProcessor(BaseProcessor):
    """Base class for processors that work with files."""
    
    def __init__(self, name: str, input_dir: Path, output_dir: Optional[Path] = None):
        """
        Initialize file processor.
        
        Args:
            name: Name of the processor
            input_dir: Input directory path
            output_dir: Output directory path (uses input_dir if None)
        """
        super().__init__(name)
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir) if output_dir else self.input_dir
        
        # Ensure directories exist
        FileOperations.ensure_directory(self.input_dir)
        if output_dir:
            FileOperations.ensure_directory(self.output_dir)
    
    @abstractmethod
    def process_file(self, file_path: Path) -> Any:
        """
        Process a single file.
        
        Args:
            file_path: Path to the file to process
            
        Returns:
            Processing result
        """
        pass
    
    def process(self, file_pattern: str = "*", recursive: bool = True) -> Dict[str, Any]:
        """
        Process all files matching the pattern.
        
        Args:
            file_pattern: Glob pattern for files
            recursive: Whether to search recursively
            
        Returns:
            Processing summary
        """
        # Find files
        if recursive:
            files = list(self.input_dir.rglob(file_pattern))
        else:
            files = list(self.input_dir.glob(file_pattern))
        
        self.logger.info(f"Found {len(files)} files to process")
        
        # Process each file
        with OperationLogger(f"{self.name} Processing") as op_logger:
            for idx, file_path in enumerate(files, 1):
                try:
                    self.log_progress(idx, len(files), "files")
                    self.process_file(file_path)
                    self.increment_success()
                except Exception as e:
                    op_logger.log_error(f"Failed to process {file_path}: {e}")
                    self.increment_error()
            
            # Log summary
            stats = self.get_statistics()
            if stats["errors"] > 0:
                op_logger.log_warning(
                    f"Completed with {stats['errors']} errors out of {stats['total']} files"
                )
            else:
                op_logger.log_info(f"Successfully processed all {stats['total']} files")
        
        return stats


class MetadataProcessor(FileProcessor):
    """Base class for processors that work with metadata files."""
    
    def __init__(
        self, 
        name: str, 
        input_dir: Path, 
        output_dir: Optional[Path] = None,
        metadata_suffix: str = "-metadata.json"
    ):
        """
        Initialize metadata processor.
        
        Args:
            name: Name of the processor
            input_dir: Input directory path
            output_dir: Output directory path
            metadata_suffix: Suffix for metadata files
        """
        super().__init__(name, input_dir, output_dir)
        self.metadata_suffix = metadata_suffix
    
    def get_metadata_path(self, file_path: Path) -> Path:
        """Get metadata file path for a given file."""
        return file_path.with_suffix("").parent / f"{file_path.stem}{self.metadata_suffix}"
    
    def load_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Load metadata for a file."""
        metadata_path = self.get_metadata_path(file_path)
        return MetadataHandler.load_metadata(metadata_path)
    
    def save_metadata(self, file_path: Path, metadata: Dict[str, Any]):
        """Save metadata for a file."""
        metadata_path = self.get_metadata_path(file_path)
        MetadataHandler.save_metadata(metadata_path, metadata)


class StepProcessor(MetadataProcessor):
    """Base class for processors that track processing steps."""
    
    def __init__(
        self,
        name: str,
        step_name: str,
        input_dir: Path,
        output_dir: Optional[Path] = None,
        required_steps: Optional[List[str]] = None
    ):
        """
        Initialize step processor.
        
        Args:
            name: Name of the processor
            step_name: Name of the processing step
            input_dir: Input directory path
            output_dir: Output directory path
            required_steps: List of required previous steps
        """
        super().__init__(name, input_dir, output_dir)
        self.step_name = step_name
        self.required_steps = required_steps or []
    
    def check_dependencies(self, metadata: Dict[str, Any]) -> None:
        """
        Check if required steps have been completed.
        
        Args:
            metadata: Metadata dictionary
            
        Raises:
            DependencyException: If required steps are not completed
        """
        for required_step in self.required_steps:
            if not MetadataHandler.is_step_completed(metadata, required_step):
                raise DependencyException(
                    self.step_name,
                    required_step,
                    {"metadata": metadata.get("doc_info", {})}
                )
    
    def check_already_completed(self, metadata: Dict[str, Any]) -> bool:
        """
        Check if this step has already been completed.
        
        Args:
            metadata: Metadata dictionary
            
        Returns:
            True if already completed
        """
        if MetadataHandler.is_step_completed(metadata, self.step_name):
            completed_at = metadata["process_steps"].get(self.step_name, "")
            self.logger.debug(
                f"Step '{self.step_name}' already completed at {completed_at}"
            )
            return True
        return False
    
    def mark_step_completed(self, file_path: Path, metadata: Dict[str, Any]) -> None:
        """
        Mark the processing step as completed.
        
        Args:
            file_path: File being processed
            metadata: Metadata dictionary
        """
        timestamp = arrow.now().format("YYYYMMDD-HHmmss")
        metadata["process_steps"][self.step_name] = timestamp
        self.save_metadata(file_path, metadata)
        self.logger.info(f"Marked step '{self.step_name}' as completed for {file_path.name}")
    
    def process_file(self, file_path: Path) -> Any:
        """
        Process a file with step tracking.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Processing result
        """
        # Load metadata
        metadata = self.load_metadata(file_path)
        
        # Check dependencies
        self.check_dependencies(metadata)
        
        # Check if already completed
        if self.check_already_completed(metadata):
            self.logger.info(f"Skipping {file_path.name} - already processed")
            return ProcessingStatus.SKIPPED
        
        # Process the file
        try:
            result = self.process_step(file_path, metadata)
            
            # Mark as completed
            self.mark_step_completed(file_path, metadata)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to process {file_path.name}: {e}")
            raise
    
    @abstractmethod
    def process_step(self, file_path: Path, metadata: Dict[str, Any]) -> Any:
        """
        Perform the actual processing step.
        
        Args:
            file_path: Path to the file
            metadata: Metadata dictionary
            
        Returns:
            Processing result
        """
        pass


class BatchProcessor(BaseProcessor):
    """Base class for processors that work with batches of items."""
    
    def __init__(self, name: str, batch_size: int = 100):
        """
        Initialize batch processor.
        
        Args:
            name: Name of the processor
            batch_size: Number of items per batch
        """
        super().__init__(name)
        self.batch_size = batch_size
    
    @abstractmethod
    def process_batch(self, items: List[Any]) -> List[Tuple[Any, Optional[Exception]]]:
        """
        Process a batch of items.
        
        Args:
            items: List of items to process
            
        Returns:
            List of (result, exception) tuples
        """
        pass
    
    def process(self, items: List[Any]) -> Dict[str, Any]:
        """
        Process all items in batches.
        
        Args:
            items: List of items to process
            
        Returns:
            Processing summary
        """
        total_items = len(items)
        self.logger.info(f"Processing {total_items} items in batches of {self.batch_size}")
        
        results = []
        
        with OperationLogger(f"{self.name} Batch Processing") as op_logger:
            for i in range(0, total_items, self.batch_size):
                batch = items[i:i + self.batch_size]
                batch_num = (i // self.batch_size) + 1
                total_batches = (total_items + self.batch_size - 1) // self.batch_size
                
                op_logger.log_progress(batch_num, total_batches, "batches")
                
                try:
                    batch_results = self.process_batch(batch)
                    results.extend(batch_results)
                    
                    # Count successes and errors
                    for result, error in batch_results:
                        if error:
                            self.increment_error()
                        else:
                            self.increment_success()
                            
                except Exception as e:
                    op_logger.log_error(f"Batch {batch_num} failed: {e}")
                    # Mark all items in batch as failed
                    for _ in batch:
                        self.increment_error()
                    results.extend([(None, e) for _ in batch])
        
        stats = self.get_statistics()
        return {
            "statistics": stats,
            "results": results
        }