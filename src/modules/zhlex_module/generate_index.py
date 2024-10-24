import json
import os

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
                        termFrequency: 1.0, 
                        pageLength: 0.1 
                    }} 
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
    Generate HTML for a collapsible tree structure using <details> and <summary> elements.
    """
    ordners = {}
    for item in data:
        # Check if the law is currently in force
        if not any(version.get("in_force") for version in item.get("versions", [])):
            continue  # Skip laws that are not in force

        # Extract category details
        category = item.get("category", {}) or {}

        ordner = category.get("ordner") or {}
        ordner_id = ordner.get("id", "unknown_ordner")
        ordner_name = ordner.get("name", "Unknown Ordner")

        section = category.get("section") or {}
        section_id = section.get("id", "unknown_section")
        section_name = section.get("name", "Unknown Section")

        subsection = category.get("subsection") or {}
        subsection_id = subsection.get("id", "unknown_subsection")
        subsection_name = subsection.get("name", "Unknown Subsection")

        # Initialize ordner
        if ordner_id not in ordners:
            ordners[ordner_id] = {"name": ordner_name, "sections": {}, "laws": []}

        # Initialize section
        if section_id not in ordners[ordner_id]["sections"]:
            ordners[ordner_id]["sections"][section_id] = {
                "name": section_name,
                "subsections": {},
                "laws": [],
            }

        # Initialize subsection
        if subsection_id != "unknown_subsection":
            if (
                subsection_id
                not in ordners[ordner_id]["sections"][section_id]["subsections"]
            ):
                ordners[ordner_id]["sections"][section_id]["subsections"][
                    subsection_id
                ] = {"name": subsection_name, "laws": []}
            # Append the law to the appropriate subsection
            ordners[ordner_id]["sections"][section_id]["subsections"][subsection_id][
                "laws"
            ].append(item)
        else:
            # Append the law directly to the section
            ordners[ordner_id]["sections"][section_id]["laws"].append(item)

    # Now generate the HTML
    tree_html = ""

    for ordner_id, ordner_data in ordners.items():
        ordner_display = (
            f'<strong>{ordner_id}</strong> <strong>-</strong> {ordner_data["name"]}'
        )
        tree_html += f"<details><summary>{ordner_display}</summary>"

        # Append laws directly under ordner
        for law in ordner_data.get("laws", []):
            ordnungsnummer = law.get("ordnungsnummer", "")
            erlasstitel = law.get("erlasstitel", "")
            zhlaw_url_dynamic = law.get("zhlaw_url_dynamic", "#")
            law_text = (
                f"<strong>{ordnungsnummer}</strong> <strong>-</strong> {erlasstitel}"
            )
            tree_html += f'<div class="law-item"><a href="{zhlaw_url_dynamic}">{law_text}</a></div>'

        for section_id, section_data in ordner_data["sections"].items():
            section_display = f'<strong>{section_id}</strong> <strong>-</strong> {section_data["name"]}'
            tree_html += f"<details><summary>{section_display}</summary>"

            # Append laws directly under section
            for law in section_data.get("laws", []):
                ordnungsnummer = law.get("ordnungsnummer", "")
                erlasstitel = law.get("erlasstitel", "")
                zhlaw_url_dynamic = law.get("zhlaw_url_dynamic", "#")
                law_text = f"<strong>{ordnungsnummer}</strong> <strong>-</strong> {erlasstitel}"
                tree_html += f'<div class="law-item"><a href="{zhlaw_url_dynamic}">{law_text}</a></div>'

            for subsection_id, subsection_data in section_data["subsections"].items():
                subsection_display = f'<strong>{subsection_id}</strong> <strong>-</strong> {subsection_data["name"]}'
                tree_html += f"<details><summary>{subsection_display}</summary>"

                for law in subsection_data["laws"]:
                    ordnungsnummer = law.get("ordnungsnummer", "")
                    erlasstitel = law.get("erlasstitel", "")
                    zhlaw_url_dynamic = law.get("zhlaw_url_dynamic", "#")
                    law_text = f"<strong>{ordnungsnummer}</strong> <strong>-</strong> {erlasstitel}"
                    tree_html += f'<div class="law-item"><a href="{zhlaw_url_dynamic}">{law_text}</a></div>'
                tree_html += "</details>"

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
