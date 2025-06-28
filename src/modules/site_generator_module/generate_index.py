"""Module for generating the main index page with systematic law overview.

This module creates the hierarchical index page that displays all laws organized
by their systematic categories. It:
- Builds a nested tree structure from law metadata
- Filters to show only laws currently in force
- Organizes laws by category, section, and subsection
- Generates collapsible HTML using details/summary elements
- Creates responsive flex containers for law listings
- Provides navigation links to individual law pages

The resulting index serves as the main entry point for browsing the complete
collection of laws in a structured manner.

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""


import json
import os
from pathlib import Path

from src.modules.dataset_generator_module import convert_csv

def get_versioned_asset_url(asset_url: str, version_map: dict = None) -> str:
    """
    Convert asset URL to versioned URL using the provided version map.
    Falls back to original URL if versioning is not available.
    """
    if not version_map:
        return asset_url
    
    # Remove leading slash for lookup
    clean_url = asset_url.lstrip('/')
    
    # Check if we have a versioned version
    if clean_url in version_map:
        return '/' + version_map[clean_url]
    
    return asset_url  # Return original if no versioned version

html_template = """
<html>
    <head>
        <link href="styles.css" rel="stylesheet">
        <link href="/favicon.ico" rel="shortcut icon" type="image/x-icon">
        <link href="/favicon.ico" rel="icon" type="image/x-icon">
        <meta charset="UTF-8">
        <meta content="width=device-width, initial-scale=1.0" name="viewport">
        <meta name="language" content="de-CH">
        <meta name="description" content="zhlaw.ch ist eine digitale, durchsuch- und verlinkbare Erlasssammlung (Kanton ZH). Massgebend sind die offiziellen Publikationen.">
        <title>zhlaw</title>
    </head>
    <body>
        <div class="main-container">
            <div class="content">
                <h1>Systematische Übersicht</h1>
                <div id="tree">
                    {tree_structure}
                </div>
            </div>
        </div>
    </body>
