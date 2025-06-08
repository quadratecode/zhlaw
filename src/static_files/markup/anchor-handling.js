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
     * It is now also called from the click handler for dynamic scrolling.
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

        if (clickedHash && clickedHash === currentHash) {
            history.pushState("", document.title, window.location.pathname + window.location.search);
            applyHighlight();
        } else {
            history.pushState(null, '', clickedHash);
            applyHighlight();
            // MODIFICATION: Add manual scroll on click
            scrollToAnchorWithOffset(clickedHash);
        }
    });

    // --- Event Listener for Browser History (Back/Forward buttons) ---
    window.addEventListener('hashchange', applyHighlight);


    // --- Initial Page Load Actions ---
    applyHighlight();
    // Use a timeout to ensure the browser has rendered the page before scrolling
    setTimeout(() => {
        scrollToAnchorWithOffset(window.location.hash);
    }, 50);
});
