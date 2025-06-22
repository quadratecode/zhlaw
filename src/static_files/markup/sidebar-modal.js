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

        // Background scrolling is allowed when modal is open
        
        // Touch event variables for swipe detection
        let touchStartX = 0;
        let touchStartY = 0;
        let touchEndX = 0;
        let touchEndY = 0;
        let isDragging = false;

        // Swipe detection functions
        function handleTouchStart(e) {
            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
            isDragging = false;
        }

        function handleTouchMove(e) {
            touchEndX = e.touches[0].clientX;
            touchEndY = e.touches[0].clientY;
            
            const deltaX = touchEndX - touchStartX;
            const deltaY = touchEndY - touchStartY;
            
            // Determine if this is primarily a horizontal gesture
            if (!isDragging && Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > 10) {
                isDragging = true;
            }
            
            // Apply visual feedback during swipe if it's a horizontal gesture
            if (isDragging && deltaX < 0 && Math.abs(deltaX) > 10) {
                // Right-to-left swipe - add slight transform
                const progress = Math.min(Math.abs(deltaX) / 150, 1);
                const translateX = -progress * 30; // Max 30px drag
                sidebarModalContent.style.transform = `translateX(${translateX}px)`;
                sidebarModalContent.style.transition = 'none';
            }
        }

        function handleTouchEnd(e) {
            if (isDragging) {
                const deltaX = touchEndX - touchStartX;
                const deltaY = touchEndY - touchStartY;
                
                // Reset visual feedback
                sidebarModalContent.style.transform = '';
                sidebarModalContent.style.transition = '';
                
                // Check if it's a valid right-to-left swipe
                if (Math.abs(deltaX) > Math.abs(deltaY) && // More horizontal than vertical
                    deltaX < -50 && // At least 50px right-to-left
                    Math.abs(deltaX) > 20) { // Minimum swipe distance
                    closeSidebarModal();
                }
            }
            
            // Reset values
            touchStartX = 0;
            touchStartY = 0;
            touchEndX = 0;
            touchEndY = 0;
            isDragging = false;
        }

        // Open sidebar modal
        function openSidebarModal() {
            // Ensure we have fresh sidebar content
            if (!sidebarClone || window.innerWidth <= 768) {
                createSidebarClone();
            }
            
            sidebarModal.style.display = 'flex';
            
            // Trigger the slide-in animation
            requestAnimationFrame(() => {
                sidebarModal.classList.add('active');
            });
            
            // Focus management for accessibility
            const firstFocusableElement = sidebarModalContent.querySelector('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
            if (firstFocusableElement) {
                firstFocusableElement.focus();
            }
            
            // Add touch event listeners for swipe detection
            sidebarModalContent.addEventListener('touchstart', handleTouchStart, { passive: true });
            sidebarModalContent.addEventListener('touchmove', handleTouchMove, { passive: true });
            sidebarModalContent.addEventListener('touchend', handleTouchEnd, { passive: true });
        }

        // Close sidebar modal
        function closeSidebarModal() {
            sidebarModal.classList.remove('active');
            
            // Remove touch event listeners
            sidebarModalContent.removeEventListener('touchstart', handleTouchStart);
            sidebarModalContent.removeEventListener('touchmove', handleTouchMove);
            sidebarModalContent.removeEventListener('touchend', handleTouchEnd);
            
            // Wait for animation to complete before hiding
            setTimeout(() => {
                if (!sidebarModal.classList.contains('active')) {
                    sidebarModal.style.display = 'none';
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