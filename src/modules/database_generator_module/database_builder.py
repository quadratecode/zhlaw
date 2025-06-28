"""Main database builder for creating SQL databases from markdown files.

This module orchestrates the database creation process by scanning markdown files,
parsing them, and populating the SQLite database with laws, versions, and provisions.

Functions:
    build_database(input_dir, output_file, collections, mode, max_workers): Main entry point
    process_collection(collection_path, collection_name, conn): Process a single collection
    insert_law_data(conn, law_data): Insert or update law record
    insert_version_data(conn, version_data): Insert version record
    insert_provisions_data(conn, provisions, col_ordnungsnummer_nachtragsnummer): Insert provisions

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import sqlite3
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import concurrent.futures
# from tqdm import tqdm  # Replaced with progress_utils
from src.utils.progress_utils import progress_manager, track_concurrent_futures

from .database_schema import create_database_schema, drop_all_tables, get_table_info
from .markdown_parser import (
    parse_markdown_file, 
    extract_law_data, 
    extract_version_data,
    MarkdownParseError
)

from src.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)


class DatabaseBuildError(Exception):
    """Custom exception for database build errors."""
    pass


def build_database(
    input_dir: Path,
    output_file: Path,
    collections: List[str] = None,
    processing_mode: str = "concurrent",
    max_workers: Optional[int] = None
) -> bool:
    """Build the complete legal database from markdown files.
    
    Args:
        input_dir: Directory containing md-files subdirectories
        output_file: Path to output SQLite database file
        collections: List of collections to process (e.g., ["zh", "ch"])
        processing_mode: "concurrent" or "sequential"
        max_workers: Number of worker processes for concurrent mode
        
    Returns:
        True if database was built successfully, False otherwise
    """
    try:
        logger.info(f"Building database from {input_dir} to {output_file}")
        logger.info(f"Processing mode: {processing_mode}")
        
        # Validate input directory
        md_files_dir = input_dir / "md-files"
        if not md_files_dir.exists():
            raise DatabaseBuildError(f"md-files directory not found: {md_files_dir}")
        
        # Determine collections to process
        if collections is None:
            collections = []
            for item in md_files_dir.iterdir():
                if item.is_dir():
                    collections.append(item.name)
        
        if not collections:
            raise DatabaseBuildError("No collections found to process")
        
        logger.info(f"Processing collections: {collections}")
        
        # Remove existing database file
        if output_file.exists():
            output_file.unlink()
            logger.info(f"Removed existing database: {output_file}")
        
        # Create database connection
        conn = sqlite3.connect(str(output_file))
        
        try:
            # Create database schema
            if not create_database_schema(conn):
                raise DatabaseBuildError("Failed to create database schema")
            
            # Process each collection
            total_files = 0
            for collection in collections:
                collection_path = md_files_dir / collection
                if not collection_path.exists():
                    logger.warning(f"Collection directory not found: {collection_path}")
                    continue
                
                files_processed = process_collection(
                    collection_path, 
                    collection, 
                    conn,
                    processing_mode,
                    max_workers
                )
                total_files += files_processed
            
            # Get final database statistics
            table_info = get_table_info(conn)
            logger.info(f"Database build complete:")
            logger.info(f"  - Processed {total_files} markdown files")
            logger.info(f"  - Laws: {table_info.get('laws', 0)}")
            logger.info(f"  - Versions: {table_info.get('versions', 0)}")
            logger.info(f"  - Provisions: {table_info.get('provisions', 0)}")
            
            return True
            
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error building database: {e}")
        return False


def process_collection(
    collection_path: Path,
    collection_name: str,
    conn: sqlite3.Connection,
    processing_mode: str = "concurrent",
    max_workers: Optional[int] = None
) -> int:
    """Process all markdown files in a collection directory.
    
    Args:
        collection_path: Path to collection directory (e.g., md-files/zh/)
        collection_name: Name of collection (e.g., "zh")
        conn: Database connection
        processing_mode: "concurrent" or "sequential"
        max_workers: Number of worker processes
        
    Returns:
        Number of files processed successfully
    """
    try:
        logger.info(f"Processing collection: {collection_name} from {collection_path}")
        
        # Get all markdown files
        md_files = list(collection_path.glob("*.md"))
        if not md_files:
            logger.warning(f"No markdown files found in {collection_path}")
            return 0
        
        logger.info(f"Found {len(md_files)} markdown files in {collection_name}")
        
        # Process files
        if processing_mode == "concurrent" and len(md_files) > 1:
            return _process_files_concurrent(md_files, collection_name, conn, max_workers)
        else:
            return _process_files_sequential(md_files, collection_name, conn)
            
    except Exception as e:
        logger.error(f"Error processing collection {collection_name}: {e}")
        return 0


def _process_files_sequential(
    md_files: List[Path],
    collection_name: str,
    conn: sqlite3.Connection
) -> int:
    """Process files sequentially.
    
    Args:
        md_files: List of markdown file paths
        collection_name: Collection identifier
        conn: Database connection
        
    Returns:
        Number of files processed successfully
    """
    successful_count = 0
    
    with progress_manager() as pm:
        counter = pm.create_counter(
            total=len(md_files),
            desc=f"Processing {len(md_files)} {collection_name} files",
            unit="files"
        )
        
        for md_file in md_files:
            try:
                if _process_single_file(md_file, collection_name, conn):
                    successful_count += 1
            except Exception as e:
                logger.error(f"Error processing file {md_file}: {e}")
            finally:
                counter.update()
    
    logger.info(f"Sequential processing complete: {successful_count}/{len(md_files)} files")
    return successful_count


def _process_files_concurrent(
    md_files: List[Path],
    collection_name: str,
    conn: sqlite3.Connection,
    max_workers: Optional[int] = None
) -> int:
    """Process files concurrently.
    
    Args:
        md_files: List of markdown file paths
        collection_name: Collection identifier
        conn: Database connection
        max_workers: Number of worker processes
        
    Returns:
        Number of files processed successfully
    """
    successful_count = 0
    effective_max_workers = max_workers or os.cpu_count()
    
    logger.info(f"Processing {len(md_files)} files concurrently (max_workers={effective_max_workers})")
    
    # Parse files concurrently
    parsed_data_list = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=effective_max_workers) as executor:
        # Submit parsing tasks
        future_to_file = {
            executor.submit(_parse_file_worker, md_file, collection_name): md_file
            for md_file in md_files
        }
        
        # Convert to list of futures for tracking
        futures = list(future_to_file.keys())
        
        # Collect results
        for future in track_concurrent_futures(
            futures,
            desc=f"Parsing {len(md_files)} {collection_name} files",
            unit="files"
        ):
            md_file = future_to_file[future]
            try:
                result = future.result()
                if result:
                    parsed_data_list.append(result)
            except Exception as e:
                logger.error(f"Error parsing file {md_file}: {e}")
                continue
    
    # Insert parsed data into database sequentially (SQLite doesn't handle concurrent writes well)
    logger.info(f"Inserting {len(parsed_data_list)} parsed files into database")
    with progress_manager() as pm:
        counter = pm.create_counter(
            total=len(parsed_data_list),
            desc=f"Inserting {len(parsed_data_list)} {collection_name} records",
            unit="records"
        )
        
        for parsed_data in parsed_data_list:
            try:
                if _insert_parsed_data(parsed_data, conn):
                    successful_count += 1
            except Exception as e:
                logger.error(f"Error inserting data: {e}")
            finally:
                counter.update()
    
    logger.info(f"Concurrent processing complete: {successful_count}/{len(md_files)} files")
    return successful_count


def _parse_file_worker(file_path: Path, collection_name: str) -> Optional[Dict[str, Any]]:
    """Worker function for parsing files in concurrent mode.
    
    Args:
        file_path: Path to markdown file
        collection_name: Collection identifier
        
    Returns:
        Parsed data dictionary or None if parsing failed
    """
    try:
        parsed_data = parse_markdown_file(file_path)
        parsed_data['collection_name'] = collection_name
        return parsed_data
    except Exception as e:
        logger.error(f"Worker error parsing {file_path}: {e}")
        return None


def _process_single_file(file_path: Path, collection_name: str, conn: sqlite3.Connection) -> bool:
    """Process a single markdown file and insert data into database.
    
    Args:
        file_path: Path to markdown file
        collection_name: Collection identifier
        conn: Database connection
        
    Returns:
        True if processing was successful, False otherwise
    """
    try:
        # Parse the file
        parsed_data = parse_markdown_file(file_path)
        parsed_data['collection_name'] = collection_name
        
        # Insert into database
        return _insert_parsed_data(parsed_data, conn)
        
    except MarkdownParseError as e:
        logger.error(f"Markdown parsing error for {file_path}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error processing {file_path}: {e}")
        return False


def _insert_parsed_data(parsed_data: Dict[str, Any], conn: sqlite3.Connection) -> bool:
    """Insert parsed data into database tables.
    
    Args:
        parsed_data: Parsed markdown data
        conn: Database connection
        
    Returns:
        True if insertion was successful, False otherwise
    """
    try:
        collection_name = parsed_data['collection_name']
        
        # Extract and insert law data
        law_data = extract_law_data(parsed_data, collection_name)
        insert_law_data(conn, law_data)
        
        # Extract and insert version data
        version_data = extract_version_data(parsed_data, collection_name)
        insert_version_data(conn, version_data)
        
        # Insert provisions data
        provisions = parsed_data.get('provisions', [])
        col_ordnungsnummer_nachtragsnummer = version_data['col_ordnungsnummer_nachtragsnummer']
        insert_provisions_data(conn, provisions, col_ordnungsnummer_nachtragsnummer)
        
        conn.commit()
        return True
        
    except sqlite3.Error as e:
        logger.error(f"Database error inserting data: {e}")
        conn.rollback()
        return False
    except Exception as e:
        logger.error(f"Unexpected error inserting data: {e}")
        conn.rollback()
        return False


def insert_law_data(conn: sqlite3.Connection, law_data: Dict[str, Any]) -> None:
    """Insert or update law data in the laws table.
    
    Args:
        conn: Database connection
        law_data: Law data dictionary
    """
    # Use INSERT OR REPLACE to handle duplicates
    sql = """
        INSERT OR REPLACE INTO laws (
            collection, ordnungsnummer, col_ordnungsnummer, erlasstitel, abkuerzung,
            kurztitel, category_folder_id, category_folder_name, category_section_id,
            category_section_name, category_subsection_id, category_subsection_name,
            dynamic_source, zhlaw_url_dynamic
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    params = (
        law_data['collection'],
        law_data['ordnungsnummer'],
        law_data['col_ordnungsnummer'],
        law_data['erlasstitel'],
        law_data['abkuerzung'],
        law_data['kurztitel'],
        law_data['category_folder_id'],
        law_data['category_folder_name'],
        law_data['category_section_id'],
        law_data['category_section_name'],
        law_data['category_subsection_id'],
        law_data['category_subsection_name'],
        law_data['dynamic_source'],
        law_data['zhlaw_url_dynamic']
    )
    
    conn.execute(sql, params)


def insert_version_data(conn: sqlite3.Connection, version_data: Dict[str, Any]) -> None:
    """Insert version data in the versions table.
    
    Args:
        conn: Database connection
        version_data: Version data dictionary
    """
    sql = """
        INSERT OR REPLACE INTO versions (
            collection, col_ordnungsnummer, nachtragsnummer, col_ordnungsnummer_nachtragsnummer,
            numeric_nachtragsnummer, erlassdatum, in_force, inkraftsetzungsdatum,
            aufhebungsdatum, law_page_url, law_text_redirect, law_text_url,
            publikationsdatum, full_version_text_markdown
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    params = (
        version_data['collection'],
        version_data['col_ordnungsnummer'],
        version_data['nachtragsnummer'],
        version_data['col_ordnungsnummer_nachtragsnummer'],
        version_data['numeric_nachtragsnummer'],
        version_data['erlassdatum'],
        version_data['in_force'],
        version_data['inkraftsetzungsdatum'],
        version_data['aufhebungsdatum'],
        version_data['law_page_url'],
        version_data['law_text_redirect'],
        version_data['law_text_url'],
        version_data['publikationsdatum'],
        version_data['full_version_text_markdown']
    )
    
    conn.execute(sql, params)


def insert_provisions_data(
    conn: sqlite3.Connection,
    provisions: List[Dict[str, Any]],
    col_ordnungsnummer_nachtragsnummer: str
) -> None:
    """Insert provisions data in the provisions table.
    
    Args:
        conn: Database connection
        provisions: List of provision dictionaries
        col_ordnungsnummer_nachtragsnummer: Foreign key reference
    """
    if not provisions:
        return
    
    sql = """
        INSERT INTO provisions (
            col_ordnungsnummer_nachtragsnummer, provision_markdown, provision_sequence,
            provision_number, provision_hyperlink
        ) VALUES (?, ?, ?, ?, ?)
    """
    
    for provision in provisions:
        params = (
            col_ordnungsnummer_nachtragsnummer,
            provision.get('provision_markdown'),
            provision.get('provision_sequence'),
            provision.get('provision_number'),
            provision.get('provision_hyperlink')
        )
        
        conn.execute(sql, params)