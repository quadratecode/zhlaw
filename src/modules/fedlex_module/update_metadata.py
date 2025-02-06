#!/usr/bin/env python3
import os
import json
import re
import time
import requests

# --- Part 1. Functions: SPARQL query and dynamic_source ---

SPARQL_ENDPOINT = "https://fedlex.data.admin.ch/sparqlendpoint"


def get_aufhebungsdatum(sr_notation):
    query = f"""
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
PREFIX skos:  <http://www.w3.org/2004/02/skos/core#>

SELECT DISTINCT (str(?aufhebungsdatum) AS ?aufhebungsdatum)
WHERE {{
  ?consoAbstract a jolux:ConsolidationAbstract .
  ?consoAbstract jolux:classifiedByTaxonomyEntry/skos:notation ?srNotation .
  FILTER(str(?srNotation) = "{sr_notation}")
  OPTIONAL {{ ?consoAbstract jolux:aufhebungsdatum ?aufhebungsdatum . }}
}}
LIMIT 1
    """
    try:
        response = requests.get(
            SPARQL_ENDPOINT, params={"query": query, "format": "json"}, timeout=20
        )
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error querying SPARQL for {sr_notation}: {e}")
        time.sleep(1)
        return ""
    try:
        result_json = response.json()
    except ValueError as e:
        print(f"Error decoding JSON response for {sr_notation}: {e}")
        time.sleep(1)
        return ""
    bindings = result_json.get("results", {}).get("bindings", [])
    time.sleep(1)
    if bindings:
        return bindings[0].get("aufhebungsdatum", {}).get("value", "")
    else:
        return ""


def compute_dynamic_source(law_text_url):
    pattern = r"^https://fedlex\.data\.admin\.ch/filestore/fedlex\.data\.admin\.ch(\/eli\/cc\/\d+\/[^/]+)\/\d+\/(de)\/html/.*\.html$"
    match = re.match(pattern, law_text_url)
    if match:
        path_part = match.group(1)
        lang = match.group(2)
        return f"https://www.fedlex.admin.ch{path_part}/{lang}"
    else:
        print(f"Warning: law_text_url did not match expected pattern:\n{law_text_url}")
        return ""


# --- Part 2. Category Assignment Functions ---


def assign_category_codes(ordnungsnummer, is_international):
    """
    Returns a tuple (folder_code, section_code, subsection_code) computed from the ordnungsnummer.

    For Internationales Recht (is_international==True):
      - Expects a format like "0.131.1".
      - Folder = p0 + "." + first character of p1.
      - Section = p0 + "." + first two characters of p1.
      - Subsection = p0 + "." + p1, if there is a third part; otherwise None.

    For Landesrecht (is_international==False):
      - If no dot (e.g. "101"): folder = first digit, section = first two digits.
      - If one dot (e.g. "170.32"): let p1 be part before the dot and p2 the part after.
           • Folder = p1 with its last digit dropped.
           • Section = p1 + "." + first digit of p2.
           • Subsection = p1 + "." + p2.
      - If three parts are present, use p1 and p2 as above.

    Also, if the computed folder or section equals the entire ordnungsnummer, they are omitted.
    """
    if is_international:
        parts = ordnungsnummer.split(".")
        if len(parts) >= 2:
            p0 = parts[0]
            p1 = parts[1]
            folder_code = f"{p0}.{p1[0]}" if p1 else p0
            section_code = f"{p0}.{p1[:2]}" if len(p1) >= 2 else f"{p0}.{p1}"
            subsection_code = f"{p0}.{p1}" if len(parts) >= 3 else None
        else:
            folder_code = ordnungsnummer
            section_code = ""
            subsection_code = None
    else:
        parts = ordnungsnummer.split(".")
        if len(parts) == 1:
            if len(ordnungsnummer) >= 3:
                folder_code = ordnungsnummer[0]
                section_code = ordnungsnummer[:2]
            else:
                folder_code = ordnungsnummer
                section_code = ""
            subsection_code = None
        elif len(parts) == 2:
            p1 = parts[0]
            p2 = parts[1]
            folder_code = p1[:-1] if len(p1) > 1 else p1
            section_code = f"{p1}.{p2[0]}" if p2 else p1
            subsection_code = f"{p1}.{p2}"
        elif len(parts) >= 3:
            p1 = parts[0]
            p2 = parts[1]
            folder_code = p1[:-1] if len(p1) > 1 else p1
            section_code = f"{p1}.{p2}"
            subsection_code = ordnungsnummer
        else:
            folder_code = ""
            section_code = ""
            subsection_code = None

    if ordnungsnummer == folder_code:
        section_code = ""
        subsection_code = None
    if ordnungsnummer == section_code:
        section_code = ""
        subsection_code = None

    return folder_code, section_code, subsection_code


