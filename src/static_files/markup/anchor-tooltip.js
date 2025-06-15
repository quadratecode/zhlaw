/**
 * Anchor tooltip functionality for dynamic linking to the latest version of provisions
 */

(function() {
    'use strict';

    // State management
    let anchorMap = null;
    let currentTooltip = null;
    let tooltipTimer = null;
    let collection = null;
    let ordnungsnummer = null;
    
    // Global state for anchor interaction
    window.zhLawAnchorActive = false;

    // Extract collection and ordnungsnummer from URL
    function extractLawInfo() {
        const pathMatch = window.location.pathname.match(/\/(col-[^\/]+)\/([^-]+)-\d+\.html/);
        if (pathMatch) {
            collection = pathMatch[1].replace('col-', '');
            ordnungsnummer = pathMatch[2];
            return true;
        }
        return false;
    }

    // Load anchor map for the current law
    async function loadAnchorMap() {
        if (!collection || !ordnungsnummer) return;

        try {
            const response = await fetch(`/anchor-maps/${collection}/${ordnungsnummer}-map.json`);
            if (response.ok) {
                anchorMap = await response.json();
            }
        } catch (error) {
            console.error('Failed to load anchor map:', error);
        }
    }

    // Parse anchor ID to extract provision and subprovision numbers
    function parseAnchorId(anchorId) {
        const match = anchorId.match(/seq-\d+-prov-(\d+[a-z]?)(?:-sub-(\d+))?/);
        if (match) {
            return {
                provision: match[1],
                subprovision: match[2] || null
            };
        }
        return null;
    }

    // Generate human-readable reference
    function generateHumanReference(provision, subprovision) {
        if (!anchorMap || !anchorMap.metadata) return '';

        const provType = anchorMap.metadata.provision_type || '§';
        const title = anchorMap.metadata.title || '';
        
        let reference = `${provType} ${provision}`;
        if (subprovision) {
            reference += ` Abs. ${subprovision}`;
        }
        reference += ` ${title}`;
        
        return reference;
    }

    // Check if anchor exists in latest version
    function checkAnchorExistsInLatest(provision, subprovision) {
        if (!anchorMap || !anchorMap.provisions || !anchorMap.provisions[provision]) {
            return false;
        }

        const provData = anchorMap.provisions[provision];
        
        if (subprovision) {
            return provData.subprovisions && 
                   provData.subprovisions[subprovision] && 
                   provData.subprovisions[subprovision].latest_version;
        }
        
        return provData.latest_version;
    }

    // Create tooltip element
    function createTooltip(text) {
        const tooltip = document.createElement('div');
        tooltip.className = 'anchor-tooltip';
        tooltip.textContent = text;
        document.body.appendChild(tooltip);
        return tooltip;
    }

    // Position tooltip above element
    function positionTooltip(tooltip, targetElement) {
        const rect = targetElement.getBoundingClientRect();
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;
        const margin = 10; // Minimum margin from viewport edges
        
        // Get tooltip dimensions by temporarily making it visible but off-screen
        tooltip.style.visibility = 'hidden';
        tooltip.style.left = '-9999px';
        tooltip.style.top = '-9999px';
        const tooltipRect = tooltip.getBoundingClientRect();
        const tooltipWidth = tooltipRect.width;
        tooltip.style.visibility = '';
        
        // Calculate initial position (centered above element)
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

    // Remove current tooltip
    function removeTooltip() {
        if (currentTooltip) {
            currentTooltip.remove();
            currentTooltip = null;
        }
        if (tooltipTimer) {
            clearTimeout(tooltipTimer);
            tooltipTimer = null;
        }
    }

    // Copy to clipboard with fallback
    async function copyToClipboard(text) {
        try {
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(text);
            } else {
                // Fallback for older browsers or non-secure contexts
                const textArea = document.createElement('textarea');
                textArea.value = text;
                textArea.style.position = 'fixed';
                textArea.style.left = '-999999px';
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
            }
            return true;
        } catch (error) {
            console.error('Failed to copy to clipboard:', error);
            return false;
        }
    }

    // Handle any anchor hover/focus for global state
    function handleAnyAnchorHover(element) {
        element.addEventListener('mouseenter', () => {
            window.zhLawAnchorActive = true;
            // Add class to all highlighted containers
            document.querySelectorAll('.provision-container.highlight, .subprovision-container.highlight, p.footnote.highlight').forEach(container => {
                container.classList.add('anchor-hover');
            });
        });
        
        element.addEventListener('mouseleave', () => {
            window.zhLawAnchorActive = false;
            // Remove class from all highlighted containers
            document.querySelectorAll('.provision-container.highlight, .subprovision-container.highlight, p.footnote.highlight').forEach(container => {
                container.classList.remove('anchor-hover');
            });
        });
        
        element.addEventListener('focus', () => {
            window.zhLawAnchorActive = true;
            // Add class to all highlighted containers
            document.querySelectorAll('.provision-container.highlight, .subprovision-container.highlight, p.footnote.highlight').forEach(container => {
                container.classList.add('anchor-hover');
            });
        });
        
        element.addEventListener('blur', () => {
            window.zhLawAnchorActive = false;
            // Remove class from all highlighted containers
            document.querySelectorAll('.provision-container.highlight, .subprovision-container.highlight, p.footnote.highlight').forEach(container => {
                container.classList.remove('anchor-hover');
            });
        });
    }

    // Handle anchor interaction
    function handleAnchorInteraction(element) {
        const href = element.getAttribute('href');
        if (!href || !href.startsWith('#')) return;

        const anchorId = href.substring(1);
        const parsed = parseAnchorId(anchorId);
        if (!parsed) return;

        element.addEventListener('mouseenter', handleMouseEnter);
        element.addEventListener('mouseleave', handleMouseLeave);
        element.addEventListener('focus', handleFocusEnter);
        element.addEventListener('blur', handleFocusLeave);
        element.addEventListener('click', handleClick);

        function handleMouseEnter() {
            removeTooltip();
            
            // Always show "Link kopieren" tooltip
            currentTooltip = createTooltip('Link kopieren');
            positionTooltip(currentTooltip, element);
        }

        function handleMouseLeave() {
            removeTooltip();
        }
        
        function handleFocusEnter() {
            removeTooltip();
            
            // Always show "Link kopieren" tooltip
            currentTooltip = createTooltip('Link kopieren');
            positionTooltip(currentTooltip, element);
        }
        
        function handleFocusLeave() {
            removeTooltip();
        }

        async function handleClick(event) {
            event.preventDefault();
            
            // Add anchor-hover class immediately to prevent outline on selection
            const container = element.closest('.provision-container, .subprovision-container, p.footnote');
            if (container) {
                container.classList.add('anchor-hover');
                // Also add to all other highlighted containers to be consistent
                document.querySelectorAll('.provision-container.highlight, .subprovision-container.highlight, p.footnote.highlight').forEach(c => {
                    c.classList.add('anchor-hover');
                });
            }
            
            // Generate the redirect link using the current domain
            const currentOrigin = window.location.origin;
            const redirectLink = `${currentOrigin}/col-${collection}/${ordnungsnummer}/latest#${anchorId}`;
            
            // Copy to clipboard
            const copied = await copyToClipboard(redirectLink);
            
            if (copied) {
                // Update tooltip to show success
                removeTooltip();
                currentTooltip = createTooltip('Link kopiert');
                positionTooltip(currentTooltip, element);
                
                // Remove after delay
                tooltipTimer = setTimeout(() => {
                    removeTooltip();
                }, 2000);
            }

            // Save current scroll position
            const scrollX = window.scrollX;
            const scrollY = window.scrollY;
            
            // Set flag to prevent scrolling BEFORE updating URL
            if (window.isInternalNavigation !== undefined) {
                window.isInternalNavigation = true;
            }
            
            // Update URL without triggering scroll
            history.pushState(null, '', '#' + anchorId);
            
            // Restore scroll position immediately to counteract any browser scrolling
            window.scrollTo(scrollX, scrollY);
            
            // Ensure flag stays set and trigger highlight update
            setTimeout(() => {
                // Re-set the flag in case it was cleared
                if (window.isInternalNavigation !== undefined) {
                    window.isInternalNavigation = true;
                }
                const event = new Event('hashchange');
                window.dispatchEvent(event);
                // Restore scroll position again in case hashchange triggered scrolling
                window.scrollTo(scrollX, scrollY);
            }, 0);
        }
    }

    // Show warning for missing anchors
    function showMissingAnchorWarning() {
        const hash = window.location.hash.substring(1);
        if (!hash) return;

        const parsed = parseAnchorId(hash);
        if (!parsed) return;

        // Check if this was a redirect from /latest
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('redirected') === 'true' && urlParams.get('anchor_missing') === 'true') {
            const humanRef = generateHumanReference(parsed.provision, parsed.subprovision);
            const currentVersion = document.querySelector('[data-pagefind-meta="nachtragsnummer"]')?.getAttribute('content') || '';
            
            const warning = document.createElement('div');
            warning.className = 'anchor-warning';
            warning.innerHTML = `
                <div class="anchor-warning-content">
                    <span>Die verlinkte Bestimmung ${humanRef} ist in der Nachtragsnummer ${currentVersion} nicht mehr enthalten.</span>
                    <button class="anchor-warning-close" onclick="this.parentElement.parentElement.remove()">×</button>
                </div>
            `;
            document.body.insertBefore(warning, document.body.firstChild);
        }
    }

    // Initialize when DOM is ready
    function initialize() {
        if (!extractLawInfo()) return;

        loadAnchorMap().then(() => {
            // Find all provision and subprovision anchors for tooltip functionality
            const provisionAnchors = document.querySelectorAll('a[href^="#seq-"][href*="-prov-"]');
            provisionAnchors.forEach(handleAnchorInteraction);
            
            // Find ALL anchors (including footnotes, etc.) for hover state management
            const allAnchors = document.querySelectorAll('a[href^="#"]');
            allAnchors.forEach(handleAnyAnchorHover);

            // Show warning if needed
            showMissingAnchorWarning();
        });
    }

    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize);
    } else {
        initialize();
    }
})();