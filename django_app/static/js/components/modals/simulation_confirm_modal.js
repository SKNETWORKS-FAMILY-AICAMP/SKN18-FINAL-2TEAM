// Simulation Confirm Modal JavaScript

const modalId = 'simulationConfirmModal';
let selectedToolsData = [];
let currentSequence = '';

// DOM elements
const modal = document.getElementById(modalId);
const titleInput = document.getElementById('simulationTitleInput');
const sequenceContainer = document.getElementById('simulationProteinSequenceContainer');
const sequenceDisplay = document.getElementById('simulationProteinSequence');
const toolsList = document.getElementById('simulationSelectedToolsList');
const runBtn = document.getElementById('simulationConfirmRunBtn');

// Initialize modal
function initSimulationConfirmModal() {
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

    // Run button
    runBtn?.addEventListener('click', handleRunSimulation);
}

// Open modal
function openSimulationConfirmModal(tools, sequence) {
    if (!modal || !tools || tools.length === 0) return;

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

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSimulationConfirmModal);
} else {
    initSimulationConfirmModal();
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.SimulationConfirmModal = {
        open: openSimulationConfirmModal,
        close: closeModal,
        init: initSimulationConfirmModal,
    };
}
