"""SPARQL client for querying the Fedlex endpoint.

This module handles all SPARQL queries to the Fedlex endpoint, including
retry logic, error handling, and result parsing.

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import logging
import time
from typing import Dict, List, Optional, Any
import requests

from . import fedlex_config as config
from .fedlex_models import SPARQLResults, LawVersion
from .fedlex_utils import retry_on_failure, format_date

logger = logging.getLogger(__name__)


class SPARQLClient:
    """Client for interacting with the Fedlex SPARQL endpoint."""
    
    def __init__(self, endpoint: str = config.SPARQL_ENDPOINT):
        """Initialize the SPARQL client.
        
        Args:
            endpoint: SPARQL endpoint URL
        """
        self.endpoint = endpoint
        self.session = requests.Session()
        self.session.headers.update(config.SPARQL_HEADERS)
    
    def execute_query(self, query: str) -> Optional[SPARQLResults]:
        """Execute a SPARQL query with retry logic.
        
        Args:
            query: SPARQL query string
            
        Returns:
            SPARQLResults object or None if failed
        """
        @retry_on_failure(
            max_retries=config.SPARQL_MAX_RETRIES,
            delay=config.SPARQL_DELAY_BETWEEN_REQUESTS
        )
        def _execute():
            response = self.session.get(
                self.endpoint,
                params={"query": query},
                timeout=config.SPARQL_TIMEOUT
            )
            response.raise_for_status()
            
            if not response.text or response.text.isspace():
                raise ValueError("Empty response from SPARQL endpoint")
            
            return SPARQLResults(**response.json())
        
        try:
            return _execute()
        except Exception as e:
            logger.error(f"Failed to execute SPARQL query: {e}")
            return None
    
    def get_current_laws(self) -> List[LawVersion]:
        """Get all currently valid laws from Fedlex.
        
        Returns:
            List of LawVersion objects
        """
        query = """
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
  ?fileURL
