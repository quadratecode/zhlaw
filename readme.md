# About

**Warning: This project is in early development. Stuff will change and break.**

This repository contains:

- A data processing pipeline to scrape and analyse the weekly dispatch of the legislative body of the canton of Zurich
- A data processing pipeline to scrape the collection of laws of the canton of Zurich and to convert them from PDF into HTML
- A static site generator to serve these files in a browsable format (currently available under [https://www.zhlaw.ch](https://www.zhlaw.ch))

This project aims to enhance usability of legal documents and to enable further data processing.

# Features

**Implemented features**:

- [x] Rapid search
- [x] Deep linking into provisions and subprovisions
- [x] Checking against other versions and indicating in force status
- [x] Backlinking footnotes to better visualize changes

**Planned features:**

- [ ] Further metadata for laws (e.g. processing time)
- [ ] Data sets of the collection and collection structure
- [ ] Direct access to a browsable index
- [ ] Dark mode
- [ ] Better search results
    - [ ] Fine tune relevance
    - [ ] Better excerpts
    - [ ] Default filter for in force laws
- [ ] Better mobile experience
- [ ] Sitemap and better head meta tags
- [ ] Code refractoring
- [ ] Ongoing quality control
- [ ] Design enhancements
- [ ] Version comparison between preceeding and following versions
- [ ] Provision of datasets
- [ ] Collection completion (currently errors with ~200 entries)

**Moonshot features:**

- [ ] Version comparison against all versions of a law
- [ ] Processing for tables, amendmends and other non-standard content

# Development Requirements

Data processing for the weekly digest:
- Python 3.10
- Adobe Extract API Key
- OpenAI API Key

Data processing for laws:
- Python 3.10
- Adobe Extract API Key

Static site generator:
- Python 3.10
- [Pagefind](https://github.com/CloudCannon/pagefind)

**Please remember to be friendly to the servers you are requesting from.**

# License

This project is licensed under the EUPL (v1.2 only, with specific provisions). For more information, see the [LICENSE](https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md) file.

# Contribute

Contributions are greatly appreciated. Please be advised that if you add content to this repository, which is licensed under the EUPL (v1.2 only, with specific provisions), you license your content under the same terms, and you agree that you have the right to license that Content under those terms (see [GitHub TOS](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service#6-contributions-under-repository-license)). Please do not forget to add your username or real name to the [list of contributors](https://github.com/quadratecode/zhlaw/blob/main/CONTRIBUTORS.md) upon inclusion of your content.
