"""Data models for the Fedlex module.

This module defines Pydantic models for type-safe data handling throughout
the Fedlex processing pipeline. These models ensure data consistency and
provide validation for all data structures.

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
import arrow


class Category(BaseModel):
    """Represents a category in the law hierarchy."""
    id: Optional[str] = None
    name: Optional[str] = None


class CategoryInfo(BaseModel):
    """Complete category information for a law."""
    folder: Optional[Category] = None
    section: Optional[Category] = None
    subsection: Optional[Category] = None


class VersionSummary(BaseModel):
    """Summary information for a law version, used in version linking."""
    law_page_url: str = ""
    law_text_url: str = ""
    nachtragsnummer: str  # YYYYMMDD format
    numeric_nachtragsnummer: Optional[float] = None
    erlassdatum: str = ""
    inkraftsetzungsdatum: str = ""
    publikationsdatum: str = ""
    aufhebungsdatum: str = ""
    in_force: bool = False
    
    @validator('nachtragsnummer', 'erlassdatum', 'inkraftsetzungsdatum', 
               'publikationsdatum', 'aufhebungsdatum')
    def validate_date_format(cls, v):
        """Ensure dates are in YYYYMMDD format or empty."""
        if v and len(v) == 8 and v.isdigit():
            return v
        elif not v:
            return ""
        else:
            # Try to parse and reformat
            try:
                return arrow.get(v).format("YYYYMMDD")
            except:
                return ""


class VersionLinks(BaseModel):
    """Links to other versions of the same law."""
    older_versions: List[VersionSummary] = Field(default_factory=list)
    newer_versions: List[VersionSummary] = Field(default_factory=list)


class DocInfo(BaseModel):
    """Complete document information for a law version."""
    law_page_url: str = ""
    law_text_url: str = ""
    law_text_redirect: str = ""
    nachtragsnummer: str  # YYYYMMDD format
    numeric_nachtragsnummer: Optional[float] = None
    erlassdatum: str = ""
    inkraftsetzungsdatum: str = ""
    publikationsdatum: str = ""
    aufhebungsdatum: str = ""
    in_force: bool = False
    bandnummer: str = ""
    hinweise: str = ""
    erlasstitel: str = ""
    ordnungsnummer: str  # SR number
    kurztitel: str = ""
    abkuerzung: str = ""
    category: CategoryInfo = Field(default_factory=CategoryInfo)
    dynamic_source: str = ""
    zhlaw_url_dynamic: str = ""
    versions: VersionLinks = Field(default_factory=VersionLinks)


class ProcessSteps(BaseModel):
    """Tracks processing timestamps."""
    download: str = ""
    process: str = ""


class LawMetadata(BaseModel):
    """Complete metadata structure for a law version."""
    doc_info: DocInfo
    process_steps: ProcessSteps = Field(default_factory=ProcessSteps)


class SPARQLBinding(BaseModel):
    """Represents a single binding from SPARQL results."""
    rsNr: Optional[Dict[str, str]] = None
    dateApplicability: Optional[Dict[str, str]] = None
    title: Optional[Dict[str, str]] = None
    abbreviation: Optional[Dict[str, str]] = None
    titleAlternative: Optional[Dict[str, str]] = None
    dateDocument: Optional[Dict[str, str]] = None
    dateEntryInForce: Optional[Dict[str, str]] = None
    publicationDate: Optional[Dict[str, str]] = None
    fileURL: Optional[Dict[str, str]] = None
    aufhebungsdatum: Optional[Dict[str, str]] = None
    
    def get_value(self, field: str) -> str:
        """Extract value from SPARQL binding field."""
        field_data = getattr(self, field, None)
        if field_data and isinstance(field_data, dict):
            return field_data.get("value", "").strip()
        return ""


class SPARQLResults(BaseModel):
    """Complete SPARQL query results."""
    results: Dict[str, Any] = Field(default_factory=dict)
    
    @property
    def bindings(self) -> List[Dict[str, Any]]:
        """Get bindings from results."""
        return self.results.get("bindings", [])
    
    def to_bindings(self) -> List[SPARQLBinding]:
        """Convert raw bindings to typed objects."""
        return [SPARQLBinding(**binding) for binding in self.bindings]


class LawVersion(BaseModel):
    """Represents a single version of a law from SPARQL."""
    sr_number: str
    date_applicability: str  # YYYYMMDD
    title: str = ""
    abbreviation: str = ""
    title_alternative: str = ""
    date_document: str = ""
    date_entry_in_force: str = ""
    publication_date: str = ""
    file_url: str = ""
    aufhebungsdatum: str = ""
    
    @validator('date_applicability', 'date_document', 'date_entry_in_force', 
               'publication_date', 'aufhebungsdatum')
    def format_dates(cls, v):
        """Ensure dates are formatted as YYYYMMDD."""
        if not v:
            return ""
        try:
            return arrow.get(v).format("YYYYMMDD")
        except:
            return ""
    
    @property
    def numeric_date(self) -> Optional[float]:
        """Convert date_applicability to numeric format."""
        try:
            return float(self.date_applicability) if self.date_applicability else None
        except ValueError:
            return None
    
    def to_metadata(self) -> LawMetadata:
        """Convert to full metadata structure."""
        doc_info = DocInfo(
            law_text_url=self.file_url,
            nachtragsnummer=self.date_applicability,
            numeric_nachtragsnummer=self.numeric_date,
            erlassdatum=self.date_document,
            inkraftsetzungsdatum=self.date_entry_in_force,
            publikationsdatum=self.publication_date or self.date_applicability,
            aufhebungsdatum=self.aufhebungsdatum,
            in_force=not bool(self.aufhebungsdatum),
            erlasstitel=self.title,
            ordnungsnummer=self.sr_number,
            kurztitel=self.title_alternative,
            abkuerzung=self.abbreviation
        )
        return LawMetadata(doc_info=doc_info)


class ProcessingResult(BaseModel):
    """Result of a processing operation."""
    success: bool
    message: str = ""
    data: Optional[Any] = None
    error: Optional[str] = None


class DownloadResult(BaseModel):
    """Result of a file download operation."""
    success: bool
    file_path: Optional[str] = None
    error: Optional[str] = None
    retries: int = 0