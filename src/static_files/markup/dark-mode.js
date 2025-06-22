// Function to toggle dark mode
function toggleDarkMode() {
    // Remove both classes first
    document.documentElement.classList.remove('dark-mode', 'light-mode');
    
    // Check the current state
    const currentMode = localStorage.getItem('colorMode');
    
    // Toggle to the opposite mode
    if (currentMode === 'dark') {
        document.documentElement.classList.add('light-mode');
        localStorage.setItem('colorMode', 'light');
        updateToggleIcon(false);
    } else {
        document.documentElement.classList.add('dark-mode');
        localStorage.setItem('colorMode', 'dark');
        updateToggleIcon(true);
    }
}

// Function to update the toggle icon
function updateToggleIcon(isDarkMode) {
    const toggle = document.getElementById('dark-mode-toggle');
    if (toggle) {
        // Update icon and text content
        const iconSvg = isDarkMode ? 
            // Sun icon (LucideSun.svg) - show when in dark mode to indicate switching to light
            '<svg class="dark-mode-icon" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32l1.41 1.41M2 12h2m16 0h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"></path></svg>' : 
            // Moon icon (LucideMoon.svg) - show when in light mode to indicate switching to dark
            '<svg class="dark-mode-icon" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9a9 9 0 1 1-9-9"></path></svg>';
        
        toggle.innerHTML = iconSvg;
        
        // Update the aria-label for accessibility
        toggle.setAttribute('aria-label', isDarkMode ? 'Switch to light mode' : 'Switch to dark mode');
    }
}

// Function to check user preference
function checkDarkModePreference() {
    // First explicitly add light-mode to ensure defaults work with CSS
    document.documentElement.classList.add('light-mode');
    
    // Check localStorage first
    const colorMode = localStorage.getItem('colorMode');
    
    if (colorMode === 'dark') {
        document.documentElement.classList.remove('light-mode');
        document.documentElement.classList.add('dark-mode');
        updateToggleIcon(true);
    } else if (colorMode === 'light') {
        // Already added light-mode class above
        updateToggleIcon(false);
    } else {
        // If no preference is saved, check system preference
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            document.documentElement.classList.remove('light-mode');
            document.documentElement.classList.add('dark-mode');
            localStorage.setItem('colorMode', 'dark');
            updateToggleIcon(true);
        } else {
            // Already added light-mode class above
            localStorage.setItem('colorMode', 'light');
            updateToggleIcon(false);
        }
    }
}

// Listen for changes in system dark mode preference
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
    // Only apply system preference if user hasn't explicitly chosen a mode
    if (!localStorage.getItem('colorMode')) {
        document.documentElement.classList.remove('dark-mode', 'light-mode');
        
        if (e.matches) {
            document.documentElement.classList.add('dark-mode');
            localStorage.setItem('colorMode', 'dark');
            updateToggleIcon(true);
        } else {
            document.documentElement.classList.add('light-mode');
            localStorage.setItem('colorMode', 'light');
            updateToggleIcon(false);
        }
    }
});

// Initialize dark mode
document.addEventListener('DOMContentLoaded', function() {
    // Add the no-js class to detect JavaScript
    document.documentElement.classList.remove('no-js');
    document.documentElement.classList.add('js-enabled');
    
    // Add click event to toggle
    const toggle = document.getElementById('dark-mode-toggle');
    if (toggle) {
        toggle.addEventListener('click', toggleDarkMode);
    }
    
    // Check preference
    checkDarkModePreference();
});
