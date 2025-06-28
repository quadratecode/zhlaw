"""
Module for cropping PDF margins to separate main content from marginalia.

This module provides functionality to:
- Crop PDF pages to isolate main content and marginalia
- Handle different margin widths for odd and even pages
- Create separate PDF files for main content and marginalia
- Support the marginalia extraction and matching pipeline

License:
    https://github.com/quadratecode/zhlaw/blob/main/LICENSE.md
"""

import fitz

# Get logger from main module
from src.utils.logging_utils import get_module_logger
logger = get_module_logger(__name__)


def main(original_pdf_path, modified_pdf_path, marginalia_pdf_path):
    """
    Crop the margins of a PDF document and save the modified document and marginalia separately.

    Args:
        original_pdf_path (str): The file path of the original PDF document.
        modified_pdf_path (str): The file path to save the modified PDF document with margins cropped.
        marginalia_pdf_path (str): The file path to save the marginalia PDF document.

    Returns:
        None
    """
    doc = fitz.open(original_pdf_path)
    modified_doc = fitz.open()  # Document for the content with strips removed
    marginalia_doc = fitz.open()  # Document for the marginalia

    crop_width_odd = 83.9  # 29.6mm in points for odd pages
    crop_width_even = 82.8  # 29.2mm in points for even pages

    for page_number in range(len(doc)):
        page = doc.load_page(page_number)

        # Adjusting for the difference in page numbering between documents and programming
        is_odd_page = page_number % 2 == 0  # True for odd pages, False for even pages

        if is_odd_page:
            # Odd pages (in document terms) - crop right margin
            crop_rect_main = fitz.Rect(
                0, 0, page.rect.width - crop_width_odd, page.rect.height
            )
            crop_rect_marginalia = fitz.Rect(
                page.rect.width - crop_width_odd, 0, page.rect.width, page.rect.height
            )
        else:
            # Even pages (in document terms) - crop left margin
            crop_rect_main = fitz.Rect(
                crop_width_even, 0, page.rect.width, page.rect.height
            )
            crop_rect_marginalia = fitz.Rect(0, 0, crop_width_even, page.rect.height)

        # Add main content (middle part) to the modified document
        new_page = modified_doc.new_page(
            width=crop_rect_main.width, height=crop_rect_main.height
        )
        new_page.show_pdf_page(new_page.rect, doc, page_number, clip=crop_rect_main)

        # Add marginalia (appropriate side depending on odd/even page) to the marginalia document
        marginalia_page = marginalia_doc.new_page(
            width=crop_rect_marginalia.width, height=crop_rect_marginalia.height
        )
        marginalia_page.show_pdf_page(
            marginalia_page.rect, doc, page_number, clip=crop_rect_marginalia
        )

    modified_doc.save(modified_pdf_path)
    marginalia_doc.save(marginalia_pdf_path)

    modified_doc.close()
    marginalia_doc.close()
    doc.close()


if __name__ == "__main__":
    main()
