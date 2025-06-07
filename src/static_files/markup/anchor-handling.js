// In src/static_files/markup/anchor-handling.js

document.addEventListener('DOMContentLoaded', () => {
    // --- Configuration ---
    const SCROLL_OFFSET = 100;
    const HIGHLIGHT_CLASS = 'highlight';

    // --- State Variable ---
    let currentHighlightedContainer = null;

    // --- Reusable Logic Functions ---

    /**
     * This function ONLY handles applying or removing the visual highlight based on the URL hash.
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
                    const container = targetElement.closest('.provision-container, .subprovision-container');
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
     * This function ONLY handles the custom scrolling. 
     * It is designed to be called just once on initial page load.
     */
    function initialScrollToAnchorWithOffset() {
        const hash = window.location.hash;
        if (hash) {
            try {
                const targetElement = document.querySelector(hash);
                if (targetElement) {
                    // Use a timeout to ensure the browser has rendered the page layout.
                    setTimeout(() => {
                        const elementRect = targetElement.getBoundingClientRect();
                        const offsetPosition = elementRect.top + window.pageYOffset - SCROLL_OFFSET;
                        window.scrollTo({
                            top: offsetPosition,
                            behavior: 'smooth'
                        });
                    }, 50);
                }
            } catch (e) {
                console.error("Error scrolling to anchor:", e);
            }
        }
    }

    // --- Primary Click Listener to Control ALL In-Page Navigation ---
    document.addEventListener('click', (event) => {
        // Find the anchor tag that was clicked, if any.
        const anchor = event.target.closest('a[href^="#"]');
        if (!anchor) {
            return; // Exit if the click was not on a relevant anchor link.
        }

        // ALWAYS prevent the browser's default jump for any managed anchor click.
        event.preventDefault();

        const clickedHash = anchor.hash;
        const currentHash = window.location.hash;

        // Case 1: Toggle OFF if clicking the currently active anchor.
        if (clickedHash && clickedHash === currentHash) {
            // Remove the hash from the URL.
            history.pushState("", document.title, window.location.pathname + window.location.search);
            // Update the highlight (which will remove it).
            applyHighlight();
        }
        // Case 2: Toggle ON for a new or different anchor.
        else {
            // Set the new hash in the URL.
            history.pushState(null, '', clickedHash);
            // Apply the highlight for the new hash.
            applyHighlight();
        }
    });

    // --- Fallback Event Listener for Browser History (Back/Forward buttons) ---
    // This ensures highlighting updates correctly without causing a custom scroll.
    window.addEventListener('hashchange', applyHighlight);


    // --- Initial Page Load Actions ---
    // On page load, we apply the highlight AND perform the special scroll.
    applyHighlight();
    initialScrollToAnchorWithOffset();
});
