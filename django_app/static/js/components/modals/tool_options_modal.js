// Tool Options Modal JavaScript

(function() {
    'use strict';

const modalId = 'toolOptionsModal';
let currentTool = null;
let toolOptions = {};

// DOM elements (will be initialized when DOM is ready)
let modal = null;
let modalTitle = null;
let optionsContent = null;
let saveBtn = null;

// Initialize DOM elements
function initDOMElements() {
    modal = document.getElementById(modalId);
    modalTitle = document.getElementById('toolOptionsModalTitle');
    optionsContent = document.getElementById('toolOptionsContent');
    saveBtn = document.getElementById('toolOptionsSaveBtn');
    
    return !!modal; // Return true if modal was found
}

// Initialize modal
function initToolOptionsModal() {
    // Initialize DOM elements if not already done
    if (!modal) {
        initDOMElements();
    }
    if (!modal) {
        console.warn('[ToolOptionsModal] Modal element not found in initToolOptionsModal');
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

    // Save button
    saveBtn?.addEventListener('click', handleSaveOptions);
    
    return true;
}

// Open modal
function openToolOptionsModal(tool) {
    // Ensure DOM elements are initialized
    if (!modal) {
        initDOMElements();
    }
    if (!modal || !tool) {
        console.error('[ToolOptionsModal] Modal or tool not available');
        return;
    }

    currentTool = tool;

    // Update title
    if (modalTitle) {
        modalTitle.textContent = `${tool.name} 옵션 설정`;
    }

    // Get current options or initialize with defaults
    toolOptions = window.ExperimentPage?.toolOptions?.[tool.id] || {};
    if (!toolOptions || Object.keys(toolOptions).length === 0) {
        toolOptions = {};
        if (tool.optionFields) {
            tool.optionFields.forEach(field => {
                toolOptions[field.name] = field.default;
            });
        }
    }

    // Render options
    renderToolOptions(tool);

    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
}

// Close modal
function closeModal() {
    if (!modal) return;
    modal.style.display = 'none';
    document.body.style.overflow = '';
    currentTool = null;
    toolOptions = {};
}

// Render tool options
function renderToolOptions(tool) {
    if (!optionsContent || !tool.optionFields) return;

    optionsContent.innerHTML = tool.optionFields.map(field => {
        const value = toolOptions[field.name] ?? field.default;

        let inputHtml = '';
        if (field.type === 'number') {
            inputHtml = `
                <input
                    type="number"
                    class="form-input"
                    data-field-name="${field.name}"
                    value="${value}"
                    min="${field.min || ''}"
                    max="${field.max || ''}"
                    step="${field.step || 1}"
                />
            `;
        } else if (field.type === 'select') {
            inputHtml = `
                <select class="form-select" data-field-name="${field.name}">
                    ${field.options.map(opt => 
                        `<option value="${opt}" ${value === opt ? 'selected' : ''}>${escapeHtml(opt)}</option>`
                    ).join('')}
                </select>
            `;
        } else if (field.type === 'checkbox') {
            inputHtml = `
                <label class="checkbox-label">
                    <input
                        type="checkbox"
                        data-field-name="${field.name}"
                        ${value ? 'checked' : ''}
                    />
                    <span>활성화</span>
                </label>
            `;
        }

        const rangeText = (field.type === 'number' && field.min !== undefined && field.max !== undefined) 
            ? `<p class="form-help-text">범위: ${field.min} ~ ${field.max}</p>`
            : '';

        return `
            <div class="form-group">
                <label>${escapeHtml(field.label)}</label>
                ${inputHtml}
                ${rangeText}
            </div>
        `;
    }).join('');

    // Attach event listeners
    attachOptionListeners();
}

// Attach option listeners
function attachOptionListeners() {
    const inputs = optionsContent.querySelectorAll('[data-field-name]');
    inputs.forEach(input => {
        const fieldName = input.getAttribute('data-field-name');
        
        if (input.type === 'checkbox') {
            input.addEventListener('change', (e) => {
                toolOptions[fieldName] = e.target.checked;
            });
        } else {
            input.addEventListener('input', (e) => {
                const value = input.type === 'number' 
                    ? parseFloat(e.target.value) 
                    : e.target.value;
                toolOptions[fieldName] = value;
            });
        }
    });
}

// Handle save options
function handleSaveOptions() {
    if (!currentTool) return;

    // Save options to ExperimentPage
    if (window.ExperimentPage) {
        if (!window.ExperimentPage.toolOptions) {
            window.ExperimentPage.toolOptions = {};
        }
        window.ExperimentPage.toolOptions[currentTool.id] = { ...toolOptions };
    }

    if (window.notyf) {
        window.notyf.success('도구 옵션이 저장되었습니다.');
    }

    closeModal();
}

// Escape HTML
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

    // Export to window immediately
    window.ToolOptionsModal = {
        open: openToolOptionsModal,
        close: closeModal,
        init: initToolOptionsModal,
        initDOMElements: initDOMElements,
    };
    
    // Initialize when DOM is ready
    function tryInit() {
        if (initDOMElements() && initToolOptionsModal()) {
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
})();
