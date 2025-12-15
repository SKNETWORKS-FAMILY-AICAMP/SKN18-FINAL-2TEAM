// Common Modal Utility Functions

/**
 * Open a modal
 * @param {string} modalId - The ID of the modal element
 * @param {object} options - Additional options to pass to modal (e.g., { scheduleId: 123 })
 */
function openModal(modalId, options = {}) {
    const modal = document.getElementById(modalId);
    if (!modal) {
        console.warn(`Modal with ID "${modalId}" not found`);
        return;
    }

    // Add active class
    modal.classList.add('active');
    
    // Prevent body scroll
    document.body.style.overflow = 'hidden';
    
    // Focus trap
    trapFocus(modal);
    
    // Dispatch custom event with additional data
    const event = new CustomEvent('modal:open', { 
        detail: { modalId, ...options }
    });
    document.dispatchEvent(event);
}

/**
 * Close a modal
 * @param {string} modalId - The ID of the modal element
 */
function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;

    // Add closing class for animation
    modal.classList.add('closing');
    modal.classList.remove('active');
    
    // Restore body scroll
    document.body.style.overflow = '';
    
    // Remove closing class after animation
    setTimeout(() => {
        modal.classList.remove('closing');
    }, 200);
    
    // Dispatch custom event
    const event = new CustomEvent('modal:close', { detail: { modalId } });
    document.dispatchEvent(event);
}

/**
 * Close modal when clicking overlay
 */
function setupModalOverlayClick() {
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('modal-overlay')) {
            const modalId = e.target.id;
            closeModal(modalId);
        }
    });
}

/**
 * Close modal with Escape key
 */
function setupModalEscapeKey() {
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const activeModal = document.querySelector('.modal-overlay.active');
            if (activeModal) {
                closeModal(activeModal.id);
            }
        }
    });
}

/**
 * Focus trap for accessibility
 */
function trapFocus(modal) {
    const focusableElements = modal.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    
    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];
    
    if (firstElement) {
        firstElement.focus();
    }
    
    modal.addEventListener('keydown', function handleTab(e) {
        if (e.key !== 'Tab') return;
        
        if (e.shiftKey) {
            if (document.activeElement === firstElement) {
                e.preventDefault();
                lastElement.focus();
            }
        } else {
            if (document.activeElement === lastElement) {
                e.preventDefault();
                firstElement.focus();
            }
        }
    });
}

/**
 * Setup cancel button handlers (취소 buttons)
 * Uses event delegation to handle dynamically created modals
 */
function setupModalCancelButtons() {
    document.addEventListener('click', (e) => {
        // Check if clicked element or its parent has data-action="close"
        const cancelBtn = e.target.closest('[data-action="close"]');
        if (cancelBtn) {
            const modal = cancelBtn.closest('.modal-overlay');
            if (modal) {
                e.preventDefault();
                e.stopPropagation();
                closeModal(modal.id);
            }
        }
    });
}

/**
 * Initialize modal system
 */
function initModalSystem() {
    setupModalOverlayClick();
    setupModalEscapeKey();
    setupModalCancelButtons();
    
    // Auto-close buttons (X button)
    document.querySelectorAll('.modal-close-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const modal = e.target.closest('.modal-overlay');
            if (modal) {
                closeModal(modal.id);
            }
        });
    });
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initModalSystem);
} else {
    initModalSystem();
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.Modal = {
        open: openModal,
        close: closeModal,
        init: initModalSystem,
    };
}
