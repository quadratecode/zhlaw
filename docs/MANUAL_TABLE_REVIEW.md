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

- **Intelligent Table Extraction**: Automatically identifies and deduplicates tables across multiple document versions
- **Web-Based Editor**: Intuitive browser interface for reviewing and editing table structures
- **Four-Status System**: Clear status options (Undefined → Confirmed without changes/Confirmed with changes/Rejected)
- **Advanced Editing**: Add/remove rows/columns, edit cell content, merge tables
- **Batch Processing**: Efficient processing of multiple laws with progress tracking and automatic resume capability
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

1. **Test with Sample Data**
   ```bash
   # Navigate to project root
   cd /home/rdm/github/zhlaw
   
   # Review tables in test dataset using batch processing
   python -m src.main_entry_points.f1_table_review --folder zhlex_files_test
   ```

2. **Review a Specific Law**
   ```bash
   # Review tables for a specific law
   python -m src.main_entry_points.f1_table_review --law 170.4 --folder zhlex_files_test
   ```

3. **Generate Reports**
   ```bash
   # Generate comprehensive reports
   python -m src.main_entry_points.f1_table_review --report html --folder zhlex_files_test
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
│  Main Entry Point: table_review.py                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ LawTableReview  │  │ BatchProcessor  │  │ ProgressReporter│ │
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
    ↓ (LawTableExtractor.extract_unique_tables_from_law)
[Unique table structures with hashes]
    ↓ (TableEditorInterface.launch_editor_for_law)
[Human review via web interface]
    ↓ (CorrectionManager.save_corrections)
[Saved correction files (.json)]
    ↓ (During HTML generation)
[CorrectionApplier.apply_corrections]
    ↓ (json_to_html.py)
[Final HTML with corrected tables]
```

### Component Responsibilities

| Component | Purpose | Key Methods |
|-----------|---------|-------------|
| **LawTableExtractor** | Extract and deduplicate tables | `extract_unique_tables_from_law()` |
| **TableEditorInterface** | Manage web-based editor | `launch_editor_for_law()` |
| **CorrectionManager** | Save/load corrections | `save_corrections()`, `get_corrections()` |
| **BatchProcessor** | Batch processing with progress | `process_folder_batch()` |
| **CorrectionApplier** | Apply corrections to pipeline | `apply_corrections()` |
| **StatisticsCollector** | Generate reports and metrics | `collect_statistics()` |

---

## User Workflows

### Workflow 1: Batch Processing (Recommended)

```bash
# Process entire test dataset
python -m src.main_entry_points.f1_table_review \
    --folder zhlex_files_test \
    --workers 4 \
    --resume
```

**Steps:**
1. System scans all laws in the folder
2. Extracts unique tables across versions
3. Opens web interface for each law with tables
4. User reviews and corrects tables
5. Progress is automatically saved
6. Can be interrupted and resumed

### Workflow 2: Individual Law Review

```bash
# Review specific law
python -m src.main_entry_points.f1_table_review \
    --law 170.4 \
    --folder zhlex_files_test
```

**Steps:**
1. System processes only the specified law
2. Extracts tables for all versions of that law
3. Opens web interface for review
4. Saves corrections for that law only

### Workflow 3: Legacy Sequential Processing

```bash
# Process laws one by one without parallelization (legacy mode)
python -m src.main_entry_points.f1_table_review \
    --folder zhlex_files_test \
    --no-batch
```

**Steps:**
1. Process laws in alphabetical order
2. Complete each law before moving to next
3. Suitable for compatibility with old workflows

### Workflow 4: Interactive Sequential Mode

```bash
# Review laws one by one with navigation controls
python -m src.main_entry_points.f1_table_review \
    --folder zhlex_files_test \
    --sequential
```

**Steps:**
1. Lists all laws with tables and their completion status
2. Allows navigation between laws (next, previous, skip)
3. Provides interactive controls for methodical review
4. Can be paused and resumed at any time

### Workflow 5: Report Generation

