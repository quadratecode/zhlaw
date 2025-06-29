"""
HTML operation utilities for ZHLaw processing system.

This module provides common HTML operations with BeautifulSoup,
reducing code duplication across HTML processing modules.

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

from typing import List, Dict, Any, Optional, Callable, Union
from pathlib import Path
from bs4 import BeautifulSoup, Tag, NavigableString
import re

from src.logging_config import get_logger
from src.constants import HTMLClasses, DataAttributes

logger = get_logger(__name__)


class HTMLProcessor:
    """Common HTML processing operations with BeautifulSoup."""
    
    def __init__(self, parser: str = "html.parser"):
        """
        Initialize HTML processor.
        
        Args:
            parser: BeautifulSoup parser to use
        """
        self.parser = parser
    
    def parse_html(self, html_content: str) -> BeautifulSoup:
        """
        Parse HTML content into BeautifulSoup object.
        
        Args:
            html_content: HTML string
            
        Returns:
            BeautifulSoup object
        """
        return BeautifulSoup(html_content, self.parser)
    
    def parse_html_file(self, file_path: Path, encoding: str = "utf-8") -> BeautifulSoup:
        """
        Parse HTML from file.
        
        Args:
            file_path: Path to HTML file
            encoding: File encoding
            
        Returns:
            BeautifulSoup object
        """
        with open(file_path, 'r', encoding=encoding) as f:
            return self.parse_html(f.read())
    
    @staticmethod
    def find_elements_by_class(
        soup: BeautifulSoup, 
        class_name: str, 
        tag: Optional[str] = None
    ) -> List[Tag]:
        """
        Find all elements with a specific class.
        
        Args:
            soup: BeautifulSoup object
            class_name: CSS class name
            tag: Optional tag name to filter
            
        Returns:
            List of matching elements
        """
        return soup.find_all(tag, class_=class_name)
    
    @staticmethod
    def find_elements_by_attribute(
        soup: BeautifulSoup,
        attr_name: str,
        attr_value: Optional[str] = None,
        tag: Optional[str] = None
    ) -> List[Tag]:
        """
        Find elements by attribute.
        
        Args:
            soup: BeautifulSoup object
            attr_name: Attribute name
            attr_value: Optional attribute value
            tag: Optional tag name to filter
            
        Returns:
            List of matching elements
        """
        if attr_value is None:
            # Find elements that have the attribute
            return soup.find_all(tag, attrs={attr_name: True})
        else:
            # Find elements with specific attribute value
            return soup.find_all(tag, attrs={attr_name: attr_value})
    
    @staticmethod
    def extract_text(element: Union[Tag, BeautifulSoup], separator: str = " ") -> str:
        """
        Extract clean text from an element.
        
        Args:
            element: BeautifulSoup element
            separator: Text separator
            
        Returns:
            Cleaned text content
        """
        return element.get_text(separator=separator, strip=True)
    
    @staticmethod
    def create_element(
        tag_name: str,
        content: Optional[str] = None,
        attrs: Optional[Dict[str, str]] = None,
        classes: Optional[List[str]] = None
    ) -> Tag:
        """
        Create a new HTML element.
        
        Args:
            tag_name: HTML tag name
            content: Text content
            attrs: Element attributes
            classes: CSS classes
            
        Returns:
            New BeautifulSoup Tag
        """
        soup = BeautifulSoup("", "html.parser")
        tag = soup.new_tag(tag_name)
        
        if content:
            tag.string = content
        
        if attrs:
            for key, value in attrs.items():
                tag[key] = value
        
        if classes:
            tag["class"] = classes
        
        return tag
    
    @staticmethod
    def add_class(element: Tag, class_name: str) -> None:
        """
        Add a CSS class to an element.
        
        Args:
            element: BeautifulSoup Tag
            class_name: Class name to add
        """
        if "class" in element.attrs:
            if class_name not in element["class"]:
                element["class"].append(class_name)
        else:
            element["class"] = [class_name]
    
    @staticmethod
    def remove_class(element: Tag, class_name: str) -> None:
        """
        Remove a CSS class from an element.
        
        Args:
            element: BeautifulSoup Tag
            class_name: Class name to remove
        """
        if "class" in element.attrs and class_name in element["class"]:
            element["class"].remove(class_name)
            if not element["class"]:
                del element["class"]
    
    @staticmethod
    def wrap_element(element: Tag, wrapper_tag: str, **wrapper_attrs) -> Tag:
        """
        Wrap an element with another tag.
        
        Args:
            element: Element to wrap
            wrapper_tag: Wrapper tag name
            **wrapper_attrs: Attributes for wrapper
            
        Returns:
            Wrapper element
        """
        wrapper = element.wrap(element.parent.new_tag(wrapper_tag))
        for key, value in wrapper_attrs.items():
            wrapper[key] = value
        return wrapper
    
    @staticmethod
    def clean_html(soup: BeautifulSoup, remove_tags: Optional[List[str]] = None) -> BeautifulSoup:
        """
        Clean HTML by removing unwanted tags and empty elements.
        
        Args:
            soup: BeautifulSoup object
            remove_tags: List of tag names to remove
            
        Returns:
            Cleaned BeautifulSoup object
        """
        # Default tags to remove
        if remove_tags is None:
            remove_tags = ["script", "style", "meta", "link"]
        
        # Remove specified tags
        for tag_name in remove_tags:
            for tag in soup.find_all(tag_name):
                tag.decompose()
        
        # Remove empty paragraphs
        for p in soup.find_all("p"):
            if not p.get_text(strip=True):
                p.decompose()
        
        # Remove comments
        for comment in soup.find_all(string=lambda text: isinstance(text, NavigableString) and "<!--" in str(text)):
            comment.extract()
        
        return soup


class HTMLBuilder:
    """Builder for creating HTML documents."""
    
    def __init__(self, title: str = "", lang: str = "de"):
        """
        Initialize HTML builder.
        
        Args:
            title: Document title
            lang: Document language
        """
        self.soup = BeautifulSoup("<!DOCTYPE html>", "html.parser")
        self.html = self.soup.new_tag("html", lang=lang)
        self.soup.append(self.html)
        
        # Create head
        self.head = self.soup.new_tag("head")
        self.html.append(self.head)
        
        # Add meta charset
        meta_charset = self.soup.new_tag("meta", charset="utf-8")
        self.head.append(meta_charset)
        
        # Add title
        if title:
            title_tag = self.soup.new_tag("title")
            title_tag.string = title
            self.head.append(title_tag)
        
        # Create body
        self.body = self.soup.new_tag("body")
        self.html.append(self.body)
    
    def add_meta(self, name: str, content: str) -> 'HTMLBuilder':
        """
        Add a meta tag.
        
        Args:
            name: Meta name
            content: Meta content
            
        Returns:
            Self for chaining
        """
        meta = self.soup.new_tag("meta", attrs={"name": name, "content": content})
        self.head.append(meta)
        return self
    
    def add_css(self, href: str) -> 'HTMLBuilder':
        """
        Add a CSS link.
        
        Args:
            href: CSS file URL
            
        Returns:
            Self for chaining
        """
        link = self.soup.new_tag("link", rel="stylesheet", href=href)
        self.head.append(link)
        return self
    
    def add_script(self, src: str, defer: bool = False) -> 'HTMLBuilder':
        """
        Add a JavaScript file.
        
        Args:
            src: Script URL
            defer: Whether to defer loading
            
        Returns:
            Self for chaining
        """
        script = self.soup.new_tag("script", src=src)
        if defer:
            script["defer"] = ""
        self.body.append(script)
        return self
    
    def add_element(self, element: Tag, to_body: bool = True) -> 'HTMLBuilder':
        """
        Add an element to the document.
        
        Args:
            element: Element to add
            to_body: Add to body (True) or head (False)
            
        Returns:
            Self for chaining
        """
        if to_body:
            self.body.append(element)
        else:
            self.head.append(element)
        return self
    
    def build(self) -> str:
        """
        Build the final HTML string.
        
        Returns:
            Complete HTML document
        """
        return str(self.soup.prettify())


class LinkProcessor:
    """Process and transform links in HTML."""
    
    @staticmethod
    def process_links(
        soup: BeautifulSoup,
        link_transformer: Callable[[str], str],
        selector: str = "a[href]"
    ) -> int:
        """
        Process all links matching selector.
        
        Args:
            soup: BeautifulSoup object
            link_transformer: Function to transform link URLs
            selector: CSS selector for links
            
        Returns:
            Number of links processed
        """
        count = 0
        for link in soup.select(selector):
            original_href = link.get("href", "")
            new_href = link_transformer(original_href)
            if new_href != original_href:
                link["href"] = new_href
                count += 1
        
        logger.debug(f"Processed {count} links")
        return count
    
    @staticmethod
    def make_links_absolute(soup: BeautifulSoup, base_url: str) -> int:
        """
        Convert relative links to absolute.
        
        Args:
            soup: BeautifulSoup object
            base_url: Base URL for conversion
            
        Returns:
            Number of links converted
        """
        def make_absolute(href: str) -> str:
            if href.startswith(("http://", "https://", "//", "#")):
                return href
            if href.startswith("/"):
                return base_url.rstrip("/") + href
            return base_url.rstrip("/") + "/" + href
        
        return LinkProcessor.process_links(soup, make_absolute)
    
    @staticmethod
    def add_external_link_attributes(soup: BeautifulSoup, internal_domain: str) -> int:
        """
        Add target="_blank" and rel="noopener" to external links.
        
        Args:
            soup: BeautifulSoup object
            internal_domain: Domain to consider internal
            
        Returns:
            Number of external links processed
        """
        count = 0
        for link in soup.select("a[href]"):
            href = link.get("href", "")
            if href.startswith(("http://", "https://")) and internal_domain not in href:
                link["target"] = "_blank"
                link["rel"] = "noopener noreferrer"
                count += 1
        
        return count


# Convenience functions
def parse_html(html_content: str) -> BeautifulSoup:
    """Convenience function to parse HTML."""
    return HTMLProcessor().parse_html(html_content)


def clean_html(html_content: str, remove_tags: Optional[List[str]] = None) -> str:
    """Convenience function to clean HTML."""
    processor = HTMLProcessor()
    soup = processor.parse_html(html_content)
    cleaned = processor.clean_html(soup, remove_tags)
    return str(cleaned)


def extract_text_from_html(html_content: str) -> str:
    """Convenience function to extract text from HTML."""
    processor = HTMLProcessor()
    soup = processor.parse_html(html_content)
    return processor.extract_text(soup)


def prettify_html_soup(soup: BeautifulSoup, indent: int = 4) -> str:
    """
    Convert BeautifulSoup object to pretty-printed HTML string.
    
    Args:
        soup: BeautifulSoup object to prettify
        indent: Number of spaces for indentation (Note: BeautifulSoup uses fixed indentation)
        
    Returns:
        Pretty-printed HTML string
    """
    return soup.prettify(formatter="html")


def write_pretty_html(
    soup: BeautifulSoup, 
    file_path: str, 
    encoding: str = "utf-8",
    add_doctype: bool = True,
    indent: int = 4
) -> None:
    """
    Write BeautifulSoup object to file as pretty-printed HTML.
    
    Args:
        soup: BeautifulSoup object to write
        file_path: Output file path
        encoding: File encoding
        add_doctype: Whether to add DOCTYPE if missing
        indent: Number of spaces for indentation
    """
    from bs4 import Doctype
    
    with open(file_path, "w", encoding=encoding) as f:
        # Check if DOCTYPE already exists
        has_doctype = any(isinstance(element, Doctype) for element in soup.contents)
        
        # Add DOCTYPE if requested and not present
        if add_doctype and not has_doctype:
            f.write("<!DOCTYPE html>\n")
        
        # Write pretty-printed HTML
        f.write(prettify_html_soup(soup, indent))