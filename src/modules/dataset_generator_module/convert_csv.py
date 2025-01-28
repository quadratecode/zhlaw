# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

import json
import csv
import arrow


def extract_latest_version_info(versions):
    """
    Extracts the in_force status and dates from the version with the highest 'numeric_nachtragsnummer'.
    """
    if not versions:
        return False, "", "", "", ""

    # Use 'numeric_nachtragsnummer' for sorting
    for version in versions:
        try:
            version["numeric_nachtragsnummer_float"] = float(
                version.get("numeric_nachtragsnummer", 0)
            )
        except ValueError:
            version["numeric_nachtragsnummer_float"] = 0.0

    # Sort versions by 'numeric_nachtragsnummer_float' in descending order
    sorted_versions = sorted(
        versions, key=lambda x: x["numeric_nachtragsnummer_float"], reverse=True
    )

    latest_version = sorted_versions[0]

    in_force = latest_version.get("in_force", False)
    erlassdatum = latest_version.get("erlassdatum", "")
    inkraftsetzungsdatum = latest_version.get("inkraftsetzungsdatum", "")
    publikationsdatum = latest_version.get("publikationsdatum", "")
    aufhebungsdatum = latest_version.get("aufhebungsdatum", "")

    return (
        in_force,
        erlassdatum,
        inkraftsetzungsdatum,
        publikationsdatum,
        aufhebungsdatum,
    )


def format_date(date_str):
    if date_str:
        try:
            date = arrow.get(date_str, "YYYYMMDD")
            return date.format("YYYY-MM-DD")
        except Exception:
            return ""
    else:
        return ""


def extract_category(item):
    """
    Safely extracts the folder, section, and subsection (and their IDs) from the category field in the JSON item.
    Handles cases where category or subfields might be None.
    """
    category = item.get("category", {})

    # Extract folder details
    folder = category.get("folder", {})
    folder_name = folder.get("name", "") if folder else ""
    folder_id = folder.get("id", "") if folder else ""

    # Extract section details
    section = category.get("section", {})
    section_name = section.get("name", "") if section else ""
    section_id = section.get("id", "") if section else ""

    # Extract subsection details
    subsection = category.get("subsection", {})
    subsection_name = subsection.get("name", "") if subsection else ""
    subsection_id = subsection.get("id", "") if subsection else ""

    return (
        folder_name,
        folder_id,
        section_name,
        section_id,
        subsection_name,
        subsection_id,
    )


def convert_json_to_csv(json_file, csv_file):
    # Open and load the JSON data
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Open the CSV file for writing
    with open(csv_file, "w", newline="", encoding="utf-8-sig") as csvfile:
        fieldnames = [
            "Ordnungsnummer",
            "Erlasstitel",
            "Kurztitel",
            "Abkürzung",
            "Dynamischer Link",
            "In Kraft",
            "Erlassdatum",
            "Inkraftsetzungsdatum",
            "Letzte Publikation",
            "Aufhebungsdatum",
            "folder_id",
            "folder",
            "section_id",
            "section",
            "subsection_id",
            "subsection",
            "timestamp",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        # Write the header row
        writer.writeheader()

        # Loop through each item in the JSON data
        for item in data:
            # Extract necessary fields
            ordnungsnummer = item.get("ordnungsnummer", "")
            erlasstitel = item.get("erlasstitel", "")
            kurztitel = item.get("kurztitel", "")
            abkuerzung = item.get("abkuerzung", "")
            dynamic_source = item.get("dynamic_source", "")

            # Extract folder, section, and subsection (and their IDs) from the category field
            folder, folder_id, section, section_id, subsection, subsection_id = (
                extract_category(item)
            )

            # Extract the latest version info using 'numeric_nachtragsnummer'
            (
                in_force,
                erlassdatum,
                inkraftsetzungsdatum,
                publikationsdatum,
                aufhebungsdatum,
            ) = extract_latest_version_info(item.get("versions", []))

            # Format the dates
            erlassdatum_formatted = format_date(erlassdatum)
            inkraftsetzungsdatum_formatted = format_date(inkraftsetzungsdatum)
            aufhebungsdatum_formatted = format_date(aufhebungsdatum)
            publikationsdatum_formatted = format_date(publikationsdatum)

            # Write the row to CSV
            writer.writerow(
                {
                    "Ordnungsnummer": ordnungsnummer,
                    "Erlasstitel": erlasstitel,
                    "Kurztitel": kurztitel,
                    "Abkürzung": abkuerzung,
                    "Dynamischer Link": dynamic_source,
                    "In Kraft": in_force,
                    "Erlassdatum": erlassdatum_formatted,
                    "Inkraftsetzungsdatum": inkraftsetzungsdatum_formatted,
                    "Letzte Publikation": publikationsdatum_formatted,
                    "Aufhebungsdatum": aufhebungsdatum_formatted,
                    "folder_id": folder_id,
                    "folder": folder,
                    "section_id": section_id,
                    "section": section,
                    "subsection_id": subsection_id,
                    "subsection": subsection,
                    "timestamp": arrow.now().format("YYYY-MM-DD HH:mm:ss"),
                }
            )


def main(processed_data):
    csv_file = "data/zhlex/zhlex_data/zhlex_data_cc_comp.csv"  # Replace with the desired output CSV file name

    # Convert the JSON data to CSV
    convert_json_to_csv(processed_data, csv_file)


if __name__ == "__main__":
    main("data/zhlex/zhlex_data/zhlex_data_processed.json")
