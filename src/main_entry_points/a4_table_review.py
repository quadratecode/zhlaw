"""
Table Review Main Entry Point

Human-in-the-loop table review system for the zhlaw pipeline.
This is Step 2 of the manual table review process - human review of extracted tables.
Run f1_table_extraction.py first to extract tables before using this module.
"""

import argparse
import sys
import os
from pathlib import Path
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import shutil
import json
import signal

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.modules.manual_review_module.table_extractor import LawTableExtractor
from src.modules.manual_review_module.editor_interface import TableEditorInterface
from src.modules.manual_review_module.correction_manager import CorrectionManager
from src.modules.manual_review_module.batch_processor import BatchProcessor, ProgressReporter
from src.modules.manual_review_module.statistics import StatisticsCollector, ReportExporter, generate_comprehensive_report
from src.logging_config import setup_logging


class LawTableReview:
    """Main class for reviewing and correcting table structures."""
    
    def __init__(self, base_path: str = "data/zhlex", simulate_editor: bool = False, max_workers: Optional[int] = None):
        self.base_path = Path(base_path)
        self.extractor = LawTableExtractor()
        self.editor = TableEditorInterface()
        self.correction_manager = CorrectionManager(str(self.base_path))
        self.batch_processor = BatchProcessor(str(self.base_path), max_workers)
        self.progress_reporter = ProgressReporter()
        self.statistics_collector = StatisticsCollector(str(self.base_path))
        self.report_exporter = ReportExporter()
        self.logger = logging.getLogger(__name__)
        self.simulate_editor = simulate_editor
        self.setup_signal_handlers()
    
    def resolve_versions(self, law_id: str, version_spec: str, folder_path: str) -> list:
        """
        Resolve version specification to actual version list.
        
        Args:
            law_id: The law identifier (required if version_spec is not 'latest' or 'all')
            version_spec: Version specification ('latest', 'all', or specific version)
            folder_path: Path to the folder containing laws
            
        Returns:
            List of version strings to process
        """
        if law_id:
            # Get all versions for this specific law
            full_path = self.base_path / folder_path
            available_versions = self.extractor.find_law_versions(law_id, str(full_path))
            
            if not available_versions:
                self.logger.warning(f"No versions found for law {law_id}")
                return []
            
            if version_spec == "latest":
                return [self._get_latest_version(law_id, available_versions.keys(), folder_path)]
            elif version_spec == "all":
                return list(available_versions.keys())
            else:
                # Specific version
                if version_spec in available_versions:
                    return [version_spec]
                else:
                    self.logger.error(f"Version {version_spec} not found for law {law_id}. Available: {list(available_versions.keys())}")
                    return []
        else:
            # No specific law - process all laws in folder
            if version_spec == "latest":
                return ["latest"]  # Will be resolved per-law
            elif version_spec == "all":
                return ["all"]  # Will be resolved per-law
            else:
                self.logger.error("Specific version requires --law argument")
                return []
    
    def _get_latest_version(self, law_id: str, versions: list, folder_path: str) -> str:
        """
        Get the latest version based on numeric_nachtragsnummer.
        
        Args:
            law_id: The law identifier
            versions: List of available version strings
            folder_path: Path to the folder
            
        Returns:
            Latest version string
        """
        if not versions:
            return None
        
        if len(versions) == 1:
            return list(versions)[0]
        
        # Read metadata files to get numeric_nachtragsnummer
        version_with_numbers = []
        
        for version in versions:
            metadata_path = self.base_path / folder_path / law_id / version / f"{law_id}-{version}-metadata.json"
            
            if metadata_path.exists():
                try:
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    
                    doc_info = metadata.get('doc_info', {})
                    numeric_nachtragsnummer = doc_info.get('numeric_nachtragsnummer')
                    
                    if numeric_nachtragsnummer is not None:
                        version_with_numbers.append((version, float(numeric_nachtragsnummer)))
                    else:
                        # Fallback: try to convert version string to number
                        try:
                            version_with_numbers.append((version, float(version)))
                        except ValueError:
                            # Can't convert, use 0 as fallback
                            version_with_numbers.append((version, 0.0))
                            
                except Exception as e:
                    self.logger.warning(f"Error reading metadata for {law_id} version {version}: {e}")
                    # Fallback: try to convert version string to number
                    try:
                        version_with_numbers.append((version, float(version)))
                    except ValueError:
                        version_with_numbers.append((version, 0.0))
            else:
                # No metadata file, try to convert version string to number
                try:
                    version_with_numbers.append((version, float(version)))
                except ValueError:
                    version_with_numbers.append((version, 0.0))
        
        # Sort by numeric value and return the highest
        if version_with_numbers:
            latest = max(version_with_numbers, key=lambda x: x[1])
            return latest[0]
        else:
            # Fallback to first version if all else fails
            return list(versions)[0]
    
    def review_folder_latest_versions(self, folder_path: str, resume: bool = True) -> None:
        """
        Review latest versions of all laws in a folder.
        
        Args:
            folder_path: Path to the folder containing laws
            resume: Whether to resume from previous progress
        """
        full_path = self.base_path / folder_path
        
        if not full_path.exists():
            self.logger.error(f"Folder does not exist: {full_path}")
            return
        
        laws = self.get_laws_in_folder(str(full_path))
        
        if not laws:
            self.logger.warning(f"No laws found in folder: {full_path}")
            return
        
        print(f"\n📊 Reviewing Latest Versions - {folder_path}")
        print("=" * 60)
        
        laws_to_review = []
        total_versions = 0
        
        for law_id in laws:
            # Get latest version for this law
            available_versions = self.extractor.find_law_versions(law_id, str(full_path))
            if not available_versions:
                continue
                
            latest_version = self._get_latest_version(law_id, available_versions.keys(), folder_path)
            if not latest_version:
                continue
            
            # Check if this version has tables and needs review
            tables = self.extractor.extract_tables_from_version(law_id, latest_version, str(full_path))
            if tables:
                # Check if version needs review
                corrections = self.correction_manager.get_corrections(law_id, latest_version, folder_path)
                needs_review = self._version_needs_review(tables, corrections, resume)
                
                if needs_review:
                    laws_to_review.append((law_id, latest_version))
                    total_versions += 1
                    print(f"  📋 {law_id} v{latest_version}: {len(tables)} tables to review")
                else:
                    print(f"  ✅ {law_id} v{latest_version}: completed ({len(tables)} tables)")
            else:
                print(f"  ⚪ {law_id} v{latest_version}: no tables")
        
        if not laws_to_review:
            print(f"\n🎉 All latest versions completed! No laws need review.")
            return
        
        print(f"\n🔄 Starting review of {len(laws_to_review)} law versions...")
        
        for i, (law_id, version) in enumerate(laws_to_review, 1):
            print(f"\n[{i}/{len(laws_to_review)}] Reviewing {law_id} version {version}")
            
            # Prepare progression info for auto-progression
            progression_info = {
                'current_index': i,
                'total_count': len(laws_to_review),
                'has_next': i < len(laws_to_review),
                'next_law_info': f"{laws_to_review[i][0]} v{laws_to_review[i][1]}" if i < len(laws_to_review) else None
            }
            
            self.review_specific_law_version_with_progression(law_id, version, folder_path, progression_info)
    
    def review_folder_all_versions(self, folder_path: str, resume: bool = True) -> None:
        """
        Review all versions of all laws in a folder.
        
        Args:
            folder_path: Path to the folder containing laws
            resume: Whether to resume from previous progress
        """
        full_path = self.base_path / folder_path
        
        if not full_path.exists():
            self.logger.error(f"Folder does not exist: {full_path}")
            return
        
        laws = self.get_laws_in_folder(str(full_path))
        
        if not laws:
            self.logger.warning(f"No laws found in folder: {full_path}")
            return
        
        print(f"\n📊 Reviewing All Versions - {folder_path}")
        print("=" * 60)
        
        versions_to_review = []
        total_versions = 0
        
        for law_id in laws:
            # Get all versions for this law
            available_versions = self.extractor.find_law_versions(law_id, str(full_path))
            if not available_versions:
                continue
                
            for version in available_versions.keys():
                # Check if this version has tables and needs review
                tables = self.extractor.extract_tables_from_version(law_id, version, str(full_path))
                if tables:
                    # Check if version needs review
                    corrections = self.correction_manager.get_corrections(law_id, version, folder_path)
                    needs_review = self._version_needs_review(tables, corrections, resume)
                    
                    if needs_review:
                        versions_to_review.append((law_id, version))
                        total_versions += 1
                        print(f"  📋 {law_id} v{version}: {len(tables)} tables to review")
                    else:
                        print(f"  ✅ {law_id} v{version}: completed ({len(tables)} tables)")
                else:
                    print(f"  ⚪ {law_id} v{version}: no tables")
        
        if not versions_to_review:
            print(f"\n🎉 All versions completed! No law versions need review.")
            return
        
        print(f"\n🔄 Starting review of {len(versions_to_review)} law versions...")
        
        for i, (law_id, version) in enumerate(versions_to_review, 1):
            print(f"\n[{i}/{len(versions_to_review)}] Reviewing {law_id} version {version}")
            
            # Prepare progression info for auto-progression
            progression_info = {
                'current_index': i,
                'total_count': len(versions_to_review),
                'has_next': i < len(versions_to_review),
                'next_law_info': f"{versions_to_review[i][0]} v{versions_to_review[i][1]}" if i < len(versions_to_review) else None
            }
            
            self.review_specific_law_version_with_progression(law_id, version, folder_path, progression_info)
    
    def review_specific_law_versions(self, law_id: str, versions: list, folder_path: str) -> None:
        """
        Review specific versions of a law.
        
        Args:
            law_id: The law identifier
            versions: List of version strings to review
            folder_path: Path to the folder
        """
        print(f"\n📊 Reviewing Law {law_id} - Versions {versions}")
        print("=" * 60)
        
        for i, version in enumerate(versions, 1):
            print(f"\n[{i}/{len(versions)}] Reviewing {law_id} version {version}")
            
            # Prepare progression info for auto-progression
            progression_info = {
                'current_index': i,
                'total_count': len(versions),
                'has_next': i < len(versions),
                'next_law_info': f"{law_id} v{versions[i]}" if i < len(versions) else None
            }
            
            self.review_specific_law_version_with_progression(law_id, version, folder_path, progression_info)
    
    def review_specific_law_version_with_progression(self, law_id: str, version: str, folder_path: str, progression_info: dict = None) -> None:
        """
        Review a specific version of a law with auto-progression support.
        
        Args:
            law_id: The law identifier
            version: The version string
            folder_path: Path to the folder
            progression_info: Information about progression state for auto-progression
        """
        # Extract tables for this specific version
        tables = self.extractor.extract_tables_from_version(law_id, version, str(self.base_path / folder_path))
        
        if not tables:
            print(f"⚪ No tables found in {law_id} version {version}")
            return
        
        # Check existing corrections
        corrections = self.correction_manager.get_corrections(law_id, version, folder_path)
        
        # Debug logging
        if corrections:
            self.logger.info(f"Loaded {len(corrections.get('tables', {}))} existing corrections for {law_id} v{version}")
            for table_hash, correction in corrections.get('tables', {}).items():
                self.logger.debug(f"  Table {table_hash[:8]}... has status: {correction.get('status', 'undefined')}")
        else:
            self.logger.info(f"No existing corrections found for {law_id} v{version}")
        
        # Convert to legacy format for editor compatibility - allow re-review when targeting specific law
        legacy_tables = self._convert_to_legacy_format(tables, corrections, allow_re_review=True)
        
        if not legacy_tables:
            print(f"✅ All tables in {law_id} version {version} are already reviewed")
            return
        
        print(f"📋 Found {len(legacy_tables)} tables to review in {law_id} version {version}")
        
        # Launch editor interface with progression support
        try:
            if self.simulate_editor:
                print(f"🔄 [SIMULATION] Would review {len(legacy_tables)} tables for {law_id} v{version}")
                return
            
            # Use progression-aware editor
            review_mode = 'folder' if progression_info else 'single'
            base_path_str = str(self.base_path / folder_path)
            
            result = self.editor.launch_editor_for_law_with_progression(
                law_id, 
                legacy_tables, 
                base_path_str, 
                progression_info, 
                review_mode,
                use_legacy_format=True
            )
            
            if result and result.get('corrections'):
                # Save corrections for this specific version
                success = self.correction_manager.save_corrections(
                    law_id, result['corrections'], version, folder_path
                )
                
                if success:
                    print(f"✅ Saved corrections for {law_id} version {version}")
                else:
                    print(f"❌ Failed to save corrections for {law_id} version {version}")
            else:
                print(f"⚠️ No corrections received for {law_id} version {version}")
                
        except Exception as e:
            self.logger.error(f"Error reviewing {law_id} version {version}: {e}")
            print(f"❌ Error reviewing {law_id} version {version}: {e}")
    
    def review_specific_law_version(self, law_id: str, version: str, folder_path: str) -> None:
        """
        Review a specific version of a law.
        
        Args:
            law_id: The law identifier
            version: The version string
            folder_path: Path to the folder
        """
        # Extract tables for this specific version
        tables = self.extractor.extract_tables_from_version(law_id, version, str(self.base_path / folder_path))
        
        if not tables:
            print(f"⚪ No tables found in {law_id} version {version}")
            return
        
        # Check existing corrections
        corrections = self.correction_manager.get_corrections(law_id, version, folder_path)
        
        # Convert to legacy format for editor compatibility - allow re-review of all tables
        legacy_tables = self._convert_to_legacy_format(tables, corrections, allow_re_review=True)
        
        if not legacy_tables:
            print(f"⚪ No tables found in {law_id} version {version}")
            return
        
        print(f"📋 Found {len(legacy_tables)} tables to review in {law_id} version {version}")
        
        # Launch editor interface
        try:
            if self.simulate_editor:
                print(f"🔄 [SIMULATION] Would review {len(legacy_tables)} tables for {law_id} v{version}")
                return
            
            # Launch editor directly with legacy tables
            result = self.editor.launch_editor_for_law(law_id, legacy_tables, str(self.base_path / folder_path), 'version')
            
            if result and result.get('corrections'):
                # Save corrections for this specific version
                success = self.correction_manager.save_corrections(
                    law_id, result['corrections'], version, folder_path
                )
                
                if success:
                    print(f"✅ Saved corrections for {law_id} version {version}")
                else:
                    print(f"❌ Failed to save corrections for {law_id} version {version}")
            else:
                print(f"⚠️ No corrections received for {law_id} version {version}")
                
        except Exception as e:
            self.logger.error(f"Error reviewing {law_id} version {version}: {e}")
            print(f"❌ Error reviewing {law_id} version {version}: {e}")
    
    def _version_needs_review(self, tables: dict, corrections: dict, resume: bool) -> bool:
        """
        Check if a version needs review based on table status.
        
        Args:
            tables: Extracted tables for the version
            corrections: Existing corrections (if any)
            resume: Whether to skip completed tables
            
        Returns:
            True if version needs review
        """
        if not resume:
            return len(tables) > 0
        
        if not corrections:
            return len(tables) > 0
        
        # Check if any tables are still undefined
        correction_tables = corrections.get('tables', {})
        
        for table_hash in tables.keys():
            if table_hash not in correction_tables:
                return True  # New table found
            
            status = correction_tables[table_hash].get('status', 'undefined')
            if status == 'undefined':
                return True  # Table still needs review
        
        return False  # All tables are reviewed
    
    def _convert_to_legacy_format(self, version_tables: dict, corrections: dict, allow_re_review: bool = False) -> dict:
        """
        Convert per-version tables to legacy format for editor compatibility.
        
        Args:
            version_tables: Tables from extract_tables_from_version
            corrections: Existing corrections
            allow_re_review: If True, include all tables regardless of completion status
            
        Returns:
            Dictionary in legacy format with cross-version structure
        """
        legacy_tables = {}
        correction_tables = corrections.get('tables', {}) if corrections else {}
        
        for table_hash, table_data in version_tables.items():
            # Skip tables that are already completed (if resume mode and not re-review)
            if not allow_re_review and table_hash in correction_tables:
                status = correction_tables[table_hash].get('status', 'undefined')
                if status != 'undefined':
                    continue  # Skip completed tables
            
            # Convert to legacy format
            legacy_table = {
                'hash': table_hash,
                'found_in_versions': [table_data['version']],
                'pages': {table_data['version']: table_data['pages']},
                'pdf_paths': {table_data['version']: table_data['pdf_path']},
                'source_links': {table_data['version']: table_data['source_link']},
                'original_structure': table_data['original_structure']
            }
            
            # Include correction data if it exists and we're allowing re-review
            if allow_re_review and table_hash in correction_tables:
                correction = correction_tables[table_hash]
                legacy_table['status'] = correction.get('status', 'undefined')
                if 'corrected_structure' in correction:
                    legacy_table['corrected_structure'] = correction['corrected_structure']
                self.logger.debug(f"Including correction for table {table_hash[:8]}... with status: {legacy_table['status']}")
            else:
                # Set default status for tables without corrections
                legacy_table['status'] = 'undefined'
            
            legacy_tables[table_hash] = legacy_table
        
        return legacy_tables
    
    def review_folder(self, folder_path: str, use_batch: bool = True, resume: bool = True, 
                     max_workers: Optional[int] = None) -> None:
        """
        Review all laws in a folder using sequential auto-progression.
        
        Args:
            folder_path: Path to the folder containing laws
            use_batch: Whether to use batch processing (deprecated - now always sequential)
            resume: Whether to resume from previous progress
            max_workers: Maximum number of worker threads (deprecated)
        """
        # Always use sequential auto-progression for folder review to avoid multiple tabs
        self.review_folder_auto_sequential(folder_path, resume=resume)
    
    def setup_signal_handlers(self) -> None:
        """Setup signal handlers for immediate termination."""
        def signal_handler(signum, frame):
            if signum == signal.SIGINT:  # CTRL+C
                print("\n\n⚠️ CTRL+C detected - terminating process immediately...")
                print("💻 Browser window can be closed manually")
                print("✅ Process terminated")
                # Force immediate exit - don't wait for cleanup
                os._exit(0)
            elif signum == signal.SIGTERM:  # Termination signal
                print("\n\n⚠️ Termination signal detected - terminating process...")
                os._exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def review_folder_auto_sequential(self, folder_path: str, resume: bool = True) -> None:
        """
        Review all laws in a folder sequentially with automatic progression.
        Opens one browser tab at a time and automatically progresses to the next law.
        
        Args:
            folder_path: Path to the folder containing laws
            resume: Whether to resume from previous progress
        """
        full_path = self.base_path / folder_path
        
        if not full_path.exists():
            self.logger.error(f"Folder does not exist: {full_path}")
            return
        
        laws = self.get_laws_in_folder(str(full_path))
        
        if not laws:
            self.logger.warning(f"No laws found in folder: {full_path}")
            return
        
        # Filter to only laws with tables and not yet completed
        laws_to_review = []
        total_tables = 0
        
        print(f"\n🔄 Scanning laws in {folder_path}...")
        
        for law_id in laws:
            # Check if law has tables
            unique_tables = self.extractor.extract_unique_tables_from_law(law_id, str(full_path))
            if unique_tables:
                # Update corrections with any new tables (preserves existing corrections)
                self.correction_manager.update_corrections_with_new_tables(law_id, folder_path)
                
                # Check how many tables actually need review
                editor_data = self.editor.prepare_editor_data(
                    law_id, unique_tables, 'folder', str(full_path), folder_path
                )
                tables_to_review = len(editor_data.get('tables', []))
                
                # Skip if no tables need review (if resume is True)
                if resume and tables_to_review == 0:
                    continue
                
                laws_to_review.append(law_id)
                total_tables += tables_to_review  # Count only tables that need review
        
        if not laws_to_review:
            print(f"\n✅ All laws in {folder_path} have been reviewed!")
            return
        
        print(f"\n📊 Table Review - {folder_path}")
        print("=" * 60)
        print(f"Laws to review: {len(laws_to_review)}")
        print(f"Total tables: {total_tables}")
        print(f"Resume mode: {'ON' if resume else 'OFF'}")
        print("\nStarting sequential review with auto-progression...")
        print("⚠️ Press CTRL+C in this terminal to quit at any time")
        print("=" * 60)
        
        # Process laws one by one with auto-progression
        for i, law_id in enumerate(laws_to_review):
            is_last_law = (i == len(laws_to_review) - 1)
            next_law_id = laws_to_review[i + 1] if not is_last_law else None
            
            print(f"\n📋 Processing law {i + 1}/{len(laws_to_review)}: {law_id}")
            
            try:
                
                # Review this law with auto-progression info
                action = self.review_law_with_progression(law_id, str(full_path), folder_path, 
                                                         next_law_id, is_last_law)
                
                
                # Handle the action returned
                self.logger.info(f"Received action from law {law_id}: {action}")
                
                if action == 'cancel':
                    print("\n❌ Review cancelled by user")
                    break
                elif action in ['cancel_next', 'next']:
                    # Continue to next law automatically
                    continue
                elif action == 'error':
                    # Error occurred, ask user
                    if not is_last_law:
                        response = input(f"\nError occurred. Continue with next law ({next_law_id})? (y/n): ")
                        if response.lower() not in ['y', 'yes']:
                            print("Review paused by user.")
                            break
                else:
                    # Unknown action or browser closed unexpectedly
                    if not is_last_law:
                        response = input(f"\nContinue with next law ({next_law_id})? (y/n): ")
                        if response.lower() not in ['y', 'yes']:
                            print("Review paused by user.")
                            break
                        
            except KeyboardInterrupt:
                # This should not happen since we handle SIGINT in signal handler
                print("\n⚠️ Review interrupted")
                sys.exit(0)
            except Exception as e:
                self.logger.error(f"Error reviewing law {law_id}: {e}")
                print(f"❌ Error reviewing law {law_id}: {e}")
                
                if not is_last_law and not self.stop_requested:
                    try:
                        response = input("Continue with next law? (y/n): ")
                        if response.lower() not in ['y', 'yes']:
                            break
                    except (EOFError, KeyboardInterrupt):
                        print("\n⚠️ Review terminated")
                        sys.exit(0)
        
        # Final summary
        print(f"\n🎉 FOLDER REVIEW COMPLETED")
        print("=" * 60)
        completed_count = sum(1 for law_id in laws 
                            if self.correction_manager.is_law_fully_completed(law_id, folder_path))
        print(f"Total laws completed: {completed_count}/{len(laws)}")
        
        if completed_count < len(laws):
            print(f"Laws remaining: {len(laws) - completed_count}")
            print("Run the command again to continue reviewing.")
    
    
    
    def review_law_with_progression(self, law_id: str, base_path: str, folder_name: str,
                                   next_law_id: Optional[str] = None, is_last_law: bool = False) -> None:
        """
        Review a single law with auto-progression support.
        
        Args:
            law_id: The law identifier
            base_path: Full path to the law files
            folder_name: Name of the folder for corrections
            next_law_id: ID of the next law to review (None if last)
            is_last_law: Whether this is the last law in the sequence
        """
        try:
            # Extract unique tables across all versions
            unique_tables = self.extractor.extract_unique_tables_from_law(law_id, base_path)
            
            if not unique_tables:
                self.logger.info(f"No tables found in law {law_id}")
                return 'next'  # Skip to next law
            
            # Update corrections with any new tables (preserves existing corrections)
            self.correction_manager.update_corrections_with_new_tables(law_id, folder_name)
            
            # Prepare editor data to check how many tables actually need review  
            editor_data = self.editor.prepare_editor_data(
                law_id, unique_tables, 'folder', base_path, folder_name
            )
            
            tables_to_review = len(editor_data.get('tables', []))
            already_reviewed = editor_data.get('metadata', {}).get('already_reviewed', 0)
            
            if tables_to_review == 0:
                print(f"✅ All tables in law {law_id} have already been reviewed!")
                print(f"   Total tables: {len(unique_tables)}, Already reviewed: {already_reviewed}")
                return 'next'  # Skip to next law
            
            if tables_to_review < len(unique_tables):
                print(f"📊 Law {law_id}: {tables_to_review} new tables to review, {already_reviewed} already completed")
            
            self.logger.info(f"Found {len(unique_tables)} unique tables in law {law_id}, {tables_to_review} need review")
            
            # Prepare progression info
            progression_info = {
                'next_law_id': next_law_id,
                'is_last_law': is_last_law,
                'folder_name': folder_name
            }
            
            # Launch table editor with progression support
            if self.simulate_editor:
                self.editor.force_simulation = True
            result = self.editor.launch_editor_for_law_with_progression(
                law_id, unique_tables, base_path, progression_info, review_mode='folder'
            )
            
            if result:
                # Check if result contains action info
                if isinstance(result, dict) and 'action' in result:
                    action = result.get('action', 'complete')
                    corrections = result.get('corrections', {})
                    cancelled = result.get('cancelled', False)
                    self.logger.info(f"Received action '{action}' from editor for law {law_id}")
                else:
                    # Legacy format - just corrections
                    corrections = result
                    action = 'complete'
                    cancelled = False
                    self.logger.info(f"Received legacy format result for law {law_id}, defaulting action to 'complete'")
                
                if action in ['cancel', 'cancel_next'] or cancelled:
                    # Don't save corrections if cancelled
                    self.logger.info(f"❌ Review cancelled for law {law_id} - no corrections saved")
                elif corrections:
                    # Save corrections
                    success = self.correction_manager.save_corrections(law_id, corrections, folder_name)
                    if success:
                        self.logger.info(f"✅ Saved corrections for law {law_id}")
                    else:
                        self.logger.error(f"❌ Failed to save corrections for law {law_id}")
                else:
                    self.logger.warning(f"No corrections received for law {law_id}")
                
                # Return the action for the main loop to handle
                self.logger.info(f"review_law_with_progression returning action '{action}' to main review loop")
                return action
            else:
                self.logger.warning(f"No result received for law {law_id}")
                return 'error'
                
        except Exception as e:
            self.logger.error(f"Error reviewing law {law_id}: {e}")
            raise
    
    def _review_folder_sequential(self, folder_path: str) -> None:
        """Legacy sequential folder review (kept for compatibility)."""
        full_path = self.base_path / folder_path
        
        if not full_path.exists():
            self.logger.error(f"Folder does not exist: {full_path}")
            return
        
        laws = self.get_laws_in_folder(str(full_path))
        
        if not laws:
            self.logger.warning(f"No laws found in folder: {full_path}")
            return
        
        self.logger.info(f"Found {len(laws)} laws in folder: {folder_path}")
        
        for i, law_id in enumerate(laws, 1):
            self.logger.info(f"Processing law {i}/{len(laws)}: {law_id}")
            
            if self.correction_manager.is_law_fully_completed(law_id, folder_path):
                self.logger.info(f"✅ {law_id} already completed")
                continue
            
            self.logger.info(f"📋 Reviewing law {law_id}")
            self.review_law(law_id, str(full_path), folder_path)
    
    def review_folder_batch(self, folder_path: str, resume: bool = True, 
                           max_workers: Optional[int] = None, show_progress: bool = True) -> None:
        """
        Review all laws in a folder using advanced batch processing.
        
        Args:
            folder_path: Path to the folder containing laws
            resume: Whether to resume from previous progress
            max_workers: Maximum number of worker threads
            show_progress: Whether to show live progress updates
        """
        # Update batch processor worker count if specified
        if max_workers:
            self.batch_processor.max_workers = max_workers
        
        def progress_callback(progress):
            if show_progress:
                self.progress_reporter.print_progress(progress)
        
        try:
            final_progress = self.batch_processor.process_folder_batch(
                folder_path=folder_path,
                resume=resume,
                simulate_editor=self.simulate_editor,
                progress_callback=progress_callback if show_progress else None
            )
            
            # Print final summary
            print("\n" + "=" * 60)
            print("🎉 BATCH PROCESSING COMPLETED")
            print("=" * 60)
            print(f"Total laws: {final_progress.total_laws}")
            print(f"Completed: {final_progress.completed_laws}")
            print(f"Failed: {final_progress.failed_laws}")
            print(f"Success rate: {(final_progress.completed_laws / final_progress.total_laws) * 100:.1f}%")
            
            if final_progress.failed_law_ids:
                print(f"\nFailed laws:")
                for law_id in final_progress.failed_law_ids:
                    print(f"  - {law_id}")
            
            elapsed = final_progress.elapsed_time
            print(f"\nTotal time: {elapsed/60:.1f} minutes")
            
            if final_progress.completed_laws > 0:
                avg_time = elapsed / final_progress.completed_laws
                print(f"Average time per law: {avg_time:.1f} seconds")
        
        except KeyboardInterrupt:
            print("\n⏸️  Batch processing paused by user")
            print("Use --resume to continue later")
        except Exception as e:
            self.logger.error(f"Batch processing failed: {e}")
            raise
    
    def review_law(self, law_id: str, base_path: str, folder_name: str, allow_re_review: bool = False) -> None:
        """
        Review all tables in a single law.
        
        Args:
            law_id: The law identifier
            base_path: Full path to the law files
            folder_name: Name of the folder for corrections
            allow_re_review: Whether to allow re-reviewing already completed laws
        """
        try:
            # Extract unique tables across all versions
            unique_tables = self.extractor.extract_unique_tables_from_law(law_id, base_path)
            
            if not unique_tables:
                self.logger.info(f"No tables found in law {law_id}")
                return
            
            # Update corrections with any new tables (preserves existing corrections)
            self.correction_manager.update_corrections_with_new_tables(law_id, folder_name)
            
            # Check if already fully completed (unless re-review is allowed)
            if not allow_re_review and self.correction_manager.is_law_fully_completed(law_id, folder_name):
                self.logger.info(f"Law {law_id} already fully completed, skipping")
                return
            
            self.logger.info(f"Found {len(unique_tables)} unique tables in law {law_id}")
            
            # Prepare editor data to check how many tables actually need review
            editor_data = self.editor.prepare_editor_data(
                law_id, unique_tables, 'single' if allow_re_review else 'folder', base_path, folder_name
            )
            
            tables_to_review = len(editor_data.get('tables', []))
            already_reviewed = editor_data.get('metadata', {}).get('already_reviewed', 0)
            
            if tables_to_review == 0 and not allow_re_review:
                print(f"✅ All tables in law {law_id} have already been reviewed!")
                print(f"   Total tables: {len(unique_tables)}, Already reviewed: {already_reviewed}")
                print(f"   Use --law {law_id} to re-review or edit existing corrections")
                return
            
            if tables_to_review < len(unique_tables) and not allow_re_review:
                print(f"📊 Law {law_id}: {tables_to_review} new tables to review, {already_reviewed} already completed")
            
            # Launch table_editor (with simulation mode if requested)
            if self.simulate_editor:
                self.editor.force_simulation = True
            result = self.editor.launch_editor_for_law(law_id, unique_tables, base_path, review_mode='single' if allow_re_review else 'folder')
            
            if result:
                # Check if result contains action info (new format)
                if isinstance(result, dict) and 'action' in result:
                    corrections = result.get('corrections', {})
                else:
                    # Legacy format - just corrections
                    corrections = result
                
                if corrections:
                    # Save corrections
                    success = self.correction_manager.save_corrections(law_id, corrections, folder_name)
                    if success:
                        self.logger.info(f"✅ Saved corrections for law {law_id}")
                    else:
                        self.logger.error(f"❌ Failed to save corrections for law {law_id}")
                else:
                    self.logger.warning(f"No corrections received for law {law_id}")
            else:
                self.logger.warning(f"No result received for law {law_id}")
                
        except Exception as e:
            self.logger.error(f"Error reviewing law {law_id}: {e}")
    
    def show_progress(self, folder_path: str) -> None:
        """
        Show review progress for a folder using per-version approach.
        
        Args:
            folder_path: Path to the folder
        """
        progress = self._get_per_version_progress_summary(folder_path)
        
        if "error" in progress:
            self.logger.error(progress["error"])
            return
        
        print(f"\n📊 Review Progress for {folder_path}")
        print("=" * 60)
        print(f"Total laws: {progress['total_laws']}")
        print(f"Total versions: {progress['total_versions']}")
        print(f"Laws with tables: {progress['laws_with_tables']}")
        print(f"Versions with tables: {progress['versions_with_tables']}")
        print("")
        print(f"📋 Tables in latest versions: {progress['latest_version_tables']}")
        print(f"📋 All tables (all versions): {progress['total_tables']}")
        print("")
        print(f"✅ Completed versions: {progress['completed_versions']}")
        print(f"📝 Versions needing review: {progress['versions_needing_review']}")
        print(f"⚪ Versions without tables: {progress['versions_without_tables']}")
        
        if progress['versions_with_tables'] > 0:
            completion_rate = (progress['completed_versions'] / progress['versions_with_tables']) * 100
            print(f"\nCompletion rate: {completion_rate:.1f}%")
        
        # Show detailed status by law
        if progress['law_details']:
            print(f"\n📋 Detailed Status by Law:")
            print("-" * 40)
            
            for law_info in sorted(progress['law_details'], key=lambda x: x['law_id']):
                law_id = law_info['law_id']
                versions = law_info['versions']
                
                if not versions:
                    print(f"  {law_id}: No versions found")
                    continue
                
                # Count tables and status
                total_tables = sum(v['table_count'] for v in versions)
                completed_versions = sum(1 for v in versions if v['status'] == 'completed')
                versions_with_tables = sum(1 for v in versions if v['table_count'] > 0)
                
                if total_tables == 0:
                    print(f"  ⚪ {law_id}: {len(versions)} versions, no tables")
                elif completed_versions == versions_with_tables:
                    print(f"  ✅ {law_id}: {len(versions)} versions, {total_tables} tables (all completed)")
                else:
                    print(f"  📋 {law_id}: {len(versions)} versions, {total_tables} tables ({completed_versions}/{versions_with_tables} completed)")
                
                # Show version details if more than one version
                if len(versions) > 1:
                    latest_version = max(versions, key=lambda v: v.get('numeric_nachtragsnummer', 0))
                    for version_info in versions:
                        status_icon = "✅" if version_info['status'] == 'completed' else "📋" if version_info['table_count'] > 0 else "⚪"
                        latest_marker = " (latest)" if version_info == latest_version else ""
                        print(f"    {status_icon} v{version_info['version']}: {version_info['table_count']} tables{latest_marker}")
    
    def _get_per_version_progress_summary(self, folder_path: str) -> Dict[str, Any]:
        """
        Get comprehensive progress summary using per-version approach.
        
        Args:
            folder_path: Path to the folder
            
        Returns:
            Dictionary containing detailed progress statistics
        """
        full_path = self.base_path / folder_path
        
        if not full_path.exists():
            return {"error": f"Folder {folder_path} does not exist"}
        
        laws = self.get_laws_in_folder(str(full_path))
        
        summary = {
            "total_laws": len(laws),
            "total_versions": 0,
            "laws_with_tables": 0,
            "versions_with_tables": 0,
            "versions_without_tables": 0,
            "completed_versions": 0,
            "versions_needing_review": 0,
            "total_tables": 0,
            "latest_version_tables": 0,
            "law_details": []
        }
        
        for law_id in laws:
            # Get all versions for this law
            available_versions = self.extractor.find_law_versions(law_id, str(full_path))
            law_info = {
                "law_id": law_id,
                "versions": []
            }
            
            law_has_tables = False
            latest_version_num = 0
            latest_version_tables = 0
            
            for version in available_versions.keys():
                summary["total_versions"] += 1
                
                # Get tables for this version
                tables = self.extractor.extract_tables_from_version(law_id, version, str(full_path))
                table_count = len(tables)
                summary["total_tables"] += table_count
                
                # Get numeric version for latest detection
                try:
                    metadata_path = full_path / law_id / version / f"{law_id}-{version}-metadata.json"
                    numeric_nachtragsnummer = 0
                    if metadata_path.exists():
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        numeric_nachtragsnummer = metadata.get('doc_info', {}).get('numeric_nachtragsnummer', 0)
                    
                    if not numeric_nachtragsnummer:
                        numeric_nachtragsnummer = float(version)
                except:
                    numeric_nachtragsnummer = 0
                
                # Check if latest version for this law
                if numeric_nachtragsnummer > latest_version_num:
                    latest_version_num = numeric_nachtragsnummer
                    latest_version_tables = table_count
                
                # Determine status
                if table_count == 0:
                    status = 'no_tables'
                    summary["versions_without_tables"] += 1
                else:
                    law_has_tables = True
                    summary["versions_with_tables"] += 1
                    
                    # Check if version is completed
                    corrections = self.correction_manager.get_corrections(law_id, version, folder_path)
                    needs_review = self._version_needs_review(tables, corrections, True)
                    
                    if needs_review:
                        status = 'needs_review'
                        summary["versions_needing_review"] += 1
                    else:
                        status = 'completed'
                        summary["completed_versions"] += 1
                
                law_info["versions"].append({
                    "version": version,
                    "table_count": table_count,
                    "status": status,
                    "numeric_nachtragsnummer": numeric_nachtragsnummer
                })
            
            if law_has_tables:
                summary["laws_with_tables"] += 1
                summary["latest_version_tables"] += latest_version_tables
            
            summary["law_details"].append(law_info)
        
        return summary
    
    def get_laws_in_folder(self, folder_path: str) -> list:
        """
        Get all law IDs in a folder.
        
        Args:
            folder_path: Path to the folder
            
        Returns:
            List of law IDs
        """
        return self.extractor.get_laws_in_folder(folder_path)
    
    def review_specific_law(self, law_id: str, folder_path: str) -> None:
        """
        Review a specific law.
        
        Args:
            law_id: The law identifier
            folder_path: Path to the folder
        """
        full_path = self.base_path / folder_path
        
        if not full_path.exists():
            self.logger.error(f"Folder does not exist: {full_path}")
            return
        
        law_path = full_path / law_id
        if not law_path.exists():
            self.logger.error(f"Law {law_id} does not exist in folder {folder_path}")
            return
        
        self.logger.info(f"Reviewing specific law: {law_id}")
        # Allow re-reviewing when using --law parameter
        self.review_law(law_id, str(full_path), folder_path, allow_re_review=True)
    
    def reset_law_corrections(self, law_id: str, folder_path: str) -> None:
        """
        Reset corrections for a law (delete existing corrections).
        
        Args:
            law_id: The law identifier
            folder_path: Path to the folder
        """
        # Check if corrections exist (legacy law-level)
        corrections = self.correction_manager.get_corrections(law_id, None, folder_path)
        if not corrections:
            print(f"ℹ️  No corrections found for law {law_id}")
            return
        
        print(f"\n⚠️  WARNING: This will permanently delete corrections for law {law_id}")
        print(f"📋 Current status: {corrections.get('status', 'unknown')}")
        print(f"📋 Number of table corrections: {len(corrections.get('tables', {}))}")
        
        # Confirmation prompt
        try:
            confirmation = input(f"\n❓ Are you sure you want to reset corrections for {law_id}? Type 'yes' to confirm: ").strip().lower()
            if confirmation != 'yes':
                print("❌ Operation cancelled by user")
                return
        except KeyboardInterrupt:
            print("\n❌ Operation cancelled by user")
            return
        
        success = self.correction_manager.delete_corrections(law_id, folder_path)
        if success:
            self.logger.info(f"✅ Reset corrections for law {law_id}")
        else:
            self.logger.error(f"❌ Failed to reset corrections for law {law_id}")
    
    def reset_all_corrections(self, folder_path: str) -> None:
        """
        Reset all corrections in a folder.
        
        Args:
            folder_path: Path to the folder
        """
        full_path = self.base_path / folder_path
        
        if not full_path.exists():
            self.logger.error(f"Folder does not exist: {full_path}")
            return
        
        laws = self.get_laws_in_folder(str(full_path))
        
        if not laws:
            self.logger.warning(f"No laws found in folder: {full_path}")
            return
        
        # Get current progress to see which laws have corrections
        progress = self.correction_manager.get_progress_summary(folder_path)
        completed_laws = progress.get('laws_by_status', {}).get('completed', [])
        
        if not completed_laws:
            print(f"No corrections found to reset in folder: {folder_path}")
            return
        
        print(f"\n🔄 Resetting All Corrections in {folder_path}")
        print("=" * 60)
        print(f"Found {len(completed_laws)} laws with corrections to reset:")
        for law_id in completed_laws:
            print(f"  - {law_id}")
        
        # Confirm with user
        response = input(f"\nAre you sure you want to reset all {len(completed_laws)} corrections? (y/N): ")
        if response.lower() not in ['y', 'yes']:
            print("Operation cancelled.")
            return
        
        # Reset each law
        reset_count = 0
        failed_count = 0
        
        for law_id in completed_laws:
            try:
                success = self.correction_manager.delete_corrections(law_id, folder_path)
                if success:
                    reset_count += 1
                    print(f"✅ Reset {law_id}")
                else:
                    failed_count += 1
                    print(f"❌ Failed to reset {law_id}")
            except Exception as e:
                failed_count += 1
                print(f"❌ Error resetting {law_id}: {e}")
        
        print(f"\n📊 Reset Summary:")
        print(f"  Successfully reset: {reset_count}")
        print(f"  Failed: {failed_count}")
        print(f"  Total processed: {reset_count + failed_count}")
        
        if reset_count > 0:
            self.logger.info(f"✅ Successfully reset {reset_count} corrections in {folder_path}")
        if failed_count > 0:
            self.logger.warning(f"⚠️ Failed to reset {failed_count} corrections in {folder_path}")
    
    def review_folder_sequential(self, folder_path: str) -> None:
        """
        Review laws in a folder sequentially, one after another.
        
        Args:
            folder_path: Path to the folder
        """
        full_path = self.base_path / folder_path
        
        if not full_path.exists():
            self.logger.error(f"Folder does not exist: {full_path}")
            return
        
        laws = self.get_laws_in_folder(str(full_path))
        
        if not laws:
            self.logger.warning(f"No laws found in folder: {full_path}")
            return
        
        # Get current progress
        progress = self.correction_manager.get_progress_summary(folder_path)
        completed_laws = set(progress.get('laws_by_status', {}).get('completed', []))
        
        # Filter laws to review (only include laws with tables)
        laws_to_review = []
        for law_id in laws:
            unique_tables = self.extractor.extract_unique_tables_from_law(law_id, str(full_path))
            if unique_tables:  # Only include laws with tables
                laws_to_review.append((law_id, len(unique_tables), law_id in completed_laws))
        
        if not laws_to_review:
            print(f"❌ No laws with tables found in folder: {folder_path}")
            return
        
        # Sort by completion status (incomplete first) then by table count (more tables first)
        laws_to_review.sort(key=lambda x: (x[2], -x[1]))
        
        print(f"\n🔄 Sequential Table Review - {folder_path}")
        print("=" * 70)
        print(f"Found {len(laws_to_review)} laws with tables:")
        
        for i, (law_id, table_count, is_completed) in enumerate(laws_to_review, 1):
            status = "✅ Completed" if is_completed else "⏳ Pending"
            print(f"  {i:2d}. {law_id:<12} ({table_count:2d} tables) - {status}")
        
        print(f"\nStarting sequential review...")
        print("Navigate: 'n' = next, 'p' = previous, 's' = skip, 'q' = quit")
        print("=" * 70)
        
        current_index = 0
        
        while current_index < len(laws_to_review):
            law_id, table_count, is_completed = laws_to_review[current_index]
            
            print(f"\n📋 Law {current_index + 1}/{len(laws_to_review)}: {law_id}")
            print(f"   Tables: {table_count}, Status: {'✅ Completed' if is_completed else '⏳ Pending'}")
            
            if is_completed:
                print(f"   This law has already been reviewed.")
                choice = input(f"   Review again? (y/n/s=skip/q=quit): ").lower().strip()
                if choice == 'q':
                    break
                elif choice == 's' or choice == 'n':
                    current_index += 1
                    continue
                elif choice != 'y':
                    current_index += 1
                    continue
            
            try:
                # Review the law
                print(f"\n🔧 Opening table editor for law {law_id}...")
                self.review_law(law_id, str(full_path), folder_path)
                
                # After review, ask what to do next
                while True:
                    choice = input(f"\nLaw {law_id} reviewed. Next action? (n=next, p=previous, s=skip, r=review again, q=quit): ").lower().strip()
                    
                    if choice in ['n', 'next', '']:
                        current_index += 1
                        break
                    elif choice in ['p', 'previous', 'prev']:
                        if current_index > 0:
                            current_index -= 1
                        break
                    elif choice in ['s', 'skip']:
                        current_index += 1
                        break
                    elif choice in ['r', 'review', 'again']:
                        # Review again - stay at current index
                        break
                    elif choice in ['q', 'quit', 'exit']:
                        current_index = len(laws_to_review)  # Exit loop
                        break
                    else:
                        print("Invalid choice. Use: n=next, p=previous, s=skip, r=review again, q=quit")
                
            except KeyboardInterrupt:
                print(f"\n⚠️ Review interrupted by user")
                choice = input("Continue with next law? (y/n): ").lower().strip()
                if choice in ['n', 'no']:
                    break
                current_index += 1
            except Exception as e:
                self.logger.error(f"Error reviewing law {law_id}: {e}")
                print(f"❌ Error reviewing law {law_id}: {e}")
                choice = input("Continue with next law? (y/n): ").lower().strip()
                if choice in ['n', 'no']:
                    break
                current_index += 1
        
        # Final summary
        final_progress = self.correction_manager.get_progress_summary(folder_path)
        final_completed = len(final_progress.get('laws_by_status', {}).get('completed', []))
        
        print(f"\n🎉 Sequential Review Complete!")
        print("=" * 50)
        print(f"Final Status: {final_completed}/{len(laws_to_review)} laws with corrections")
        
        if final_completed < len(laws_to_review):
            remaining = len(laws_to_review) - final_completed
            print(f"Remaining: {remaining} laws still need review")
            print(f"Run again with --sequential to continue where you left off")
    
    def check_editor_status(self) -> None:
        """Check if the table editor is available."""
        editor_info = self.editor.get_editor_info()
        
        print("\n🔧 Table Editor Status")
        print("=" * 30)
        print(f"Editor path: {editor_info['editor_path']}")
        print(f"Available: {'✅ Yes' if editor_info['available'] else '❌ No'}")
        print(f"Version: {editor_info['version'] or 'Unknown'}")
        print("\nFeatures:")
        for feature in editor_info['features']:
            print(f"  - {feature}")
    
    def generate_report(self, folder_path: str, output_format: str = "all", 
                       output_dir: str = "reports") -> None:
        """
        Generate comprehensive statistics report for a folder.
        
        Args:
            folder_path: Path to the folder to analyze
            output_format: Format to export (json, csv, html, all)
            output_dir: Directory to save reports
        """
        print(f"\n📊 Generating {output_format.upper()} report for {folder_path}...")
        
        try:
            if output_format == "all":
                # Generate all formats
                output_files = generate_comprehensive_report(
                    folder_path, output_dir, str(self.base_path)
                )
                
                print("✅ Reports generated successfully:")
                for fmt, file_path in output_files.items():
                    print(f"  📄 {fmt.upper()}: {file_path}")
                    
            else:
                # Generate single format
                report = self.statistics_collector.generate_folder_report(folder_path)
                
                # Create output directory
                output_path = Path(output_dir)
                output_path.mkdir(exist_ok=True)
                
                # Generate filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"table_review_{folder_path}_{timestamp}.{output_format}"
                file_path = output_path / filename
                
                # Export based on format
                if output_format == "json":
                    self.report_exporter.export_json(report, str(file_path))
                elif output_format == "csv":
                    self.report_exporter.export_csv(report, str(file_path))
                elif output_format == "html":
                    self.report_exporter.export_html(report, str(file_path))
                else:
                    raise ValueError(f"Unsupported format: {output_format}")
                
                print(f"✅ {output_format.upper()} report generated: {file_path}")
                
        except Exception as e:
            self.logger.error(f"Failed to generate report: {e}")
            print(f"❌ Report generation failed: {e}")
    
    def show_detailed_statistics(self, folder_path: str) -> None:
        """
        Show detailed statistics for a folder.
        
        Args:
            folder_path: Path to the folder to analyze
        """
        try:
            report = self.statistics_collector.generate_folder_report(folder_path)
            
            print(f"\n📊 Detailed Statistics for {folder_path}")
            print("=" * 60)
            
            # Law statistics
            print("\n🏛️  Law Statistics:")
            print(f"  Total laws: {report.law_stats.total_laws}")
            print(f"  Completed laws: {report.law_stats.completed_laws}")
            print(f"  Laws with tables: {report.law_stats.laws_with_tables}")
            print(f"  Laws without tables: {report.law_stats.laws_without_tables}")
            print(f"  Laws with errors: {report.law_stats.laws_with_errors}")
            print(f"  Completion rate: {report.law_stats.completion_rate:.1f}%")
            
            if report.law_stats.avg_processing_time:
                print(f"  Avg processing time: {report.law_stats.avg_processing_time:.1f}s")
            
            # Table statistics
            print("\n📋 Table Statistics:")
            print(f"  Total tables: {report.table_stats.total_tables}")
            print(f"  Confirmed tables: {report.table_stats.confirmed_tables}")
            print(f"  Rejected tables: {report.table_stats.rejected_tables}")
            print(f"  Edited tables: {report.table_stats.edited_tables}")
            print(f"  Merged tables: {report.table_stats.merged_tables}")
            print(f"  Tables with errors: {report.table_stats.tables_with_errors}")
            print(f"  Avg tables per law: {report.table_stats.avg_tables_per_law:.1f}")
            
            # Processing summary
            if report.processing_summary:
                print("\n⚡ Efficiency Metrics:")
                efficiency = report.processing_summary.get("efficiency_metrics", {})
                
                if efficiency.get("laws_per_hour"):
                    print(f"  Laws per hour: {efficiency['laws_per_hour']:.1f}")
                if efficiency.get("tables_per_hour"):
                    print(f"  Tables per hour: {efficiency['tables_per_hour']:.1f}")
                if efficiency.get("error_rate"):
                    print(f"  Error rate: {efficiency['error_rate']:.1f}%")
                
                # Table distribution
                print("\n📈 Table Distribution:")
                dist = report.processing_summary.get("table_distribution", {})
                print(f"  Laws with 1 table: {dist.get('laws_with_1_table', 0)}")
                print(f"  Laws with 2-5 tables: {dist.get('laws_with_2_5_tables', 0)}")
                print(f"  Laws with 6+ tables: {dist.get('laws_with_6_plus_tables', 0)}")
                print(f"  Max tables in single law: {dist.get('max_tables_in_single_law', 0)}")
                print(f"  Median tables per law: {dist.get('median_tables_per_law', 0)}")
            
            # Show top laws by table count
            laws_with_most_tables = sorted(
                [r for r in report.detailed_results if r["table_count"] > 0],
                key=lambda x: x["table_count"],
                reverse=True
            )[:5]
            
            if laws_with_most_tables:
                print("\n🔝 Laws with Most Tables:")
                for i, law in enumerate(laws_with_most_tables, 1):
                    status = "✅" if law["completed"] else "⏳"
                    print(f"  {i}. {law['law_id']}: {law['table_count']} tables {status}")
            
        except Exception as e:
            self.logger.error(f"Failed to show statistics: {e}")
            print(f"❌ Statistics failed: {e}")
    
    def export_corrections(self, folder_path: str, export_path: Optional[str] = None) -> None:
        """
        Export all correction JSON files from a folder to a specified location.
        
        Args:
            folder_path: Path to the folder containing laws with corrections
            export_path: Path where to export the corrections (will prompt if not provided)
        """
        full_path = self.base_path / folder_path
        
        if not full_path.exists():
            self.logger.error(f"Folder does not exist: {full_path}")
            return
        
        # If export path not provided, prompt user
        if not export_path:
            print("\n📤 Export Table Corrections")
            print("=" * 50)
            print(f"Source folder: {full_path}")
            export_path = input("Enter export destination path: ").strip()
            
            if not export_path:
                print("❌ Export cancelled - no path provided")
                return
        
        # Create export directory
        export_dir = Path(export_path)
        try:
            export_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.logger.error(f"Failed to create export directory: {e}")
            print(f"❌ Failed to create export directory: {e}")
            return
        
        # Find all correction files
        correction_files = []
        exported_count = 0
        skipped_count = 0
        
        print(f"\n🔍 Scanning for correction files in {folder_path}...")
        
        # Walk through all subdirectories
        for law_dir in full_path.iterdir():
            if law_dir.is_dir():
                # Look for correction files in the law directory
                correction_pattern = f"{law_dir.name}-table-corrections.json"
                correction_file = law_dir / correction_pattern
                
                if correction_file.exists():
                    correction_files.append((law_dir.name, correction_file))
        
        if not correction_files:
            print(f"❌ No correction files found in {folder_path}")
            return
        
        print(f"Found {len(correction_files)} correction files to export")
        
        # Create a subdirectory with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_subdir = export_dir / f"table_corrections_{folder_path}_{timestamp}"
        export_subdir.mkdir(exist_ok=True)
        
        # Export each file
        print(f"\n📦 Exporting to: {export_subdir}")
        
        for law_id, source_file in correction_files:
            try:
                # Create law subdirectory in export location
                law_export_dir = export_subdir / law_id
                law_export_dir.mkdir(exist_ok=True)
                
                # Copy correction file
                dest_file = law_export_dir / source_file.name
                shutil.copy2(source_file, dest_file)
                
                # Verify the file was copied correctly
                with open(source_file, 'r') as f:
                    original_data = json.load(f)
                with open(dest_file, 'r') as f:
                    copied_data = json.load(f)
                
                if original_data == copied_data:
                    exported_count += 1
                    print(f"  ✅ {law_id}/{source_file.name}")
                else:
                    skipped_count += 1
                    print(f"  ⚠️ {law_id}/{source_file.name} - verification failed")
                    
            except Exception as e:
                skipped_count += 1
                self.logger.error(f"Failed to export {law_id}: {e}")
                print(f"  ❌ {law_id}/{source_file.name} - {e}")
        
        # Create a summary file
        summary_file = export_subdir / "export_summary.json"
        summary_data = {
            "export_timestamp": timestamp,
            "source_folder": str(full_path),
            "export_location": str(export_subdir),
            "total_files": len(correction_files),
            "exported": exported_count,
            "skipped": skipped_count,
            "exported_files": [
                {
                    "law_id": law_id,
                    "file_name": source_file.name,
                    "file_path": str(source_file.relative_to(self.base_path))
                }
                for law_id, source_file in correction_files
            ]
        }
        
        with open(summary_file, 'w') as f:
            json.dump(summary_data, f, indent=2)
        
        # Final summary
        print(f"\n📊 Export Summary")
        print("=" * 50)
        print(f"Total files found: {len(correction_files)}")
        print(f"Successfully exported: {exported_count}")
        print(f"Skipped/Failed: {skipped_count}")
        print(f"Export location: {export_subdir}")
        print(f"Summary file: {summary_file}")
        
        if exported_count > 0:
            self.logger.info(f"✅ Successfully exported {exported_count} correction files to {export_subdir}")
        else:
            self.logger.warning("⚠️ No files were successfully exported")


