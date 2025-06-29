"""Module for building KRZH dispatch HTML pages.

This module generates HTML pages for parliamentary dispatches (KRZH dispatches).
It handles:
- Converting dispatch data to HTML format
- Creating a sidebar with dispatch controls (expand/collapse all)
- Generating dispatch listings with collapsible details
- Adding RSS feed links and metadata
- Implementing client-side JavaScript for interactivity

The module creates a structured layout similar to law pages but optimized for
dispatches, with controls to expand/collapse all dispatch entries at once.

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import arrow
import re


# Modified generate_html_page function to implement sidebar like on law pages


def generate_html_page(content):
    return f"""<!DOCTYPE html>
<html>
<head>
        <meta charset="UTF-8">
        <meta content="width=device-width, initial-scale=1.0" name="viewport">
        <meta name="language" content="de-CH">
        <meta name="description" content="Feed der parlamentarischen Geschäfte (Kanton ZH). Massgebend sind die offiziellen Publikationen.">
        <link rel="stylesheet" type="text/css" href="styles.css">
        <link rel="alternate" type="application/rss+xml" title="zhlaw.ch - KRZH Dispatch" href="/dispatch-feed.xml">
        <title>zhlaw - Dispatch KRZH</title>
    </head>
    <body>
        <div class="main-container">
            <div id="sidebar">
                <!-- Dispatch info container styled like links-container -->
                <div id="dispatch-info-container" class="links-container">
                    <div class="links-inner">
                        <div class="link-group">
                            <div class="link-title">Letzte Aktualisierung:</div>
                            <div class="link-url">{arrow.now().format('DD.MM.YYYY')}</div>
                        </div>
                        <hr class="links-separator">
                        <div class="link-group">
                            <div class="link-url">
                                <a href="/dispatch-feed.xml" target="_blank" class="rss-link">
                                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                        <path d="M4 11a9 9 0 0 1 9 9"></path>
                                        <path d="M4 4a16 16 0 0 1 16 16"></path>
                                        <circle cx="5" cy="19" r="1"></circle>
                                    </svg>
                                    RSS-Feed
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Dispatch controls styled like nav-buttons -->
                <div class="nav-buttons">
                    <button id="expand-all" class="nav-button">
                        <span class="nav-symbol">+</span>
                        <span class="nav-text">alle einblenden</span>
                    </button>
                    <button id="collapse-all" class="nav-button">
                        <span class="nav-symbol">-</span>
                        <span class="nav-text">alle ausblenden</span>
                    </button>
                </div>
            </div>
            <div class="content">
                <h1>Dispatch KRZH</h1>
                <div id="dispatch-static">
                    {content}
                </div>
            </div>
        </div>
        
        <script>
            // JavaScript to handle expand/collapse functionality
            document.addEventListener("DOMContentLoaded", function() {{
                // Get all dispatch details elements
                const detailsElements = document.querySelectorAll(".dispatch-details");
                
                // Add event listener for expand all button
                document.getElementById("expand-all").addEventListener("click", function() {{
                    detailsElements.forEach(function(element) {{
                        element.setAttribute("open", "");
                    }});
                }});
                
                // Add event listener for collapse all button
                document.getElementById("collapse-all").addEventListener("click", function() {{
                    detailsElements.forEach(function(element) {{
                        element.removeAttribute("open");
                    }});
                }});
            }});
        </script>
    </body>
