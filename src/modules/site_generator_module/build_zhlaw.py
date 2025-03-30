# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

import logging
import re
from typing import Any, Dict, List, Tuple, Union
from bs4 import BeautifulSoup, Tag
import arrow

# Get logger from main module
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Module-Level Constants
# -----------------------------------------------------------------------------
BUTTON_CONFIGS: List[Dict[str, str]] = [
    {"symbol": "⇽", "text": "vorherige Version", "id": "prev_ver"},
    {"symbol": "⇾", "text": "nächste Version", "id": "next_ver"},
    {"symbol": "⇥", "text": "neuste Version", "id": "new_ver"},
]
ENUM_CLASSES: List[str] = ["enum-lit", "enum-ziff", "enum-dash"]
EXCLUDED_MERGE_CLASSES = {"marginalia", "provision", "subprovision"}
ANNEX_KEYWORDS: List[str] = ["Anhang", "Anhänge", "Verzeichnis"]
FOOTNOTE_LINE_ID = "footnote-line"


# -----------------------------------------------------------------------------
# Navigation and Header Functions
# -----------------------------------------------------------------------------
def create_nav_buttons(soup: BeautifulSoup) -> Tag:
    """
    Creates navigation buttons with separated symbols and text.
    """
    nav_div: Tag = soup.new_tag("div", **{"class": "nav-buttons"})
    for config in BUTTON_CONFIGS:
        button: Tag = soup.new_tag(
            "button",
            **{
                "class": "nav-button",
                "id": config["id"],
                "onclick": "location.href='#';",
            },
        )
        symbol: Tag = soup.new_tag("span", **{"class": "nav-symbol"})
        symbol.string = config["symbol"]
        button.append(symbol)
        text: Tag = soup.new_tag("span", **{"class": "nav-text"})
        text.string = config["text"]
        button.append(text)
        nav_div.append(button)
    return nav_div


