# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§


import os
import json


def update_file(file_path, source_data):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Identify and process the correct version based on ordnungsnummer
    ordnungsnummer = data["doc_info"].get("ordnungsnummer")

    if ordnungsnummer is None:
        return

    found_record = None

    for record in source_data:
        if record.get("ordnungsnummer") == ordnungsnummer:
            found_record = record
            break

    if found_record:
        current_nachtragsnummer = data["doc_info"].get("nachtragsnummer")
        # Get nachtragsnummer from filename, weere the number is stated after the first "-", e.g. "102-026-original.pdf" -> "026"
        if current_nachtragsnummer is None:
            current_nachtragsnummer = file_path.split("-")[1]
        found_version = None
        older_versions = []
        newer_versions = []

        versions_list = record.get("versions", [])
        for version in versions_list:
            version_nachtragsnummer = version.get("nachtragsnummer")
            if version_nachtragsnummer == current_nachtragsnummer:
                found_version = version
            elif version_nachtragsnummer < current_nachtragsnummer:
                older_versions.append(version)
            elif version_nachtragsnummer > current_nachtragsnummer:
                newer_versions.append(version)

        if found_version:
            # Replace the existing doc_info with the found version
            data["doc_info"] = found_version
            # Add erlasstitel and ordnungsnummer back
            data["doc_info"]["erlasstitel"] = found_record.get("erlasstitel", "")
            data["doc_info"]["ordnungsnummer"] = found_record.get("ordnungsnummer", "")
            data["doc_info"]["kurztitel"] = found_record.get("kurztitel", "")
            data["doc_info"]["abkuerzung"] = found_record.get("abkuerzung", "")
            data["doc_info"]["category"] = found_record.get("category", "")
            data["doc_info"]["dynamic_source"] = found_record.get("dynamic_source", "")
            data["doc_info"]["zhlaw_url_dynamic"] = found_record.get(
                "zhlaw_url_dynamic", ""
            )
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


def main(root_folder, source_json_path):
    # Walk through each file in the specified folder and update metadata for files ending with '-metadata.json'
    for root, dirs, files in os.walk(root_folder):
        for file in files:
            if file.endswith("-metadata.json"):
                file_path = os.path.join(root, file)

                # Load the JSON data from the specified source path
                with open(source_json_path, "r") as f:
                    source_data = json.load(f)
                update_file(file_path, source_data)


if __name__ == "__main__":
    main()
