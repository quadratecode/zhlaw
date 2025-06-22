# zhlaw – a static site builder for laws

[![License: EUPL v1.2](https://img.shields.io/badge/License-EUPL_v1.2-blue.svg)](https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md)

A comprehensive static site builder for legal texts from the Canton of Zurich with a full conversion pipeline from PDF to structured HTML and MD. Support for federal laws is planned.

**⚠️ Important**: This is an unofficial tool. The conversion process may introduce errors. Always refer to the original PDFs published by official sources for authoritative information. Use at your own risk.

**Note**: This project is in active development. Functionality and interfaces may change.

<img width="960" alt="20250622_zhlaw" src="https://github.com/user-attachments/assets/947faa75-41c9-4508-bf01-36a8ce738050" />

## Features

### Data Processing
- **Automated PDF extraction** using Adobe Extract API
- **Cross-reference detection** and linking between legal provisions
- **Version tracking** with history preservation
- **Metadata extraction** and enrichment
- **Marginalia processing** for annotations and references
- **Intelligent text processing** with OpenAI for revision detection within dispatches

### Web Presentation
- **Static site generation** for fast, secure hosting
- **Full-text search** powered by [Pagefind](https://pagefind.app/)
- **Dark/light theme** with system preference detection
- **Mobile-responsive design**
- **Version tracking** and navigation
- **Anchor linking** for precise references
- **Parliamentary dispatch integration** with RSS feeds

See the [project board](https://github.com/users/quadratecode/projects/1/views/1) for planned features and known issues.

## Contributing

Contributions are welcome. Please note that by contributing, you agree to license your contributions under the project's license terms.

## License

This project is licensed under the EUPL, v1.2 only, with specific provisions. See [LICENSE.md](https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md) for details.

### Third-party Components

- **Pagefind**: MIT License
- **Adobe Extract API**: Commercial service
- **OpenAI API**: Commercial service

---

For questions or issues, please use the [GitHub issue tracker](https://github.com/quadratecode/zhlaw/issues).
