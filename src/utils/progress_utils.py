"""
Centralized progress bar utilities for ZHLaw processing system.

This module provides a consistent progress bar interface that integrates well
with the logging system and supports both sequential and concurrent operations.

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import sys
import time
from typing import Any, Callable, Iterable, Optional, Union, List
from concurrent.futures import Future, as_completed
from contextlib import contextmanager

try:
    import enlighten
    ENLIGHTEN_AVAILABLE = True
except ImportError:
    import tqdm
    ENLIGHTEN_AVAILABLE = False

from src.logging_config import get_logger

logger = get_logger(__name__)


class ProgressManager:
    """
    Centralized progress bar manager that provides consistent progress tracking
    across the application with logging integration.
    """
    
    def __init__(self, use_enlighten: bool = None):
        """
        Initialize the progress manager.
        
        Args:
            use_enlighten: Force use of enlighten if True, tqdm if False, auto-detect if None
        """
        if use_enlighten is None:
            self.use_enlighten = ENLIGHTEN_AVAILABLE and self._is_tty()
        else:
            self.use_enlighten = use_enlighten and ENLIGHTEN_AVAILABLE
            
        self.manager = None
        self._active_bars = []
        
        if self.use_enlighten:
            self.manager = enlighten.get_manager()
            logger.debug("Using enlighten progress bars with logging integration")
        else:
            logger.debug("Using tqdm progress bars (enlighten not available or not TTY)")
    
    def _is_tty(self) -> bool:
        """Check if we're running in a TTY environment."""
        return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    
    def create_counter(
        self,
        total: Optional[int] = None,
        desc: str = "",
        unit: str = "items",
        **kwargs
    ) -> 'ProgressCounter':
        """
        Create a new progress counter.
        
        Args:
            total: Total number of items (None for unknown)
            desc: Description for the progress bar
            unit: Unit name for items
            **kwargs: Additional arguments passed to underlying progress bar
            
        Returns:
            ProgressCounter instance
        """
        counter = ProgressCounter(
            manager=self,
            total=total,
            desc=desc,
            unit=unit,
            **kwargs
        )
        self._active_bars.append(counter)
        return counter
    
    def track_iterable(
        self,
        iterable: Iterable,
        desc: str = "",
        unit: str = "items",
        **kwargs
    ) -> Iterable:
        """
        Track progress of an iterable.
        
        Args:
            iterable: Iterable to track
            desc: Description for the progress bar
            unit: Unit name for items
            **kwargs: Additional arguments
            
        Returns:
            Wrapped iterable with progress tracking
        """
        items = list(iterable) if not hasattr(iterable, '__len__') else iterable
        total = len(items) if hasattr(items, '__len__') else None
        
        counter = self.create_counter(total=total, desc=desc, unit=unit, **kwargs)
        
        try:
            for item in items:
                yield item
                counter.update()
        finally:
            counter.close()
    
    def track_concurrent(
        self,
        futures: List[Future],
        desc: str = "",
        unit: str = "tasks",
        **kwargs
    ) -> Iterable:
        """
        Track progress of concurrent futures.
        
        Args:
            futures: List of Future objects to track
            desc: Description for the progress bar
            unit: Unit name for items
            **kwargs: Additional arguments
            
        Returns:
            Iterator over completed futures with progress tracking
        """
        counter = self.create_counter(total=len(futures), desc=desc, unit=unit, **kwargs)
        
        try:
            for future in as_completed(futures):
                yield future
                counter.update()
        finally:
            counter.close()
    
    def close(self):
        """Close all active progress bars and the manager."""
        for bar in self._active_bars:
            bar.close()
        self._active_bars.clear()
        
        if self.use_enlighten and self.manager:
            self.manager.stop()
            self.manager = None
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


