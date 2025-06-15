// In src/static_files/markup/anchor-highlight.js

document.addEventListener('DOMContentLoaded', () => {
    // --- Configuration ---
    const SCROLL_OFFSET = 100;
    const HIGHLIGHT_CLASS = 'highlight';

    // --- State Variables ---
    let currentHighlightedContainer = null;
    // Make isInternalNavigation accessible globally so anchor-tooltip.js can set it
    window.isInternalNavigation = false;

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

    // --- State for deselection tooltip ---
    let deselectionTooltip = null;
    let deselectionTooltipTimer = null;
    let hoveredContainer = null;
    
    // Create deselection tooltip
    function createDeselectionTooltip(text) {
        const tooltip = document.createElement('div');
        tooltip.className = 'anchor-tooltip';
        tooltip.textContent = text;
        document.body.appendChild(tooltip);
        return tooltip;
    }
    
    // Position deselection tooltip at top-middle of container
    function positionDeselectionTooltip(tooltip, container) {
        const rect = container.getBoundingClientRect();
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;
        const margin = 10;
        
        // Get tooltip dimensions by temporarily making it visible but off-screen
        tooltip.style.visibility = 'hidden';
        tooltip.style.left = '-9999px';
        tooltip.style.top = '-9999px';
        const tooltipRect = tooltip.getBoundingClientRect();
        const tooltipWidth = tooltipRect.width;
        tooltip.style.visibility = '';
        
        // Calculate initial position (centered above container)
        let left = rect.left + (rect.width / 2);
        
        // Adjust if tooltip would go off-screen
        if (left - tooltipWidth / 2 < margin) {
            // Align to left edge with margin
            left = margin + tooltipWidth / 2;
        } else if (left + tooltipWidth / 2 > window.innerWidth - margin) {
            // Align to right edge with margin
            left = window.innerWidth - margin - tooltipWidth / 2;
        }
        
        // Set final position
        tooltip.style.left = (left + scrollLeft) + 'px';
        tooltip.style.top = (rect.top + scrollTop - 4) + 'px';
    }
    
    // Remove deselection tooltip
    function removeDeselectionTooltip() {
        if (deselectionTooltip) {
            deselectionTooltip.remove();
            deselectionTooltip = null;
        }
        if (deselectionTooltipTimer) {
            clearTimeout(deselectionTooltipTimer);
            deselectionTooltipTimer = null;
        }
        hoveredContainer = null;
    }
    
    // --- Hover Handler for Deselection Tooltip ---
    document.addEventListener('mouseover', (event) => {
        // Check if ANY anchor is active globally
        if (window.zhLawAnchorActive) {
            removeDeselectionTooltip();
            return;
        }
        
        const container = event.target.closest('.provision-container.highlight, .subprovision-container.highlight, p.footnote.highlight');
        
        if (container && container !== hoveredContainer) {
            // Check if hovering over an anchor
            const anchor = event.target.closest('a[href^="#"]');
            if (!anchor) {
                hoveredContainer = container;
                removeDeselectionTooltip();
                deselectionTooltip = createDeselectionTooltip('Auswahl aufheben');
                positionDeselectionTooltip(deselectionTooltip, container);
            }
        }
    });
    
    document.addEventListener('mouseout', (event) => {
        const container = event.target.closest('.provision-container.highlight, .subprovision-container.highlight, p.footnote.highlight');
        const relatedTarget = event.relatedTarget;
        
        if (!relatedTarget || !relatedTarget.closest('.provision-container.highlight, .subprovision-container.highlight, p.footnote.highlight')) {
            removeDeselectionTooltip();
        }
    });
    
    // Watch for anchor active state changes
    let previousAnchorState = false;
    setInterval(() => {
        if (window.zhLawAnchorActive !== previousAnchorState) {
            previousAnchorState = window.zhLawAnchorActive;
            if (window.zhLawAnchorActive) {
                removeDeselectionTooltip();
            }
        }
    }, 50);
    
    // --- Primary Click Listener to Control ALL In-Page Navigation ---
    document.addEventListener('click', (event) => {
        const anchor = event.target.closest('a[href^="#"]');
        if (!anchor) {
            return;
        }
        
        // Check if this is a provision/subprovision anchor that anchor-tooltip.js handles
        const href = anchor.getAttribute('href');
        if (href && href.match(/#seq-\d+-prov-/)) {
            // Let anchor-tooltip.js handle these anchors
            return;
        }
        
        event.preventDefault();

        const clickedHash = anchor.hash;
        const currentHash = window.location.hash;
        const isFootnoteRefClick = !!anchor.closest('sup.footnote-ref');

        // Set flag to indicate this is internal navigation
        window.isInternalNavigation = true;

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
        // Only scroll if this is a browser navigation event (back/forward)
        // or if we're not doing internal navigation
        if (!window.isInternalNavigation) {
            scrollToAnchorWithOffset(window.location.hash);
        }
        // Reset the flag
        window.isInternalNavigation = false;
    });


    
    // --- Click Handler for Highlighted Containers (Deselection) ---
    document.addEventListener('click', (event) => {
        // Check if ANY anchor is active globally
        if (window.zhLawAnchorActive) {
            return;
        }
        
        // Check if the clicked element is within a highlighted container (including footnotes)
        const container = event.target.closest('.provision-container.highlight, .subprovision-container.highlight, p.footnote.highlight');
        
        if (!container) {
            return;
        }
        
        // Double-check if the click was on an anchor
        const anchor = event.target.closest('a[href^="#"]');
        if (anchor) {
            return;
        }
        
        // Prevent default and stop propagation
        event.preventDefault();
        event.stopPropagation();
        
        // Remove tooltip immediately on click
        removeDeselectionTooltip();
        
        // Set flag to prevent scrolling
        window.isInternalNavigation = true;
        
        // Remove the hash to trigger deselection
        history.pushState("", document.title, window.location.pathname + window.location.search);
        
        // Trigger highlight update
        setTimeout(() => {
            if (window.isInternalNavigation !== undefined) {
                window.isInternalNavigation = true;
            }
            const hashChangeEvent = new Event('hashchange');
            window.dispatchEvent(hashChangeEvent);
        }, 0);
    });

    // --- Initial Page Load Actions ---
    applyHighlight();
    // Only scroll on fresh page load or refresh, not on navigation within the page
    if (performance.navigation.type === performance.navigation.TYPE_NAVIGATE || 
        performance.navigation.type === performance.navigation.TYPE_RELOAD ||
        performance.navigation.type === undefined) { // Fallback for older browsers
        // Use a timeout to ensure the browser has rendered the page before scrolling
        setTimeout(() => {
            scrollToAnchorWithOffset(window.location.hash);
        }, 50);
    }
});
