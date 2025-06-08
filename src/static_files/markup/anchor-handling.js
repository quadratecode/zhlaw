// In src/static_files/markup/anchor-handling.js

document.addEventListener('DOMContentLoaded', () => {
    // --- Configuration ---
    const SCROLL_OFFSET = 100;
    const HIGHLIGHT_CLASS = 'highlight';

    // --- State Variable ---
    let currentHighlightedContainer = null;

    // --- Reusable Logic Functions ---

    /**
     * This function handles applying or removing the visual highlight based on the URL hash.
     * It now also handles highlighting footnote paragraphs.
     */
    function applyHighlight() {
        // Always clear the previous highlight.
        if (currentHighlightedContainer) {
            currentHighlightedContainer.classList.remove(HIGHLIGHT_CLASS);
            currentHighlightedContainer = null;
        }

        const hash = window.location.hash;
        if (hash) {
            try {
                const targetElement = document.querySelector(hash);
                if (targetElement) {
                    // Find the container to highlight
                    let container = targetElement.closest('.provision-container, .subprovision-container');

                    // If no container is found, check if the target itself is a footnote paragraph
                    if (!container && targetElement.matches('p.footnote')) {
                        container = targetElement;
                    }

                    if (container) {
                        container.classList.add(HIGHLIGHT_CLASS);
                        currentHighlightedContainer = container;
                    }
                }
            } catch (e) {
                console.error("Error applying highlight:", e);
            }
        }
    }

    /**
     * This function handles the custom scrolling to an anchor with an offset.
     */
    function scrollToAnchorWithOffset(hash) {
        if (hash) {
            try {
                const targetElement = document.querySelector(hash);
                if (targetElement) {
                    const elementRect = targetElement.getBoundingClientRect();
                    const offsetPosition = elementRect.top + window.pageYOffset - SCROLL_OFFSET;
                    window.scrollTo({
                        top: offsetPosition,
                        behavior: 'smooth'
                    });
                }
            } catch (e) {
                console.error("Error scrolling to anchor:", e);
            }
        }
    }

    // --- Primary Click Listener to Control ALL In-Page Navigation ---
    document.addEventListener('click', (event) => {
        const anchor = event.target.closest('a[href^="#"]');
        if (!anchor) {
            return;
        }
        event.preventDefault();

        const clickedHash = anchor.hash;
        const currentHash = window.location.hash;
        const isFootnoteRefClick = !!anchor.closest('sup.footnote-ref');

        if (isFootnoteRefClick) {
            // A footnote reference in the main text was clicked.
            // Always refresh the selection and scroll, even if it's the same footnote.
            history.pushState(null, '', clickedHash);
            applyHighlight();
            scrollToAnchorWithOffset(clickedHash);
        } else {
            // This is not a footnote reference (e.g., a provision or a footnote number at the bottom).
            if (clickedHash && clickedHash === currentHash) {
                // This handles deselecting by clicking the same link again (like the footnote number at the bottom).
                history.pushState("", document.title, window.location.pathname + window.location.search);
                applyHighlight();
                // No scroll on deselect.
            } else {
                // This handles selecting a new, non-footnote-ref link (e.g., a provision).
                history.pushState(null, '', clickedHash);
                applyHighlight();
                // No scroll, as per the previous request.
            }
        }
    });

    // --- Event Listener for Browser History (Back/Forward buttons) ---
    // The hashchange event should also trigger a scroll.
    window.addEventListener('hashchange', () => {
        applyHighlight();
        scrollToAnchorWithOffset(window.location.hash);
    });


    // --- Initial Page Load Actions ---
    applyHighlight();
    // Use a timeout to ensure the browser has rendered the page before scrolling
    setTimeout(() => {
        scrollToAnchorWithOffset(window.location.hash);
    }, 50);
});
