"""
Table Extraction Main Entry Point

Automated table extraction system for the zhlaw pipeline with per-version correction file creation.
This is Step 1 of the manual table review process - extracts tables and creates per-version correction files with undefined status.
"""

import argparse
import sys
from pathlib import Path
import logging
from typing import Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.modules.manual_review_module.table_extractor import LawTableExtractor
from src.modules.manual_review_module.correction_manager import CorrectionManager
from src.logging_config import setup_logging


class TableExtractionProcessor:
    """Main class for automated table extraction with per-version correction file creation."""
    
    def __init__(self, base_path: str = "data/zhlex", max_workers: Optional[int] = None):
        self.base_path = Path(base_path)
        self.extractor = LawTableExtractor()
        self.correction_manager = CorrectionManager(str(self.base_path))
        self.logger = logging.getLogger(__name__)
        self.max_workers = max_workers or 4
    
    def extract_tables_for_folder(self, folder_path: str, concurrent: bool = True) -> None:
        """
        Extract tables for all laws in a folder and create per-version correction files.
        
        Args:
            folder_path: Path to the folder containing laws
            concurrent: Whether to use concurrent processing
        """
        full_path = self.base_path / folder_path
        
        if not full_path.exists():
            self.logger.error(f"Folder does not exist: {full_path}")
            return
        
        # Get all laws in the folder
        laws = self.extractor.get_laws_in_folder(str(full_path))
        
        if not laws:
            self.logger.warning(f"No laws found in folder: {full_path}")
            return
        
        self.logger.info(f"Starting table extraction for {len(laws)} laws in {folder_path}")
        print(f"\n📊 Table Extraction - {folder_path}")
        print("=" * 60)
        print(f"Processing {len(laws)} laws...")
        
        start_time = time.time()
        
        if concurrent:
            self._extract_concurrent(laws, str(full_path), folder_path)
        else:
            self._extract_sequential(laws, str(full_path), folder_path)
        
        elapsed_time = time.time() - start_time
        
        # Final summary
        print(f"\n🎉 TABLE EXTRACTION COMPLETED")
        print("=" * 60)
        print(f"Processed laws: {len(laws)}")
        print(f"Total time: {elapsed_time/60:.1f} minutes")
        print(f"Average time per law: {elapsed_time/len(laws):.1f} seconds")
        print(f"\nNext step: Run table review with:")
        print(f"python -m src.main_entry_points.a4_table_review --folder {folder_path}")
    
    def _extract_concurrent(self, laws: list, full_path: str, folder_path: str) -> None:
        """Extract tables concurrently."""
        completed = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all extraction tasks
            future_to_law = {
                executor.submit(self._extract_law_tables, law_id, full_path, folder_path): law_id 
                for law_id in laws
            }
            
            # Process completed tasks
            for future in as_completed(future_to_law):
                law_id = future_to_law[future]
                completed += 1
                
                try:
                    table_count = future.result()
                    status = f"✅ {law_id}: {table_count} tables extracted"
                except Exception as e:
                    self.logger.error(f"Error extracting tables for law {law_id}: {e}")
                    status = f"❌ {law_id}: extraction failed"
                
                # Progress update
                progress = (completed / len(laws)) * 100
                print(f"[{completed:3d}/{len(laws)}] ({progress:5.1f}%) {status}")
    
    def _extract_sequential(self, laws: list, full_path: str, folder_path: str) -> None:
        """Extract tables sequentially."""
        for i, law_id in enumerate(laws, 1):
            try:
                table_count = self._extract_law_tables(law_id, full_path, folder_path)
                status = f"✅ {law_id}: {table_count} tables extracted"
            except Exception as e:
                self.logger.error(f"Error extracting tables for law {law_id}: {e}")
                status = f"❌ {law_id}: extraction failed"
            
            # Progress update
            progress = (i / len(laws)) * 100
            print(f"[{i:3d}/{len(laws)}] ({progress:5.1f}%) {status}")
    
    def _extract_law_tables(self, law_id: str, base_path: str, folder_name: str = None) -> int:
        """
        Extract tables for a single law and create per-version correction files.
        
        Args:
            law_id: The law identifier
            base_path: Full path to the law files
            folder_name: Name of the folder for correction files (e.g., 'zhlex_files_test')
            
        Returns:
            Number of unique tables extracted across all versions
        """
        try:
            # Find all versions for this law
            versions = self.extractor.find_law_versions(law_id, base_path)
            if not versions:
                self.logger.warning(f"No versions found for law {law_id}")
                return 0
            
            total_tables = 0
            
            # Extract tables for each version and create correction files
            for version in versions.keys():
                version_tables = self.extractor.extract_tables_from_version(law_id, version, base_path)
                if version_tables:
                    # Create correction file for this version if folder_name is provided
                    if folder_name:
                        success = self.correction_manager.create_correction_file_for_version(
                            law_id, version, version_tables, folder_name
                        )
                        if success:
                            self.logger.debug(f"Created correction file for {law_id} version {version}")
                        else:
                            self.logger.warning(f"Failed to create correction file for {law_id} version {version}")
                    
                    total_tables += len(version_tables)
            
            self.logger.info(f"Extracted {total_tables} total tables across {len(versions)} versions for law {law_id}")
            return total_tables
            
        except Exception as e:
            self.logger.error(f"Failed to extract tables for law {law_id}: {e}")
            raise
    
    def extract_tables_for_law(self, law_id: str, folder_path: str) -> None:
        """
        Extract tables for a specific law.
        
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
        
        print(f"\n📊 Table Extraction - Law {law_id}")
        print("=" * 50)
        
        start_time = time.time()
        
        try:
            table_count = self._extract_law_tables(law_id, str(full_path), folder_path)
            elapsed_time = time.time() - start_time
            
            print(f"✅ Extraction completed")
            print(f"Tables extracted: {table_count}")
            print(f"Time taken: {elapsed_time:.1f} seconds")
            print(f"\nNext step: Review tables with:")
            print(f"python -m src.main_entry_points.a4_table_review --law {law_id} --folder {folder_path}")
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            print(f"❌ Extraction failed: {e}")
            print(f"Time taken: {elapsed_time:.1f} seconds")
    
    def show_extraction_status(self, folder_path: str) -> None:
        """
        Show extraction status for a folder.
        
        Args:
            folder_path: Path to the folder
        """
        full_path = self.base_path / folder_path
        
        if not full_path.exists():
            self.logger.error(f"Folder does not exist: {full_path}")
            return
        
        laws = self.extractor.get_laws_in_folder(str(full_path))
        
        if not laws:
            print(f"No laws found in folder: {folder_path}")
            return
        
        print(f"\n📊 Table Extraction Status - {folder_path}")
        print("=" * 60)
        
        laws_with_tables = 0
        total_tables = 0
        
        for law_id in laws:
            try:
                unique_tables = self.extractor.extract_unique_tables_from_law(law_id, str(full_path))
                table_count = len(unique_tables)
                
                if table_count > 0:
                    laws_with_tables += 1
                    total_tables += table_count
                    print(f"  {law_id:<15} {table_count:3d} tables")
                else:
                    print(f"  {law_id:<15}   0 tables")
                    
            except Exception as e:
                print(f"  {law_id:<15} ERROR: {e}")
        
        print(f"\n📈 Summary:")
        print(f"  Total laws: {len(laws)}")
        print(f"  Laws with tables: {laws_with_tables}")
        print(f"  Laws without tables: {len(laws) - laws_with_tables}")
        print(f"  Total unique tables: {total_tables}")
        
        if laws_with_tables > 0:
            print(f"  Average tables per law (with tables): {total_tables / laws_with_tables:.1f}")
    
    def regenerate_tables_for_law(self, law_id: str, folder_path: str) -> None:
        """
        Regenerate table data for a specific law from scratch.
        
        This will:
        1. Clear any existing correction files for the law
        2. Re-extract tables from the original JSON files
        3. Create fresh table data
        
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
        
        print(f"\n🔄 REGENERATING TABLE DATA - Law {law_id}")
        print("=" * 60)
        print("⚠️  WARNING: This will permanently delete existing corrections and re-extract table data from scratch!")
        
        # Check if corrections exist
        corrections_exist = self.correction_manager.get_corrections(law_id, folder_path) is not None
        if corrections_exist:
            print(f"📋 Existing corrections found for law {law_id}")
        else:
            print(f"📋 No existing corrections found for law {law_id}")
        
        print(f"\nThis action will:")
        print(f"  • Clear any existing correction files for law {law_id}")
        print(f"  • Re-extract table data from original JSON files")
        print(f"  • Reset the law to 'not reviewed' status")
        
        # Confirmation prompt
        try:
            confirmation = input("\n❓ Are you sure you want to proceed? Type 'yes' to confirm: ").strip().lower()
            if confirmation != 'yes':
                print("❌ Operation cancelled by user")
                return
        except KeyboardInterrupt:
            print("\n❌ Operation cancelled by user")
            return
        
        start_time = time.time()
        
        try:
            # Step 1: Clear existing correction files (both legacy and per-version)
            print(f"\n1️⃣ Clearing existing corrections...")
            reset_results = self.correction_manager.reset_law_corrections(law_id, folder_path)
            
            if reset_results["success"]:
                print(f"   ✅ Cleared {reset_results['files_deleted']} correction file(s) for law {law_id}")
                if reset_results["legacy_file_deleted"]:
                    print(f"      📋 Deleted legacy correction file")
                if reset_results["version_files_deleted"] > 0:
                    print(f"      📋 Deleted {reset_results['version_files_deleted']} per-version correction file(s)")
            else:
                print(f"   ℹ️  No existing corrections found for law {law_id}")
            
            # Step 2: Re-extract tables
            print(f"\n2️⃣ Re-extracting table data...")
            table_count = self._extract_law_tables(law_id, str(full_path), folder_path)
            
            elapsed_time = time.time() - start_time
            
            # Success summary
            print(f"\n🎉 REGENERATION COMPLETED")
            print("=" * 60)
            print(f"Law: {law_id}")
            print(f"Tables extracted: {table_count}")
            print(f"Correction files cleared: {reset_results['files_deleted']} file(s)")
            print(f"Time taken: {elapsed_time:.1f} seconds")
            print(f"\nNext step: Review tables with:")
            print(f"python -m src.main_entry_points.a4_table_review --law {law_id} --folder {folder_path}")
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            print(f"❌ Regeneration failed: {e}")
            print(f"Time taken: {elapsed_time:.1f} seconds")
    
    def regenerate_tables_for_folder(self, folder_path: str, concurrent: bool = True) -> None:
        """
        Regenerate table data for all laws in a folder from scratch.
        
        This will:
        1. Clear all existing correction files in the folder
        2. Re-extract tables from original JSON files for all laws
        3. Create fresh table data for the entire folder
        
        Args:
            folder_path: Path to the folder containing laws
            concurrent: Whether to use concurrent processing
        """
        full_path = self.base_path / folder_path
        
        if not full_path.exists():
            self.logger.error(f"Folder does not exist: {full_path}")
            return
        
        # Get all laws in the folder
        laws = self.extractor.get_laws_in_folder(str(full_path))
        
        if not laws:
            self.logger.warning(f"No laws found in folder: {full_path}")
            return
        
        print(f"\n🔄 REGENERATING ALL TABLE DATA - {folder_path}")
        print("=" * 70)
        print("⚠️  WARNING: This will permanently delete ALL existing corrections in the folder!")
        
        # Check for existing corrections
        laws_with_corrections = self.correction_manager.get_all_laws_with_corrections(folder_path)
        
        print(f"\n📊 Folder analysis:")
        print(f"  • Total laws in folder: {len(laws)}")
        print(f"  • Laws with existing corrections: {len(laws_with_corrections)}")
        if laws_with_corrections:
            print(f"  • Laws that will lose corrections: {', '.join(laws_with_corrections[:5])}")
            if len(laws_with_corrections) > 5:
                print(f"    ... and {len(laws_with_corrections) - 5} more")
        
        print(f"\nThis action will:")
        print(f"  • Clear ALL existing correction files in {folder_path}")
        print(f"  • Re-extract table data from original JSON files for all {len(laws)} laws")
        print(f"  • Reset ALL laws to 'not reviewed' status")
        print(f"  • Process using {'concurrent' if concurrent else 'sequential'} mode")
        
        # Confirmation prompt
        try:
            confirmation = input(f"\n❓ Are you sure you want to regenerate ALL {len(laws)} laws? Type 'yes' to confirm: ").strip().lower()
            if confirmation != 'yes':
                print("❌ Operation cancelled by user")
                return
        except KeyboardInterrupt:
            print("\n❌ Operation cancelled by user")
            return
        
        start_time = time.time()
        
        try:
            # Step 1: Clear all existing correction files
            print(f"\n1️⃣ Clearing all existing corrections...")
            reset_results = self.correction_manager.reset_all_corrections(folder_path)
            print(f"   📊 Laws with corrections: {reset_results['total_found']}")
            print(f"   📊 Per-version files found: {reset_results['per_version_files_found']}")
            print(f"   ✅ Laws successfully cleared: {reset_results['successfully_reset']}")
            print(f"   🗑️ Total files deleted: {reset_results['files_deleted']}")
            if reset_results['failed'] > 0:
                print(f"   ❌ Failed to clear: {reset_results['failed']} ({reset_results['failed_laws']})")
            
            # Step 2: Re-extract all tables
            print(f"\n2️⃣ Re-extracting table data for all laws...")
            
            if concurrent:
                self._extract_concurrent(laws, str(full_path), folder_path)
            else:
                self._extract_sequential(laws, str(full_path), folder_path)
            
            elapsed_time = time.time() - start_time
            
            # Final summary
            print(f"\n🎉 FOLDER REGENERATION COMPLETED")
            print("=" * 70)
            print(f"Folder: {folder_path}")
            print(f"Laws processed: {len(laws)}")
            print(f"Laws with cleared corrections: {reset_results['successfully_reset']}")
            print(f"Total correction files deleted: {reset_results['files_deleted']}")
            print(f"Total time: {elapsed_time/60:.1f} minutes")
            print(f"Average time per law: {elapsed_time/len(laws):.1f} seconds")
            print(f"\nNext step: Review tables with:")
            print(f"python -m src.main_entry_points.a4_table_review --folder {folder_path}")
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            print(f"❌ Folder regeneration failed: {e}")
            print(f"Time taken: {elapsed_time/60:.1f} minutes")