</html>
"""


def generate_tree_structure(data):
    """
    Generate HTML for a collapsible tree structure using <details> and <summary> elements,
    with laws displayed in flex containers for better mobile responsiveness.
    Uses <span> elements for summary numbers and text (no <strong> tags).
    """
    # Build a nested dictionary for three levels: category -> section -> subsection.
    categories = {}

    for item in data:
        # Get 'in_force' status, etc. (assuming a helper function exists):
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

        # Extract top-level (folder), second-level (section), third-level (subsection)
        cat = item.get("category", {})
        folder = cat.get("folder", {}) or {}
        section = cat.get("section", {}) or {}
        subsection = cat.get("subsection", {}) or {}

        # Category (folder)
        category_id = str(folder.get("id", "Unbekannte Kategorie")).strip()
        category_name = folder.get("name", "").strip()

        # Section
        section_id = section.get("id")
        section_name = section.get("name", "")

        # Subsection
        subsection_id = subsection.get("id")
        subsection_name = subsection.get("name", "")

        # 1) Initialize the category if not present
        if category_id not in categories:
            categories[category_id] = {
                "name": category_name,
                "sections": {},
                "laws": [],
            }

        # 2) If we have a section
        if section_id is not None:
            section_id = str(section_id).strip()

            # Make sure this section exists under this category
            if section_id not in categories[category_id]["sections"]:
                categories[category_id]["sections"][section_id] = {
                    "name": section_name,
                    "subsections": {},
                    "laws": [],
                }

            # 3) If we also have a subsection
            if subsection_id is not None:
                subsection_id = str(subsection_id).strip()

                # Make sure this subsection exists
                if (
                    subsection_id
                    not in categories[category_id]["sections"][section_id][
                        "subsections"
                    ]
                ):
                    categories[category_id]["sections"][section_id]["subsections"][
                        subsection_id
                    ] = {"name": subsection_name, "laws": []}

                # Place the law in the subsection
                categories[category_id]["sections"][section_id]["subsections"][
                    subsection_id
                ]["laws"].append(item)
            else:
                # If no subsection, place the law directly under the section
                categories[category_id]["sections"][section_id]["laws"].append(item)
        else:
            # If no section, place the law directly under the category
            categories[category_id]["laws"].append(item)

    # Generate nested HTML
    tree_html = ""

    # Sort categories numerically (unknown last)
    category_items = list(categories.items())
    category_items.sort(
        key=lambda x: (
            x[0] == "Unbekannte Kategorie",
            int(x[0]) if x[0].isdigit() else float("inf"),
        )
    )

    # Build the <details> structure
    for cat_id, cat_data in category_items:
        # Category summary with spans instead of <strong>
        category_display = (
            f'<span class="summary-col-number">{cat_id}:</span>'
            f'<span class="summary-col-text"> {cat_data["name"]}</span>'
        )
        tree_html += (
            f'<details class="details-col"><summary>{category_display}</summary>'
        )

        # Laws directly under this category
        if cat_data.get("laws"):
            tree_html += '<div class="law-container">'
            for law in cat_data["laws"]:
                ordnungsnummer = law.get("ordnungsnummer", "")
                erlasstitel = law.get("erlasstitel", "")
                zhlaw_url_dynamic = law.get("zhlaw_url_dynamic", "#")
                tree_html += f"""
                <div class="law-item">
                    <div class="law-number">{ordnungsnummer}</div>
                    <div class="law-title">
                        <a href="{zhlaw_url_dynamic}">{erlasstitel}</a>
                    </div>
                </div>
                """
            tree_html += "</div>"

        # Sort sections numerically
        section_items = list(cat_data["sections"].items())
        section_items.sort(
            key=lambda x: (int(x[0]) if x[0].isdigit() else float("inf"))
        )

        for sec_id, sec_data in section_items:
            # Section summary
            section_display = (
                f'<span class="summary-col-number">{sec_id}:</span>'
                f'<span class="summary-col-text"> {sec_data["name"]}</span>'
            )
            tree_html += (
                f'<details class="details-col"><summary>{section_display}</summary>'
            )

            # Laws directly under this section
            if sec_data.get("laws"):
                tree_html += '<div class="law-container">'
                for law in sec_data["laws"]:
                    ordnungsnummer = law.get("ordnungsnummer", "")
                    erlasstitel = law.get("erlasstitel", "")
                    zhlaw_url_dynamic = law.get("zhlaw_url_dynamic", "#")
                    tree_html += f"""
                    <div class="law-item">
                        <div class="law-number">{ordnungsnummer}</div>
                        <div class="law-title">
                            <a href="{zhlaw_url_dynamic}">{erlasstitel}</a>
                        </div>
                    </div>
                    """
                tree_html += "</div>"

            # Sort subsections numerically
            subsection_items = list(sec_data["subsections"].items())
            subsection_items.sort(
                key=lambda x: (int(x[0]) if x[0].isdigit() else float("inf"))
            )

            for sub_id, sub_data in subsection_items:
                # Subsection summary
                subsection_display = (
                    f'<span class="summary-col-number">{sub_id}:</span>'
                    f'<span class="summary-col-text"> {sub_data["name"]}</span>'
                )
                tree_html += f'<details class="details-col"><summary>{subsection_display}</summary>'

                # Laws under this subsection
                if sub_data.get("laws"):
                    tree_html += '<div class="law-container">'
                    for law in sub_data["laws"]:
                        ordnungsnummer = law.get("ordnungsnummer", "")
                        erlasstitel = law.get("erlasstitel", "")
                        zhlaw_url_dynamic = law.get("zhlaw_url_dynamic", "#")
                        tree_html += f"""
                        <div class="law-item">
                            <div class="law-number">{ordnungsnummer}</div>
                            <div class="law-title">
                                <a href="{zhlaw_url_dynamic}">{erlasstitel}</a>
                            </div>
                        </div>
                        """
                    tree_html += "</div>"

                tree_html += "</details>"  # end subsection <details>

            tree_html += "</details>"  # end section <details>

        tree_html += "</details>"  # end category <details>

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


def generate_minimal_index(output_file_path, version_map=None):
    """
    Generate a minimal index.html with just header and footer for FedLex-only builds.
    This serves as a placeholder until a proper systematic overview for FedLex is implemented.
    """
    # Get versioned CSS URL
    versioned_css_url = get_versioned_asset_url("styles.css", version_map)
    
    minimal_html = f"""<!DOCTYPE html>
<html>
<head>
    <link href="{versioned_css_url}" rel="stylesheet">
    <link href="/favicon.ico" rel="shortcut icon" type="image/x-icon">
    <link href="/favicon.ico" rel="icon" type="image/x-icon">
    <meta charset="UTF-8">
    <meta content="width=device-width, initial-scale=1.0" name="viewport">
    <title>zhlaw</title>
</head>
<body>
    <div class="main-container">
        <div class="content">
            <!-- Placeholder for future FedLex systematic overview -->
        </div>
    </div>
</body>
</html>"""
    
    save_html_file(minimal_html, output_file_path)
    print(f"Minimal index HTML file generated at: {output_file_path}")


def main(json_file_path, output_file_path, version_map=None):
    # Load JSON data
    data = load_json_data(json_file_path)

    # Generate collapsible tree structure HTML
    tree_structure = generate_tree_structure(data)

    # Get versioned CSS URL
    versioned_css_url = get_versioned_asset_url("styles.css", version_map)

    # Replace placeholder with tree structure and versioned CSS in the HTML template
    final_html = html_template.format(tree_structure=tree_structure).replace(
        'href="styles.css"', f'href="{versioned_css_url}"'
    )

    # Save the generated HTML to the output file
    save_html_file(final_html, output_file_path)

    print(f"HTML file successfully generated at: {output_file_path}")


if __name__ == "__main__":
    main(
        "data/zhlex/zhlex_data/zhlex_data_processed.json",
        "src/static_files/html/index.html",
    )
