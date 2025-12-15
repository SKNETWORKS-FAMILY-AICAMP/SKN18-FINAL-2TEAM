// Feedback Modal Component JavaScript Logic

// State variables
let feedback = '';
let category = 'general';

// DOM elements
const modalId = 'feedbackModal';
let feedbackCategory = null;
let feedbackText = null;
let submitFeedbackBtn = null;

// Initialize modal
function initFeedbackModal() {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    
    // Get DOM elements
    feedbackCategory = document.getElementById('feedbackCategory');
    feedbackText = document.getElementById('feedbackText');
    submitFeedbackBtn = document.getElementById('submitFeedbackBtn');
    
    // Reset state
    feedback = '';
    category = 'general';
    
    // Update UI
    if (feedbackCategory) {
        feedbackCategory.value = category;
    }
    if (feedbackText) {
        feedbackText.value = feedback;
    }
    
    // Event listeners
    if (feedbackCategory) {
        feedbackCategory.addEventListener('change', (e) => {
            category = e.target.value;
        });
    }
    
    if (feedbackText) {
        feedbackText.addEventListener('input', (e) => {
            feedback = e.target.value;
        });
    }
    
    if (submitFeedbackBtn) {
        submitFeedbackBtn.addEventListener('click', handleSubmit);
    }
    
    // Close button handler
    const closeBtn = modal.querySelector('.modal-close-btn');
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            closeFeedbackModal();
        });
    }
    
    // Footer button handlers
    const footerButtons = modal.querySelectorAll('.modal-footer [data-action]');
    footerButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const action = e.currentTarget.getAttribute('data-action');
            if (action === 'close') {
                closeFeedbackModal();
            } else if (action === 'submit') {
                handleSubmit();
            }
        });
    });
    
    // Close on overlay click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeFeedbackModal();
        }
    });
    
    // Close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal.classList.contains('active')) {
            closeFeedbackModal();
        }
    });
}

// Handle submit
function handleSubmit() {
    console.log('Feedback submitted:', { category, feedback });
    
    // Here you can add API call to submit feedback
    // Example:
    // fetch('/api/feedback/', {
    //     method: 'POST',
    //     headers: {
    //         'Content-Type': 'application/json',
    //         'X-CSRFToken': getCsrfToken(),
    //     },
    //     body: JSON.stringify({ category, feedback }),
    // })
    // .then(response => response.json())
    // .then(data => {
    //     console.log('Feedback submitted successfully:', data);
    //     closeFeedbackModal();
    // })
    // .catch(error => {
    //     console.error('Error submitting feedback:', error);
    // });
    
    closeFeedbackModal();
}

// Open feedback modal
function openFeedbackModal() {
    // Use global Modal system if available
    if (window.Modal) {
        window.Modal.open(modalId);
    } else {
        const modal = document.getElementById(modalId);
        if (!modal) return;
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
    
    // Reset state
    feedback = '';
    category = 'general';
    
    // Update UI
    if (feedbackCategory) {
        feedbackCategory.value = category;
    }
    if (feedbackText) {
        feedbackText.value = feedback;
    }
    
    // Focus on textarea
    if (feedbackText) {
        setTimeout(() => {
            feedbackText.focus();
        }, 100);
    }
}

// Close feedback modal
function closeFeedbackModal() {
    // Use global Modal system if available
    if (window.Modal) {
        window.Modal.close(modalId);
    } else {
        const modal = document.getElementById(modalId);
        if (!modal) return;
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
    
    // Reset state
    feedback = '';
    category = 'general';
    
    if (feedbackCategory) {
        feedbackCategory.value = category;
    }
    if (feedbackText) {
        feedbackText.value = feedback;
    }
}

// Get CSRF token
function getCsrfToken() {
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === 'csrftoken') {
            return value;
        }
    }
    return '';
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initFeedbackModal);
} else {
    initFeedbackModal();
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.FeedbackModal = {
        open: openFeedbackModal,
        close: closeFeedbackModal,
        init: initFeedbackModal,
    };
    
    // Also register with global Modal system if available
    if (window.Modal) {
        window.Modal.feedback = {
            open: openFeedbackModal,
            close: closeFeedbackModal,
        };
    }
}
