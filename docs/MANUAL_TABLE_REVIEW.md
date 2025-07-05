# Manual Table Review System Documentation

## Table of Contents

- [Overview](#overview)
- [Getting Started](#getting-started)
- [System Architecture](#system-architecture)
- [User Workflows](#user-workflows)
- [Web Interface Guide](#web-interface-guide)
- [Command Line Reference](#command-line-reference)
- [File Formats and Data Structures](#file-formats-and-data-structures)
- [Configuration](#configuration)
- [Integration with zhlaw Pipeline](#integration-with-zhlaw-pipeline)
- [API Reference](#api-reference)
- [Troubleshooting](#troubleshooting)
- [Advanced Topics](#advanced-topics)

---

## Overview

### Purpose

The Manual Table Review System is a sophisticated human-in-the-loop quality control system for reviewing and correcting table structures extracted from legal documents by Adobe's Extract API. It provides a web-based interface for manual review and correction of tables, ensuring high-quality output in the zhlaw legal document processing pipeline.

### Key Features

- **Per-Version Architecture**: Independent correction files for each law version (no cross-version deduplication)
- **Version Targeting**: Focus on latest versions (immediate value) or target specific/all versions
- **Two-Step Process**: Separate table extraction (a3) and human review (a4) phases
- **Auto-Progression Interface**: Single-tab workflow with automatic progression between laws
- **Advanced Table Editor**: Compact controls for editing, merging, and status management
- **Smart Completion Validation**: Prevents completion until all tables are decided
- **Comprehensive Reporting**: Statistics, progress tracking, and export capabilities
- **Pipeline Integration**: Seamless integration with the main zhlaw document processing pipeline

### System Requirements

- Python 3.10 or higher
- Web browser (Chrome, Firefox, Edge, Safari)
- WSL support for Windows environments
- Network access for localhost web server

---

## Getting Started

### Quick Start

1. **Extract Tables from Legal Documents**
   ```bash
   # Navigate to project root
   cd /home/rdm/github/zhlaw
   
   # Extract tables from test dataset
   python -m src.main_entry_points.a3_table_extraction --folder zhlex_files_test
   ```

2. **Review Extracted Tables**
   ```bash
   # Review latest versions only (recommended for immediate value)
   python -m src.main_entry_points.a4_table_review --version latest --folder zhlex_files_test
   
   # Review all versions of all laws (comprehensive coverage)
   python -m src.main_entry_points.a4_table_review --version all --folder zhlex_files_test
   
   # Review specific law and version
   python -m src.main_entry_points.a4_table_review --law 172.110.1 --version 129 --folder zhlex_files_test
   ```

3. **Generate Reports**
   ```bash
   # Generate comprehensive reports
   python -m src.main_entry_points.a4_table_review --report html --folder zhlex_files_test
   ```

### First Use Walkthrough

1. **Initialize the system** by running the command above
2. **Browser opens automatically** with the table review interface
3. **Review each table** using the radio button interface:
   - Select "Confirmed" to approve a table
   - Select "Rejected" to exclude a table
   - Edit table content when status is "Confirmed"
4. **Save corrections** when finished
5. **Results are stored** in the appropriate data directory

---

## System Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    Manual Table Review System                    │
├─────────────────────────────────────────────────────────────────┤
│  Entry Points: a3_table_extraction.py | a4_table_review.py      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ TableExtractor  │  │ BatchProcessor  │  │ ProgressReporter│ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  Core Processing Modules                                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │LawTableExtractor│  │ EditorInterface │  │CorrectionManager│ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  Support Modules                                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │    Validation   │  │   Statistics    │  │CorrectionApplier│ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  User Interface                                                 │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │           Custom Web-Based Table Editor                     │ │
│  │              (custom_table_review.html)                     │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
[Legal Document PDFs]
    ↓ (Adobe Extract API)
[JSON with table elements]
    ↓ (LawTableExtractor.extract_tables_from_version)
[Per-version table structures with hashes]
    ↓ (CorrectionManager.create_correction_file_for_version)
[Per-version correction files (.json)]
    ↓ (TableEditorInterface.launch_editor_for_law)
[Human review via web interface]
    ↓ (CorrectionManager.save_corrections)
[Updated per-version correction files]
    ↓ (During HTML generation)
[CorrectionApplier.apply_corrections]
    ↓ (json_to_html.py)
[Final HTML with corrected tables]
```

### Component Responsibilities

| Component | Purpose | Key Methods |
|-----------|---------|-------------|
| **LawTableExtractor** | Extract per-version tables | `extract_tables_from_version()` |
| **TableEditorInterface** | Manage web-based editor | `launch_editor_for_law()` |
| **CorrectionManager** | Save/load per-version corrections | `save_corrections()`, `create_correction_file_for_version()` |
| **BatchProcessor** | Batch processing with progress | `process_folder_batch()` |
| **CorrectionApplier** | Apply corrections to pipeline | `apply_corrections()` |
| **StatisticsCollector** | Generate reports and metrics | `collect_statistics()` |

---

## User Workflows

### Workflow 1: Complete Two-Step Process (Recommended)

```bash
# Step 1: Extract tables from entire dataset and create per-version correction files
python -m src.main_entry_points.a3_table_extraction --folder zhlex_files_test

# Step 2: Review latest versions for immediate value (recommended)
python -m src.main_entry_points.a4_table_review --version latest --folder zhlex_files_test
```

**Steps:**
1. **Extraction Phase**: System scans all laws and extracts tables per version (no deduplication)
2. **Review Phase**: Single-tab interface opens with auto-progression
3. User reviews tables one law at a time
4. System automatically moves to next law upon completion (no manual prompts)
5. Smart validation prevents incomplete reviews
6. Progress is automatically saved per version

### Review Modes: Auto-Progression vs Manual Navigation

The table review system offers two distinct review modes for processing multiple laws:

#### 🚀 Auto-Progression Mode (Default: `--folder`)

**Browser Behavior:**
- **Single browser tab** that automatically loads the next law when you finish the current one
- Browser **automatically transitions** from one law to the next without closing
- **No command-line interaction** required during review process
- **Seamless workflow** - you stay in the browser throughout

**User Experience:**
1. Opens browser with Law 1
2. You review tables in browser
3. When you finish, browser **automatically loads Law 2**
4. Process continues until all laws reviewed
5. Only stops if you close browser or encounter errors

**Terminal Interaction:**
- Minimal terminal interaction during review
- Only prompts if errors occur: `"Continue with next law? (y/n)"`
- Progress shown: `"📋 Processing law 2/5: 170.4"`

**Best for:** Fast, focused review sessions where you want to process many laws sequentially without interruption.

#### 🎮 Manual Navigation Mode (`--sequential`)

**Browser Behavior:**
- **New browser tab** opened for each law
- Browser tab **closes** when you finish reviewing each law
- **Returns to terminal** after each law for navigation choices

**User Experience:**
1. Shows complete law list with status first
2. Opens browser for Law 1
3. When finished, **returns to terminal**
4. Terminal asks: `"Next action? (n=next, p=previous, s=skip, r=review again, q=quit)"`
5. You choose what to do next
6. Opens browser for your chosen law
7. Repeat process

**Terminal Interaction:**
- **Heavy terminal interaction** between each law
- Full navigation control with commands:
  - `n` = next law
  - `p` = previous law
  - `s` = skip current law
  - `r` = review current law again
  - `q` = quit entirely
- Shows law overview: `"📋 Law 2/5: 170.4 (3 tables) - ⏳ Pending"`

**Best for:** Deliberate review where you want full control over which law to review next, ability to go back to previous laws, or when you need to take breaks between laws.

#### 📊 Comparison Summary

| Aspect | Auto-Progression | Manual Navigation |
|--------|------------------|------------------|
| **Browser tabs** | 1 tab, auto-updates | New tab per law |
| **Terminal use** | Minimal | Heavy between laws |
| **Flow** | Continuous | Stop-and-choose |
| **Control** | Limited (close to stop) | Full (next/prev/skip/quit) |
| **Speed** | Faster, seamless | Slower, more deliberate |
| **Re-review** | Run command again | Built-in `r` option |
| **Backtrack** | Not possible | `p` for previous |

**Note:** Both modes automatically skip laws that have been completed and only show laws with undefined tables that need review.

### Workflow 2: Version-Specific Review

```bash
# Extract tables for specific law
python -m src.main_entry_points.a3_table_extraction --law 172.110.1 --folder zhlex_files_test

# Review latest version only
python -m src.main_entry_points.a4_table_review --law 172.110.1 --version latest --folder zhlex_files_test

# Review specific version
python -m src.main_entry_points.a4_table_review --law 172.110.1 --version 129 --folder zhlex_files_test

# Review all versions of specific law
python -m src.main_entry_points.a4_table_review --law 172.110.1 --version all --folder zhlex_files_test
```

**Steps:**
1. System processes specified law and version(s)
2. Creates per-version correction files
3. Opens web interface for targeted review
4. Saves corrections per version independently

### Workflow 3: Complete Coverage Review

```bash
# Review all versions for comprehensive coverage (when needed)
python -m src.main_entry_points.a4_table_review --version all --folder zhlex_files_test

# Regenerate all correction files from scratch
python -m src.main_entry_points.a3_table_extraction --folder zhlex_files_test --regenerate-all
```

**Key Features:**
- **Per-Version Processing**: Each law version processed independently with separate correction files
- **No Cross-Version Deduplication**: Eliminates brittleness from API output variations
- **Version Targeting**: `--version latest/all/specific` for focused or comprehensive coverage
- **Auto-Progression**: Seamless browser workflow with quit option

### Workflow 4: Report Generation

```bash
# Generate comprehensive reports
python -m src.main_entry_points.a4_table_review \
    --report html \
    --folder zhlex_files_test
```

**Steps:**
1. Analyzes existing corrections
2. Generates statistics and progress reports
3. Exports in specified format (JSON, CSV, HTML)

---

## Web Interface Guide

### Interface Overview

The web-based table editor provides an intuitive interface for reviewing table structures:

```
┌─────────────────────────────────────────────────────────────────┐
│                      Table Review Interface                      │
├─────────────────────────────────────────────────────────────────┤
│  Navigation: [← Previous] [Next →] [Overview]                   │
│  Progress: 5/23 tables reviewed (22%) | Auto-Progression: ON   │
├─────────────────────────────────────────────────────────────────┤
│  Context Information:                                           │
│  • Found in versions: v118, v119                               │
│  • Pages: v118: 2,3 | v119: 2,3                               │
│  • PDF Documents: [View v118 on zh.ch] [View v119 on zh.ch]   │
│  • Structure: 5 rows × 3 columns                               │
├─────────────────────────────────────────────────────────────────┤
│  Table Editor: [+ Row] [+ Col] [- Row] [- Col] [Reset] [☑ Has Header] │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Header 1  │  Header 2   │  Header 3   │                   │ │
│  │  Cell 1,1  │  Cell 1,2   │  Cell 1,3   │ (editable cells) │ │
│  │  Cell 2,1  │  Cell 2,2   │  Cell 2,3   │                   │ │
│  └─────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  Status: [Confirmed] [Confirmed+] [Rejected] [Unmerge]         │
├─────────────────────────────────────────────────────────────────┤
│  Actions: [⟱ Merge with Next] [Finish Review] [Save & Continue]│
└─────────────────────────────────────────────────────────────────┘
```

### Table Status System

| Status | Button | Description | Editing Enabled |
|--------|--------|-------------|-----------------|
| **Undefined** | *None* | Default state, no decision made | ❌ No |
| **Confirmed without changes** | [Confirmed] | Table correctly converted, no editing needed | ❌ No |
| **Confirmed with changes** | [Confirmed+] | Table is valid but edits are needed | ✅ Yes |
| **Rejected** | [Rejected] | Table excluded from output (converted to paragraphs) | ❌ No |
| **Merged** | [Unmerge] | Table merged with previous (double-click to unmerge) | ❌ No |

### Key Features

#### 1. Auto-Progression Interface
- **Single-tab workflow**: One tab automatically progresses between laws
- **Smart completion validation**: Prevents progression until all tables decided
- **Automatic save**: Server-side saving without downloads

#### 2. Compact Table Editor
- **Integrated controls**: Row/column operations in table header
- **Header checkbox**: Mark tables with header rows
- **Reset button**: Restore original table structure
- **Status controls**: Compact buttons below table editor

#### 3. Status Selection
- **Button interface**: Clear status buttons replacing radio buttons
- **Color-coded** status indicators
- **Automatic save** when status changes

#### 4. Table Editing (Confirmed+ Status Only)
- **Cell selection restricted**: Cells can only be selected when "Confirmed with changes" is active
- **Click cells** to edit content
- **Add/remove rows/columns** with integrated buttons
- **Visual feedback** for modified cells
- **Automatic structure updates**
- **Proper row height**: Empty rows maintain sufficient height for cursor visibility

#### 5. Merge & Unmerge Functionality
- **Combine tables**: Merge current table with next table
- **Smart disable**: Merge button automatically disabled on last table
- **Unmerge capability**: Unmerge merged tables back to undefined status
- **Status updates**: Next table marked as "merged"
- **Seamless workflow**: Continue editing merged result

#### 6. Smart Context Information
- **Version tracking**: Which versions contain this table
- **Page references**: Exact page numbers
- **PDF links**: Direct links to view original documents on zh.ch
- **Structure info**: Current table dimensions
- **Incremental processing**: Shows only new undefined tables when corrections exist

#### 7. Navigation
- **Previous/Next**: Navigate between tables
- **Progress tracking**: Current position and completion percentage
- **Overview**: Summary of all table statuses

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd + ←` | Previous table |
| `Ctrl/Cmd + →` | Next table |
| `Ctrl/Cmd + S` | Save corrections |

### Intelligent Processing Features

#### Per-Version Processing
- **Independent files**: Each version gets separate correction file: `{law_id}-{version}-table-corrections.json`
- **No cross-version deduplication**: Each version processed independently for API stability
- **Version targeting**: Focus on latest versions or target specific versions as needed

#### Incremental Correction Updates
- **Preserve existing work**: When new law versions added, existing per-version corrections preserved
- **New tables only**: Only newly discovered tables marked as "undefined"
- **Automatic detection**: System automatically detects new vs. existing tables per version

#### Completion Validation
- **Comprehensive checking**: All tables must have status before law completion
- **Prevents incomplete work**: Cannot progress until all tables decided
- **Smart validation**: Uses `validate_law_completion()` method

---

## Command Line Reference

### Step 1: Table Extraction

```bash
python -m src.main_entry_points.a3_table_extraction [OPTIONS]
```

### Step 2: Table Review

```bash
python -m src.main_entry_points.a4_table_review [OPTIONS]
```

### Required Arguments

| Argument | Description | Values |
|----------|-------------|--------|
| `--folder` | Target folder for processing | `zhlex_files_test`, `zhlex_files` |

### Table Extraction Arguments

| Argument | Description | Default | Example |
|----------|-------------|---------|---------|
| `--law LAW_ID` | Process specific law only | None | `--law 172.110.1` |
| `--status` | Show extraction status without processing | False | `--status` |
| `--regenerate` | Regenerate specific law from scratch (requires --law) | False | `--regenerate` |
| `--regenerate-all` | Regenerate all per-version correction files from scratch | False | `--regenerate-all` |
| `--workers N` | Number of concurrent workers | 4 | `--workers 8` |
| `--no-concurrent` | Use sequential processing | False | `--no-concurrent` |
| `--verbose` | Enable verbose logging | False | `--verbose` |

### Table Review Arguments

| Argument | Description | Default | Example |
|----------|-------------|---------|---------|
| `--law LAW_ID` | Review specific law only | None | `--law 172.110.1` |
| `--version SPEC` | **Version targeting**: latest/all/specific version | None | `--version latest` |
| `--sequential` | Use manual navigation mode with full control | False | `--sequential` |
| `--report FORMAT` | Generate reports (json/csv/html/all) | None | `--report html` |
| `--status` | Show basic review progress | False | `--status` |
| `--stats` | Show detailed statistics and metrics | False | `--stats` |
| `--export` | Export all correction JSON files | False | `--export` |
| `--export-path PATH` | Destination for export | None | `--export-path /backup` |
| `--verbose` | Enable verbose logging | False | `--verbose` |

### Version Targeting Options

| Version Spec | Description | Use Case |
|--------------|-------------|----------|
| `--version latest` | Review latest version of each law | **Recommended**: Focus on current content for immediate value |
| `--version all` | Review all versions of all laws | Comprehensive coverage when needed |
| `--version 129` | Review specific version (requires --law) | Target specific law version |
| `--law X --version latest` | Latest version of specific law | Single law, current content |
| `--law X --version all` | All versions of specific law | Single law, all versions |

### Processing Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **Default (Auto-Progression)** | Single-tab browser with automatic progression between laws | Fast, focused review sessions |
| **`--sequential` (Manual Navigation)** | Interactive terminal-controlled review with full navigation | Deliberate review with user control and ability to backtrack |

### Report Formats

| Format | Description | Output |
|--------|-------------|--------|
| `json` | Machine-readable statistics | `reports/statistics.json` |
| `csv` | Spreadsheet-compatible data | `reports/table_review_data.csv` |
| `html` | Comprehensive web report | `reports/table_review_report.html` |
| `all` | Generate all formats | Multiple files |

### Examples

#### Basic Two-Step Workflow
```bash
# Step 1: Extract tables from test dataset
python -m src.main_entry_points.a3_table_extraction --folder zhlex_files_test

# Step 2: Review extracted tables (single-tab auto-progression)
python -m src.main_entry_points.a4_table_review --folder zhlex_files_test

# Production dataset workflow
python -m src.main_entry_points.a3_table_extraction --folder zhlex_files
python -m src.main_entry_points.a4_table_review --folder zhlex_files
```

#### Advanced Table Review Options
```bash
# Review with incremental processing (preserves existing corrections)
python -m src.main_entry_points.a4_table_review \
    --folder zhlex_files_test

# Review specific law (allows re-review of completed laws)
python -m src.main_entry_points.a4_table_review \
    --law 170.4 \
    --folder zhlex_files_test

# Reset and re-review specific law
python -m src.main_entry_points.a4_table_review \
    --law 170.4 \
    --reset \
    --folder zhlex_files_test
```

#### Incremental Processing (New Tables)
```bash
# When new version of law is processed, only new tables require review
# Existing corrections are preserved automatically

# Extract new tables (preserves existing extractions)
python -m src.main_entry_points.a3_table_extraction --folder zhlex_files_test

# Review only shows new "undefined" tables, existing corrections preserved
python -m src.main_entry_points.a4_table_review --folder zhlex_files_test

# Force complete re-review of all tables in a law
python -m src.main_entry_points.a4_table_review \
    --law 170.4 \
    --reset \
    --folder zhlex_files_test
```

#### Report Generation and Statistics
```bash
# Show basic progress summary (completed/total counts, law lists)
python -m src.main_entry_points.a4_table_review \
    --folder zhlex_files_test \
    --status

# Show detailed statistics and metrics (processing efficiency, distribution, etc.)
python -m src.main_entry_points.a4_table_review \
    --folder zhlex_files_test \
    --stats

# Generate HTML report
python -m src.main_entry_points.a4_table_review \
    --report html \
    --folder zhlex_files_test

# Generate all report formats
python -m src.main_entry_points.a4_table_review \
    --report all \
    --folder zhlex_files
```

#### Export and Backup
```bash
# Export all correction JSON files (prompts for destination)
python -m src.main_entry_points.a4_table_review \
    --export \
    --folder zhlex_files_test

# Export with specific destination path
python -m src.main_entry_points.a4_table_review \
    --export \
    --folder zhlex_files_test \
    --export-path /path/to/backup
```

#### Reset and Maintenance
```bash
# Reset specific law (forces complete re-review)
python -m src.main_entry_points.a4_table_review \
    --law 170.4 \
    --reset \
    --folder zhlex_files_test

# Reset all corrections (use with caution!)
python -m src.main_entry_points.a4_table_review \
    --reset-all \
    --folder zhlex_files_test
```

---

## File Formats and Data Structures

### Input Data

#### Adobe Extract JSON Format
The system processes JSON files generated by Adobe's Extract API:

```
data/zhlex/zhlex_files_test/170.4/118/170.4-118-modified-updated.json
```

**Key fields used:**
- `elements[]`: Array of document elements
- `elements[].attributes.TableID`: Identifies table elements
- `elements[].Text`: Cell content
- `elements[].Path`: Element structure path
- `elements[].Bounds`: Position coordinates
- `elements[].Page`: Page number

#### Metadata Files
Source information for PDF links:

```
data/zhlex/zhlex_files_test/170.4/118/170.4-118-metadata.json
```

**Key fields:**
- `doc_info.law_page_url`: Link to official page on zh.ch
- `doc_info.law_text_url`: Direct PDF download link

### Output Data

#### Per-Version Correction Files
Saved as `{law_id}-{version}-table-corrections.json` in version directories:

**File Structure:**
```
data/zhlex/zhlex_files_test/
└── 172.110.1/
    └── 129/
        └── 172.110.1-129-table-corrections.json
```

**File Format:**
```json
{
  "law_id": "172.110.1",
  "reviewed_at": "2025-07-05T15:14:13.079884",
  "reviewer": "user",
  "status": "completed",
  "tables": {
    "4050be8c04bc5b59": {
      "hash": "4050be8c04bc5b59",
      "status": "confirmed_without_changes",
      "found_in_versions": ["129"],
      "pages": {"129": [19]},
      "pdf_paths": {"129": "data/zhlex/zhlex_files_test/172.110.1/129/172.110.1-129-original.pdf"},
      "source_links": {"129": "https://www.zh.ch/de/politik-staat/gesetze-beschluesse/..."},
      "original_structure": [
        ["Verwaltungseinheit", "Gliederung"],
        ["Gemeindeamt", "a. Antragstellung an das Eidgenössische Justiz- und Polizeidepartement..."]
      ]
    }
  }
}
```

#### Table Status Types

| Status | Description | Required Fields |
|--------|-------------|-----------------|
| `confirmed_without_changes` | Table approved without changes | `original_structure` |
| `confirmed_with_changes` | Table approved with modifications | `original_structure`, `corrected_structure` |
| `rejected` | Table excluded from output | `reason` (optional) |
| `merged_with_*` | Table merged into another | `merged_into`, `reason` |
| Legacy: `confirmed` | Migrated to appropriate new status | Varies |
| Legacy: `edited` | Migrated to `confirmed_with_changes` | `original_structure`, `corrected_structure` |

#### Progress Files
Batch processing progress is saved as `batch_progress.json`:

```json
{
  "batch_id": "batch_zhlex_files_test_1720089456",
  "total_laws": 25,
  "completed_laws": 15,
  "failed_laws": 2,
  "current_law": "172.110.1",
  "start_time": "2024-07-04T10:30:00.000Z",
  "last_update": "2024-07-04T12:15:30.000Z",
  "status": "running",
  "completed_law_ids": ["170.4", "131.1", "..."],
  "failed_law_ids": ["999.999"],
  "estimated_time_remaining": 3600.0
}
```

### Directory Structure

```
data/zhlex/zhlex_files_test/
├── 170.4/                          # Law directory
│   ├── 118/                        # Version directory
│   │   ├── 170.4-118-modified-updated.json    # Adobe Extract output
│   │   ├── 170.4-118-metadata.json            # Law metadata
│   │   └── 170.4-118-original.pdf             # Original PDF
│   ├── 119/                        # Another version
│   │   └── ...
│   └── 170.4-table-corrections.json      # Table corrections (after review)
├── 172.110.1/
│   └── ...
└── batch_progress.json             # Progress tracking
```

### Export Structure

When using `--export`, corrections are organized in a timestamped directory:

```
/export/path/table_corrections_zhlex_files_test_20240705_143022/
├── 170.4/
│   └── 170.4-table-corrections.json
├── 172.110.1/
│   └── 172.110.1-table-corrections.json
├── ...
└── export_summary.json            # Export metadata and file list
```

---

## Configuration

### Environment Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `ZHLAW_BASE_PATH` | Base path for data files | `data/zhlaw` | `/custom/path` |
| `ZHLAW_MAX_WORKERS` | Default worker count | Auto-detect | `4` |
| `ZHLAW_BROWSER_TIMEOUT` | Browser open timeout (ms) | `10000` | `15000` |

### System Configuration

#### Python Logging
Configure logging level in your environment:

```bash
export PYTHONPATH="${PYTHONPATH}:/home/rdm/github/zhlaw"
export LOGLEVEL="INFO"  # DEBUG, INFO, WARNING, ERROR
```

#### Browser Configuration
The system attempts to open browsers in this order:
1. Windows browser (if running in WSL)
2. System default browser
3. Manual URL display

#### WSL Support
For Windows Subsystem for Linux users:
- Automatic Windows browser detection
- Multiple fallback methods
- Manual URL fallback if auto-open fails

### Performance Tuning

#### Worker Configuration
```bash
# CPU-intensive tasks (table extraction)
--workers $(nproc)  # Use all CPU cores

# I/O-intensive tasks (large files)
--workers $(($(nproc) * 2))  # Use 2x CPU cores

# Memory-constrained systems
--workers 2  # Limit to 2 workers
```

#### Memory Optimization
```bash
# For large datasets, use sequential mode
--mode sequential

# Or limit workers
--workers 1
```

---

## Integration with zhlaw Pipeline

### Integration Point

The manual table review system integrates with the main zhlaw pipeline through the `CorrectionApplier` class:

```python
# Integration occurs during HTML generation
from src.modules.manual_review_module.correction_applier import CorrectionApplier

correction_applier = CorrectionApplier(base_path="data/zhlex")
corrected_elements, corrections_info = correction_applier.apply_corrections(
    elements, law_id, version, folder
)
json_data["elements"] = corrected_elements
```

### Pipeline Flow

```
1. [Main Pipeline: 01_scrape_zhlex_main.py]
   Downloads PDFs and extracts metadata
   ↓
2. [Main Pipeline: 02_process_zhlex_main.py]
   Processes PDFs with Adobe Extract API
   ↓
3. [Table Review: a3_table_extraction.py]
   Extracts and deduplicates tables from processed JSON
   ↓
4. [Table Review: a4_table_review.py]
   Manual review of extracted tables
   ↓
5. [Main Pipeline: 03_build_zhlex_main.py]
   Applies corrections and generates final output
```

### Handling New Law Versions

When new versions of laws are added to the system, the table review process intelligently handles both existing and new tables:

#### For Existing Tables (Previously Reviewed)
- **Preserved decisions**: All existing corrections are maintained
- **No re-review needed**: Tables with existing corrections are not shown for review
- **Content-based matching**: Uses table content hash to identify existing tables across versions

#### For New Tables (Newly Discovered)
- **Automatic detection**: System identifies tables not present in previous versions
- **Undefined status**: New tables are marked as "undefined" requiring review
- **Incremental processing**: Only new tables are presented for review
- **Smart updates**: Uses `CorrectionManager.update_corrections_with_new_tables()`

#### Example Workflow
```bash
# Initial review of law 170.4
python -m src.main_entry_points.a3_table_extraction --law 170.4 --folder zhlex_files_test
python -m src.main_entry_points.a4_table_review --law 170.4 --folder zhlex_files_test
# User reviews 5 tables, saves corrections

# New version of law 170.4 is added with 2 additional tables
python -m src.main_entry_points.a3_table_extraction --law 170.4 --folder zhlex_files_test
python -m src.main_entry_points.a4_table_review --law 170.4 --folder zhlex_files_test
# User only needs to review 2 new tables, existing 5 corrections preserved
```

#### Force Complete Re-Review
If you need to re-review all tables in a law (not just new ones):
```bash
python -m src.main_entry_points.a4_table_review --law 170.4 --reset --folder zhlex_files_test
```

### Correction Application

When HTML is generated, the `CorrectionApplier` modifies the element stream:

| Table Status | Action Taken |
|-------------|--------------|
| **Confirmed without changes** | Table elements preserved as-is |
| **Confirmed with changes** | Original table structure replaced with corrected version |
| **Rejected** | Table elements converted to regular paragraphs |
| **Merged with [hash]** | Table elements removed (merged into another table) |
| **Undefined** | Table elements preserved as-is (no decision made) |
| Legacy statuses | Automatically migrated to new system during processing |

### Data Preservation

- **Original data**: Never modified, always preserved
- **Corrections**: Stored separately, can be reset/modified
- **Versioning**: Each correction file includes timestamps and reviewer info
- **Rollback**: Corrections can be completely removed to restore original behavior

### Performance Impact

- **Zero impact** when no corrections exist
- **Minimal impact** during HTML generation (simple element replacement)
- **No preprocessing** required - corrections applied on-demand

---

## API Reference

### Core Classes

#### LawTableReview

Main orchestrator class for the review process.

```python
from src.main_entry_points.f1_table_review import LawTableReview

# Initialize
reviewer = LawTableReview(
    base_path="data/zhlex",
    simulate_editor=False,
    max_workers=4
)

# Review entire folder with batch processing
reviewer.review_folder(
    folder_path="zhlex_files_test",
    use_batch=True,
    resume=True,
    max_workers=4
)

# Review specific law
reviewer.review_specific_law("170.4", "zhlex_files_test")

# Interactive sequential review
reviewer.review_folder_sequential("zhlex_files_test")

# Generate comprehensive statistics
reviewer.show_detailed_statistics("zhlex_files_test")
```

#### LawTableExtractor

Extracts and deduplicates tables from law files.

```python
from src.modules.manual_review_module.table_extractor import LawTableExtractor

extractor = LawTableExtractor()

# Extract unique tables for a law
unique_tables = extractor.extract_unique_tables_from_law(
    law_id="170.4",
    base_path="data/zhlex/zhlex_files_test"
)

# Get all laws in folder
laws = extractor.get_laws_in_folder("data/zhlex/zhlex_files_test")
```

#### TableEditorInterface

Manages the web-based table editor.

```python
from src.modules.manual_review_module.editor_interface import TableEditorInterface

editor = TableEditorInterface()

# Launch editor for a law
corrections = editor.launch_editor_for_law(
    law_id="170.4",
    unique_tables=unique_tables,
    base_path="data/zhlex/zhlex_files_test"
)

# Enable simulation mode for testing
editor.force_simulation = True
```

#### CorrectionManager

Manages saving and loading of table corrections.

```python
from src.modules.manual_review_module.correction_manager import CorrectionManager

manager = CorrectionManager("data/zhlex")

# Save corrections
success = manager.save_corrections("170.4", corrections, "zhlex_files_test")

# Load corrections
existing_corrections = manager.get_corrections("170.4", "zhlex_files_test")

# Check if law is completed
is_done = manager.is_law_completed("170.4", "zhlex_files_test")
```

#### BatchProcessor

Handles batch processing with progress tracking.

```python
from src.modules.manual_review_module.batch_processor import BatchProcessor

processor = BatchProcessor("data/zhlex", max_workers=4)

# Process folder with progress tracking
final_progress = processor.process_folder_batch(
    folder_path="zhlex_files_test",
    resume=True,
    simulate_editor=False,
    progress_callback=lambda p: print(f"Progress: {p.completion_percentage:.1f}%")
)
```

#### CorrectionApplier

Applies corrections during HTML generation.

```python
from src.modules.manual_review_module.correction_applier import CorrectionApplier

applier = CorrectionApplier("data/zhlex")

# Apply corrections to elements
corrected_elements, info = applier.apply_corrections(
    elements=original_elements,
    law_id="170.4",
    version="118",
    folder="zhlex_files_test"
)
```

### Error Handling

#### Custom Exceptions

```python
from src.modules.manual_review_module.validation import ValidationError

try:
    manager.save_corrections(law_id, corrections, folder)
except ValidationError as e:
    print(f"Validation failed: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

#### Graceful Degradation

The system is designed to fail gracefully:
- Missing correction files → No corrections applied
- Invalid correction data → Validation errors with details
- Browser launch failure → Manual URL provided
- Network issues → Local file fallback

### Extension Points

#### Custom Validation

```python
from src.modules.manual_review_module.validation import CorrectionValidator

class CustomValidator(CorrectionValidator):
    def validate_table_correction(self, correction_data):
        # Custom validation logic
        super().validate_table_correction(correction_data)
        # Additional checks...
```

#### Custom Progress Reporting

```python
def custom_progress_callback(progress):
    # Send to external monitoring system
    send_to_monitoring_dashboard(progress.completion_percentage)
    
    # Log to custom format
    logger.info(f"Batch {progress.batch_id}: {progress.completed_laws}/{progress.total_laws}")

processor.process_folder_batch(
    folder_path="zhlex_files",
    progress_callback=custom_progress_callback
)
```

---

## Troubleshooting

### Common Issues

#### 1. Browser Doesn't Open Automatically

**Problem**: Web interface doesn't open automatically

**Solutions**:
```bash
# Check if running in WSL
cat /proc/version | grep -i microsoft

# Try manual browser opening
# URL will be displayed in console output

# Use simulation mode for testing
python -m src.main_entry_points.f1_table_review --simulate --folder zhlex_files_test
```

#### 2. No Tables Found

**Problem**: System reports "No tables found" for laws that should have tables

**Diagnosis**:
```bash
# Check if JSON files exist
ls data/zhlex/zhlex_files_test/170.4/118/

# Verify JSON file contains table elements
python -c "
import json
with open('data/zhlex/zhlex_files_test/170.4/118/170.4-118-modified-updated.json') as f:
    data = json.load(f)
    table_elements = [e for e in data['elements'] if 'TableID' in e.get('attributes', {})]
    print(f'Found {len(table_elements)} table elements')
"
```

**Solutions**:
- Ensure Adobe Extract API processing was successful
- Check that the JSON files are not corrupted
- Verify the file naming pattern matches expected format

#### 3. Memory Issues During Batch Processing

**Problem**: System runs out of memory during large batch operations

**Solutions**:
```bash
# Reduce worker count
python -m src.main_entry_points.f1_table_review --workers 1 --folder zhlex_files

# Use sequential mode
python -m src.main_entry_points.f1_table_review --mode sequential --folder zhlex_files

# Process smaller batches
python -m src.main_entry_points.f1_table_review --law 170.4 --folder zhlex_files
# Repeat for each law individually
```

#### 4. Correction Files Not Saved

**Problem**: Web interface appears to save but corrections aren't persisted

**Diagnosis**:
```bash
# Check file permissions
ls -la data/zhlex/zhlex_files_test/170.4/

# Check disk space
df -h

# Verify path exists
mkdir -p data/zhlex/zhlex_files_test/170.4/
```

**Solutions**:
- Ensure write permissions on data directory
- Check available disk space
- Verify the base path configuration

#### 5. Web Server Port Conflicts

**Problem**: HTTP server fails to start (port already in use)

**Solutions**:
- System automatically tries ports 8765-8775
- If all ports busy, close other applications or restart system
- Check for other instances of the review system

### Performance Issues

#### Slow Table Extraction

**Symptoms**: Long delays during table extraction phase

**Solutions**:
```bash
# Enable debug logging to identify bottlenecks
export LOGLEVEL=DEBUG
python -m src.main_entry_points.f1_table_review --folder zhlex_files_test

# Use parallel processing
python -m src.main_entry_points.f1_table_review --workers 4 --folder zhlex_files_test
```

#### Slow Web Interface

**Symptoms**: Table editor loads slowly or is unresponsive

**Causes & Solutions**:
- **Large tables**: System handles up to 50 rows × 20 columns efficiently
- **Browser performance**: Try different browser (Chrome recommended)
- **Network issues**: Interface runs on localhost, check firewall settings

### Data Issues

#### Corrupted Correction Files

**Symptoms**: Error loading existing corrections

**Recovery**:
```bash
# Backup corrupted file
cp data/zhlex/zhlex_files_test/170.4/170.4-corrections.json backup/

# Reset corrections for law
python -m src.main_entry_points.f1_table_review --reset 170.4 --folder zhlex_files_test

# Or edit file manually (validate JSON syntax)
```

#### Missing Metadata Files

**Symptoms**: PDF links don't work, missing source URLs

**Solutions**:
- Re-run metadata extraction: `01_scrape_zhlex_main.py`
- Check metadata file naming: `{law_id}-{version}-metadata.json`
- Verify JSON structure includes `doc_info.law_page_url`

### Debugging Tools

#### Enable Verbose Logging

```bash
export LOGLEVEL=DEBUG
python -m src.main_entry_points.f1_table_review --folder zhlex_files_test
```

#### Validation Tool

```python
# Validate correction file
from src.modules.manual_review_module.validation import CorrectionValidator

validator = CorrectionValidator()
try:
    with open('data/zhlex/zhlex_files_test/170.4/170.4-corrections.json') as f:
        corrections = json.load(f)
    validator.validate_correction_file(corrections)
    print("Validation passed")
except Exception as e:
    print(f"Validation failed: {e}")
```

#### Statistics for Debugging

```bash
# Generate detailed statistics
python -m src.main_entry_points.f1_table_review --report json --folder zhlex_files_test

# Check reports/statistics.json for insights
```

---

## Advanced Topics

### Performance Optimization

#### Concurrent Processing Tuning

The system supports fine-tuned concurrent processing:

```python
import multiprocessing

# Optimal for CPU-bound tasks (table extraction)
cpu_workers = multiprocessing.cpu_count()

# Optimal for I/O-bound tasks (file operations)
io_workers = cpu_workers * 2

# Memory-constrained environments
memory_safe_workers = max(1, cpu_workers // 2)
```

#### Memory Usage Patterns

| Component | Memory Impact | Optimization Strategy |
|-----------|---------------|---------------------|
| Table Extraction | Medium | Process laws sequentially |
| Web Interface | Low | Single-law processing |
| Batch Processing | High | Limit workers, use resume |
| Report Generation | Medium | Generate reports separately |

#### Scaling Considerations

- **Small datasets** (< 50 laws): Use default settings
- **Medium datasets** (50-200 laws): Consider sequential mode
- **Large datasets** (200+ laws): Use batch processing with resume
- **Very large datasets** (1000+ laws): Process in chunks by law prefix

### Testing and Quality Assurance

#### Simulation Mode

The system includes comprehensive simulation capabilities:

```bash
# Test extraction and processing without human interaction
python -m src.main_entry_points.f1_table_review \
    --simulate \
    --folder zhlex_files_test \
    --workers 1
```

**Simulation behavior**:
- Tables with content → Automatically confirmed
- Empty tables → Automatically rejected
- No browser interaction required
- Full correction file generation

#### Validation Testing

```python
# Test correction file validation
from src.modules.manual_review_module.validation import CorrectionValidator, ValidationError

validator = CorrectionValidator()

test_corrections = {
    "law_id": "test_law",
    "tables": {
        "test_hash": {
            "status": "confirmed",
            "original_structure": [["A", "B"], ["1", "2"]]
        }
    }
}

try:
    validator.validate_correction_file(test_corrections)
    print("✓ Validation passed")
except ValidationError as e:
    print(f"✗ Validation failed: {e}")
```

#### Integration Testing

```bash
# Test full pipeline integration
python -m src.cmd.02_process_zhlex_main --folder zhlex_files_test
python -m src.main_entry_points.f1_table_review --simulate --folder zhlex_files_test
python -m src.cmd.03_build_site_main --folder zhlex_test_files
```

### Extending the System

#### Custom Table Operations

Add new table operations by extending the web interface:

```javascript
// In custom_table_review.html
function customTableOperation() {
    const table = lawData.tables[currentTableIndex];
    
    // Custom logic here
    
    // Update corrections
    corrections[table.hash] = {
        // ... custom correction data
    };
    
    // Update UI
    showTable(currentTableIndex);
}
```

#### Custom Correction Types

Extend the correction system with new status types:

```python
# In correction_applier.py
class ExtendedCorrectionApplier(CorrectionApplier):
    def apply_corrections(self, elements, law_id, version, folder):
        corrections = self.load_corrections(law_id, folder)
        
        for element in elements:
            table_id = element.get('attributes', {}).get('TableID')
            if table_id and table_id in corrections:
                correction = corrections[table_id]
                
                if correction['status'] == 'custom_status':
                    # Handle custom status
                    pass
                    
        return super().apply_corrections(elements, law_id, version, folder)
```

#### Custom Reporting

Create custom report formats:

```python
from src.modules.manual_review_module.statistics import StatisticsCollector

class CustomReportGenerator:
    def __init__(self, base_path):
        self.stats = StatisticsCollector(base_path)
    
    def generate_custom_report(self, folder_path):
        stats = self.stats.collect_statistics(folder_path)
        
        # Custom report logic
        custom_data = self.process_statistics(stats)
        
        # Export in custom format
        self.export_custom_format(custom_data)
```

### Security Considerations

#### Data Protection

- **No sensitive data exposure**: System only processes public legal documents
- **Local processing**: All review happens on local machine
- **Secure connections**: PDF links use HTTPS to official sources

#### Access Control

- **File system permissions**: Respect system file permissions
- **Network access**: Only accesses localhost web server
- **Browser isolation**: Editor runs in isolated browser context

#### Audit Trail

- **Complete traceability**: All corrections include timestamps and reviewer info
- **Reversible changes**: Original data never modified
- **Version tracking**: Full history of corrections available

### Migration and Backup

#### Backup Strategy

```bash
# Recommended: Use the built-in export command
python -m src.main_entry_points.a4_table_review --export --folder zhlex_files_test

# Alternative: Manual backup
cp -r data/zhlex/zhlex_files_test/*/*.json backup/corrections/

# Backup progress files
cp batch_progress.json backup/

# Backup reports
cp -r reports/ backup/
```

#### Migration Between Environments

```bash
# Export corrections from source environment
tar -czf corrections_backup.tar.gz data/zhlex/*//*-corrections.json

# Import to target environment
tar -xzf corrections_backup.tar.gz -C /target/path/
```

#### Version Compatibility

The correction file format is designed for forward compatibility:
- **Unknown fields**: Ignored gracefully
- **Schema evolution**: New fields can be added without breaking existing files
- **Validation**: Strict validation ensures data integrity

---

## Conclusion

The Manual Table Review System provides a comprehensive solution for human-supervised quality control of automatically extracted table structures. With its intuitive web interface, robust batch processing capabilities, and seamless pipeline integration, it ensures high-quality output while maintaining efficiency and reliability.

For additional support or feature requests, please refer to the project's issue tracker or documentation updates.

---

**Document Version**: 1.1  
**Last Updated**: January 2025  
**Compatibility**: zhlaw pipeline v2.0+