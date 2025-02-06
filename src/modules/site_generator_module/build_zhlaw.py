from bs4 import BeautifulSoup
import logging
import arrow
import re

# Get logger from main module
logger = logging.getLogger(__name__)


def create_nav_buttons(soup):
    """
    Creates navigation buttons with separated symbols and text.
    """
    # Create a new div to hold the buttons
    nav_div = soup.new_tag("div", **{"class": "nav-buttons"})

    # Define button configurations
    buttons = [
        {"symbol": "⇽", "text": "vorherige Version", "id": "prev_ver"},
        {"symbol": "⇾", "text": "nächste Version", "id": "next_ver"},
        {"symbol": "⇥", "text": "neuste Version", "id": "new_ver"},
    ]

    # Create buttons
    for button_config in buttons:
        # Create button container
        button = soup.new_tag(
            "button",
            **{
                "class": "nav-button",
                "id": button_config["id"],
                "onclick": "location.href='#';",
            },
        )

        # Add symbol
        symbol = soup.new_tag("span", **{"class": "nav-symbol"})
        symbol.string = button_config["symbol"]
        button.append(symbol)

        # Add text
        text = soup.new_tag("span", **{"class": "nav-text"})
        text.string = button_config["text"]
        button.append(text)

        nav_div.append(button)

    return nav_div


def alphanum_key(s):
    """Turn a string into a list of string and number chunks.
    "z23a" -> ["z", 23, "a"]
    """
    return [
        int(text) if text.isdigit() else text.lower()
        for text in re.split("([0-9]+)", s)
    ]


