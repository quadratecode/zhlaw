# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

import arrow
from email.utils import formatdate
import xml.etree.ElementTree as ET
from xml.dom import minidom
import html
import re


def format_rfc822_date(date_str):
    """
    Convert a date string in YYYYMMDD format to RFC 822 format required for RSS.
    """
    date = arrow.get(date_str, "YYYYMMDD")
    # Format to RFC 822 format
    return formatdate(date.timestamp(), localtime=False)


def generate_guid(dispatch_date, affair_guid, title):
    """
    Generate a unique GUID for the item by combining the dispatch date and either:
    1. The affair GUID if available, or
    2. A hash of the title as fallback

    Using a hash of the title ensures consistency even for affairs without an official ID.
    """
    import hashlib

    if affair_guid:
        return f"zhlaw-krzh-{dispatch_date}-{affair_guid}"
    else:
        # Create a consistent hash of the title
        title_hash = hashlib.md5(title.encode("utf-8")).hexdigest()[:12]
        return f"zhlaw-krzh-{dispatch_date}-title-{title_hash}"


def create_description(affair):
    """
    Create an HTML description for the affair including all relevant metadata.
    """
    description = f"<h3>{html.escape(affair['title'])}</h3>"
    description += (
        "<table border='1' cellpadding='5' style='border-collapse: collapse;'>"
    )

    # Add affair type if available
    if affair.get("affair_type"):
        description += f"<tr><td>Geschäftsart:</td><td>{html.escape(affair['affair_type'])}</td></tr>"

    # Add Vorlagen-Nr if available
    if affair.get("vorlagen_nr"):
        description += f"<tr><td>Vorlagen-Nr:</td><td>{html.escape(affair['vorlagen_nr'])}</td></tr>"

    # Add KR-Nr if available
    if affair.get("kr_nr"):
        description += (
            f"<tr><td>KR-Nr:</td><td>{html.escape(affair['kr_nr'])}</td></tr>"
        )

    # Add steps if available
    if affair.get("affair_steps"):
        steps = "<br>".join(
            [
                f"{arrow.get(step['affair_step_date']).format('DD.MM.YYYY')}: {html.escape(step['affair_step_type'])}"
                for step in affair["affair_steps"]
            ]
        )
        description += f"<tr><td>Ablaufschritte:</td><td>{steps}</td></tr>"

    # Add AI changes if available
    if affair.get("ai_changes"):
        try:
            ai_output = affair.get("ai_changes", {})
            if isinstance(ai_output, str):
                # Handle string output
                description += f"<tr><td>Änderungen (KI):</td><td>{html.escape(ai_output)}</td></tr>"
            elif "info" in ai_output:
                description += f"<tr><td>Änderungen (KI):</td><td>Keine Änderungen gefunden.</td></tr>"
            elif ai_output:
                # Format AI changes as a list
                formatted_changes = []
                for law, changes in ai_output.items():
                    # Clean up § and . from changes for better readability
                    cleaned_changes = []
                    for change in changes:
                        # Remove § and dot from the changes
                        cleaned = re.sub(r"[§\.]", "", change)
                        cleaned = cleaned.strip()
                        cleaned_changes.append(html.escape(cleaned))

                    formatted_changes.append(
                        f"{html.escape(law)}: {', '.join(cleaned_changes)}"
                    )

                ai_output_formatted = "<br>".join(formatted_changes)
                description += (
                    f"<tr><td>Änderungen (KI):</td><td>{ai_output_formatted}</td></tr>"
                )
        except Exception as e:
            # If there's an error formatting AI changes, just display them as is
            description += f"<tr><td>Änderungen (KI):</td><td>Fehler bei der Formatierung: {html.escape(str(e))}</td></tr>"

    # Add PDF link if available
    if affair.get("krzh_pdf_url"):
        description += f"<tr><td>PDF:</td><td><a href='{html.escape(affair['krzh_pdf_url'])}'>PDF herunterladen</a></td></tr>"

    description += "</table>"

    return description


