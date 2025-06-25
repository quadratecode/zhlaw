# Main Entry Points Documentation

This document lists all main entry point files and their possible argument combinations. Each command can be copy-pasted directly.

## 1. a1_scrape_zhlex.py - ZH-Lex Scraping Pipeline

Scrapes law metadata from ZH website, downloads PDFs, and processes them.

**No command-line arguments**

```bash
python -m src.main_entry_points.a1_scrape_zhlex
```

## 2. a2_process_zhlex.py - ZH-Lex PDF Processing Pipeline

Processes ZH-Lex PDF files that have been scraped and downloaded.

### Arguments:
- `--folder`: Choose folder to process
  - `zhlex_files`: Process all Canton of Zurich files
  - `zhlex_files_test`: Process test dataset only (default)
- `--mode`: Processing mode
  - `concurrent`: Parallel processing (default)
  - `sequential`: Sequential processing (for debugging)

### All possible combinations:

```bash
# Process test files with concurrent mode (default)
python -m src.main_entry_points.a2_process_zhlex

# Process test files with sequential mode
python -m src.main_entry_points.a2_process_zhlex --mode sequential

# Process all files with concurrent mode
python -m src.main_entry_points.a2_process_zhlex --folder zhlex_files

# Process all files with sequential mode
python -m src.main_entry_points.a2_process_zhlex --folder zhlex_files --mode sequential
```

## 3. b1_process_krzh_dispatch.py - Parliamentary Dispatch Processing

Processes parliamentary dispatches from Kantonsrat Zürich.

**No command-line arguments**

```bash
python -m src.main_entry_points.b1_process_krzh_dispatch
```

## 4. c1_scrape_fedlex.py - Fedlex Scraping Pipeline

Scrapes federal law metadata from Fedlex SPARQL endpoint.

**No command-line arguments**

```bash
python -m src.main_entry_points.c1_scrape_fedlex
```

## 5. c2_process_fedlex.py - Fedlex File Processing Pipeline

Processes Fedlex federal law HTML files.

### Arguments:
- `--folder`: Choose folder to process
  - `fedlex_files`: Process all federal law files (default)
  - `fedlex_files_test`: Process test dataset only
- `--mode`: Processing mode
  - `concurrent`: Parallel processing
  - `sequential`: Sequential processing (default)
- `--workers`: Number of worker processes (only for concurrent mode)

### All possible combinations:

```bash
# Process test files with sequential mode (default for test)
python -m src.main_entry_points.c2_process_fedlex --folder fedlex_files_test

# Process test files with concurrent mode
python -m src.main_entry_points.c2_process_fedlex --folder fedlex_files_test --mode concurrent

# Process test files with concurrent mode and 4 workers
python -m src.main_entry_points.c2_process_fedlex --folder fedlex_files_test --mode concurrent --workers 4

# Process all files with sequential mode
python -m src.main_entry_points.c2_process_fedlex --folder fedlex_files --mode sequential

# Process all files with concurrent mode
python -m src.main_entry_points.c2_process_fedlex --folder fedlex_files --mode concurrent

# Process all files with concurrent mode and 8 workers
python -m src.main_entry_points.c2_process_fedlex --folder fedlex_files --mode concurrent --workers 8
```

## 6. d1_build_site.py - Static Site Generation Pipeline

Generates the static website from processed law data.

### Arguments:
- `--folder`: Choose collections to build
  - `all_test_files`: Test files for fedlex and zhlex
  - `fedlex_test_files`: Test files only for fedlex
  - `zhlex_test_files`: Test files only for zhlex
  - `all_main_files`: All files in fedlex_files and zhlex_files (default)
  - `zhlex_main_files`: All files in zhlex_files only
  - `fedlex_main_files`: All files in fedlex_files only
- `--db-build`: Build markdown dataset
  - `yes`: Generate dataset (default)
  - `no`: Skip dataset generation
- `--placeholders`: Create placeholder pages
  - `yes`: Create placeholders (default)
  - `no`: Skip placeholders
- `--mode`: Processing mode
  - `concurrent`: Parallel processing (default)
  - `sequential`: Sequential processing
- `--workers`: Number of worker processes

### Common workflows:

```bash
# Build everything with defaults (all files, with dataset, with placeholders, concurrent)
python -m src.main_entry_points.d1_build_site

# Build test files for quick testing
python -m src.main_entry_points.d1_build_site --folder all_test_files

# Build only ZH test files
python -m src.main_entry_points.d1_build_site --folder zhlex_test_files

# Build only Fedlex test files
python -m src.main_entry_points.d1_build_site --folder fedlex_test_files

# Build all ZH files without dataset
python -m src.main_entry_points.d1_build_site --folder zhlex_main_files --db-build no

# Build all Fedlex files without placeholders
python -m src.main_entry_points.d1_build_site --folder fedlex_main_files --placeholders no

# Build everything sequentially for debugging
python -m src.main_entry_points.d1_build_site --mode sequential

# Build with specific number of workers
python -m src.main_entry_points.d1_build_site --workers 4
```

### All possible combinations for test files:

