#!/usr/bin/env python3
"""Updates federal law metadata with additional information from Fedlex.

This module enriches existing federal law metadata by querying additional
information from Fedlex, including version details, document URLs, and
publication information. It handles rate limiting and error recovery.

Functions:
    query_fedlex_sparql(query): Executes SPARQL queries against Fedlex
    update_law_metadata(sr_number, metadata): Updates metadata for a specific law
    process_metadata_updates(input_file): Main function to update all metadata

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import os
import json
import re
import time
import requests
import logging
import arrow  # Using arrow for robust date parsing/formatting
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- Constants and Configuration ---

SPARQL_ENDPOINT = "https://fedlex.data.admin.ch/sparqlendpoint"
REQUEST_TIMEOUT = 60  # Timeout for network requests in seconds
BATCH_SIZE = 20  # Reduced batch size further to decrease server load
DELAY_BETWEEN_REQUESTS = 0.5  # Increased delay further
MAX_RETRIES = 3  # Maximum number of retry attempts for failed requests

# --- Optimized SPARQL Queries ---


def batch_get_aufhebungsdatum(sr_notations):
    """
    Retrieves aufhebungsdatum for multiple SR notations using VALUES.
    Uses path: Notation -> TaxonomyEntry -> Abstract, with datatype filter.
    Handles retries and errors gracefully.

    Args:
        sr_notations (list): List of SR notations (strings).

    Returns:
        dict: Dictionary mapping SR notations to their aufhebungsdatum (string, YYYY-MM-DD or empty).
    """
    if not sr_notations:
        return {}
    unique_notations = sorted(list(set(sr_notations)))
    num_notations = len(unique_notations)
    logger.info(
        f"Querying aufhebungsdatum for {num_notations} unique SR notations (with datatype filter)."
    )
    values_clause = " ".join([f'"{notation}"' for notation in unique_notations])

    # Query with datatype filter
    query = f"""
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
PREFIX skos:  <http://www.w3.org/2004/02/skos/core#>

