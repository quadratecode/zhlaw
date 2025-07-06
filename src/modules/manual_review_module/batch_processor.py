"""
Batch Processor Module

Provides improved batch processing capabilities for table review operations.
"""

import json
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import multiprocessing
import threading

from src.modules.manual_review_module.table_extractor import LawTableExtractor
from src.modules.manual_review_module.correction_manager import CorrectionManager
from src.modules.manual_review_module.editor_interface import TableEditorInterface


@dataclass
class BatchProgress:
    """Tracks progress of batch processing operations."""
    batch_id: str
    total_laws: int
    completed_laws: int
    failed_laws: int
    current_law: Optional[str]
    start_time: str
    last_update: str
    status: str  # "running", "paused", "completed", "failed"
    completed_law_ids: List[str]
    failed_law_ids: List[str]
    estimated_time_remaining: Optional[float] = None
    
    @property
    def completion_percentage(self) -> float:
        """Calculate completion percentage."""
        if self.total_laws == 0:
            return 0.0
        return (self.completed_laws / self.total_laws) * 100.0
    
    @property
    def elapsed_time(self) -> float:
        """Calculate elapsed time in seconds."""
        start = datetime.fromisoformat(self.start_time)
        last = datetime.fromisoformat(self.last_update)
        return (last - start).total_seconds()
    
    def estimate_remaining_time(self) -> Optional[float]:
        """Estimate remaining time based on current progress."""
        if self.completed_laws == 0:
            return None
        
        time_per_law = self.elapsed_time / self.completed_laws
        remaining_laws = self.total_laws - self.completed_laws
        return time_per_law * remaining_laws


