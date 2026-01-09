// PDB Selection Modal JavaScript
console.log('[PdbSelectionModal] ===== Script file loading... =====');

(function() {
    'use strict';

    console.log('[PdbSelectionModal] IIFE starting...');

    // State
    let allPdbFiles = [];
    let selectedPdbFiles = [];
    let savedStates = [];
    let selectedTool = null; // Currently selected tool in sidebar
    let isInitialized = false;

    // DOM element references
    const modalId = 'pdbSelectionModal';
    let modal = null;
    let selectAllCheckbox = null;
    let pdbList = null;
    let toolSidebar = null;
    let savedStatesList = null;
    let selectedCountEl = null;
    let confirmBtn = null;
    let tabButtons = null;
    let tabContents = null;

    // Get DOM elements
    function getModalElements() {
        modal = document.getElementById(modalId);
        selectAllCheckbox = document.getElementById('selectAllPdbFiles');
        pdbList = document.getElementById('pdbSelectionList');
        toolSidebar = document.getElementById('pdbToolSidebar');
        savedStatesList = document.getElementById('pdbSavedStatesList');
        selectedCountEl = document.getElementById('selectedPdbCount');
        confirmBtn = document.getElementById('confirmPdbSelectionBtn');
        tabButtons = modal ? modal.querySelectorAll('.pdb-tab-btn') : null;
        tabContents = modal ? modal.querySelectorAll('.pdb-tab-content') : null;
    }

    // Escape HTML
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Initialize modal
    function initPdbSelectionModal() {
        if (isInitialized) return true;

        getModalElements();
        if (!modal) {
            console.warn('[PdbSelectionModal] Modal element not found');
            return false;
        }

        // Ensure modal is initially hidden
        modal.classList.remove('active');
        modal.classList.remove('closing');

        // Close button handlers
        const closeBtns = modal.querySelectorAll('[data-action="close"]');
        closeBtns.forEach(btn => {
            btn.addEventListener('click', closePdbSelectionModal);
        });

        // Close on overlay click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closePdbSelectionModal();
            }
        });

        // Select all handler
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', handleSelectAll);
        }

        // Confirm handler
        if (confirmBtn) {
            confirmBtn.addEventListener('click', handleConfirm);
        }
        
        // Tab switching handlers
        if (tabButtons) {
            tabButtons.forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const tabName = e.currentTarget.getAttribute('data-tab');
                    switchTab(tabName);
                });
            });
        }

        isInitialized = true;
        console.log('[PdbSelectionModal] Initialized successfully');
        return true;
    }
    
    // Switch between tabs
    function switchTab(tabName) {
        if (!tabButtons || !tabContents) {
            getModalElements();
        }
        
        // Update tab buttons
        tabButtons.forEach(btn => {
            if (btn.getAttribute('data-tab') === tabName) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
        
        // Update tab contents
        tabContents.forEach(content => {
            if (content.id === `${tabName}-tab`) {
                content.classList.add('active');
            } else {
                content.classList.remove('active');
            }
        });
        
        // Load saved states if switching to saved states tab
        if (tabName === 'saved-states' && savedStates.length === 0) {
            loadSavedStates();
        }
    }
    
    // Load saved states from API
    async function loadSavedStates() {
        const experimentId = window.currentExperimentId;
        if (!experimentId) {
            console.error('[PdbSelectionModal] No experiment ID for loading saved states');
            if (savedStatesList) {
                savedStatesList.innerHTML = '<div style="padding: 2rem; text-align: center; color: #6b7280;"><p>실험 ID를 찾을 수 없습니다.</p></div>';
            }
            return;
        }
        
        try {
            const response = await fetch(`/api/experiments/${experimentId}/viewer-state/`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) {
                throw new Error('저장된 상태를 불러오는데 실패했습니다.');
            }
            
            const data = await response.json();
            savedStates = data.states || [];
            
            renderSavedStates();
        } catch (error) {
            console.error('[PdbSelectionModal] Error loading saved states:', error);
            if (savedStatesList) {
                savedStatesList.innerHTML = `<div style="padding: 2rem; text-align: center; color: #dc2626;"><p>저장된 상태를 불러오는데 실패했습니다.</p></div>`;
            }
        }
    }
    
    // Render saved states with toggle
    function renderSavedStates() {
        if (!savedStatesList) {
            getModalElements();
        }
        if (!savedStatesList) return;
        
        if (savedStates.length === 0) {
            savedStatesList.innerHTML = `
                <div style="padding: 2rem; text-align: center; color: #6b7280;">
                    <p>저장된 상태가 없습니다.</p>
                </div>
            `;
            return;
        }
        
        savedStatesList.innerHTML = savedStates.map((state, index) => {
            const stateDate = state.created_at ? formatPdbDate(state.created_at) : '';
            const fileCount = state.state_data?.loadedFiles?.length || 0;
            
            return `
                <div class="pdb-saved-state-item">
                    <div class="pdb-saved-state-header">
                        <input 
                            type="radio" 
                            name="savedState" 
                            id="savedState${state.state_sid}"
                            value="${state.state_sid}"
                            class="pdb-saved-state-radio"
                        />
                        <label for="savedState${state.state_sid}" class="pdb-saved-state-label">
                            <div class="pdb-saved-state-name">${escapeHtml(state.state_name || '이름 없음')}</div>
                            <div class="pdb-saved-state-meta">
                                ${fileCount > 0 ? `<span>${fileCount}개 파일</span>` : ''}
                                ${stateDate ? `<span>${escapeHtml(stateDate)}</span>` : ''}
                            </div>
                        </label>
                    </div>
                </div>
            `;
        }).join('');
        
        // Attach radio handlers
        savedStatesList.querySelectorAll('.pdb-saved-state-radio').forEach(radio => {
            radio.addEventListener('change', (e) => {
                if (e.target.checked) {
                    const stateId = parseInt(e.target.value);
                    loadSavedState(stateId);
                }
            });
        });
    }
    
    // Load a saved state
    async function loadSavedState(stateId) {
        const experimentId = window.currentExperimentId;
        if (!experimentId) {
            console.error('[PdbSelectionModal] No experiment ID for loading saved state');
            return;
        }
        
        try {
            const response = await fetch(`/api/experiments/${experimentId}/viewer-state/${stateId}/`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) {
                throw new Error('상태를 불러오는데 실패했습니다.');
            }
            
            const state = await response.json();
            const loadedFiles = state.state_data?.loadedFiles || [];
            
            if (loadedFiles.length === 0) {
                if (window.notyf) {
                    window.notyf.warning('저장된 상태에 파일 정보가 없습니다.');
                }
                return;
            }
            
            // Close this modal
            closePdbSelectionModal();
            
            // Open viewer with loaded files
            if (window.MolstarModal) {
                if (typeof window.MolstarModal.openMultiple === 'function') {
                    window.MolstarModal.openMultiple(loadedFiles, experimentId);
                    if (window.notyf) {
                        window.notyf.success('저장된 상태를 불러왔습니다.');
                    }
                } else if (typeof window.MolstarModal.open === 'function') {
                    const firstFile = loadedFiles[0];
                    window.MolstarModal.open(firstFile.url, firstFile.name, experimentId);
                    if (window.notyf) {
                        window.notyf.info('저장된 상태를 불러왔습니다.');
                    }
                }
            }
        } catch (error) {
            console.error('[PdbSelectionModal] Error loading saved state:', error);
            if (window.notyf) {
                window.notyf.error(`상태 불러오기 실패: ${error.message}`);
            }
        }
    }

    // Handle select all (only for current tool's files)
    function handleSelectAll(e) {
        const isChecked = e.target.checked;
        
        // Get files for current tool
        const currentToolFiles = selectedTool 
            ? allPdbFiles.filter(f => (f.tool || '기타') === selectedTool)
            : allPdbFiles;
        
        if (isChecked) {
            // Add all current tool files to selection
            currentToolFiles.forEach(file => {
                if (!selectedPdbFiles.some(f => f.id === file.id)) {
                    selectedPdbFiles.push(file);
                }
            });
        } else {
            // Remove all current tool files from selection
            const currentToolFileIds = currentToolFiles.map(f => f.id);
            selectedPdbFiles = selectedPdbFiles.filter(f => !currentToolFileIds.includes(f.id));
        }
        
        // Update all checkboxes in current view
        if (pdbList) {
            pdbList.querySelectorAll('.pdb-checkbox').forEach(checkbox => {
                checkbox.checked = isChecked;
            });
        }
        
        updateSelectedCount();
        updateConfirmButton();
    }

    // Update selected count
    function updateSelectedCount() {
        if (selectedCountEl) {
            selectedCountEl.textContent = selectedPdbFiles.length;
        }
        
        // Update select all checkbox state
        if (selectAllCheckbox && allPdbFiles.length > 0) {
            selectAllCheckbox.checked = selectedPdbFiles.length === allPdbFiles.length;
            selectAllCheckbox.indeterminate = 
                selectedPdbFiles.length > 0 && selectedPdbFiles.length < allPdbFiles.length;
        }
    }

    // Update confirm button state
    function updateConfirmButton() {
        if (confirmBtn) {
            confirmBtn.disabled = selectedPdbFiles.length === 0;
        }
    }

    // Group PDB files by tool
    function groupFilesByTool(files) {
        const grouped = {};
        files.forEach(file => {
            const tool = file.tool || '기타';
            if (!grouped[tool]) {
                grouped[tool] = [];
            }
            grouped[tool].push(file);
        });
        return grouped;
    }
    
    // Render tool sidebar
    function renderToolSidebar() {
        if (!toolSidebar) {
            getModalElements();
        }
        if (!toolSidebar) return;
        
        const grouped = groupFilesByTool(allPdbFiles);
        const tools = Object.keys(grouped).sort();
        
        if (tools.length === 0) {
            toolSidebar.innerHTML = '';
            return;
        }
        
        // Select first tool if none selected
        if (!selectedTool && tools.length > 0) {
            selectedTool = tools[0];
        }
        
        toolSidebar.innerHTML = tools.map(tool => {
            const count = grouped[tool].length;
            const isActive = selectedTool === tool;
            
            return `
                <button 
                    class="pdb-tool-item ${isActive ? 'active' : ''}" 
                    data-tool="${escapeHtml(tool)}"
                >
                    <span class="pdb-tool-name">${escapeHtml(tool)}</span>
                    <span class="pdb-tool-count">${count}</span>
                </button>
            `;
        }).join('');
        
        // Attach tool selection handlers
        toolSidebar.querySelectorAll('.pdb-tool-item').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const tool = e.currentTarget.getAttribute('data-tool');
                selectTool(tool);
            });
        });
    }
    
    // Select a tool and render its files
    function selectTool(tool) {
        selectedTool = tool;
        renderToolSidebar();
        renderPdbFiles();
    }
    
    // Render PDB files (filtered by selected tool)
    function renderPdbFiles() {
        if (!pdbList) {
            getModalElements();
        }
        if (!pdbList) return;

        if (allPdbFiles.length === 0) {
            pdbList.innerHTML = `
                <div style="padding: 2rem; text-align: center; color: #6b7280;">
                    <p>PDB 파일이 없습니다</p>
                </div>
            `;
            return;
        }
        
        // Filter files by selected tool
        const filteredFiles = selectedTool 
            ? allPdbFiles.filter(f => (f.tool || '기타') === selectedTool)
            : allPdbFiles;
        
        if (filteredFiles.length === 0) {
            pdbList.innerHTML = `
                <div style="padding: 2rem; text-align: center; color: #6b7280;">
                    <p>선택한 도구에 PDB 파일이 없습니다</p>
                </div>
            `;
            return;
        }

        pdbList.innerHTML = filteredFiles.map((file, index) => {
            const isSelected = selectedPdbFiles.some(f => f.id === file.id);
            const fileDate = file.date || file.created_at || '';
            const formattedDate = fileDate ? formatPdbDate(fileDate) : '';
            
            // Find original index in allPdbFiles
            const originalIndex = allPdbFiles.findIndex(f => f.id === file.id);
            
            return `
                <label class="pdb-selection-item">
                    <div class="pdb-selection-content">
                        <div class="pdb-selection-header">
                            <input 
                                type="checkbox" 
                                ${isSelected ? 'checked' : ''}
                                data-pdb-id="${file.id}"
                                data-pdb-index="${originalIndex}"
                                class="pdb-checkbox"
                            />
                            <h4 class="pdb-selection-name">${escapeHtml(file.name)}</h4>
                        </div>
                        <div class="pdb-selection-meta">
                            <span class="pdb-selection-tool">${escapeHtml(file.tool || '기타')}</span>
                            ${formattedDate ? `<span class="pdb-selection-date">${escapeHtml(formattedDate)}</span>` : ''}
                        </div>
                    </div>
                </label>
            `;
        }).join('');

        // Attach checkbox handlers
        pdbList.querySelectorAll('.pdb-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const pdbId = e.target.getAttribute('data-pdb-id');
                const pdbIndex = parseInt(e.target.getAttribute('data-pdb-index'));
                
                // Validate index and find file
                let file = null;
                if (pdbIndex >= 0 && pdbIndex < allPdbFiles.length) {
                    file = allPdbFiles[pdbIndex];
                } else {
                    // Fallback: find by ID
                    file = allPdbFiles.find(f => f.id === pdbId);
                }
                
                if (!file) {
                    console.error('[PdbSelectionModal] File not found for pdbId:', pdbId, 'pdbIndex:', pdbIndex);
                    return;
                }
                
                if (e.target.checked) {
                    if (!selectedPdbFiles.some(f => f.id === pdbId)) {
                        selectedPdbFiles.push(file);
                        console.log('[PdbSelectionModal] Added file to selection:', file);
                    }
                } else {
                    selectedPdbFiles = selectedPdbFiles.filter(f => f.id !== pdbId);
                    console.log('[PdbSelectionModal] Removed file from selection:', pdbId);
                }
                
                updateSelectedCount();
                updateConfirmButton();
            });
        });
    }

    // Format date
    function formatPdbDate(dateStr) {
        if (!dateStr) return '';
        try {
            const date = new Date(dateStr);
            if (isNaN(date.getTime())) return dateStr;
            return date.toLocaleDateString('ko-KR', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch (e) {
            return dateStr;
        }
    }

    // Handle confirm
    function handleConfirm() {
        // Validate selected files
        const validSelectedFiles = selectedPdbFiles.filter(file => file && file.url && file.name);
        
        if (validSelectedFiles.length === 0) {
            console.error('[PdbSelectionModal] No valid files selected. selectedPdbFiles:', selectedPdbFiles);
            if (window.notyf) {
                window.notyf.warning('최소 하나의 파일을 선택해주세요.');
            }
            return;
        }

        console.log('[PdbSelectionModal] Selected files:', validSelectedFiles);
        
        // Close this modal
        closePdbSelectionModal();
        
        // Open viewer modal with selected files
        if (window.MolstarModal) {
            // Validate all files have required properties
            const filesToLoad = validSelectedFiles.filter(file => {
                if (!file || !file.url || !file.name) {
                    console.warn('[PdbSelectionModal] Skipping invalid file:', file);
                    return false;
                }
                return true;
            });
            
            if (filesToLoad.length === 0) {
                console.error('[PdbSelectionModal] No valid files to load');
                if (window.notyf) {
                    window.notyf.error('파일 정보가 올바르지 않습니다.');
                }
                return;
            }
            
            console.log('[PdbSelectionModal] Opening viewer with', filesToLoad.length, 'files:', filesToLoad);
            
            // Get experiment ID
            const experimentId = window.currentExperimentId || null;
            
            // Use openMultiple if available, otherwise open first file
            if (typeof window.MolstarModal.openMultiple === 'function' && filesToLoad.length > 1) {
                window.MolstarModal.openMultiple(filesToLoad, experimentId);
                if (window.notyf) {
                    window.notyf.success(`${filesToLoad.length}개 구조 파일을 로드했습니다.`);
                }
            } else if (typeof window.MolstarModal.open === 'function') {
                const firstFile = filesToLoad[0];
                window.MolstarModal.open(firstFile.url, firstFile.name, experimentId);
                
                if (filesToLoad.length > 1) {
                    if (window.notyf) {
                        window.notyf.info(`${filesToLoad.length}개 파일 중 첫 번째 파일을 열었습니다.`);
                    }
                }
            } else {
                console.error('[PdbSelectionModal] MolstarModal.open or openMultiple not available');
                if (window.notyf) {
                    window.notyf.error('3D 뷰어를 열 수 없습니다. 페이지를 새로고침해주세요.');
                }
            }
        } else {
            console.error('[PdbSelectionModal] MolstarModal is not available');
            if (window.notyf) {
                window.notyf.error('3D 뷰어를 열 수 없습니다. 페이지를 새로고침해주세요.');
            }
        }
    }

    // Open modal with PDB files
    function openPdbSelectionModal(pdbFiles) {
        if (!initPdbSelectionModal()) {
            console.error('[PdbSelectionModal] Failed to initialize');
            return;
        }

        if (!pdbFiles || pdbFiles.length === 0) {
            if (window.notyf) {
                window.notyf.warning('PDB 구조 파일이 없습니다.');
            }
            return;
        }

        // Reset state
        allPdbFiles = pdbFiles.map(file => ({
            id: file.id || file.result_sid || file.file_id,
            name: file.name || file.result_name || 'Unknown',
            url: file.url || (file.id ? `/api/experiments/results/${file.id}/file/` : ''),
            tool: file.tool || '기타',
            date: file.date || file.created_at,
            type: file.type || file.result_type || 'PDB'
        }));
        
        selectedPdbFiles = [];
        selectedTool = null; // Reset selected tool
        
        // Render tool sidebar and files
        renderToolSidebar();
        renderPdbFiles();
        updateSelectedCount();
        updateConfirmButton();
        
        // Switch to PDB files tab
        switchTab('pdb-files');
        
        // Show modal
        if (modal) {
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
            console.log('[PdbSelectionModal] Modal element found, adding active class');
        } else {
            console.error('[PdbSelectionModal] Modal element not found when trying to open');
            getModalElements();
            if (modal) {
                modal.classList.add('active');
                document.body.style.overflow = 'hidden';
                console.log('[PdbSelectionModal] Modal element found after re-fetch, adding active class');
            }
        }
        
        console.log('[PdbSelectionModal] Opened with', allPdbFiles.length, 'files');
    }

    // Close modal
    function closePdbSelectionModal() {
        if (modal) {
            modal.classList.remove('active');
            modal.classList.add('closing');
            setTimeout(() => {
                if (modal) {
                    modal.classList.remove('closing');
                }
            }, 200);
            document.body.style.overflow = '';
        }
        
        // Reset state
        selectedPdbFiles = [];
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = false;
            selectAllCheckbox.indeterminate = false;
        }
    }

    // Refresh saved states (called after saving)
    function refreshSavedStates() {
        if (savedStatesList && savedStatesList.closest('.pdb-tab-content.active')) {
            loadSavedStates();
        }
    }
    
    // Export to window
    window.PdbSelectionModal = {
        open: openPdbSelectionModal,
        close: closePdbSelectionModal,
        init: initPdbSelectionModal,
        refreshSavedStates: refreshSavedStates
    };

    // Auto-initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPdbSelectionModal);
    } else {
        initPdbSelectionModal();
    }

    console.log('[PdbSelectionModal] ===== Script file loaded =====');
})();
