import os
import json
import time
import requests
import arrow

# The SPARQL endpoint URL
SPARQL_ENDPOINT = "https://fedlex.data.admin.ch/sparqlendpoint"

# The SPARQL query
SPARQL_QUERY = """
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
PREFIX skos:  <http://www.w3.org/2004/02/skos/core#>
PREFIX xsd:   <http://www.w3.org/2001/XMLSchema#>

SELECT DISTINCT 
  (str(?srNotation) AS ?rsNr) 
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
WHERE {
  # Use the current date for all validity comparisons
  BIND(now() AS ?currentDate)
  # Use German as the language filter (DEU and “de”)
  BIND(<http://publications.europa.eu/resource/authority/language/DEU> AS ?language)
  
  ######################################################################
  # PART 1: Current Consolidation (law instance) – from Query 1
  ######################################################################
  ?consolidation a jolux:Consolidation .
  ?consolidation jolux:dateApplicability ?dateApplicabilityNode .
  OPTIONAL { ?consolidation jolux:dateEndApplicability ?dateEndApplicability . }
  FILTER( xsd:date(?dateApplicabilityNode) <= xsd:date(?currentDate)
          && (!BOUND(?dateEndApplicability) || xsd:date(?dateEndApplicability) >= xsd:date(?currentDate)) )
  
  ?consolidation jolux:isRealizedBy ?consoExpression .
  ?consoExpression jolux:language ?language .
  ?consoExpression jolux:isEmbodiedBy ?manifestation .
  
  # Retrieve the file URL and file format from the manifestation.
  ?manifestation jolux:isExemplifiedBy ?fileURL .
  ?manifestation jolux:userFormat/skos:notation ?fileFormatNode .
  FILTER( datatype(?fileFormatNode) = <https://fedlex.data.admin.ch/vocabulary/notation-type/uri-suffix> )
  FILTER( str(?fileFormatNode) = "html" )
  
  ######################################################################
  # PART 2: Abstract metadata – from Query 2
  ######################################################################
  # Link the consolidation to its abstract (metadata) information.
  ?consolidation jolux:isMemberOf ?consoAbstract .
  ?consoAbstract a jolux:ConsolidationAbstract .
  ?consoAbstract jolux:classifiedByTaxonomyEntry/skos:notation ?srNotation .
  FILTER( datatype(?srNotation) = <https://fedlex.data.admin.ch/vocabulary/notation-type/id-systematique> )
  
  # Validity filters at the abstract level
  OPTIONAL { ?consoAbstract jolux:dateNoLongerInForce ?ccNoLonger . }
  OPTIONAL { ?consoAbstract jolux:dateEndApplicability ?ccEnd . }
  FILTER( !BOUND(?ccNoLonger) || xsd:date(?ccNoLonger) > xsd:date(?currentDate) )
  FILTER( !BOUND(?ccEnd) || xsd:date(?ccEnd) >= xsd:date(?currentDate) )
  
  # Abstract dates and title information
  ?consoAbstract jolux:dateDocument ?dateDocumentNode .
  OPTIONAL { ?consoAbstract jolux:dateEntryInForce ?dateEntryInForceNode . }
  OPTIONAL { ?consoAbstract jolux:publicationDate ?publicationDateNode . }
  
  ?consoAbstract jolux:isRealizedBy ?consoAbstractExpression .
  ?consoAbstractExpression jolux:language ?languageConcept .
  ?consoAbstractExpression jolux:title ?title .
  OPTIONAL { ?consoAbstractExpression jolux:titleShort ?abbreviation . }
  OPTIONAL { ?consoAbstractExpression jolux:titleAlternative ?titleAlternative . }
  
  # Optionally retrieve the “aufhebungsdatum” if available.
  OPTIONAL {
    ?consoAbstract jolux:aufhebungsdatum ?aufhebungsdatum .
  }
  
  # Further validity filters on the abstract’s applicability dates
  OPTIONAL { ?consoAbstract jolux:dateEndApplicability ?ccEndDate . }
  FILTER( !BOUND(?ccEndDate) || xsd:date(?ccEndDate) >= xsd:date(?currentDate) )
  OPTIONAL { ?consoAbstract jolux:dateNoLongerInForce ?ccEndForce . }
  FILTER( !BOUND(?ccEndForce) || xsd:date(?ccEndForce) > xsd:date(?currentDate) )
  
  # Additional properties added:
  OPTIONAL {
    ?consoAbstract <http://cogni.internal.system/model#firstPublicationDate> ?firstPublicationDateNode .
  }
  OPTIONAL {
    ?consoAbstract <http://data.legilux.public.lu/resource/ontology/jolux#basicAct> ?basicAct .
  }
  
  # Language filter on the abstract expression
  ?languageConcept skos:notation ?languageNotation .
  FILTER( datatype(?languageNotation) = <http://publications.europa.eu/ontology/euvoc#XML_LNG> )
  FILTER( str(?languageNotation) = "de" )
}
ORDER BY ?srNotation
"""

