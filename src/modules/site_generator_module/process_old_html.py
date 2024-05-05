# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

import logging
from bs4 import NavigableString, Tag

# Get logger from main module
logger = logging.getLogger(__name__)


def modify_html(soup):

    # Remove all JavaScript
    for script in soup.find_all("script"):
        script.decompose()

    # Convert font size 5 elements to <h1> and merge adjacent ones
    h1_added = False
    previous_h1 = None
    for element in soup.find_all("font", {"size": "5"}):
        new_tag = soup.new_tag("h1")
        new_tag.string = element.get_text()
        element.replace_with(new_tag)

    # Remove bgcolor and text attributes from the body tag
    if soup.body.has_attr("bgcolor"):
        del soup.body["bgcolor"]
    if soup.body.has_attr("text"):
        del soup.body["text"]

    # Remove <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"> tag
    for doctype in soup.contents:
        if isinstance(doctype, NavigableString):
            doctype.extract()

    # Create the source-text div and move contents into it
    source_div = soup.new_tag("div", id="source-text", class_="html-source")
    while soup.body.contents:
        content = soup.body.contents[0]
        if isinstance(content, NavigableString) and not content.strip():
            content.extract()  # Remove empty strings
            continue
        source_div.append(content.extract())
    soup.body.append(source_div)

    # Move source div into law div
    law_div = soup.new_tag("div", id="law")
    law_div.append(source_div.extract())
    soup.body.append(law_div)

    # Process font tags with color
    for font_tag in list(
        source_div.find_all(["font", "i", "b"])
    ):  # Use list to avoid modifying the iterable
        # Unwrap font tags
        font_tag.unwrap()

    return soup


def main(soup):

    soup = modify_html(soup)

    return soup


if __name__ == "__main__":
    main()
