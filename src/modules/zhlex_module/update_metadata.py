"""Module for updating metadata files with enriched information.

This module processes existing metadata files and enriches them with additional information
from the scraped ZH-Lex data. It matches files based on law numbers (ordnungsnummer) and
updates metadata with detailed document information, version data, and processing timestamps.

Key features:
- Updates existing metadata files with enriched information
- Handles missing or corrupted metadata files gracefully
- Extracts metadata from filenames when necessary
- Matches files to source data by ordnungsnummer
- Updates version-specific information
- Preserves existing processing timestamps
- Creates valid metadata structures for files without proper metadata

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""


import os
import json
import arrow
from src.utils.logging_utils import get_module_logger

# Get logger from main module
logger = get_module_logger(__name__)

timestamp = arrow.now().format("YYYYMMDD-HHmmss")


def update_file(file_path, source_data):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                logger.warning(
                    f"Invalid or empty metadata file: {file_path}, creating new one."
                )
                # Create a default metadata structure
                data = {
                    "doc_info": {},
                    "process_steps": {
                        "crop_pdf": timestamp,
                        "call_api_law": timestamp,
                        "call_api_marginalia": timestamp,
                        "generate_html": timestamp,
                    },
                }
    except FileNotFoundError:
        logger.warning(f"Metadata file not found: {file_path}, creating new one.")
        # Create a default metadata structure
        data = {
            "doc_info": {},
            "process_steps": {
                "crop_pdf": timestamp,
                "call_api_law": timestamp,
                "call_api_marginalia": timestamp,
                "generate_html": timestamp,
            },
        }

    # Extract filename components to populate basic metadata if missing
    try:
        filename = os.path.basename(file_path)
        parts = filename.split("-")
        if len(parts) >= 2:
            ordnungsnummer = parts[0]
            nachtragsnummer = parts[1]

            # Set basic ordnungsnummer/nachtragsnummer if not present
            if "doc_info" not in data:
                data["doc_info"] = {}

            if (
                "ordnungsnummer" not in data["doc_info"]
                or not data["doc_info"]["ordnungsnummer"]
            ):
                data["doc_info"]["ordnungsnummer"] = ordnungsnummer

            if (
                "nachtragsnummer" not in data["doc_info"]
                or not data["doc_info"]["nachtragsnummer"]
            ):
                data["doc_info"]["nachtragsnummer"] = nachtragsnummer
    except Exception as e:
        logger.warning(f"Error extracting metadata from filename {file_path}: {e}")

    # Identify and process the correct version based on ordnungsnummer
    ordnungsnummer = data["doc_info"].get("ordnungsnummer")

    if ordnungsnummer is None:
        logger.warning(f"No ordnungsnummer found in {file_path}, skipping.")
        # Save the default data anyway to create a valid JSON file
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return

    found_record = None

    for record in source_data:
        if record.get("ordnungsnummer") == ordnungsnummer:
            found_record = record
            break

    if found_record:
        current_nachtragsnummer = data["doc_info"].get("nachtragsnummer")
        # Get nachtragsnummer from filename, where the number is stated after the first "-", e.g. "102-026-original.pdf" -> "026"
        if current_nachtragsnummer is None:
            try:
                current_nachtragsnummer = file_path.split("-")[1]
                data["doc_info"]["nachtragsnummer"] = current_nachtragsnummer
            except IndexError:
                logger.warning(
                    f"Cannot extract nachtragsnummer from file path: {file_path}"
                )
                current_nachtragsnummer = ""

        found_version = None
        older_versions = []
        newer_versions = []

        versions_list = found_record.get("versions", [])
        for version in versions_list:
            version_nachtragsnummer = version.get("nachtragsnummer")
            if version_nachtragsnummer == current_nachtragsnummer:
                found_version = version
            elif version_nachtragsnummer < current_nachtragsnummer:
                older_versions.append(version)
            elif version_nachtragsnummer > current_nachtragsnummer:
                newer_versions.append(version)

        if found_version:
            # Create a fresh doc_info structure - don't reference the found_version directly
            new_doc_info = {}

            # Copy primitive values from found_version to avoid reference issues
            for key, value in found_version.items():
                if key != "versions":  # Skip any existing versions key
                    new_doc_info[key] = value

            # Replace doc_info with our fresh structure
            data["doc_info"] = new_doc_info

            # Add erlasstitel and ordnungsnummer back
            data["doc_info"]["erlasstitel"] = found_record.get("erlasstitel", "")
            data["doc_info"]["ordnungsnummer"] = found_record.get("ordnungsnummer", "")
            data["doc_info"]["kurztitel"] = found_record.get("kurztitel", "")
            data["doc_info"]["abkuerzung"] = found_record.get("abkuerzung", "")

            # Safely handle category which might be complex
            if isinstance(found_record.get("category"), dict):
                # Create a deep copy of category
                category_dict = {}
                source_category = found_record.get("category", {})
                for cat_key, cat_value in source_category.items():
                    if isinstance(cat_value, dict):
                        category_dict[cat_key] = {k: v for k, v in cat_value.items()}
                    else:
                        category_dict[cat_key] = cat_value
                data["doc_info"]["category"] = category_dict
            else:
                data["doc_info"]["category"] = found_record.get("category", "")

            data["doc_info"]["dynamic_source"] = found_record.get("dynamic_source", "")
            data["doc_info"]["zhlaw_url_dynamic"] = found_record.get(
                "zhlaw_url_dynamic", ""
            )

            # Add information about whether the document is in force
            if data["doc_info"].get("aufhebungsdatum", "") == "":
                data["doc_info"]["in_force"] = True
            else:
                data["doc_info"]["in_force"] = False

            # Create fresh copies of version arrays to avoid reference issues
            older_versions_copy = []
            for v in older_versions:
                older_versions_copy.append({k: v for k, v in v.items()})

            newer_versions_copy = []
            for v in newer_versions:
                newer_versions_copy.append({k: v for k, v in v.items()})

            # Add versioning
            data["doc_info"]["versions"] = {
                "older_versions": older_versions_copy,
                "newer_versions": newer_versions_copy,
            }
        else:
            logger.warning(
                f"No matching version found for {file_path} with nachtragsnummer {current_nachtragsnummer}"
            )
            # Add minimal metadata from found_record
            data["doc_info"]["erlasstitel"] = found_record.get("erlasstitel", "")
            data["doc_info"]["kurztitel"] = found_record.get("kurztitel", "")
            data["doc_info"]["abkuerzung"] = found_record.get("abkuerzung", "")
            data["doc_info"]["category"] = found_record.get("category", "")
            data["doc_info"]["dynamic_source"] = found_record.get("dynamic_source", "")
            data["doc_info"]["zhlaw_url_dynamic"] = found_record.get(
                "zhlaw_url_dynamic", ""
            )
            # Add versioning
            data["doc_info"]["versions"] = {
                "older_versions": older_versions,
                "newer_versions": newer_versions,
            }

    # Save the updated data back to the file
    try:
        # Create a serializable copy by converting to and from a string
        # This breaks circular references
        try:
            # First attempt: Try standard serialization
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except (TypeError, ValueError, RecursionError) as e:
            if "Circular reference detected" in str(e):
                logger.warning(
                    f"Circular reference detected in {file_path}, attempting to fix..."
                )

                # Second attempt: Break circular references by deep-copying only serializable parts
                import copy

                # Helper function to create a safe copy that breaks circular references
                def safe_copy(obj, seen=None):
                    if seen is None:
                        seen = set()

                    # Get object ID to detect cycles
                    obj_id = id(obj)
                    if obj_id in seen:
                        return None  # Break the cycle

                    seen.add(obj_id)

                    if isinstance(obj, dict):
                        return {k: safe_copy(v, seen.copy()) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [safe_copy(item, seen.copy()) for item in obj]
                    else:
                        return copy.deepcopy(obj)

                # Create a clean copy
                clean_data = safe_copy(data)

                # Write the clean copy
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(clean_data, f, ensure_ascii=False, indent=4)
            else:
                raise
    except Exception as e:
        logger.error(f"Error writing updated metadata to {file_path}: {e}")
        # As a last resort, try to save at least the basic structure
        try:
            basic_data = {
                "doc_info": {
                    "ordnungsnummer": data.get("doc_info", {}).get(
                        "ordnungsnummer", ""
                    ),
                    "nachtragsnummer": data.get("doc_info", {}).get(
                        "nachtragsnummer", ""
                    ),
                    "erlasstitel": data.get("doc_info", {}).get("erlasstitel", ""),
                },
                "process_steps": data.get("process_steps", {}),
            }
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(basic_data, f, ensure_ascii=False, indent=4)
            logger.info(f"Saved simplified metadata for {file_path} after error")
        except Exception as nested_e:
            logger.error(
                f"Final attempt to save metadata failed for {file_path}: {nested_e}"
            )


def main(root_folder, source_json_path):
    # Load the JSON data from the specified source path
    try:
        with open(source_json_path, "r", encoding="utf-8") as f:
            try:
                source_data = json.load(f)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in source file: {source_json_path}")
                return
    except FileNotFoundError:
        logger.error(f"Source JSON file not found: {source_json_path}")
        return
    except Exception as e:
        logger.error(f"Error reading source JSON file {source_json_path}: {e}")
        return

    # Walk through each file in the specified folder and update metadata for files ending with '-metadata.json'
    for root, dirs, files in os.walk(root_folder):
        for file in files:
            if file.endswith("-metadata.json"):
                file_path = os.path.join(root, file)
                try:
                    update_file(file_path, source_data)
                except Exception as e:
                    logger.error(f"Error updating metadata for {file_path}: {e}")


if __name__ == "__main__":
    main()
