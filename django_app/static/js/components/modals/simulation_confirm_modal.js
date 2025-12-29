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
    console.log('[SimulationConfirmModal] ====== openSimulationConfirmModal called ======');
    console.log('[SimulationConfirmModal] tools:', tools);
    console.log('[SimulationConfirmModal] sequence:', sequence);
    
    // Ensure DOM elements are initialized
    if (!modal) {
        console.log('[SimulationConfirmModal] Modal not found, initializing DOM elements...');
        initDOMElements();
    }
    if (!modal) {
        console.error('[SimulationConfirmModal] Modal not found after initialization');
        return;
    }
    if (!tools || tools.length === 0) {
        console.error('[SimulationConfirmModal] Tools not available or empty');
        return;
    }
    
    console.log('[SimulationConfirmModal] Modal found:', modal);
    console.log('[SimulationConfirmModal] Modal current display:', window.getComputedStyle(modal).display);

    selectedToolsData = tools;
    currentSequence = sequence || '';

    // Set default title
    if (titleInput) {
        const defaultTitle = `Pipeline ${new Date().toLocaleString('ko-KR')}`;
        titleInput.value = defaultTitle;
        console.log('[SimulationConfirmModal] Title set:', defaultTitle);
    } else {
        console.warn('[SimulationConfirmModal] titleInput not found');
    }

    // Render sequence
    renderSequence(sequence);

    // Render selected tools
    renderSelectedTools(tools);

    modal.style.display = 'flex';
    modal.classList.add('active'); // Add active class for CSS
    document.body.style.overflow = 'hidden';
    
    console.log('[SimulationConfirmModal] Modal display set to flex');
    console.log('[SimulationConfirmModal] Modal computed display:', window.getComputedStyle(modal).display);
    
    // Check modal visibility after setting display
    setTimeout(() => {
        const computedStyle = window.getComputedStyle(modal);
        const rect = modal.getBoundingClientRect();
        console.log('[SimulationConfirmModal] Modal visibility check:', {
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
            console.warn('[SimulationConfirmModal] WARNING: Modal has zero dimensions!');
        }
    }, 50);
    
    console.log('[SimulationConfirmModal] ====== Modal opened ======');
}

// Close modal
function closeModal() {
    if (!modal) return;
    modal.style.display = 'none';
    modal.classList.remove('active'); // Remove active class
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
    // Wrap in <p> tag to match React structure: <p className="font-mono text-sm text-gray-900 break-all leading-relaxed">
    sequenceDisplay.innerHTML = `<p>${escapeHtml(sequence || '서열 정보가 없습니다.')}</p>`;
}

// Render selected tools
function renderSelectedTools(tools) {
    if (!toolsList || !tools) return;

    toolsList.innerHTML = tools.map(tool => {
        const iconClass = tool.icon || "fas fa-cog";
        return `
            <div class="simulation-selected-tool-item">
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
        // Update selected tools using setter method
        if (window.ExperimentPage.setSelectedTools) {
            window.ExperimentPage.setSelectedTools(toolIds);
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
