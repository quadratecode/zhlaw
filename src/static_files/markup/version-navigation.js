/**
 * Version Navigation
 * Adds navigation between original and diff views with dynamic content loading
 */

// Initialize when the DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
  // Add custom CSS for the version toggle button
  addCustomStyles();
  
  // Initialize navigation
  initVersionNavigation();
});

// Global state to track original content
let originalContent = null;
let diffContent = null;
let diffUrl = null;
let inDiffView = false;

/**
 * Adds custom CSS for the version toggle button and diff styling
 */
function addCustomStyles() {
  const styleElement = document.createElement('style');
  styleElement.textContent = `
    /* Compact button styling */
    .version-toggle-container {
      margin-top: 10px;
    }
    
    .version-toggle-button {
      display: flex !important;
      flex-direction: row !important;
      align-items: center;
      justify-content: center;
      width: 100%;
      padding: 8px !important;
    }
    
    .version-toggle-button .nav-symbol {
      margin-right: 8px;
      font-size: 1.2rem;
    }
    
    /* Diff view info box */
    .diff-info-box {
      border: 1px solid var(--dark-dark-purple);
      background-color: var(--light-purple);
      color: var(--dark-purple);
      font-weight: var(--font-weight-bold);
      padding: 1em;
      margin-top: 0.5em;
      margin-bottom: 1em;
      line-height: 1.5;
      font-size: 0.95em;
    }
    
    /* Dark mode compatible colors for diffs */
    .insert {
      background-color: var(--in-force-green) !important;
      text-decoration: none !important;
      padding: 1px 0 !important;
    }
    
    .delete {
      background-color: var(--in-force-red) !important;
      text-decoration: line-through !important;
      padding: 1px 0 !important;
    }
  `;
  document.head.appendChild(styleElement);
}

/**
 * Main initialization function
 * Analyzes the current page and adds the appropriate button
 */
function initVersionNavigation() {
  // Get current URL and path
  const url = window.location.pathname;
  
  // Check if we're on a diff page or a regular law page
  const isDiffPage = url.includes('/diff/');
  
  if (isDiffPage) {
    // If already on a diff page, just save the state
    inDiffView = true;
    
    // Extract URL components to generate the original URL
    const diffMatch = url.match(/\/diff\/([0-9\.]+)-([0-9a-z]+)-diff-([0-9a-z]+)\.html/i);
    if (diffMatch && diffMatch.length >= 4) {
      const ordnungsnummer = diffMatch[1];
      const newerVersion = diffMatch[3];
      
      // Save the original URL for the toggle button
      const originalUrl = `/col-zh/${ordnungsnummer}-${newerVersion}.html`;
      
      // Add the toggle button
      addToggleButton(originalUrl);
      
      // Add the diff info box if not already present
      addDiffInfoBox();
    }
  } else {
    // Extract URL components to generate the diff URL
    const originalMatch = url.match(/\/col-zh\/([0-9\.]+)-([0-9a-z]+)\.html/i);
    if (originalMatch && originalMatch.length >= 3) {
      const ordnungsnummer = originalMatch[1];
      const currentVersion = originalMatch[2];
      
      // Find previous version by checking the navigation buttons
      const prevButton = document.getElementById('prev_ver');
      if (!prevButton) return;
      
      // If button is disabled, no previous version exists
      if (prevButton.hasAttribute('disabled')) {
        const disabledButton = createToggleButton('Änderungen zur letzten Version anzeigen', null, true);
        addButtonToVersionContainer(disabledButton);
        return;
      }
      
      // Extract previous version from onclick attribute
      const prevButtonClick = prevButton.getAttribute('onclick') || '';
      const prevMatch = prevButtonClick.match(/location\.href='[^-]+-([0-9a-z]+)\.html';/);
      
      if (!prevMatch || prevMatch.length < 2) {
        // No previous version found, add disabled button
        const disabledButton = createToggleButton('Änderungen zur letzten Version anzeigen', null, true);
        addButtonToVersionContainer(disabledButton);
        return;
      }
      
      const prevVersion = prevMatch[1];
      
      // Construct the diff URL
      diffUrl = `/col-zh/diff/${ordnungsnummer}-${prevVersion}-diff-${currentVersion}.html`;
      
      // Check if diff file exists (not necessary, but could be added later)
      // For now, assume it exists if we have a previous version
      
      // Add toggle button
      addToggleButton(diffUrl);
    }
  }
}

