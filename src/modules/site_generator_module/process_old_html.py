# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

import logging
import re
import sys
from bs4 import BeautifulSoup, NavigableString, Tag
from typing import Any

# Get logger from main module
logger = logging.getLogger(__name__)


def remove_javascript(soup: BeautifulSoup) -> None:
    """Remove all <script> tags from the HTML."""
    for script in soup.find_all("script"):
        script.decompose()


def convert_font_size_5_to_h1(soup: BeautifulSoup) -> None:
    """
    Convert all <font> tags with size="5" to <h1> tags.
    (Note: Merging adjacent ones is not implemented.)
    """
    for element in soup.find_all("font", {"size": "5"}):
        new_tag: Tag = soup.new_tag("h1")
        new_tag.string = element.get_text()
        element.replace_with(new_tag)


def remove_body_attributes(soup: BeautifulSoup) -> None:
    """Remove bgcolor and text attributes from the <body> tag if they exist."""
    if soup.body.has_attr("bgcolor"):
        del soup.body["bgcolor"]
    if soup.body.has_attr("text"):
        del soup.body["text"]


def remove_doctype(soup: BeautifulSoup) -> None:
    """
    Remove DOCTYPE-related strings from the soup contents.
    This targets NavigableString items that contain "DOCTYPE".
    """
    for item in list(soup.contents):
        if isinstance(item, NavigableString) and "DOCTYPE" in item:
            item.extract()


def create_source_div(soup: BeautifulSoup) -> Tag:
    """
    Create a new div with id 'source-text' and class 'html-source' and move all
    non-empty contents from the <body> into this div.
    """
    source_div: Tag = soup.new_tag("div", id="source-text", **{"class": "html-source"})
    while soup.body.contents:
        content = soup.body.contents[0]
        if isinstance(content, NavigableString) and not content.strip():
            content.extract()  # Remove empty strings
            continue
        source_div.append(content.extract())
    soup.body.append(source_div)
    return source_div


def move_source_div_into_law_div(soup: BeautifulSoup, source_div: Tag) -> None:
    """
    Create a new div with id 'law' and move the source_div into it.
    """
    law_div: Tag = soup.new_tag("div", id="law")
    law_div.append(source_div.extract())
    soup.body.append(law_div)


def unwrap_font_tags(container: Tag) -> None:
    """
    Unwrap all <font>, <i>, and <b> tags within the given container.
    """
    for tag in list(container.find_all(["font", "i", "b"])):
        tag.unwrap()


def modify_html(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Modify the HTML soup by performing the following steps:
      1. Remove all JavaScript.
      2. Convert <font size="5"> elements to <h1> tags.
      3. Remove bgcolor and text attributes from the <body> tag.
      4. Remove DOCTYPE strings.
      5. Create a 'source-text' div and move all body contents into it.
      6. Create a 'law' div and move the source-text div into it.
      7. Unwrap font tags (and <i>, <b>) within the source-text div.
    """
    remove_javascript(soup)
    convert_font_size_5_to_h1(soup)
    remove_body_attributes(soup)
    remove_doctype(soup)
    source_div: Tag = create_source_div(soup)
    move_source_div_into_law_div(soup, source_div)
    # Unwrap font tags from the original source div
    unwrap_font_tags(source_div)
    return soup


def main(soup: BeautifulSoup) -> BeautifulSoup:
    """Process the HTML soup and return the modified soup."""
    return modify_html(soup)


if __name__ == "__main__":
    main()
