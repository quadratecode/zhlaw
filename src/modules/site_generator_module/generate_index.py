# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

import json
import os

from src.modules.dataset_generator_module import convert_csv

html_template = """
<html>
    <head>
        <link href="styles.css" rel="stylesheet">
        <link href="/favicon.ico" rel="shortcut icon" type="image/x-icon">
        <link href="/favicon.ico" rel="icon" type="image/x-icon">
        <meta charset="UTF-8">
        <meta content="width=device-width, initial-scale=1.0" name="viewport">
        <title>ZHLaw</title>
    </head>
    <body>
        <div id="content">
            <link href="/pagefind/pagefind-ui.css" rel="stylesheet">
            <script src="/pagefind/pagefind-ui.js"></script>
            <div id="search"></div>
            <script>
            window.addEventListener('DOMContentLoaded', (event) => {{
                new PagefindUI({{ 
                    element: "#search", 
                    showSubResults: false, 
                    pageSize: 15, 
                    excerptLength: 25,
                    ranking: {{
                        termFrequency: 0.0,
                        termSaturation: 1.6,
                        termSimilarity: 2.0,
                    }},
                }});
            }});
            </script>
            <!-- Tree Structure Placeholder -->
            <h1>Systematische Sammlung</h1>
            <div id="tree">
                {tree_structure}
            </div>
        </div>
    </body>
</html>
"""


def generate_tree_structure(data):
    """
    Generate HTML for a collapsible tree structure using <details> and <summary> elements,
    with laws displayed in tables for vertical alignment.
    """
    ordners = {}
    for item in data:
        # Get in_force status from the latest version
        (
            in_force,
            erlassdatum,
            inkraftsetzungsdatum,
            publikationsdatum,
            aufhebungsdatum,
        ) = convert_csv.extract_latest_version_info(item.get("versions", []))

        # Skip laws that are not in force
        if not in_force:
            continue

        # Extract category details
        category = item.get("category", {}) or {}

        # Ordner
        if category.get("ordner") and category["ordner"].get("id"):
            ordner = category["ordner"]
            ordner_id = str(ordner.get("id", "")).strip()
            ordner_name = ordner.get("name", "").strip()
        else:
            ordner_id = "Unbekannter Ordner"
            ordner_name = ""

        # Section
        if category.get("section") and category["section"].get("id"):
            section = category["section"]
            section_id = str(section.get("id", "")).strip()
            section_name = section.get("name", "").strip()
        else:
            section_id = None
            section_name = None

        # Initialize ordner
        if ordner_id not in ordners:
            ordners[ordner_id] = {"name": ordner_name, "sections": {}, "laws": []}

        if section_id:
            # Initialize section
            if section_id not in ordners[ordner_id]["sections"]:
                ordners[ordner_id]["sections"][section_id] = {
                    "name": section_name,
                    "laws": [],
                }
            # Append the law to the appropriate section
            ordners[ordner_id]["sections"][section_id]["laws"].append(item)
        else:
            # Append the law directly to the ordner
            ordners[ordner_id]["laws"].append(item)

    # Now generate the HTML
    tree_html = ""

    # Get ordner_items, sort ordners numerically, placing 'Unbekannter Ordner' last
    ordner_items = list(ordners.items())
    ordner_items.sort(
        key=lambda x: (
            x[0] == "Unbekannter Ordner",
            int(x[0]) if x[0].isdigit() else float("inf"),
        )
    )

    for ordner_id, ordner_data in ordner_items:
        ordner_display = (
            f'<strong>{ordner_id}</strong><strong>:</strong> {ordner_data["name"]}'
        )
        tree_html += f'<details class="details-col"><summary>{ordner_display}</summary>'

        # Append laws directly under ordner
        if ordner_data.get("laws"):
            tree_html += '<table class="law-table">'
            for law in ordner_data.get("laws", []):
                ordnungsnummer = law.get("ordnungsnummer", "")
                erlasstitel = law.get("erlasstitel", "")
                zhlaw_url_dynamic = law.get("zhlaw_url_dynamic", "#")
                law_text = f"<strong>{ordnungsnummer}</strong><strong>:</strong> "
                tree_html += f"""
                <tr onclick="window.location='{zhlaw_url_dynamic}'" class="clickable-row">
                    <td class="ordnungsnummer-col">{law_text}</td>
                    <td class="erlasstitel-col">{erlasstitel}</td>
                </tr>
                """
            tree_html += "</table>"

        # Get section_items, sort sections numerically
        section_items = list(ordner_data["sections"].items())
        section_items.sort(
            key=lambda x: (int(x[0]) if x[0].isdigit() else float("inf"))
        )

        for section_id, section_data in section_items:
            section_display = f'<strong>{section_id}</strong><strong>:</strong> {section_data["name"]}'
            tree_html += (
                f'<details class="details-col"><summary>{section_display}</summary>'
            )

            # Append laws under section
            if section_data.get("laws"):
                tree_html += '<table class="law-table">'
                for law in section_data.get("laws", []):
                    ordnungsnummer = law.get("ordnungsnummer", "")
                    erlasstitel = law.get("erlasstitel", "")
                    zhlaw_url_dynamic = law.get("zhlaw_url_dynamic", "#")
                    law_text = f"<strong>{ordnungsnummer}</strong>"
                    tree_html += f"""
                    <tr onclick="window.location='{zhlaw_url_dynamic}'" class="clickable-row">
                        <td class="ordnungsnummer-col">{law_text}</td>
                        <td class="erlasstitel-col">{erlasstitel}</td>
                    </tr>
                    """
                tree_html += "</table>"

            tree_html += "</details>"
        tree_html += "</details>"

    return tree_html


def load_json_data(file_path):
    """
    Load the JSON data from the specified file path.
    """
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_html_file(html_content, file_path):
    """
    Save the generated HTML content to the specified file path.
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(html_content)


def main(json_file_path, output_file_path):
    # Load JSON data
    data = load_json_data(json_file_path)

    # Generate collapsible tree structure HTML using <details> and <summary>
    tree_structure = generate_tree_structure(data)

    # Replace placeholder with tree structure in the HTML template
    final_html = html_template.format(tree_structure=tree_structure)

    # Save the generated HTML to the output file
    save_html_file(final_html, output_file_path)

    print(f"HTML file successfully generated at: {output_file_path}")


if __name__ == "__main__":
    main(
        "data/zhlex/zhlex_data/zhlex_data_processed.json",
        "src/static_files/html/index.html",
    )
