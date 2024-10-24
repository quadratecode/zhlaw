# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

import json
import csv


def extract_in_force(versions):
    """
    Extracts the 'in_force' status. If any version has 'in_force' set to true,
    it returns True, otherwise False.
    """
    for version in versions:
        if version.get("in_force", False):
            return True
    return False


def extract_category(item):
    """
    Safely extracts the ordner, section, and subsection (and their IDs) from the category field in the JSON item.
    Handles cases where category or subfields might be None.
    """
    category = item.get("category", {})

    # Extract ordner details
    ordner = category.get("ordner", {})
    ordner_name = ordner.get("name", "") if ordner else ""
    ordner_id = ordner.get("id", "") if ordner else ""

    # Extract section details
    section = category.get("section", {})
    section_name = section.get("name", "") if section else ""
    section_id = section.get("id", "") if section else ""

    # Extract subsection details
    subsection = category.get("subsection", {})
    subsection_name = subsection.get("name", "") if subsection else ""
    subsection_id = subsection.get("id", "") if subsection else ""

    return (
        ordner_name,
        ordner_id,
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
            "ordnungsnummer",
            "erlasstitel",
            "kurztitel",
            "abkuerzung",
            "dynamic_source",
            "in_force",
            "ordner_id",
            "ordner",
            "section_id",
            "section",
            "subsection_id",
            "subsection",
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

            # Extract ordner, section, and subsection (and their IDs) from the category field
            ordner, ordner_id, section, section_id, subsection, subsection_id = (
                extract_category(item)
            )

            # Check the 'in_force' status based on the versions
            in_force = extract_in_force(item.get("versions", []))

            # Write the row to CSV
            writer.writerow(
                {
                    "ordnungsnummer": ordnungsnummer,
                    "erlasstitel": erlasstitel,
                    "kurztitel": kurztitel,
                    "abkuerzung": abkuerzung,
                    "dynamic_source": dynamic_source,
                    "in_force": in_force,
                    "ordner_id": ordner_id,
                    "ordner": ordner,
                    "section_id": section_id,
                    "section": section,
                    "subsection_id": subsection_id,
                    "subsection": subsection,
                }
            )


def main(processed_data):
    csv_file = "data/zhlex/zhlex_data/zhlex_data_cc_comp.csv"  # Replace with the desired output CSV file name

    # Convert the JSON data to CSV
    convert_json_to_csv(processed_data, csv_file)


if __name__ == "__main__":
    main("data/zhlex/zhlex_data/zhlex_data_processed.json")
