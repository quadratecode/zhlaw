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
        toggle.innerHTML = isDarkMode ? 
            '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>' : 
            '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>';
        
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
