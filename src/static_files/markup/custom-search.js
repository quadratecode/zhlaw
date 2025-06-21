/**
 * Custom Pagefind Search Implementation
 * Displays search results with provision anchors as sub-results
 */

class CustomSearch {
    constructor() {
        this.pagefind = null;
        this.searchInput = null;
        this.resultsContainer = null;
        this.loadingIndicator = null;
        this.noResultsMessage = null;
        this.searchContainer = null;
        this.currentSearchTerm = '';
        this.currentSearchResults = [];
        this.displayedResults = 0;
        this.resultsPerPage = 20;
        this.debounceTimer = null;
        this.availableFilters = null;
        this.selectedFilters = {};
        this.isExpanded = false;
        this.statusFilter = 'all'; // 'all', 'in_force', 'not_in_force'
        this.modalOpen = false;
        this.searchButton = null;
        this.searchModal = null;
        this.clearButton = null;
        this.translations = {
            placeholder: "Gesetzessammlungen durchsuchen",
            zero_results: "Keine Treffer für",
            loading: "Suche läuft...",
            error: "Fehler bei der Suche",
            show_more: "Weitere Treffer anzeigen",
            filter_all: "Alle",
            filter_in_force: "In Kraft",
            filter_not_in_force: "Nicht in Kraft",
            collection_all: "Alle Sammlungen"
        };
    }

    /**
     * Initialize the search interface
     */
    async init() {
        this.setupDOM();
        this.bindEvents();
    }

