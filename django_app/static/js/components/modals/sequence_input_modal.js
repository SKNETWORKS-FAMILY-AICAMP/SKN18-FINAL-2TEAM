// Sequence Input Modal JavaScript

(function() {
    'use strict';
    
    console.log('[SequenceInputModal] IIFE starting...');

const modalId = 'sequenceInputModal';
let currentSequence = '';

// DOM elements (will be initialized when DOM is ready)
let modal = null;
let sequenceTextarea = null;
let charCount = null;
let applyBtn = null;
let infoBox = null;

// Initialize DOM elements
function initDOMElements() {
    modal = document.getElementById(modalId);
    sequenceTextarea = document.getElementById('sequenceInputModalTextarea');
    charCount = document.getElementById('sequenceInputModalCharCount');
    applyBtn = document.getElementById('sequenceInputModalApplyBtn');
    infoBox = document.getElementById('sequenceInputModalInfo');
    
    return !!modal; // Return true if modal was found
}

// Initialize modal
function initSequenceInputModal() {
    // Initialize DOM elements if not already done
    if (!modal) {
        initDOMElements();
    }
    if (!modal) {
        console.warn('[SequenceInputModal] Modal element not found in initSequenceInputModal');
        return false;
    }

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
    
    return true;
}

// Open modal
function openSequenceInputModal(initialSequence = '') {
    console.log('[SequenceInputModal] ====== openSequenceInputModal called ======');
    console.log('[SequenceInputModal] initialSequence:', initialSequence);
    
    // Ensure DOM elements are initialized
    if (!modal) {
        console.log('[SequenceInputModal] Modal not found, initializing DOM elements...');
        initDOMElements();
    }
    if (!modal) {
        console.error('[SequenceInputModal] Modal not found after initialization');
        return;
    }
    
    console.log('[SequenceInputModal] Modal found:', modal);
    console.log('[SequenceInputModal] Modal current display:', window.getComputedStyle(modal).display);

    currentSequence = initialSequence;
    
    if (sequenceTextarea) {
        sequenceTextarea.value = initialSequence;
        console.log('[SequenceInputModal] Textarea value set:', sequenceTextarea.value);
    } else {
        console.warn('[SequenceInputModal] sequenceTextarea not found');
    }

    updateCharCount();
    updateApplyButton();
    updateInfoBox();

    modal.style.display = 'flex';
    modal.classList.add('active'); // Add active class for CSS
    document.body.style.overflow = 'hidden';
    
    // Check modal visibility after setting display
    setTimeout(() => {
        const computedStyle = window.getComputedStyle(modal);
        const rect = modal.getBoundingClientRect();
        console.log('[SequenceInputModal] Modal visibility check:', {
            display: computedStyle.display,
            visibility: computedStyle.visibility,
            opacity: computedStyle.opacity,
            zIndex: computedStyle.zIndex,
            position: computedStyle.position,
            width: rect.width,
            height: rect.height,
            top: rect.top,
            left: rect.left,
            isVisible: rect.width > 0 && rect.height > 0 && computedStyle.display !== 'none'
        });
        
        if (rect.width === 0 || rect.height === 0) {
            console.warn('[SequenceInputModal] WARNING: Modal has zero dimensions!');
        }
    }, 50);
    
    console.log('[SequenceInputModal] Modal display set to flex');
    console.log('[SequenceInputModal] Modal computed display:', window.getComputedStyle(modal).display);
    
    // Focus textarea
    if (sequenceTextarea) {
        setTimeout(() => {
            sequenceTextarea.focus();
            console.log('[SequenceInputModal] Textarea focused');
        }, 100);
    }
    
    console.log('[SequenceInputModal] ====== Modal opened ======');
}

// Close modal
function closeModal() {
    if (!modal) return;
    modal.style.display = 'none';
    modal.classList.remove('active'); // Remove active class
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
    infoBox.style.display = currentSequence.length > 0 ? 'flex' : 'none';
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

    // Update experiment page sequence via ExperimentPage API (not direct DOM manipulation)
    // Note: Do NOT update proteinSequenceInput field - modal should be independent
    if (window.ExperimentPage) {
        // Update sequence query using setter method
        if (window.ExperimentPage.setSequenceQuery) {
            window.ExperimentPage.setSequenceQuery(currentSequence);
        }
        
        // Update selected protein using setter method
        if (window.ExperimentPage.setSelectedProtein) {
            window.ExperimentPage.setSelectedProtein(customProtein);
        }
        
        // Do NOT update proteinSequenceInput field - keep modal independent
        // The sequence is stored in sequenceQuery and selectedProtein, which is sufficient

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

    // Export to window immediately
    console.log('[SequenceInputModal] Assigning window.SequenceInputModal...');
    window.SequenceInputModal = {
        open: openSequenceInputModal,
        close: closeModal,
        init: initSequenceInputModal,
        initDOMElements: initDOMElements,
    };
    console.log('[SequenceInputModal] window.SequenceInputModal assigned:', window.SequenceInputModal);
    
    // Initialize when DOM is ready
    function tryInit() {
        if (initDOMElements() && initSequenceInputModal()) {
            console.log('[SequenceInputModal] Initialized successfully');
            return true;
        }
        return false;
    }
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            if (!tryInit()) {
                setTimeout(tryInit, 100);
            }
        });
    } else {
        // DOM already ready
        if (!tryInit()) {
            setTimeout(tryInit, 100);
        }
    }
    
    console.log('[SequenceInputModal] Script loaded, window.SequenceInputModal available');
})();
