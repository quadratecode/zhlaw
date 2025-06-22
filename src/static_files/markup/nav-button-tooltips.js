/**
 * Nav Button Tooltips
 * Adds tooltip functionality to navigation buttons on larger screens
 */

class NavButtonTooltips {
    constructor() {
        this.tooltips = new Map(); // Track tooltips for each button
        this.tooltipTimers = new Map(); // Track timers for each button
        this.init();
    }

    init() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.attachTooltips());
        } else {
            this.attachTooltips();
        }
    }

    attachTooltips() {
        // Find all nav-buttons with data-tooltip attribute
        const navButtons = document.querySelectorAll('.nav-button[data-tooltip]');
        
        navButtons.forEach(button => {
            this.addTooltipToButton(button);
        });
    }

    addTooltipToButton(button) {
        const tooltipText = button.getAttribute('data-tooltip');
        if (!tooltipText) return;

        const showTooltip = () => {
            // Only show on larger screens (1200px+)
            if (window.innerWidth < 1200) return;

            const buttonId = button.id || 'unknown';
            
            // Clear any existing timer
            if (this.tooltipTimers.has(buttonId)) {
                clearTimeout(this.tooltipTimers.get(buttonId));
                this.tooltipTimers.delete(buttonId);
            }
            
            // Remove existing tooltip for this button
            if (this.tooltips.has(buttonId)) {
                this.tooltips.get(buttonId).remove();
                this.tooltips.delete(buttonId);
            }
            
            // Create new tooltip
            const tooltip = document.createElement('div');
            tooltip.className = 'anchor-tooltip'; // Use anchor-tooltip class for above positioning
            tooltip.textContent = tooltipText;
            document.body.appendChild(tooltip);
            this.tooltips.set(buttonId, tooltip);
            
            // Position tooltip above button (centered) - using anchor-tooltip positioning
            const buttonRect = button.getBoundingClientRect();
            
            // Calculate centered position above the button
            const centerX = buttonRect.left + (buttonRect.width / 2);
            const tooltipY = buttonRect.top;
            
            // Apply position using the same transform pattern as anchor-tooltip
            tooltip.style.position = 'fixed';
            tooltip.style.left = centerX + 'px';
            tooltip.style.top = tooltipY + 'px';
            tooltip.style.transform = 'translateX(-50%) translateY(-100%)';
            tooltip.style.marginTop = '-4px';
            tooltip.style.visibility = 'visible';
        };
        
        const hideTooltip = (immediate = false) => {
            const buttonId = button.id || 'unknown';
            
            if (this.tooltipTimers.has(buttonId)) {
                clearTimeout(this.tooltipTimers.get(buttonId));
                this.tooltipTimers.delete(buttonId);
            }
            
            if (immediate) {
                if (this.tooltips.has(buttonId)) {
                    this.tooltips.get(buttonId).remove();
                    this.tooltips.delete(buttonId);
                }
            } else {
                const timer = setTimeout(() => {
                    if (this.tooltips.has(buttonId)) {
                        this.tooltips.get(buttonId).remove();
                        this.tooltips.delete(buttonId);
                    }
                }, 100);
                this.tooltipTimers.set(buttonId, timer);
            }
        };
        
        // Add event listeners
        button.addEventListener('mouseenter', showTooltip);
        button.addEventListener('mouseleave', () => hideTooltip(false));
        button.addEventListener('focus', showTooltip);
        button.addEventListener('blur', () => hideTooltip(false));
        
        // Hide tooltip immediately on various navigation events
        window.addEventListener('resize', () => hideTooltip(true));
        window.addEventListener('scroll', () => hideTooltip(true));
        window.addEventListener('beforeunload', () => hideTooltip(true));
        document.addEventListener('click', (e) => {
            if (!button.contains(e.target)) {
                hideTooltip(true);
            }
        });
    }

    // Clean up all tooltips
    cleanup() {
        this.tooltips.forEach(tooltip => tooltip.remove());
        this.tooltipTimers.forEach(timer => clearTimeout(timer));
        this.tooltips.clear();
        this.tooltipTimers.clear();
    }
}

// Initialize nav button tooltips when script loads
const navButtonTooltips = new NavButtonTooltips();