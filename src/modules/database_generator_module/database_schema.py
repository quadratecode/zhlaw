"""Database schema definitions for the legal text database.

This module contains all SQL DDL statements for creating tables, indexes,
and constraints for the legal database. It supports both Swiss cantonal
and federal law collections.

Functions:
    get_create_tables_sql(): Returns SQL statements for table creation
    get_create_indexes_sql(): Returns SQL statements for index creation
    create_database_schema(conn): Creates complete database schema

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import sqlite3

from src.utils.logging_utils import get_module_logger
logger = get_module_logger(__name__)


def get_create_tables_sql():
    """Return SQL statements for creating all database tables."""
    return [
        """
        CREATE TABLE IF NOT EXISTS laws (
            law_id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection TEXT NOT NULL,
            ordnungsnummer TEXT NOT NULL,
            col_ordnungsnummer TEXT UNIQUE NOT NULL,
            erlasstitel TEXT,
            abkuerzung TEXT,
            kurztitel TEXT,
            category_folder_id INTEGER,
            category_folder_name TEXT,
            category_section_id INTEGER,
            category_section_name TEXT,
            category_subsection_id INTEGER,
            category_subsection_name TEXT,
            dynamic_source TEXT,
            zhlaw_url_dynamic TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS versions (
            version_id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection TEXT NOT NULL,
            col_ordnungsnummer TEXT NOT NULL,
            nachtragsnummer TEXT NOT NULL,
            col_ordnungsnummer_nachtragsnummer TEXT UNIQUE NOT NULL,
            numeric_nachtragsnummer REAL,
            erlassdatum DATE,
            in_force BOOLEAN,
            inkraftsetzungsdatum DATE,
            aufhebungsdatum DATE,
            law_page_url TEXT,
            law_text_redirect TEXT,
            law_text_url TEXT,
            publikationsdatum DATE,
            full_version_text_markdown TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (col_ordnungsnummer) REFERENCES laws(col_ordnungsnummer)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS provisions (
            provision_id INTEGER PRIMARY KEY AUTOINCREMENT,
            col_ordnungsnummer_nachtragsnummer TEXT NOT NULL,
            provision_markdown TEXT,
            provision_sequence INTEGER,
            provision_number TEXT,
            provision_hyperlink TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (col_ordnungsnummer_nachtragsnummer) REFERENCES versions(col_ordnungsnummer_nachtragsnummer)
        )
        """
    ]


def get_create_indexes_sql():
    """Return SQL statements for creating database indexes."""
    return [
        "CREATE INDEX IF NOT EXISTS idx_col_ordnungsnummer ON laws(col_ordnungsnummer)",
        "CREATE INDEX IF NOT EXISTS idx_in_force ON versions(in_force)",
        "CREATE INDEX IF NOT EXISTS idx_collection ON laws(collection)",
        "CREATE INDEX IF NOT EXISTS idx_versions_col_ordnungsnummer ON versions(col_ordnungsnummer)",
        "CREATE INDEX IF NOT EXISTS idx_provisions_col_ordnungsnummer_nachtragsnummer ON provisions(col_ordnungsnummer_nachtragsnummer)"
    ]


def create_database_schema(conn):
    """Create the complete database schema including tables and indexes.
    
    Args:
        conn: SQLite database connection
        
    Returns:
        bool: True if schema creation was successful, False otherwise
    """
    try:
        # Create tables
        for sql in get_create_tables_sql():
            conn.execute(sql)
            logger.debug(f"Created table: {sql.split()[5]}")  # Extract table name
        
        # Create indexes
        for sql in get_create_indexes_sql():
            conn.execute(sql)
            logger.debug(f"Created index: {sql.split()[5]}")  # Extract index name
        
        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON")
        
        conn.commit()
        logger.info("Database schema created successfully")
        return True
        
    except sqlite3.Error as e:
        logger.error(f"Error creating database schema: {e}")
        conn.rollback()
        return False


def drop_all_tables(conn):
    """Drop all tables from the database (for clean rebuild).
    
    Args:
        conn: SQLite database connection
    """
    try:
        # Drop tables in reverse order to handle foreign key constraints
        drop_statements = [
            "DROP TABLE IF EXISTS provisions",
            "DROP TABLE IF EXISTS versions", 
            "DROP TABLE IF EXISTS laws"
        ]
        
        for sql in drop_statements:
            conn.execute(sql)
            logger.debug(f"Dropped table: {sql.split()[4]}")
        
        conn.commit()
        logger.info("All tables dropped successfully")
        
    except sqlite3.Error as e:
        logger.error(f"Error dropping tables: {e}")
        conn.rollback()


def get_table_info(conn):
    """Get information about existing tables in the database.
    
    Args:
        conn: SQLite database connection
        
    Returns:
        dict: Table information including row counts
    """
    try:
        tables = ['laws', 'versions', 'provisions']
        info = {}
        
        for table in tables:
            cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            info[table] = count
            
        return info
        
    except sqlite3.Error as e:
        logger.error(f"Error getting table info: {e}")
        return {}