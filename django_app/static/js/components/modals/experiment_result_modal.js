// Experiment Result Modal Component JavaScript Logic
console.log('[ExperimentResultModal] ===== Script file loading... =====');

(function() {
    'use strict';
    
    console.log('[ExperimentResultModal] IIFE starting...');

    // State variables
    let selectedExperiment = null;
    let experiments = [];
    let currentView = 'list'; // 'list' | 'results'
    let isInitialized = false;

    // DOM elements
    const modalId = 'experimentResultModal';
    let experimentListView = null;
    let experimentResultsView = null;
    let experimentsList = null;
    let backToExperimentsBtn = null;
    let selectedExperimentInfo = null;
    let resultsGrid = null;

    // Get DOM elements
    function getModalElements() {
        experimentListView = document.getElementById('experimentListView');
        experimentResultsView = document.getElementById('experimentResultsView');
        experimentsList = document.getElementById('experimentsList');
        backToExperimentsBtn = document.getElementById('backToExperimentsBtn');
        selectedExperimentInfo = document.getElementById('selectedExperimentInfo');
        resultsGrid = document.getElementById('resultsGrid');
    }

    // Initialize modal
    function initExperimentResultModal() {
        if (isInitialized) return true;
        
        const modal = document.getElementById(modalId);
        if (!modal) {
            console.warn('[ExperimentResultModal] Modal element not found');
            return false;
        }
        
        // Get DOM elements
        getModalElements();
        
        // Close button handlers
        const closeBtns = modal.querySelectorAll('[data-action="close"]');
        closeBtns.forEach(btn => {
            btn.addEventListener('click', closeExperimentResultModal);
        });
        
        // Back button handler
        if (backToExperimentsBtn) {
            backToExperimentsBtn.addEventListener('click', () => {
                selectedExperiment = null;
                currentView = 'list';
                renderExperimentList();
                showExperimentListView();
            });
        }
        
        isInitialized = true;
        console.log('[ExperimentResultModal] Initialized successfully');
        return true;
    }

    // Load experiments from API
    async function loadExperiments() {
        try {
            // TODO: Replace with actual API endpoint
            // const response = await fetch('/api/experiments/');
            // const data = await response.json();
            // experiments = data.experiments;
            
            // Mock data for now
            experiments = [
                {
                    id: 1,
                    pipeline: 'Protein Structure Prediction',
                    tools: ['AlphaFold2', 'RoseTTAFold'],
                    status: '완료',
                    progress: 100,
                    created: '2024-01-15',
                    results: [
                        { id: 1, name: 'structure.pdb', type: 'PDB', size: '2.3 MB', date: '2024-01-15' },
                        { id: 2, name: 'confidence.csv', type: 'CSV', size: '145 KB', date: '2024-01-15' }
                    ]
                },
                {
                    id: 2,
                    pipeline: 'Molecular Dynamics Simulation',
                    tools: ['GROMACS', 'VMD'],
                    status: '진행중',
                    progress: 65,
                    created: '2024-01-20',
                    results: [
                        { id: 3, name: 'trajectory.xtc', type: 'XTC', size: '450 MB', date: '2024-01-20' }
                    ]
                },
                {
                    id: 3,
                    pipeline: 'Sequence Alignment',
                    tools: ['BLAST', 'ClustalW'],
                    status: '준비',
                    progress: 0,
                    created: '2024-01-22',
                    results: []
                }
            ];
            
            renderExperimentList();
        } catch (error) {
            console.error('[ExperimentResultModal] Error loading experiments:', error);
            experiments = [];
            renderExperimentList();
        }
    }

    // Render experiment list
    function renderExperimentList() {
        if (!experimentsList) {
            getModalElements();
        }
        if (!experimentsList) return;
        
        if (experiments.length === 0) {
            experimentsList.innerHTML = '<div class="empty-state">실험 결과가 없습니다.</div>';
            return;
        }
        
        experimentsList.innerHTML = experiments.map(exp => {
            const statusClass = getStatusClass(exp.status);
            const statusDotClass = getStatusDotClass(exp.status);
            
            return `
                <div class="experiment-item" data-experiment-id="${exp.id}">
                    <div class="experiment-item-header">
                        <div class="experiment-item-content">
                            <h3 class="experiment-item-title">${escapeHtml(exp.pipeline)}</h3>
                            <div class="experiment-tools">
                                ${exp.tools.map(tool => `
                                    <span class="experiment-tool-tag">${escapeHtml(tool)}</span>
                                `).join('')}
                            </div>
                        </div>
                        <span class="experiment-status ${statusClass}">
                            <span class="experiment-status-dot ${statusDotClass}"></span>
                            ${escapeHtml(exp.status)}
                        </span>
                    </div>
                    <div class="experiment-item-footer">
                        <span>${escapeHtml(exp.created)}</span>
                        <span>${exp.progress}% 완료</span>
                    </div>
                </div>
            `;
        }).join('');
        
        // Attach click handlers
        const experimentItems = experimentsList.querySelectorAll('.experiment-item');
        experimentItems.forEach(item => {
            item.addEventListener('click', (e) => {
                const experimentId = parseInt(item.getAttribute('data-experiment-id'));
                const experiment = experiments.find(exp => exp.id === experimentId);
                if (experiment) {
                    selectExperiment(experiment);
                }
            });
        });
    }

    // Get status class
    function getStatusClass(status) {
        const statusMap = {
            '준비': 'status-ready',
            '진행중': 'status-progress',
            '완료': 'status-complete'
        };
        return statusMap[status] || 'status-ready';
    }

    // Get status dot class
    function getStatusDotClass(status) {
        return getStatusClass(status);
    }

    // Select experiment
    function selectExperiment(experiment) {
        selectedExperiment = experiment;
        currentView = 'results';
        renderExperimentResults();
        showExperimentResultsView();
    }

    // Render experiment results
    function renderExperimentResults() {
        if (!selectedExperiment) return;
        
        if (!selectedExperimentInfo || !resultsGrid) {
            getModalElements();
        }
        
        // Render experiment info
        if (selectedExperimentInfo) {
            selectedExperimentInfo.innerHTML = `
                <h3 class="experiment-info-title">${escapeHtml(selectedExperiment.pipeline)}</h3>
                <div class="experiment-info-details">
                    <span>상태: ${escapeHtml(selectedExperiment.status)}</span>
                    <span>진행률: ${selectedExperiment.progress}%</span>
                    <span>${escapeHtml(selectedExperiment.created)}</span>
                </div>
            `;
        }
        
        // Render results
        if (resultsGrid) {
            if (selectedExperiment.results.length === 0) {
                resultsGrid.innerHTML = '<div class="empty-state">결과 데이터가 없습니다.</div>';
                return;
            }
            
            resultsGrid.innerHTML = selectedExperiment.results.map(result => {
                return `
                    <div class="result-item" data-result-id="${result.id}">
                        <div class="result-item-header">
                            <div>
                                <p class="result-item-name">${escapeHtml(result.name)}</p>
                                <div class="result-item-meta">
                                    <span class="result-item-type">${escapeHtml(result.type)}</span>
                                    <span>${escapeHtml(result.size)}</span>
                                    <span>·</span>
                                    <span>${escapeHtml(result.date)}</span>
                                </div>
                            </div>
                            <div class="result-item-download">
                                <i class="fa-solid fa-download"></i>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
            
            // Attach click handlers
            const resultItems = resultsGrid.querySelectorAll('.result-item');
            resultItems.forEach(item => {
                item.addEventListener('click', (e) => {
                    const resultId = parseInt(item.getAttribute('data-result-id'));
                    const result = selectedExperiment.results.find(r => r.id === resultId);
                    if (result) {
                        handleAttachExperiment(result);
                    }
                });
            });
        }
    }

    // Handle attach experiment
    function handleAttachExperiment(result) {
        const experimentData = {
            id: Date.now(),
            experimentId: selectedExperiment.id,
            experimentName: selectedExperiment.pipeline,
            resultId: result.id,
            resultName: result.name,
            resultType: result.type,
            resultSize: result.size,
            resultDate: result.date
        };
        
        // Dispatch event to chat.js
        const event = new CustomEvent('experiment:attached', {
            detail: experimentData
        });
        document.dispatchEvent(event);
        
        // Close modal
        closeExperimentResultModal();
    }

    // Show experiment list view
    function showExperimentListView() {
        if (!experimentListView || !experimentResultsView) {
            getModalElements();
        }
        if (experimentListView) {
            experimentListView.style.display = 'block';
        }
        if (experimentResultsView) {
            experimentResultsView.style.display = 'none';
        }
    }

    // Show experiment results view
    function showExperimentResultsView() {
        if (!experimentListView || !experimentResultsView) {
            getModalElements();
        }
        if (experimentListView) {
            experimentListView.style.display = 'none';
        }
        if (experimentResultsView) {
            experimentResultsView.style.display = 'block';
        }
    }

    // Open experiment result modal
    function openExperimentResultModal() {
        console.log('[ExperimentResultModal] Opening modal...');
        
        // Ensure initialization
        if (!isInitialized) {
            initExperimentResultModal();
        }
        
        const modal = document.getElementById(modalId);
        if (!modal) {
            console.error('[ExperimentResultModal] Modal element not found');
            return;
        }
        
        // Reset state
        selectedExperiment = null;
        currentView = 'list';
        showExperimentListView();
        
        // Reload experiments
        loadExperiments();
        
        modal.classList.add('active');
        console.log('[ExperimentResultModal] Modal opened');
    }

    // Close experiment result modal
    function closeExperimentResultModal() {
        const modal = document.getElementById(modalId);
        if (!modal) return;
        
        modal.classList.remove('active');
        
        // Reset state
        selectedExperiment = null;
        currentView = 'list';
        showExperimentListView();
    }

    // Escape HTML
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Export to window immediately
    console.log('[ExperimentResultModal] Assigning window.ExperimentResultModal...');
    window.ExperimentResultModal = {
        open: openExperimentResultModal,
        close: closeExperimentResultModal,
        init: initExperimentResultModal,
        isReady: function() {
            return isInitialized;
        }
    };
    console.log('[ExperimentResultModal] window.ExperimentResultModal assigned:', window.ExperimentResultModal);

    // Initialize when DOM is ready
    function tryInit() {
        if (initExperimentResultModal()) {
            document.dispatchEvent(new Event('experimentResultModal:ready'));
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

    console.log('[ExperimentResultModal] Script loaded, window.ExperimentResultModal available');
})();