```bash
# Generate comprehensive reports
python -m src.main_entry_points.f1_table_review \
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
│  Progress: 5/23 tables reviewed (22%)                          │
├─────────────────────────────────────────────────────────────────┤
│  Table 1 of 23 | hash: a1b2c3d4... | Status: [Radio Buttons]  │
│                                                                 │
│  ○ Undefined  ◉ Confirmed  ○ Rejected                         │
├─────────────────────────────────────────────────────────────────┤
│  Context Information:                                           │
│  • Found in versions: v118, v119                               │
│  • Pages: v118: 2,3 | v119: 2,3                               │
│  • PDF Documents: [View v118 on zh.ch] [View v119 on zh.ch]   │
│  • Structure: 5 rows × 3 columns                               │
├─────────────────────────────────────────────────────────────────┤
│  Table Editor: [+ Row] [+ Column] [- Row] [- Column] [Reset]   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Header 1  │  Header 2   │  Header 3   │                   │ │
│  │  Cell 1,1  │  Cell 1,2   │  Cell 1,3   │ (editable cells) │ │
│  │  Cell 2,1  │  Cell 2,2   │  Cell 2,3   │                   │ │
│  └─────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  Actions: [⟱ Merge with Next] [→ Skip for Now]                │
├─────────────────────────────────────────────────────────────────┤
│  Final Actions: [Save All Corrections] [Export JSON] [Cancel]  │
└─────────────────────────────────────────────────────────────────┘
```

### Table Status System

| Status | Description | Editing Enabled |
|--------|-------------|-----------------|
| **Undefined** | Default state, no decision made | ❌ No |
| **Confirmed without changes** | Table correctly converted, no editing needed | ❌ No |
| **Confirmed with changes** | Table is valid but edits are needed | ✅ Yes |
| **Rejected** | Table excluded from output (converted to paragraphs) | ❌ No |

### Key Features

#### 1. Status Selection
- **Radio buttons** for status selection
- **Color-coded** status indicators
- **Automatic save** when status changes

#### 2. Table Editing (Confirmed Status Only)
- **Click cells** to edit content
- **Add/remove rows/columns** with buttons
- **Visual feedback** for modified cells
- **Automatic structure updates**

#### 3. Context Information
- **Version tracking**: Which versions contain this table
- **Page references**: Exact page numbers
- **PDF links**: Direct links to view original documents on zh.ch
- **Structure info**: Current table dimensions

#### 4. Merge Functionality
- **Combine tables**: Merge current table with next table
- **Automatic append**: Next table content added to current
- **Status updates**: Next table marked as "merged"
- **Seamless workflow**: Continue editing merged result

#### 5. Navigation
- **Previous/Next**: Navigate between tables
- **Progress tracking**: Current position and completion percentage
- **Overview**: Summary of all table statuses

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd + ←` | Previous table |
| `Ctrl/Cmd + →` | Next table |
| `Ctrl/Cmd + S` | Save corrections |

---

## Command Line Reference

### Main Command

```bash
python -m src.main_entry_points.f1_table_review [OPTIONS]
```

### Required Arguments

| Argument | Description | Values |
|----------|-------------|--------|
| `--folder` | Target folder for processing | `zhlex_files_test`, `zhlex_files` |

### Optional Arguments

| Argument | Description | Default | Example |
|----------|-------------|---------|---------|
| `--law LAW_ID` | Review specific law only | None | `--law 170.4` |
| `--workers N` | Number of parallel workers | Auto-detect | `--workers 4` |
| `--sequential` | Interactive sequential mode | False | `--sequential` |
| `--no-batch` | Use legacy sequential mode | False | `--no-batch` |
| `--simulate` | Use simulation instead of browser | False | `--simulate` |
| `--no-resume` | Don't resume from previous progress | False | `--no-resume` |
| `--report FORMAT` | Generate reports | None | `--report html` |
| `--reset` | Reset corrections (with --law) | False | `--reset` |
| `--reset-all` | Reset all corrections | False | `--reset-all` |
| `--status` | Show review progress | False | `--status` |
| `--stats` | Show detailed statistics | False | `--stats` |

### Processing Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| Default (batch) | Parallel processing with automatic resume | Fast batch processing |
| `--sequential` | Interactive one-by-one review with navigation | Methodical review with user control |
| `--no-batch` | Legacy sequential mode (one law at a time) | Compatibility mode |

### Report Formats

| Format | Description | Output |
|--------|-------------|--------|
| `json` | Machine-readable statistics | `reports/statistics.json` |
| `csv` | Spreadsheet-compatible data | `reports/table_review_data.csv` |
| `html` | Comprehensive web report | `reports/table_review_report.html` |
| `all` | Generate all formats | Multiple files |

### Examples

#### Basic Usage
```bash
# Review test dataset
python -m src.main_entry_points.f1_table_review --folder zhlex_files_test

