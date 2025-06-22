/**
 * Copy links functionality for the sidebar URL fields with tooltip support
 */

(function() {
    'use strict';

    // State management for tooltips
    let currentTooltip = null;
    let tooltipTimer = null;

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

    // Create tooltip element
    function createTooltip(text) {
        const tooltip = document.createElement('div');
        tooltip.className = 'copy-tooltip';
        tooltip.textContent = text;
        document.body.appendChild(tooltip);
        return tooltip;
    }

    // Position tooltip above button
    function positionTooltip(tooltip, button) {
        const rect = button.getBoundingClientRect();
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        const margin = 10;
        
        // Get tooltip dimensions
        tooltip.style.visibility = 'hidden';
        tooltip.style.left = '-9999px';
        tooltip.style.top = '-9999px';
        const tooltipRect = tooltip.getBoundingClientRect();
        const tooltipWidth = tooltipRect.width;
        tooltip.style.visibility = '';
        
        // Calculate position (centered above button)
        let left = rect.left + (rect.width / 2);
        
        // Adjust if tooltip would go off-screen
        if (left - tooltipWidth / 2 < margin) {
            left = margin + tooltipWidth / 2;
        } else if (left + tooltipWidth / 2 > window.innerWidth - margin) {
            left = window.innerWidth - margin - tooltipWidth / 2;
        }
        
        // Set position
        tooltip.style.left = left + 'px';
        tooltip.style.top = (rect.top + scrollTop) + 'px';
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

    // Create checkmark SVG from LucideCopyCheck icon
    function createCheckmarkSVG() {
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
        svg.setAttribute('width', '16');
        svg.setAttribute('height', '16');
        svg.setAttribute('viewBox', '0 0 24 24');
        
        const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        g.setAttribute('fill', 'none');
        g.setAttribute('stroke', 'currentColor');
        g.setAttribute('stroke-linecap', 'round');
        g.setAttribute('stroke-linejoin', 'round');
        g.setAttribute('stroke-width', '2');
        
        const checkPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        checkPath.setAttribute('d', 'm12 15l2 2l4-4');
        
        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('width', '14');
        rect.setAttribute('height', '14');
        rect.setAttribute('x', '8');
        rect.setAttribute('y', '8');
        rect.setAttribute('rx', '2');
        rect.setAttribute('ry', '2');
        
        const copyPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        copyPath.setAttribute('d', 'M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2');
        
        g.appendChild(checkPath);
        g.appendChild(rect);
        g.appendChild(copyPath);
        svg.appendChild(g);
        
        return svg;
    }

    // Handle button interaction
    function handleButtonInteraction(button) {
        const textToCopy = button.getAttribute('data-copy-text');
        if (!textToCopy) return;

        // Store original SVG
        const originalSVG = button.querySelector('svg').cloneNode(true);

        // Show tooltip on hover
        button.addEventListener('mouseenter', () => {
            removeTooltip();
            currentTooltip = createTooltip('Link kopieren');
            positionTooltip(currentTooltip, button);
        });

        button.addEventListener('mouseleave', () => {
            removeTooltip();
        });

        // Show tooltip on focus
        button.addEventListener('focus', () => {
            removeTooltip();
            currentTooltip = createTooltip('Link kopieren');
            positionTooltip(currentTooltip, button);
        });

        button.addEventListener('blur', () => {
            removeTooltip();
        });

        // Handle click
        button.addEventListener('click', async (e) => {
            e.preventDefault();
            
            const success = await copyToClipboard(textToCopy);
            
            if (success) {
                // Update tooltip to show success
                removeTooltip();
                currentTooltip = createTooltip('Link kopiert');
                positionTooltip(currentTooltip, button);
                
                // Replace icon with checkmark
                const currentSVG = button.querySelector('svg');
                const checkmarkSVG = createCheckmarkSVG();
                button.classList.add('copy-success');
                currentSVG.replaceWith(checkmarkSVG);
                
                // Remove tooltip after delay
                tooltipTimer = setTimeout(() => {
                    removeTooltip();
                }, 2000);
                
                // Revert icon after 1.2 seconds
                setTimeout(() => {
                    const newOriginalSVG = originalSVG.cloneNode(true);
                    button.querySelector('svg').replaceWith(newOriginalSVG);
                    button.classList.remove('copy-success');
                }, 1200);
            }
        });
    }

    // Initialize copy buttons
    function initialize() {
        // Add js-enabled class to show JS-only elements
        document.documentElement.classList.add('js-enabled');
        
        const copyButtons = document.querySelectorAll('.link-copy-btn');
        copyButtons.forEach(button => {
            handleButtonInteraction(button);
        });
    }

    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialize);
    } else {
        initialize();
    }
})();