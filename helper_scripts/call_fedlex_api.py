#!/usr/bin/env python3
import os
import json
import time
import requests

# Set your SPARQL endpoint URL (update if necessary)
SPARQL_ENDPOINT = "https://fedlex.data.admin.ch/sparqlendpoint"

# Delay in seconds between requests
DELAY_SECONDS = 0.5


def convert_date(date_str):
    """
    Convert a date in YYYYMMDD format to YYYY-MM-DD.
    If the string is not exactly 8 digits, it is returned unchanged.
    """
    if len(date_str) == 8 and date_str.isdigit():
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    return date_str


def process_metadata_file(file_path):
    """
    For a given metadata JSON file, extract the ordnungsnummer and publikationsdatum,
    perform a SPARQL query using these values, and update the metadata with values
    returned by the query.
    """
    # Load existing metadata
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading JSON from {file_path}: {e}")
        return

    doc_info = data.get("doc_info", {})

    # Retrieve the ordnungsnummer and publikationsdatum from the metadata.
    # Note: The publikationsdatum should have been set using the date from the filename.
    sr = doc_info.get("ordnungsnummer", "").strip()
    publikation = doc_info.get("publikationsdatum", "").strip()
    if not sr or not publikation:
        print(
            f"Missing 'ordnungsnummer' or 'publikationsdatum' in {file_path}. Skipping."
        )
        return

    # Convert the publikationsdatum (e.g., "20210701") to ISO format ("2021-07-01")
    valid_date = convert_date(publikation)

    # Build the SPARQL query using .format() with double braces for literal curly braces.
    query = """
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
PREFIX skos:  <http://www.w3.org/2004/02/skos/core#>
PREFIX xsd:   <http://www.w3.org/2001/XMLSchema#>

SELECT DISTINCT 
  ?title 
  ?abbreviation 
  ?titleAlternative 
  (str(?dateDocumentNode) AS ?dateDocument) 
  (str(?dateEntryInForceNode) AS ?dateEntryInForce) 
  (str(?publicationDateNode) AS ?publicationDate) 
  (str(?languageNotation) AS ?languageTag) 
  (str(?dateApplicabilityNode) AS ?dateApplicability) 
  (str(?fileFormatNode) AS ?fileFormat) 
  ?fileUri
{{
  VALUES (?srString)        {{ ("{sr}") }}
  VALUES (?validDateString) {{ ("{valid_date}") }}
  
  ?consoAbstract a jolux:ConsolidationAbstract .
  ?consoAbstract jolux:classifiedByTaxonomyEntry/skos:notation ?rsNotation . 
  FILTER(str(?rsNotation) = ?srString)
  
  # Retrieve dateDocument, dateEntryInForce, and publicationDate from the abstract
  ?consoAbstract jolux:dateDocument ?dateDocumentNode . 
  OPTIONAL {{ ?consoAbstract jolux:dateEntryInForce ?dateEntryInForceNode . }}
  OPTIONAL {{ ?consoAbstract jolux:publicationDate ?publicationDateNode . }}
  
  ?consoAbstract jolux:isRealizedBy ?consoAbstractExpression .
  ?consoAbstractExpression jolux:language ?languageConcept .
  ?consoAbstractExpression jolux:title ?title .
  OPTIONAL {{ ?consoAbstractExpression jolux:titleShort ?abbreviation . }}
  OPTIONAL {{ ?consoAbstractExpression jolux:titleAlternative ?titleAlternative . }}
  OPTIONAL {{ ?consoAbstract jolux:dateEndApplicability ?ccEndDate . }}
  FILTER(!BOUND(?ccEndDate) || xsd:date(?ccEndDate) >= xsd:date(?validDateString))
  OPTIONAL {{ ?consoAbstract jolux:dateNoLongerInForce ?ccEndForce . }}
  FILTER(!BOUND(?ccEndForce) || xsd:date(?ccEndForce) > xsd:date(?validDateString))
  
  ?conso a jolux:Consolidation .
  ?conso jolux:isMemberOf ?consoAbstract .
  ?conso jolux:dateApplicability ?dateApplicabilityNode .
  OPTIONAL {{ ?conso jolux:dateEndApplicability ?endDate . }}
  FILTER(xsd:date(?dateApplicabilityNode) <= xsd:date(?validDateString))
  FILTER(!BOUND(?endDate) || xsd:date(?endDate) >= xsd:date(?validDateString))
  
  ?conso jolux:isRealizedBy ?consoExpression . 
  ?consoExpression jolux:isEmbodiedBy ?manifestation .
  ?consoExpression jolux:language ?languageConcept .
  ?manifestation jolux:isExemplifiedBy ?fileUri .
  ?manifestation jolux:userFormat/skos:notation ?fileFormatNode . 
  FILTER(datatype(?fileFormatNode) = <https://fedlex.data.admin.ch/vocabulary/notation-type/uri-suffix>)
  
  ?languageConcept skos:notation ?languageNotation .
  FILTER(datatype(?languageNotation) = <http://publications.europa.eu/ontology/euvoc#XML_LNG>)
  
  # Only show results where fileFormat is "html"
  FILTER(str(?fileFormatNode) = "html")
  
  # Only show results where language is "de"
  FILTER(str(?languageNotation) = "de")
}}
ORDER BY ?languageTag ?fileFormat
""".format(
        sr=sr, valid_date=valid_date
    )

    headers = {"Accept": "application/sparql-results+json"}
    params = {"query": query}

    try:
        response = requests.get(SPARQL_ENDPOINT, params=params, headers=headers)
        if response.status_code != 200:
            print(f"Error querying SPARQL for {file_path}: HTTP {response.status_code}")
            return
        if not response.text.strip():
            print(f"Empty response for {file_path}")
            return
        try:
            result_json = response.json()
        except json.JSONDecodeError as e:
            print(
                f"JSON decode error for {file_path}: {e}\nResponse text: {response.text}"
            )
            return
    except Exception as e:
        print(f"Exception during SPARQL query for {file_path}: {e}")
        return

    # Check if we got any results
    bindings = result_json.get("results", {}).get("bindings", [])
    if not bindings:
        print(f"No SPARQL results for {file_path}")
        return

    # Take the first result and extract the values (if present)
    result = bindings[0]
    abbreviation = result.get("abbreviation", {}).get("value", "")
    title_alternative = result.get("titleAlternative", {}).get("value", "")
    date_entry_in_force = result.get("dateEntryInForce", {}).get("value", "")
    file_uri = result.get("fileUri", {}).get("value", "")

    # Map SPARQL response values into metadata
    doc_info["abkuerzung"] = abbreviation
    doc_info["kurztitel"] = title_alternative
    doc_info["inkraftsetzungsdatum"] = date_entry_in_force
    doc_info["law_text_url"] = file_uri

    # Write back the updated metadata file (overwrite it)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Updated metadata file: {file_path}")
    except Exception as e:
        print(f"Error writing updated metadata to {file_path}: {e}")


def update_all_metadata():
    """
    Walk through the folder structure (data/fedlex/fedlex_files_processed) and process
    every file ending with -metadata.json.
    """
    base_dir = "data/fedlex/fedlex_files_processed"
    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.endswith("-metadata.json"):
                file_path = os.path.join(root, file)
                process_metadata_file(file_path)
                # Wait between requests to avoid rate limiting
                time.sleep(DELAY_SECONDS)


if __name__ == "__main__":
    update_all_metadata()