def main():
    """Main entry point for the table extraction system."""
    parser = argparse.ArgumentParser(
        description="Extract table structures from legal documents and create per-version correction files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract tables for all laws in test folder and create correction files (concurrent)
  python -m src.main_entry_points.a3_table_extraction --folder zhlex_files_test
  
  # Extract tables for all laws in production folder and create correction files
  python -m src.main_entry_points.a3_table_extraction --folder zhlex_files
  
  # Extract tables for specific law
  python -m src.main_entry_points.a3_table_extraction --law 170.4 --folder zhlex_files_test
  
  # Regenerate table data for specific law (clears corrections)
  python -m src.main_entry_points.a3_table_extraction --law 170.4 --folder zhlex_files_test --regenerate
  
  # Regenerate table data for all laws (clears all corrections)
  python -m src.main_entry_points.a3_table_extraction --folder zhlex_files_test --regenerate-all
  
  # Sequential processing (single-threaded)
  python -m src.main_entry_points.a3_table_extraction --folder zhlex_files_test --no-concurrent
  
  # Show extraction status
  python -m src.main_entry_points.a3_table_extraction --status --folder zhlex_files_test
  
  # Custom worker count
  python -m src.main_entry_points.a3_table_extraction --folder zhlex_files_test --workers 8
        """
    )
    
    parser.add_argument(
        "--folder",
        required=True,
        help="Folder to process (e.g., zhlex_files_test, zhlex_files)"
    )
    
    parser.add_argument(
        "--law",
        help="Extract tables for specific law only (e.g., 170.4)"
    )
    
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show extraction status for folder"
    )
    
    parser.add_argument(
        "--workers",
        type=int,
        help="Number of worker threads for concurrent processing (default: 4)"
    )
    
    parser.add_argument(
        "--no-concurrent",
        action="store_true",
        help="Disable concurrent processing (use sequential mode)"
    )
    
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="Regenerate table data for specific law from scratch (clears corrections, requires --law)"
    )
    
    parser.add_argument(
        "--regenerate-all",
        action="store_true",
        help="Regenerate table data for all laws in folder from scratch (clears all corrections)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Validate argument combinations
    if args.regenerate and not args.law:
        print("❌ Error: --regenerate requires --law to specify which law to regenerate")
        sys.exit(1)
    
    if args.regenerate and args.regenerate_all:
        print("❌ Error: Cannot use --regenerate and --regenerate-all together")
        sys.exit(1)
    
    # Setup logging
    log_level = 'DEBUG' if args.verbose else 'INFO'
    setup_logging(log_level=log_level)
    
    # Create processor
    processor = TableExtractionProcessor(max_workers=args.workers)
    
    try:
        if args.regenerate_all:
            processor.regenerate_tables_for_folder(
                args.folder,
                concurrent=not args.no_concurrent
            )
        elif args.regenerate:
            processor.regenerate_tables_for_law(args.law, args.folder)
        elif args.status:
            processor.show_extraction_status(args.folder)
        elif args.law:
            processor.extract_tables_for_law(args.law, args.folder)
        else:
            processor.extract_tables_for_folder(
                args.folder, 
                concurrent=not args.no_concurrent
            )
            
    except KeyboardInterrupt:
        print("\nExtraction cancelled by user")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()