```bash
# All test files combinations
python -m src.main_entry_points.d1_build_site --folder all_test_files
python -m src.main_entry_points.d1_build_site --folder all_test_files --db-build no
python -m src.main_entry_points.d1_build_site --folder all_test_files --placeholders no
python -m src.main_entry_points.d1_build_site --folder all_test_files --db-build no --placeholders no
python -m src.main_entry_points.d1_build_site --folder all_test_files --mode sequential
python -m src.main_entry_points.d1_build_site --folder all_test_files --mode sequential --db-build no
python -m src.main_entry_points.d1_build_site --folder all_test_files --workers 2

# ZH test files combinations
python -m src.main_entry_points.d1_build_site --folder zhlex_test_files
python -m src.main_entry_points.d1_build_site --folder zhlex_test_files --db-build no
python -m src.main_entry_points.d1_build_site --folder zhlex_test_files --placeholders no
python -m src.main_entry_points.d1_build_site --folder zhlex_test_files --mode sequential

# Fedlex test files combinations
python -m src.main_entry_points.d1_build_site --folder fedlex_test_files
python -m src.main_entry_points.d1_build_site --folder fedlex_test_files --db-build no
python -m src.main_entry_points.d1_build_site --folder fedlex_test_files --placeholders no
python -m src.main_entry_points.d1_build_site --folder fedlex_test_files --mode sequential
```

### All possible combinations for main files:

```bash
# All main files combinations
python -m src.main_entry_points.d1_build_site --folder all_main_files
python -m src.main_entry_points.d1_build_site --folder all_main_files --db-build no
python -m src.main_entry_points.d1_build_site --folder all_main_files --placeholders no
python -m src.main_entry_points.d1_build_site --folder all_main_files --db-build no --placeholders no
python -m src.main_entry_points.d1_build_site --folder all_main_files --mode sequential
python -m src.main_entry_points.d1_build_site --folder all_main_files --workers 8

# ZH main files combinations
python -m src.main_entry_points.d1_build_site --folder zhlex_main_files
python -m src.main_entry_points.d1_build_site --folder zhlex_main_files --db-build no
python -m src.main_entry_points.d1_build_site --folder zhlex_main_files --placeholders no
python -m src.main_entry_points.d1_build_site --folder zhlex_main_files --mode sequential
python -m src.main_entry_points.d1_build_site --folder zhlex_main_files --workers 4

# Fedlex main files combinations
python -m src.main_entry_points.d1_build_site --folder fedlex_main_files
python -m src.main_entry_points.d1_build_site --folder fedlex_main_files --db-build no
python -m src.main_entry_points.d1_build_site --folder fedlex_main_files --placeholders no
python -m src.main_entry_points.d1_build_site --folder fedlex_main_files --mode sequential
python -m src.main_entry_points.d1_build_site --folder fedlex_main_files --workers 6
```

## Complete Processing Pipelines

### Test Pipeline (Quick Testing)
```bash
# 1. Scrape and process ZH test data
python -m src.main_entry_points.a1_scrape_zhlex
python -m src.main_entry_points.a2_process_zhlex --folder zhlex_files_test

# 2. Scrape and process Fedlex test data
python -m src.main_entry_points.c1_scrape_fedlex
python -m src.main_entry_points.c2_process_fedlex --folder fedlex_files_test

# 3. Build test site
python -m src.main_entry_points.d1_build_site --folder all_test_files
```

### Full Production Pipeline
```bash
# 1. Scrape and process all ZH data
python -m src.main_entry_points.a1_scrape_zhlex
python -m src.main_entry_points.a2_process_zhlex --folder zhlex_files

# 2. Scrape and process all Fedlex data
python -m src.main_entry_points.c1_scrape_fedlex
python -m src.main_entry_points.c2_process_fedlex --folder fedlex_files --mode concurrent

# 3. Process parliamentary dispatches
python -m src.main_entry_points.b1_process_krzh_dispatch

# 4. Build complete site
python -m src.main_entry_points.d1_build_site --folder all_main_files
```

### ZH-Only Pipeline
```bash
# 1. Scrape and process ZH data
python -m src.main_entry_points.a1_scrape_zhlex
python -m src.main_entry_points.a2_process_zhlex --folder zhlex_files

# 2. Build ZH-only site
python -m src.main_entry_points.d1_build_site --folder zhlex_main_files
```

### Fedlex-Only Pipeline
```bash
# 1. Scrape and process Fedlex data
python -m src.main_entry_points.c1_scrape_fedlex
python -m src.main_entry_points.c2_process_fedlex --folder fedlex_files --mode concurrent

# 2. Build Fedlex-only site
python -m src.main_entry_points.d1_build_site --folder fedlex_main_files
```

### Debug Pipeline (Sequential Processing)
```bash
# Process everything sequentially for easier debugging
python -m src.main_entry_points.a2_process_zhlex --folder zhlex_files_test --mode sequential
python -m src.main_entry_points.c2_process_fedlex --folder fedlex_files_test --mode sequential
python -m src.main_entry_points.d1_build_site --folder all_test_files --mode sequential
```

## Notes

1. **Processing Order**: Always run scraping scripts (a1, c1) before processing scripts (a2, c2)
2. **Test vs Production**: Use test folders for development and debugging
3. **Concurrent vs Sequential**: Use concurrent for speed, sequential for debugging
4. **Worker Count**: If not specified, uses system CPU count
5. **API Limits**: Adobe API has monthly limits - use test files to avoid exhausting quota
6. **OpenAI Requirement**: Only needed for b1_process_krzh_dispatch (dispatch processing)