def find_in_tree(target, tree):
    """
    Searches for a key exactly matching target in the given tree (dict).
    If tree is None, returns an empty string.
    If an exact match is not found, attempts a prefix search.
    Searches recursively in children under keys "folders", "sections", and "subsections".
    Returns the found "name" (or an empty string if not found).
    """
    if tree is None:
        return ""
    # Try an exact match:
    if target in tree:
        val = tree[target]
        if isinstance(val, dict) and "name" in val:
            return val["name"]
        elif isinstance(val, str):
            return val
    # Try prefix matching:
    for key, val in tree.items():
        if key.startswith(target):
            if isinstance(val, dict) and "name" in val:
                return val["name"]
            elif isinstance(val, str):
                return val
    # Recursively search in children:
    for key, val in tree.items():
        if isinstance(val, dict):
            for child_key in ("folders", "sections", "subsections"):
                child = val.get(child_key, {})
                if child is None:
                    child = {}
                result = find_in_tree(target, child)
                if result:
                    return result
    return ""


def assign_category_to_metadata(doc_info, fedlex_hierarchy):
    """
    Updates doc_info["category"] by looking up the computed folder, section and subsection
    in the fedlex hierarchy (which now uses keys "folders", then "sections", then "subsections").
    The law’s own number is not stored; only the hierarchy‐assigned folder/section/subsection.
    If a given level is not found or is empty, that field is set to None.
    """
    ordnungsnummer = doc_info.get("ordnungsnummer", "")
    if not ordnungsnummer:
        return

    is_international = ordnungsnummer.strip().startswith("0")
    branch = "A" if is_international else "B"
    branch_data = fedlex_hierarchy.get(branch, {})
    folders_tree = branch_data.get("folders", {})

    folder_code, section_code, subsection_code = assign_category_codes(
        ordnungsnummer, is_international
    )

    folder_name = find_in_tree(folder_code, folders_tree)
    section_name = ""
    subsection_name = ""

    if section_code:
        folder_item = folders_tree.get(folder_code, {})
        sections_tree = (
            folder_item.get("sections", {}) if isinstance(folder_item, dict) else {}
        )
        if sections_tree is None:
            sections_tree = {}
        section_name = find_in_tree(section_code, sections_tree)
    if subsection_code:
        folder_item = folders_tree.get(folder_code, {})
        sections_tree = (
            folder_item.get("sections", {}) if isinstance(folder_item, dict) else {}
        )
        if sections_tree is None:
            sections_tree = {}
        section_item = (
            sections_tree.get(section_code, {}) if section_code in sections_tree else {}
        )
        subsections_tree = (
            section_item.get("subsections", {})
            if isinstance(section_item, dict)
            else {}
        )
        if subsections_tree is None:
            subsections_tree = {}
        subsection_name = find_in_tree(subsection_code, subsections_tree)

    doc_info["category"] = {
        "folder": {"id": folder_code, "name": folder_name} if folder_code else None,
        "section": {"id": section_code, "name": section_name} if section_code else None,
        "subsection": (
            {"id": subsection_code, "name": subsection_name}
            if subsection_code
            else None
        ),
    }


# --- Part 3. Processing Individual Metadata Files ---


def process_metadata_file(file_path, fedlex_hierarchy):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Failed to load JSON from {file_path}: {e}")
        return

    doc_info = data.get("doc_info", {})

    # (1) Update dynamic_source from law_text_url.
    law_text_url = doc_info.get("law_text_url", "")
    doc_info["dynamic_source"] = compute_dynamic_source(law_text_url)

    # (2) Query SPARQL for aufhebungsdatum and update in_force.
    sr_notation = doc_info.get("ordnungsnummer", "")
    if sr_notation:
        aufhebungsdatum = get_aufhebungsdatum(sr_notation)
        doc_info["aufhebungsdatum"] = aufhebungsdatum
        doc_info["in_force"] = False if aufhebungsdatum else True
    else:
        print(f"No ordnungsnummer found in {file_path}; skipping SPARQL query.")
        doc_info["aufhebungsdatum"] = ""
        doc_info["in_force"] = True

    # (3) Update category based on ordnungsnummer using the new hierarchy.
    assign_category_to_metadata(doc_info, fedlex_hierarchy)

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Updated {file_path}")
    except Exception as e:
        print(f"Failed to write updated JSON to {file_path}: {e}")


