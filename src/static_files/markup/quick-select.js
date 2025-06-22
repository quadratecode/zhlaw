/**
 * Quick Select Functionality
 * Provides quick navigation to specific law provisions
 */

class QuickSelect {
    constructor() {
        this.container = document.getElementById('quick-select');
        if (!this.container) return;
        
        this.modal = null;
        this.isOpen = false;
        this.lawsIndex = [];
        this.currentHighlightIndex = -1;
        
        this.init();
    }
    
    init() {
        this.createButton();
        this.createModal();
        this.loadLawsIndex();
        this.attachEventListeners();
    }
    
    createButton() {
        this.container.innerHTML = `
            <button class="quick-select-button" aria-label="Schnellauswahl öffnen">
                <svg class="quick-select-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"></path>
                    <path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"></path>
                    <path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"></path>
                    <path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"></path>
                </svg>
                <span class="quick-select-button-text">
                    Schnellauswahl
                </span>
            </button>
        `;
        
        this.button = this.container.querySelector('.quick-select-button');
        this.button.addEventListener('click', () => this.open());
        
        // Add tooltip functionality
        this.addTooltip();
    }
    
    createModal() {
        this.modal = document.createElement('div');
        this.modal.className = 'quick-select-modal';
        this.modal.innerHTML = `
            <div class="quick-select-modal-content">
                <form class="quick-select-form">
                    <div class="quick-select-fields">
                        <div class="quick-select-field-group collection-field">
                            <label for="quick-select-collection" class="quick-select-label">Sammlung</label>
                            <select id="quick-select-collection" class="quick-select-select">
                                <option value="zh" selected>ZH</option>
                                <option value="ch">CH</option>
                            </select>
                        </div>
                        <div class="quick-select-field-group">
                            <label for="quick-select-abbreviation" class="quick-select-label">Abkürzung, Kurztitel oder Ordnungsnummer</label>
                            <div style="position: relative;">
                                <input type="text" id="quick-select-abbreviation" class="quick-select-input" 
                                       placeholder="z.B. IDG oder 170.4" autocomplete="off">
                                <div class="quick-select-autocomplete" id="quick-select-autocomplete"></div>
                            </div>
                        </div>
                        <div class="quick-select-field-group provision-field">
                            <label for="quick-select-provision" class="quick-select-label">Bestimmung</label>
                            <input type="text" id="quick-select-provision" class="quick-select-input" 
                                   placeholder="z.B. 1 oder 10a" maxlength="8" autocomplete="off">
                        </div>
                    </div>
                    <button type="submit" class="quick-select-submit">Zur Bestimmung navigieren</button>
                    <div class="quick-select-error" id="quick-select-error"></div>
                    <div class="quick-select-loading" id="quick-select-loading">Lade Gesetzesindex...</div>
                </form>
            </div>
        `;
        
        document.body.appendChild(this.modal);
        
        // Cache DOM elements
        this.form = this.modal.querySelector('.quick-select-form');
        this.collectionSelect = this.modal.querySelector('#quick-select-collection');
        this.abbreviationInput = this.modal.querySelector('#quick-select-abbreviation');
        this.provisionInput = this.modal.querySelector('#quick-select-provision');
        this.autocompleteContainer = this.modal.querySelector('#quick-select-autocomplete');
        this.submitBtn = this.modal.querySelector('.quick-select-submit');
        this.errorDiv = this.modal.querySelector('#quick-select-error');
        this.loadingDiv = this.modal.querySelector('#quick-select-loading');
    }
    
    async loadLawsIndex() {
        try {
            // Load anchor maps index
            const response = await fetch('/anchor-maps-index.json');
            if (!response.ok) {
                console.error('Failed to load anchor maps index');
                return;
            }
            
            const data = await response.json();
            this.lawsIndex = data.laws || [];
            
            // Check if we have multiple collections and hide filter if only one
            this.updateCollectionFilterVisibility();
            
            // Hide loading message
            this.loadingDiv.style.display = 'none';
        } catch (error) {
            console.error('Error loading laws index:', error);
            this.loadingDiv.textContent = 'Fehler beim Laden des Gesetzesindex';
        }
    }
    
