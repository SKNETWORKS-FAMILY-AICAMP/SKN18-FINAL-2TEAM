// Feedback Modal Component JavaScript Logic

// State variables
let feedback = '';
let category = 'general';
let modalElement = null;
let lifecycleEventsBound = false;
let isSubmitting = false;

// DOM elements
const modalId = 'feedbackModal';
let feedbackCategory = null;
let feedbackText = null;
let submitFeedbackBtn = null;

function updateSubmitButtonState() {
    if (!submitFeedbackBtn) return;
    const hasContent = (feedback || '').trim().length > 0;
    submitFeedbackBtn.disabled = isSubmitting || !hasContent;
    submitFeedbackBtn.textContent = isSubmitting ? '전송 중...' : '전송';
}

function updateDomReferences() {
    modalElement = modalElement || document.getElementById(modalId);
    feedbackCategory = feedbackCategory || document.getElementById('feedbackCategory');
    feedbackText = feedbackText || document.getElementById('feedbackText');
    submitFeedbackBtn = submitFeedbackBtn || document.getElementById('submitFeedbackBtn');
}

function updateFormUI(options = {}) {
    const { focusTextarea = false } = options;
    updateDomReferences();
    if (feedbackCategory) {
        feedbackCategory.value = category;
    }
    if (feedbackText) {
        feedbackText.value = feedback;
        if (focusTextarea) {
            setTimeout(() => {
                feedbackText.focus();
            }, 50);
        }
    }
    updateSubmitButtonState();
}

function resetFormState(options = {}) {
    feedback = '';
    category = 'general';
    isSubmitting = false;
    updateFormUI(options);
}

function setSubmittingState(value) {
    isSubmitting = value;
    updateSubmitButtonState();
}

function showFeedbackNotification(type, message) {
    if (window.notyf && typeof window.notyf[type] === 'function') {
        window.notyf[type](message);
    } else {
        window.alert(message);
    }
}

// Initialize modal
function initFeedbackModal() {
    modalElement = document.getElementById(modalId);
    if (!modalElement) return;
    
    // Get DOM elements
    feedbackCategory = document.getElementById('feedbackCategory');
    feedbackText = document.getElementById('feedbackText');
    submitFeedbackBtn = document.getElementById('submitFeedbackBtn');
    
    // Reset state
    resetFormState();
    
    // Event listeners
    if (feedbackCategory) {
        feedbackCategory.addEventListener('change', (e) => {
            category = e.target.value;
        });
    }
    
    if (feedbackText) {
        feedbackText.addEventListener('input', (e) => {
            feedback = e.target.value;
            updateSubmitButtonState();
        });
    }
    
    submitFeedbackBtn?.addEventListener('click', handleSubmit);
    
    // Close button handler
    const closeBtn = modalElement.querySelector('.modal-close-btn');
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            closeFeedbackModal();
        });
    }
    
    // Footer button handlers
    const footerButtons = modalElement.querySelectorAll('.modal-footer [data-action]');
    footerButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const action = e.currentTarget.getAttribute('data-action');
            if (action === 'close') {
                closeFeedbackModal();
            } else if (action === 'submit') {
                handleSubmit(e);
            }
        });
    });
    
    // Close on overlay click
    modalElement.addEventListener('click', (e) => {
        if (e.target === modalElement) {
            closeFeedbackModal();
        }
    });
    
    // Close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modalElement.classList.contains('active')) {
            closeFeedbackModal();
        }
    });

    if (!lifecycleEventsBound) {
        document.addEventListener('modal:open', (event) => {
            if (event.detail?.modalId === modalId) {
                resetFormState({ focusTextarea: true });
            }
        });
        document.addEventListener('modal:close', (event) => {
            if (event.detail?.modalId === modalId) {
                resetFormState();
            }
        });
        lifecycleEventsBound = true;
    }
}

// Handle submit
async function handleSubmit(event) {
    if (event) {
        event.preventDefault();
    }
    
    updateDomReferences();
    
    if (isSubmitting) {
        return;
    }
    
    const trimmedFeedback = (feedback || '').trim();
    if (!trimmedFeedback) {
        showFeedbackNotification('error', '피드백 내용을 입력해주세요.');
        if (feedbackText) {
            feedbackText.focus();
        }
        return;
    }
    
    setSubmittingState(true);
    
    try {
        const response = await fetch('/api/feedback/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
            body: JSON.stringify({
                category,
                feedback: trimmedFeedback,
            }),
        });
        
        const data = await response.json().catch(() => ({}));
        if (!response.ok || data.status !== 'success') {
            const errorMessage = data.error || data.message || '피드백 저장에 실패했습니다.';
            throw new Error(errorMessage);
        }
        
        showFeedbackNotification('success', '피드백이 저장되었습니다. 감사합니다!');
        closeFeedbackModal();
    } catch (error) {
        console.error('Error submitting feedback:', error);
        showFeedbackNotification('error', error.message || '피드백 전송 중 오류가 발생했습니다.');
    } finally {
        setSubmittingState(false);
    }
}

// Open feedback modal
function openFeedbackModal() {
    updateDomReferences();
    // Use global Modal system if available
    if (window.Modal) {
        window.Modal.open(modalId);
    } else {
        if (!modalElement) return;
        modalElement.classList.add('active');
        document.body.style.overflow = 'hidden';
        resetFormState({ focusTextarea: true });
    }
}

// Close feedback modal
function closeFeedbackModal() {
    updateDomReferences();
    // Use global Modal system if available
    if (window.Modal) {
        window.Modal.close(modalId);
    } else {
        if (!modalElement) return;
        modalElement.classList.remove('active');
        document.body.style.overflow = '';
        resetFormState();
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