def main(dispatch_data, site_url="https://www.zhlaw.ch"):
    """
    Generate an RSS feed from the dispatch data.

    Args:
        dispatch_data: The processed dispatch data
        site_url: The base URL of the site

    Returns:
        str: The RSS feed as an XML string
    """
    # Create the root RSS element
    rss = ET.Element("rss", version="2.0")

    # Add required namespaces
    rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")

    channel = ET.SubElement(rss, "channel")

    # Add channel metadata
    ET.SubElement(channel, "title").text = "zhlaw - Dispatch KRZH"
    ET.SubElement(channel, "link").text = f"{site_url}/dispatch.html"
    ET.SubElement(channel, "description").text = "zhlaw - Mutationen Geschäfte KRZH"
    ET.SubElement(channel, "language").text = "de-ch"
    ET.SubElement(channel, "lastBuildDate").text = formatdate(localtime=False)

    # Add atom:link for self-reference (RSS 2.0 best practice)
    atom_link = ET.SubElement(channel, "{http://www.w3.org/2005/Atom}link")
    atom_link.set("href", f"{site_url}/dispatch-feed.xml")
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")

    # Sort dispatches by date (newest first)
    sorted_dispatches = sorted(
        dispatch_data, key=lambda x: x["krzh_dispatch_date"], reverse=True
    )

    # Limit to most recent 50 items for performance
    item_count = 0
    max_items = 100

    # Add items for each affair
    for dispatch in sorted_dispatches:
        if item_count >= max_items:
            break

        dispatch_date = dispatch["krzh_dispatch_date"]
        formatted_date = arrow.get(dispatch_date, "YYYYMMDD").format("DD.MM.YYYY")
        pub_date = format_rfc822_date(dispatch_date)

        # Sort affairs by type priority
        affair_type_priorities = {
            "vorlage": 1,
            "einzelinitiative": 2,
            "behördeninitiative": 3,
            "parlamentarische initiative": 4,
        }

        def get_priority(affair):
            affair_type = affair.get("affair_type", "").lower()
            for key, priority in affair_type_priorities.items():
                if key in affair_type:
                    return priority
            return 5  # Default priority

        sorted_affairs = sorted(dispatch["affairs"], key=get_priority)

        for affair in sorted_affairs:
            if item_count >= max_items:
                break

            # Create item element
            item = ET.SubElement(channel, "item")

            # Add dispatch date to title for context
            title = f"{formatted_date}: {affair['title']}"
            ET.SubElement(item, "title").text = title

            # Add link - prefer affair URL, fall back to PDF URL
            link = (
                affair.get("krzh_affair_url")
                or affair.get("krzh_pdf_url")
                or f"{site_url}/dispatch.html#{dispatch_date}"
            )
            ET.SubElement(item, "link").text = link

            # Add description (HTML content)
            ET.SubElement(item, "description").text = create_description(affair)

            # Add publication date
            ET.SubElement(item, "pubDate").text = pub_date

            # Add guid
            guid = generate_guid(
                dispatch_date, affair.get("affair_guid", ""), affair["title"]
            )
            guid_elem = ET.SubElement(item, "guid")
            guid_elem.text = guid
            guid_elem.set("isPermaLink", "false")

            item_count += 1

    # Convert to string with pretty printing
    xml_str = ET.tostring(rss, encoding="unicode")

    # Clean up the XML and handle namespaces properly
    parsed_xml = minidom.parseString(xml_str)
    pretty_xml = parsed_xml.toprettyxml(indent="  ")

    # Remove unwanted XML declaration in the content
    pretty_xml = pretty_xml.replace(
        '<?xml version="1.0" ?>', '<?xml version="1.0" encoding="UTF-8"?>'
    )

    return pretty_xml


if __name__ == "__main__":
    # For testing
    import json

    with open(
        "data/krzh_dispatch/krzh_dispatch_data/krzh_dispatch_data.json", "r"
    ) as f:
        data = json.load(f)
    rss_feed = main(data)
    print(rss_feed)