    updateCollectionFilterVisibility() {
        // Get unique collections from laws index
        const collections = new Set();
        this.lawsIndex.forEach(law => {
            if (law.collection) {
                collections.add(law.collection);
            }
        });
        
        // Hide collection filter if only one collection is available
        const collectionFieldGroup = this.modal.querySelector('.collection-field');
        if (collections.size <= 1) {
            collectionFieldGroup.style.display = 'none';
        } else {
            collectionFieldGroup.style.display = 'block';
        }
    }
    
    attachEventListeners() {
        // Close on background click
        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) {
                this.close();
            }
        });
        
        // Close on Escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isOpen) {
                this.close();
            }
        });
        
        // Open on 'Q' key (when not in input)
        document.addEventListener('keydown', (e) => {
            const isInputFocused = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName);
            if ((e.key === 'q' || e.key === 'Q') && !isInputFocused && !this.isOpen) {
                e.preventDefault();
                this.open();
            }
        });
        
        // Autocomplete functionality
        this.abbreviationInput.addEventListener('input', () => this.handleAutocomplete());
        this.abbreviationInput.addEventListener('keydown', (e) => this.handleAutocompleteKeyboard(e));
        
        // Auto-populate with top result on blur
        this.abbreviationInput.addEventListener('blur', () => {
            // Small delay to allow click events on autocomplete items to fire first
            setTimeout(() => {
                // If input has a value but no selection has been made yet
                if (this.abbreviationInput.value.trim() && !this.abbreviationInput.dataset.ordnungsnummer) {
                    // Perform search to find matches
                    const query = this.abbreviationInput.value.trim().toLowerCase();
                    const collection = this.collectionSelect.value;
                    
                    // Filter laws by collection and search query
                    const matches = this.lawsIndex.filter(law => {
                        if (law.collection !== collection) return false;
                        
                        const abbreviation = (law.abbreviation || '').toLowerCase();
                        const title = (law.title || '').toLowerCase();
                        const kurztitel = (law.kurztitel || '').toLowerCase();
                        const ordnungsnummer = (law.ordnungsnummer || '').toLowerCase();
                        
                        return abbreviation.includes(query) || 
                               title.includes(query) || 
                               kurztitel.includes(query) ||
                               ordnungsnummer.includes(query);
                    });
                    
                    // Sort matches: exact abbreviation matches first, then partial matches
                    matches.sort((a, b) => {
                        const aAbbr = (a.abbreviation || '').toLowerCase();
                        const bAbbr = (b.abbreviation || '').toLowerCase();
                        
                        if (aAbbr === query && bAbbr !== query) return -1;
                        if (bAbbr === query && aAbbr !== query) return 1;
                        if (aAbbr.startsWith(query) && !bAbbr.startsWith(query)) return -1;
                        if (bAbbr.startsWith(query) && !aAbbr.startsWith(query)) return 1;
                        
                        return aAbbr.localeCompare(bAbbr);
                    });
                    
                    // If we have matches, select the first one
                    if (matches.length > 0) {
                        const topMatch = matches[0];
                        
                        // Build the display value
                        const parts = [];
                        if (topMatch.abbreviation) parts.push(topMatch.abbreviation);
                        if (topMatch.ordnungsnummer) parts.push(topMatch.ordnungsnummer);
                        // Only add kurztitel if neither abbreviation nor ordnungsnummer exist
                        if (!topMatch.abbreviation && !topMatch.ordnungsnummer && topMatch.kurztitel) {
                            parts.push(topMatch.kurztitel);
                        }
                        const displayValue = parts.join(' ∗ ');
                        
                        // Update the input with the full result
                        this.abbreviationInput.value = displayValue;
                        this.abbreviationInput.dataset.ordnungsnummer = topMatch.ordnungsnummer;
                        this.abbreviationInput.dataset.abbreviation = topMatch.abbreviation || '';
                        this.abbreviationInput.dataset.kurztitel = topMatch.kurztitel || '';
                    }
                }
                this.hideAutocomplete();
            }, 200);
        });
        
        // Collection change
        this.collectionSelect.addEventListener('change', () => {
            this.handleAutocomplete();
            this.clearError();
        });
        
        // Form submission
        this.form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleSubmit();
        });
        
        // Clear error on input
        this.abbreviationInput.addEventListener('input', () => this.clearError());
        this.provisionInput.addEventListener('input', () => this.clearError());
        
        // Restrict provision input to alphanumeric characters only
        this.provisionInput.addEventListener('input', (e) => {
            const value = e.target.value;
            const cleanedValue = value.replace(/[^a-zA-Z0-9]/g, '');
            if (value !== cleanedValue) {
                e.target.value = cleanedValue;
            }
        });
        
        // Note: Warning display is handled by anchor-tooltip.js
        // We only store metadata in sessionStorage for it to use
    }
    
    handleAutocomplete() {
        const query = this.abbreviationInput.value.trim().toLowerCase();
        const collection = this.collectionSelect.value;
        
        if (query.length < 1) {
            this.hideAutocomplete();
            return;
        }
        
        // Filter laws by collection and search query
        const matches = this.lawsIndex.filter(law => {
            if (law.collection !== collection) return false;
            
            const abbreviation = (law.abbreviation || '').toLowerCase();
            const title = (law.title || '').toLowerCase();
            const kurztitel = (law.kurztitel || '').toLowerCase();
            const ordnungsnummer = (law.ordnungsnummer || '').toLowerCase();
            
            return abbreviation.includes(query) || 
                   title.includes(query) || 
                   kurztitel.includes(query) ||
                   ordnungsnummer.includes(query);
        });
        
        // Sort matches: exact abbreviation matches first, then partial matches
        matches.sort((a, b) => {
            const aAbbr = (a.abbreviation || '').toLowerCase();
            const bAbbr = (b.abbreviation || '').toLowerCase();
            
            if (aAbbr === query && bAbbr !== query) return -1;
            if (bAbbr === query && aAbbr !== query) return 1;
            if (aAbbr.startsWith(query) && !bAbbr.startsWith(query)) return -1;
            if (bAbbr.startsWith(query) && !aAbbr.startsWith(query)) return 1;
            
            return aAbbr.localeCompare(bAbbr);
        });
        
        // Show top 15 matches for slightly longer dropdown
        const topMatches = matches.slice(0, 15);
        this.showAutocomplete(topMatches);
    }
    
    showAutocomplete(matches) {
        if (matches.length === 0) {
            // Show "no results" message
            this.autocompleteContainer.innerHTML = `
                <div class="quick-select-autocomplete-no-results">
                    Kein Eintrag gefunden.
                </div>
            `;
            this.autocompleteContainer.style.display = 'block';
            return;
        }
        
        this.autocompleteContainer.innerHTML = matches.map((law, index) => {
            // Build first line with available fields
            const parts = [];
            if (law.abbreviation) parts.push(this.escapeHtml(law.abbreviation));
            if (law.kurztitel) parts.push(this.escapeHtml(law.kurztitel));
            if (law.ordnungsnummer) parts.push(this.escapeHtml(law.ordnungsnummer));
            const firstLine = parts.join(' ∗ ');
            
            return `
                <div class="quick-select-autocomplete-item" data-index="${index}" 
                     data-ordnungsnummer="${law.ordnungsnummer}"
                     data-abbreviation="${law.abbreviation || ''}"
                     data-kurztitel="${law.kurztitel || ''}"
                     data-title="${law.title || ''}">
                    <div class="autocomplete-abbreviation">${firstLine}</div>
                    <div class="autocomplete-title">${this.escapeHtml(law.title)}</div>
                </div>
            `;
        }).join('');
        
        this.autocompleteContainer.style.display = 'block';
        this.currentHighlightIndex = -1;
        
        // Add click handlers
        this.autocompleteContainer.querySelectorAll('.quick-select-autocomplete-item').forEach(item => {
            item.addEventListener('click', () => this.selectAutocompleteItem(item));
        });
    }
    
    hideAutocomplete() {
        this.autocompleteContainer.style.display = 'none';
        this.currentHighlightIndex = -1;
    }
    
    handleAutocompleteKeyboard(e) {
        const items = this.autocompleteContainer.querySelectorAll('.quick-select-autocomplete-item');
        if (items.length === 0) return;
        
        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.currentHighlightIndex = Math.min(this.currentHighlightIndex + 1, items.length - 1);
                this.updateHighlight(items);
                break;
                
            case 'ArrowUp':
                e.preventDefault();
                this.currentHighlightIndex = Math.max(this.currentHighlightIndex - 1, -1);
                this.updateHighlight(items);
                break;
                
            case 'Enter':
                if (this.currentHighlightIndex >= 0) {
                    e.preventDefault();
                    this.selectAutocompleteItem(items[this.currentHighlightIndex]);
                }
                break;
                
            case 'Escape':
                this.hideAutocomplete();
                break;
            
            case 'Tab':
                if (this.currentHighlightIndex >= 0) {
                    e.preventDefault();
                    this.selectAutocompleteItem(items[this.currentHighlightIndex]);
                } else {
                    this.hideAutocomplete();
                }
                break;
        }
    }
    
    updateHighlight(items) {
        items.forEach((item, index) => {
            if (index === this.currentHighlightIndex) {
                item.classList.add('highlighted');
                item.scrollIntoView({ block: 'nearest' });
            } else {
                item.classList.remove('highlighted');
            }
        });
    }
    
    selectAutocompleteItem(item) {
        const abbreviation = item.dataset.abbreviation;
        const kurztitel = item.dataset.kurztitel;
        const ordnungsnummer = item.dataset.ordnungsnummer;
        
        // Build the display value showing abbreviation and ordnungsnummer (most common case)
        const parts = [];
        if (abbreviation) parts.push(abbreviation);
        if (ordnungsnummer) parts.push(ordnungsnummer);
        // Only add kurztitel if neither abbreviation nor ordnungsnummer exist
        if (!abbreviation && !ordnungsnummer && kurztitel) {
            parts.push(kurztitel);
        }
        const displayValue = parts.join(' ∗ ');
        
        this.abbreviationInput.value = displayValue;
        this.abbreviationInput.dataset.ordnungsnummer = ordnungsnummer;
        this.abbreviationInput.dataset.abbreviation = abbreviation;
        this.abbreviationInput.dataset.kurztitel = kurztitel;
        this.hideAutocomplete();
        
        // Only focus provision input if we're not already in the blur event
        if (document.activeElement === this.abbreviationInput) {
            this.provisionInput.focus();
        }
    }
    
    async handleSubmit() {
        this.clearError();
        
        const collection = this.collectionSelect.value;
        const abbreviation = this.abbreviationInput.value.trim();
        const provision = this.provisionInput.value.trim();
        
        if (!abbreviation) {
            this.showError('Bitte geben Sie eine Abkürzung, einen Kurztitel oder eine Ordnungsnummer ein');
            return;
        }
        
        // If ordnungsnummer was stored from selection, use that directly
        let ordnungsnummer = this.abbreviationInput.dataset.ordnungsnummer;
        let law = null;
        
        if (ordnungsnummer) {
            // Find law by ordnungsnummer
            law = this.lawsIndex.find(l => 
                l.collection === collection && l.ordnungsnummer === ordnungsnummer
            );
        } else {
            // Parse the input to find the law
            const input = abbreviation.toLowerCase().trim();
            
            // First try exact match on any field
            law = this.lawsIndex.find(l => {
                if (l.collection !== collection) return false;
                const abbr = (l.abbreviation || '').toLowerCase();
                const ord = l.ordnungsnummer.toLowerCase();
                const kurz = (l.kurztitel || '').toLowerCase();
                
                // Exact match on any single field
                return abbr === input || ord === input || kurz === input;
            });
            
            // If no exact match, try partial match
            if (!law) {
                law = this.lawsIndex.find(l => {
                    if (l.collection !== collection) return false;
                    const abbr = (l.abbreviation || '').toLowerCase();
                    const ord = l.ordnungsnummer.toLowerCase();
                    const kurz = (l.kurztitel || '').toLowerCase();
                    const title = (l.title || '').toLowerCase();
                    
                    // For formatted display (contains ∗ separator)
                    if (input.includes('∗')) {
                        return input.includes(abbr) || input.includes(ord) || input.includes(kurz);
                    }
                    
                    // Otherwise check if any field starts with the input
                    return abbr.startsWith(input) || ord.startsWith(input) || 
                           kurz.startsWith(input) || title.includes(input);
                });
            }
        }
        
        if (!law) {
            this.showError('Erlass nicht gefunden');
            return;
        }
        
        // Use the ordnungsnummer from the found law
        ordnungsnummer = ordnungsnummer || law.ordnungsnummer;
        
        // If no provision specified, redirect to the latest version
        if (!provision) {
            // Use the unified redirect to get the latest version
            window.location.href = `/col-${collection}/${ordnungsnummer}`;
            this.close();
            return;
        }
        
        try {
            // Load the specific anchor map for this law
            const anchorMapPath = `/anchor-maps/${collection}/${ordnungsnummer}-map.json`;
            const response = await fetch(anchorMapPath);
            
            if (!response.ok) {
                throw new Error('Anchor map not found');
            }
            
            const anchorMap = await response.json();
            
            // Parse provision number (handle formats like "1", "1a", "10.2", etc.)
            const provisionMatch = provision.match(/^(\d+)([a-z]?)(?:\.(\d+))?$/i);
            
            if (!provisionMatch) {
                this.showError('Ungültiges Bestimmungsformat');
                return;
            }
            
            const mainProvision = provisionMatch[1] + (provisionMatch[2] || '').toLowerCase();
            const subProvision = provisionMatch[3];
            
            // Check if provision exists in anchor map
            const provisionData = anchorMap.provisions[mainProvision];
            
            // Get the latest version from anchor map metadata
            const latestVersion = anchorMap.metadata?.latest_version || '0';
            
            if (latestVersion === '0') {
                this.showError('Fehler: Keine Version gefunden');
                return;
            }
            
            if (!provisionData) {
                // Provision doesn't exist, navigate with warning
                // Store law metadata in sessionStorage for the warning
                const lawMetadata = {
                    provision_type: anchorMap.metadata?.provision_type || '§',
                    title: law?.title || anchorMap.metadata?.title || ''
                };
                sessionStorage.setItem('quickSelectLawMetadata', JSON.stringify(lawMetadata));
                
                const url = `/col-${collection}/${ordnungsnummer}-${latestVersion}.html?redirected=true&anchor_missing=true#seq-0-prov-${mainProvision}`;
                window.location.href = url;
                this.close();
                return;
            }
            
            // Check if subprovision exists (if specified)
            if (subProvision && (!provisionData.subprovisions || 
                                !provisionData.subprovisions[subProvision] || 
                                !provisionData.subprovisions[subProvision].sequences)) {
                // Subprovision doesn't exist, navigate to main provision with warning
                // Store law metadata in sessionStorage for the warning
                const lawMetadata = {
                    provision_type: anchorMap.metadata?.provision_type || '§',
                    title: law?.title || anchorMap.metadata?.title || ''
                };
                sessionStorage.setItem('quickSelectLawMetadata', JSON.stringify(lawMetadata));
                
                const url = `/col-${collection}/${ordnungsnummer}-${latestVersion}.html?redirected=true&anchor_missing=true#seq-0-prov-${mainProvision}-sub-${subProvision}`;
                window.location.href = url;
                this.close();
                return;
            }
            
            // Build URL to the specific version with anchor
            // Always use seq-0 to navigate to the first instance of the provision
            let anchor = `#seq-0-prov-${mainProvision}`;
            if (subProvision) {
                anchor += `-sub-${subProvision}`;
            }
            
            const url = `/col-${collection}/${ordnungsnummer}-${latestVersion}.html${anchor}`;
            
            // Navigate to the URL
            window.location.href = url;
            this.close();
            
        } catch (error) {
            console.error('Error loading anchor map:', error);
            this.showError('Fehler beim Laden der Gesetzesdaten');
        }
    }
    
    showError(message) {
        this.errorDiv.textContent = message;
        this.errorDiv.style.display = 'block';
    }
    
    clearError() {
        this.errorDiv.style.display = 'none';
    }
    
    open() {
        if (this.isOpen) return;
        
        this.isOpen = true;
        this.modal.style.display = 'flex';
        document.body.classList.add('search-modal-open'); // Reuse the class from search modal
        document.documentElement.classList.add('search-modal-open');
        
        // Reset form
        this.collectionSelect.value = 'zh';
        this.abbreviationInput.value = '';
        this.abbreviationInput.dataset.ordnungsnummer = '';
        this.abbreviationInput.dataset.abbreviation = '';
        this.abbreviationInput.dataset.kurztitel = '';
        this.provisionInput.value = '';
        this.clearError();
        this.hideAutocomplete();
        
        // Focus first field
        setTimeout(() => {
            this.abbreviationInput.focus();
        }, 100);
    }
    
    close() {
        if (!this.isOpen) return;
        
        this.isOpen = false;
        this.modal.style.display = 'none';
        document.body.classList.remove('search-modal-open');
        document.documentElement.classList.remove('search-modal-open');
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }
    
    // Parse anchor ID to extract provision and subprovision numbers
    parseAnchorId(anchorId) {
        const match = anchorId.match(/seq-\d+-prov-(\d+[a-z]?)(?:-sub-(\d+))?/);
        if (match) {
            return {
                provision: match[1],
                subprovision: match[2] || null
            };
        }
        return null;
    }
    
    // Generate human-readable reference for warnings
    generateHumanReference(provision, subprovision, law) {
        const provType = law?.provision_type || '§';
        const title = law?.title || '';
        
        let reference = `${provType} ${provision}`;
        if (subprovision) {
            reference += ` Abs. ${subprovision}`;
        }
        if (title) {
            reference += ` ${title}`;
        }
        
        return reference;
    }
    
    // Note: showMissingAnchorWarning method removed
    // Warning display is now handled exclusively by anchor-tooltip.js
    // This prevents duplicate warnings when using quick-select
    
    // Note: checkForMissingAnchorWarning method removed
    // Warning display is now handled exclusively by anchor-tooltip.js
    // This prevents duplicate warnings when using quick-select
    
    addTooltip() {
        let tooltip = null;
        let tooltipTimer = null;
        
        const showTooltip = () => {
            // Only show on larger screens
            if (window.innerWidth <= 768) return;
            
            // Clear any existing timer
            if (tooltipTimer) {
                clearTimeout(tooltipTimer);
            }
            
            // Remove existing tooltip
            if (tooltip) {
                tooltip.remove();
                tooltip = null;
            }
            
            // Create new tooltip
            tooltip = document.createElement('div');
            tooltip.className = 'button-tooltip button-tooltip-below';
            tooltip.textContent = 'Shortcut: "Q"';
            document.body.appendChild(tooltip);
            
            // Position tooltip below button (centered)
            const buttonRect = this.button.getBoundingClientRect();
            
            // Set initial position to measure tooltip width
            tooltip.style.visibility = 'hidden';
            tooltip.style.position = 'fixed';
            tooltip.style.left = '0px';
            tooltip.style.top = '0px';
            
            // Force reflow to ensure tooltip is rendered
            tooltip.offsetHeight;
            
            // Get tooltip dimensions after rendering
            const tooltipRect = tooltip.getBoundingClientRect();
            
            // Calculate centered position
            const centerX = buttonRect.left + (buttonRect.width / 2);
            const tooltipX = centerX - (tooltipRect.width / 2);
            const tooltipY = buttonRect.bottom + 4;
            
            // Debug logging (can be removed later)
            console.log('Quick Select Tooltip Positioning:', {
                buttonRect: { left: buttonRect.left, width: buttonRect.width, bottom: buttonRect.bottom },
                tooltipRect: { width: tooltipRect.width, height: tooltipRect.height },
                centerX,
                tooltipX,
                tooltipY
            });
            
            // Apply final position and make visible
            tooltip.style.left = Math.round(tooltipX) + 'px';
            tooltip.style.top = Math.round(tooltipY) + 'px';
            tooltip.style.visibility = 'visible';
        };
        
        const hideTooltip = (immediate = false) => {
            if (tooltipTimer) {
                clearTimeout(tooltipTimer);
            }
            
            if (immediate) {
                if (tooltip) {
                    tooltip.remove();
                    tooltip = null;
                }
            } else {
                tooltipTimer = setTimeout(() => {
                    if (tooltip) {
                        tooltip.remove();
                        tooltip = null;
                    }
                }, 100);
            }
        };
        
        // Add event listeners
        this.button.addEventListener('mouseenter', showTooltip);
        this.button.addEventListener('mouseleave', () => hideTooltip(false));
        this.button.addEventListener('focus', showTooltip);
        this.button.addEventListener('blur', () => hideTooltip(false));
        
        // Hide tooltip immediately on various navigation events
        window.addEventListener('resize', () => hideTooltip(true));
        window.addEventListener('scroll', () => hideTooltip(true));
        window.addEventListener('beforeunload', () => hideTooltip(true));
        document.addEventListener('click', (e) => {
            if (!this.button.contains(e.target)) {
                hideTooltip(true);
            }
        });
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => new QuickSelect());
} else {
    new QuickSelect();
}