SELECT DISTINCT ?srNotationValue ?consoAbstract (STR(?aufhebungsdatum) AS ?aufhebungsdatumStr)
WHERE {{
  VALUES ?srNotationValue {{ {values_clause} }}

  # Find the taxonomy entry resource that has the skos:notation with the specific datatype
  ?taxonomyEntry skos:notation ?srNotationLiteral .
  FILTER(STR(?srNotationLiteral) = ?srNotationValue) # Match the string value
  FILTER( datatype(?srNotationLiteral) = <https://fedlex.data.admin.ch/vocabulary/notation-type/id-systematique> ) # Match the datatype

  # Find the ConsolidationAbstract that is classified by this taxonomy entry
  ?consoAbstract jolux:classifiedByTaxonomyEntry ?taxonomyEntry .
  ?consoAbstract a jolux:ConsolidationAbstract .

  # Optionally get the aufhebungsdatum from the abstract
  OPTIONAL {{ ?consoAbstract jolux:aufhebungsdatum ?aufhebungsdatum . }}
}}
    """

    retries = 0
    while retries < MAX_RETRIES:
        try:
            logger.debug(
                f"SPARQL aufhebungsdatum query attempt {retries+1}/{MAX_RETRIES} for {num_notations} notations."
            )
            response = requests.get(
                SPARQL_ENDPOINT,
                params={"query": query},
                headers={"Accept": "application/sparql-results+json"},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()

            if not response.text or response.text.isspace():
                logger.warning(f"Empty response (aufhebungsdatum, attempt {retries+1})")
                retries += 1
                time.sleep(DELAY_BETWEEN_REQUESTS * (retries + 1))
                continue

            result_json = response.json()
            results = {}
            found_abstracts = set()
            bindings = result_json.get("results", {}).get("bindings", [])
            logger.debug(
                f"Received {len(bindings)} bindings for aufhebungsdatum query."
            )

            for binding in bindings:
                sr_notation_node = binding.get(
                    "srNotationValue"
                )  # Using the variable from VALUES
                conso_abstract_node = binding.get("consoAbstract")
                aufhebungsdatum_node = binding.get("aufhebungsdatumStr")

                if sr_notation_node and sr_notation_node.get("value"):
                    sr_notation = sr_notation_node["value"]
                    if conso_abstract_node and conso_abstract_node.get("value"):
                        found_abstracts.add(sr_notation)
                    aufhebungsdatum = (
                        aufhebungsdatum_node.get("value", "")
                        if aufhebungsdatum_node
                        else ""
                    )
                    results[sr_notation] = aufhebungsdatum

            for notation in unique_notations:
                if notation not in found_abstracts:
                    logger.warning(
                        f"Query with datatype filter could not link SR notation to ConsolidationAbstract: {notation}"
                    )

            final_results = {
                notation: results.get(notation, "") for notation in unique_notations
            }
            found_count = sum(1 for d in final_results.values() if d)
            logger.info(
                f"Successfully retrieved aufhebungsdatum for {found_count}/{num_notations} notations (found abstracts for {len(found_abstracts)})."
            )
            time.sleep(DELAY_BETWEEN_REQUESTS)
            return final_results

        except json.JSONDecodeError as je:
            logger.error(
                f"JSON decode error (aufhebungsdatum, attempt {retries+1}): {je}\nResponse Text: {response.text[:500]}..."
            )
            retries += 1
            time.sleep(DELAY_BETWEEN_REQUESTS * (retries + 1))
        except requests.exceptions.Timeout as te:
            logger.error(f"Timeout (aufhebungsdatum, attempt {retries+1}): {te}")
            retries += 1
            time.sleep(DELAY_BETWEEN_REQUESTS * (retries + 1))
        except requests.exceptions.RequestException as re:
            # Check response before logging potentially sensitive info
            resp_status = (
                response.status_code if "response" in locals() and response else "N/A"
            )
            if resp_status == 500:
                logger.error(
                    f"Server Error 500 (aufhebungsdatum, attempt {retries+1}). Error: {re}"
                )
                logger.debug(f"Failing Query:\n{query}")
            else:
                logger.error(
                    f"Request failed (aufhebungsdatum, attempt {retries+1}) Status={resp_status}: {re}"
                )
            retries += 1
            time.sleep(DELAY_BETWEEN_REQUESTS * (retries + 1))
        except Exception as e:
            logger.error(
                f"Unexpected error (aufhebungsdatum, attempt {retries+1}): {e}",
                exc_info=True,
            )
            retries += 1
            time.sleep(DELAY_BETWEEN_REQUESTS * (retries + 1))

    logger.error(
        f"Failed to retrieve aufhebungsdatum for batch starting with {unique_notations[0]} after {MAX_RETRIES} attempts."
    )
    return {notation: "" for notation in unique_notations}


def batch_get_all_versions(sr_notations):
    """
    Retrieves all versions using VALUES and the simplified path with datatype filter.
    MODIFIED: No longer filters based on the presence of titles.

    Args:
        sr_notations (list): List of SR notations to query.

    Returns:
        dict: Dictionary mapping SR notation (str) to a list of its version dicts.
    """
    if not sr_notations:
        return {}
    unique_notations = sorted(list(set(sr_notations)))
    num_notations = len(unique_notations)
    logger.info(
        f"Querying all versions for {num_notations} unique SR notations (with datatype filter)."
    )
    values_clause = " ".join([f'"{notation}"' for notation in unique_notations])

    # Query with datatype filter
    query = f"""
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
PREFIX skos:  <http://www.w3.org/2004/02/skos/core#>
PREFIX xsd:   <http://www.w3.org/2001/XMLSchema#>
PREFIX dct:   <http://purl.org/dc/terms/>

SELECT DISTINCT
  ?srNotationValue ?consoAbstract # Select abstract URI for debugging
  (STR(?dateApplicabilityNode) AS ?dateApplicability)
  ?title ?titleShort ?titleAlternative
  (STR(?dateDocumentNode) AS ?dateDocument)
  (STR(?dateEntryInForceNode) AS ?dateEntryInForce)
  (STR(?publicationDateNode) AS ?publicationDate)
  ?fileURL
WHERE {{
  BIND(<http://publications.europa.eu/resource/authority/language/DEU> AS ?language)
  VALUES ?srNotationValue {{ {values_clause} }}

  # --- Link Notation to Abstract via Taxonomy Entry with datatype filter ---
  ?taxonomyEntry skos:notation ?srNotationLiteral .
  FILTER(STR(?srNotationLiteral) = ?srNotationValue) # Match the string value
  FILTER( datatype(?srNotationLiteral) = <https://fedlex.data.admin.ch/vocabulary/notation-type/id-systematique> ) # Match the datatype

  ?consoAbstract jolux:classifiedByTaxonomyEntry ?taxonomyEntry .
  ?consoAbstract a jolux:ConsolidationAbstract .

  # --- Get details from the abstract ---
  ?consolidation jolux:isMemberOf ?consoAbstract .
  ?consolidation a jolux:Consolidation .
  ?consolidation jolux:dateApplicability ?dateApplicabilityNode .

  ?consolidation jolux:isRealizedBy ?consoExpression .
  ?consoExpression jolux:language ?language .

  OPTIONAL {{ ?consoExpression jolux:title ?title . }}
  OPTIONAL {{ ?consoExpression jolux:titleShort ?titleShort . }}
  OPTIONAL {{ ?consoExpression jolux:titleAlternative ?titleAlternative . }}

  ?consoExpression jolux:isEmbodiedBy ?manifestation .
  ?manifestation jolux:userFormat/skos:notation ?fileFormatNode .
  FILTER(STR(?fileFormatNode) = "html")
  ?manifestation jolux:isExemplifiedBy ?fileURL .

  ?consoAbstract jolux:dateDocument ?dateDocumentNode .
  OPTIONAL {{ ?consoAbstract jolux:dateEntryInForce ?dateEntryInForceNode . }}
  OPTIONAL {{ ?consoAbstract jolux:publicationDate ?publicationDateNode . }}
}}
ORDER BY ?srNotationValue ?dateApplicabilityNode
    """

    retries = 0
    while retries < MAX_RETRIES:
        try:
            logger.debug(
                f"SPARQL versions query attempt {retries+1}/{MAX_RETRIES} for {num_notations} notations."
            )
            response = requests.get(
                SPARQL_ENDPOINT,
                params={"query": query},
                headers={"Accept": "application/sparql-results+json"},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            if not response.text or response.text.isspace():
                logger.warning(f"Empty response (versions, attempt {retries+1})")
                retries += 1
                time.sleep(DELAY_BETWEEN_REQUESTS * (retries + 1))
                continue

            result_json = response.json()
            results = {notation: [] for notation in unique_notations}
            bindings = result_json.get("results", {}).get("bindings", [])
            logger.debug(f"Received {len(bindings)} bindings for versions query.")

            def get_val(binding, key):
                node = binding.get(key)
                return node.get("value", "") if node else ""

            processed_bindings_count = 0
            abstracts_found_map = {}

            for i, binding in enumerate(bindings):
                sr_notation = get_val(
                    binding, "srNotationValue"
                )  # Use the variable from VALUES
                if not sr_notation:
                    continue

                conso_abstract_uri = get_val(binding, "consoAbstract")
                if sr_notation not in abstracts_found_map and conso_abstract_uri:
                    abstracts_found_map[sr_notation] = conso_abstract_uri
                    # logger.debug(f"Found abstract for {sr_notation}: {conso_abstract_uri}")

                main_title = get_val(binding, "title")
                short_title = get_val(binding, "titleShort")
                alternative_title = get_val(binding, "titleAlternative")
                version_data = {
                    "dateApplicability": get_val(binding, "dateApplicability"),
                    "title": main_title,
                    "abbreviation": short_title,  # Corresponds to titleShort
                    "titleAlternative": alternative_title,
                    "dateDocument": get_val(binding, "dateDocument"),
                    "dateEntryInForce": get_val(binding, "dateEntryInForce"),
                    "publicationDate": get_val(binding, "publicationDate"),
                    "fileURL": get_val(binding, "fileURL"),
                }

                # --- MODIFICATION START ---
                # Only check for essential dateApplicability and fileURL
                if version_data["dateApplicability"] and version_data["fileURL"]:
                    results[sr_notation].append(version_data)
                    processed_bindings_count += 1
                # --- MODIFICATION END ---
                # else: logger.warning(f"Version for {sr_notation} missing date/URL. Binding: {binding}")

            found_count = sum(1 for v_list in results.values() if v_list)
            logger.info(
                f"Processed {processed_bindings_count} valid bindings (requiring date & URL), resulting in version data for {found_count}/{num_notations} SR notations (found abstracts for {len(abstracts_found_map)})."
            )
            time.sleep(DELAY_BETWEEN_REQUESTS)
            return results

        except json.JSONDecodeError as je:
            logger.error(
                f"JSON decode error (versions, attempt {retries+1}): {je}\nResponse Text: {response.text[:500]}..."
            )
            retries += 1
            time.sleep(DELAY_BETWEEN_REQUESTS * (retries + 1))
        except requests.exceptions.Timeout as te:
            logger.error(f"Timeout (versions, attempt {retries+1}): {te}")
            retries += 1
            time.sleep(DELAY_BETWEEN_REQUESTS * (retries + 1))
        except requests.exceptions.RequestException as re:
            # Check response before logging potentially sensitive info
            resp_status = (
                response.status_code if "response" in locals() and response else "N/A"
            )
            if resp_status == 500:
                logger.error(
                    f"Server Error 500 (versions, attempt {retries+1}). Error: {re}"
                )
                logger.debug(f"Failing Query:\n{query}")
            else:
                logger.error(
                    f"Request failed (versions, attempt {retries+1}) Status={resp_status}: {re}"
                )
            retries += 1
            time.sleep(DELAY_BETWEEN_REQUESTS * (retries + 1))
        except Exception as e:
            logger.error(
                f"Unexpected error (versions, attempt {retries+1}): {e}", exc_info=True
            )
            retries += 1
            time.sleep(DELAY_BETWEEN_REQUESTS * (retries + 1))

    logger.error(
        f"Failed to retrieve versions for batch starting with {unique_notations[0]} after {MAX_RETRIES} attempts."
    )
    return {}


# --- Date Formatting ---


def format_date(date_str):
    """Uses arrow to parse various date string formats and returns YYYYMMDD."""
    if not date_str or not isinstance(date_str, str):
        return ""
    try:
        # Attempt to parse with Arrow, handling potential errors
        return arrow.get(date_str).format("YYYYMMDD")
    except (arrow.parser.ParserError, TypeError, ValueError):
        # Log the problematic date string if needed for debugging
        # logger.debug(f"Could not parse date string: {date_str}")
        return ""  # Return empty string if parsing fails


# --- File Downloading ---


def download_missing_versions(
    missing_versions, sr_notation, base_dir, aufhebungsdatum_cache
):
    """Downloads HTML and creates metadata JSON for missing law versions."""
    success_count = 0
    aufhebungsdatum_law_raw = aufhebungsdatum_cache.get(sr_notation, "")
    aufhebungsdatum_law_formatted = format_date(aufhebungsdatum_law_raw)
    # logger.info(f"Attempting to download {len(missing_versions)} missing versions for {sr_notation}.")

    for version in missing_versions:
        dateApplicability_raw = version.get("dateApplicability", "").strip()
        fileURL = version.get("fileURL", "").strip()
        dateApplicability_formatted = format_date(dateApplicability_raw)
        if not dateApplicability_formatted or not fileURL:
            logger.warning(
                f"Skipping download for {sr_notation} due to missing dateApplicability ('{dateApplicability_raw}') or fileURL ('{fileURL}')."
            )
            continue  # Skip invalid

        erlassdatum_formatted = format_date(version.get("dateDocument", "").strip())
        inkraftsetzungsdatum_formatted = format_date(
            version.get("dateEntryInForce", "").strip()
        )
        publikationsdatum_formatted = format_date(
            version.get("publicationDate", "").strip()
        )
        # Fallback for publication date if missing
        if not publikationsdatum_formatted:
            publikationsdatum_formatted = dateApplicability_formatted

        numeric_nachtragsnummer = None
        try:
            # Use dateApplicability as the source for numeric version identifier
            numeric_nachtragsnummer = (
                float(dateApplicability_formatted)
                if dateApplicability_formatted
                else None
            )
        except ValueError:
            logger.warning(
                f"Could not convert dateApplicability '{dateApplicability_formatted}' to float for {sr_notation}."
            )
            pass  # Ignore conversion errors, numeric_nachtragsnummer remains None

        version_dir = os.path.join(base_dir, sr_notation, dateApplicability_formatted)
        os.makedirs(version_dir, exist_ok=True)
        raw_html_path = os.path.join(
            version_dir, f"{sr_notation}-{dateApplicability_formatted}-raw.html"
        )
        metadata_path = os.path.join(
            version_dir, f"{sr_notation}-{dateApplicability_formatted}-metadata.json"
        )

        # Check if files already exist
        if os.path.exists(raw_html_path) and os.path.exists(metadata_path):
            # logger.debug(f"Files already exist for {sr_notation} version {dateApplicability_formatted}.")
            try:  # Check/update aufhebungsdatum in existing metadata
                with open(metadata_path, "r+", encoding="utf-8") as mf:
                    md = json.load(mf)
                    di = md.get("doc_info", {})
                    # Update if aufhebungsdatum differs or in_force status is incorrect
                    current_auf = di.get("aufhebungsdatum", "")
                    current_if = di.get(
                        "in_force", None
                    )  # Use None to detect if key is missing
                    expected_if = not bool(aufhebungsdatum_law_formatted)

                    if (
                        current_auf != aufhebungsdatum_law_formatted
                        or current_if != expected_if
                    ):
                        di["aufhebungsdatum"] = aufhebungsdatum_law_formatted
                        di["in_force"] = expected_if
                        mf.seek(0)
                        json.dump(md, mf, indent=4, ensure_ascii=False)
                        mf.truncate()
                        # logger.info(f"Updated aufhebungsdatum/in_force in existing metadata: {metadata_path}")
            except json.JSONDecodeError as e:
                logger.error(
                    f"Error reading existing JSON metadata {metadata_path}: {e}"
                )
            except Exception as e:
                logger.error(
                    f"Error checking/updating existing metadata {metadata_path}: {e}"
                )
            continue  # Move to the next version

        # Download HTML content
        # logger.info(f"Downloading HTML for {sr_notation} version {dateApplicability_formatted} from {fileURL}")
        retries = 0
        download_success = False
        html_content = None
        while retries < MAX_RETRIES and not download_success:
            try:
                response = requests.get(fileURL, timeout=REQUEST_TIMEOUT)
                if response.status_code == 200:
                    # Use apparent_encoding to handle potential encoding issues
                    response.encoding = response.apparent_encoding
                    html_content = response.text
                    if (
                        html_content and not html_content.isspace()
                    ):  # Check for non-empty, non-whitespace content
                        download_success = True
                    else:
                        logger.warning(
                            f"Empty or whitespace content received from {fileURL} (try {retries+1})"
                        )
                        retries += 1
                        time.sleep(0.5 * (retries + 1))
                elif response.status_code >= 500:  # Server errors are worth retrying
                    logger.warning(
                        f"Server error {response.status_code} downloading {fileURL} (try {retries+1})"
                    )
                    retries += 1
                    time.sleep(0.5 * (retries + 1))
                else:  # Client errors (4xx) or other issues usually aren't worth retrying
                    logger.error(
                        f"HTTP error {response.status_code} downloading {fileURL}. Not retrying."
                    )
                    break  # Exit retry loop for this file
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout downloading {fileURL} (try {retries+1})")
                retries += 1
                time.sleep(0.5 * (retries + 1))
            except requests.exceptions.RequestException as re:
                logger.warning(
                    f"Request error downloading {fileURL} (try {retries+1}): {re}"
                )
                retries += 1
                time.sleep(0.5 * (retries + 1))
            except Exception as e:  # Catch unexpected errors during download
                logger.error(
                    f"Unexpected download error for {fileURL} (try {retries+1}): {e}",
                    exc_info=True,
                )
                retries += 1
                time.sleep(0.5 * (retries + 1))

        # Save HTML and create metadata if download was successful
        if download_success and html_content:
            try:
                # Save HTML
                with open(raw_html_path, "w", encoding="utf-8") as f:
                    f.write(html_content)

                # Prepare metadata
                metadata = {
                    "doc_info": {
                        "law_page_url": "",  # Placeholder, potentially fill later if needed
                        "law_text_url": fileURL,
                        "law_text_redirect": "",  # Placeholder
                        "nachtragsnummer": dateApplicability_formatted,  # Use formatted date as version ID
                        "numeric_nachtragsnummer": numeric_nachtragsnummer,  # Store the float version if available
                        "erlassdatum": erlassdatum_formatted,
                        "inkraftsetzungsdatum": inkraftsetzungsdatum_formatted,
                        "publikationsdatum": publikationsdatum_formatted,
                        "aufhebungsdatum": aufhebungsdatum_law_formatted,
                        "in_force": not bool(aufhebungsdatum_law_formatted),
                        "bandnummer": "",  # Placeholder
                        "hinweise": "",  # Placeholder
                        "erlasstitel": version.get("title", "").strip(),
                        "ordnungsnummer": sr_notation,
                        "kurztitel": version.get("titleAlternative", "").strip(),
                        "abkuerzung": version.get("abbreviation", "").strip(),
                        "category": {  # Initialize category structure
                            "folder": None,
                            "section": None,
                            "subsection": None,
                        },
                        "dynamic_source": "",  # Placeholder, filled in metadata update phase
                        "zhlaw_url_dynamic": "",  # Placeholder
                        "versions": {
                            "older_versions": [],
                            "newer_versions": [],
                        },  # Initialize version links
                    },
                    "process_steps": {
                        "download": arrow.now().format("YYYYMMDD-HHmmss"),
                        "process": "",  # Timestamp for metadata processing
                    },
                }
                # Save metadata
                with open(metadata_path, "w", encoding="utf-8") as mf:
                    json.dump(metadata, mf, indent=4, ensure_ascii=False)

                logger.info(
                    f"Saved HTML and metadata for {sr_notation} version {dateApplicability_formatted}"
                )
                success_count += 1
            except IOError as e:
                logger.error(
                    f"Error writing file for {sr_notation} version {dateApplicability_formatted}: {e}"
                )
                # Attempt cleanup if saving failed partially
                if os.path.exists(raw_html_path):
                    os.remove(raw_html_path)
                if os.path.exists(metadata_path):
                    os.remove(metadata_path)
            except Exception as e:
                logger.error(
                    f"Error saving files for {sr_notation} version {dateApplicability_formatted}: {e}",
                    exc_info=True,
                )
                # Attempt cleanup
                if os.path.exists(raw_html_path):
                    os.remove(raw_html_path)
                if os.path.exists(metadata_path):
                    os.remove(metadata_path)
        else:  # Log download failure after retries
            logger.error(
                f"Failed download for {sr_notation} version {dateApplicability_formatted} from {fileURL} after {MAX_RETRIES} attempts."
            )

        # Optional short delay between downloads within a batch
        time.sleep(0.1)  # Small delay to be polite to the server

    # logger.info(f"Finished download attempt for {sr_notation}. Saved {success_count} new versions.")
    return success_count


# --- Version Identification ---


def identify_missing_versions(all_versions_from_sparql, scraped_version_dirs_set):
    """Identifies versions from SPARQL results that are not present locally based on dateApplicability."""
    missing = []
    seen_dates = (
        set()
    )  # Track dates processed for this law to avoid duplicates if SPARQL returns multiple entries for the same date
    if not all_versions_from_sparql:
        return missing

    for v in all_versions_from_sparql:
        date_fmt = format_date(v.get("dateApplicability", ""))
        # Check if date is valid, not already scraped locally, and not already added to the missing list for this law
        if (
            date_fmt
            and date_fmt not in scraped_version_dirs_set
            and date_fmt not in seen_dates
        ):
            # Basic validation: Ensure we have a file URL as well (already checked in batch_get_all_versions, but good safety)
            if v.get("fileURL"):
                missing.append(v)
                seen_dates.add(date_fmt)
            else:
                logger.warning(
                    f"SPARQL version entry for date {date_fmt} is missing a fileURL. Skipping."
                )

    return missing


# --- Batch Processing Orchestration ---


def process_law_versions_batched(sr_notations_batch, base_dir, aufhebungsdatum_cache):
    """Processes a batch of SR notations: fetches data, identifies missing, downloads."""
    if not sr_notations_batch:
        return {}
    results = {
        sr: 0 for sr in sr_notations_batch
    }  # Initialize download counts for this batch

    # 1. Fetch Aufhebungsdatum for laws in the batch not already in cache
    needing_aufhebung = [
        sr for sr in sr_notations_batch if sr not in aufhebungsdatum_cache
    ]
    if needing_aufhebung:
        logger.info(
            f"Fetching aufhebungsdatum for {len(needing_aufhebung)} laws in batch..."
        )
        aufhebung_data = batch_get_aufhebungsdatum(needing_aufhebung)
        aufhebungsdatum_cache.update(aufhebung_data)  # Update the main cache
        # logger.info(f"Updated aufhebungsdatum cache with {len(aufhebung_data)} entries.")

    # 2. Fetch all version details for the batch
    all_versions = batch_get_all_versions(sr_notations_batch)

    # Handle case where SPARQL query for versions might fail entirely for the batch
    if not all_versions:
        # Check if aufhebungsdatum also failed for all items in the batch (as a secondary indicator of problems)
        all_aufhebung_failed = all(
            not aufhebungsdatum_cache.get(sr)
            for sr in sr_notations_batch
            if sr in aufhebungsdatum_cache
        )
        if all_aufhebung_failed:
            logger.error(
                f"Both aufhebungsdatum and version queries failed to return data for the batch starting with {sr_notations_batch[0]}. Check SPARQL endpoint status and query validity."
            )
        else:
            logger.warning(
                f"Version query returned no data for the batch starting with {sr_notations_batch[0]}, but some aufhebungsdatum might exist."
            )
        return results  # Return 0 downloads for all in this batch

    # 3. Process each law in the batch
    for sr in sr_notations_batch:
        versions_for_law = all_versions.get(sr, [])
        if not versions_for_law:
            # Log if SPARQL returned nothing for this specific law, even if the batch query succeeded overall
            if sr not in aufhebungsdatum_cache or not aufhebungsdatum_cache.get(
                sr
            ):  # Check if we also lack aufhebungsdatum
                logger.warning(
                    f"No version data found via SPARQL for SR {sr}, and no aufhebungsdatum cached. Law might not exist or query failed for it."
                )
            else:
                logger.debug(
                    f"No version data from SPARQL for SR {sr}, but aufhebungsdatum is cached."
                )
            continue  # Skip to the next law in the batch

        law_dir = os.path.join(base_dir, sr)
        scraped_dirs = set()
        # Check existing local directories for this law
        if os.path.isdir(law_dir):
            try:
                # List subdirectories that match the YYYYMMDD format
                scraped_dirs = {
                    d
                    for d in os.listdir(law_dir)
                    if os.path.isdir(os.path.join(law_dir, d))
                    and re.fullmatch(r"\d{8}", d)
                }
            except OSError as e:
                logger.error(f"Error listing directories in {law_dir}: {e}")
                # Continue processing other laws even if one directory fails
                continue

        # Identify versions present in SPARQL results but not locally
        missing = identify_missing_versions(versions_for_law, scraped_dirs)

        if missing:
            logger.info(
                f"Found {len(missing)} missing versions for SR {sr}. Starting download..."
            )
            # Download the missing versions
            download_count = download_missing_versions(
                missing, sr, base_dir, aufhebungsdatum_cache
            )
            results[sr] = (
                download_count  # Store the number of successful downloads for this SR
            )
            logger.info(
                f"Finished download for SR {sr}. Successfully saved {download_count} new versions."
            )
        elif scraped_dirs:
            # If no new versions to download, but local versions exist,
            # ensure the aufhebungsdatum is up-to-date in the *latest* existing metadata file.
            # This handles cases where a law is repealed after its last version was downloaded.
            try:
                latest_date = max(
                    scraped_dirs
                )  # Find the most recent version date locally
                latest_metadata_path = os.path.join(
                    law_dir, latest_date, f"{sr}-{latest_date}-metadata.json"
                )
                if os.path.exists(latest_metadata_path):
                    auf_fmt = format_date(aufhebungsdatum_cache.get(sr, ""))
                    expected_if = not bool(auf_fmt)
                    with open(latest_metadata_path, "r+", encoding="utf-8") as mf:
                        md = json.load(mf)
                        di = md.get("doc_info", {})
                        # Check if update is needed
                        if (
                            di.get("aufhebungsdatum") != auf_fmt
                            or di.get("in_force") != expected_if
                        ):
                            di["aufhebungsdatum"] = auf_fmt
                            di["in_force"] = expected_if
                            mf.seek(0)
                            json.dump(md, mf, indent=4, ensure_ascii=False)
                            mf.truncate()
                            # logger.info(f"Updated aufhebungsdatum/in_force in latest existing metadata: {latest_metadata_path}")
            except json.JSONDecodeError as e:
                logger.error(
                    f"Error reading latest JSON metadata {latest_metadata_path} for update: {e}"
                )
            except Exception as e:
                logger.error(
                    f"Error updating aufhebungsdatum in existing metadata for {sr} ({latest_date}): {e}"
                )
        # else: No missing versions and no existing local versions (should ideally not happen if SPARQL returned versions)

    return results  # Return download counts for the processed batch


# --- Dynamic Source URL Computation ---


def compute_dynamic_source(law_text_url):
    """Computes the corresponding www.fedlex.admin.ch URL from a filestore URL."""
    if not law_text_url or not isinstance(law_text_url, str):
        return ""
    # Regex to capture the essential path parts and language code
    # Example URL: https://fedlex.data.admin.ch/filestore/fedlex.data.admin.ch/eli/cc/2023/100/20240101/de/html/fedlex-data-admin-ch-eli-cc-2023-100-20240101-de-html-1.html
    # We want to capture: /eli/cc/2023/100 and de
    pattern = r"https://fedlex\.data\.admin\.ch/filestore/fedlex\.data\.admin\.ch(/eli/cc/\d+/[^/]+)/\d+/([^/]+)/html/.*\.html$"
    match = re.search(pattern, law_text_url)
    if match:
        path_part, lang = match.groups()
        # Construct the public-facing URL
        return f"https://www.fedlex.admin.ch{path_part}/{lang}"
    else:
        logger.debug(f"Could not extract dynamic source path from URL: {law_text_url}")
        return ""  # Return empty if pattern doesn't match


# --- Category Assignment Logic ---


def assign_category_codes(ordnungsnummer):
    """Derives potential folder, section, and subsection codes from an Ordnungsnummer."""
    f, s, ss = "", "", None
    if (
        not ordnungsnummer
        or not isinstance(ordnungsnummer, str)
        or not re.match(r"^[0-9.]+$", ordnungsnummer.strip())
    ):
        logger.debug(
            f"Invalid ordnungsnummer format for category coding: {ordnungsnummer}"
        )
        return f, s, ss

    onum = ordnungsnummer.strip()
    is_intl = onum.startswith("0.")

    if is_intl:
        # Handle international law format (0.XXX.YYY...)
        parts = onum.split(".")
        if len(parts) >= 2 and parts[0] == "0" and parts[1].isdigit():
            digits = parts[1]
            num_digits = len(digits)
            if num_digits >= 1:
                f = f"0.{digits[0]}"
            if num_digits >= 2:
                s = f"0.{digits[:2]}"
            if num_digits >= 3:
                ss = f"0.{digits[:3]}"
            # Prevent assigning self as child category
            if onum == f:
                s, ss = "", None
            elif onum == s:
                ss = None
        else:
            logger.debug(f"Unexpected international ordnungsnummer format: {onum}")
    else:
        # Handle national law format (XXX.YYY...)
        parts = onum.split(".")
        main_part = parts[0]
        if main_part.isdigit():
            num_digits = len(main_part)
            if num_digits >= 1:
                f = main_part[0]
            if num_digits >= 2:
                s = main_part[:2]
            if num_digits >= 3:
                ss = main_part[:3]
            # Prevent assigning self as child category
            if onum == f:
                s, ss = "", None
            elif onum == s:
                ss = None
            # Special case: if the input is exactly 3 digits (e.g., "170"),
            # ss would initially equal s. Nullify ss in this specific case.
            if ss == s and len(parts) == 1 and num_digits == 3:
                ss = None
        else:
            logger.debug(f"Non-digit main part in national ordnungsnummer: {onum}")
            return "", "", None  # Cannot derive codes if main part isn't digits

    # Final safety check: if ss somehow ended up identical to s, nullify ss.
    if ss == s:
        ss = None

    return f, s, ss


def find_category_details(code, level_dict):
    """
    Looks for 'code' in the hierarchy level dict. Returns name and the *item's dict*.
    Enhanced with logging and whitespace stripping.
    """
    if not isinstance(level_dict, dict) or not code:
        logger.debug(
            f"find_category_details: Invalid input. Code: '{code}', Dict Type: {type(level_dict)}"
        )
        return None, None  # Invalid input

    code_str = str(code).strip()  # Ensure string and strip whitespace
    if not code_str:
        logger.debug(
            f"find_category_details: Code became empty after stripping: '{code}'"
        )
        return None, None

    item = level_dict.get(code_str)  # Lookup using stripped string code

    if item is None:
        # Log available keys if lookup fails - helps identify typos/case issues
        logger.debug(
            f"find_category_details: Code '{code_str}' not found in keys: {list(level_dict.keys())}"
        )
        return None, None  # Code not found

    if isinstance(item, dict):
        name = item.get("name")
        # Check if name exists and is a non-empty string
        if isinstance(name, str) and name.strip():
            return name.strip(), item  # Return stripped name and the dictionary itself
        else:
            logger.debug(
                f"find_category_details: Found item for '{code_str}', but 'name' is missing, None, or empty. Name: '{name}', Item: {item}"
            )
            return None, None  # Name invalid
    else:
        logger.debug(
            f"find_category_details: Found item for '{code_str}', but it's not a dictionary. Type: {type(item)}, Value: {item}"
        )
        return None, None  # Item is not a dictionary


def assign_category_to_metadata(doc_info, hierarchy):
    """Updates the doc_info["category"] dictionary by traversing the hierarchy (Top-Down)."""
    onum = doc_info.get("ordnungsnummer", "")
    # Initialize category structure in doc_info, ensuring it exists
    cat = {"folder": None, "section": None, "subsection": None}
    doc_info["category"] = cat

    if not onum:
        logger.debug("Assign Category: No Ordnungsnummer provided.")
        return  # Cannot assign category without Ordnungsnummer

    # Determine branch (A=International, B=National) and derive potential codes
    is_intl = onum.strip().startswith("0.")
    branch = "A" if is_intl else "B"
    f_c, s_c, ss_c = assign_category_codes(
        onum
    )  # Get folder, section, subsection codes

    # Log derived codes for debugging
    logger.debug(
        f"Assign Category for {onum}: Codes=(F:'{f_c}', S:'{s_c}', SS:'{ss_c}') Branch='{branch}'"
    )

    # --- Step 1: Find Folder ---
    # Get the dictionary of folders for the determined branch
    folder_search_dict = hierarchy.get(branch, {}).get("folders")
    if not isinstance(folder_search_dict, dict):
        logger.debug(
            f"Assign Category: Branch '{branch}' has no 'folders' dictionary in hierarchy."
        )
        return  # Cannot proceed without folders definition

    # Attempt to find the folder using the derived folder code
    logger.debug(  # Keep this log
        f"Assign Category: Looking for Folder '{f_c}' in keys: {list(folder_search_dict.keys())}"
    )
    folder_name, folder_item_dict = find_category_details(f_c, folder_search_dict)

    # Check if folder was found and is valid
    if not (folder_name and folder_item_dict):
        logger.debug(
            f"Assign Category: Folder '{f_c}' not found or invalid in hierarchy. Stopping."  # Modified log
        )
        return  # Stop if folder is not found

    # Folder found, assign it to the category dictionary
    cat["folder"] = {"id": f_c, "name": folder_name}
    logger.debug(f"Assign Category: Found Folder: {cat['folder']}")
    # *** ADDED LOG: Log the structure found for the folder ***
    logger.debug(f"Assign Category: Folder item dict structure: {folder_item_dict}")

    # --- Step 2: Determine Where to Search for Section/Subsection ---
    # Default assumption: Sections are nested under 'sections' key of the folder item
    section_search_dict = folder_item_dict.get("sections")
    subsection_search_dict = None  # Will be set later if section is found or if folder has direct subsections

    # Check if the folder item has a 'sections' dictionary.
    if not isinstance(section_search_dict, dict):
        # If no 'sections', check if it has 'subsections' directly (less common structure)
        logger.debug(
            f"Assign Category: Folder '{f_c}' has no 'sections' dict. Checking for direct 'subsections'."
        )
        direct_subsection_dict = folder_item_dict.get("subsections")
        if isinstance(direct_subsection_dict, dict):
            # If direct subsections exist, prepare to search within them
            logger.debug(
                f"Assign Category: Folder '{f_c}' has direct 'subsections'. Will search these."
            )
            subsection_search_dict = (
                direct_subsection_dict  # Set the dict for the subsection search step
            )
            # *** ADDED LOG: Log keys if searching direct subsections ***
            logger.debug(
                f"Assign Category: Direct subsection keys: {list(subsection_search_dict.keys())}"
            )
            s_c = None  # CRITICAL: Clear the section code, as we are skipping the section level search
        else:
            # If neither 'sections' nor 'subsections' exist or are valid dicts, stop here.
            logger.debug(
                f"Assign Category: Folder '{f_c}' has no valid 'sections' or 'subsections'. Stopping category assignment."
            )
            return  # Cannot proceed further down the hierarchy
    # *** ADDED LOG: Log section keys if section dict exists ***
    elif s_c:  # Only log keys if we actually have a section code to look for
        logger.debug(
            f"Assign Category: Section keys to search for '{s_c}': {list(section_search_dict.keys())}"
        )

    # --- Step 3: Find Section (if applicable) ---
    # This block executes only if a section code (s_c) was derived AND we found a valid 'sections' dictionary in the folder
    if s_c and isinstance(section_search_dict, dict):
        logger.debug(  # Keep this log
            f"Assign Category: Looking for Section '{s_c}'..."  # Simplified log
        )
        # Attempt to find the section within the folder's sections dictionary
        section_name, section_item_dict = find_category_details(
            s_c, section_search_dict
        )
        # *** ADDED LOG: Log the result of the section lookup ***
        logger.debug(
            f"Assign Category: Section lookup result - Name: '{section_name}', Item Dict Type: {type(section_item_dict)}"
        )

        # Check if section was found and is valid
        if section_name and section_item_dict:
            # Section found, assign it
            cat["section"] = {"id": s_c, "name": section_name}
            logger.debug(f"Assign Category: Found Section: {cat['section']}")

            # Now, prepare for the subsection search by looking inside the *found section item*
            subsection_search_dict = section_item_dict.get("subsections")
            # *** ADDED LOG: Log the subsection dict obtained from the section ***
            logger.debug(
                f"Assign Category: Subsection dict from section '{s_c}': Type={type(subsection_search_dict)}"
            )

            # Check if this section item actually contains a 'subsections' dictionary
            if not isinstance(subsection_search_dict, dict):
                logger.debug(
                    f"Assign Category: Section '{s_c}' found, but it has no 'subsections' dict inside. Subsection search won't proceed."
                )
                # Explicitly set to None so the next step's check fails correctly
                subsection_search_dict = None
            # *** ADDED LOG: Log subsection keys if searching within section ***
            elif ss_c:  # Only log keys if we have a subsection code to look for
                logger.debug(
                    f"Assign Category: Subsection keys to search for '{ss_c}': {list(subsection_search_dict.keys())}"
                )

            # --- IMPORTANT: Do NOT return here. Finding a section without further subsections is valid. ---

        else:
            # If the derived section code exists (s_c is not None) but wasn't found in the folder's sections dict
            logger.debug(
                f"Assign Category: Section '{s_c}' derived but not found or invalid in folder's sections. Stopping."  # Modified log
            )
            # Stop processing for this law, as the expected hierarchy path is broken.
            return

    elif s_c:
        # This condition handles the case where s_c was derived, but we skipped the section search
        # because the folder had direct subsections (subsection_search_dict was set earlier).
        logger.debug(
            f"Assign Category: Section code '{s_c}' derived, but searching in folder's direct subsections. Skipping section assignment."
        )
        # No action needed here, subsection_search_dict is already set correctly for the next step.

    # --- Step 4: Find Subsection (if applicable) ---
    # This block executes only if a subsection code (ss_c) was derived AND
    # we have a valid dictionary (subsection_search_dict) to search within
    # (either from the found section or directly from the folder).
    if ss_c and isinstance(subsection_search_dict, dict):
        logger.debug(  # Keep this log
            f"Assign Category: Looking for Subsection '{ss_c}'..."  # Simplified log
        )
        # Attempt to find the subsection within the determined search dictionary
        subsection_name, subsection_item_dict = (  # Get dict too for logging
            find_category_details(  # We only need the name for assignment
                ss_c, subsection_search_dict
            )
        )
        # *** ADDED LOG: Log the result of the subsection lookup ***
        logger.debug(
            f"Assign Category: Subsection lookup result - Name: '{subsection_name}', Item Dict Type: {type(subsection_item_dict)}"
        )

        # Check if subsection was found
        if subsection_name:  # No need to check dict here, find_category_details does
            # Subsection found, assign it
            cat["subsection"] = {"id": ss_c, "name": subsection_name}
            logger.debug(f"Assign Category: Found Subsection: {cat['subsection']}")
        else:
            # Subsection code was derived, but not found in the expected location
            logger.debug(
                f"Assign Category: Subsection '{ss_c}' not found or invalid in the relevant dictionary."  # Modified log
            )
            # Do not return, just means this law doesn't go down to the subsection level found

    elif ss_c:
        # This condition handles cases where ss_c was derived, but subsection_search_dict ended up
        # not being a valid dictionary (e.g., section found but had no subsections).
        logger.debug(
            f"Assign Category: Subsection code '{ss_c}' derived, but no valid dictionary provided to search in (subsection_search_dict is not a dict or None)."  # Modified log
        )
        # No action needed, subsection remains None.

    # Function completes. The doc_info["category"] dictionary now holds the assigned categories.


# --- Metadata File Processing ---


def process_metadata_file_batch(paths, hierarchy, cache):
    """Processes a batch of metadata files to update dynamic source, status, and category."""
    srs_processed_in_batch = (
        set()
    )  # Keep track of SRs touched in this specific batch run
    updated_files_count = 0
    if not paths:
        return []  # Return empty list if no paths provided

    # logger.info(f"Processing metadata batch of {len(paths)} files.")
    for file_path in paths:
        try:
            # Read existing metadata
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Basic validation of metadata structure
            doc_info = data.get("doc_info")
            if not isinstance(doc_info, dict):
                logger.error(
                    f"Invalid metadata structure (missing 'doc_info') in {file_path}"
                )
                continue  # Skip this file

            sr = doc_info.get("ordnungsnummer")
            if not sr or not isinstance(sr, str):
                logger.warning(f"Missing or invalid 'ordnungsnummer' in {file_path}")
                continue  # Skip this file

            srs_processed_in_batch.add(sr)  # Add SR to the set for this batch
            original_data_str = json.dumps(
                data, sort_keys=True
            )  # Store original state for change comparison
            changed = False
            change_reasons = []  # Track reasons for updating the file

            # (1) Update dynamic_source URL
            current_ds = doc_info.get("dynamic_source", "")
            law_text_url = doc_info.get("law_text_url", "")
            new_ds = compute_dynamic_source(law_text_url)
            if current_ds != new_ds:
                doc_info["dynamic_source"] = new_ds
                changed = True
                change_reasons.append("dynamic_source")

            # (2) Update aufhebungsdatum and in_force status from cache
            auf_raw = cache.get(sr)  # Get cached raw date (might be None or empty)
            auf_fmt = format_date(
                auf_raw if auf_raw is not None else ""
            )  # Format it (returns "" if invalid/empty)
            expected_in_force = not bool(
                auf_fmt
            )  # Law is in force if formatted date is empty

            current_auf = doc_info.get("aufhebungsdatum", "")
            current_in_force = doc_info.get(
                "in_force"
            )  # Could be True, False, or None if missing

            if current_auf != auf_fmt:
                doc_info["aufhebungsdatum"] = auf_fmt
                changed = True
                change_reasons.append("aufhebungsdatum")
            if current_in_force != expected_in_force:
                doc_info["in_force"] = expected_in_force
                changed = True
                change_reasons.append("in_force")

            # (3) Update category using the corrected function
            # Store old category state as a string for comparison
            old_cat_str = json.dumps(doc_info.get("category", {}), sort_keys=True)
            # Call the function - it modifies doc_info['category'] in place
            assign_category_to_metadata(doc_info, hierarchy)
            # Get the new category state as a string
            new_cat_str = json.dumps(doc_info.get("category", {}), sort_keys=True)

            # Check if the category structure or content actually changed
            if old_cat_str != new_cat_str:
                changed = True
                change_reasons.append("category")

            # (4) Save the file ONLY if changes were made
            if changed:
                # Log changes before writing
                logger.info(
                    f"Updating metadata for {file_path}. Reasons: {', '.join(change_reasons)}"
                )

                # --- START MODIFICATION ---
                # Ensure process_steps dictionary and sub-keys exist before updating
                if "process_steps" not in data or not isinstance(
                    data.get("process_steps"), dict
                ):
                    logger.warning(
                        f"Initializing missing 'process_steps' structure in {file_path}"
                    )
                    # Create the structure if it's missing entirely
                    data["process_steps"] = {
                        "download": "",  # Add placeholder for download timestamp
                        "process": arrow.now().format("YYYYMMDD-HHmmss"),
                    }
                else:
                    # If process_steps exists, just update the process timestamp
                    data["process_steps"]["process"] = arrow.now().format(
                        "YYYYMMDD-HHmmss"
                    )
                    # Optionally ensure download exists even if process_steps was present
                    if "download" not in data["process_steps"]:
                        data["process_steps"][
                            "download"
                        ] = ""  # Add placeholder if missing
                # --- END MODIFICATION ---

                try:
                    # Write the updated data back to the file
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=4)
                    updated_files_count += 1
                except IOError as e:
                    logger.error(f"Error writing updated metadata to {file_path}: {e}")
                except Exception as e:  # Catch other potential errors during write
                    logger.error(
                        f"Unexpected error writing {file_path}: {e}", exc_info=True
                    )

        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {file_path}: {e}")

        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {file_path}: {e}")
        except IOError as e:
            logger.error(f"Error reading metadata file {file_path}: {e}")
        except (
            Exception
        ) as e:  # Catch-all for unexpected errors during processing of a single file
            logger.error(
                f"Unexpected error processing metadata file {file_path}: {e}",
                exc_info=True,
            )

    if updated_files_count > 0:
        logger.info(f"Updated {updated_files_count} metadata files in this batch.")

    return list(
        srs_processed_in_batch
    )  # Return the list of unique SRs processed in this batch


# --- Version Linking Functions ---


def extract_version_data(di):
    """Extracts relevant subset of metadata for linking versions."""
    if not isinstance(di, dict):
        return {}
    # Define keys to extract for the version summary
    keys = [
        "law_page_url",
        "law_text_url",
        "nachtragsnummer",  # The YYYYMMDD version identifier
        "numeric_nachtragsnummer",  # The float representation, if available
        "erlassdatum",
        "inkraftsetzungsdatum",
        "publikationsdatum",
        "aufhebungsdatum",
        "in_force",
    ]
    # Create summary dict, defaulting missing keys to None
    rec = {k: di.get(k) for k in keys}

    # Ensure numeric_nachtragsnummer is float or None
    try:
        num_nachtrag_val = rec.get("numeric_nachtragsnummer")
        rec["numeric_nachtragsnummer"] = (
            float(num_nachtrag_val) if num_nachtrag_val is not None else None
        )
    except (ValueError, TypeError):
        # If conversion fails, set to None and log potentially
        # logger.warning(f"Could not convert numeric_nachtragsnummer '{rec.get('numeric_nachtragsnummer')}' to float.")
        rec["numeric_nachtragsnummer"] = None

    # Ensure in_force is boolean
    rec["in_force"] = bool(rec.get("in_force", False))  # Default to False if missing

    # Ensure date fields are formatted as YYYYMMDD or empty string
    date_keys = [
        "nachtragsnummer",
        "erlassdatum",
        "inkraftsetzungsdatum",
        "publikationsdatum",
        "aufhebungsdatum",
    ]
    for dk in date_keys:
        rec[dk] = format_date(rec.get(dk))  # format_date handles None/empty input

    return rec


def update_versions_for_law_group(paths):
    """Updates older/newer version links within metadata files for a single law."""
    num_files = len(paths)
    if num_files <= 1:
        # If only one file exists, ensure the 'versions' structure is present but empty.
        if num_files == 1:
            try:
                with open(paths[0], "r+", encoding="utf-8") as f:
                    data = json.load(f)
                    doc_info = data.get("doc_info", {})
                    versions_node = doc_info.get("versions")
                    # Check if 'versions' key exists and is a dict with the required subkeys
                    if (
                        not isinstance(versions_node, dict)
                        or "older_versions" not in versions_node
                        or "newer_versions" not in versions_node
                    ):
                        # If structure is missing or incomplete, create/reset it
                        doc_info["versions"] = {
                            "older_versions": [],
                            "newer_versions": [],
                        }
                        # Rewrite the file only if structure was changed
                        f.seek(0)
                        json.dump(data, f, ensure_ascii=False, indent=4)
                        f.truncate()
                        # logger.debug(f"Ensured version structure exists in single file: {paths[0]}")
            except json.JSONDecodeError as e:
                logger.error(
                    f"Error reading single JSON file {paths[0]} for version structure check: {e}"
                )
            except IOError as e:
                logger.error(
                    f"Error reading/writing single file {paths[0]} for version structure check: {e}"
                )
            except Exception as e:
                logger.error(
                    f"Unexpected error ensuring version struct in {paths[0]}: {e}",
                    exc_info=True,
                )
        return  # Nothing more to do if 0 or 1 file

    # Load data and prepare for sorting
    loaded_versions = []
    sr_notation = None  # Try to extract SR notation from filename for logging
    for file_path in paths:
        try:
            # Extract SR notation once from the first valid path
            if not sr_notation:
                match = re.search(
                    r"([0-9.]+)-\d{8}-metadata\.json$", os.path.basename(file_path)
                )
                if match:
                    sr_notation = match.group(1)

            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            doc_info = data.get("doc_info")
            if not isinstance(doc_info, dict):
                logger.warning(
                    f"Skipping file due to invalid doc_info structure: {file_path}"
                )
                continue

            # Use numeric_nachtragsnummer for sorting, fallback to infinity if missing/invalid
            num_n = doc_info.get("numeric_nachtragsnummer")
            try:
                # Use float representation for reliable comparison
                sort_key = float(num_n) if num_n is not None else float("inf")
            except (ValueError, TypeError):
                sort_key = float("inf")  # Treat invalid numeric versions as the latest
                logger.warning(
                    f"Invalid numeric_nachtragsnummer '{num_n}' in {file_path}, using infinity for sorting."
                )

            # Extract summary data for linking
            version_summary = extract_version_data(doc_info)

            # Store necessary info for processing and saving
            loaded_versions.append(
                {
                    "file_path": file_path,
                    "full_data": data,  # Keep the full data structure
                    "doc_info": doc_info,  # Reference to the doc_info part
                    "sort_key": sort_key,  # Numeric key for sorting
                    "summary": version_summary,  # Extracted data for linking
                }
            )
        except json.JSONDecodeError as e:
            logger.error(
                f"Error decoding JSON from {file_path} during version linking: {e}"
            )
        except IOError as e:
            logger.error(f"Error reading file {file_path} during version linking: {e}")
        except Exception as e:
            logger.error(
                f"Unexpected error loading data for linking from {file_path}: {e}",
                exc_info=True,
            )

    # Check if any valid data was loaded
    if not loaded_versions:
        logger.error(
            f"No valid version data loaded for linking group: {sr_notation or 'Unknown SR'}"
        )
        return

    # Sort versions based on numeric_nachtragsnummer (ascending), use filepath as tiebreaker
    loaded_versions.sort(key=lambda x: (x["sort_key"], x["file_path"]))

    # Link versions
    update_count = 0
    for i in range(len(loaded_versions)):
        current_version = loaded_versions[i]
        current_doc_info = current_version["doc_info"]
        current_sort_key = current_version["sort_key"]

        # Skip linking for versions with invalid sort keys (treated as latest)
        if current_sort_key == float("inf"):
            current_doc_info["versions"] = {"older_versions": [], "newer_versions": []}
            current_version["needs_save"] = (
                True  # Mark for saving if structure was missing
            )
            continue

        older_versions_summary = []
        newer_versions_summary = []

        # Compare with all other versions in the group
        for j in range(len(loaded_versions)):
            if i == j:
                continue  # Don't compare with self

            other_version = loaded_versions[j]
            other_sort_key = other_version["sort_key"]

            # Skip comparison if the other version has an invalid sort key
            if other_sort_key == float("inf"):
                continue

            # Add to older or newer list based on sort key
            if other_sort_key < current_sort_key:
                older_versions_summary.append(other_version["summary"])
            elif other_sort_key > current_sort_key:
                newer_versions_summary.append(other_version["summary"])

        # Sort the older/newer lists for consistency (optional but good practice)
        # Sort older descending by numeric key (most recent older first)
        older_versions_summary.sort(
            key=lambda x: x.get(
                "numeric_nachtragsnummer", -1
            ),  # Use -1 for None to sort them earliest
            reverse=True,
        )
        # Sort newer ascending by numeric key (earliest newer first)
        newer_versions_summary.sort(
            key=lambda x: x.get(
                "numeric_nachtragsnummer", float("inf")
            )  # Use inf for None to sort them latest
        )

        # Prepare the new versions structure
        new_versions_dict = {
            "older_versions": older_versions_summary,
            "newer_versions": newer_versions_summary,
        }

        # Compare with existing structure to see if update is needed
        # Serialize to JSON strings for reliable comparison of potentially complex structures
        old_versions_str = json.dumps(
            current_doc_info.get("versions", {}), sort_keys=True
        )
        new_versions_str = json.dumps(new_versions_dict, sort_keys=True)

        if old_versions_str != new_versions_str:
            current_doc_info["versions"] = (
                new_versions_dict  # Update the doc_info in place
            )
            current_version["needs_save"] = True  # Mark this version's data for saving
            update_count += 1
        else:
            current_version["needs_save"] = False  # No changes needed for this file

    # Save files that were marked for update
    if update_count > 0:
        logger.info(
            f"Updating version links in {update_count} files for SR {sr_notation or 'Unknown SR'}."
        )
        for version_info in loaded_versions:
            if version_info.get("needs_save"):
                try:
                    # Write the entire modified data structure back to the file
                    with open(version_info["file_path"], "w", encoding="utf-8") as f:
                        json.dump(
                            version_info["full_data"], f, ensure_ascii=False, indent=4
                        )
                except IOError as e:
                    logger.error(
                        f"Error writing updated version links to {version_info['file_path']}: {e}"
                    )
                except Exception as e:
                    logger.error(
                        f"Unexpected error writing link update {version_info['file_path']}: {e}",
                        exc_info=True,
                    )


# --- File Discovery ---


def group_files_by_uid(base_dir):
    """Scans the base directory structure and groups metadata file paths by SR Notation (UID)."""
    groups = {}  # Dictionary to store {sr_notation: [list_of_metadata_paths]}
    logger.info(f"Scanning for law groups in: {base_dir}")
    if not os.path.isdir(base_dir):
        logger.error(f"Base directory not found: {base_dir}")
        return groups  # Return empty dict if base directory doesn't exist

    try:
        # Iterate through items in the base directory (expected to be SR notation folders)
        for uid_folder in os.listdir(base_dir):
            law_path = os.path.join(base_dir, uid_folder)
            # Check if it's a directory and matches the expected SR notation pattern
            if os.path.isdir(law_path) and re.match(r"^[0-9.]+$", uid_folder):
                try:
                    # Iterate through items inside the SR notation folder (expected to be YYYYMMDD version folders)
                    for version_folder in os.listdir(law_path):
                        version_path = os.path.join(law_path, version_folder)
                        # Check if it's a directory and matches the YYYYMMDD pattern
                        if os.path.isdir(version_path) and re.fullmatch(
                            r"\d{8}", version_folder
                        ):
                            # Construct the expected metadata filename
                            metadata_filename = (
                                f"{uid_folder}-{version_folder}-metadata.json"
                            )
                            metadata_filepath = os.path.join(
                                version_path, metadata_filename
                            )
                            # Check if the metadata file actually exists
                            if os.path.isfile(metadata_filepath):
                                # Add the file path to the corresponding SR group
                                groups.setdefault(uid_folder, []).append(
                                    metadata_filepath
                                )
                except OSError as e:
                    logger.error(
                        f"Error accessing or listing files within {law_path}: {e}"
                    )
                    # Continue to the next SR folder even if one fails
                    continue
    except OSError as e:
        logger.error(f"Error listing base directory {base_dir}: {e}")

    logger.info(
        f"Found {len(groups)} law groups with {sum(len(paths) for paths in groups.values())} total metadata files."
    )
    return groups


# --- Main Processing Routine ---


def main():
    """Main function to orchestrate the Fedlex data processing."""
    start_time = time.time()
    logger.info("--- Starting Fedlex Data Processing Script ---")

    try:
        # Determine project root directory relative to the script location
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
    except NameError:
        # Fallback if __file__ is not defined (e.g., running in an interactive environment)
        logger.warning(
            "Could not determine script directory via __file__. Using current working directory as project root."
        )
        project_root = os.getcwd()

    # Define paths relative to the project root
    hierarchy_file = os.path.join(
        project_root,
        "data",
        "fedlex",
        "fedlex_data",
        "fedlex_cc_folders_hierarchy.json",
    )
    base_data_dir = os.path.join(project_root, "data", "fedlex", "fedlex_files")

    logger.info(f"Project root determined as: {project_root}")
    logger.info(f"Expecting hierarchy file at: {hierarchy_file}")
    logger.info(f"Expecting base data directory at: {base_data_dir}")

    # --- Pre-checks ---
    # Check if base data directory exists
    if not os.path.isdir(base_data_dir):
        logger.error(
            f"Base data directory not found: {base_data_dir}. Please create it or check the path. Exiting."
        )
        return  # Cannot proceed without the data directory

    # Load hierarchy data
    hierarchy = None
    try:
        with open(hierarchy_file, "r", encoding="utf-8") as f:
            hierarchy = json.load(f)
        logger.info("Successfully loaded category hierarchy.")
    except FileNotFoundError:
        logger.error(
            f"Hierarchy file not found: {hierarchy_file}. Category assignment will fail. Exiting."
        )
        return
    except json.JSONDecodeError as e:
        logger.error(
            f"Error decoding JSON from hierarchy file {hierarchy_file}: {e}. Exiting."
        )
        return
    except Exception as e:  # Catch other potential loading errors
        logger.error(
            f"Unexpected error loading hierarchy file {hierarchy_file}: {e}",
            exc_info=True,
        )
        return

    # --- Phase 1: Discover Existing Laws & Download New/Missing Versions ---
    logger.info(
        "--- Phase 1: Discovering laws and checking/downloading new versions ---"
    )
    # Scan the directory to find existing laws and their versions
    law_groups_phase1 = group_files_by_uid(base_data_dir)
    all_sr_notations = sorted(list(law_groups_phase1.keys()))
    num_existing_laws = len(all_sr_notations)
    logger.info(f"Found {num_existing_laws} existing law groups locally.")

    if num_existing_laws == 0:
        logger.warning(
            "No existing laws found in the data directory. The script will only check for updates if SR notations are known through other means or if the SPARQL query is modified to discover all laws."
        )
        # Depending on requirements, might want to add logic here to fetch *all* SRs from SPARQL if local dir is empty.
        # For now, we proceed assuming updates are checked based on locally present SRs.

    # Initialize cache for aufhebungsdatum (persists across batches)
    aufhebungsdatum_cache = {}
    total_downloaded_files = 0
    num_batches_phase1 = (
        (num_existing_laws + BATCH_SIZE - 1) // BATCH_SIZE
        if num_existing_laws > 0
        else 0
    )

    # Process laws in batches
    for i in range(0, num_existing_laws, BATCH_SIZE):
        batch_start_time = time.time()
        current_batch_srs = all_sr_notations[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        logger.info(
            f"--> Starting Phase 1 / Batch {batch_num}/{num_batches_phase1} ({len(current_batch_srs)} laws)..."
        )

        # Process the batch: fetch data, identify missing, download
        batch_download_results = process_law_versions_batched(
            current_batch_srs, base_data_dir, aufhebungsdatum_cache
        )
        batch_download_count = sum(batch_download_results.values())
        total_downloaded_files += batch_download_count

        batch_duration = time.time() - batch_start_time
        logger.info(
            f"<-- Finished Phase 1 / Batch {batch_num}. Downloaded {batch_download_count} files. Duration: {batch_duration:.2f}s"
        )

    logger.info(
        f"--- Phase 1 Summary: Finished checking all {num_existing_laws} discovered laws. Downloaded a total of {total_downloaded_files} new version files. ---"
    )

    # --- Phase 2: Update Metadata (Dynamic Source, Status, Category) ---
    logger.info("--- Phase 2: Updating metadata for all local files ---")
    # Rescan directory to include newly downloaded files
    law_groups_phase2 = group_files_by_uid(base_data_dir)
    # Flatten the list of all metadata file paths
    all_metadata_files = [
        path for paths in law_groups_phase2.values() for path in paths
    ]
    num_total_files = len(all_metadata_files)
    logger.info(f"Found {num_total_files} total metadata files for processing.")

    if num_total_files > 0:
        num_batches_phase2 = (num_total_files + BATCH_SIZE - 1) // BATCH_SIZE
        total_updated_metadata = 0
        # Process metadata files in batches
        for i in range(0, num_total_files, BATCH_SIZE):
            batch_start_time = time.time()
            current_batch_files = all_metadata_files[i : i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            logger.info(
                f"--> Starting Phase 2 / Batch {batch_num}/{num_batches_phase2} ({len(current_batch_files)} files)..."
            )

            # Process the batch of metadata files
            # Pass the hierarchy data and the populated aufhebungsdatum_cache
            processed_srs = process_metadata_file_batch(
                current_batch_files, hierarchy, aufhebungsdatum_cache
            )
            # Note: process_metadata_file_batch logs the number of files updated within the batch

            batch_duration = time.time() - batch_start_time
            logger.info(
                f"<-- Finished Phase 2 / Batch {batch_num}. Duration: {batch_duration:.2f}s"
            )
            # We don't have a direct count of updated files returned, rely on internal logging of process_metadata_file_batch
    else:
        logger.warning("No metadata files found to process in Phase 2.")

    logger.info("--- Phase 2 Summary: Metadata update process complete. ---")

    # --- Phase 3: Update Version Links ---
    logger.info("--- Phase 3: Updating older/newer version links ---")
    # Rescan directory again to ensure all files are considered
    law_groups_phase3 = group_files_by_uid(base_data_dir)
    num_law_groups = len(law_groups_phase3)
    logger.info(f"Found {num_law_groups} law groups for version linking.")

    if num_law_groups > 0:
        processed_group_count = 0
        # Iterate through each law group (SR Notation)
        for sr_notation, file_paths in law_groups_phase3.items():
            processed_group_count += 1
            # Log progress periodically
            if (
                processed_group_count % 50 == 0
                or processed_group_count == num_law_groups
            ):
                logger.info(
                    f"Processing Phase 3 / Group {processed_group_count}/{num_law_groups} (SR: {sr_notation})..."
                )

            # Update links within the files of this specific law group
            update_versions_for_law_group(file_paths)
            # update_versions_for_law_group logs internally if updates were made
    else:
        logger.warning("No law groups found for version linking in Phase 3.")

    logger.info("--- Phase 3 Summary: Version linking complete. ---")

    # --- Final Summary ---
    end_time = time.time()
    total_duration = end_time - start_time
    logger.info(
        f"--- Script finished successfully in {total_duration:.2f} seconds. ---"
    )


if __name__ == "__main__":
    main()
