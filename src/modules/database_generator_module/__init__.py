"""Database generator module for creating SQL databases from markdown files.

This module processes markdown law files and creates an SQLite database with
proper schema for laws, versions, and provisions. It handles metadata extraction,
provision parsing, and data validation.

Modules:
    database_schema: SQL DDL definitions and schema management
    markdown_parser: Parse markdown files and extract structured data
    database_builder: Main database creation and population logic
    date_utils: Date conversion utilities for legal data formats

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""