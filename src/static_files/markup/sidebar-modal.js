/**
 * Sidebar Modal Functionality
 * Handles the floating info button and sidebar modal for mobile screens
 */

(function() {
    'use strict';

    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initSidebarModal);
    } else {
        initSidebarModal();
    }

    function initSidebarModal() {
        const floatingButton = document.getElementById('floating-info-button');
        const sidebarModal = document.getElementById('sidebar-modal');
        const sidebarModalContent = document.querySelector('.sidebar-modal-content');
        const originalSidebar = document.getElementById('sidebar');
        
        if (!floatingButton || !sidebarModal || !sidebarModalContent || !originalSidebar) {
            return; // Elements not found, exit gracefully
        }

        // Clone sidebar content for mobile modal
        let sidebarClone = null;
        
        function createSidebarClone() {
            if (sidebarClone) {
                sidebarClone.remove();
            }
            sidebarClone = originalSidebar.cloneNode(true);
            sidebarClone.id = 'sidebar-clone';
            sidebarModalContent.appendChild(sidebarClone);
        }

        // Initialize clone on first load if on mobile
        if (window.innerWidth <= 768) {
            createSidebarClone();
        }

        // Open sidebar modal
        function openSidebarModal() {
            // Ensure we have fresh sidebar content
            if (!sidebarClone || window.innerWidth <= 768) {
                createSidebarClone();
            }
            
            sidebarModal.style.display = 'flex';
            document.body.classList.add('sidebar-modal-open');
            document.documentElement.classList.add('sidebar-modal-open');
            
            // Trigger the slide-in animation
            requestAnimationFrame(() => {
                sidebarModal.classList.add('active');
            });
            
            // Focus management for accessibility
            const firstFocusableElement = sidebarModalContent.querySelector('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
            if (firstFocusableElement) {
                firstFocusableElement.focus();
            }
        }

        // Close sidebar modal
        function closeSidebarModal() {
            sidebarModal.classList.remove('active');
            
            // Wait for animation to complete before hiding
            setTimeout(() => {
                if (!sidebarModal.classList.contains('active')) {
                    sidebarModal.style.display = 'none';
                    document.body.classList.remove('sidebar-modal-open');
                    document.documentElement.classList.remove('sidebar-modal-open');
                }
            }, 300); // Match CSS transition duration
            
            // Return focus to floating button
            floatingButton.focus();
        }

        // Event listeners
        floatingButton.addEventListener('click', openSidebarModal);

        // Close on overlay click
        sidebarModal.addEventListener('click', function(e) {
            if (e.target === sidebarModal) {
                closeSidebarModal();
            }
        });

        // Close on ESC key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && sidebarModal.classList.contains('active')) {
                closeSidebarModal();
            }
        });

        // Handle focus trapping within modal
        sidebarModal.addEventListener('keydown', function(e) {
            if (e.key === 'Tab' && sidebarModal.classList.contains('active')) {
                const focusableElements = sidebarModalContent.querySelectorAll(
                    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
                );
                const firstElement = focusableElements[0];
                const lastElement = focusableElements[focusableElements.length - 1];

                if (e.shiftKey && document.activeElement === firstElement) {
                    e.preventDefault();
                    lastElement.focus();
                } else if (!e.shiftKey && document.activeElement === lastElement) {
                    e.preventDefault();
                    firstElement.focus();
                }
            }
        });

        // Handle window resize
        window.addEventListener('resize', function() {
            if (window.innerWidth > 768) {
                // Close modal if open
                if (sidebarModal.classList.contains('active')) {
                    closeSidebarModal();
                }
                // Remove clone on desktop
                if (sidebarClone) {
                    sidebarClone.remove();
                    sidebarClone = null;
                }
            } else if (window.innerWidth <= 768 && !sidebarClone) {
                // Create clone for mobile if it doesn't exist
                createSidebarClone();
            }
        });
    }
})();