# Review production dataset
python -m src.main_entry_points.f1_table_review --folder zhlex_files
```

#### Advanced Usage
```bash
# High-performance batch processing
python -m src.main_entry_points.f1_table_review \
    --folder zhlex_files \
    --workers 8

# Interactive sequential review
python -m src.main_entry_points.f1_table_review \
    --folder zhlex_files_test \
    --sequential

# Testing without browser interaction
python -m src.main_entry_points.f1_table_review \
    --folder zhlex_files_test \
    --simulate

# Start fresh (don't resume previous work)
python -m src.main_entry_points.f1_table_review \
    --folder zhlex_files_test \
    --no-resume
```

#### Specific Law Review
```bash
# Review single law
python -m src.main_entry_points.f1_table_review \
    --law 170.4 \
    --folder zhlex_files_test

# Review multiple specific laws (run separately)
python -m src.main_entry_points.f1_table_review --law 170.4 --folder zhlex_files_test
python -m src.main_entry_points.f1_table_review --law 172.110.1 --folder zhlex_files_test
```

#### Report Generation and Statistics
```bash
# Show basic progress
python -m src.main_entry_points.f1_table_review \
    --folder zhlex_files_test \
    --status

# Show detailed statistics
python -m src.main_entry_points.f1_table_review \
    --folder zhlex_files_test \
    --stats

# Generate HTML report
python -m src.main_entry_points.f1_table_review \
    --report html \
    --folder zhlex_files_test

# Generate all report formats
python -m src.main_entry_points.f1_table_review \
    --report all \
    --folder zhlex_files
```

#### Reset and Maintenance
```bash
# Reset specific law
python -m src.main_entry_points.f1_table_review \
    --law 170.4 \
    --reset \
    --folder zhlex_files_test

# Reset all corrections (use with caution!)
python -m src.main_entry_points.f1_table_review \
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

#### Correction Files
Saved as `{law_id}-table-corrections.json` in law directory:

```json
{
  "law_id": "170.4",
  "reviewed_at": "2024-07-04T12:34:56.789Z",
  "reviewer": "system_user",
  "status": "completed",
  "statistics": {
    "total_tables": 3,
    "confirmed": 2,
    "rejected": 1,
    "edited": 1,
    "merged": 0
  },
  "tables": {
    "a1b2c3d4e5f6g7h8": {
      "hash": "a1b2c3d4e5f6g7h8",
      "status": "confirmed",
      "found_in_versions": ["118", "119"],
      "pages": {
        "118": [2, 3],
        "119": [2, 3]
      },
      "pdf_paths": {
        "118": "data/zhlex/zhlex_files_test/170.4/118/170.4-118-original.pdf",
        "119": "data/zhlex/zhlex_files_test/170.4/119/170.4-119-original.pdf"
      },
      "source_links": {
        "118": "https://www.zh.ch/de/politik-staat/gesetze-beschluesse/...",
        "119": "https://www.zh.ch/de/politik-staat/gesetze-beschluesse/..."
      },
      "original_structure": [
        ["Header 1", "Header 2", "Header 3"],
        ["Cell 1,1", "Cell 1,2", "Cell 1,3"],
        ["Cell 2,1", "Cell 2,2", "Cell 2,3"]
      ],
      "corrected_structure": [
        ["Header 1", "Header 2", "Header 3"],
        ["Cell 1,1", "Corrected Cell", "Cell 1,3"],
        ["Cell 2,1", "Cell 2,2", "Cell 2,3"]
      ]
    },
    "x9y8z7w6v5u4t3s2": {
      "hash": "x9y8z7w6v5u4t3s2",
      "status": "rejected",
      "found_in_versions": ["118"],
      "pages": {
        "118": [5]
      },
      "reason": "Not a real table - just aligned text"
    },
    "m1n2o3p4q5r6s7t8": {
      "hash": "m1n2o3p4q5r6s7t8",
      "status": "merged",
      "found_in_versions": ["118"],
      "pages": {
        "118": [4]
      },
      "merged_into": "a1b2c3d4e5f6g7h8",
      "reason": "Merged into table a1b2c3d4e5f6g7h8"
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
3. [Manual Review: table_review.py] ← MANUAL INTERVENTION
   Human reviews and corrects tables
   ↓
4. [Main Pipeline: 03_build_site_main.py]
   Generates HTML with corrections applied
   ↓
5. [Output: Static website with corrected tables]
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
# Backup all corrections
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

**Document Version**: 1.0  
**Last Updated**: July 2024  
**Compatibility**: zhlaw pipeline v2.0+