def insert_header(soup):
    """
    Inserts a header with logo on the left and a search bar on the right,
    wrapped in a search-container. Pagefind UI assets go to <head>.
    """
    # Create the main header container
    header = soup.new_tag("div", **{"id": "page-header"})

    # Create the flex container for logo & search
    header_content = soup.new_tag("div", **{"class": "header-content"})
    header.append(header_content)

    # -- Add logo container --
    logo_container = soup.new_tag("div", **{"class": "logo-container"})
    logo_link = soup.new_tag("a", href="/")
    logo_img = soup.new_tag(
        "img",
        src="/logo-zhlaw.svg",
        alt="zhlaw.ch Logo",
        **{"class": "header-logo"},
    )
    logo_link.append(logo_img)
    logo_container.append(logo_link)
    header_content.append(logo_container)

    # -- Add search-container --
    search_container = soup.new_tag("div", **{"class": "search-container"})
    search_div = soup.new_tag("div", id="search")
    search_container.append(search_div)
    header_content.append(search_container)

    # Insert the Pagefind UI references into <head> (if not already present)
    head = soup.find("head")
    if head:
        # Add Pagefind CSS
        css_link = soup.new_tag(
            "link", href="/pagefind/pagefind-ui.css", rel="stylesheet"
        )
        head.append(css_link)

        # Add Pagefind JS
        script_tag = soup.new_tag("script", src="/pagefind/pagefind-ui.js")
        head.append(script_tag)

    # Create script for Pagefind initialization (in body)
    search_script = soup.new_tag("script")
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
                autofocus: true,
                showImages: false
            });
        });
    """
    header.append(search_script)

    # Finally place header at the top within body
    body = soup.find("body")
    if body:
        body.insert(0, header)

    return soup


def modify_html(soup, erlasstitel):
    # Ensure the head exists
    head = soup.head
    if head is None:
        head = soup.new_tag("head")
        soup.html.insert(0, head)

    # Add the CSS stylesheet link
    css_link = soup.new_tag("link", rel="stylesheet", href="../styles.css")
    head.append(css_link)

    # Add favicon links
    shortcut_icon = soup.new_tag(
        "link", rel="shortcut icon", href="../favicon.ico", type="image/x-icon"
    )
    head.append(shortcut_icon)

    favicon = soup.new_tag(
        "link", rel="icon", href="../favicon.ico", type="image/x-icon"
    )
    head.append(favicon)

    # Add title
    title_tag = soup.new_tag("title")
    title_tag.string = erlasstitel
    head.append(title_tag)

    # Add viewport meta tag
    viewport_meta = soup.new_tag(
        "meta",
        attrs={"name": "viewport", "content": "width=device-width, initial-scale=1"},
    )
    head.append(viewport_meta)

    # Add encoding meta tag
    encoding_meta = soup.new_tag("meta", charset="utf-8")
    head.append(encoding_meta)

    # Modify the body structure
    body = soup.body
    if body:
        # Create main container for layout
        main_container = soup.new_tag("div", **{"class": "main-container"})

        # Create sidebar container with id instead of class
        sidebar = soup.new_tag("div", id="sidebar")

        # Create content container
        content = soup.new_tag("div", **{"class": "content"})

        # Create law container
        law_div = soup.new_tag("div", **{"id": "law", "data-pagefind-body": None})

        # Move existing body contents to law_div
        while body.contents:
            law_div.append(body.contents[0])

        # Append containers in proper hierarchy
        content.append(law_div)
        main_container.append(sidebar)
        main_container.append(content)
        body.append(main_container)

    return soup


def format_date(date_str):
    """
    Formats a date string from YYYYMMDD to DD.MM.YYYY.
    """
    try:
        return arrow.get(date_str, "YYYYMMDD").format("DD.MM.YYYY")
    except Exception as e:
        logger.warning(f"Error formatting date {date_str}: {e} -> Returning N/A")
        return "N/A"


def insert_combined_table(
    soup,
    doc_info,
    in_force_status,
    ordnungsnummer,
    current_nachtragsnummer,
    law_origin,
):
    """
    Inserts metadata with vertical layout and status information.
    """
    status_div = soup.new_tag(
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

    # Create collapsible container for detailed information with sticky positioning
    details = soup.new_tag(
        "details",
        **{
            "id": "doc-info",
            "style": "position:sticky; top:0; background:white; z-index:10;",
        },
    )
    summary = soup.new_tag("summary")
    summary.string = "Basisinformationen"
    details.append(summary)

    # Create metadata content container
    metadata_content = soup.new_tag("div", **{"class": "metadata-content"})

    # Define metadata fields and their labels
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
        ("in_force", "In Kraft"),
        ("law_page_url", "Quelle"),
    ]

    for key, label in metadata_fields:
        # Create item container
        item_div = soup.new_tag("div", **{"class": "metadata-item"})

        # Create label
        label_div = soup.new_tag("div", **{"class": "metadata-label"})
        label_div.string = f"{label}:"

        # Create value
        value_div = soup.new_tag("div", **{"class": "metadata-value"})
        value = doc_info.get(key)
        if not value:
            value = "N/A"

        # Handle different types of metadata
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
            value_div.attrs["data-pagefind-meta"] = "title"
            value_div.attrs["data-pagefind-weight"] = "10"
        elif key == "kurztitel":
            value_div.string = value
            value_div.attrs["data-pagefind-meta"] = "Kurztitel"
        elif key == "abkuerzung":
            value_div.string = value
            value_div.attrs["data-pagefind-meta"] = "Abkürzung"
            value_div.attrs["data-pagefind-weight"] = "10"
        elif key == "ordnungsnummer":
            value_div.string = value
            value_div.attrs["data-pagefind-meta"] = "Ordnungsnummer"
        elif key == "nachtragsnummer":
            value_div.string = value
            value_div.attrs["data-pagefind-meta"] = "Nachtragsnummer"
        elif key == "law_page_url":
            if value != "N/A":
                link = soup.new_tag("a", href=value, target="_blank")
                link.string = "Link"
                value_div.append(link)
            else:
                value_div.string = value
        elif key == "in_force":
            value_div.string = "Ja" if value == True else "Nein"
            value_div.attrs["data-pagefind-meta"] = "Text in Kraft"
            value_div.attrs["data-pagefind-filter"] = "Text in Kraft"
        elif law_origin:
            value.div.string = "ZH" if law_origin == "zh" else "CH"
            value.div.attrs["data-pagefind-meta"] = "Gesetzessammlung"
            value.div.attrs["data-pagefind-filter"] = "Gesetzessammlung"
        else:
            value_div.string = str(value)

        # Append label and value to item container
        item_div.append(label_div)
        item_div.append(value_div)

        # Add separator if not the last item
        if key != metadata_fields[-1][0]:
            separator = soup.new_tag("div", **{"class": "metadata-separator"})
            item_div.append(separator)

        # Add item to metadata content
        metadata_content.append(item_div)

    # Create versions section
    versions_container = soup.new_tag(
        "div", **{"class": "metadata-item versions-container"}
    )
    versions_label = soup.new_tag("div", **{"class": "metadata-label"})
    versions_label.string = "Versionen:"
    versions_container.append(versions_label)

    # Add versions container to save space for later
    versions_value = soup.new_tag("div", **{"class": "metadata-value versions-value"})
    versions_container.append(versions_value)
    metadata_content.append(versions_container)

    # Append metadata content to details
    details.append(metadata_content)

    # Find the sidebar and insert the details and status message
    sidebar = soup.find("div", id="sidebar")
    if sidebar:
        sidebar.insert(0, details)
        sidebar.insert(1, status_div)

    return soup


def insert_versions_and_update_navigation(
    soup, versions, ordnungsnummer, current_nachtragsnummer
):
    """
    Updates version information and navigation buttons.
    """
    # Check if key "older_versions" or "newer_versions" exists in versions
    if "older_versions" in versions:
        all_versions = versions.get("older_versions", []) + versions.get(
            "newer_versions", []
        )
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

    # Find the versions value container
    versions_value = soup.find("div", {"class": "versions-value"})
    if versions_value:
        for version in all_versions:
            if "current" in version:
                span = soup.new_tag("span", **{"class": "version-current"})
            else:
                span = soup.new_tag(
                    "a",
                    href=f"{ordnungsnummer}-{version['nachtragsnummer']}.html",
                    **{"class": "version-link"},
                )
            span.string = version["nachtragsnummer"]
            versions_value.append(span)

            # Add separator between versions
            if version != all_versions[-1]:
                separator = soup.new_tag("span", **{"class": "version-separator"})
                separator.string = "∗"
                versions_value.append(separator)

    # Update navigation buttons
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

    # Update button links
    if prev_ver:
        soup.find("button", id="prev_ver")["onclick"] = (
            f"location.href='{ordnungsnummer}-{prev_ver}.html';"
        )
    else:
        button = soup.find("button", id="prev_ver")
        button["disabled"] = True

    if next_ver:
        soup.find("button", id="next_ver")["onclick"] = (
            f"location.href='{ordnungsnummer}-{next_ver}.html';"
        )
    else:
        button = soup.find("button", id="next_ver")
        button["disabled"] = True

    if new_ver:
        soup.find("button", id="new_ver")["onclick"] = (
            f"location.href='{ordnungsnummer}-{new_ver}.html';"
        )
    else:
        button = soup.find("button", id="new_ver")
        button["disabled"] = True

    return soup


def insert_footer(soup):
    """
    Inserts a footer with links including contact at the bottom of the HTML document.
    """
    footer = soup.new_tag("div", **{"id": "page-footer"})
    links_container = soup.new_tag("div", **{"class": "footer-links-container"})

    links = [
        ("Home", "/"),
        ("Über zhlaw.ch", "/about.html"),
        ("Datenschutz", "/privacy.html"),
        ("Ratsversand", "/dispatch.html"),
        ("Datensätze", "/data.html"),
        ("Kontakt", "mailto:admin@zhlaw.ch"),
    ]

    for i, (text, href) in enumerate(links):
        # Create link
        link = soup.new_tag("a", href=href, **{"class": "footer-links"})
        link.string = text
        links_container.append(link)

        # Add separator if not the last link
        if i < len(links) - 1:
            separator = soup.new_tag("span", **{"class": "footer-seperator"})
            separator.string = "∗"
            links_container.append(separator)

    # Add the links container to the footer
    footer.append(links_container)

    # Add disclaimer
    disclaimer = soup.new_tag("p", **{"id": "disclaimer"})
    disclaimer.string = "Keine amtliche Veröffentlichung. Massgebend ist die Veröffentlichung durch die Staatskanzlei ZH."
    footer.append(disclaimer)

    # Insert the footer
    body = soup.find("body")
    if body:
        body.append(footer)

    return soup


def process_enum_elements(soup):
    """
    Processes enumerated paragraphs to separate list numbers from content.
    Handles both letter (a., b., c.) and number (1., 2., 3.) enumerations.
    Preserves HTML tags, including footnote references in superscript.

    Args:
        soup: BeautifulSoup object containing the HTML

    Returns:
        BeautifulSoup object with processed enumeration elements
    """
    # Find all paragraphs with enum-lit or enum-ziff classes
    enum_paragraphs = soup.find_all(
        "p", class_=lambda x: x and ("enum-lit" in x or "enum-ziff" in x)
    )

    for p in enum_paragraphs:
        # Instead of get_text(), we'll work with the contents directly

        # Find the first text node that contains the enumeration number
        first_text = None
        for content in p.contents:
            if isinstance(content, str) and content.strip():
                first_text = content
                break

        if first_text:
            # Pattern for both letter and number enumerations
            match = re.match(r"^([a-zA-Z0-9]+\.)", first_text)

            if match:
                number = match.group(1)
                # Replace the matched text with empty string in the original node
                new_text = first_text[len(number) :].lstrip()
                if new_text:
                    first_text.replace_with(new_text)
                else:
                    first_text.extract()

                # Create number span
                number_span = soup.new_tag("span", **{"class": "enum-enumerator"})
                number_span.string = number

                # Create content span
                content_span = soup.new_tag("span", **{"class": "enum-content"})

                # Move all existing contents to the content span
                while p.contents:
                    content_span.append(p.contents[0])

                # Add both spans to the paragraph
                p.append(number_span)
                p.append(content_span)

    return soup


def consolidate_enum_paragraphs(soup):
    """
    Identifies and consolidates paragraphs that belong to enum-lit or enum-ziff elements.
    Now includes separation of list numbers from content while preserving HTML tags.
    """
    # First process the enumeration elements to separate numbers from content
    soup = process_enum_elements(soup)

    paragraphs = soup.find_all("p")

    i = 0
    while i < len(paragraphs) - 1:
        current = paragraphs[i]

        if current.get("class") and any(
            c in current.get("class") for c in ["enum-lit", "enum-ziff"]
        ):
            next_idx = i + 1

            while next_idx < len(paragraphs):
                next_p = paragraphs[next_idx]

                if next_p.get("class"):
                    break

                # Get the content span from current paragraph
                content_span = current.find("span", class_="enum-content")
                if content_span and len(content_span.contents) > 0:
                    content_span.append(" ")

                # Move all content from next_p to the content span
                while len(next_p.contents) > 0:
                    content_span.append(next_p.contents[0])

                next_p.decompose()
                next_idx += 1

            i = next_idx
            continue

        i += 1

    return soup


def wrap_subprovisions(soup):
    """
    Identifies and wraps subprovisions and their corresponding paragraphs in container divs.
    Handles multi-paragraph subprovisions by checking if subsequent paragraphs belong to the same subprovision.
    Preserves HTML structure including footnotes when consolidating paragraphs.
    """
    paragraphs = soup.find_all("p")

    i = 0
    while i < len(paragraphs) - 1:
        current = paragraphs[i]

        if current.get("class") and "subprovision" in current.get("class"):
            container = soup.new_tag("div", **{"class": "subprovision-container"})
            current.insert_before(container)
            container.append(current)

            next_idx = i + 1

            while next_idx < len(paragraphs):
                next_p = paragraphs[next_idx]

                if next_p.get("class") and (
                    "subprovision" in next_p.get("class")
                    or "enum-lit" in next_p.get("class")
                    or "enum-ziff" in next_p.get("class")
                ):
                    break

                if next_p.get("class") and (
                    "provision" in next_p.get("class")
                    or "marginalia" in next_p.get("class")
                ):
                    break

                if not next_p.get("class"):
                    container.append(next_p)
                    next_idx += 1
                    continue

                break

            i = next_idx
            continue

        i += 1

    for container in soup.find_all("div", class_="subprovision-container"):
        paragraphs = container.find_all("p")
        if len(paragraphs) > 2:
            first_content_p = paragraphs[1]

            for p in paragraphs[2:]:
                if len(first_content_p.contents) > 0:
                    first_content_p.append(" ")

                while len(p.contents) > 0:
                    first_content_p.append(p.contents[0])

                p.decompose()

    return soup


def main(soup, html_file, doc_info, type, law_origin):
    """
    Loads HTML content, applies transformations, and returns the modified soup.
    If law_origin is provided ("zh" or "ch"), we add a meta tag in <head> for Pagefind filtering.
    """

    if type != "site_element":
        erlasstitel = doc_info.get("erlasstitel")
        ordnungsnummer = doc_info.get("ordnungsnummer")
        current_nachtragsnummer = doc_info.get("nachtragsnummer")
        in_force_status = doc_info.get("in_force", False)
        versions = doc_info.get("versions", {})

        # First consolidate enum paragraphs
        soup = consolidate_enum_paragraphs(soup)

        # Then wrap subprovisions
        soup = wrap_subprovisions(soup)

        # Modify basic HTML structure first
        soup = modify_html(soup, erlasstitel)

        # Insert combined table (doc-info and status message) into sidebar
        soup = insert_combined_table(
            soup,
            doc_info,
            in_force_status,
            ordnungsnummer,
            current_nachtragsnummer,
            law_origin,
        )

        # Insert navigation buttons and status message into version-container
        sidebar = soup.find("div", id="sidebar")
        if sidebar:
            nav_div = create_nav_buttons(soup)
            version_container = soup.new_tag("div", id="version-container")
            status_div = soup.find("div", id="status-message")
            if status_div:
                status_div.extract()
            version_container.append(status_div)
            version_container.append(nav_div)
            sidebar.insert(1, version_container)

        soup = insert_versions_and_update_navigation(
            soup, versions, ordnungsnummer, current_nachtragsnummer
        )

    # Insert header and footer (always, unless it's a site element we want to skip—but we do it anyway for site pages)
    soup = insert_header(soup)
    soup = insert_footer(soup)

    return soup


if __name__ == "__main__":
    # This module is intended to be imported and used by another script.
    # If needed, you could place test code here.
    pass
