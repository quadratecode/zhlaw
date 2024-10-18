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
        # Add the erlass_kurztitel and erlass_abkrz to the doc_info
        # Values will be overwritten if key already exists
        data["doc_info"]["ordnungsnummer"] = found_record.get("ordnungsnummer", "")
        data["doc_info"]["erlasstitel"] = found_record.get("erlasstitel", "")
        data["doc_info"]["erlass_kurztitel"] = found_record.get("erlass_kurztitel", "")
        data["doc_info"]["erlass_abkrz"] = found_record.get("erlass_abkrz", "")

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
