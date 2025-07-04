"""
Table Review Main Entry Point

Human-in-the-loop table review system for the zhlaw pipeline.
"""

import argparse
import sys
from pathlib import Path
import logging
from typing import Optional
from datetime import datetime

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
    
    def review_folder(self, folder_path: str, use_batch: bool = True, resume: bool = True, 
                     max_workers: Optional[int] = None) -> None:
        """
        Review all laws in a folder using improved batch processing.
        
        Args:
            folder_path: Path to the folder containing laws
            use_batch: Whether to use batch processing (recommended)
            resume: Whether to resume from previous progress
            max_workers: Maximum number of worker threads (None for auto)
        """
        if use_batch:
            self.review_folder_batch(folder_path, resume=resume, max_workers=max_workers)
        else:
            self._review_folder_sequential(folder_path)
    
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
            
            if self.correction_manager.is_law_completed(law_id, folder_path):
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
    
    def review_law(self, law_id: str, base_path: str, folder_name: str) -> None:
        """
        Review all tables in a single law.
        
        Args:
            law_id: The law identifier
            base_path: Full path to the law files
            folder_name: Name of the folder for corrections
        """
        try:
            # Extract unique tables across all versions
            unique_tables = self.extractor.extract_unique_tables_from_law(law_id, base_path)
            
            if not unique_tables:
                self.logger.info(f"No tables found in law {law_id}")
                return
            
            # Check if already reviewed
            existing_corrections = self.correction_manager.get_corrections(law_id, folder_name)
            if existing_corrections:
                self.logger.info(f"Law {law_id} already has corrections, skipping")
                return
            
            self.logger.info(f"Found {len(unique_tables)} unique tables in law {law_id}")
            
            # Launch table_editor (with simulation mode if requested)
            if self.simulate_editor:
                self.editor.force_simulation = True
            corrections = self.editor.launch_editor_for_law(law_id, unique_tables, base_path)
            
            if corrections:
                # Save corrections
                success = self.correction_manager.save_corrections(law_id, corrections, folder_name)
                if success:
                    self.logger.info(f"✅ Saved corrections for law {law_id}")
                else:
                    self.logger.error(f"❌ Failed to save corrections for law {law_id}")
            else:
                self.logger.warning(f"No corrections received for law {law_id}")
                
        except Exception as e:
            self.logger.error(f"Error reviewing law {law_id}: {e}")
    
    def show_progress(self, folder_path: str) -> None:
        """
        Show review progress for a folder.
        
        Args:
            folder_path: Path to the folder
        """
        progress = self.correction_manager.get_progress_summary(folder_path)
        
        # Check if there's an error message (not just error count)
        if isinstance(progress, dict) and "error" in progress and isinstance(progress["error"], str):
            self.logger.error(progress["error"])
            return
        
        print(f"\n📊 Review Progress for {folder_path}")
        print("=" * 50)
        print(f"Total laws: {progress['total_laws']}")
        print(f"Completed: {progress['completed']}")
        print(f"Not started: {progress['not_started']}")
        print(f"In progress: {progress['in_progress']}")
        print(f"Errors: {progress['error']}")
        
        if progress['total_laws'] > 0:
            completion_rate = (progress['completed'] / progress['total_laws']) * 100
            print(f"Completion rate: {completion_rate:.1f}%")
        
        # Show detailed status
        for status, laws in progress['laws_by_status'].items():
            if laws:
                print(f"\n{status.title()} ({len(laws)} laws):")
                for law_id in laws[:10]:  # Show first 10
                    print(f"  - {law_id}")
                if len(laws) > 10:
                    print(f"  ... and {len(laws) - 10} more")
    
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
        self.review_law(law_id, str(full_path), folder_path)
    
    def reset_law_corrections(self, law_id: str, folder_path: str) -> None:
        """
        Reset corrections for a law (delete existing corrections).
        
        Args:
            law_id: The law identifier
            folder_path: Path to the folder
        """
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