/**
 * Adds a toggle button to switch between original and diff views
 */
function addToggleButton(targetUrl) {
  const button = createToggleButton(
    inDiffView ? 'Original anzeigen' : 'Änderungen zur letzten Version anzeigen', 
    () => toggleView(targetUrl),
    false
  );
  
  if (inDiffView) {
    // Add button to sidebar on diff page
    const sidebar = document.getElementById('sidebar');
    if (sidebar) {
      sidebar.appendChild(button);
    }
  } else {
    // Add button to version container on original page
    addButtonToVersionContainer(button);
  }
}

/**
 * Creates a button with the specified text, click handler, and disabled state
 */
function createToggleButton(text, clickHandler, isDisabled) {
  // Create container
  const container = document.createElement('div');
  container.className = 'nav-buttons version-toggle-container';
  
  // Create button
  const button = document.createElement('button');
  button.className = 'nav-button version-toggle-button';
  button.id = 'version-toggle-button';
  
  // Add icon based on mode
  const iconSpan = document.createElement('span');
  iconSpan.className = 'nav-symbol';
  iconSpan.textContent = inDiffView ? '←' : '⑂';  // Back arrow or git branch symbol
  button.appendChild(iconSpan);
  
  // Add text
  const textSpan = document.createElement('span');
  textSpan.className = 'nav-text';
  textSpan.textContent = text;
  button.appendChild(textSpan);
  
  // Set disabled state if needed
  if (isDisabled) {
    button.disabled = true;
  } else {
    // Add click handler if provided
    button.addEventListener('click', clickHandler);
  }
  
  container.appendChild(button);
  return container;
}

/**
 * Adds the button to the version container on original law pages
 */
function addButtonToVersionContainer(buttonContainer) {
  const versionContainer = document.getElementById('version-container');
  if (versionContainer) {
    versionContainer.appendChild(buttonContainer);
  }
}

/**
 * Adds an info box at the top of the law section
 */
function addDiffInfoBox() {
  // Check if the info box already exists
  if (document.querySelector('.diff-info-box')) {
    return;
  }
  
  // Find the law div
  const lawDiv = document.getElementById('law');
  if (!lawDiv) return;
  
  // Create the info box
  const infoBox = document.createElement('div');
  infoBox.className = 'diff-info-box';
  infoBox.textContent = 'Dies ist eine Versionsvergleichsansicht. Grün markierte Texte wurden hinzugefügt, rot markierte Texte wurden entfernt.';
  
  // Insert at the beginning of the law div
  lawDiv.insertBefore(infoBox, lawDiv.firstChild);
}

/**
 * Toggles between original and diff views
 */
function toggleView(targetUrl) {
  if (inDiffView) {
    // We're currently in diff view, switch to original
    switchToOriginal(targetUrl);
  } else {
    // We're in original view, switch to diff
    switchToDiff(targetUrl);
  }
}

/**
 * Switches from diff view to original view
 */
function switchToOriginal(originalUrl) {
  // If we have cached original content, use it
  if (originalContent) {
    applyOriginalContent();
  } else {
    // Otherwise, navigate to the original page
    window.location.href = originalUrl;
  }
}

/**
 * Applies the cached original content
 */
function applyOriginalContent() {
  // Find the content elements
  const sourceTextDiv = document.getElementById('source-text');
  const contentDiv = document.querySelector('.content');
  
  if (sourceTextDiv && contentDiv && originalContent) {
    // Remove diff info box
    const diffInfoBox = document.querySelector('.diff-info-box');
    if (diffInfoBox) {
      diffInfoBox.remove();
    }
    
    // Remove diff explanation if it exists
    const diffExplanation = document.querySelector('.diff-explanation');
    if (diffExplanation) {
      diffExplanation.remove();
    }
    
    // Restore original content
    sourceTextDiv.innerHTML = originalContent;
    
    // Reset heading if it was changed
    const h1 = contentDiv.querySelector('h1');
    if (h1 && h1.textContent.startsWith('Änderungen: ')) {
      h1.textContent = h1.textContent.replace('Änderungen: ', '');
    }
    
    // Remove version subheading if it exists
    const versionHeading = contentDiv.querySelector('h1 + h2');
    if (versionHeading && versionHeading.textContent.includes('Version ')) {
      versionHeading.remove();
    }
    
    // Update button
    updateToggleButton('Änderungen zur letzten Version anzeigen', '⑂');
    
    // Update state
    inDiffView = false;
  }
}