class ProgressCounter:
    """
    A wrapper around progress bar implementations that provides a consistent interface.
    """
    
    def __init__(
        self,
        manager: ProgressManager,
        total: Optional[int] = None,
        desc: str = "",
        unit: str = "items",
        **kwargs
    ):
        """
        Initialize the progress counter.
        
        Args:
            manager: Parent ProgressManager instance
            total: Total number of items
            desc: Description for the progress bar
            unit: Unit name for items
            **kwargs: Additional arguments
        """
        self.manager = manager
        self.total = total
        self.desc = desc
        self.unit = unit
        self.count = 0
        self.start_time = time.time()
        self._bar = None
        
        # Create the underlying progress bar
        if manager.use_enlighten and manager.manager:
            self._bar = manager.manager.counter(
                total=total,
                desc=desc,
                unit=unit,
                **kwargs
            )
        else:
            # Fallback to tqdm with minimal config to avoid log interference
            import tqdm
            # Use file=sys.stderr to keep logs and progress separate
            self._bar = tqdm.tqdm(
                total=total,
                desc=desc,
                unit=unit,
                file=sys.stderr,
                dynamic_ncols=True,
                **kwargs
            )
    
    def update(self, increment: int = 1):
        """
        Update the progress counter.
        
        Args:
            increment: Number of items to increment by
        """
        self.count += increment
        
        if self._bar:
            if self.manager.use_enlighten:
                self._bar.update(increment)
            else:
                self._bar.update(increment)
    
    def set_description(self, desc: str):
        """
        Update the progress bar description.
        
        Args:
            desc: New description
        """
        self.desc = desc
        if self._bar:
            if hasattr(self._bar, 'desc'):
                self._bar.desc = desc
            elif hasattr(self._bar, 'set_description'):
                self._bar.set_description(desc)
    
    def close(self):
        """Close the progress bar."""
        if self._bar:
            if hasattr(self._bar, 'close'):
                self._bar.close()
            self._bar = None
        
        # Log completion summary
        duration = time.time() - self.start_time
        logger.info(
            f"Completed {self.desc}: {self.count}/{self.total or 'unknown'} {self.unit} "
            f"in {duration:.2f}s"
        )
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


@contextmanager
def progress_manager(**kwargs):
    """
    Context manager for creating and managing progress bars.
    
    Args:
        **kwargs: Arguments passed to ProgressManager
        
    Yields:
        ProgressManager instance
    """
    manager = ProgressManager(**kwargs)
    try:
        yield manager
    finally:
        manager.close()


def track_progress(
    iterable: Iterable,
    desc: str = "",
    total: Optional[int] = None,
    unit: str = "items",
    **kwargs
) -> Iterable:
    """
    Simple function to track progress of an iterable.
    
    Args:
        iterable: Iterable to track
        desc: Description for the progress bar
        total: Total number of items (auto-detected if None)
        unit: Unit name for items
        **kwargs: Additional arguments
        
    Returns:
        Wrapped iterable with progress tracking
    """
    with progress_manager() as manager:
        yield from manager.track_iterable(iterable, desc=desc, unit=unit, **kwargs)


def track_concurrent_futures(
    futures: List[Future],
    desc: str = "",
    unit: str = "tasks",
    **kwargs
) -> Iterable:
    """
    Simple function to track progress of concurrent futures.
    
    Args:
        futures: List of Future objects to track
        desc: Description for the progress bar
        unit: Unit name for items
        **kwargs: Additional arguments
        
    Returns:
        Iterator over completed futures with progress tracking
    """
    with progress_manager() as manager:
        yield from manager.track_concurrent(futures, desc=desc, unit=unit, **kwargs)


# Legacy compatibility functions for drop-in replacement
def tqdm_wrapper(*args, **kwargs):
    """
    Drop-in replacement for tqdm that uses the new progress system.
    
    This function provides backward compatibility while users migrate.
    """
    # Extract common tqdm parameters
    iterable = args[0] if args else kwargs.get('iterable')
    desc = kwargs.get('desc', '')
    total = kwargs.get('total')
    unit = kwargs.get('unit', 'it')
    
    if iterable is not None:
        # If iterable is provided, wrap it
        return track_progress(iterable, desc=desc, total=total, unit=unit)
    else:
        # Return a counter for manual updates
        manager = ProgressManager()
        return manager.create_counter(total=total, desc=desc, unit=unit)


# Export public interface
__all__ = [
    'ProgressManager',
    'ProgressCounter', 
    'progress_manager',
    'track_progress',
    'track_concurrent_futures',
    'tqdm_wrapper',
    'ENLIGHTEN_AVAILABLE'
]