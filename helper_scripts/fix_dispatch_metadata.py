import os
import json


def rename_title_in_json(folder_path):
    # Walk through all directories and files in the provided folder path
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            # Check if the file ends with '-metadata.json'
            if file.endswith("-metadata.json"):
                full_path = os.path.join(root, file)
                # Open the JSON file for reading and loading its content
                with open(full_path, "r", encoding="utf-8") as json_file:
                    data = json.load(json_file)

                # Check if the key 'title' exists in 'doc_info' and is not already 'erlasstitel'
                if (
                    "title" in data["doc_info"]
                    and "erlasstitel" not in data["doc_info"]
                ):
                    # Rename the key
                    data["doc_info"]["erlasstitel"] = data["doc_info"].pop("title")

                    # Write the modified data back to the JSON file
                    with open(full_path, "w", encoding="utf-8") as json_file:
                        json.dump(data, json_file, indent=4, ensure_ascii=False)
                    print(f"Updated file: {full_path}")
                else:
                    print(f"No update needed for file: {full_path}")


# Specify the path to the folder containing the JSON files
folder_path = "zhlaw/data/krzh_dispatch/krzh_dispatch_files"
rename_title_in_json(folder_path)