    /**
     * Create and setup DOM elements
     */
    setupDOM() {
        // Get the search container
        this.searchContainer = document.getElementById('search');
        if (!this.searchContainer) return;

        // Create the search button
        this.searchContainer.innerHTML = `
            <button class="search-button" aria-label="Suche öffnen">
                <svg class="search-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="11" cy="11" r="8"></circle>
                    <path d="m21 21-4.35-4.35"></path>
                </svg>
                <span class="search-button-text">
                    Volltextsuche
                </span>
            </button>
        `;

        // Create the modal
        const modal = document.createElement('div');
        modal.className = 'search-modal';
        modal.style.display = 'none';
        modal.innerHTML = `
            <div class="search-modal-content">
                <div class="custom-search-input-wrapper">
                    <input type="search" 
                           class="pagefind-ui__search-input custom-search-input" 
                           placeholder="${this.translations.placeholder}"
                           autocomplete="off"
                           aria-label="Suche">
                    <button class="custom-search-clear" aria-label="Eingabe löschen">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <line x1="18" y1="6" x2="6" y2="18"></line>
                            <line x1="6" y1="6" x2="18" y2="18"></line>
                        </svg>
                    </button>
                </div>
                <div class="custom-search-filters">
                    <div class="status-filter-group" role="group" aria-label="Status Filter">
                        <button class="status-filter-btn active" data-filter="all">${this.translations.filter_all}</button>
                        <button class="status-filter-btn" data-filter="in_force">${this.translations.filter_in_force}</button>
                        <button class="status-filter-btn" data-filter="not_in_force">${this.translations.filter_not_in_force}</button>
                    </div>
                    <div class="collection-filter-wrapper">
                        <select class="collection-filter" aria-label="Sammlung auswählen">
                            <option value="">${this.translations.collection_all}</option>
                        </select>
                    </div>
                </div>
                <div class="custom-search-results">
                    <div class="custom-search-loading" style="display: none;">
                        ${this.translations.loading}
                    </div>
                    <div class="custom-search-no-results" style="display: none;">
                        <span class="no-results-text"></span>
                    </div>
                    <div class="custom-search-results-list"></div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        this.searchModal = modal;

        // Get references to elements
        this.searchButton = this.searchContainer.querySelector('.search-button');
        
        // Add tooltip functionality
        this.addTooltip();
        this.searchInput = modal.querySelector('.custom-search-input');
        this.clearButton = modal.querySelector('.custom-search-clear');
        this.dropdown = modal.querySelector('.search-modal-content');
        this.filtersContainer = modal.querySelector('.custom-search-filters');
        this.resultsContainer = modal.querySelector('.custom-search-results');
        this.loadingIndicator = modal.querySelector('.custom-search-loading');
        this.noResultsMessage = modal.querySelector('.custom-search-no-results');
        this.resultsListContainer = modal.querySelector('.custom-search-results-list');
        this.collectionFilter = modal.querySelector('.collection-filter');
        this.statusFilterButtons = modal.querySelectorAll('.status-filter-btn');
    }

    /**
     * Bind event handlers
     */
    bindEvents() {
        // Open modal on button click
        this.searchButton.addEventListener('click', () => this.openModal());

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Open modal with S or /
            if ((e.key === 's' || e.key === 'S' || e.key === '/') && !this.modalOpen) {
                // Don't trigger if user is typing in an input
                if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
                    e.preventDefault();
                    this.openModal();
                }
            }
            // Close modal with Escape
            if (e.key === 'Escape' && this.modalOpen) {
                this.closeModal();
            }
        });

        // Handle search input with debouncing
        this.searchInput.addEventListener('input', (e) => this.handleSearchInput(e));

        // Clear button
        this.clearButton.addEventListener('click', (e) => {
            e.stopPropagation();
            this.clearSearch();
        });

        // Close on backdrop click
        this.searchModal.addEventListener('click', (e) => {
            if (e.target === this.searchModal) {
                this.closeModal();
            }
        });

        // Status filter buttons
        this.statusFilterButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                this.statusFilterButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.statusFilter = btn.dataset.filter;
                if (this.currentSearchTerm) {
                    this.performSearch(this.currentSearchTerm);
                }
            });
        });

        // Collection filter
        this.collectionFilter.addEventListener('change', () => {
            this.handleFilterChange();
        });
    }

    /**
     * Initialize Pagefind library and load filters
     */
    async initPagefind() {
        if (this.pagefind) return;

        try {
            this.pagefind = await import('/pagefind/pagefind.js');
            await this.pagefind.options({
                ranking: {
                    termFrequency: 0.0,
                    termSaturation: 1.6,
                    termSimilarity: 2.0,
                }
            });
            await this.pagefind.init();
            
            // Load available filters
            await this.loadFilters();
        } catch (error) {
            console.error('Failed to initialize Pagefind:', error);
        }
    }
    
    /**
     * Load available filters from Pagefind
     */
    async loadFilters() {
        try {
            this.availableFilters = await this.pagefind.filters();
            this.populateFilterUI();
        } catch (error) {
            console.error('Failed to load filters:', error);
        }
    }
    
    /**
     * Populate filter UI based on available filters
     */
    populateFilterUI() {
        if (!this.availableFilters || !this.availableFilters['Gesetzessammlung']) return;
        
        // Populate collection dropdown
        let options = `<option value="">${this.translations.collection_all}</option>`;
        for (const [value] of Object.entries(this.availableFilters['Gesetzessammlung'])) {
            options += `<option value="${value}">${value}</option>`;
        }
        this.collectionFilter.innerHTML = options;
    }

    /**
     * Handle search input changes with debouncing
     */
    handleSearchInput(event) {
        const searchTerm = event.target.value.trim();
        
        // Show/hide clear button
        this.clearButton.style.display = searchTerm ? 'flex' : 'none';
        
        // Clear existing timer
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }

        // Hide results if search is empty
        if (!searchTerm) {
            this.resultsContainer.style.display = 'none';
            return;
        }

        // Show results container and loading state
        this.resultsContainer.style.display = 'block';
        this.showLoading();

        // Debounce the search
        this.debounceTimer = setTimeout(() => {
            this.performSearch(searchTerm);
        }, 300);
    }
    
    /**
     * Handle filter changes
     */
    handleFilterChange() {
        // Collect current filter selections
        this.selectedFilters = {};
        
        // Add collection filter if selected
        if (this.collectionFilter.value) {
            this.selectedFilters['Gesetzessammlung'] = this.collectionFilter.value;
        }
        
        // Re-run search if we have a search term
        if (this.currentSearchTerm) {
            this.performSearch(this.currentSearchTerm);
        }
    }

    /**
     * Perform the search
     */
    async performSearch(searchTerm) {
        if (!this.pagefind) {
            await this.initPagefind();
        }

        this.currentSearchTerm = searchTerm;
        this.currentSearchResults = [];
        this.displayedResults = 0;

        try {
            // Build search options with filters
            const searchOptions = {};
            
            // Add collection filter
            if (Object.keys(this.selectedFilters).length > 0) {
                searchOptions.filters = this.selectedFilters;
            }
            
            // Add status filter via the "Text in Kraft" field
            if (this.statusFilter === 'in_force') {
                searchOptions.filters = { ...searchOptions.filters, 'Text in Kraft': 'Ja' };
            } else if (this.statusFilter === 'not_in_force') {
                searchOptions.filters = { ...searchOptions.filters, 'Text in Kraft': 'Nein' };
            }
            
            const search = await this.pagefind.search(searchTerm, searchOptions);

            if (search.results.length === 0) {
                this.showNoResults(searchTerm);
            } else {
                // Load full data for all results
                const fullResults = await Promise.all(
                    search.results.map(r => r.data())
                );
                
                // Sort results: exact matches in title/abbreviation first
                this.currentSearchResults = this.prioritizeResults(fullResults, searchTerm);
                
                // Update filter counts if available
                if (search.filters) {
                    this.updateFilterCounts(search.filters);
                }
                
                // Render first batch
                this.renderInitialResults();
            }
        } catch (error) {
            console.error('Search failed:', error);
            this.showError();
        }
    }

    /**
     * Update filter counts in the UI
     */
    updateFilterCounts(filterCounts) {
        // Update collection dropdown with result counts
        if (this.collectionFilter && filterCounts['Gesetzessammlung']) {
            const currentValue = this.collectionFilter.value;
            let options = `<option value="">${this.translations.collection_all}</option>`;
            
            // Get all available collections from the initial load
            const allCollections = this.availableFilters['Gesetzessammlung'] || {};
            
            for (const [value] of Object.entries(allCollections)) {
                const currentCount = filterCounts['Gesetzessammlung'][value] || 0;
                const selected = value === currentValue ? 'selected' : '';
                const disabled = currentCount === 0 ? 'disabled' : '';
                options += `<option value="${value}" ${selected} ${disabled}>${value} (${currentCount})</option>`;
            }
            
            this.collectionFilter.innerHTML = options;
        }
    }

    /**
     * Prioritize results with exact matches in title or abbreviation
     */
    prioritizeResults(results, searchTerm) {
        const searchLower = searchTerm.toLowerCase();
        
        return results.sort((a, b) => {
            // Check title matches
            const aTitleMatch = (a.meta.title || '').toLowerCase().includes(searchLower);
            const bTitleMatch = (b.meta.title || '').toLowerCase().includes(searchLower);
            
            // Extract abbreviation from content - it's marked with high weight
            // Look for pattern like "Abkürzung:</div><div...>IDG</div>"
            const aAbbrMatch = this.extractAbbreviation(a, searchLower);
            const bAbbrMatch = this.extractAbbreviation(b, searchLower);
            
            // Exact abbreviation match gets highest priority
            if (aAbbrMatch && !bAbbrMatch) return -1;
            if (!aAbbrMatch && bAbbrMatch) return 1;
            
            // Title match gets second priority
            if (aTitleMatch && !bTitleMatch) return -1;
            if (!aTitleMatch && bTitleMatch) return 1;
            
            // Otherwise maintain original order (relevance-based)
            return 0;
        });
    }

    /**
     * Extract and check abbreviation from result content
     */
    extractAbbreviation(result, searchTerm) {
        // Look for abbreviation in the content using regex
        const abbrPattern = /Abkürzung:<\/div><div[^>]*data-pagefind-weight="10"[^>]*>([^<]+)<\/div>/;
        const match = result.content.match(abbrPattern);
        if (match && match[1]) {
            const abbreviation = match[1].trim();
            return abbreviation.toLowerCase() === searchTerm;
        }
        return false;
    }

    /**
     * Render initial batch of results
     */
    renderInitialResults() {
        this.resultsListContainer.innerHTML = '';
        this.displayedResults = 0;
        this.renderMoreResults();
    }

    /**
     * Render more results
     */
    renderMoreResults() {
        const startIndex = this.displayedResults;
        const endIndex = Math.min(startIndex + this.resultsPerPage, this.currentSearchResults.length);
        
        const resultsToRender = this.currentSearchResults.slice(startIndex, endIndex);
        
        resultsToRender.forEach(result => {
            const resultElement = this.createResultElement(result);
            this.resultsListContainer.appendChild(resultElement);
        });
        
        this.displayedResults = endIndex;
        
        // Remove existing load more button if any
        const existingButton = this.resultsContainer.querySelector('.load-more-button');
        if (existingButton) {
            existingButton.remove();
        }
        
        // Add load more button if there are more results
        if (this.displayedResults < this.currentSearchResults.length) {
            const loadMoreButton = document.createElement('button');
            loadMoreButton.className = 'load-more-button';
            loadMoreButton.textContent = `${this.translations.show_more} (${this.currentSearchResults.length - this.displayedResults})`;
            loadMoreButton.addEventListener('click', () => this.renderMoreResults());
            this.resultsContainer.appendChild(loadMoreButton);
        }
        
        this.showResults();
    }

    /**
     * Create a result element with provision sub-results
     */
    createResultElement(result) {
        // Create main link wrapper
        const resultLink = document.createElement('a');
        resultLink.href = result.url;
        resultLink.className = 'custom-search-result';
        
        // Close modal when clicking on result
        resultLink.addEventListener('click', () => {
            this.closeModal();
        });
        
        // Add status indicator class
        // Default to in-force if the field is missing or undefined
        let isInForce = true;
        
        // Check if we have the Text in Kraft filter
        if (result.filters && result.filters['Text in Kraft']) {
            // Handle both array and string cases
            const kraftValue = Array.isArray(result.filters['Text in Kraft']) 
                ? result.filters['Text in Kraft'][0] 
                : result.filters['Text in Kraft'];
            isInForce = kraftValue === 'Ja';
        }
        
        resultLink.classList.add(isInForce ? 'in-force' : 'not-in-force');
        
        // Create header with title and unified status/collection badge
        const headerDiv = document.createElement('div');
        headerDiv.className = 'custom-search-result-header';
        
        // Unified collection badge with status color
        if (result.filters && result.filters['Gesetzessammlung']) {
            const collectionBadge = document.createElement('span');
            collectionBadge.className = 'collection-badge';
            let collection = result.filters['Gesetzessammlung'];
            
            // Handle case where collection might be an array
            if (Array.isArray(collection)) {
                collection = collection[0] || '';
            }
            
            // Convert to string to ensure we can call string methods
            collection = String(collection);
            
            // Determine badge text based on collection
            let badgeText = '';
            if (collection.includes('Zürich') || collection.includes('Zurich')) {
                badgeText = 'ZH';
                collectionBadge.classList.add('collection-zh');
            } else if (collection.includes('Bund') || collection.includes('CH')) {
                badgeText = 'CH';
                collectionBadge.classList.add('collection-ch');
            } else if (collection.length > 0) {
                // Fallback for other collections
                badgeText = collection.substring(0, 2).toUpperCase();
            } else {
                // If no valid collection string, use a generic badge
                badgeText = '??';
            }
            
            collectionBadge.textContent = badgeText;
            
            // Add status class for color coding
            if (isInForce) {
                collectionBadge.classList.add('in-force');
                collectionBadge.setAttribute('aria-label', `${badgeText} - In Kraft`);
            } else {
                collectionBadge.classList.add('not-in-force');
                collectionBadge.setAttribute('aria-label', `${badgeText} - Nicht in Kraft`);
            }
            
            headerDiv.appendChild(collectionBadge);
        }
        
        // Main result title
        const mainTitle = document.createElement('span');
        mainTitle.className = 'custom-search-result-title';
        mainTitle.textContent = result.meta.title || 'Untitled';
        headerDiv.appendChild(mainTitle);
        
        resultLink.appendChild(headerDiv);

        // Generate provision sub-results
        const subResults = this.generateProvisionSubResults(result);
        
        if (subResults.length > 0) {
            const subResultsContainer = document.createElement('div');
            subResultsContainer.className = 'custom-search-sub-results';
            
            // Limit to 4 sub-results
            const displayedSubResults = subResults.slice(0, 4);
            const remainingCount = subResults.length - displayedSubResults.length;
            
            displayedSubResults.forEach(subResult => {
                const subLink = document.createElement('a');
                subLink.href = subResult.url;
                subLink.className = 'custom-search-sub-result';
                
                // Close modal when clicking on sub-result
                subLink.addEventListener('click', () => {
                    this.closeModal();
                });
                
                const provisionSpan = document.createElement('span');
                provisionSpan.className = 'provision-number';
                provisionSpan.textContent = subResult.title;
                
                const excerptSpan = document.createElement('span');
                excerptSpan.className = 'provision-excerpt';
                excerptSpan.innerHTML = subResult.excerpt;
                
                subLink.appendChild(provisionSpan);
                subLink.appendChild(excerptSpan);
                subResultsContainer.appendChild(subLink);
            });
            
            // Add "weitere Bestimmungen" text if there are more results
            if (remainingCount > 0) {
                const moreResultsDiv = document.createElement('div');
                moreResultsDiv.className = 'custom-search-more-provisions';
                moreResultsDiv.textContent = `und ${remainingCount} weitere Bestimmung${remainingCount > 1 ? 'en' : ''}...`;
                subResultsContainer.appendChild(moreResultsDiv);
            }
            
            resultLink.appendChild(subResultsContainer);
        } else {
            // Show main excerpt if no provision matches
            const excerpt = document.createElement('div');
            excerpt.className = 'custom-search-excerpt';
            // Remove footnote references from excerpt
            let cleanExcerpt = result.excerpt.replace(/\[\d+\]/g, '');
            excerpt.innerHTML = cleanExcerpt;
            resultLink.appendChild(excerpt);
        }

        return resultLink;
    }

    /**
     * Generate provision-based sub-results from anchors and locations
     */
    generateProvisionSubResults(result) {
        if (!result.anchors || !result.locations || result.locations.length === 0) {
            return [];
        }

        // Filter anchors to only include main provisions (exclude subprovisions)
        const provisionAnchors = result.anchors.filter(anchor => {
            return anchor.id && anchor.id.match(/seq-\d+-prov-[\d\w]+$/) && !anchor.id.includes('-sub-');
        });

        if (provisionAnchors.length === 0) {
            return [];
        }

        // Sort anchors by location
        provisionAnchors.sort((a, b) => a.location - b.location);

        // Map search hits to provisions
        const provisionHits = [];
        const contentWords = result.content.split(/\s+/);

        provisionAnchors.forEach((anchor, index) => {
            const startLocation = anchor.location;
            const endLocation = (index + 1 < provisionAnchors.length) 
                ? provisionAnchors[index + 1].location 
                : result.content.length;

            // Find hits within this provision's range
            const hits = result.locations.filter(loc => 
                loc >= startLocation && loc < endLocation
            );

            if (hits.length > 0) {
                // Extract provision number from anchor text or ID
                let provisionTitle = this.extractProvisionTitle(anchor);
                
                // Generate excerpt around first hit
                const excerpt = this.generateExcerpt(contentWords, hits, this.currentSearchTerm);
                
                provisionHits.push({
                    title: provisionTitle,
                    url: `${result.url}#${anchor.id}`,
                    excerpt: excerpt,
                    hitCount: hits.length,
                    anchorId: anchor.id
                });
            }
        });

        // Sort by natural provision order (not by hit count)
        return provisionHits.sort((a, b) => {
            return this.compareProvisions(a.title, b.title);
        });
    }

    /**
     * Extract a readable provision title from anchor
     */
    extractProvisionTitle(anchor) {
        // Try to use anchor text first
        if (anchor.text && anchor.text.trim()) {
            const text = anchor.text.trim();
            
            // Check if this is already a well-formatted provision (e.g., "§ 1." or "Art. 2")
            if (text.match(/^(§|Art\.|art\.)\s*\d+/)) {
                return text;
            }
            
            return text;
        }
        
        // Fallback: parse from ID
        const idMatch = anchor.id.match(/prov-([\d\w]+)$/);
        if (idMatch) {
            const prov = idMatch[1];
            return `§ ${prov}`;
        }
        
        return 'Provision';
    }

    /**
     * Compare two provision titles for natural sorting
     */
    compareProvisions(a, b) {
        // Extract numbers and letters from provision titles
        const parseProvision = (title) => {
            const match = title.match(/(?:§|Art\.|art\.)\s*(\d+)([a-zA-Z]*)/);
            if (match) {
                return {
                    number: parseInt(match[1], 10),
                    letter: match[2] || ''
                };
            }
            // Try to extract just numbers
            const numberMatch = title.match(/(\d+)([a-zA-Z]*)/);
            if (numberMatch) {
                return {
                    number: parseInt(numberMatch[1], 10),
                    letter: numberMatch[2] || ''
                };
            }
            return { number: 0, letter: title };
        };

        const provA = parseProvision(a);
        const provB = parseProvision(b);

        // Compare numbers first
        if (provA.number !== provB.number) {
            return provA.number - provB.number;
        }

        // If numbers are equal, compare letters
        return provA.letter.localeCompare(provB.letter);
    }

    /**
     * Generate excerpt with highlighted search terms
     */
    generateExcerpt(words, hitLocations, searchTerm) {
        if (!hitLocations.length) return '';

        const excerptLength = 20;
        const firstHit = hitLocations[0];
        const start = Math.max(0, firstHit - Math.floor(excerptLength / 2));
        const end = Math.min(words.length, start + excerptLength);

        let excerpt = words.slice(start, end).join(' ');

        // Remove footnote references (e.g., [1], [2], etc.)
        excerpt = excerpt.replace(/\[\d+\]/g, '');

        // Highlight search terms (case-insensitive)
        const searchWords = searchTerm.toLowerCase().split(/\s+/);
        searchWords.forEach(term => {
            const regex = new RegExp(`\\b(${term}\\w*)\\b`, 'gi');
            excerpt = excerpt.replace(regex, '<mark class="search-highlight">$1</mark>');
        });

        // Add ellipsis if truncated
        if (start > 0) excerpt = '… ' + excerpt;
        if (end < words.length) excerpt = excerpt + ' …';

        return excerpt;
    }

    /**
     * Show/hide UI states
     */
    showLoading() {
        this.resultsContainer.style.display = 'block';
        this.loadingIndicator.style.display = 'block';
        this.noResultsMessage.style.display = 'none';
        this.resultsListContainer.innerHTML = '';
    }

    showResults() {
        this.resultsContainer.style.display = 'block';
        this.loadingIndicator.style.display = 'none';
        this.noResultsMessage.style.display = 'none';
    }

    showNoResults(searchTerm) {
        this.resultsContainer.style.display = 'block';
        this.loadingIndicator.style.display = 'none';
        this.noResultsMessage.style.display = 'block';
        this.noResultsMessage.querySelector('.no-results-text').textContent = 
            `${this.translations.zero_results} "${searchTerm}"`;
        this.resultsListContainer.innerHTML = '';
    }

    showError() {
        this.resultsContainer.style.display = 'block';
        this.loadingIndicator.style.display = 'none';
        this.noResultsMessage.style.display = 'block';
        this.noResultsMessage.querySelector('.no-results-text').textContent = 
            this.translations.error;
        this.resultsListContainer.innerHTML = '';
    }

    /**
     * Open the search modal
     */
    openModal() {
        this.modalOpen = true;
        this.searchModal.style.display = 'flex';
        document.body.classList.add('search-modal-open');
        
        // Focus the search input
        setTimeout(() => {
            this.searchInput.focus();
        }, 100);
        
        // Initialize Pagefind if not already done
        this.initPagefind();
    }

    /**
     * Close the search modal
     */
    closeModal() {
        this.modalOpen = false;
        this.searchModal.style.display = 'none';
        document.body.classList.remove('search-modal-open');
        
        // Clear search
        this.searchInput.value = '';
        this.currentSearchTerm = '';
        this.resultsContainer.style.display = 'none';
        this.clearButton.style.display = 'none';
    }

    /**
     * Clear the search input
     */
    clearSearch() {
        this.searchInput.value = '';
        this.currentSearchTerm = '';
        this.resultsContainer.style.display = 'none';
        this.clearButton.style.display = 'none';
        this.searchInput.focus();
    }
    
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
            tooltip.textContent = 'Shortcut: "S" oder "/"';
            document.body.appendChild(tooltip);
            
            // Position tooltip below button (centered)
            const buttonRect = this.searchButton.getBoundingClientRect();
            
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
            console.log('Search Tooltip Positioning:', {
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
        this.searchButton.addEventListener('mouseenter', showTooltip);
        this.searchButton.addEventListener('mouseleave', () => hideTooltip(false));
        this.searchButton.addEventListener('focus', showTooltip);
        this.searchButton.addEventListener('blur', () => hideTooltip(false));
        
        // Hide tooltip immediately on various navigation events
        window.addEventListener('resize', () => hideTooltip(true));
        window.addEventListener('scroll', () => hideTooltip(true));
        window.addEventListener('beforeunload', () => hideTooltip(true));
        document.addEventListener('click', (e) => {
            if (!this.searchButton.contains(e.target)) {
                hideTooltip(true);
            }
        });
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const customSearch = new CustomSearch();
    customSearch.init();
});
