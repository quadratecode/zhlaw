"""Build SQL database from markdown law files.

This script creates an SQLite database from processed markdown law files.
It processes markdown files from the md-files directory structure and creates
a comprehensive database with laws, versions, and provisions tables.

Usage:
    python -m src.main_entry_points.e1_build_database [options]

Options:
    --input-dir: Input directory containing md-files (default: public/)
    --output-file: Database file name (default: zhlaw.db)
    --collections: Which collections to process (zh, ch, all - default: all)
    --mode: Processing mode (concurrent, sequential - default: concurrent)
    --workers: Number of worker processes (default: auto-detect)

Examples:
    # Build database from all collections
    python -m src.main_entry_points.e1_build_database

    # Build from test files only
    python -m src.main_entry_points.e1_build_database --input-dir public_test/

    # Build only ZH collection with sequential processing
    python -m src.main_entry_points.e1_build_database --collections zh --mode sequential

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import argparse
import os
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.modules.database_generator_module.database_builder import build_database
from src.utils.logging_decorators import configure_logging
from src.utils.logging_utils import get_module_logger

# Get logger for this module
logger = get_module_logger(__name__)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Build SQL database from markdown law files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s
  %(prog)s --input-dir public_test/
  %(prog)s --target zh --mode sequential  
  %(prog)s --output-file custom_laws.db
        """
    )
    
    # Standardized arguments (5 total)
    parser.add_argument(
        "--target",
        choices=["zh", "ch", "all"],
        default="all",
        help="Target collections to process: zh, ch, or all (default: all)"
    )
    
    parser.add_argument(
        "--input-dir",
        type=str,
        default="public/",
        help="Input directory containing md-files subdirectory (default: public/)"
    )
    
    parser.add_argument(
        "--output-file",
        type=str,
        default="zhlaw.db",
        help="Output database filename (default: zhlaw.db)"
    )
    
    parser.add_argument(
        "--mode",
        choices=["concurrent", "sequential"],
        default="concurrent",
        help="Processing mode: concurrent (parallel) or sequential (default: concurrent)"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        default="info",
        help="Logging level (default: info)"
    )
    
    return parser.parse_args()


def validate_arguments(args):
    """Validate command line arguments."""
    # Check if we should use datasets directory
    md_files_path = Path("datasets/md-files")
    
    # If datasets/md-files exists, use it. Otherwise fall back to the input_dir approach
    if md_files_path.exists():
        input_path = Path("datasets")
        logger.info(f"Using markdown files from datasets directory: {md_files_path}")
    else:
        # Validate input directory
        input_path = Path(args.input_dir)
        if not input_path.exists():
            raise ValueError(f"Input directory does not exist: {input_path}")
        
        md_files_path = input_path / "md-files"
        if not md_files_path.exists():
            raise ValueError(f"md-files directory not found: {md_files_path}")
    
    # Validate collections
    available_collections = []
    for item in md_files_path.iterdir():
        if item.is_dir():
            available_collections.append(item.name)
    
    if not available_collections:
        raise ValueError(f"No collections found in {md_files_path}")
    
    # Determine collections to process
    if args.target == "all":
        collections = available_collections
    else:
        collections = [args.target]
        if args.target not in available_collections:
            raise ValueError(f"Collection '{args.target}' not found. Available: {available_collections}")
    
    # Validate output file path
    output_path = Path(args.output_file)
    if not output_path.parent.exists():
        raise ValueError(f"Output directory does not exist: {output_path.parent}")
    
    return {
        'input_dir': input_path,
        'output_file': output_path,
        'collections': collections,
        'processing_mode': args.mode,
        'max_workers': None  # Auto-detect worker count
    }


@configure_logging()
def main():
    """Main entry point."""
    try:
        # Parse arguments
        args = parse_arguments()
        
        logger.info("Starting database build process")
        logger.info(f"Script arguments: {args}")
        
        # Validate arguments
        validated_args = validate_arguments(args)
        
        logger.info(f"Input directory: {validated_args['input_dir']}")
        logger.info(f"Output file: {validated_args['output_file']}")
        logger.info(f"Collections: {validated_args['collections']}")
        logger.info(f"Processing mode: {validated_args['processing_mode']}")
        logger.info(f"Max workers: {validated_args['max_workers'] or 'auto-detect'}")
        
        # Build database
        success = build_database(
            input_dir=validated_args['input_dir'],
            output_file=validated_args['output_file'],
            collections=validated_args['collections'],
            processing_mode=validated_args['processing_mode'],
            max_workers=validated_args['max_workers']
        )
        
        if success:
            logger.info("Database build completed successfully!")
            logger.info(f"Database file: {validated_args['output_file']}")
            
            # Display database file size
            db_size = validated_args['output_file'].stat().st_size
            logger.info(f"Database size: {db_size:,} bytes ({db_size / 1024 / 1024:.2f} MB)")
            
            sys.exit(0)
        else:
            logger.error("Database build failed")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Build process interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()