import os
import json


from src.modules.zhlex_module.scrape_collection import (
    load_hierarchy,
    find_category_by_ordnungsnummer,
)


def update_categories_in_metadata():
    # 1) Load the full hierarchy once.
    hierarchy = load_hierarchy()

    # 2) Define the root folder containing your metadata files.
    root_folder = "data/zhlex/zhlex_files"

    # 3) Walk through all subfolders in data/zhlex/zhlex_files
    for dirpath, dirnames, filenames in os.walk(root_folder):
        for filename in filenames:
            # We only want to process .json files
            if filename.endswith("-metadata.json"):
                json_path = os.path.join(dirpath, filename)

                # 4) Load the metadata JSON
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except json.JSONDecodeError:
                    print(f"Skipping invalid JSON: {json_path}")
                    continue

                doc_info = data.get("doc_info", {})
                ordnungsnummer = doc_info.get("ordnungsnummer")

                # If ordnungsnummer is missing or empty, skip
                if not ordnungsnummer:
                    print(f"No ordnungsnummer found for {json_path}. Skipping.")
                    continue

                # 5) Use find_category_by_ordnungsnummer to get updated category
                updated_category = find_category_by_ordnungsnummer(
                    hierarchy, ordnungsnummer
                )

                # 6) Update the doc_info["category"] with the new result
                doc_info["category"] = updated_category
                data["doc_info"] = doc_info

                # 7) Write back the updated JSON to the same file
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)

                print(f"Updated category for {json_path}")


if __name__ == "__main__":
    update_categories_in_metadata()
