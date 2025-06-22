/**
 * Provision Jump Functionality
 * Allows quick navigation to specific provisions within the currently open law
 */

class ProvisionJump {
    constructor() {
        this.container = null;
        this.button = null;
        this.modal = null;
        this.isOpen = false;
        this.currentLawInfo = null;
        this.anchorMap = null;
        
        this.init();
    }
    
    init() {
        // Only initialize if we're on a law page
        if (!this.detectLawPage()) {
            return;
        }
        
        this.extractCurrentLawInfo();
        this.findExistingButton();
        this.createModal();
        this.loadAnchorMap();
        this.attachEventListeners();
    }
    
    detectLawPage() {
        // Check if we're on a law page by looking for the law container
        return document.getElementById('law') !== null;
    }
    
    extractCurrentLawInfo() {
        // Extract from URL pattern: /col-{collection}/{ordnungsnummer}-{version}.html
        const pathMatch = window.location.pathname.match(/\/(col-[^\/]+)\/([^-]+)-(\d+)\.html/);
        if (pathMatch) {
            this.currentLawInfo = {
                collection: pathMatch[1].replace('col-', ''),
                ordnungsnummer: pathMatch[2],
                version: pathMatch[3]
            };
            return;
        }
        
        // Fallback: Extract from DOM attributes
        const lawElement = document.getElementById('law');
        if (lawElement) {
            this.currentLawInfo = {
                collection: 'zh', // Default to zh if not found
                ordnungsnummer: lawElement.getAttribute('data-ordnungsnummer'),
                version: lawElement.getAttribute('data-nachtragsnummer')
            };
        }
    }
    
    findExistingButton() {
        // Find the existing provision jump button that was added by the server
        this.button = document.getElementById('provision_jump');
        if (!this.button) {
            console.warn('Provision jump button not found');
            return;
        }
        
        // Add click handler to existing button
        this.button.addEventListener('click', () => this.open());
    }
    
    createModal() {
        this.modal = document.createElement('div');
        this.modal.className = 'provision-jump-modal';
        this.modal.innerHTML = `
            <div class="provision-jump-modal-content">
                <form class="provision-jump-form">
                    <div class="provision-jump-field-group">
                        <label for="provision-jump-input" class="provision-jump-label">Bestimmung</label>
                        <input type="text" id="provision-jump-input" class="provision-jump-input" 
                               placeholder="z.B. 1 oder 10a oder 2.3" maxlength="8" autocomplete="off">
                    </div>
                    <button type="submit" class="provision-jump-submit">Zur Bestimmung springen</button>
                    <div class="provision-jump-error" id="provision-jump-error" style="display: none;">
                        Bestimmung nicht gefunden
                    </div>
                    <div class="provision-jump-loading" id="provision-jump-loading" style="display: none;">
                        Lade Gesetzesdaten...
                    </div>
                </form>
            </div>
        `;
        
        document.body.appendChild(this.modal);
        
        // Cache DOM elements
        this.form = this.modal.querySelector('.provision-jump-form');
        this.input = this.modal.querySelector('#provision-jump-input');
        this.submitBtn = this.modal.querySelector('.provision-jump-submit');
        this.errorDiv = this.modal.querySelector('#provision-jump-error');
        this.loadingDiv = this.modal.querySelector('#provision-jump-loading');
    }
    
    async loadAnchorMap() {
        if (!this.currentLawInfo) {
            console.warn('No current law info available');
            return;
        }
        
        try {
            const anchorMapPath = `/anchor-maps/${this.currentLawInfo.collection}/${this.currentLawInfo.ordnungsnummer}-map.json`;
            const response = await fetch(anchorMapPath);
            
            if (!response.ok) {
                console.warn('Failed to load anchor map');
                return;
            }
            
            this.anchorMap = await response.json();
            
            // Hide loading message
            if (this.loadingDiv) {
                this.loadingDiv.style.display = 'none';
            }
        } catch (error) {
            console.error('Error loading anchor map:', error);
            if (this.loadingDiv) {
                this.loadingDiv.textContent = 'Fehler beim Laden der Gesetzesdaten';
            }
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
        
        // Open on 'G' key (when not in input)
        document.addEventListener('keydown', (e) => {
            const isInputFocused = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName);
            if ((e.key === 'g' || e.key === 'G') && !isInputFocused && !this.isOpen) {
                e.preventDefault();
                this.open();
            }
        });
        
        // Form submission
        this.form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleSubmit();
        });
        
        // Clear error on input
        this.input.addEventListener('input', () => this.clearError());
        
        // Restrict input to alphanumeric characters and dots
        this.input.addEventListener('input', (e) => {
            const value = e.target.value;
            const cleanedValue = value.replace(/[^a-zA-Z0-9.]/g, '');
            if (value !== cleanedValue) {
                e.target.value = cleanedValue;
            }
        });
    }
    
    validateProvision(provision, subprovision = null) {
        if (!this.anchorMap?.provisions) {
            // If no anchor map, check if anchor exists in current page DOM
            return this.checkProvisionExistsInPage(provision, subprovision);
        }
        
        const provisionData = this.anchorMap.provisions[provision];
        if (!provisionData) {
            return false;
        }
        
        if (subprovision) {
            return provisionData.subprovisions?.[subprovision]?.sequences > 0;
        }
        
        return provisionData.sequences > 0;
    }
    
    checkProvisionExistsInPage(provision, subprovision = null) {
        let anchorId = `seq-0-prov-${provision}`;
        if (subprovision) {
            anchorId += `-sub-${subprovision}`;
        }
        return document.getElementById(anchorId) !== null;
    }
    
    parseProvisionInput(input) {
        // Handle formats like "1", "1a", "10.2", "2a.3", etc.
        const match = input.match(/^(\d+[a-z]?)(?:\.(\d+))?$/i);
        
        if (!match) {
            return null;
        }
        
        return {
            provision: match[1].toLowerCase(),
            subprovision: match[2] || null
        };
    }
    
    handleSubmit() {
        this.clearError();
        
        const inputValue = this.input.value.trim();
        if (!inputValue) {
            this.showError('Bitte geben Sie eine Bestimmung ein');
            return;
        }
        
        const parsed = this.parseProvisionInput(inputValue);
        if (!parsed) {
            this.showError('Ungültiges Bestimmungsformat');
            return;
        }
        
        const { provision, subprovision } = parsed;
        
        // Validate provision exists
        if (!this.validateProvision(provision, subprovision)) {
            this.showError('Bestimmung nicht gefunden');
            return;
        }
        
        // Navigate to provision
        this.navigateToProvision(provision, subprovision);
        this.close();
    }
    
    navigateToProvision(provision, subprovision = null) {
        let anchor = `#seq-0-prov-${provision}`;
        if (subprovision) {
            anchor += `-sub-${subprovision}`;
        }
        
        // Update URL hash - this will automatically scroll to the element
        window.location.hash = anchor;
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
        this.input.value = '';
        this.clearError();
        
        // Focus input
        setTimeout(() => {
            this.input.focus();
        }, 100);
    }
    
    close() {
        if (!this.isOpen) return;
        
        this.isOpen = false;
        this.modal.style.display = 'none';
        document.body.classList.remove('search-modal-open');
        document.documentElement.classList.remove('search-modal-open');
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => new ProvisionJump());
} else {
    new ProvisionJump();
}