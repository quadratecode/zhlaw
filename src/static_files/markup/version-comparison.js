/**
 * Version Navigation
 * Handles toggling between original law view and diff view
 * Works with the minimal diff file structure
 */

// Initialize when the DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
  // Initialize navigation
  initVersionNavigation();
});

// Global state to track original content
let originalContent = null;
let diffUrl = null;

/**
 * Main initialization function
 * Analyzes the current page and adds the appropriate button
 */
function initVersionNavigation() {
  // Get current URL and path
  const url = window.location.pathname;
  
  // We only need to handle the regular law pages now
  // since users will always start from an original file
  const originalMatch = url.match(/\/col-zh\/([0-9\.]+)-([0-9a-z]+)\.html/i);
  if (originalMatch && originalMatch.length >= 3) {
    const ordnungsnummer = originalMatch[1];
    const currentVersion = originalMatch[2];
    
    // Find previous version by checking the navigation buttons
    const prevButton = document.getElementById('prev_ver');
    if (!prevButton) return;
    
    // If button is disabled, no previous version exists
    if (prevButton.hasAttribute('disabled')) {
      const disabledButton = createToggleButton('Keine früheren Versionen verfügbar', null, true);
      addButtonToVersionContainer(disabledButton);
      return;
    }
    
    // Extract previous version from onclick attribute
    const prevButtonClick = prevButton.getAttribute('onclick') || '';
    const prevMatch = prevButtonClick.match(/location\.href='[^-]+-([0-9a-z]+)\.html';/);
    
    if (!prevMatch || prevMatch.length < 2) {
      // No previous version found, add disabled button
      const disabledButton = createToggleButton('Keine früheren Versionen verfügbar', null, true);
      addButtonToVersionContainer(disabledButton);
      return;
    }
    
    const prevVersion = prevMatch[1];
    
    // Construct the diff URL
    diffUrl = `/col-zh/diff/${ordnungsnummer}-${prevVersion}-diff-${currentVersion}.html`;
    
    // Check if the diff file exists (asynchronously)
    fetch(diffUrl, { method: 'HEAD' })
      .then(response => {
        if (response.ok) {
          // Diff file exists, add active button
          addToggleButton(diffUrl);
        } else {
          // Diff file doesn't exist, add disabled button
          const disabledButton = createToggleButton('Versionsvergleich nicht verfügbar', null, true);
          addButtonToVersionContainer(disabledButton);
        }
      })
      .catch(() => {
        // Error checking file, assume it doesn't exist
        const disabledButton = createToggleButton('Versionsvergleich nicht verfügbar', null, true);
        addButtonToVersionContainer(disabledButton);
      });
  }
}

/**
 * Adds a toggle button to switch between original and diff views
 */
function addToggleButton(targetUrl) {
  const button = createToggleButton(
    'Versionen vergleichen', 
    () => toggleToDiffView(targetUrl),
    false
  );
  
  // Add button to version container
  addButtonToVersionContainer(button);
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
  
  // Add icon
  const iconSpan = document.createElement('span');
  iconSpan.className = 'nav-symbol';
  iconSpan.textContent = '↺';  // Circular arrow symbol for "compare versions"
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
 * Adds the button to the version container
 */
function addButtonToVersionContainer(buttonContainer) {
  const versionContainer = document.getElementById('version-container');
  if (versionContainer) {
    versionContainer.appendChild(buttonContainer);
  }
}

/**
 * Toggles to diff view by fetching the diff content and updating the page
 */
function toggleToDiffView(diffUrl) {
  // Store original content if not already cached
  if (!originalContent) {
    // Save the title
    const originalTitle = document.title;
    
    // Save the source text content
    const sourceTextDiv = document.getElementById('source-text');
    if (sourceTextDiv) {
      originalContent = {
        title: originalTitle,
        content: sourceTextDiv.innerHTML,
        h1Text: document.querySelector('.content h1')?.textContent || ''
      };
    }
  }
  
  // Show loading state
  const sourceTextDiv = document.getElementById('source-text');
  if (sourceTextDiv) {
    sourceTextDiv.innerHTML = '<div style="text-align: center; padding: 20px;">Lädt Versionsvergleich...</div>';
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
      const diffTitle = diffDoc.querySelector('title').textContent;
      const diffH1 = diffDoc.querySelector('.content h1')?.textContent || '';
      const diffH2 = diffDoc.querySelector('.content h1 + h2')?.textContent || '';
      const diffExplanation = diffDoc.querySelector('.diff-explanation')?.outerHTML || '';
      
      if (diffSourceText) {
        // Update the document title
        document.title = diffTitle;
        
        // Update the content heading
        const contentH1 = document.querySelector('.content h1');
        if (contentH1) {
          contentH1.textContent = diffH1;
        }
        
        // Add version subheading if not present
        if (diffH2) {
          const existingH2 = document.querySelector('.content h1 + h2');
          if (existingH2) {
            existingH2.textContent = diffH2;
          } else if (contentH1) {
            const h2 = document.createElement('h2');
            h2.textContent = diffH2;
            contentH1.after(h2);
          }
        }
        
        // Add explanation if available
        if (diffExplanation) {
          const existingExplanation = document.querySelector('.diff-explanation');
          if (!existingExplanation) {
            const explanationDiv = document.createElement('div');
            explanationDiv.innerHTML = diffExplanation;
            const h2 = document.querySelector('.content h1 + h2');
            if (h2) {
              h2.after(explanationDiv.firstChild);
            } else if (contentH1) {
              contentH1.after(explanationDiv.firstChild);
            }
          }
        }
        
        // Add diff info box
        addDiffInfoBox();
        
        // Update the source text with diff content
        sourceTextDiv.innerHTML = diffSourceText.innerHTML;
        
        // Update button for toggling back to original
        updateToggleButton('Original anzeigen', '↩', () => toggleToOriginalView());
      } else {
        // Handle error - diff content not found
        sourceTextDiv.innerHTML = '<div style="text-align: center; padding: 20px; color: red;">Fehler beim Laden der Änderungen</div>';
      }
    })
    .catch(error => {
      console.error('Error fetching diff:', error);
      // Handle error
      if (sourceTextDiv) {
        sourceTextDiv.innerHTML = '<div style="text-align: center; padding: 20px; color: red;">Fehler beim Laden der Änderungen: ' + error.message + '</div>';
      }
    });
}

