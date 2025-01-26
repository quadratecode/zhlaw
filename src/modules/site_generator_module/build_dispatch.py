# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

import arrow
import re


def generate_html_page(content):
    return f"""
    <!DOCTYPE html>
    <head>
        <meta charset="UTF-8">
        <meta content="width=device-width, initial-scale=1.0" name="viewport">
        <link rel="stylesheet" type="text/css" href="styles.css">
        <title>KRZH Dispatch</title>
    </head>
    <body>
        <div class="main-container">
            <div class="content">
                <div id="dispatch-static">
                    {content}
                </div>
            </div>
        </div>
    </body>
    </html>
    """


def convert_to_html(data):
    html_content = ""

    # Add timestamp at the top of the page
    html_content += f"<p id='update'>Letzte Aktualisierung: {arrow.now().format('DD.MM.YYYY HH:mm:ss')}</p>\n"

    for dispatch in data:
        dispatch_date = arrow.get(dispatch["krzh_dispatch_date"]).format("DD.MM.YYYY")
        html_content += f'<h2 id="{dispatch["krzh_dispatch_date"]}"><a href="#{dispatch["krzh_dispatch_date"]}">&#8617</a> Ratsversand vom {dispatch_date}</h2>\n'

        if not dispatch["affairs"]:
            html_content += "<p>[Keine relevanten Geschäfte gefunden]</p>\n"
        else:
            for affair in dispatch["affairs"]:
                html_content += f"<h3>{affair['title']}</h3>\n"
                html_content += "<table class='dispatch-entry-table'>\n"

                if affair.get("affair_type"):
                    html_content += f"<tr><td>Geschäftsart:</td><td>{affair['affair_type']}</td></tr>\n"

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

                if (
                    affair.get("pdf_orientation") == "landscape"
                    and affair.get("affair_type") == "Vorlage"
                ):
                    html_content += f"<tr><td>Änderungen (Regex):</td><td>[Synopse: Manuelle Prüfung erforderlich]</td></tr>\n"
                elif affair.get("affair_type") != "Vorlage":
                    html_content += f"<tr><td>Änderungen (Regex):</td><td>[Keine Vorlage: Manuelle Prüfung erforderlich]</td></tr>\n"
                else:
                    changes = affair.get("regex_changes", {})
                    if changes:
                        # Remove § and . from changes
                        changes = {
                            law: [
                                re.sub(r"[\§\.]", "", change) for change in changes[law]
                            ]
                            for law in changes
                        }
                        # List changes as lawname:changes
                        # Changes seperated by comma, laws seperated by <br>
                        changes_str = "<br>".join(
                            [f"{law}: {', '.join(changes[law])}" for law in changes]
                        )
                    else:
                        changes_str = "[Keine Normen gefunden]"

                    changes_str = re.sub(r"[\§\.]", "", changes_str)
                    html_content += (
                        f"<tr><td>Änderungen (Regex):</td><td>{changes_str}</td></tr>\n"
                    )

                if affair.get("ai_changes"):
                    # Try to convert process ai output same as changes
                    try:
                        ai_output = affair.get("ai_changes", {})
                        # if output contains "no changes found", include unchanged
                        if "info" in ai_output:
                            pass
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
                    f"<tr><td>Änderungen (AI):</td><td>{ai_output}</td></tr>\n"
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

    return html_content


def main(dispatch_data):

    html_content = convert_to_html(dispatch_data)
    complete_html = generate_html_page(html_content)

    return complete_html


if __name__ == "__main__":
    main()
