(function () {
    const modalId = 'chatDislikeModal';
    let modalEl = null;
    let reasonInputs = [];
    let textareaWrapper = null;
    let textareaEl = null;
    let submitBtn = null;
    let removeBtn = null;
    let initialized = false;
    let currentMessageId = null;
    let currentFeedbackType = null;
    let selectedReason = '';
    let reasonText = '';
    const handlers = {
        onSubmit: null,
        onRemove: null,
    };

    function setupElements() {
        if (initialized) return true;
        modalEl = document.getElementById(modalId);
        if (!modalEl) {
            return false;
        }
        reasonInputs = modalEl.querySelectorAll('input[name="chatDislikeReason"]');
        textareaWrapper = modalEl.querySelector('#chatDislikeTextareaWrapper');
        textareaEl = modalEl.querySelector('#chatDislikeReasonText');
        submitBtn = modalEl.querySelector('#chatDislikeSubmitBtn');
        removeBtn = modalEl.querySelector('#chatDislikeRemoveBtn');

        reasonInputs.forEach((input) => {
            input.addEventListener('change', () => {
                selectedReason = input.value;
                if (selectedReason === 'other') {
                    toggleTextarea(true);
                } else {
                    reasonText = '';
                    if (textareaEl) {
                        textareaEl.value = '';
                    }
                    toggleTextarea(false);
                }
                updateSubmitState();
            });
        });

        if (textareaEl) {
            textareaEl.addEventListener('input', () => {
                reasonText = textareaEl.value;
                updateSubmitState();
            });
        }

        if (submitBtn) {
            submitBtn.addEventListener('click', handleSubmit);
        }

        if (removeBtn) {
            removeBtn.addEventListener('click', handleRemove);
        }

        document.addEventListener('modal:close', (event) => {
            if (event.detail?.modalId === modalId) {
                resetState();
            }
        });

        initialized = true;
        document.dispatchEvent(new CustomEvent('chat-dislike-modal:ready'));
        return true;
    }

    function resetState() {
        currentMessageId = null;
        currentFeedbackType = null;
        selectedReason = '';
        reasonText = '';
        reasonInputs.forEach((input) => {
            input.checked = false;
        });
        toggleTextarea(false);
        if (textareaEl) {
            textareaEl.value = '';
        }
        if (submitBtn) {
            submitBtn.disabled = true;
        }
        if (removeBtn) {
            removeBtn.disabled = true;
        }
    }

    function toggleTextarea(visible) {
        if (!textareaWrapper) return;
        if (visible) {
            textareaWrapper.classList.add('visible');
        } else {
            textareaWrapper.classList.remove('visible');
        }
    }

    function updateSubmitState() {
        if (!submitBtn) return;
        if (!selectedReason) {
            submitBtn.disabled = true;
            return;
        }
        if (selectedReason === 'other') {
            submitBtn.disabled = !(reasonText && reasonText.trim().length > 0);
            return;
        }
        submitBtn.disabled = false;
    }

    function handleSubmit() {
        if (!currentMessageId || !handlers.onSubmit || submitBtn?.disabled) {
            return;
        }
        handlers.onSubmit({
            messageId: currentMessageId,
            reasonCode: selectedReason,
            reasonText: selectedReason === 'other' ? (reasonText || '').trim() : '',
        });
    }

    function handleRemove() {
        if (!currentMessageId || !handlers.onRemove || removeBtn?.disabled) {
            return;
        }
        handlers.onRemove({ messageId: currentMessageId });
    }

    function openModal(messageId, options = {}) {
        if (!setupElements()) {
            console.warn('[ChatDislikeModal] Modal elements are not ready');
            return;
        }
        currentMessageId = messageId;
        currentFeedbackType = options.currentFeedbackType || null;
        selectedReason = options.reasonCode || '';
        reasonText = options.reasonText || '';

        reasonInputs.forEach((input) => {
            input.checked = input.value === selectedReason;
        });

        if (selectedReason === 'other') {
            toggleTextarea(true);
            if (textareaEl) {
                textareaEl.value = reasonText || '';
            }
        } else {
            toggleTextarea(false);
            if (textareaEl) {
                textareaEl.value = '';
            }
        }

        if (removeBtn) {
            removeBtn.disabled = currentFeedbackType !== 'D';
        }

        updateSubmitState();

        if (window.Modal && typeof window.Modal.open === 'function') {
            window.Modal.open(modalId);
        } else {
            modalEl?.classList.add('active');
        }
    }

    function closeModal() {
        if (!initialized) return;
        if (window.Modal && typeof window.Modal.close === 'function') {
            window.Modal.close(modalId);
        } else {
            modalEl?.classList.remove('active');
            resetState();
        }
    }

    function setHandlers(newHandlers = {}) {
        if (typeof newHandlers.onSubmit === 'function') {
            handlers.onSubmit = newHandlers.onSubmit;
        }
        if (typeof newHandlers.onRemove === 'function') {
            handlers.onRemove = newHandlers.onRemove;
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupElements);
    } else {
        setupElements();
    }

    window.ChatDislikeModal = {
        open: openModal,
        close: closeModal,
        setHandlers,
    };
})();