def insert_header(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Inserts a header with search bar on the left, toggle in the middle, and logo on the right.
    Also adds Pagefind UI assets to the <head> and dark mode toggle button.
    """
    header: Tag = soup.new_tag("div", **{"id": "page-header"})
    header_content: Tag = soup.new_tag("div", **{"class": "header-content"})
    header.append(header_content)

    # Search container (now first)
    search_container: Tag = soup.new_tag("div", **{"class": "search-container"})
    search_div: Tag = soup.new_tag("div", id="search")
    search_container.append(search_div)
    header_content.append(search_container)

    # Dark mode toggle container (now second)
    dark_mode_container: Tag = soup.new_tag(
        "div", **{"class": "dark-mode-toggle-container"}
    )
    dark_mode_toggle: Tag = soup.new_tag(
        "button", id="dark-mode-toggle", **{"aria-label": "Toggle dark mode"}
    )

    # Use SVG for moon icon (default)
    moon_svg = soup.new_tag(
        "svg",
        xmlns="http://www.w3.org/2000/svg",
        width="28",
        height="28",
        viewBox="0 0 24 24",
        fill="none",
        stroke="currentColor",
        **{"stroke-width": "2", "stroke-linecap": "round", "stroke-linejoin": "round"},
    )
    moon_path = soup.new_tag(
        "path", d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"
    )
    moon_svg.append(moon_path)
    dark_mode_toggle.append(moon_svg)

    dark_mode_container.append(dark_mode_toggle)
    header_content.append(dark_mode_container)

    # Logo container (now third/last)
    logo_container: Tag = soup.new_tag("div", **{"class": "logo-container"})
    logo_link: Tag = soup.new_tag("a", href="/")
    logo_img: Tag = soup.new_tag(
        "img", src="/logo-zhlaw.svg", alt="zhlaw.ch Logo", **{"class": "header-logo"}
    )
    logo_link.append(logo_img)
    logo_container.append(logo_link)
    header_content.append(logo_container)

    # Insert Pagefind UI assets into <head>
    head: Union[Tag, None] = soup.find("head")
    if head:
        css_link: Tag = soup.new_tag(
            "link", href="/pagefind/pagefind-ui.css", rel="stylesheet"
        )
        head.append(css_link)
        script_tag: Tag = soup.new_tag("script", src="/pagefind/pagefind-ui.js")
        head.append(script_tag)

        # Add dark mode script
        dark_mode_script: Tag = soup.new_tag("script", src="/dark-mode.js", defer=True)
        head.append(dark_mode_script)

    # Pagefind initialization script
    search_script: Tag = soup.new_tag("script")
    search_script.string = """
        window.addEventListener('DOMContentLoaded', (event) => {
            new PagefindUI({
                element: "#search",
                showSubResults: false,
                pageSize: 15,
                excerptLength: 25,
                ranking: {
                    termFrequency: 0.0,
                    termSaturation: 1.6,
                    termSimilarity: 2.0,
                },
                translations: {
                    placeholder: "Gesetzessammlung durchsuchen",
                    zero_results: "Keine Treffer für [SEARCH_TERM]"
                },
                openFilters: ["Text in Kraft"],
                autofocus: true,
                showImages: false
            });
        });
    """
    header.append(search_script)

    body: Union[Tag, None] = soup.find("body")
    if body:
        body.insert(0, header)
    return soup


def insert_footer(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Inserts a footer with links (including contact) and a disclaimer at the bottom of the HTML.
    """
    footer: Tag = soup.new_tag("div", **{"id": "page-footer"})
    links_container: Tag = soup.new_tag("div", **{"class": "footer-links-container"})
    links = [
        ("Home", "/"),
        ("Über zhlaw.ch", "/about.html"),
        ("Datenschutz", "/privacy.html"),
        ("Ratsversand", "/dispatch.html"),
        ("Datensätze", "/data.html"),
        ("Kontakt", "mailto:admin@zhlaw.ch"),
    ]
    for i, (text, href) in enumerate(links):
        link: Tag = soup.new_tag("a", href=href, **{"class": "footer-links"})
        link.string = text
        links_container.append(link)
        if i < len(links) - 1:
            separator: Tag = soup.new_tag("span", **{"class": "footer-seperator"})
            separator.string = "∗"
            links_container.append(separator)
    footer.append(links_container)
    disclaimer_container: Tag = soup.new_tag("div", **{"id": "disclaimer"})
    disclaimer_p1: Tag = soup.new_tag("p")
    disclaimer_p1.string = "Dies ist keine amtliche Veröffentlichung. Massgebend ist die Veröffentlichung durch die Staatskanzlei ZH."
    disclaimer_container.append(disclaimer_p1)
    disclaimer_p2: Tag = soup.new_tag("p")
    disclaimer_p2.string = "Es wird keine Gewähr für die Richtigkeit, Vollständigkeit oder Aktualität der hier zur Verfügung gestellten Inhalte übernommen."
    disclaimer_container.append(disclaimer_p2)
    footer.append(disclaimer_container)
    body: Union[Tag, None] = soup.find("body")
    if body:
        body.append(footer)

        # Add GoatCounter script
        # Comment out if not needed on clone
        goatcounter_script = soup.new_tag(
            "script",
            attrs={
                "data-goatcounter": "https://stats.zhlaw.ch/count",
                "async": None,
                "src": "//stats.zhlaw.ch/count.js",
            },
        )
        body.append(goatcounter_script)
    return soup


# -----------------------------------------------------------------------------
# HTML Structure Modification Functions
# -----------------------------------------------------------------------------
def modify_html(soup: BeautifulSoup, erlasstitel: str) -> BeautifulSoup:
    """
    Modifies the HTML by adding stylesheet, favicon, meta tags, and reorganizing the body structure.
    Also adds dark mode support by including the dark mode script.
    Note: No data-pagefind-body attribute is added here - it will be added selectively later.
    """
    # Add no-js class to html element for JavaScript detection
    html_tag = soup.html
    if html_tag:
        html_tag["class"] = html_tag.get("class", []) + ["no-js", "light-mode"]

    head: Union[Tag, None] = soup.head
    if head is None:
        head = soup.new_tag("head")
        soup.html.insert(0, head)

    # Add CSS stylesheet
    css_link: Tag = soup.new_tag("link", rel="stylesheet", href="../styles.css")
    head.append(css_link)

    # Add favicon links
    shortcut_icon: Tag = soup.new_tag(
        "link", rel="shortcut icon", href="../favicon.ico", type="image/x-icon"
    )
    head.append(shortcut_icon)
    favicon: Tag = soup.new_tag(
        "link", rel="icon", href="../favicon.ico", type="image/x-icon"
    )
    head.append(favicon)

    # Add title
    title_tag: Tag = soup.new_tag("title")
    title_tag.string = erlasstitel
    head.append(title_tag)

    # Add viewport and charset meta tags
    viewport_meta: Tag = soup.new_tag(
        "meta",
        attrs={"name": "viewport", "content": "width=device-width, initial-scale=1"},
    )
    head.append(viewport_meta)
    encoding_meta: Tag = soup.new_tag("meta", charset="utf-8")
    head.append(encoding_meta)

    # Add dark mode script
    dark_mode_script: Tag = soup.new_tag("script", src="../dark-mode.js", defer=True)
    head.append(dark_mode_script)

    # Reorganize body contents into structured containers
    body: Union[Tag, None] = soup.body
    if body:
        main_container: Tag = soup.new_tag("div", **{"class": "main-container"})
        sidebar: Tag = soup.new_tag("div", id="sidebar")
        content: Tag = soup.new_tag("div", **{"class": "content"})
        # Create law_div without data-pagefind-body (will be added conditionally later)
        law_div: Tag = soup.new_tag("div", **{"id": "law"})
        while body.contents:
            law_div.append(body.contents[0])
        content.append(law_div)
        main_container.append(sidebar)
        main_container.append(content)
        body.append(main_container)
    return soup


# -----------------------------------------------------------------------------
# Date and Sorting Functions
# -----------------------------------------------------------------------------
def format_date(date_str: str) -> str:
    """
    Formats a date string from YYYYMMDD to DD.MM.YYYY.
    """
    try:
        return arrow.get(date_str, "YYYYMMDD").format("DD.MM.YYYY")
    except Exception as e:
        logger.warning(f"Error formatting date {date_str}: {e} -> Returning N/A")
        return "N/A"


def alphanum_key(s: str) -> List[Union[int, str]]:
    """
    Splits a string into a list of number and non-number chunks for natural sorting.
    """
    return [
        int(text) if text.isdigit() else text.lower()
        for text in re.split("([0-9]+)", s)
    ]


# -----------------------------------------------------------------------------
# Metadata, Versions, and Navigation Functions
# -----------------------------------------------------------------------------
def insert_combined_table(
    soup: BeautifulSoup,
    doc_info: Dict[str, Any],
    in_force_status: bool,
    ordnungsnummer: str,
    current_nachtragsnummer: str,
    law_origin: str,
) -> BeautifulSoup:
    """
    Inserts a metadata table and status message into the document.
    """
    # Add the pagefind metadata to the head section
    head: Union[Tag, None] = soup.find("head")
    if head:
        pagefind_meta: Tag = soup.new_tag("meta")
        pagefind_meta["name"] = "pagefind:Text in Kraft"
        pagefind_meta["content"] = "Ja" if in_force_status else "Nein"
        head.append(pagefind_meta)

        # Also add a filter metadata tag
        pagefind_filter: Tag = soup.new_tag("meta")
        pagefind_filter["data-pagefind-filter"] = (
            f"Text in Kraft:{pagefind_meta['content']}"
        )
        head.append(pagefind_filter)

    status_div: Tag = soup.new_tag(
        "div",
        **{
            "id": "status-message",
            "class": "in-force-yes" if in_force_status else "in-force-no",
        },
    )
    status_div.string = (
        f"Text in Kraft ({ordnungsnummer}-{current_nachtragsnummer})"
        if in_force_status
        else f"Text nicht in Kraft ({ordnungsnummer}-{current_nachtragsnummer})"
    )

    details: Tag = soup.new_tag(
        "details",
        **{
            "id": "doc-info",
        },
    )
    summary: Tag = soup.new_tag("summary")
    summary.string = "Basisinformationen"
    details.append(summary)
    metadata_content: Tag = soup.new_tag("div", **{"class": "metadata-content"})

    metadata_fields = [
        ("erlasstitel", "Titel"),
        ("kurztitel", "Kurztitel"),
        ("abkuerzung", "Abkürzung"),
        ("ordnungsnummer", "Ordnungsnummer"),
        ("nachtragsnummer", "Nachtragsnummer"),
        ("erlassdatum", "Erlassdatum"),
        ("inkraftsetzungsdatum", "Inkraftsetzungsdatum"),
        ("publikationsdatum", "Publikationsdatum"),
        ("aufhebungsdatum", "Aufhebungsdatum"),
        # Removed "in_force" entry as it's now handled via meta tags in the head
    ]

    for key, label in metadata_fields:
        item_div: Tag = soup.new_tag("div", **{"class": "metadata-item"})
        label_div: Tag = soup.new_tag("div", **{"class": "metadata-label"})
        label_div.string = f"{label}:"
        value_div: Tag = soup.new_tag("div", **{"class": "metadata-value"})
        value: Any = doc_info.get(key)
        if not value:
            value = "N/A"
        if key in [
            "erlassdatum",
            "inkraftsetzungsdatum",
            "publikationsdatum",
            "aufhebungsdatum",
        ]:
            value = format_date(value) if value != "N/A" else "N/A"
            value_div.string = value
        elif key == "erlasstitel":
            value_div.string = value
            value_div.attrs["data-pagefind-weight"] = "10"
        elif key == "kurztitel":
            value_div.string = value
        elif key == "abkuerzung":
            value_div.string = value
            value_div.attrs["data-pagefind-weight"] = "10"
        elif key == "ordnungsnummer":
            value_div.string = value
            value_div.attrs["data-pagefind-meta"] = "Ordnungsnummer"
        elif key == "nachtragsnummer":
            value_div.string = value
            value_div.attrs["data-pagefind-meta"] = "Nachtragsnummer"
        else:
            value_div.string = str(value)
        item_div.append(label_div)
        item_div.append(value_div)
        # Always add a separator after each metadata item
        separator: Tag = soup.new_tag("div", **{"class": "metadata-separator"})
        item_div.append(separator)
        metadata_content.append(item_div)

    law_origin_div: Tag = soup.new_tag("div", **{"class": "metadata-item"})
    law_origin_label: Tag = soup.new_tag("div", **{"class": "metadata-label"})
    law_origin_label.string = "Gesetzessammlung:"
    law_origin_value: Tag = soup.new_tag("div", **{"class": "metadata-value"})
    if law_origin:
        law_origin_value.string = "Kanton Zürich" if law_origin == "zh" else "Bund"
        law_origin_value.attrs["data-pagefind-meta"] = "Gesetzessammlung"
        law_origin_value.attrs["data-pagefind-filter"] = "Gesetzessammlung"
    else:
        law_origin_value.string = "N/A"
    law_origin_div.append(law_origin_label)
    law_origin_div.append(law_origin_value)
    separator = soup.new_tag("div", **{"class": "metadata-separator"})
    law_origin_div.append(separator)
    metadata_content.append(law_origin_div)

    versions_container: Tag = soup.new_tag(
        "div", **{"class": "metadata-item versions-container"}
    )
    versions_label: Tag = soup.new_tag("div", **{"class": "metadata-label"})
    versions_label.string = "Versionen:"
    versions_container.append(versions_label)
    versions_value: Tag = soup.new_tag(
        "div", **{"class": "metadata-value versions-value"}
    )
    versions_container.append(versions_value)
    metadata_content.append(versions_container)

    details.append(metadata_content)
    sidebar: Union[Tag, None] = soup.find("div", id="sidebar")
    if sidebar:
        sidebar.insert(0, details)
        sidebar.insert(1, status_div)
    return soup


def insert_versions_and_update_navigation(
    soup: BeautifulSoup,
    versions: Any,
    ordnungsnummer: str,
    current_nachtragsnummer: str,
) -> Tuple[BeautifulSoup, List[Dict[str, Any]]]:
    """
    Updates version information in the 'Versionen' display and navigation buttons.
    Returns the modified soup and the sorted list of all versions.
    """
    if "older_versions" in versions:
        all_versions: List[Dict[str, Any]] = versions.get(
            "older_versions", []
        ) + versions.get("newer_versions", [])
        all_versions.append(
            {"nachtragsnummer": current_nachtragsnummer, "current": True}
        )
    else:
        all_versions = versions
        for version in all_versions:
            if version["nachtragsnummer"] == current_nachtragsnummer:
                version["current"] = True

    all_versions = sorted(
        all_versions, key=lambda x: alphanum_key(x["nachtragsnummer"])
    )
    versions_value: Union[Tag, None] = soup.find("div", {"class": "versions-value"})
    if versions_value:
        for version in all_versions:
            if version.get("current", False):
                span = soup.new_tag("span", **{"class": "version-current"})
            else:
                span = soup.new_tag(
                    "a",
                    href=f"{ordnungsnummer}-{version['nachtragsnummer']}.html",
                    **{"class": "version-link"},
                )
            span.string = version["nachtragsnummer"]
            versions_value.append(span)
            if version != all_versions[-1]:
                separator = soup.new_tag("span", **{"class": "version-separator"})
                separator.string = "∗"
                versions_value.append(separator)
    prev_ver, next_ver, new_ver = None, None, None
    current_index = next(
        (i for i, v in enumerate(all_versions) if v.get("current", False)), None
    )
    if current_index is not None:
        if current_index > 0:
            prev_ver = all_versions[current_index - 1]["nachtragsnummer"]
        if current_index + 1 < len(all_versions):
            next_ver = all_versions[current_index + 1]["nachtragsnummer"]
        if all_versions[-1]["nachtragsnummer"] != current_nachtragsnummer:
            new_ver = all_versions[-1]["nachtragsnummer"]
    if prev_ver:
        soup.find("button", id="prev_ver")["onclick"] = (
            f"location.href='{ordnungsnummer}-{prev_ver}.html';"
        )
    else:
        button = soup.find("button", id="prev_ver")
        if button:
            button["disabled"] = True
    if next_ver:
        soup.find("button", id="next_ver")["onclick"] = (
            f"location.href='{ordnungsnummer}-{next_ver}.html';"
        )
    else:
        button = soup.find("button", id="next_ver")
        if button:
            button["disabled"] = True
    if new_ver:
        soup.find("button", id="new_ver")["onclick"] = (
            f"location.href='{ordnungsnummer}-{new_ver}.html';"
        )
    else:
        button = soup.find("button", id="new_ver")
        if button:
            button["disabled"] = True
    return soup, all_versions


# -----------------------------------------------------------------------------
# Enumeration and Subprovision Processing
# -----------------------------------------------------------------------------
def process_enum_elements(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Processes enumerated paragraphs to separate list numbers from content.
    Handles both letter and number enumerations while preserving HTML tags.
    """
    enum_paragraphs: List[Tag] = soup.find_all(
        "p",
        class_=lambda x: x and any(cls in x for cls in ENUM_CLASSES),
    )
    for p in enum_paragraphs:
        first_text = None
        for content in p.contents:
            if isinstance(content, str) and content.strip():
                first_text = content
                break
        if first_text:
            match = re.match(r"^((?:[a-zA-Z0-9]+\.)|(?:– ))", first_text)
            if match:
                number = match.group(1)
                new_text = first_text[len(number) :].lstrip()
                if new_text:
                    first_text.replace_with(new_text)
                else:
                    first_text.extract()
                number_span: Tag = soup.new_tag("span", **{"class": "enum-enumerator"})
                number_span.string = number
                content_span: Tag = soup.new_tag("span", **{"class": "enum-content"})
                while p.contents:
                    content_span.append(p.contents[0])
                p.append(number_span)
                p.append(content_span)
    return soup


def consolidate_enum_paragraphs(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Consolidates paragraphs that belong to enumerations (enum-lit or enum-ziff).
    Merges subsequent paragraphs without a class into the content of the current enumeration,
    but stops merging if there is any heading element (<h1> through <h6>) between them.
    """
    soup = process_enum_elements(soup)
    paragraphs: List[Tag] = soup.find_all("p")
    i = 0
    while i < len(paragraphs) - 1:
        current = paragraphs[i]
        # Check if the current paragraph is an enumeration paragraph (either enum-lit or enum-ziff)
        if current.get("class") and any(
            c in current.get("class") for c in ["enum-lit", "enum-ziff"]
        ):
            next_idx = i + 1
            while next_idx < len(paragraphs):
                next_p = paragraphs[next_idx]
                # Check for any heading element between the current enumeration paragraph and the next paragraph.
                barrier_found = False
                next_element = current.find_next()
                while next_element is not None and next_element != next_p:
                    if next_element.name in {
                        "h1",
                        "h2",
                        "h3",
                        "h4",
                        "h5",
                        "h6",
                        "table",
                    }:
                        barrier_found = True
                        break
                    next_element = next_element.find_next()
                # If a heading is found between, stop merging further paragraphs.
                if barrier_found:
                    break

                # Stop merging if the next paragraph has a class attribute.
                if next_p.get("class"):
                    break

                # Find the span that holds the enumeration content.
                content_span = current.find("span", class_="enum-content")
                if content_span and len(content_span.contents) > 0:
                    # Append a space if the span already has content.
                    content_span.append(" ")
                # Move all child elements from the next paragraph to the content span.
                while next_p.contents:
                    content_span.append(next_p.contents[0])
                # Remove the now empty paragraph from the DOM.
                next_p.decompose()
                next_idx += 1
            # Update the index to the next unmerged paragraph.
            i = next_idx
            continue
        i += 1
    return soup


def wrap_subprovisions(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Wraps subprovisions and their corresponding paragraphs in container divs.
    Handles multi-paragraph subprovisions by grouping consecutive paragraphs without certain classes.
    Excludes content from within annex sections to prevent incorrect merging.
    Stops merging when encountering headings (h1-h6) or another subprovision.
    """
    # Get all paragraphs except those with id="annex-info" and those inside the annex section
    paragraphs: List[Tag] = [
        p
        for p in soup.find_all("p")
        if p.get("id") != "annex-info" and not p.find_parent("details", id="annex")
    ]

    # First pass: Identify subprovisions and group them with related paragraphs
    i = 0
    while i < len(paragraphs) - 1:
        current = paragraphs[i]
        # Check if current paragraph is a subprovision
        if current.get("class") and "subprovision" in current.get("class"):
            # Create a new container div for this subprovision group
            container = soup.new_tag("div", **{"class": "subprovision-container"})
            # Insert the container before the current paragraph in the DOM
            current.insert_before(container)
            # Move the subprovision paragraph into the container
            container.append(current)

            # Look ahead to find paragraphs that belong to this subprovision
            next_idx = i + 1
            while next_idx < len(paragraphs):
                next_p = paragraphs[next_idx]

                # Skip if the next paragraph is inside the annex section
                if next_p.find_parent("details", id="annex"):
                    next_idx += 1
                    continue

                # Stop if we encounter another subprovision or enumeration
                if next_p.get("class") and (
                    "subprovision" in next_p.get("class")
                    or "enum-lit" in next_p.get("class")
                    or "enum-ziff" in next_p.get("class")
                ):
                    break

                # Stop if we encounter a provision or marginalia
                if next_p.get("class") and (
                    "provision" in next_p.get("class")
                    or "marginalia" in next_p.get("class")
                ):
                    break

                # Check for any heading element between the current container and the next paragraph
                # This is critical for proper section handling
                next_element = container.find_next()
                while next_element and next_element != next_p:
                    if next_element.name in {
                        "h1",
                        "h2",
                        "h3",
                        "h4",
                        "h5",
                        "h6",
                        "table",
                    }:
                        # Found a heading - stop including paragraphs in this container
                        next_p = None
                        break
                    next_element = next_element.find_next()

                # If we found a heading, exit the loop
                if next_p is None:
                    break

                # Include paragraphs without classes (content paragraphs)
                if not next_p.get("class"):
                    container.append(next_p)
                    next_idx += 1
                    continue

                # If we reach here, we've found a paragraph that doesn't belong
                break

            # Update index to continue from next unprocessed paragraph
            i = next_idx
            continue

        # Move to next paragraph if current is not a subprovision
        i += 1

    # Second pass: Only merge paragraphs within the same container
    # This avoids merging content across headings/sections
    for container in soup.find_all("div", class_="subprovision-container"):
        paragraphs_in_container = container.find_all("p")

        # If container has more than 2 paragraphs (subprovision + content paragraphs)
        if len(paragraphs_in_container) > 2:
            # First content paragraph (index 1) will contain all merged content
            first_content_p = paragraphs_in_container[1]

            # Merge all subsequent paragraphs into the first content paragraph
            for p in paragraphs_in_container[2:]:
                # Skip any paragraphs that are inside the annex section
                if p.find_parent("details", id="annex"):
                    continue

                # Add space between merged paragraph contents
                if len(first_content_p.contents) > 0:
                    first_content_p.append(" ")

                # Move all contents from current paragraph to first content paragraph
                while p.contents:
                    first_content_p.append(p.contents[0])

                # Remove the now-empty paragraph from the DOM
                p.decompose()

    # Return the modified BeautifulSoup object
    return soup


def merge_paragraphs_with_footnote_refs(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Merges consecutive paragraphs where the first contains a footnote reference
    and the second starts with lowercase letter or punctuation.

    Requirements:
    - Elements must be directly consecutive siblings
    - Elements must be the same tag with identical classes (except "first-level" or "second-level")
    - First element must contain a sup.footnote-ref tag
    - Second element must start with lowercase letter or punctuation
    """
    # Define excluded classes and punctuation characters
    excluded_classes = ["first-level", "second-level"]
    punctuation_chars = ".,;:?!()[]{}"

    # Process multiple passes until no more changes
    changes_made = True
    while changes_made:
        changes_made = False

        # Get fresh list of elements
        elements = soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6"])

        for i in range(len(elements) - 1):
            current_elem = elements[i]
            next_elem = elements[i + 1]

            # Must be direct siblings
            if next_elem != current_elem.find_next_sibling():
                continue

            # Check for excluded classes
            current_classes = current_elem.get("class", [])
            next_classes = next_elem.get("class", [])

            if any(cls in excluded_classes for cls in current_classes) or any(
                cls in excluded_classes for cls in next_classes
            ):
                continue

            # Must be same tag type
            if current_elem.name != next_elem.name:
                continue

            # Must have identical classes
            if set(current_classes) != set(next_classes):
                continue

            # First element must contain a footnote reference
            footnote_ref = current_elem.find("sup", class_="footnote-ref")
            if not footnote_ref:
                continue

            # Second element must start with lowercase or punctuation
            next_text = next_elem.get_text().strip()
            if not next_text:
                continue

            if not (next_text[0].islower() or next_text[0] in punctuation_chars):
                continue

            # All conditions met - merge the elements
            current_elem.append(" ")
            while next_elem.contents:
                current_elem.append(next_elem.contents[0])
            next_elem.decompose()

            changes_made = True
            break

    return soup


def create_links_display(
    soup: BeautifulSoup, current_url: str, dynamic_url: str, law_page_url: str = ""
) -> Tag:
    """
    Creates a display of static, dynamic, and source URLs for copying.

    Args:
        soup: BeautifulSoup object for creating new tags
        current_url: URL to the current version (static link)
        dynamic_url: URL to the latest version (dynamic link)
        law_page_url: URL to the source document on ZHLex (if available)

    Returns:
        Tag: A div containing all link displays
    """
    # Create container for all links
    links_container: Tag = soup.new_tag("div", **{"class": "links-container"})

    # Create the container with border that contains all links
    links_inner: Tag = soup.new_tag("div", **{"class": "links-inner"})
    links_container.append(links_inner)

    # Static Link Group
    static_group: Tag = soup.new_tag("div", **{"class": "link-group"})
    links_inner.append(static_group)

    # Static Link Title
    static_title: Tag = soup.new_tag("div", **{"class": "link-title"})
    static_title.string = "Zu dieser Version:"
    static_group.append(static_title)

    # Static Link URL
    static_url: Tag = soup.new_tag("div", **{"class": "link-url"})
    static_url.string = f"https://www.zhlaw.ch{current_url}"
    static_group.append(static_url)

    # Add separator
    separator: Tag = soup.new_tag("hr", **{"class": "links-separator"})
    links_inner.append(separator)

    # Dynamic Link Group
    dynamic_group: Tag = soup.new_tag("div", **{"class": "link-group"})
    links_inner.append(dynamic_group)

    # Dynamic Link Title
    dynamic_title: Tag = soup.new_tag("div", **{"class": "link-title"})
    dynamic_title.string = "Immer zur neusten Version:"
    dynamic_group.append(dynamic_title)

    # Dynamic Link URL
    dynamic_url_tag: Tag = soup.new_tag("div", **{"class": "link-url"})
    dynamic_url_tag.string = dynamic_url
    dynamic_group.append(dynamic_url_tag)

    # Add source link if available
    if law_page_url:
        # Add separator
        separator2: Tag = soup.new_tag("hr", **{"class": "links-separator"})
        links_inner.append(separator2)

        # Source Link Group
        source_group: Tag = soup.new_tag("div", **{"class": "link-group"})
        links_inner.append(source_group)

        # Source Link Title with a hyperlink
        source_title: Tag = soup.new_tag("div", **{"class": "link-title"})
        source_link: Tag = soup.new_tag("a", href=law_page_url, target="_blank")
        source_link.string = "Quelle auf ZHLex"
        source_title.append(source_link)
        source_group.append(source_title)

    return links_container


# -----------------------------------------------------------------------------
# Main Processing Function
# -----------------------------------------------------------------------------
def main(
    soup: BeautifulSoup,
    html_file: str,
    doc_info: Dict[str, Any],
    type_str: str,
    law_origin: str,
) -> BeautifulSoup:
    """
    Processes the HTML soup.
    If type_str is not "site_element", performs document-specific processing.
    Always inserts header and footer.
    Only adds data-pagefind-body to the newest version.
    """
    if type_str != "site_element":
        erlasstitel: str = doc_info.get("erlasstitel", "")
        ordnungsnummer: str = doc_info.get("ordnungsnummer", "")
        current_nachtragsnummer: str = doc_info.get("nachtragsnummer", "")
        in_force_status: bool = doc_info.get("in_force", False)
        versions: Any = doc_info.get("versions", {})
        dynamic_url: str = doc_info.get("zhlaw_url_dynamic", "")
        law_page_url: str = doc_info.get("law_page_url", "")

        soup = consolidate_enum_paragraphs(soup)
        soup = wrap_subprovisions(soup)
        soup = merge_paragraphs_with_footnote_refs(soup)
        soup = modify_html(soup, erlasstitel)
        soup = insert_combined_table(
            soup,
            doc_info,
            in_force_status,
            ordnungsnummer,
            current_nachtragsnummer,
            law_origin,
        )
        sidebar: Union[Tag, None] = soup.find("div", id="sidebar")
        if sidebar:
            # Create the current URL (static link) for this version
            current_url = f"/col-zh/{ordnungsnummer}-{current_nachtragsnummer}.html"

            # Create the links display with both static, dynamic, and source URLs
            links_display = create_links_display(
                soup, current_url, dynamic_url, law_page_url
            )

            # Create nav buttons
            nav_div: Tag = create_nav_buttons(soup)

            # Add the status message, links display, and nav buttons to version_container
            version_container: Tag = soup.new_tag("div", id="version-container")
            status_div: Union[Tag, None] = soup.find("div", id="status-message")
            if status_div:
                status_div.extract()
            version_container.append(status_div)
            version_container.append(links_display)  # Links display
            version_container.append(nav_div)  # Then nav buttons
            sidebar.insert(1, version_container)

            soup, all_versions = insert_versions_and_update_navigation(
                soup, versions, ordnungsnummer, current_nachtragsnummer
            )

        # Check if this version is the newest
        is_newest = False
        if all_versions:
            newest_nachtragsnummer: str = all_versions[-1]["nachtragsnummer"]
            is_newest = newest_nachtragsnummer == current_nachtragsnummer
        else:
            is_newest = True

        # Apply attributes based on version status
        law_div: Union[Tag, None] = soup.find("div", id="law")
        if law_div and is_newest:
            # Only add data-pagefind-body to newest version
            law_div["data-pagefind-body"] = None
            # No filter for "Versionen" is needed anymore

        annex: Union[Tag, None] = soup.find("details", id="annex")
        if annex:
            annex_info: Tag = soup.new_tag("div", id="annex-info")
            law_page_url: Any = doc_info.get("law_page_url")
            if law_page_url:
                annex_info.clear()
                annex_info.append(
                    "Achtung: Anhänge weisen oft Konvertierungsfehler auf. Bitte überpürfe die "
                )
                link: Tag = soup.new_tag("a", href=law_page_url, target="_blank")
                link.string = "Originalquelle"
                annex_info.append(link)
                annex_info.append(".")
            else:
                annex_info.string = "Achtung: Anhänge weisen oft Konvertierungsfehler auf. Bitte überpürfe die Originalquelle."
            annex.insert(0, annex_info)

    soup = insert_header(soup)
    soup = insert_footer(soup)
    return soup


if __name__ == "__main__":
    # This module is intended to be imported by another script.
    # For testing, you can create a BeautifulSoup object and call main() accordingly.
    pass