class BatchProcessor:
    """Handles batch processing of table review operations with improved features."""
    
    def __init__(self, base_path: str = "data/zhlex", max_workers: Optional[int] = None):
        self.base_path = Path(base_path)
        self.max_workers = max_workers or min(4, multiprocessing.cpu_count())
        self.logger = logging.getLogger(__name__)
        
        # Components
        self.extractor = LawTableExtractor()
        self.correction_manager = CorrectionManager(str(self.base_path))
        self.editor = TableEditorInterface()
        
        # Progress tracking
        self.progress_file = Path("batch_progress.json")
        self.current_progress: Optional[BatchProgress] = None
        self._stop_requested = False
        self._progress_lock = threading.Lock()
    
    def process_folder_batch(self, folder_path: str, 
                           resume: bool = True,
                           simulate_editor: bool = False,
                           progress_callback: Optional[Callable[[BatchProgress], None]] = None) -> BatchProgress:
        """
        Process all laws in a folder with batch processing improvements.
        
        Args:
            folder_path: Path to the folder containing laws
            resume: Whether to resume from previous progress
            simulate_editor: Use simulation mode for editor
            progress_callback: Optional callback for progress updates
            
        Returns:
            Final batch progress
        """
        full_path = self.base_path / folder_path
        
        if not full_path.exists():
            raise ValueError(f"Folder does not exist: {full_path}")
        
        # Get all laws in folder
        all_laws = self.extractor.get_laws_in_folder(str(full_path))
        
        if not all_laws:
            raise ValueError(f"No laws found in folder: {full_path}")
        
        # Initialize or resume progress
        batch_id = f"batch_{folder_path}_{int(time.time())}"
        
        if resume:
            existing_progress = self._load_progress()
            if existing_progress and existing_progress.status in ["running", "paused"]:
                self.current_progress = existing_progress
                self.logger.info(f"Resuming batch {existing_progress.batch_id} with {existing_progress.completed_laws}/{existing_progress.total_laws} completed")
            else:
                self.current_progress = self._create_new_progress(batch_id, all_laws, folder_path)
        else:
            self.current_progress = self._create_new_progress(batch_id, all_laws, folder_path)
        
        # Filter out already completed laws
        laws_to_process = [
            law_id for law_id in all_laws 
            if law_id not in self.current_progress.completed_law_ids
        ]
        
        if not laws_to_process:
            self.logger.info("All laws already completed")
            self.current_progress.status = "completed"
            self._save_progress()
            return self.current_progress
        
        self.logger.info(f"Starting batch processing: {len(laws_to_process)} laws to process")
        self.current_progress.status = "running"
        self._save_progress()
        
        # Process laws
        if self.max_workers == 1:
            # Sequential processing
            self._process_laws_sequential(laws_to_process, str(full_path), folder_path, 
                                        simulate_editor, progress_callback)
        else:
            # Parallel processing
            self._process_laws_parallel(laws_to_process, str(full_path), folder_path,
                                      simulate_editor, progress_callback)
        
        # Finalize
        self.current_progress.status = "completed" if not self._stop_requested else "paused"
        self.current_progress.last_update = datetime.now().isoformat()
        self._save_progress()
        
        return self.current_progress
    
    def _create_new_progress(self, batch_id: str, all_laws: List[str], folder_path: str) -> BatchProgress:
        """Create new batch progress tracking."""
        # Filter out already completed laws from previous runs
        already_completed = []
        for law_id in all_laws:
            if self.correction_manager.is_law_completed(law_id, folder_path):
                already_completed.append(law_id)
        
        return BatchProgress(
            batch_id=batch_id,
            total_laws=len(all_laws),
            completed_laws=len(already_completed),
            failed_laws=0,
            current_law=None,
            start_time=datetime.now().isoformat(),
            last_update=datetime.now().isoformat(),
            status="initialized",
            completed_law_ids=already_completed,
            failed_law_ids=[]
        )
    
    def _process_laws_sequential(self, laws: List[str], base_path: str, folder_name: str,
                               simulate_editor: bool, progress_callback: Optional[Callable]) -> None:
        """Process laws sequentially."""
        for law_id in laws:
            if self._stop_requested:
                break
                
            action = self._process_single_law(law_id, base_path, folder_name, simulate_editor)
            
            # No special quit action handling needed - simplified interface
            
            if progress_callback:
                progress_callback(self.current_progress)
    
    def _process_laws_parallel(self, laws: List[str], base_path: str, folder_name: str,
                             simulate_editor: bool, progress_callback: Optional[Callable]) -> None:
        """Process laws in parallel with thread pool."""
        # Note: Parallel processing is disabled for interactive review to ensure proper action handling
        self.logger.warning("Parallel processing disabled for interactive review. Using sequential processing.")
        self._process_laws_sequential(laws, base_path, folder_name, simulate_editor, progress_callback)
    
    def _process_single_law(self, law_id: str, base_path: str, folder_name: str, simulate_editor: bool) -> str:
        """Process a single law.
        
        Returns:
            Action string indicating what to do next ('next', 'quit', 'cancel_quit', etc.)
        """
        try:
            with self._progress_lock:
                self.current_progress.current_law = law_id
                self.current_progress.last_update = datetime.now().isoformat()
            
            # Check if already completed
            if self.correction_manager.is_law_completed(law_id, folder_name):
                self.logger.info(f"✅ {law_id} already completed")
                with self._progress_lock:
                    if law_id not in self.current_progress.completed_law_ids:
                        self.current_progress.completed_laws += 1
                        self.current_progress.completed_law_ids.append(law_id)
                        self.current_progress.last_update = datetime.now().isoformat()
                        self._save_progress()
                return 'next'
            
            # Extract tables
            unique_tables = self.extractor.extract_unique_tables_from_law(law_id, base_path)
            
            if not unique_tables:
                self.logger.info(f"No tables found in law {law_id}")
                # Mark as completed even without tables
                with self._progress_lock:
                    self.current_progress.completed_laws += 1
                    self.current_progress.completed_law_ids.append(law_id)
                    self.current_progress.last_update = datetime.now().isoformat()
                    self._save_progress()
                return 'next' 'next'
            
            self.logger.info(f"Found {len(unique_tables)} unique tables in law {law_id}")
            
            # Process with editor
            if simulate_editor:
                self.editor.force_simulation = True
            
            result = self.editor.launch_editor_for_law(law_id, unique_tables, base_path, review_mode='folder')
            
            if result:
                # Check if result contains action info (new format)
                if isinstance(result, dict) and 'action' in result:
                    action = result.get('action', 'complete')
                    corrections = result.get('corrections', {})
                    cancelled = result.get('cancelled', False)
                else:
                    # Legacy format - just corrections
                    corrections = result
                    action = 'complete'
                    cancelled = False
                
                # No special quit action handling needed - simplified interface
                
                if action in ['cancel', 'cancel_next'] or cancelled:
                    # Don't save corrections if cancelled, but continue to next law
                    self.logger.info(f"❌ Review cancelled for law {law_id} - no corrections saved")
                    with self._progress_lock:
                        self.current_progress.completed_laws += 1
                        self.current_progress.completed_law_ids.append(law_id)
                        self.current_progress.last_update = datetime.now().isoformat()
                        self._save_progress()
                elif corrections:
                    success = self.correction_manager.save_corrections(law_id, corrections, folder_name)
                    if success:
                        self.logger.info(f"✅ Saved corrections for law {law_id}")
                        with self._progress_lock:
                            self.current_progress.completed_laws += 1
                            self.current_progress.completed_law_ids.append(law_id)
                            self.current_progress.last_update = datetime.now().isoformat()
                            # Update estimated time
                            self.current_progress.estimated_time_remaining = self.current_progress.estimate_remaining_time()
                            self._save_progress()
                    else:
                        raise Exception("Failed to save corrections")
                else:
                    self.logger.warning(f"No corrections received for law {law_id}")
                    # Mark as completed even without corrections
                    with self._progress_lock:
                        self.current_progress.completed_laws += 1
                        self.current_progress.completed_law_ids.append(law_id)
                        self.current_progress.last_update = datetime.now().isoformat()
                        self._save_progress()
            else:
                self.logger.warning(f"No result received for law {law_id}")
                raise Exception("No result received")
            
            # If we get here, return 'next' to continue processing
            return 'next'
                
        except Exception as e:
            self.logger.error(f"Error processing law {law_id}: {e}")
            with self._progress_lock:
                self.current_progress.failed_laws += 1
                self.current_progress.failed_law_ids.append(law_id)
                self.current_progress.last_update = datetime.now().isoformat()
                self._save_progress()
            # Return 'next' even on error to continue processing other laws
            return 'error'
    
    def pause_batch(self) -> None:
        """Request to pause the current batch processing."""
        self._stop_requested = True
        if self.current_progress:
            self.current_progress.status = "paused"
            self._save_progress()
    
    def resume_batch(self, folder_path: str, **kwargs) -> BatchProgress:
        """Resume a paused batch."""
        return self.process_folder_batch(folder_path, resume=True, **kwargs)
    
    def get_current_progress(self) -> Optional[BatchProgress]:
        """Get current batch progress."""
        return self.current_progress
    
    def _save_progress(self) -> None:
        """Save progress to file."""
        if self.current_progress:
            try:
                with open(self.progress_file, 'w', encoding='utf-8') as f:
                    json.dump(asdict(self.current_progress), f, indent=2, ensure_ascii=False)
            except Exception as e:
                self.logger.error(f"Failed to save progress: {e}")
    
    def _load_progress(self) -> Optional[BatchProgress]:
        """Load progress from file."""
        try:
            if self.progress_file.exists():
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return BatchProgress(**data)
        except Exception as e:
            self.logger.error(f"Failed to load progress: {e}")
        return None
    
    def get_batch_statistics(self) -> Dict[str, Any]:
        """Get comprehensive batch statistics."""
        if not self.current_progress:
            return {}
        
        stats = {
            "batch_info": {
                "batch_id": self.current_progress.batch_id,
                "status": self.current_progress.status,
                "start_time": self.current_progress.start_time,
                "last_update": self.current_progress.last_update
            },
            "progress": {
                "total_laws": self.current_progress.total_laws,
                "completed_laws": self.current_progress.completed_laws,
                "failed_laws": self.current_progress.failed_laws,
                "remaining_laws": self.current_progress.total_laws - self.current_progress.completed_laws - self.current_progress.failed_laws,
                "completion_percentage": self.current_progress.completion_percentage
            },
            "timing": {
                "elapsed_time_seconds": self.current_progress.elapsed_time,
                "estimated_remaining_seconds": self.current_progress.estimated_time_remaining,
                "average_time_per_law": (
                    self.current_progress.elapsed_time / self.current_progress.completed_laws
                    if self.current_progress.completed_laws > 0 else None
                )
            },
            "details": {
                "completed_law_ids": self.current_progress.completed_law_ids,
                "failed_law_ids": self.current_progress.failed_law_ids,
                "current_law": self.current_progress.current_law
            }
        }
        
        return stats