/**
 * Switches from original view to diff view by fetching the diff content
 */
function switchToDiff(diffUrl) {
  // Store original content if not already cached
  if (!originalContent) {
    const sourceTextDiv = document.getElementById('source-text');
    if (sourceTextDiv) {
      originalContent = sourceTextDiv.innerHTML;
    }
  }
  
  // If we already have the diff content cached, use it
  if (diffContent) {
    applyDiffContent();
    return;
  }
  
  // Show loading state
  const sourceTextDiv = document.getElementById('source-text');
  if (sourceTextDiv) {
    sourceTextDiv.innerHTML = '<div style="text-align: center; padding: 20px;">Lädt Änderungen...</div>';
  }
  
  // Fetch the diff content
  fetch(diffUrl)
    .then(response => {
      if (!response.ok) {
        throw new Error('Network response was not ok');
      }
      return response.text();
    })
    .then(html => {
      // Parse the diff page HTML
      const parser = new DOMParser();
      const diffDoc = parser.parseFromString(html, 'text/html');
      
      // Extract the diff content
      const diffSourceText = diffDoc.getElementById('source-text');
      const diffH1 = diffDoc.querySelector('.content h1');
      const diffH2 = diffDoc.querySelector('.content h1 + h2');
      const diffExplanation = diffDoc.querySelector('.diff-explanation');
      
      if (diffSourceText) {
        // Save the diff content
        diffContent = {
          sourceText: diffSourceText.innerHTML,
          heading: diffH1 ? diffH1.textContent : null,
          subheading: diffH2 ? diffH2.textContent : null,
          explanation: diffExplanation ? diffExplanation.outerHTML : null
        };
        
        // Apply the diff content
        applyDiffContent();
      } else {
        // Handle error
        if (sourceTextDiv) {
          sourceTextDiv.innerHTML = '<div style="text-align: center; padding: 20px; color: red;">Fehler beim Laden der Änderungen</div>';
        }
      }
    })
    .catch(error => {
      console.error('Error fetching diff:', error);
      // Handle error
      if (sourceTextDiv) {
        sourceTextDiv.innerHTML = '<div style="text-align: center; padding: 20px; color: red;">Fehler beim Laden der Änderungen</div>';
      }
    });
}

/**
 * Applies the cached diff content
 */
function applyDiffContent() {
  // Find the content elements
  const sourceTextDiv = document.getElementById('source-text');
  const contentDiv = document.querySelector('.content');
  const lawDiv = document.getElementById('law');
  
  if (sourceTextDiv && contentDiv && diffContent) {
    // Update content elements
    sourceTextDiv.innerHTML = diffContent.sourceText;
    
    // Update heading if available
    const h1 = contentDiv.querySelector('h1');
    if (h1 && diffContent.heading) {
      h1.textContent = diffContent.heading;
    }
    
    // Add version subheading if available
    if (diffContent.subheading) {
      const h2 = document.createElement('h2');
      h2.textContent = diffContent.subheading;
      if (h1) {
        h1.after(h2);
      }
    }
    
    // Add explanation if available
    if (diffContent.explanation) {
      const explanationDiv = document.createElement('div');
      explanationDiv.innerHTML = diffContent.explanation;
      const explanationElement = explanationDiv.firstChild;
      
      // Insert after heading or subheading
      const subheading = contentDiv.querySelector('h1 + h2');
      if (subheading) {
        subheading.after(explanationElement);
      } else if (h1) {
        h1.after(explanationElement);
      } else {
        contentDiv.prepend(explanationElement);
      }
    }
    
    // Add diff info box
    if (lawDiv) {
      addDiffInfoBox();
    }
    
    // Update button
    updateToggleButton('Original anzeigen', '←');
    
    // Update state
    inDiffView = true;
  }
}

/**
 * Updates the toggle button text and icon
 */
function updateToggleButton(text, icon) {
  const button = document.getElementById('version-toggle-button');
  if (button) {
    const textSpan = button.querySelector('.nav-text');
    const iconSpan = button.querySelector('.nav-symbol');
    
    if (textSpan) {
      textSpan.textContent = text;
    }
    
    if (iconSpan) {
      iconSpan.textContent = icon;
    }
  }
}
