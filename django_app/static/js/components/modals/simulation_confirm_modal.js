// Simulation Confirm Modal JavaScript

(function() {
    'use strict';

const modalId = 'simulationConfirmModal';
let selectedToolsData = [];
let currentSequence = '';

// DOM elements (will be initialized when DOM is ready)
let modal = null;
let titleInput = null;
let sequenceContainer = null;
let sequenceDisplay = null;
let toolsList = null;
let runBtn = null;

// Initialize DOM elements
function initDOMElements() {
    modal = document.getElementById(modalId);
    titleInput = document.getElementById('simulationTitleInput');
    sequenceContainer = document.getElementById('simulationProteinSequenceContainer');
    sequenceDisplay = document.getElementById('simulationProteinSequence');
    toolsList = document.getElementById('simulationSelectedToolsList');
    runBtn = document.getElementById('simulationConfirmRunBtn');
    
    return !!modal; // Return true if modal was found
}

// Initialize modal
function initSimulationConfirmModal() {
    // Initialize DOM elements if not already done
    if (!modal) {
        initDOMElements();
    }
    if (!modal) {
        console.warn('[SimulationConfirmModal] Modal element not found in initSimulationConfirmModal');
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

    // Run button
    runBtn?.addEventListener('click', handleRunSimulation);
    
    return true;
}

// Open modal
function openSimulationConfirmModal(tools, sequence) {
    // Ensure DOM elements are initialized
    if (!modal) {
        initDOMElements();
    }
    if (!modal || !tools || tools.length === 0) {
        console.error('[SimulationConfirmModal] Modal or tools not available');
        return;
    }

    selectedToolsData = tools;
    currentSequence = sequence || '';

    // Set default title
    if (titleInput) {
        const defaultTitle = `Pipeline ${new Date().toLocaleString('ko-KR')}`;
        titleInput.value = defaultTitle;
    }

    // Render sequence
    renderSequence(sequence);

    // Render selected tools
    renderSelectedTools(tools);

    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
}

// Close modal
function closeModal() {
    if (!modal) return;
    modal.style.display = 'none';
    document.body.style.overflow = '';
    selectedToolsData = [];
    currentSequence = '';
}

// Render sequence
function renderSequence(sequence) {
    if (!sequence || !sequenceDisplay || !sequenceContainer) {
        if (sequenceContainer) {
            sequenceContainer.style.display = 'none';
        }
        return;
    }

    sequenceContainer.style.display = 'block';
    sequenceDisplay.textContent = sequence || '서열 정보가 없습니다.';
}

// Render selected tools
function renderSelectedTools(tools) {
    if (!toolsList || !tools) return;

    toolsList.innerHTML = tools.map(tool => {
        const iconClass = tool.icon || "fas fa-cog";
        return `
            <div class="selected-tool-item">
                <i class="${iconClass}"></i>
                <p>${escapeHtml(tool.name || '')}</p>
            </div>
        `;
    }).join('');
}

// Handle run simulation
function handleRunSimulation() {
    if (!titleInput) return;

    const title = titleInput.value.trim() || `Pipeline ${new Date().toLocaleString('ko-KR')}`;

    if (window.ExperimentPage && window.ExperimentPage.executeSimulation) {
        const toolIds = selectedToolsData.map(t => t.id);
        if (window.ExperimentPage.selectedTools) {
            window.ExperimentPage.selectedTools = toolIds;
        }
        window.ExperimentPage.executeSimulation(currentSequence, title);
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
    window.SimulationConfirmModal = {
        open: openSimulationConfirmModal,
        close: closeModal,
        init: initSimulationConfirmModal,
        initDOMElements: initDOMElements,
    };
    
    // Initialize when DOM is ready
    function tryInit() {
        if (initDOMElements() && initSimulationConfirmModal()) {
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
