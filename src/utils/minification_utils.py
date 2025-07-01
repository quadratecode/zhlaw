"""
Minification utilities for HTML, CSS, and JavaScript using minify-html.
Provides centralized minification functions with error handling and fallbacks.
"""

import logging
from typing import Optional

try:
    import minify_html
    MINIFY_HTML_AVAILABLE = True
except ImportError:
    MINIFY_HTML_AVAILABLE = False

from src.utils.logging_utils import get_module_logger
logger = get_module_logger(__name__)


def minify_html_content(
    html_content: str, 
    minify_css: bool = True, 
    minify_js: bool = True,
    fallback_on_error: bool = True
) -> str:
    """
    Minify HTML content with optional CSS and JS minification.
    
    Args:
        html_content: The HTML content to minify
        minify_css: Whether to minify inline CSS
        minify_js: Whether to minify inline JavaScript
        fallback_on_error: If True, return original content on error
        
    Returns:
        Minified HTML content, or original content if minification fails and fallback is enabled
    """
    if not MINIFY_HTML_AVAILABLE:
        if fallback_on_error:
            logger.warning("minify-html not available, returning original content")
            return html_content
        else:
            raise ImportError("minify-html library is not installed")
    
    try:
        minified = minify_html.minify(
            html_content,
            minify_css=minify_css,
            minify_js=False,  # Disable JS minification to prevent multiprocessing issues
            remove_bangs=False,  # Keep IE conditional comments
            minify_doctype=False,  # Preserve DOCTYPE
            keep_closing_tags=True,  # Keep all closing tags for safety
            keep_html_and_head_opening_tags=True,  # Keep structural tags
            allow_removing_spaces_between_attributes=False,  # Keep spaces to ensure valid HTML
            keep_comments=False,  # Remove HTML comments
            remove_processing_instructions=False  # Keep <?xml...?> if present
        )
        logger.debug(f"HTML minified: {len(html_content)} -> {len(minified)} bytes")
        return minified
        
    except Exception as e:
        if fallback_on_error:
            logger.warning(f"HTML minification failed: {e}, returning original content")
            return html_content
        else:
            raise


def minify_css_content(css_content: str, fallback_on_error: bool = True) -> str:
    """
    Minify CSS content.
    
    Args:
        css_content: The CSS content to minify
        fallback_on_error: If True, return original content on error
        
    Returns:
        Minified CSS content, or original content if minification fails and fallback is enabled
    """
    if not MINIFY_HTML_AVAILABLE:
        if fallback_on_error:
            logger.warning("minify-html not available, returning original CSS content")
            return css_content
        else:
            raise ImportError("minify-html library is not installed")
    
    try:
        # Wrap CSS in a style tag for minify-html to process
        wrapped_html = f"<style>{css_content}</style>"
        minified_html = minify_html.minify(
            wrapped_html,
            minify_css=True,
            minify_js=False,
            keep_comments=False
        )
        
        # Extract the minified CSS from the style tag
        start_tag = "<style>"
        end_tag = "</style>"
        start_idx = minified_html.find(start_tag) + len(start_tag)
        end_idx = minified_html.find(end_tag)
        
        if start_idx > len(start_tag) - 1 and end_idx > start_idx:
            minified_css = minified_html[start_idx:end_idx]
            logger.debug(f"CSS minified: {len(css_content)} -> {len(minified_css)} bytes")
            return minified_css
        else:
            raise ValueError("Failed to extract minified CSS from processed HTML")
            
    except Exception as e:
        if fallback_on_error:
            logger.warning(f"CSS minification failed: {e}, returning original content")
            return css_content
        else:
            raise


def minify_js_content(js_content: str, fallback_on_error: bool = True) -> str:
    """
    Minify JavaScript content.
    
    NOTE: JavaScript minification is currently disabled due to compatibility issues
    with the Rust-based minifier in multiprocessing environments. The PanicException
    from the Rust library cannot be pickled for inter-process communication.
    
    Args:
        js_content: The JavaScript content to minify
        fallback_on_error: If True, return original content on error
        
    Returns:
        Original JavaScript content (minification disabled for stability)
    """
    # Temporarily disable JS minification due to multiprocessing compatibility issues
    logger.debug("JavaScript minification disabled due to multiprocessing compatibility issues")
    return js_content
    
    # Original implementation commented out - kept for future use when issue is resolved
    # if not MINIFY_HTML_AVAILABLE:
    #     if fallback_on_error:
    #         logger.warning("minify-html not available, returning original JS content")
    #         return js_content
    #     else:
    #         raise ImportError("minify-html library is not installed")
    # 
    # try:
    #     # Check if the JS content is empty or whitespace only
    #     if not js_content.strip():
    #         return js_content
    #     
    #     # Wrap JS in a script tag for minify-html to process
    #     wrapped_html = f"<script>{js_content}</script>"
    #     minified_html = minify_html.minify(
    #         wrapped_html,
    #         minify_css=False,
    #         minify_js=True,
    #         keep_comments=False
    #     )
    #     
    #     # Extract the minified JS from the script tag
    #     start_tag = "<script>"
    #     end_tag = "</script>"
    #     start_idx = minified_html.find(start_tag) + len(start_tag)
    #     end_idx = minified_html.find(end_tag)
    #     
    #     if start_idx > len(start_tag) - 1 and end_idx > start_idx:
    #         minified_js = minified_html[start_idx:end_idx]
    #         logger.debug(f"JavaScript minified: {len(js_content)} -> {len(minified_js)} bytes")
    #         return minified_js
    #     else:
    #         raise ValueError("Failed to extract minified JavaScript from processed HTML")
    #         
    # except Exception as e:
    #     if fallback_on_error:
    #         # Log the specific file or context if possible
    #         logger.warning(f"JavaScript minification failed: {type(e).__name__}: {e}, returning original content")
    #         return js_content
    #     else:
    #         raise
    # except BaseException as e:
    #     if fallback_on_error:
    #         # Catch system-level exceptions like PanicException
    #         logger.warning(f"JavaScript minification failed with system error: {type(e).__name__}: {e}, returning original content")
    #         return js_content
    #     else:
    #         raise


def get_minification_stats(original_size: int, minified_size: int) -> dict:
    """
    Calculate minification statistics.
    
    Args:
        original_size: Size of original content in bytes
        minified_size: Size of minified content in bytes
        
    Returns:
        Dictionary with size reduction statistics
    """
    reduction = original_size - minified_size
    percentage = (reduction / original_size * 100) if original_size > 0 else 0
    
    return {
        'original_size': original_size,
        'minified_size': minified_size,
        'bytes_saved': reduction,
        'percentage_reduction': round(percentage, 2)
    }