# --- Part 4. Version Update Functions ---


def extract_version_data(doc_info):
    """
    From doc_info, extract a dictionary containing these keys:
      law_page_url, law_text_url, law_text_redirect, nachtragsnummer,
      numeric_nachtragsnummer, erlassdatum, inkraftsetzungsdatum, publikationsdatum,
      aufhebungsdatum, in_force, bandnummer, hinweise.
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


def update_versions_for_law_group(file_paths):
    """
    For all files (versions) of a given law (uid), update each file’s
    doc_info["versions"] with:
      - older_versions: list of version data for versions with lower numeric_nachtragsnummer
      - newer_versions: list of version data for versions with higher numeric_nachtragsnummer.
    """
    versions = []
    for fp in file_paths:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            doc_info = data.get("doc_info", {})
            try:
                num = float(doc_info.get("numeric_nachtragsnummer", 0))
            except (ValueError, TypeError):
                num = 0
            version_data = extract_version_data(doc_info)
            versions.append(
                {
                    "file_path": fp,
                    "data": data,
                    "doc_info": doc_info,
                    "numeric": num,
                    "version_data": version_data,
                }
            )
        except Exception as e:
            print(f"Error loading {fp} for version update: {e}")

    versions.sort(key=lambda x: x["numeric"])

    n = len(versions)
    for i in range(n):
        current_numeric = versions[i]["numeric"]
        older = []
        newer = []
        for j in range(n):
            if i == j:
                continue
            try:
                other_numeric = float(
                    versions[j]["doc_info"].get("numeric_nachtragsnummer", 0)
                )
            except (ValueError, TypeError):
                other_numeric = 0
            if other_numeric < current_numeric:
                older.append(versions[j]["version_data"])
            elif other_numeric > current_numeric:
                newer.append(versions[j]["version_data"])
        versions[i]["doc_info"]["versions"] = {
            "older_versions": older,
            "newer_versions": newer,
        }
        try:
            with open(versions[i]["file_path"], "w", encoding="utf-8") as f:
                json.dump(versions[i]["data"], f, ensure_ascii=False, indent=4)
            print(f"Updated versions in {versions[i]['file_path']}")
        except Exception as e:
            print(f"Error writing updated versions to {versions[i]['file_path']}: {e}")


def group_files_by_uid(base_dir):
    """
    Walk through base_dir and group metadata file paths by law uid.
    The law uid is assumed to be the name of the first folder under base_dir.
    Returns a dict mapping uid -> list of file paths.
    """
    groups = {}
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith("-metadata.json"):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, base_dir)
                parts = rel_path.split(os.sep)
                if parts:
                    uid = parts[0]
                    groups.setdefault(uid, []).append(file_path)
    return groups


# --- Part 5. Main Processing Routine ---


def main():
    hierarchy_file = "data/fedlex/fedlex_data/fedlex_cc_folders_hierarchy.json"
    try:
        with open(hierarchy_file, "r", encoding="utf-8") as f:
            fedlex_hierarchy = json.load(f)
    except Exception as e:
        print(f"Error loading hierarchy file {hierarchy_file}: {e}")
        return

    base_dir = "data/fedlex/fedlex_files"
    all_files = []

    # First pass: process each file (update dynamic_source, SPARQL, and category)
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith("-metadata.json"):
                file_path = os.path.join(root, file)
                all_files.append(file_path)
                print(f"Processing file: {file_path}")
                process_metadata_file(file_path, fedlex_hierarchy)

    # Second pass: group files by law uid and update versions info.
    groups = group_files_by_uid(base_dir)
    for uid, file_paths in groups.items():
        print(f"Updating versions for law uid {uid} with {len(file_paths)} version(s)")
        update_versions_for_law_group(file_paths)


if __name__ == "__main__":
    main()
