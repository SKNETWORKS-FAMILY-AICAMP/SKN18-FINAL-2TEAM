// Sequence Input Modal JavaScript

const modalId = 'sequenceInputModal';
let currentSequence = '';

// DOM elements
const modal = document.getElementById(modalId);
const sequenceTextarea = document.getElementById('sequenceInputTextarea');
const charCount = document.getElementById('sequenceInputCharCount');
const applyBtn = document.getElementById('sequenceInputApplyBtn');
const infoBox = document.getElementById('sequenceInputInfo');

// Initialize modal
function initSequenceInputModal() {
    if (!modal) return;

    // Close button
    const closeBtn = modal.querySelector('.modal-close-btn');
    closeBtn?.addEventListener('click', () => closeModal());

    // Close on overlay click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeModal();
        }
    });

    // Footer close button
    const footerCloseBtn = modal.querySelector('[data-action="close"]');
    footerCloseBtn?.addEventListener('click', () => closeModal());

    // Textarea input handler
    if (sequenceTextarea) {
        sequenceTextarea.addEventListener('input', handleSequenceInput);
    }

    // Apply button
    applyBtn?.addEventListener('click', handleApply);
}

// Open modal
function openSequenceInputModal(initialSequence = '') {
    if (!modal) return;

    currentSequence = initialSequence;
    
    if (sequenceTextarea) {
        sequenceTextarea.value = initialSequence;
    }

    updateCharCount();
    updateApplyButton();
    updateInfoBox();

    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    
    // Focus textarea
    if (sequenceTextarea) {
        setTimeout(() => sequenceTextarea.focus(), 100);
    }
}

// Close modal
function closeModal() {
    if (!modal) return;
    modal.style.display = 'none';
    document.body.style.overflow = '';
    
    // Reset
    currentSequence = '';
    if (sequenceTextarea) {
        sequenceTextarea.value = '';
    }
    updateCharCount();
    updateApplyButton();
    updateInfoBox();
}

// Handle sequence input
function handleSequenceInput(e) {
    currentSequence = e.target.value.trim();
    updateCharCount();
    updateApplyButton();
    updateInfoBox();
}

// Update character count
function updateCharCount() {
    if (!charCount) return;
    const length = currentSequence.length;
    charCount.textContent = length > 0 ? `${length} 문자` : '서열을 입력하세요';
}

// Update apply button
function updateApplyButton() {
    if (!applyBtn) return;
    applyBtn.disabled = !currentSequence;
}

// Update info box
function updateInfoBox() {
    if (!infoBox) return;
    infoBox.style.display = currentSequence.length > 0 ? 'block' : 'none';
}

// Handle apply
function handleApply() {
    if (!currentSequence) {
        if (window.notyf) {
            window.notyf.error('서열을 입력하세요.');
        }
        return;
    }

    // Create custom protein object
    const customProtein = {
        name: '사용자 입력 서열',
        organism: 'Custom',
        length: currentSequence.length,
        sequence: currentSequence,
    };

    // Dispatch custom event to update pipeline
    const event = new CustomEvent('proteinSelected', {
        detail: { protein: customProtein, sequence: currentSequence }
    });
    document.dispatchEvent(event);

    // Update experiment page sequence
    if (window.ExperimentPage) {
        if (window.ExperimentPage.sequenceQuery !== undefined) {
            window.ExperimentPage.sequenceQuery = currentSequence;
        }
        if (window.ExperimentPage.selectedProtein !== undefined) {
            window.ExperimentPage.selectedProtein = customProtein;
        }
        
        const proteinInput = document.getElementById('proteinSequenceInput');
        if (proteinInput) {
            proteinInput.value = currentSequence;
        }

        // Update pipeline visualization
        if (window.ExperimentPage.updatePipelineSection) {
            window.ExperimentPage.updatePipelineSection();
        }
    }

    if (window.notyf) {
        window.notyf.success('단백질 서열이 선택되었습니다.');
    }

    closeModal();
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSequenceInputModal);
} else {
    initSequenceInputModal();
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.SequenceInputModal = {
        open: openSequenceInputModal,
        close: closeModal,
        init: initSequenceInputModal,
    };
}