class ProgressReporter:
    """Provides formatted progress reporting for batch operations."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def print_progress(self, progress: BatchProgress) -> None:
        """Print formatted progress to console."""
        print(f"\n📊 Batch Progress: {progress.batch_id}")
        print("=" * 60)
        print(f"Status: {progress.status.upper()}")
        print(f"Progress: {progress.completed_laws}/{progress.total_laws} ({progress.completion_percentage:.1f}%)")
        
        if progress.failed_laws > 0:
            print(f"Failed: {progress.failed_laws}")
        
        if progress.current_law:
            print(f"Current: {progress.current_law}")
        
        # Timing information
        elapsed = progress.elapsed_time
        if elapsed > 0:
            print(f"Elapsed: {self._format_duration(elapsed)}")
            
            if progress.estimated_time_remaining:
                print(f"Estimated remaining: {self._format_duration(progress.estimated_time_remaining)}")
        
        print()
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"
    
    def generate_report(self, progress: BatchProgress) -> str:
        """Generate a detailed text report."""
        report = []
        report.append(f"Batch Processing Report")
        report.append("=" * 50)
        report.append(f"Batch ID: {progress.batch_id}")
        report.append(f"Status: {progress.status}")
        report.append(f"Start Time: {progress.start_time}")
        report.append(f"Last Update: {progress.last_update}")
        report.append("")
        
        report.append("Progress Summary:")
        report.append(f"  Total Laws: {progress.total_laws}")
        report.append(f"  Completed: {progress.completed_laws} ({progress.completion_percentage:.1f}%)")
        report.append(f"  Failed: {progress.failed_laws}")
        report.append(f"  Remaining: {progress.total_laws - progress.completed_laws - progress.failed_laws}")
        report.append("")
        
        if progress.completed_laws > 0:
            avg_time = progress.elapsed_time / progress.completed_laws
            report.append(f"Average time per law: {self._format_duration(avg_time)}")
        
        if progress.failed_law_ids:
            report.append("")
            report.append("Failed Laws:")
            for law_id in progress.failed_law_ids:
                report.append(f"  - {law_id}")
        
        return "\n".join(report)