def main():
    """Main entry point for the table review system."""
    parser = argparse.ArgumentParser(
        description="Review and correct table structures in legal documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Review all tables in test folder with batch processing
  python -m src.main_entry_points.table_review --folder zhlex_files_test
  
  # Review with custom worker count
  python -m src.main_entry_points.table_review --folder zhlex_files_test --workers 8
  
  # Review specific law
  python -m src.main_entry_points.table_review --folder zhlex_files_test --law 170.4
  
  # Sequential review mode (one law at a time)
  python -m src.main_entry_points.table_review --folder zhlex_files_test --sequential
  
  # Show detailed statistics
  python -m src.main_entry_points.table_review --folder zhlex_files_test --stats
  
  # Generate comprehensive report (all formats)
  python -m src.main_entry_points.table_review --folder zhlex_files_test --report all
  
  # Generate HTML report only
  python -m src.main_entry_points.table_review --folder zhlex_files_test --report html
  
  # Show basic progress
  python -m src.main_entry_points.table_review --folder zhlex_files_test --status
  
  # Use legacy sequential mode
  python -m src.main_entry_points.table_review --folder zhlex_files_test --no-batch
  
  # Reset corrections for a law
  python -m src.main_entry_points.table_review --folder zhlex_files_test --law 170.4 --reset
  
  # Reset all corrections in a folder
  python -m src.main_entry_points.table_review --folder zhlex_files_test --reset-all
        """
    )
    
    parser.add_argument(
        "--folder",
        required=True,
        help="Folder to review (e.g., zhlex_files_test, zhlex_files)"
    )
    
    parser.add_argument(
        "--law",
        help="Review specific law (e.g., 170.4)"
    )
    
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show review progress"
    )
    
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset corrections for a law (use with --law) or all laws in folder"
    )
    
    parser.add_argument(
        "--reset-all",
        action="store_true",
        help="Reset all corrections in the specified folder"
    )
    
    parser.add_argument(
        "--check-editor",
        action="store_true",
        help="Check table editor availability"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Use simulation mode instead of launching browser editor"
    )
    
    parser.add_argument(
        "--workers",
        type=int,
        help="Number of worker threads for parallel processing (default: auto-detect)"
    )
    
    parser.add_argument(
        "--no-batch",
        action="store_true",
        help="Disable batch processing (use legacy sequential mode)"
    )
    
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Use interactive sequential mode - review laws one after another"
    )
    
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Don't resume from previous progress, start fresh"
    )
    
    parser.add_argument(
        "--report",
        choices=["json", "csv", "html", "all"],
        help="Generate statistics report in specified format"
    )
    
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show detailed statistics for the folder"
    )
    
    parser.add_argument(
        "--output-dir",
        default="reports",
        help="Directory to save reports (default: reports)"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = 'DEBUG' if args.verbose else 'INFO'
    setup_logging(log_level=log_level)
    
    # Create reviewer
    reviewer = LawTableReview(simulate_editor=args.simulate, max_workers=args.workers)
    
    try:
        if args.check_editor:
            reviewer.check_editor_status()
        elif args.report:
            reviewer.generate_report(args.folder, args.report, args.output_dir)
        elif args.stats:
            reviewer.show_detailed_statistics(args.folder)
        elif args.status:
            reviewer.show_progress(args.folder)
        elif args.reset_all:
            reviewer.reset_all_corrections(args.folder)
        elif args.reset:
            if args.law:
                reviewer.reset_law_corrections(args.law, args.folder)
            else:
                # If no specific law, reset all corrections in folder
                reviewer.reset_all_corrections(args.folder)
        elif args.sequential:
            reviewer.review_folder_sequential(args.folder)
        elif args.law:
            reviewer.review_specific_law(args.law, args.folder)
        else:
            reviewer.review_folder(
                args.folder, 
                use_batch=not args.no_batch,
                resume=not args.no_resume,
                max_workers=args.workers
            )
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()