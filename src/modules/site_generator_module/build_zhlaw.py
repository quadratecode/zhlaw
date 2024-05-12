# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

from bs4 import BeautifulSoup
import logging
import arrow
import re

# Get logger from main module
logger = logging.getLogger(__name__)


def insert_nav_buttons(soup):
    # Create a new div to hold the buttons
    nav_div = soup.new_tag("div", **{"class": "nav-buttons"})

    # Create buttons and add them to the nav_div
    for label, id_tag in [
        ("< vorherige Version", "prev_ver"),
        ("nächste Version >", "next_ver"),
        ("neuste Version >>", "new_ver"),
    ]:
        button = soup.new_tag(
            "button",
            **{
                "class": "nav-button",
                "id": id_tag,
                "onclick": "location.href='#';",  # Placeholder for actual navigation logic
            },
        )
        button.string = label
        nav_div.append(button)  # Appends the button inside the nav_div

    # Find the content div and insert the nav_div at the top
    content_div = soup.find("div", {"id": "content"})
    if content_div:
        content_div.insert(0, nav_div)

    return soup


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
    Inserts a header with a logo placeholder and a mailto link button at the top of the HTML document,
    including a superscript version number next to the logo with a specific ID for further styling.

    Args:
        soup (BeautifulSoup): The BeautifulSoup object representing the HTML document.

    Returns:
        BeautifulSoup: The updated BeautifulSoup object with the header added.
    """
    # Create the header container
    header = soup.new_tag("div", **{"id": "page-header"})

    # Create the logo placeholder
    logo = soup.new_tag("div", **{"id": "logo"})
    logo_link = soup.new_tag("a", href="/")
    # Adding the 'ZHLaw' text and the 'alpha' in superscript with a specific ID for styling
    logo_text = soup.new_tag("span")
    logo_text.string = "ZHLaw"
    alpha_sup = soup.new_tag("sup", **{"id": "logo-add"})
    alpha_sup.string = "alpha"
    logo_text.append(alpha_sup)
    logo_link.append(logo_text)
    logo.append(logo_link)
    header.append(logo)

    # Create the mailto button
    mailto = soup.new_tag(
        "a",
        **{
            "id": "contact-button",
            "href": f"mailto:admin@zhlaw.ch",
        },
    )
    mailto.string = "Kontakt"
    header.append(mailto)

    # Insert the header at the top within
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

    # Wrap body content in divs
    body = soup.body
    if body:
        content_div = soup.new_tag("div", **{"id": "content"})

        # Move existing body contents to the innermost div
        while body.contents:
            content_div.append(body.contents[0])

        body.append(content_div)

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
    soup, doc_info, in_force_status, ordnungsnummer, current_nachtragsnummer
):
    """
    Inserts a table with navigation, status information, and a collapsible infobox
    at the top of the HTML document.

    Args:
        soup (BeautifulSoup): The BeautifulSoup object representing the HTML document.
        metadata (dict): Metadata information about the document including in-force status.

    Returns:
        BeautifulSoup: The updated BeautifulSoup object with the combined table added.
    """
    in_force_status_class = "in-force-yes" if in_force_status else "in-force-no"

    # Create the table
    info_table = soup.new_tag("table", **{"id": "info-table"})

    # Collapsible row for detailed information
    info_row = soup.new_tag("tr", id="info-row")
    info_cell = soup.new_tag("td", colspan="3")
    details = soup.new_tag("details", **{"id": "doc-info"})
    summary = soup.new_tag("summary")
    summary.string = "Basisinformationen"
    details.append(summary)

    metadata_table = soup.new_tag("table", **{"id": "metadata-table"})
    for key, label in [
        ("erlasstitel", "Titel"),
        ("ordnungsnummer", "Ordnungsnummer"),
        ("nachtragsnummer", "Nachtragsnummer"),
        ("erlassdatum", "Erlassdatum"),
        ("inkraftsetzungsdatum", "Inkraftsetzungsdatum"),
        ("publikationsdatum", "Publikationsdatum"),
        ("aufhebungsdatum", "Aufhebungsdatum"),
        ("in_force", "In Kraft"),
        ("law_page_url", "Quelle"),
    ]:
        tr = soup.new_tag("tr")
        td_key = soup.new_tag("td")
        td_key.string = f"{label}:"
        td_value = soup.new_tag("td")

        value = doc_info.get(key, "N/A")
        if key in [
            "erlassdatum",
            "inkraftsetzungsdatum",
            "publikationsdatum",
            "aufhebungsdatum",
        ]:
            value = format_date(value)  # Format the date
            td_value.string = value  # Assign formatted date to the td_value
        elif key == "erlasstitel":
            td_value.string = value
            td_value.attrs["data-pagefind-meta"] = "title"
            td_value.attrs["data-pagefind-weight"] = "10"
        elif key == "ordnungsnummer":
            td_value.string = value
            td_value.attrs["data-pagefind-meta"] = "Ordnungsnummer"
        elif key == "ordnungsnummer":
            td_value.string = value
            td_value.attrs["data-pagefind-meta"] = "Nachtragsnummer"
        elif key == "law_page_url":
            link = soup.new_tag("a", href=value, target="_blank")
            link.string = "Link"
            td_value.append(link)  # Append the link to td_value
        elif key == "in_force":
            td_value.string = "Ja" if value == True else "Nein"
            td_value.attrs["data-pagefind-meta"] = "Text in Kraft"
            td_value.attrs["data-pagefind-filter"] = "Text in Kraft"
        else:
            td_value.string = value

        tr.append(td_key)
        tr.append(td_value)
        metadata_table.append(tr)

    details.append(metadata_table)
    info_cell.append(details)
    info_row.append(info_cell)
    info_table.append(info_row)

    # Row for in-force status message
    status_row = soup.new_tag("tr", id="status-row")
    status_message = soup.new_tag(
        "td",
        colspan="3",
        **{
            "class": in_force_status_class,
        },
    )
    status_message.string = (
        f"Text in Kraft ({ordnungsnummer}-{current_nachtragsnummer})"
        if in_force_status
        else f"Text nicht in Kraft ({ordnungsnummer}-{current_nachtragsnummer})"
    )
    status_row.append(status_message)
    info_table.append(status_row)

    # Insert the table at the top of the body
    law_div = soup.find("div", {"id": "law"})
    if law_div:
        law_div.insert(0, info_table)

    return soup


def insert_versions_and_update_navigation(
    soup, versions, ordnungsnummer, current_nachtragsnummer
):

    # Check if key "older_versions" or "newer_versions" exists in versions
    if "older_versions" in versions:
        # Combine older and newer versions, and sort them
        all_versions = versions.get("older_versions", []) + versions.get(
            "newer_versions", []
        )
        all_versions.append(
            {
                "nachtragsnummer": current_nachtragsnummer,  # Add the current version for complete list
                "current": True,  # Mark the current version
            }
        )
    else:
        all_versions = versions
        # Mark the current version
        for version in all_versions:
            if version["nachtragsnummer"] == current_nachtragsnummer:
                version["current"] = True

    all_versions = sorted(
        all_versions, key=lambda x: alphanum_key(x["nachtragsnummer"])
    )

    # Generate HTML for versions list row
    versions_list_row = soup.new_tag("tr")

    # Create the first cell for the label "Versionen:"
    label_cell = soup.new_tag("td")
    label_cell.string = "Versionen:"
    versions_list_row.append(label_cell)

    # Create the second cell for the versions list
    versions_cell = soup.new_tag(
        "td", colspan="2"
    )  # Adjust colspan as necessary based on your table design
    for version in all_versions:
        if "current" in version:
            span = soup.new_tag(
                "span", style="color: red;"
            )  # Highlight current version
        else:
            span = soup.new_tag(
                "a",
                href=f"{ordnungsnummer}-{version['nachtragsnummer']}.html",
            )
        span.string = version["nachtragsnummer"]
        versions_cell.append(span)
        # Add a separator between versions
        if version != all_versions[-1]:
            separator = soup.new_tag("span")
            separator.string = " | "
            versions_cell.append(separator)

    versions_list_row.append(versions_cell)

    # Find the info table and insert the versions list row
    metadata_table = soup.find("table", id="metadata-table")
    metadata_table.append(versions_list_row)

    # Update navigation buttons based on versions
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

    # Set links for the buttons
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
    Inserts a footer with two links ('About' and 'Imprint') at the bottom of the HTML document.

    Args:
        soup (BeautifulSoup): The BeautifulSoup object representing the HTML document.

    Returns:
        BeautifulSoup: The updated BeautifulSoup object with the footer added.
    """
    # Create the footer container
    footer = soup.new_tag("div", **{"id": "page-footer"})

    # Container for the links to keep them next to each other
    links_container = soup.new_tag("div", **{"class": "footer-links-container"})

    # Create the 'About' link with class 'footer-links'
    about_link = soup.new_tag("a", href="/about.html", **{"class": "footer-links"})
    about_link.string = "Über zhlaw.ch"
    links_container.append(about_link)

    # Create some space between links (optional, can be handled via CSS)
    links_container.append(soup.new_string("|"))

    # Create the 'Imprint' link with class 'footer-links'
    privacy_link = soup.new_tag("a", href="/privacy.html", **{"class": "footer-links"})
    privacy_link.string = "Datenschutz"
    links_container.append(privacy_link)

    # Create some space between links (optional, can be handled via CSS)
    links_container.append(soup.new_string("|"))

    # Create the 'Imprint' link with class 'footer-links'
    dispatch_link = soup.new_tag(
        "a", href="/dispatch.html", **{"class": "footer-links"}
    )
    dispatch_link.string = "Ratsversand"
    links_container.append(dispatch_link)

    # Create some space between links (optional, can be handled via CSS)
    links_container.append(soup.new_string("|"))

    # Create the 'Imprint' link with class 'footer-links'
    dispatch_link = soup.new_tag("a", href="/data.html", **{"class": "footer-links"})
    dispatch_link.string = "Datensätze"
    links_container.append(dispatch_link)

    # Add the links container to the footer
    footer.append(links_container)

    # Add a disclaimer below the links
    disclaimer = soup.new_tag("p", **{"id": "disclaimer"})
    disclaimer.string = "Keine amtliche Veröffentlichung. Massgebend ist die Veröffentlichung durch die Staatskanzlei ZH."
    footer.append(disclaimer)

    # Insert the footer at the bottom within
    body = soup.find("body")
    if body:
        body.append(footer)

    return soup


def main(soup, html_file, doc_info, type):
    """
    Loads HTML content, applies transformations, and saves it.
    """

    if type != "site_element":

        erlasstitel = doc_info.get("erlasstitel")
        ordnungsnummer = doc_info.get("ordnungsnummer")
        current_nachtragsnummer = doc_info.get("nachtragsnummer")
        in_force_status = doc_info.get("in_force", False)
        versions = doc_info.get("versions", {})

        # Wrap content and modify head
        soup = modify_html(soup, erlasstitel)

        # Insert navigation buttons
        soup = insert_nav_buttons(soup)

        # Insert the combined table
        soup = insert_combined_table(
            soup,
            doc_info,
            in_force_status,
            ordnungsnummer,
            current_nachtragsnummer,
        )

        # Insert versions list and update navigation buttons
        soup = insert_versions_and_update_navigation(
            soup, versions, ordnungsnummer, current_nachtragsnummer
        )

        # Set law div as index
        law_div = soup.find("div", {"id": "law"})
        if law_div:
            law_div.attrs["data-pagefind-body"] = ""

    # Insert header
    soup = insert_header(soup)

    # Insert footer
    soup = insert_footer(soup)

    return soup


if __name__ == "__main__":
    main()
