#!/usr/bin/env python3
import os
import json

# The output file where consolidated metadata will be stored.
OUTPUT_FILE = "data/fedlex/fedlex_data/fedlex_data_processed.json"
# The base directory where individual metadata files are stored.
BASE_DIR = "data/fedlex/fedlex_files"


def extract_version_data(doc_info):
    """
    From a doc_info dictionary, extract the keys that belong to a version record.
    """
    keys = [
        "law_page_url",
        "law_text_url",
        "law_text_redirect",
        "nachtragsnummer",
        "numeric_nachtragsnummer",
        "erlassdatum",
        "inkraftsetzungsdatum",
        "publikationsdatum",
        "aufhebungsdatum",
        "in_force",
        "bandnummer",
        "hinweise",
    ]
    return {key: doc_info.get(key, "") for key in keys}


def normalize_ordnungsnummer(ordnungsnummer):
    """
    For consolidation, if the ordnungsnummer starts with "0." then strip it off.
    For example, "0.101" becomes "101". Otherwise return it as is.
    """
    ordnungsnummer = ordnungsnummer.strip()
    if ordnungsnummer.startswith("0."):
        return ordnungsnummer[2:]
    return ordnungsnummer


def consolidate_metadata():
    """
    Walk through BASE_DIR and load every metadata file (files ending with "-metadata.json").
    Group files by law (using a normalized ordnungsnummer) and create one consolidated record per law.
    """
    consolidated = {}  # key: normalized ordnungsnummer, value: consolidated law record

    for root, dirs, files in os.walk(BASE_DIR):
        for file in files:
            if file.endswith("-metadata.json"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception as e:
                    print(f"Error loading {file_path}: {e}")
                    continue

                doc_info = data.get("doc_info", {})
                # Use the doc_info["ordnungsnummer"] as the law identifier.
                orig_ordnungsnummer = doc_info.get("ordnungsnummer", "").strip()
                if not orig_ordnungsnummer:
                    print(f"Warning: No ordnungsnummer in {file_path}. Skipping.")
                    continue

                # Normalize the ordnungsnummer for grouping.
                law_key = normalize_ordnungsnummer(orig_ordnungsnummer)

                # If we haven't seen this law yet, create a new record.
                if law_key not in consolidated:
                    consolidated[law_key] = {
                        "ordnungsnummer": law_key,
                        # Use the first file's top-level information.
                        "erlasstitel": doc_info.get("erlasstitel", ""),
                        "dynamic_source": doc_info.get("dynamic_source", ""),
                        "zhlaw_url_dynamic": doc_info.get("zhlaw_url_dynamic", ""),
                        "category": doc_info.get("category", None),
                        "abkuerzung": doc_info.get("abkuerzung", ""),
                        "kurztitel": doc_info.get("kurztitel", ""),
                        "versions": [],
                    }
                # Append the version record.
                version_record = extract_version_data(doc_info)
                consolidated[law_key]["versions"].append(version_record)

    # Optionally, sort the versions for each law by numeric_nachtragsnummer (largest first).
    for law in consolidated.values():
        try:
            law["versions"].sort(
                key=lambda v: float(v.get("numeric_nachtragsnummer", 0)), reverse=True
            )
        except Exception as e:
            print(f"Error sorting versions for law {law.get('ordnungsnummer')}: {e}")

    # Convert the consolidated dictionary to a list.
    consolidated_list = list(consolidated.values())
    return consolidated_list


def main():
    consolidated_data = consolidate_metadata()
    try:
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(consolidated_data, f, ensure_ascii=False, indent=4)
        print(f"Consolidated data written to {OUTPUT_FILE}")
    except Exception as e:
        print(f"Error writing consolidated file: {e}")


if __name__ == "__main__":
    main()
