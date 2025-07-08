# Main Entry Points Documentation

This document lists all main entry point modules and their standardized command-line arguments. All modules use consistent argument patterns for easier operation.

## 1. a1_scrape_zhlex.py - ZH-Lex Scraping Pipeline

Scrapes law metadata from ZH website, downloads PDFs, and processes them.

**No command-line arguments**

```bash
python -m src.main_entry_points.a1_scrape_zhlex
```

## 2. a2_process_zhlex.py - ZH-Lex PDF Processing Pipeline

Processes ZH-Lex PDF files that have been scraped and downloaded.

```bash
python -m src.main_entry_points.a2_process_zhlex
```

### Arguments:
- `--target`: Target folder to process (default: zhlex_files_test)
  - `zhlex_files_test`: Process test dataset only
  - `zhlex_files`: Process all Canton of Zurich files
- `--mode`: Processing mode (default: concurrent)
  - `concurrent`: Parallel processing
  - `sequential`: Sequential processing (for debugging)
- `--filter-new-only`: Only process files that haven't been processed yet
- `--log-level`: Logging level (default: info)
  - `debug`, `info`, `warning`, `error`

## 3. a3_table_extraction.py - Table Extraction System

Extracts table structures from legal documents and creates per-version correction files.

```bash
python -m src.main_entry_points.a3_table_extraction --target zhlex_files_test
```

### Arguments:
- `--target`: Target folder to process (**required**)
  - `zhlex_files_test`, `zhlex_files`, `fedlex_files_test`, `fedlex_files`
- `--law`: Extract tables for specific law only (e.g., 170.4)
- `--show-status`: Show extraction status for target folder
- `--workers`: Number of worker threads for concurrent processing (default: 4)
- `--mode`: Processing mode (default: concurrent)
  - `concurrent`: Parallel processing
  - `sequential`: Single-threaded processing
- `--regenerate`: Regenerate table data for specific law from scratch (requires --law)
- `--regenerate-all`: Regenerate table data for all laws in target folder from scratch
- `--log-level`: Logging level (default: info)
  - `debug`, `info`, `warning`, `error`

## 4. a4_table_review.py - Table Review System

Human-in-the-loop table review system for correcting table structures.

```bash
python -m src.main_entry_points.a4_table_review --target zhlex_files_test
```

### Arguments:
- `--target`: Target folder to review (**required**)
  - `zhlex_files_test`, `zhlex_files`, `fedlex_files_test`, `fedlex_files`
- `--law`: Review specific law (e.g., 170.4)
- `--version`: Specify version(s): specific version (e.g., '129'), 'latest', or 'all'
- `--show-status`: Show review progress and statistics
- `--reset`: Reset corrections for a law (requires --law)
- `--reset-all`: Reset all corrections in the specified target folder
- `--mode`: Processing mode (default: sequential)
  - `sequential`: Interactive mode (recommended for review)
  - `concurrent`: Batch processing mode
- `--log-level`: Logging level (default: info)
  - `debug`, `info`, `warning`, `error`

## 5. b1_process_krzh_dispatch.py - Parliamentary Dispatch Processing

Processes parliamentary dispatches from Kantonsrat Zürich.

**No command-line arguments**

```bash
python -m src.main_entry_points.b1_process_krzh_dispatch
```

## 6. c1_scrape_fedlex.py - Fedlex Scraping Pipeline

Scrapes federal law metadata from Fedlex SPARQL endpoint.

**No command-line arguments**

```bash
python -m src.main_entry_points.c1_scrape_fedlex
```

## 7. c2_process_fedlex.py - Fedlex File Processing Pipeline

Processes Fedlex federal law HTML files.

```bash
python -m src.main_entry_points.c2_process_fedlex
```

### Arguments:
- `--target`: Target folder to process (default: fedlex_files_test)
  - `fedlex_files_test`: Process test dataset only
  - `fedlex_files`: Process all federal law files
- `--mode`: Processing mode (default: concurrent)
  - `concurrent`: Parallel processing
  - `sequential`: Sequential processing (for debugging)
- `--filter-new-only`: Only process files that haven't been processed yet
- `--log-level`: Logging level (default: info)
  - `debug`, `info`, `warning`, `error`

## 8. d1_build_site.py - Static Site Generation Pipeline

Generates the static website from processed law data.

```bash
python -m src.main_entry_points.d1_build_site
```

### Arguments:
- `--target`: Target collection(s) to build (default: all_files)
  - `all_files_test`: Test files for both collections
  - `fedlex_files_test`: Fedlex test files only
  - `zhlex_files_test`: ZH-Lex test files only
  - `all_files`: Both collections (production)
  - `zhlex_files`: ZH-Lex only (production)
  - `fedlex_files`: Fedlex only (production)
- `--build-dataset` / `--no-build-dataset`: Build markdown dataset (default: enabled)
- `--create-placeholders` / `--no-placeholders`: Create placeholder pages for missing documents (default: enabled, ZH-Lex only)
- `--mode`: Processing mode (default: concurrent)
  - `concurrent`: Parallel processing
  - `sequential`: Sequential processing (for debugging)
- `--workers`: Number of worker processes (default: auto-detect)
- `--no-minify`: Disable minification for debugging (pretty-print HTML and CSS)
- `--log-level`: Logging level (default: info)
  - `debug`, `info`, `warning`, `error`

## 9. e1_build_database.py - SQL Database Generation Pipeline

Builds an SQLite database from processed markdown law files.

```bash
python -m src.main_entry_points.e1_build_database
```

### Arguments:
- `--target`: Target collections to process (default: all)
  - `zh`: Process only Zurich laws
  - `ch`: Process only federal laws
  - `all`: Process all collections
- `--input-dir`: Input directory containing md-files subdirectory (default: public/)
- `--output-file`: Output database filename (default: zhlaw.db)
- `--mode`: Processing mode (default: concurrent)
  - `concurrent`: Parallel processing
  - `sequential`: Sequential processing
- `--log-level`: Logging level (default: info)
  - `debug`, `info`, `warning`, `error`

## Argument Standardization

All modules follow consistent patterns:

### Core Arguments (used across all applicable modules):
- `--target`: Unified naming for folder/collection selection
- `--mode {concurrent,sequential}`: Consistent processing mode control
- `--log-level {debug,info,warning,error}`: Standardized logging (lowercase)

### Specialized Arguments:
- `--filter-new-only`: Process only unprocessed items
- `--show-status`: Display status/progress information
- Boolean flags: Use `--flag` / `--no-flag` pattern where applicable

### File Naming Convention:
- Test files: Always use full names like `zhlex_files_test`, `fedlex_files_test`
- Production files: Use `zhlex_files`, `fedlex_files`, `all_files`

## Notes

1. **Processing Order**: Always run scraping scripts (a1, c1) before processing scripts (a2, c2)
2. **Table Processing**: Run a3_table_extraction before a4_table_review
3. **Test vs Production**: Use test targets for development and debugging
4. **Concurrent vs Sequential**: Use concurrent for speed, sequential for debugging
5. **Worker Count**: Auto-detected unless specified
6. **API Limits**: Adobe API has monthly limits - use test files to avoid exhausting quota
7. **OpenAI Requirement**: Only needed for b1_process_krzh_dispatch (dispatch processing)