# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

import re
from bs4 import BeautifulSoup
import logging

# Get logger from main module
logger = logging.getLogger(__name__)


def custom_sort_key(item):
    # Regular expression to separate the number and letter parts
    match = re.match(r"(\d+)\s*([a-z]*)", item)
    number_part = int(match.group(1)) if match else 0
    letter_part = match.group(2) if match and match.group(2) else ""
    return (number_part, letter_part)


def sort_dict_lists(input_dict):
    sorted_dict = {}
    for key, values in input_dict.items():
        # Sort using the custom key
        sorted_values = sorted(values, key=custom_sort_key)
        sorted_dict[key] = sorted_values
    return sorted_dict


def extract_Law_changes(relevant_paragraphs):
    changes = {}
    current_key = None
    norms_pattern = r"^§.*?(?<!lit|abs)\."
    replacement_pattern = r"Ersatz von Bezeichnungen"

    for paragraph in relevant_paragraphs:
        # Check for a match of the word "gesetz"
        gesetz_match = re.search(
            r"(\b\w*gesetz\w*\b.*?\bvom\b.*?(?:\b\d{4}\b).*?)(?=:(?=wird wie folgt geändert:|$))",
            paragraph,
            re.IGNORECASE,
        )
        if gesetz_match:
            # Extract and clean the key
            current_key = re.sub(r"wird wie folgt geändert", "", gesetz_match.group())
            current_key = current_key.strip()
            changes[current_key] = []

        # If a key is set, search for paragraph norms or replacement pattern
        if current_key:
            # Search for a match of the norms pattern
            norms_match = re.search(norms_pattern, paragraph)
            if norms_match:
                # Add the match to the current key
                changes[current_key].append(norms_match.group())
            # Search for a match of the replacement pattern
            replacement_match = re.search(replacement_pattern, paragraph, re.IGNORECASE)
            if replacement_match:
                # Add the match to the current key
                changes[current_key].append(replacement_match.group())

    # Remove keys containing "gesetzesänderung"
    changes = {
        key: val
        for key, val in changes.items()
        if "gesetzesänderung" not in key.lower()
    }

    return changes


def main(html_file, metadata):

    # Read the html file into a soup object
    with open(html_file, "r", encoding="utf-8") as file:
        soup = BeautifulSoup(file, "html.parser")

    relevant_paragraphs = []

    for element in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6"]):
        text = element.get_text()

        # Strip whitespace from the left and right of each paragraph
        # Remove double whitespace
        text = text.strip()
        text = re.sub(r"\s+", " ", text)

        # Check for 'Bericht' (ignore case) and stop if found
        if text.lower() == "bericht":
            break
        relevant_paragraphs.append(text)

    law_changes = extract_Law_changes(relevant_paragraphs)

    # Strip whitespace from the left and right of each norm, Add them back to the list
    for law_name, norms_list in law_changes.items():
        # Remove double whitespace
        norms_list = [re.sub(r"\s+", " ", norm) for norm in norms_list]
        norms_list = [norm.strip() for norm in norms_list]
        law_changes[law_name] = norms_list

    # Remove dupliactes from affected norms
    for law_name, norms_list in law_changes.items():
        norms_list = list(dict.fromkeys(norms_list))
        law_changes[law_name] = norms_list

    # Sort affected norms by calling sort_dict_lists function
    law_changes = sort_dict_lists(law_changes)

    # Check if 'changes' key exists within 'doc_info', if not, create it
    if "regex_changes" not in metadata["doc_info"]:
        metadata["doc_info"]["regex_changes"] = {}

    # If dictionaries contain values (not only keys), add them to metadata
    if law_changes:
        metadata["doc_info"]["regex_changes"] = law_changes

    return metadata


if __name__ == "__main__":
    main()
