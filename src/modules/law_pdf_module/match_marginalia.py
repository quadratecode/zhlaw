"""Module for matching and positioning marginalia in legal HTML documents.

This module processes HTML documents to properly position marginalia (side notes) relative
to their associated provisions. It calculates vertical overlap between marginalia and main
text elements, adjusts positioning, and merges marginalia HTML with the main document.

Key features:
- Calculates vertical overlap between marginalia and provisions
- Adjusts marginalia positioning to align with appropriate provisions
- Sorts paragraphs by page and vertical position
- Merges separate marginalia HTML files with main document HTML
- Maintains proper document structure and flow

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

from bs4 import BeautifulSoup, NavigableString
import re

# Get logger from main module
from src.utils.logging_utils import get_module_logger
logger = get_module_logger(__name__)


def calculate_overlap(mod_pos, marg_pos):

    # Unpack positions
    mod_top, mod_bottom = mod_pos
    marg_top, marg_bottom = marg_pos

    # Calculate the maximum of the top values and the minimum of the bottom values
    top_max = max(mod_top, marg_top)
    bottom_min = min(mod_bottom, marg_bottom)

    # If the maximum top value is less than the minimum bottom value, there is overlap
    if top_max < bottom_min:
        # The overlap is the difference between the bottom_min and top_max
        return bottom_min - top_max
    else:
        # No overlap
        return 0


def is_target_paragraph(paragraph):
    # Check if the next sibling paragraph is a "provision"
    return (
        paragraph and paragraph.get("class") and "provision" in paragraph.get("class")
    )


def group_marginalia_by_proximity(marginalia_list, proximity_threshold=25.0):
    """
    Group marginalia elements that are vertically close to each other.
    
    Args:
        marginalia_list: List of marginalia elements with positioning data
        proximity_threshold: Maximum vertical distance to consider elements as grouped
    
    Returns:
        List of groups, where each group is a list of marginalia elements
    """
    if not marginalia_list:
        return []
    
    # Sort marginalia by page and vertical position
    sorted_marginalia = sorted(marginalia_list, key=lambda m: (
        m["page"], 
        m["pos"][0]  # top position
    ))
    
    groups = []
    current_group = [sorted_marginalia[0]]
    
    for i in range(1, len(sorted_marginalia)):
        current = sorted_marginalia[i]
        previous = sorted_marginalia[i-1]
        
        # Check if they're on the same page and within proximity threshold
        if (current["page"] == previous["page"] and 
            abs(current["pos"][0] - previous["pos"][1]) <= proximity_threshold):
            current_group.append(current)
        else:
            # Start a new group
            groups.append(current_group)
            current_group = [current]
    
    # Add the last group
    groups.append(current_group)
    
    return groups


def calculate_group_overlap(group, mod_pos):
    """
    Calculate the total overlap between a group of marginalia and a provision.
    
    Args:
        group: List of marginalia elements in the group
        mod_pos: Position tuple (top, bottom) of the provision
    
    Returns:
        Total overlap score for the group
    """
    total_overlap = 0
    for marginalia in group:
        overlap = calculate_overlap(mod_pos, marginalia["pos"])
        total_overlap += overlap
    
    return total_overlap


def merge_marginalia_containers(soup):
    """
    Merge multiple marginalia-containers that have the same data-related-provision.
    
    This function consolidates multiple marginalia containers assigned to the same
    provision into a single container, preserving all marginalia paragraphs and
    maintaining the positioning data from the first container.
    """
    # Group marginalia containers by their data-related-provision attribute
    provision_groups = {}
    all_containers = soup.find_all("div", class_="marginalia-container")
    
    for container in all_containers:
        related_provision = container.get("data-related-provision")
        if related_provision:
            if related_provision not in provision_groups:
                provision_groups[related_provision] = []
            provision_groups[related_provision].append(container)
    
    # Process groups with multiple containers
    for provision_id, containers in provision_groups.items():
        if len(containers) > 1:
            # Use the first container as the base
            base_container = containers[0]
            
            # Collect all marginalia paragraphs from all containers
            all_marginalia_paragraphs = []
            for container in containers:
                # Find all marginalia paragraphs in this container
                marginalia_paras = container.find_all("p", class_="marginalia")
                all_marginalia_paragraphs.extend(marginalia_paras)
            
            # Clear the base container's content
            base_container.clear()
            
            # Add all collected marginalia paragraphs to the base container
            for para in all_marginalia_paragraphs:
                # Clone the paragraph to avoid issues with moving elements
                new_para = soup.new_tag("p", attrs=para.attrs)
                new_para.string = para.get_text()
                base_container.append(new_para)
            
            # Remove the duplicate containers (all except the first)
            for container in containers[1:]:
                container.decompose()
            
            # Reposition the merged container to be directly above its related provision
            related_provision = soup.find(id=provision_id)
            if related_provision:
                # Move the merged container directly before the related provision
                related_provision.insert_before(base_container)
                logger.info(f"Merged {len(containers)} marginalia containers for provision {provision_id} and repositioned")
            else:
                logger.warning(f"Could not find provision {provision_id} to reposition merged marginalia container")
                logger.info(f"Merged {len(containers)} marginalia containers for provision {provision_id}")
    
    return soup


def adjust_marginalia_position(soup):
    """
    Adjust the position of marginalia containers in the HTML.
    This function is more conservative now since the group-based approach
    should already place marginalia in better initial positions.
    """
    marginalia_containers = soup.find_all("div", class_="marginalia-container")

    # Continue if a marginalia container is found
    if marginalia_containers:
        for container in marginalia_containers:
            next_sibling = container.find_next_sibling()
            previous_sibling = container.find_previous_sibling()
            iteration_count = 0

            # Only make minor adjustments if the marginalia is not already 
            # positioned correctly relative to a provision
            while (
                next_sibling
                and not is_target_paragraph(next_sibling)
                and iteration_count < 10  # Reduced from 50 to 10 for more conservative adjustment
            ):
                if previous_sibling:
                    previous_sibling.insert_before(container)
                next_sibling = container.find_next_sibling()
                previous_sibling = container.find_previous_sibling()
                iteration_count += 1

    return soup


def sort_paragraphs(soup):
    # Sort the paragraphs by page and vertical position
    paragraphs = soup.find_all("p", {"data-page-count": True})
    paragraphs.sort(
        key=lambda p: (
            int(p["data-page-count"]),
            float(p["data-vertical-position-top"]),
        )
    )

    # Reorder the paragraphs in the HTML
    for p in paragraphs:
        p.extract()
        soup.body.append(p)

    return soup


def merge_html(modified_path, marginalia_path):
    # Read and parse the HTML files
    with open(modified_path, "r", encoding="utf-8") as file:
        soup_modified = BeautifulSoup(file, "html.parser")
    with open(marginalia_path, "r", encoding="utf-8") as file:
        soup_marginalia = BeautifulSoup(file, "html.parser")

    # Collect all marginalia containers with their positioning data
    marginalia_containers = soup_marginalia.find_all(
        "div",
        {
            "class": "marginalia-container",
            "data-page-count": True,
            "data-vertical-position-top": True,
            "data-vertical-position-bottom": True,
        },
    )
    
    # Convert marginalia containers to structured format for matching
    marginalia_data = []
    for container in marginalia_containers:
        marginalia_data.append({
            "element": container,
            "page": container["data-page-count"],
            "pos": (
                float(container["data-vertical-position-top"]),
                float(container["data-vertical-position-bottom"]),
            ),
            "text": container.get_text(strip=True)
        })

    # Process each container
    for container_data in marginalia_data:
        container = container_data["element"]
        container_page = container_data["page"]
        
        # Find the best matching provision for this container
        best_overlap = 0
        best_mod_p = None
        best_provision_id = None
        
        # Only search for provisions (elements with class="provision")
        for mod_p in soup_modified.find_all("p", {"class": "provision", "data-page-count": container_page}):
            # Skip provisions without IDs
            if not mod_p.get("id"):
                continue
                
            mod_pos = (
                float(mod_p["data-vertical-position-top"]),
                float(mod_p["data-vertical-position-bottom"]),
            )
            overlap = calculate_overlap(mod_pos, container_data["pos"])
            if overlap > best_overlap:
                best_overlap = overlap
                best_mod_p = mod_p
                # Use existing provision ID
                best_provision_id = mod_p.get("id")
        
        # If no overlapping provision found, find the next provision (top-down)
        if not best_mod_p:
            # Get all provisions with IDs sorted by page and vertical position
            all_provisions = []
            for p in soup_modified.find_all("p", {"class": "provision"}):
                # Only include provisions that have IDs and positional data
                if (p.get("id") and p.get("data-page-count") and p.get("data-vertical-position-top")):
                    all_provisions.append({
                        "element": p,
                        "page": int(p["data-page-count"]),
                        "top": float(p["data-vertical-position-top"]),
                        "id": p.get("id")
                    })
            
            # Sort by page, then by vertical position
            all_provisions.sort(key=lambda x: (x["page"], x["top"]))
            
            # Find the first provision that comes after the marginalia
            container_page_int = int(container_page)
            container_top = container_data["pos"][0]
            
            for prov in all_provisions:
                # Find the first provision that's either on a later page
                # or on the same page but below the marginalia
                if (prov["page"] > container_page_int or 
                    (prov["page"] == container_page_int and prov["top"] > container_top)):
                    best_mod_p = prov["element"]
                    best_provision_id = prov["id"]  # Use the pre-validated ID
                    break
        
        # Add data-related-provision attribute to the container
        if best_mod_p and best_provision_id:
            container["data-related-provision"] = best_provision_id
        else:
            # Log warning if no valid provision found
            logger.warning(f"No valid provision found for marginalia: {container_data['text'][:50]}...")
            # Skip this marginalia container
            continue
        
        # Insert the container before the best matching provision
        if best_mod_p:
            # Clone the container and insert it into the modified document
            new_container = soup_modified.new_tag("div", attrs=container.attrs)
            new_container.string = ""  # Clear any existing content
            
            # Copy all child elements from the original container
            for child in container.children:
                if hasattr(child, 'name'):  # It's a tag
                    new_child = soup_modified.new_tag(child.name, attrs=child.attrs)
                    new_child.string = child.get_text()
                    new_container.append(new_child)
                else:  # It's text
                    new_container.append(str(child))
            
            best_mod_p.insert_before(new_container)

    # Merge multiple marginalia containers with the same provision
    soup_modified = merge_marginalia_containers(soup_modified)
    
    # Adjust the positions of the marginalia elements
    adjust_marginalia_position(soup_modified)

    return soup_modified


def clean_html(soup: BeautifulSoup) -> None:
    """
    Not sure about the original motivation behind this function -> Check for removal
    Currently requires a lot of exclusions and fine tuning just to wrap numbers in <sup> tags (reason unknown)
    """
    for element in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6"]):
        # Process text nodes individually rather than using element.string
        for content in list(element.contents):
            if isinstance(content, NavigableString):
                # Strip whitespace from direct text nodes only
                content.replace_with(content.strip())

        # Check if the element contains only a single number and doesn't have sup or sub tags
        if (
            element.get_text(strip=True).isdigit()
            and not element.find("sup")
            and not element.find("sub")
            # and does not have <numerator> or <denominator> tags
            and not element.find("numerator")
            and not element.find("denominator")
        ):
            # Save the text of the element
            element_text = element.get_text(strip=True)
            # Clear element without losing structure
            element.clear()
            # Create and append new sup tag
            sup_tag = soup.new_tag("sup")
            sup_tag.string = element_text
            element.append(sup_tag)
        else:
            # Process each text node within element
            for content in element.contents:
                if isinstance(content, NavigableString):
                    # Remove dashes between lowercase letters
                    cleaned_text = re.sub(r"(?<=[a-z])-(?=[a-z])", "", content)
                    content.replace_with(cleaned_text)

    return soup


def main(html_file_law, html_file_marginalia, merged_html_law):

    soup = merge_html(html_file_law, html_file_marginalia)
    soup = clean_html(soup)

    from src.utils.html_utils import write_html
    write_html(soup, merged_html_law, encoding="utf-8", add_doctype=False, minify=True)
    logger.info(f"Saved merged HTML to {merged_html_law}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 4:
        main(sys.argv[1], sys.argv[2], sys.argv[3])
    else:
        print("Usage: python -m match_marginalia <html_file_law> <html_file_marginalia> <merged_html_law>")
        sys.exit(1)
