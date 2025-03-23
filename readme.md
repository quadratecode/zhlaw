# ZHLaw

[![License: EUPL v1.2](https://img.shields.io/badge/License-EUPL_v1.2-blue.svg)](https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md)

## About

ZHLaw improves access to legal texts from the canton of Zurich by converting them from PDF into a machine-readable format and presenting them as a static website.

<img width="675" alt="zhlaw_dark_light_comparison_20250316" src="https://github.com/user-attachments/assets/9971ef2b-3550-49cf-8230-c85972932b42" />


**Note**: This project is in active development. Functionality and interfaces may change.

**⚠️ Important**: Since the conversion process will never be perfect, always refer to the original PDFs published by the canton of Zurich.

## Features

This repository contains:

- **Data processing pipelines**:
  - Scrape and analyze the weekly dispatch from the Zurich cantonal parliament
  - Extract and convert legal texts from PDF to HTML
  - Process and enhance legal texts with metadata and navigation
  - Apply intelligent formatting, cross-referencing, and structure

- **Web presentation**:
  - Static site generator for browsable legal documents 
  - Search functionality (powered by Pagefind)
  - Version comparison and history tracking
  - Mobile-responsive design
  - Automatic metadata extraction

See the [project kanban board](https://github.com/users/quadratecode/projects/1/views/1) for completed and planned features.

## Prerequisites

### For Zurich cantonal laws processing (in beta):
- Python 3.10+
- Adobe Extract API Key
- OpenAI API Key

### For federal laws processing (in alpha):
- Python 3.10+
- Adobe Extract API Key

### For static site generation (in beta):
- Python 3.10+
- [Pagefind](https://github.com/CloudCannon/pagefind)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/quadratecode/zhlaw.git
   cd zhlaw
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `credentials.json` file for Adobe Extract API credentials.

5. Set your OpenAI API key as an environment variable:
   ```bash
   export OPENAI_API_KEY="your-api-key-here"  # On Windows: set OPENAI_API_KEY=your-api-key-here
   ```

## Usage

### Main Processing Modules

The project consists of several command modules:

1. **Scrape and download legal texts**:
   ```bash
   python -m src.cmd.01_scrape_zhlex_main
   ```

2. **Process and enhance legal texts**:
   ```bash
   python -m src.cmd.02_process_zhlex_main
   ```

3. **Build the website**:
   ```bash
   python -m src.cmd.03_build_site_main
   ```

4. **Process parliamentary dispatches**:
   ```bash
   python -m src.cmd.04_process_krzh_dispatch_main
   ```

### Building with Specific Options

The site builder accepts parameters:

```bash
python -m src.cmd.03_build_site_main --folder [zhlex_files|ch_files|all_files|test_files] --db-build [yes|no] --placeholders [yes|no]
```

## Project Structure

```
zhlaw/
├── data/                      # Storage for processed data
├── logs/                      # Log files
├── public/                    # Generated static site
├── src/
│   ├── cmd/                   # Main command modules
│   ├── modules/               # Processing modules
│   │   ├── dataset_generator_module/ # Markdown dataset generation
│   │   ├── fedlex_module/     # Federal law processing
│   │   ├── general_module/    # Shared utilities
│   │   ├── krzh_dispatch_module/  # Parliamentary dispatch processing
│   │   ├── law_pdf_module/    # PDF processing
│   │   ├── site_generator_module/ # Static site generation
│   │   └── zhlex_module/      # Cantonal law processing
│   ├── server_scripts/        # Server-side scripts
│   └── static_files/          # Static assets
└── requirements.txt           # Python dependencies
```

## Important Notes

- **Search Indexing**: Only the newest versions of laws are indexed by the search functionality to improve build performance and search results relevance.

- **Web Server**: The project uses PHP for server-side redirects (handling `col-zh/<ordnungsnummer>` URLs).

- **API Usage**: Please be mindful of API rate limits and server load when running the API or scraping modules.

## License

This project is licensed under the EUPL (v1.2 only, with specific provisions). For more information, see the [LICENSE](https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md) file.

## Contributing

Contributions are greatly appreciated. Please note that by adding content to this repository, you agree to license your contributions under the project's license terms.
