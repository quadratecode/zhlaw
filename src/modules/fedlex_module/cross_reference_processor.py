#!/usr/bin/env python3
"""
Script: cross_reference_processor.py

Detects and processes internal cross-references in fedlex HTML documents.
Focuses on patterns like "Art. 5", "Abs. 2", "lit. a" and creates internal links.
Primarily processes within footnote content to avoid over-linking.

This module is part of Phase 3.2 of the Fedlex improvement plan to align
fedlex output with zhlex gold standard structure.

Usage:
    from src.modules.fedlex_module.cross_reference_processor import detect_and_link_cross_references
    
License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import re
from bs4 import BeautifulSoup, NavigableString, Tag


# Cross-reference patterns
PATTERNS = {
    'article': {
        'pattern': r'\b(?:Art\.|Artikel)\s*(\d+(?:[a-zA-Z]+)?)\b',
        'id_prefix': 'prov',
        'description': 'Article references (e.g., Art. 5, Art. 1bis)'
    },
    'paragraph': {
        'pattern': r'\b(?:Abs\.|Absatz)\s*(\d+)\b',
        'id_prefix': 'sub',
        'description': 'Paragraph/Absatz references (e.g., Abs. 2)'
    },
    'letter': {
        'pattern': r'\b(?:lit\.|Buchst\.|Bst\.)\s*([a-zA-Z])\b',
        'id_prefix': 'sub',
        'description': 'Letter references (e.g., lit. a, Bst. c)'
    },
    'number': {
        'pattern': r'\b(?:Ziff\.|Ziffer)\s*(\d+)\b',
        'id_prefix': 'sub',
        'description': 'Number references (e.g., Ziff. 3)'
    }
}


def find_target_element(soup, ref_type, ref_value, context_provision=None):
    """
    Find the target element for a cross-reference.
    
    Args:
        soup: BeautifulSoup object
        ref_type: Type of reference ('article', 'paragraph', 'letter', 'number')
        ref_value: Value of the reference (e.g., '5', '2', 'a')
        context_provision: Current provision ID for context-aware searching
    
    Returns:
        Target element ID if found, None otherwise
    """
    if ref_type == 'article':
        # Look for provision with matching article number
        # Pattern: seq-X-prov-Y where Y matches ref_value
        pattern = re.compile(f"seq-\\d+-prov-{re.escape(ref_value)}$")
        target = soup.find("p", class_="provision", id=pattern)
        if target:
            return target.get("id")
    
    elif ref_type in ['paragraph', 'letter', 'number']:
        # For sub-references, look within context if available
        if context_provision:
            # Extract provision number from context
            match = re.search(r"prov-(\d+\w*)", context_provision)
            if match:
                prov_num = match.group(1)
                
                # Build pattern based on reference type
                if ref_type == 'paragraph':
                    # Pattern: seq-X-prov-Y-sub-Z where Z is the paragraph number
                    pattern = re.compile(f"seq-\\d+-prov-{re.escape(prov_num)}-sub-{re.escape(ref_value)}")
                elif ref_type == 'letter':
                    # Pattern: seq-X-prov-Y-sub-Za where a is the letter
                    pattern = re.compile(f"seq-\\d+-prov-{re.escape(prov_num)}-sub-\\d*{re.escape(ref_value.lower())}")
                else:  # number
                    pattern = re.compile(f"seq-\\d+-prov-{re.escape(prov_num)}-sub-{re.escape(ref_value)}")
                
                target = soup.find("p", class_="subprovision", id=pattern)
                if target:
                    return target.get("id")
        
        # Fallback: search without context
        if ref_type == 'letter':
            # Look for any subprovision ending with the letter
            pattern = re.compile(f"sub-\\d*{re.escape(ref_value.lower())}$")
        else:
            pattern = re.compile(f"sub-{re.escape(ref_value)}\\w*$")
        
        target = soup.find("p", class_="subprovision", id=pattern)
        if target:
            return target.get("id")
    
    return None


def create_cross_reference_link(soup, text, target_id):
    """
    Create an anchor tag for a cross-reference.
    
    Args:
        soup: BeautifulSoup object
        text: Text content for the link
        target_id: ID of the target element
    
    Returns:
        Anchor tag element
    """
    a_tag = soup.new_tag("a", href=f"#{target_id}")
    a_tag["class"] = ["cross-reference"]
    a_tag.string = text
    return a_tag


def process_text_node(soup, text_node, context_provision=None):
    """
    Process a text node to detect and link cross-references.
    
    Args:
        soup: BeautifulSoup object
        text_node: NavigableString to process
        context_provision: Current provision ID for context
    
    Returns:
        List of nodes to replace the text node with
    """
    if not isinstance(text_node, NavigableString):
        return [text_node]
    
    text = str(text_node)
    new_nodes = []
    last_end = 0
    
    # Process each pattern type
    for ref_type, config in PATTERNS.items():
        pattern = config['pattern']
        
        for match in re.finditer(pattern, text):
            # Add text before the match
            if match.start() > last_end:
                new_nodes.append(NavigableString(text[last_end:match.start()]))
            
            # Extract reference value
            ref_value = match.group(1)
            
            # Find target element
            target_id = find_target_element(soup, ref_type, ref_value, context_provision)
            
            if target_id:
                # Create link
                link = create_cross_reference_link(soup, match.group(), target_id)
                new_nodes.append(link)
            else:
                # Keep original text if no target found
                new_nodes.append(NavigableString(match.group()))
            
            last_end = match.end()
    
    # Add remaining text
    if last_end < len(text):
        new_nodes.append(NavigableString(text[last_end:]))
    
    return new_nodes if new_nodes else [text_node]


def detect_and_link_cross_references(soup, scope="footnotes"):
    """
    Detect patterns like "Art. 5", "Abs. 2", "lit. a" and create internal links.
    
    Args:
        soup: BeautifulSoup object
        scope: Where to process references ("footnotes", "all", or CSS selector)
    
    Returns:
        Modified BeautifulSoup object with cross-references linked
    """
    print("  -> Detecting and linking cross-references...")
    
    links_created = 0
    
    # Determine which elements to process based on scope
    if scope == "footnotes":
        # Process only within footnote content
        elements_to_process = soup.find_all("span", class_="footnote-content")
        elements_to_process.extend(soup.find_all("p", class_="footnote"))
    elif scope == "all":
        # Process all text content (use with caution to avoid over-linking)
        elements_to_process = soup.find_all(["p", "span", "div"])
    else:
        # Use scope as CSS selector
        elements_to_process = soup.select(scope)
    
    for element in elements_to_process:
        # Get context provision if available
        context_provision = None
        parent_provision = element.find_parent("p", class_="provision")
        if parent_provision:
            context_provision = parent_provision.get("id")
        
        # Process all text nodes in the element
        for text_node in list(element.strings):
            parent = text_node.parent
            if parent and parent.name != "a":  # Don't process text already in links
                new_nodes = process_text_node(soup, text_node, context_provision)
                
                if len(new_nodes) > 1 or (len(new_nodes) == 1 and isinstance(new_nodes[0], Tag)):
                    # Replace the text node with new nodes
                    for i, new_node in enumerate(new_nodes):
                        if i == 0:
                            text_node.replace_with(new_node)
                        else:
                            parent.insert(parent.contents.index(new_nodes[i-1]) + 1, new_node)
                        
                        if isinstance(new_node, Tag) and new_node.name == "a":
                            links_created += 1
    
    print(f"  -> Created {links_created} cross-reference links")
    return soup


def enhance_cross_references(soup):
    """
    Enhanced cross-reference detection with multiple passes and strategies.
    This is a more comprehensive approach that can be used for complex documents.
    """
    print("  -> Running enhanced cross-reference detection...")
    
    # Pass 1: Process footnotes (most common location for references)
    soup = detect_and_link_cross_references(soup, scope="footnotes")
    
    # Pass 2: Process marginalia (often contain references to other provisions)
    soup = detect_and_link_cross_references(soup, scope="p.marginalia")
    
    # Pass 3: Process specific annotation classes if they exist
    annotation_classes = ["annotation", "comment", "note", "reference"]
    for cls in annotation_classes:
        if soup.find(class_=cls):
            soup = detect_and_link_cross_references(soup, scope=f".{cls}")
    
    return soup


# Module exports
__all__ = [
    'detect_and_link_cross_references',
    'enhance_cross_references',
    'PATTERNS'
]