</html>"""


def convert_to_html(data):
    html_content = ""

    # Track if this is the first dispatch (newest one)
    is_first_dispatch = True

    for dispatch in data:
        dispatch_date = arrow.get(dispatch["krzh_dispatch_date"]).format("DD.MM.YYYY")

        # Create details element, with 'open' attribute for the first dispatch only
        if is_first_dispatch:
            html_content += f'<details id="{dispatch["krzh_dispatch_date"]}" class="dispatch-details newest-dispatch" open>\n'
            is_first_dispatch = False
        else:
            html_content += f'<details id="{dispatch["krzh_dispatch_date"]}" class="dispatch-details">\n'

        # Create summary with heading inside (arrow at the end)
        html_content += f"<summary><h2>{dispatch_date}</h2></summary>\n"

        if not dispatch["affairs"]:
            html_content += "<p>[Keine relevanten Geschäfte gefunden]</p>\n"
        else:
            for affair in dispatch["affairs"]:
                html_content += f"<h3>{affair['title']}</h3>\n"
                html_content += "<table class='dispatch-entry-table'>\n"

                if affair.get("affair_type"):
                    # Check if affair_type contains any of the targeted keywords
                    affair_type_lower = affair["affair_type"].lower()
                    is_law_change = (
                        "vorlage" in affair_type_lower
                        or "einzelinitiative" in affair_type_lower
                        or "behördeninitiative" in affair_type_lower
                        or "parlamentarische initiative" in affair_type_lower
                    )

                    # Add law-change class if applicable
                    row_class = ' class="law-change"' if is_law_change else ""
                    html_content += f"<tr{row_class}><td>Geschäftsart:</td><td>{affair['affair_type']}</td></tr>\n"

                if affair.get("vorlagen_nr"):
                    html_content += f"<tr><td>Vorlagen-Nr:</td><td>{affair['vorlagen_nr']}</td></tr>\n"

                if affair.get("kr_nr"):
                    html_content += (
                        f"<tr><td>KR-Nr:</td><td>{affair['kr_nr']}</td></tr>\n"
                    )

                if affair.get("pdf_orientation"):
                    if affair["pdf_orientation"] == "portrait":
                        orientation = "Hochformat"
                    elif affair["pdf_orientation"] == "landscape":
                        orientation = "Querformat"
                    html_content += (
                        f"<tr><td>PDF-Orientierung:</td><td>{orientation}</td></tr>\n"
                    )

                steps = "<br>".join(
                    [
                        f"{arrow.get(step['affair_step_date']).format('DD.MM.YYYY')}: {step['affair_step_type']}"
                        for step in affair["affair_steps"]
                    ]
                )
                html_content += f"<tr><td>Ablaufschritte:</td><td>{steps}</td></tr>\n"

                if affair.get("ai_changes"):
                    # Try to convert process ai output same as changes
                    try:
                        ai_output = affair.get("ai_changes", {})
                        # if output contains "no changes found", include unchanged
                        if "info" in ai_output:
                            ai_output = "Keine Änderungen gefunden."
                        # if output is info: no changes found, include unchanged
                        elif ai_output:
                            # Remove § and . from changes
                            ai_output = {
                                law: [
                                    re.sub(r"[\§\.]", "", change)
                                    for change in ai_output[law]
                                ]
                                for law in ai_output
                            }
                            # List changes as lawname:changes
                            # Changes seperated by comma, laws seperated by <br>
                            ai_output = "<br>".join(
                                [
                                    f"{law}: {', '.join(ai_output[law])}"
                                    for law in ai_output
                                ]
                            )
                        else:
                            pass
                    except Exception as e:
                        ai_output = affair["ai_changes"]

                    html_content += (
                        f"<tr><td>Änderungen (KI):</td><td>{ai_output}</td></tr>\n"
                    )

                # Add hyperlinks in second column (PDF-URL and Geschäfts-URL)
                if affair.get("krzh_pdf_url") or affair.get("krzh_affair_url"):
                    html_content += "<tr><td>Hyperlinks:</td><td>\n"
                    if affair.get("krzh_pdf_url"):
                        html_content += (
                            f"<a href='{affair['krzh_pdf_url']}'>PDF</a><br>\n"
                        )
                    if affair.get("krzh_affair_url"):
                        html_content += (
                            f"<a href='{affair['krzh_affair_url']}'>Geschäft</a>\n"
                        )
                    html_content += "</td></tr>\n"

                html_content += "</table>\n"

        # Close the details element
        html_content += "</details>\n"

    return html_content


def main(dispatch_data):
    html_content = convert_to_html(dispatch_data)
    complete_html = generate_html_page(html_content)
    return complete_html


if __name__ == "__main__":
    main()
