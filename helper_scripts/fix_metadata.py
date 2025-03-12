import os
import json
import arrow

# Get the current timestamp in "YYYYMMDD-HHmmss" format
timestamp = arrow.now().format("YYYYMMDD-HHmmss")


def update_file(file_path, source_data):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Update process_steps and move filename to doc_info
    scrape_law = data.get("process_steps", {}).get("scrape_law", [])
    if len(scrape_law) == 2:
        data["process_steps"]["scrape_law"] = timestamp

    # Simplify the process_steps dictionary by removing specific steps and adding new steps
    steps_to_remove = [
        "extract_color",
        "json_to_html_law",
        "json_to_html_marginalia",
        "merge_marginalia",
        "match_marginalia",
        "match_footnotes_and_links",
        "clean_data",
    ]
    data["process_steps"] = {
        k: v for k, v in data["process_steps"].items() if k not in steps_to_remove
    }
    data["process_steps"].update({"enrich_metadata": "", "generate_html": ""})

    # Identify and process the correct version and its relative versions
    ordnungsnummer = data["doc_info"].get("ordnungsnummer")
    current_nachtragsnummer = data["doc_info"].get("nachtragsnummer")

    if current_nachtragsnummer is None:
        return

    found_version = None
    older_versions = []
    newer_versions = []

    for record in source_data:
        if record.get("ordnungsnummer") == ordnungsnummer:
            erlasstitel = record.get("erlasstitel")
            versions_list = record.get("versions", [])
            for version in versions_list:
                version_nachtragsnummer = version.get("nachtragsnummer")
                if version_nachtragsnummer == current_nachtragsnummer:
                    found_version = version
                elif version_nachtragsnummer < current_nachtragsnummer:
                    older_versions.append(version)
                elif version_nachtragsnummer > current_nachtragsnummer:
                    newer_versions.append(version)
            break

    if found_version:
        # Replace the existing doc_info with the found version
        data["doc_info"] = found_version
        # Add erlasstitel and ordnungsnummer back
        data["doc_info"]["erlasstitel"] = erlasstitel
        data["doc_info"]["ordnungsnummer"] = ordnungsnummer
        # Add information about whether the document is in force
        if data["doc_info"]["aufhebungsdatum"] == "":
            data["doc_info"]["in_force"] = True
        else:
            data["doc_info"]["in_force"] = False
        # Add versioning
        data["doc_info"]["versions"] = {
            "older_versions": older_versions,
            "newer_versions": newer_versions,
        }
        # Save the updated data back to the file
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)


def fix_metadata(root_folder, source_json_path):
    # Walk through each file in the specified folder and update metadata for files ending with '-metadata.json'
    for root, dirs, files in os.walk(root_folder):
        for file in files:
            if file.endswith("-metadata.json"):
                file_path = os.path.join(root, file)

                # Load the JSON data from the specified source path
                # (I don't understand why the source data has to be reloaded for each file but otherwise a circular reference occurs)
                with open(source_json_path, "r") as f:
                    source_data = json.load(f)
                update_file(file_path, source_data)


# Example usage of the function
folder_path = "data/zhlex/zhlex_files"
source_json_path = "data/zhlex/zhlex_data/zhlex_data_processed.json"
fix_metadata(folder_path, source_json_path)