WHERE {
  BIND(now() AS ?currentDate)
  BIND(<http://publications.europa.eu/resource/authority/language/DEU> AS ?language)
  
  ?consolidation a jolux:Consolidation .
  ?consolidation jolux:dateApplicability ?dateApplicabilityNode .
  OPTIONAL { ?consolidation jolux:dateEndApplicability ?dateEndApplicability . }
  FILTER( xsd:date(?dateApplicabilityNode) <= xsd:date(?currentDate)
          && (!BOUND(?dateEndApplicability) || xsd:date(?dateEndApplicability) >= xsd:date(?currentDate)) )
  
  ?consolidation jolux:isRealizedBy ?consoExpression .
  ?consoExpression jolux:language ?language .
  ?consoExpression jolux:isEmbodiedBy ?manifestation .
  
  ?manifestation jolux:isExemplifiedBy ?fileURL .
  ?manifestation jolux:userFormat/skos:notation ?fileFormatNode .
  FILTER( datatype(?fileFormatNode) = <https://fedlex.data.admin.ch/vocabulary/notation-type/uri-suffix> )
  FILTER( str(?fileFormatNode) = "html" )
  
  ?consolidation jolux:isMemberOf ?consoAbstract .
  ?consoAbstract a jolux:ConsolidationAbstract .
  ?consoAbstract jolux:classifiedByTaxonomyEntry/skos:notation ?srNotation .
  FILTER( datatype(?srNotation) = <https://fedlex.data.admin.ch/vocabulary/notation-type/id-systematique> )
  
  OPTIONAL { ?consoAbstract jolux:dateNoLongerInForce ?ccNoLonger . }
  OPTIONAL { ?consoAbstract jolux:dateEndApplicability ?ccEnd . }
  FILTER( !BOUND(?ccNoLonger) || xsd:date(?ccNoLonger) > xsd:date(?currentDate) )
  FILTER( !BOUND(?ccEnd) || xsd:date(?ccEnd) >= xsd:date(?currentDate) )
  
  ?consoAbstract jolux:dateDocument ?dateDocumentNode .
  OPTIONAL { ?consoAbstract jolux:dateEntryInForce ?dateEntryInForceNode . }
  OPTIONAL { ?consoAbstract jolux:publicationDate ?publicationDateNode . }
  
  ?consoAbstract jolux:isRealizedBy ?consoAbstractExpression .
  ?consoAbstractExpression jolux:language ?languageConcept .
  ?consoAbstractExpression jolux:title ?title .
  OPTIONAL { ?consoAbstractExpression jolux:titleShort ?abbreviation . }
  OPTIONAL { ?consoAbstractExpression jolux:titleAlternative ?titleAlternative . }
  
  OPTIONAL {
    ?consoAbstract jolux:aufhebungsdatum ?aufhebungsdatum .
  }
  
  ?languageConcept skos:notation ?languageNotation .
  FILTER( datatype(?languageNotation) = <http://publications.europa.eu/ontology/euvoc#XML_LNG> )
  FILTER( str(?languageNotation) = "de" )
}
ORDER BY ?srNotation
"""
        results = self.execute_query(query)
        if not results:
            return []
        
        laws = []
        for binding in results.to_bindings():
            law = LawVersion(
                sr_number=binding.get_value("rsNr"),
                date_applicability=binding.get_value("dateApplicability"),
                title=binding.get_value("title"),
                abbreviation=binding.get_value("abbreviation"),
                title_alternative=binding.get_value("titleAlternative"),
                date_document=binding.get_value("dateDocument"),
                date_entry_in_force=binding.get_value("dateEntryInForce"),
                publication_date=binding.get_value("publicationDate"),
                file_url=binding.get_value("fileURL"),
                aufhebungsdatum=binding.get_value("aufhebungsdatum")
            )
            if law.sr_number and law.date_applicability and law.file_url:
                laws.append(law)
        
        logger.info(f"Retrieved {len(laws)} current laws from SPARQL")
        return laws
    
    def get_aufhebungsdatum_batch(self, sr_numbers: List[str]) -> Dict[str, str]:
        """Get aufhebungsdatum for multiple SR numbers.
        
        Args:
            sr_numbers: List of SR numbers to query
            
        Returns:
            Dictionary mapping SR numbers to aufhebungsdatum
        """
        if not sr_numbers:
            return {}
        
        unique_numbers = sorted(list(set(sr_numbers)))
        values_clause = " ".join([f'"{num}"' for num in unique_numbers])
        
        query = f"""
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
PREFIX skos:  <http://www.w3.org/2004/02/skos/core#>

SELECT DISTINCT ?srNotationValue ?consoAbstract (STR(?aufhebungsdatum) AS ?aufhebungsdatumStr)
WHERE {{
  VALUES ?srNotationValue {{ {values_clause} }}

  ?taxonomyEntry skos:notation ?srNotationLiteral .
  FILTER(STR(?srNotationLiteral) = ?srNotationValue)
  FILTER( datatype(?srNotationLiteral) = <https://fedlex.data.admin.ch/vocabulary/notation-type/id-systematique> )

  ?consoAbstract jolux:classifiedByTaxonomyEntry ?taxonomyEntry .
  ?consoAbstract a jolux:ConsolidationAbstract .

  OPTIONAL {{ ?consoAbstract jolux:aufhebungsdatum ?aufhebungsdatum . }}
}}
"""
        
        results = self.execute_query(query)
        if not results:
            return {num: "" for num in unique_numbers}
        
        aufhebung_data = {}
        for binding in results.bindings:
            sr_num = binding.get("srNotationValue", {}).get("value", "")
            aufhebung = binding.get("aufhebungsdatumStr", {}).get("value", "")
            if sr_num:
                aufhebung_data[sr_num] = format_date(aufhebung)
        
        # Ensure all requested numbers have an entry
        for num in unique_numbers:
            if num not in aufhebung_data:
                aufhebung_data[num] = ""
        
        logger.info(f"Retrieved aufhebungsdatum for {len(aufhebung_data)} SR numbers")
        time.sleep(config.SPARQL_DELAY_BETWEEN_REQUESTS)
        return aufhebung_data
    
    def get_all_versions_batch(self, sr_numbers: List[str]) -> Dict[str, List[LawVersion]]:
        """Get all versions for multiple SR numbers.
        
        Args:
            sr_numbers: List of SR numbers to query
            
        Returns:
            Dictionary mapping SR numbers to their versions
        """
        if not sr_numbers:
            return {}
        
        unique_numbers = sorted(list(set(sr_numbers)))
        values_clause = " ".join([f'"{num}"' for num in unique_numbers])
        
        query = f"""
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
PREFIX skos:  <http://www.w3.org/2004/02/skos/core#>
PREFIX xsd:   <http://www.w3.org/2001/XMLSchema#>
PREFIX dct:   <http://purl.org/dc/terms/>

SELECT DISTINCT
  ?srNotationValue ?consoAbstract
  (STR(?dateApplicabilityNode) AS ?dateApplicability)
  ?title ?titleShort ?titleAlternative
  (STR(?dateDocumentNode) AS ?dateDocument)
  (STR(?dateEntryInForceNode) AS ?dateEntryInForce)
  (STR(?publicationDateNode) AS ?publicationDate)
  ?fileURL
WHERE {{
  BIND(<http://publications.europa.eu/resource/authority/language/DEU> AS ?language)
  VALUES ?srNotationValue {{ {values_clause} }}

  ?taxonomyEntry skos:notation ?srNotationLiteral .
  FILTER(STR(?srNotationLiteral) = ?srNotationValue)
  FILTER( datatype(?srNotationLiteral) = <https://fedlex.data.admin.ch/vocabulary/notation-type/id-systematique> )

  ?consoAbstract jolux:classifiedByTaxonomyEntry ?taxonomyEntry .
  ?consoAbstract a jolux:ConsolidationAbstract .

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
        
        results = self.execute_query(query)
        if not results:
            return {}
        
        versions_map = {num: [] for num in unique_numbers}
        
        for binding in results.bindings:
            sr_num = binding.get("srNotationValue", {}).get("value", "")
            if not sr_num:
                continue
            
            version = LawVersion(
                sr_number=sr_num,
                date_applicability=binding.get("dateApplicability", {}).get("value", ""),
                title=binding.get("title", {}).get("value", ""),
                abbreviation=binding.get("titleShort", {}).get("value", ""),
                title_alternative=binding.get("titleAlternative", {}).get("value", ""),
                date_document=binding.get("dateDocument", {}).get("value", ""),
                date_entry_in_force=binding.get("dateEntryInForce", {}).get("value", ""),
                publication_date=binding.get("publicationDate", {}).get("value", ""),
                file_url=binding.get("fileURL", {}).get("value", "")
            )
            
            if version.date_applicability and version.file_url:
                versions_map[sr_num].append(version)
        
        logger.info(f"Retrieved versions for {len(versions_map)} SR numbers")
        time.sleep(config.SPARQL_DELAY_BETWEEN_REQUESTS)
        return versions_map
    
    def close(self):
        """Close the session."""
        self.session.close()