# Base directories for storing downloaded files and API response data
BASE_FILES_DIR = os.path.join("data", "fedlex", "fedlex_files")
BASE_DATA_DIR = os.path.join("data", "fedlex", "fedlex_data")


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
        print(f"Error parsing date '{date_str}': {e}")
        return ""


def main():
    # Ensure the base directories exist
    os.makedirs(BASE_FILES_DIR, exist_ok=True)
    os.makedirs(BASE_DATA_DIR, exist_ok=True)

    print("Querying the Fedlex SPARQL endpoint...")
    headers = {"Accept": "application/sparql-results+json"}

    response = requests.get(
        SPARQL_ENDPOINT, params={"query": SPARQL_QUERY}, headers=headers
    )
    if response.status_code != 200:
        print("Error querying the SPARQL endpoint:", response.text)
        return

    # Parse and store the API response
    response_json = response.json()
    response_file = os.path.join(BASE_DATA_DIR, "fedlex_response.json")
    with open(response_file, "w", encoding="utf-8") as f:
        json.dump(response_json, f, indent=4, ensure_ascii=False)
    print(f"Stored the API response at: {response_file}")

    results = response_json.get("results", {}).get("bindings", [])
    print(f"Received {len(results)} result(s) from the query.")

    for result in results:
        # Extract fields safely
        rsNr = result.get("rsNr", {}).get("value", "").strip()
        dateApplicability_raw = (
            result.get("dateApplicability", {}).get("value", "").strip()
        )
        title = result.get("title", {}).get("value", "").strip()
        abbreviation = result.get("abbreviation", {}).get("value", "").strip()
        titleAlternative = result.get("titleAlternative", {}).get("value", "").strip()
        dateDocument_raw = result.get("dateDocument", {}).get("value", "").strip()
        dateEntryInForce_raw = (
            result.get("dateEntryInForce", {}).get("value", "").strip()
        )
        publicationDate_raw = result.get("publicationDate", {}).get("value", "").strip()
        fileURL = result.get("fileURL", {}).get("value", "").strip()
        aufhebungsdatum_raw = result.get("aufhebungsdatum", {}).get("value", "").strip()

        # Format the dates into YYYYMMDD using arrow.
        dateApplicability = format_date(dateApplicability_raw)
        erlassdatum = format_date(dateDocument_raw)
        inkraftsetzungsdatum = format_date(dateEntryInForce_raw)
        # Use dateApplicability as fallback for publikationsdatum if not provided.
        publikationsdatum = (
            format_date(publicationDate_raw)
            if publicationDate_raw
            else dateApplicability
        )
        aufhebungsdatum = format_date(aufhebungsdatum_raw)

        # Compute numeric_nachtragsnummer as a float (e.g. 20250203.0) if possible.
        try:
            numeric_nachtragsnummer = (
                float(dateApplicability) if dateApplicability else None
            )
        except Exception as e:
            print(
                f"Error converting dateApplicability '{dateApplicability}' to numeric: {e}"
            )
            numeric_nachtragsnummer = None

        # Build the output directory structure: data/fedlex/fedlex_files/<rsNr>/<dateApplicability>
        folder_path = os.path.join(BASE_FILES_DIR, rsNr, dateApplicability)
        os.makedirs(folder_path, exist_ok=True)

        # Define the filenames for the raw HTML and metadata JSON.
        raw_html_filename = f"{rsNr}-{dateApplicability}-raw.html"
        metadata_filename = f"{rsNr}-{dateApplicability}-metadata.json"
        raw_html_path = os.path.join(folder_path, raw_html_filename)
        metadata_path = os.path.join(folder_path, metadata_filename)

        # Skip processing if the files already exist.
        if os.path.exists(raw_html_path) and os.path.exists(metadata_path):
            print(
                f"Files for law {rsNr} (applicability date: {dateApplicability}) already exist. Skipping."
            )
            continue

        # Download the HTML file from fileURL
        print(
            f"Downloading HTML for law {rsNr} (applicability date: {dateApplicability})..."
        )
        try:
            html_response = requests.get(fileURL)
            if html_response.status_code == 200:
                # Set the encoding to the apparent encoding so that special characters are decoded correctly.
                html_response.encoding = html_response.apparent_encoding
                html_text = html_response.text
                with open(raw_html_path, "w", encoding="utf-8") as f:
                    f.write(html_text)
            else:
                print(
                    f"Warning: Could not download HTML from {fileURL}. HTTP status code: {html_response.status_code}"
                )
                continue
        except Exception as e:
            print(f"Error downloading HTML from {fileURL}: {e}")
            continue

        # Build the metadata JSON structure.
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
                "in_force": False,
                "bandnummer": "",
                "hinweise": "",
                "erlasstitel": title,
                "ordnungsnummer": rsNr,
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
            }
        }

        # Save the metadata JSON file
        with open(metadata_path, "w", encoding="utf-8") as meta_file:
            json.dump(metadata, meta_file, indent=4, ensure_ascii=False)

        print(f"Saved HTML to: {raw_html_path}")
        print(f"Saved metadata to: {metadata_path}")

        # Add a delay between processing each record for server compatibility.
        time.sleep(0.2)  # Adjust delay (in seconds) if needed


if __name__ == "__main__":
    main()
