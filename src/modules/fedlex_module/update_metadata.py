#!/usr/bin/env python3
import os
import json
import re
import time
import requests
import logging
import arrow
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- Constants and Configuration ---

SPARQL_ENDPOINT = "https://fedlex.data.admin.ch/sparqlendpoint"
REQUEST_TIMEOUT = 60  # Increased timeout for SPARQL queries
BATCH_SIZE = 30  # Reduced batch size for better reliability
DELAY_BETWEEN_REQUESTS = 0.5  # Increased delay between API requests
MAX_RETRIES = 3  # Maximum number of retry attempts for failed requests

# --- Optimized SPARQL Queries ---


def batch_get_aufhebungsdatum(sr_notations):
    """
    Retrieves aufhebungsdatum for multiple SR notations in a single SPARQL query.

    Args:
        sr_notations: List of SR notations

    Returns:
        Dictionary mapping SR notations to their aufhebungsdatum
    """
    if not sr_notations:
        return {}

    # Generate FILTER clause for the query
    filter_values = " || ".join(
        [f'str(?srNotation) = "{notation}"' for notation in sr_notations]
    )

    query = f"""
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
PREFIX skos:  <http://www.w3.org/2004/02/skos/core#>

SELECT DISTINCT ?srNotation (str(?aufhebungsdatum) AS ?aufhebungsdatum)
WHERE {{
  ?consoAbstract a jolux:ConsolidationAbstract .
  ?consoAbstract jolux:classifiedByTaxonomyEntry/skos:notation ?srNotation .
  FILTER({filter_values})
  OPTIONAL {{ ?consoAbstract jolux:aufhebungsdatum ?aufhebungsdatum . }}
}}
    """

    retries = 0
    while retries < MAX_RETRIES:
        try:
            logger.info(
                f"Querying aufhebungsdatum for {len(sr_notations)} SR notations (attempt {retries+1})"
            )
            response = requests.get(
                SPARQL_ENDPOINT,
                params={"query": query, "format": "json"},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()

            # Check if response contains valid JSON
            if not response.text or response.text.isspace():
                logger.warning(
                    f"Empty response from SPARQL endpoint (attempt {retries+1})"
                )
                retries += 1
                time.sleep(DELAY_BETWEEN_REQUESTS * 2)
                continue

            result_json = response.json()

            results = {}
            for binding in result_json.get("results", {}).get("bindings", []):
                sr_notation = binding.get("srNotation", {}).get("value", "")
                aufhebungsdatum = binding.get("aufhebungsdatum", {}).get("value", "")
                if sr_notation:
                    results[sr_notation] = aufhebungsdatum

            time.sleep(DELAY_BETWEEN_REQUESTS)
            return results

        except json.JSONDecodeError as je:
            logger.error(
                f"JSON decode error in aufhebungsdatum query (attempt {retries+1}): {je}"
            )
            retries += 1
            time.sleep(DELAY_BETWEEN_REQUESTS * 2)
        except requests.exceptions.Timeout as te:
            logger.error(
                f"Timeout in aufhebungsdatum query (attempt {retries+1}): {te}"
            )
            retries += 1
            time.sleep(DELAY_BETWEEN_REQUESTS * 3)
        except Exception as e:
            logger.error(
                f"Error in batch query for aufhebungsdatum (attempt {retries+1}): {e}"
            )
            retries += 1
            time.sleep(DELAY_BETWEEN_REQUESTS * 2)

    logger.error(f"Failed to retrieve aufhebungsdatum after {MAX_RETRIES} attempts")
    return {}


def batch_get_all_versions(sr_notations):
    """
    Retrieves all versions for multiple SR notations in a single query.

    Args:
        sr_notations: List of SR notations to query

    Returns:
        Dictionary mapping each SR notation to a list of its versions
    """
    if not sr_notations:
        return {}

    # Generate FILTER clause
    filter_values = " || ".join(
        [f'str(?srNotation) = "{notation}"' for notation in sr_notations]
    )

    query = f"""
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
PREFIX skos:  <http://www.w3.org/2004/02/skos/core#>
PREFIX xsd:   <http://www.w3.org/2001/XMLSchema#>

SELECT DISTINCT
  ?srNotation
  (str(?dateApplicabilityNode) AS ?dateApplicability) 
  ?title 
  ?abbreviation 
  ?titleAlternative 
  (str(?dateDocumentNode) AS ?dateDocument) 
  (str(?dateEntryInForceNode) AS ?dateEntryInForce) 
  (str(?publicationDateNode) AS ?publicationDate) 
  (str(?languageNotation) AS ?languageTag) 
  (str(?fileFormatNode) AS ?fileFormat)
  (str(?aufhebungsdatum) AS ?aufhebungsdatum)
  (str(?firstPublicationDateNode) AS ?firstPublicationDate)
  ?basicAct
  ?fileURL
WHERE {{
  # Use German as the language filter (DEU and "de")
  BIND(<http://publications.europa.eu/resource/authority/language/DEU> AS ?language)
  
  # Find consolidation for the specific SR notation
  ?consoAbstract a jolux:ConsolidationAbstract .
  ?consoAbstract jolux:classifiedByTaxonomyEntry/skos:notation ?srNotation .
  FILTER({filter_values})
  
  # Get all consolidations for this abstract
  ?consolidation jolux:isMemberOf ?consoAbstract .
  ?consolidation a jolux:Consolidation .
  ?consolidation jolux:dateApplicability ?dateApplicabilityNode .
  
  # Get the expression and manifestation
  ?consolidation jolux:isRealizedBy ?consoExpression .
  ?consoExpression jolux:language ?language .
  ?consoExpression jolux:isEmbodiedBy ?manifestation .
  
  # Retrieve the file URL and file format from the manifestation
  ?manifestation jolux:isExemplifiedBy ?fileURL .
  ?manifestation jolux:userFormat/skos:notation ?fileFormatNode .
  FILTER(datatype(?fileFormatNode) = <https://fedlex.data.admin.ch/vocabulary/notation-type/uri-suffix>)
  FILTER(str(?fileFormatNode) = "html")
  
  # Abstract dates and title information
  ?consoAbstract jolux:dateDocument ?dateDocumentNode .
  OPTIONAL {{ ?consoAbstract jolux:dateEntryInForce ?dateEntryInForceNode . }}
  OPTIONAL {{ ?consoAbstract jolux:publicationDate ?publicationDateNode . }}
  
  # Get title information
  ?consoAbstract jolux:isRealizedBy ?consoAbstractExpression .
  ?consoAbstractExpression jolux:language ?languageConcept .
  ?consoAbstractExpression jolux:title ?title .
  OPTIONAL {{ ?consoAbstractExpression jolux:titleShort ?abbreviation . }}
  OPTIONAL {{ ?consoAbstractExpression jolux:titleAlternative ?titleAlternative . }}
  
  # Optionally retrieve the "aufhebungsdatum" if available
  OPTIONAL {{
    ?consoAbstract jolux:aufhebungsdatum ?aufhebungsdatum .
  }}
  
  # Additional properties
  OPTIONAL {{
    ?consoAbstract <http://cogni.internal.system/model#firstPublicationDate> ?firstPublicationDateNode .
  }}
  OPTIONAL {{
    ?consoAbstract <http://data.legilux.public.lu/resource/ontology/jolux#basicAct> ?basicAct .
  }}
  
  # Language filter on the abstract expression
  ?languageConcept skos:notation ?languageNotation .
  FILTER(datatype(?languageNotation) = <http://publications.europa.eu/ontology/euvoc#XML_LNG>)
  FILTER(str(?languageNotation) = "de")
}}
ORDER BY ?srNotation ?dateApplicabilityNode
    """

    retries = 0
    while retries < MAX_RETRIES:
        try:
            logger.info(
                f"Batch querying versions for {len(sr_notations)} SR notations (attempt {retries+1})"
            )
            response = requests.get(
                SPARQL_ENDPOINT,
                params={"query": query, "format": "json"},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()

            # Check if response contains valid JSON
            if not response.text or response.text.isspace():
                logger.warning(
                    f"Empty response from SPARQL endpoint (attempt {retries+1})"
                )
                retries += 1
                time.sleep(DELAY_BETWEEN_REQUESTS * 2)
                continue

            result_json = response.json()

            # Group results by SR notation
            results = {}
            for binding in result_json.get("results", {}).get("bindings", []):
                sr_notation = binding.get("srNotation", {}).get("value", "")
                if not sr_notation:
                    continue

                if sr_notation not in results:
                    results[sr_notation] = []

                version = {
                    "dateApplicability": binding.get("dateApplicability", {}).get(
                        "value", ""
                    ),
                    "title": binding.get("title", {}).get("value", ""),
                    "abbreviation": binding.get("abbreviation", {}).get("value", ""),
                    "titleAlternative": binding.get("titleAlternative", {}).get(
                        "value", ""
                    ),
                    "dateDocument": binding.get("dateDocument", {}).get("value", ""),
                    "dateEntryInForce": binding.get("dateEntryInForce", {}).get(
                        "value", ""
                    ),
                    "publicationDate": binding.get("publicationDate", {}).get(
                        "value", ""
                    ),
                    "languageTag": binding.get("languageTag", {}).get("value", ""),
                    "fileFormat": binding.get("fileFormat", {}).get("value", ""),
                    "aufhebungsdatum": binding.get("aufhebungsdatum", {}).get(
                        "value", ""
                    ),
                    "firstPublicationDate": binding.get("firstPublicationDate", {}).get(
                        "value", ""
                    ),
                    "basicAct": binding.get("basicAct", {}).get("value", ""),
                    "fileURL": binding.get("fileURL", {}).get("value", ""),
                }
                results[sr_notation].append(version)

            logger.info(f"Retrieved version data for {len(results)} SR notations")
            time.sleep(DELAY_BETWEEN_REQUESTS)
            return results

        except json.JSONDecodeError as je:
            logger.error(
                f"JSON decode error in versions query (attempt {retries+1}): {je}"
            )
            retries += 1
            time.sleep(DELAY_BETWEEN_REQUESTS * 2)
        except requests.exceptions.Timeout as te:
            logger.error(f"Timeout in versions query (attempt {retries+1}): {te}")
            retries += 1
            time.sleep(DELAY_BETWEEN_REQUESTS * 3)
        except Exception as e:
            logger.error(
                f"Error in batch query for versions (attempt {retries+1}): {e}"
            )
            retries += 1
            time.sleep(DELAY_BETWEEN_REQUESTS * 2)

    logger.error(f"Failed to retrieve versions after {MAX_RETRIES} attempts")
    return {}


def format_date(date_str):
    """
    Uses arrow to parse a date string and format it as YYYYMMDD.
    If parsing fails or the string is empty, returns an empty string.
    """
    if not date_str:
        return ""
    try:
        dt = arrow.get(date_str)
        return dt.format("YYYYMMDD")
    except Exception as e:
        logger.warning(f"Error parsing date '{date_str}': {e}")
        return ""


def download_missing_versions(missing_versions, sr_notation, base_dir):
    """
    Downloads missing versions of laws.

    Args:
        missing_versions: List of version dictionaries with metadata
        sr_notation: The SR notation of the law
        base_dir: Base directory where files should be saved

    Returns:
        Number of successfully downloaded versions
    """
    success_count = 0

    for version in missing_versions:
        # Extract and format dates
        dateApplicability_raw = version.get("dateApplicability", "").strip()
        dateDocument_raw = version.get("dateDocument", "").strip()
        dateEntryInForce_raw = version.get("dateEntryInForce", "").strip()
        publicationDate_raw = version.get("publicationDate", "").strip()
        aufhebungsdatum_raw = version.get("aufhebungsdatum", "").strip()
        fileURL = version.get("fileURL", "").strip()
        title = version.get("title", "").strip()
        abbreviation = version.get("abbreviation", "").strip()
        titleAlternative = version.get("titleAlternative", "").strip()

        # Format dates
        dateApplicability = format_date(dateApplicability_raw)
        erlassdatum = format_date(dateDocument_raw)
        inkraftsetzungsdatum = format_date(dateEntryInForce_raw)
        publikationsdatum = (
            format_date(publicationDate_raw)
            if publicationDate_raw
            else dateApplicability
        )
        aufhebungsdatum = format_date(aufhebungsdatum_raw)

        # Compute numeric_nachtragsnummer as a float (e.g. 20250203.0) if possible
        try:
            numeric_nachtragsnummer = (
                float(dateApplicability) if dateApplicability else None
            )
        except Exception as e:
            logger.warning(
                f"Error converting dateApplicability '{dateApplicability}' to numeric: {e}"
            )
            numeric_nachtragsnummer = None

        # Build the output directory structure: base_dir/sr_notation/dateApplicability
        folder_path = os.path.join(base_dir, sr_notation, dateApplicability)
        os.makedirs(folder_path, exist_ok=True)

        # Define the filenames for the raw HTML and metadata JSON
        raw_html_filename = f"{sr_notation}-{dateApplicability}-raw.html"
        metadata_filename = f"{sr_notation}-{dateApplicability}-metadata.json"
        raw_html_path = os.path.join(folder_path, raw_html_filename)
        metadata_path = os.path.join(folder_path, metadata_filename)

        # Skip processing if the files already exist
        if os.path.exists(raw_html_path) and os.path.exists(metadata_path):
            logger.debug(
                f"Files for law {sr_notation} (applicability date: {dateApplicability}) already exist. Skipping."
            )
            continue

        # Download the HTML file from fileURL
        logger.info(
            f"Downloading HTML for law {sr_notation} (applicability date: {dateApplicability})..."
        )

        retries = 0
        download_success = False

        while retries < MAX_RETRIES and not download_success:
            try:
                response = requests.get(fileURL, timeout=REQUEST_TIMEOUT)
                if response.status_code == 200:
                    # Set the encoding to the apparent encoding so that special characters are decoded correctly
                    response.encoding = response.apparent_encoding
                    html_text = response.text
                    with open(raw_html_path, "w", encoding="utf-8") as f:
                        f.write(html_text)
                    download_success = True
                else:
                    logger.warning(
                        f"HTTP error {response.status_code} when downloading {fileURL} (attempt {retries+1})"
                    )
                    retries += 1
                    time.sleep(DELAY_BETWEEN_REQUESTS)
            except Exception as e:
                logger.error(f"Error downloading {fileURL} (attempt {retries+1}): {e}")
                retries += 1
                time.sleep(DELAY_BETWEEN_REQUESTS)

        if not download_success:
            logger.error(
                f"Failed to download {sr_notation}-{dateApplicability} after {MAX_RETRIES} attempts"
            )
            continue

        # Build the metadata JSON structure
        metadata = {
            "doc_info": {
                "law_page_url": "",
                "law_text_url": fileURL,
                "law_text_redirect": "",
                "nachtragsnummer": dateApplicability,  # as string in YYYYMMDD format
                "numeric_nachtragsnummer": numeric_nachtragsnummer,  # e.g., 20250203.0
                "erlassdatum": erlassdatum,
                "inkraftsetzungsdatum": inkraftsetzungsdatum,
                "publikationsdatum": publikationsdatum,
                "aufhebungsdatum": aufhebungsdatum,
                "in_force": not bool(aufhebungsdatum),
                "bandnummer": "",
                "hinweise": "",
                "erlasstitel": title,
                "ordnungsnummer": sr_notation,
                "kurztitel": titleAlternative,
                "abkuerzung": abbreviation,
                "category": {
                    "folder": {"id": 0, "name": ""},
                    "section": {"id": 0, "name": ""},
                    "subsection": None,
                },
                "dynamic_source": "",
                "zhlaw_url_dynamic": "",
                "versions": {"older_versions": [], "newer_versions": []},
            },
            "process_steps": {
                "download": arrow.now().format("YYYYMMDD-HHmmss"),
                "process": "",
            },
        }

        # Save the metadata JSON file
        with open(metadata_path, "w", encoding="utf-8") as meta_file:
            json.dump(metadata, meta_file, indent=4, ensure_ascii=False)

        logger.info(f"Saved HTML to: {raw_html_path}")
        logger.info(f"Saved metadata to: {metadata_path}")
        success_count += 1

        # Add a delay between processing each record for server compatibility
        time.sleep(DELAY_BETWEEN_REQUESTS)

    return success_count


def identify_missing_versions(all_versions, scraped_versions_dirs):
    """
    Identifies versions that need to be scraped.
    Only includes versions newer than the oldest scraped version.

    Args:
        all_versions: List of all versions from SPARQL
        scraped_versions_dirs: List of directory names (date strings) of already scraped versions

    Returns:
        List of versions that need to be scraped
    """
    # No scraped versions yet, return all versions
    if not scraped_versions_dirs:
        return all_versions

    # Find the oldest scraped version date
    try:
        oldest_scraped_date = min(scraped_versions_dirs)
    except ValueError:
        # If we can't determine the oldest version, be conservative and return nothing
        return []

    # Filter all_versions to only include versions newer than the oldest scraped version
    # and exclude versions that are already scraped
    missing_versions = []
    for version in all_versions:
        date_str = version.get("dateApplicability", "")
        # Convert to YYYYMMDD format
        try:
            date_obj = arrow.get(date_str)
            formatted_date = date_obj.format("YYYYMMDD")

            # Check if this version is newer than the oldest scraped version
            # and not already scraped
            if (
                formatted_date >= oldest_scraped_date
                and formatted_date not in scraped_versions_dirs
            ):
                missing_versions.append(version)
        except Exception as e:
            logger.warning(f"Error processing date {date_str}: {e}")

    logger.info(
        f"Identified {len(missing_versions)} missing versions newer than {oldest_scraped_date}"
    )
    return missing_versions


def process_law_versions_batched(sr_notations, base_dir):
    """
    Process multiple laws in a batch, retrieving versions and downloading missing versions.

    Args:
        sr_notations: List of SR notations to process
        base_dir: Base directory where files are stored

    Returns:
        Dictionary mapping SR notations to the number of new versions downloaded
    """
    # Split sr_notations into batches to avoid overwhelming the SPARQL endpoint
    total_sr_notations = len(sr_notations)
    results = {}

    # Process in batches of BATCH_SIZE
    for i in range(0, total_sr_notations, BATCH_SIZE):
        batch = sr_notations[i : i + BATCH_SIZE]
        logger.info(
            f"Processing batch {i//BATCH_SIZE + 1}/{(total_sr_notations+BATCH_SIZE-1)//BATCH_SIZE} ({len(batch)} laws)"
        )

        # Get all versions for all laws in this batch
        all_versions_by_sr = batch_get_all_versions(batch)

        # For each SR notation, identify missing versions and download them
        for sr_notation in batch:
            # Get all versions for this SR notation
            all_versions = all_versions_by_sr.get(sr_notation, [])

            # Get list of already scraped versions
            law_dir = os.path.join(base_dir, sr_notation)
            scraped_versions = []

            if os.path.exists(law_dir):
                # List subdirectories, which should be version dates
                scraped_versions = [
                    d
                    for d in os.listdir(law_dir)
                    if os.path.isdir(os.path.join(law_dir, d))
                ]

            # Identify missing versions newer than the oldest scraped version
            missing_versions = identify_missing_versions(all_versions, scraped_versions)

            # Download missing versions
            if missing_versions:
                downloaded = download_missing_versions(
                    missing_versions, sr_notation, base_dir
                )
                results[sr_notation] = downloaded
            else:
                results[sr_notation] = 0

    return results


def compute_dynamic_source(law_text_url):
    """
    Compute the dynamic source URL from the law text URL.
    Handles various URL patterns including historical laws with Roman numerals.
    """
    # Pattern 1: Standard pattern with numeric IDs
    pattern1 = r"^https://fedlex\.data\.admin\.ch/filestore/fedlex\.data\.admin\.ch(\/eli\/cc\/\d+\/[^/]+)\/\d+\/(de)\/html/.*\.html$"
    match1 = re.match(pattern1, law_text_url)
    if match1:
        path_part = match1.group(1)
        lang = match1.group(2)
        return f"https://www.fedlex.admin.ch{path_part}/{lang}"

    # Pattern 2: Pattern with 'X' in the path (some historical laws)
    pattern2 = r"^https://fedlex\.data\.admin\.ch/filestore/fedlex\.data\.admin\.ch(\/eli\/cc\/X\/[^/]+)\/\d+\/(de)\/html/.*\.html$"
    match2 = re.match(pattern2, law_text_url)
    if match2:
        path_part = match2.group(1)
        lang = match2.group(2)
        return f"https://www.fedlex.admin.ch{path_part}/{lang}"

    # Pattern 3: Historical laws with Roman numerals (V, VI, VII, etc.)
    pattern3 = r"^https://fedlex\.data\.admin\.ch/filestore/fedlex\.data\.admin\.ch(\/eli\/cc\/[IVX]+\/[^/]+)\/\d+\/(de)\/html/.*\.html$"
    match3 = re.match(pattern3, law_text_url)
    if match3:
        path_part = match3.group(1)
        lang = match3.group(2)
        return f"https://www.fedlex.admin.ch{path_part}/{lang}"

    # If no pattern matches, log a warning and return empty string
    logger.warning(f"Law text URL did not match expected patterns: {law_text_url}")
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
    The law's own number is not stored; only the hierarchy‐assigned folder/section/subsection.
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


def process_metadata_file_batch(file_paths, fedlex_hierarchy, aufhebungsdatum_cache):
    """
    Process multiple metadata files in a batch.

    Args:
        file_paths: List of metadata file paths to process
        fedlex_hierarchy: The hierarchy data for category assignment
        aufhebungsdatum_cache: Cache of SR notation to aufhebungsdatum mapping

    Returns:
        List of SR notations processed
    """
    # Extract SR notations for all files
    sr_notations = []
    sr_to_files = {}

    for file_path in file_paths:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            doc_info = data.get("doc_info", {})
            sr_notation = doc_info.get("ordnungsnummer", "")

            if sr_notation:
                sr_notations.append(sr_notation)
                if sr_notation not in sr_to_files:
                    sr_to_files[sr_notation] = []
                sr_to_files[sr_notation].append((file_path, data))
        except Exception as e:
            logger.error(f"Error reading metadata file {file_path}: {e}")

    # Get missing aufhebungsdatum values in batches
    missing_sr_notations = [
        sr for sr in sr_notations if sr not in aufhebungsdatum_cache
    ]

    if missing_sr_notations:
        logger.info(f"Fetching aufhebungsdatum for {len(missing_sr_notations)} laws")
        batch_results = batch_get_aufhebungsdatum(missing_sr_notations)
        aufhebungsdatum_cache.update(batch_results)

    # Process each file with the cached data
    processed_sr_notations = set()

    for sr_notation, file_data_pairs in sr_to_files.items():
        processed_sr_notations.add(sr_notation)
        aufhebungsdatum = aufhebungsdatum_cache.get(sr_notation, "")

        for file_path, data in file_data_pairs:
            doc_info = data.get("doc_info", {})

            # (1) Update dynamic_source from law_text_url
            law_text_url = doc_info.get("law_text_url", "")
            doc_info["dynamic_source"] = compute_dynamic_source(law_text_url)

            # (2) Update aufhebungsdatum and in_force
            doc_info["aufhebungsdatum"] = aufhebungsdatum
            doc_info["in_force"] = False if aufhebungsdatum else True

            # (3) Update category based on ordnungsnummer
            assign_category_to_metadata(doc_info, fedlex_hierarchy)

            # Save the updated data
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                logger.debug(f"Updated {file_path}")
            except Exception as e:
                logger.error(f"Failed to write updated JSON to {file_path}: {e}")

    return list(processed_sr_notations)


# --- Part 4. Version Update Functions ---


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


def update_versions_for_law_group(file_paths):
    """
    For all files (versions) of a given law (uid), update each file's
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
            logger.error(f"Error loading {fp} for version update: {e}")

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
            logger.debug(f"Updated versions in {versions[i]['file_path']}")
        except Exception as e:
            logger.error(
                f"Error writing updated versions to {versions[i]['file_path']}: {e}"
            )


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
        logger.error(f"Error loading hierarchy file {hierarchy_file}: {e}")
        return

    base_dir = "data/fedlex/fedlex_files"

    # Dictionary to keep track of processed laws and count of added versions
    processed_laws = {}
    total_new_versions = 0

    # Cache for aufhebungsdatum values to avoid repeated queries
    aufhebungsdatum_cache = {}

    # First pass: process metadata files in batches and collect SR notations
    all_metadata_files = []
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith("-metadata.json"):
                all_metadata_files.append(os.path.join(root, file))

    sr_notations = []
    logger.info(f"Processing {len(all_metadata_files)} metadata files in batches")

    # Process metadata files in batches
    for i in range(0, len(all_metadata_files), BATCH_SIZE):
        batch = all_metadata_files[i : i + BATCH_SIZE]
        logger.info(
            f"Processing metadata batch {i//BATCH_SIZE + 1}/{(len(all_metadata_files)+BATCH_SIZE-1)//BATCH_SIZE} ({len(batch)} files)"
        )
        batch_sr_notations = process_metadata_file_batch(
            batch, fedlex_hierarchy, aufhebungsdatum_cache
        )
        sr_notations.extend(batch_sr_notations)

    # Remove duplicates
    sr_notations = sorted(list(set(sr_notations)))
    logger.info(f"Found {len(sr_notations)} unique SR notations")

    # Now process versions for laws in batches
    version_results = process_law_versions_batched(sr_notations, base_dir)

    # Count total new versions downloaded
    for sr_notation, count in version_results.items():
        processed_laws[sr_notation] = count
        total_new_versions += count

    logger.info(
        f"Downloaded {total_new_versions} new versions across {len(processed_laws)} laws"
    )

    # Update versions in batches
    logger.info("Updating version references in metadata files")
    groups = group_files_by_uid(base_dir)
    count = 0
    total = len(groups)

    for uid, file_paths in groups.items():
        count += 1
        if count % 50 == 0 or count == total:
            logger.info(f"Updating versions: {count}/{total} law groups processed")
        update_versions_for_law_group(file_paths)

    logger.info("Metadata update completed successfully")


if __name__ == "__main__":
    main()
