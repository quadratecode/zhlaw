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
                }
            )


def main(processed_data):
    csv_file = "data/zhlex/zhlex_data/zhlex_data_cc_comp.csv"  # Replace with the desired output CSV file name

    # Convert the JSON data to CSV
    convert_json_to_csv(processed_data, csv_file)


if __name__ == "__main__":
    main()