def main():
    """Main entry point for the table review system."""
    parser = argparse.ArgumentParser(
        description="Review and correct table structures in legal documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Review all tables in test folder (run a3_table_extraction first!)
  python -m src.main_entry_points.a4_table_review --target zhlex_files_test
  
  # Review specific law (all versions)
  python -m src.main_entry_points.a4_table_review --target zhlex_files_test --law 170.4
  
  # Review specific law version
  python -m src.main_entry_points.a4_table_review --target zhlex_files_test --law 170.4 --version 129
  
  # Review latest version of all laws
  python -m src.main_entry_points.a4_table_review --target zhlex_files_test --version latest
  
  # Review all versions of all laws
  python -m src.main_entry_points.a4_table_review --target zhlex_files_test --version all
  
  # Show review progress
  python -m src.main_entry_points.a4_table_review --target zhlex_files_test --show-status
  
  # Reset corrections for a law
  python -m src.main_entry_points.a4_table_review --target zhlex_files_test --law 170.4 --reset
  
  # Reset all corrections in folder
  python -m src.main_entry_points.a4_table_review --target zhlex_files_test --reset-all
        """
    )
    
    # Core standardized arguments (8 total)
    parser.add_argument(
        "--target",
        required=True,
        help="Target folder to review (e.g., zhlex_files_test, zhlex_files, fedlex_files_test, fedlex_files)"
    )
    
    parser.add_argument(
        "--law",
        help="Review specific law (e.g., 170.4)"
    )
    
    parser.add_argument(
        "--version",
        help="Specify version(s): specific version (e.g., '129'), 'latest', or 'all'"
    )
    
    parser.add_argument(
        "--show-status",
        action="store_true",
        help="Show review progress and statistics"
    )
    
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset corrections for a law (requires --law)"
    )
    
    parser.add_argument(
        "--reset-all",
        action="store_true",
        help="Reset all corrections in the specified target folder"
    )
    
    parser.add_argument(
        "--mode",
        choices=["concurrent", "sequential"],
        default="sequential",
        help="Processing mode: sequential (interactive) or concurrent (batch) - default: sequential"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        default="info",
        help="Logging level - default: info"
    )
    
    args = parser.parse_args()
    
    # Setup logging with standardized log level
    log_level_map = {
        'debug': 'DEBUG',
        'info': 'INFO', 
        'warning': 'WARNING',
        'error': 'ERROR'
    }
    setup_logging(log_level=log_level_map[args.log_level])
    
    # Create reviewer with simplified configuration
    simulate_editor = (args.log_level == 'debug')  # Auto-enable simulation in debug mode
    max_workers = None  # Auto-detect worker count
    reviewer = LawTableReview(simulate_editor=simulate_editor, max_workers=max_workers)
    
    try:
        # Handle status/progress display
        if args.show_status:
            reviewer.show_progress(args.target)
            
        # Handle reset operations
        elif args.reset_all:
            reviewer.reset_all_corrections(args.target)
        elif args.reset:
            if args.law:
                reviewer.reset_law_corrections(args.law, args.target)
            else:
                print("❌ --reset requires --law argument to specify which law to reset")
                sys.exit(1)
                
        # Handle law-specific review
        elif args.law:
            if args.version:
                # Review specific law with version filtering
                versions_to_review = reviewer.resolve_versions(args.law, args.version, args.target)
                if versions_to_review:
                    reviewer.review_specific_law_versions(args.law, versions_to_review, args.target)
                else:
                    print(f"❌ No valid versions found for law {args.law} with version spec '{args.version}'")
            else:
                # Review all versions of specific law
                reviewer.review_specific_law(args.law, args.target)
                
        # Handle version-filtered review
        elif args.version:
            # Review all laws with version filtering
            if args.version == "latest":
                reviewer.review_folder_latest_versions(args.target, resume=True)
            elif args.version == "all":
                reviewer.review_folder_all_versions(args.target, resume=True)
            else:
                print(f"❌ Version '{args.version}' requires --law argument for specific version")
                
        # Default: review folder based on mode
        else:
            if args.mode == "sequential":
                reviewer.review_folder_sequential(args.target)
            else:  # concurrent mode
                reviewer.review_folder(
                    args.target,
                    use_batch=True,
                    resume=True,
                    max_workers=max_workers
                )
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()