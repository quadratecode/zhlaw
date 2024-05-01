# §§
# LICENSE: https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
# §§

from bs4 import BeautifulSoup, NavigableString


def merge_paragraphs(soup, vertical_threshold=2):
    """
    Merge paragraphs in a BeautifulSoup object that are on the same page and whose vertical distance
    is less than the specified threshold. Adds an additional space between merged paragraphs. Updates their positional attributes and returns the modified soup.

    :param soup: BeautifulSoup object containing the paragraphs
    :param vertical_threshold: The vertical distance threshold for merging paragraphs
    :return: Modified BeautifulSoup object with merged paragraphs
    """
    paragraphs = soup.find_all("p")
    current_paragraph = None

    for p in paragraphs:
        # Extracting positional attributes
        data = {
            "element": p,
            "page": int(p["data-page-count"]),
            "bottom": float(p["data-vertical-position-bottom"]),
            "top": float(p["data-vertical-position-top"]),
            "left": float(p["data-vertical-position-left"]),
            "right": float(p["data-vertical-position-right"]),
        }

        # If there's no current paragraph, set it to the first one
        if not current_paragraph:
            current_paragraph = data
            continue

        # Check if the current paragraph and the next one are on the same page and close enough vertically
        if (
            data["page"] == current_paragraph["page"]
            and abs(data["top"] - current_paragraph["bottom"]) < vertical_threshold
        ):
            # Append the text from the next paragraph, separated by a space, to the current paragraph
            current_paragraph["element"].append(
                " "
            )  # Add a space before appending text
            current_paragraph["element"].append(
                NavigableString(data["element"].get_text())
            )
            current_paragraph["element"].append(
                BeautifulSoup("<br/>", "html.parser")
            )  # Optionally add a line break
            current_paragraph["bottom"] = data["bottom"]
            data["element"].decompose()  # Remove the merged paragraph from the soup
        else:
            # If paragraphs are not close enough, move to the new paragraph
            current_paragraph = data

    return soup


def main(html_file_marginalia):

    # Read and parse the HTML file
    with open(html_file_marginalia, "r", encoding="utf-8") as file:
        soup = BeautifulSoup(file, "html.parser")

    # Merge paragraphs
    merged_paragraphs = merge_paragraphs(soup)

    # Save to file
    with open(html_file_marginalia, "w", encoding="utf-8") as file:
        file.write(str(merged_paragraphs))


if __name__ == "__main__":
    main()