/**
 * Toggles back to the original view using the cached content
 */
function toggleToOriginalView() {
  if (!originalContent) {
    // If no original content is cached, just reload the page
    window.location.reload();
    return;
  }
  
  // Restore original title
  document.title = originalContent.title;
  
  // Restore original heading
  const contentH1 = document.querySelector('.content h1');
  if (contentH1) {
    contentH1.textContent = originalContent.h1Text;
  }
  
  // Remove version subheading if it exists
  const versionHeading = document.querySelector('.content h1 + h2');
  if (versionHeading) {
    versionHeading.remove();
  }
  
  // Remove diff explanation if it exists
  const diffExplanation = document.querySelector('.diff-explanation');
  if (diffExplanation) {
    diffExplanation.remove();
  }
  
  // Remove diff info box if it exists
  const diffInfoBox = document.querySelector('.diff-info-box');
  if (diffInfoBox) {
    diffInfoBox.remove();
  }
  
  // Restore original content
  const sourceTextDiv = document.getElementById('source-text');
  if (sourceTextDiv) {
    sourceTextDiv.innerHTML = originalContent.content;
  }
  
  // Update button back to showing changes
  updateToggleButton('Versionen vergleichen', '↺', () => toggleToDiffView(diffUrl));
}

/**
 * Updates the toggle button text, icon, and click handler
 */
function updateToggleButton(text, icon, clickHandler) {
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
    
    // Remove old event listeners by cloning the button
    const newButton = button.cloneNode(true);
    button.parentNode.replaceChild(newButton, button);
    
    // Add new click handler
    newButton.addEventListener('click', clickHandler);
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
  
  // Extract version numbers from heading or URL
  let oldVersion = '';
  let newVersion = '';
  
  // Try to get versions from heading
  const versionHeading = document.querySelector('.content h1 + h2');
  if (versionHeading) {
    const versionMatch = versionHeading.textContent.match(/Version\s+([0-9a-z]+)\s*→\s*([0-9a-z]+)/i);
    if (versionMatch && versionMatch.length >= 3) {
      oldVersion = versionMatch[1];
      newVersion = versionMatch[2];
    }
  }
  
  // If not found in heading, try from URL
  if (!oldVersion || !newVersion) {
    const diffMatch = diffUrl?.match(/\/diff\/[^-]+-([0-9a-z]+)-diff-([0-9a-z]+)\.html/i);
    if (diffMatch && diffMatch.length >= 3) {
      oldVersion = diffMatch[1];
      newVersion = diffMatch[2];
    }
  }
  
  // Create the info box with formatted content
  const infoBox = document.createElement('div');
  infoBox.className = 'diff-info-box';
  
  // Add text with highlighted parts
  infoBox.innerHTML = `Versionsvergleich: ${oldVersion} → ${newVersion}. ` +
    `<span class="highlight-green">Grün markierte Texte</span> wurden hinzugefügt, ` +
    `<span class="highlight-red">rot markierte Texte</span> wurden entfernt.`;
  
  // Insert at the beginning of the law div
  lawDiv.insertBefore(infoBox, lawDiv.firstChild);
}
