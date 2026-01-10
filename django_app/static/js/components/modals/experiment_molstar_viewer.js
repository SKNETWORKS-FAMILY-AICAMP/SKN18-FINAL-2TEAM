// Molstar Modal Component JavaScript Logic
console.log('[MolstarModal] ===== Script file loading... =====');

(function() {
    'use strict';
    
    console.log('[MolstarModal] IIFE starting...');

    // State variables
    let isInitialized = false;
    let molstarViewer = null; // Molstar viewer instance
    let loadedFiles = []; // Track loaded files
    let currentExperimentId = null; // Current experiment ID

    // DOM elements
    const modalId = 'molstarModal';
    let modal = null;
    let viewerContainer = null;
    let viewerElement = null;
    let modalTitle = null;
    let saveStateModal = null;
    let saveStateNameInput = null;

    // Get DOM elements
    function getModalElements() {
        modal = document.getElementById(modalId);
        viewerContainer = document.getElementById('molstar-viewer-container');
        viewerElement = document.getElementById('molstar-viewer');
        modalTitle = document.getElementById('molstarModalTitle');
        saveStateModal = document.getElementById('molstarSaveStateModal');
        saveStateNameInput = document.getElementById('viewerStateName');
    }

    // Initialize modal
    function initMolstarModal() {
        if (isInitialized) return true;
        
        getModalElements();
        
        if (!modal) {
            console.warn('[MolstarModal] Modal element not found');
            return false;
        }
        
        // Close button handlers - show save confirmation
        const closeBtns = modal.querySelectorAll('[data-action="close"]');
        closeBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                showSaveStateConfirmation();
            });
        });
        
        // Close on overlay click - show save confirmation
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                e.preventDefault();
                e.stopPropagation();
                showSaveStateConfirmation(e);
            }
        });
        
        // Save state modal handlers
        if (saveStateModal) {
            const confirmBtn = document.getElementById('confirmSaveStateBtn');
            const closeWithoutSaveBtn = document.getElementById('closeWithoutSaveBtn');
            const closeSaveBtns = saveStateModal.querySelectorAll('[data-action="close-save-modal"]');
            
            // Prevent save modal clicks from propagating to viewer modal
            saveStateModal.addEventListener('click', (e) => {
                e.stopPropagation(); // Prevent event from reaching viewer modal
            });
            
            // Close without save button - close both modals without saving
            if (closeWithoutSaveBtn) {
                closeWithoutSaveBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    closeSaveStateModal();
                    // Stop the protector interval
                    if (window._viewerModalProtector) {
                        clearInterval(window._viewerModalProtector);
                        window._viewerModalProtector = null;
                    }
                    // Close viewer modal
                    setTimeout(() => {
                        closeMolstarModal();
                    }, 200);
                });
            }
            
            // Confirm button - save and close viewer
            if (confirmBtn) {
                confirmBtn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    const saveSuccess = await saveViewerState();
                    closeSaveStateModal();
                    // If save was successful, close viewer modal too
                    if (saveSuccess) {
                        // Stop the protector interval
                        if (window._viewerModalProtector) {
                            clearInterval(window._viewerModalProtector);
                            window._viewerModalProtector = null;
                        }
                        // Close viewer modal after a short delay
                        setTimeout(() => {
                            closeMolstarModal();
                        }, 300);
                    }
                });
            }
            
            // X button - same as close without save (close both modals)
            closeSaveBtns.forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    closeSaveStateModal();
                    // Stop the protector interval
                    if (window._viewerModalProtector) {
                        clearInterval(window._viewerModalProtector);
                        window._viewerModalProtector = null;
                    }
                    // Close viewer modal
                    setTimeout(() => {
                        closeMolstarModal();
                    }, 200);
                });
            });
            
            // Close on overlay click - same as close without save (close both modals)
            saveStateModal.addEventListener('click', (e) => {
                if (e.target === saveStateModal) {
                    e.preventDefault();
                    e.stopPropagation();
                    closeSaveStateModal();
                    // Stop the protector interval
                    if (window._viewerModalProtector) {
                        clearInterval(window._viewerModalProtector);
                        window._viewerModalProtector = null;
                    }
                    // Close viewer modal
                    setTimeout(() => {
                        closeMolstarModal();
                    }, 200);
                }
            });
        }
        
        isInitialized = true;
        console.log('[MolstarModal] Initialized successfully');
        return true;
    }

    // Show save state confirmation modal (on top of viewer modal)
    function showSaveStateConfirmation(e) {
        // Prevent event propagation to avoid closing viewer modal
        if (e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        if (!saveStateModal) {
            getModalElements();
        }
        if (!saveStateModal) {
            console.warn('[MolstarModal] Save state modal not found, closing directly');
            closeMolstarModal();
            return;
        }
        
        // CRITICAL: Ensure viewer modal stays open BEFORE opening save modal
        if (!modal) {
            getModalElements();
        }
        
        if (modal) {
            // Force viewer modal to stay open - ensure it's visible
            if (!modal.classList.contains('active')) {
                console.warn('[MolstarModal] Viewer modal was not active, forcing it active');
                modal.classList.add('active');
            }
            modal.style.display = 'flex';
            
            // Use setInterval to continuously check and restore active class
            if (!window._viewerModalProtector) {
                window._viewerModalProtector = setInterval(() => {
                    if (modal && saveStateModal && saveStateModal.classList.contains('active')) {
                        // Save modal is open, ensure viewer modal stays open
                        if (!modal.classList.contains('active')) {
                            console.warn('[MolstarModal] Restoring active class to viewer modal');
                            modal.classList.add('active');
                        }
                        if (window.getComputedStyle(modal).display === 'none') {
                            console.warn('[MolstarModal] Restoring display to viewer modal');
                            modal.style.display = 'flex';
                        }
                    }
                }, 100); // Check every 100ms
            }
            
            console.log('[MolstarModal] Viewer modal state before opening save modal:', {
                hasActive: modal.classList.contains('active'),
                display: modal.style.display,
                computedDisplay: window.getComputedStyle(modal).display
            });
        } else {
            console.error('[MolstarModal] Viewer modal element not found!');
        }
        
        // Reset input
        if (saveStateNameInput) {
            saveStateNameInput.value = '';
        }
        
        // Show save modal as overlay on top of viewer modal
        saveStateModal.style.display = 'flex';
        saveStateModal.classList.add('active');
        
        console.log('[MolstarModal] Save state modal opened, viewer modal should remain open');
        // Don't change body overflow - viewer modal is still open
    }
    
    // Close save state modal
    function closeSaveStateModal() {
        if (saveStateModal) {
            saveStateModal.classList.remove('active');
            setTimeout(() => {
                if (saveStateModal) {
                    saveStateModal.style.display = 'none';
                }
            }, 200);
            
            // Stop the protector interval when save modal closes
            if (window._viewerModalProtector) {
                clearInterval(window._viewerModalProtector);
                window._viewerModalProtector = null;
            }
            
            // Only keep viewer modal open if save was NOT successful (cancelled)
            // If save was successful, viewer will be closed by the confirm button handler
            console.log('[MolstarModal] Save modal closed');
        }
    }
    
    // Save viewer state to DB
    async function saveViewerState() {
        if (!currentExperimentId) {
            // Try to get from window
            currentExperimentId = window.currentExperimentId;
        }
        
        if (!currentExperimentId) {
            console.error('[MolstarModal] No experiment ID available for saving state');
            if (window.notyf) {
                window.notyf.error('실험 ID를 찾을 수 없습니다.');
            }
            return;
        }
        
        try {
            // Collect current viewer state
            const stateData = {
                loadedFiles: loadedFiles,
                timestamp: new Date().toISOString()
            };
            
            // Try to get viewer settings if available
            if (molstarViewer) {
                try {
                    const plugin = molstarViewer.plugin || molstarViewer;
                    if (plugin.managers && plugin.managers.structure) {
                        // Get loaded structures info
                        const structures = [];
                        if (plugin.managers.structure.hierarchy) {
                            const current = plugin.managers.structure.hierarchy.current;
                            if (current && current.structures) {
                                current.structures.forEach((struct, idx) => {
                                    structures.push({
                                        index: idx,
                                        name: struct.name || `Structure ${idx + 1}`
                                    });
                                });
                            }
                        }
                        stateData.structures = structures;
                    }
                } catch (e) {
                    console.warn('[MolstarModal] Could not collect viewer settings:', e);
                }
            }
            
            const stateName = saveStateNameInput ? saveStateNameInput.value.trim() : '';
            
            // Save to DB
            const response = await fetch(`/api/experiments/${currentExperimentId}/viewer-state/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    state_name: stateName || null,
                    state_data: stateData
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || '상태 저장에 실패했습니다.');
            }
            
            const result = await response.json();
            console.log('[MolstarModal] State saved:', result);
            
            if (window.notyf) {
                window.notyf.success('작업 상태가 저장되었습니다.');
            }
            
            // Refresh saved states in PDB selection modal if it exists
            if (window.PdbSelectionModal && typeof window.PdbSelectionModal.refreshSavedStates === 'function') {
                window.PdbSelectionModal.refreshSavedStates();
            }
            
            return true; // Return success
        } catch (error) {
            console.error('[MolstarModal] Error saving state:', error);
            if (window.notyf) {
                window.notyf.error(`상태 저장 실패: ${error.message}`);
            }
            return false; // Return failure
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
        // Fallback: try to get from meta tag
        const metaTag = document.querySelector('meta[name="csrf-token"]');
        if (metaTag) {
            return metaTag.getAttribute('content');
        }
        return '';
    }
    
    // Open molstar modal with PDB file
    async function openMolstarModal(fileUrl, fileName, experimentId = null) {
        // Store experiment ID
        if (experimentId) {
            currentExperimentId = experimentId;
        } else {
            currentExperimentId = window.currentExperimentId;
        }
        
        // Reset loaded files
        loadedFiles = [];
        
        // Add first file to loaded files
        if (fileUrl && fileName) {
            loadedFiles.push({
                url: fileUrl,
                name: fileName
            });
        }
        console.log('[MolstarModal] Opening modal with file:', fileUrl);
        
        // Validate fileUrl first
        if (!fileUrl || fileUrl.trim() === '') {
            console.error('[MolstarModal] Invalid file URL provided:', fileUrl);
            if (window.notyf) {
                window.notyf.error('파일 URL이 제공되지 않았습니다.');
        }
            return;
    }

        // Ensure initialization
        if (!isInitialized) {
            initMolstarModal();
        }
        
            getModalElements();
        
        if (!modal || !viewerElement) {
            console.error('[MolstarModal] Modal or viewer element not found');
            return;
        }
        
        // Modal title is fixed, no subtitle update needed
        
        // Show loading state
        viewerElement.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 100%; flex-direction: column; gap: 1rem;"><div class="spinner" style="border: 4px solid #f3f4f6; border-top: 4px solid #2563eb; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite;"></div><p style="color: #6b7280; font-size: 0.875rem;">PDB 파일을 로드하는 중...</p></div>';
        
        // Add spinner animation if not exists
        if (!document.getElementById('molstar-spinner-style')) {
            const style = document.createElement('style');
            style.id = 'molstar-spinner-style';
            style.textContent = '@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }';
            document.head.appendChild(style);
        }
        
        // Show modal first - ensure it stays open
        modal.classList.add('active');
        modal.style.display = 'flex';
        
        // Set up protection to prevent modal from closing when save modal opens
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                    // If active class is removed while save modal is open, restore it
                    if (!modal.classList.contains('active') && saveStateModal && saveStateModal.classList.contains('active')) {
                        console.warn('[MolstarModal] Active class was removed while save modal is open, restoring it');
                        modal.classList.add('active');
                        modal.style.display = 'flex';
                    }
                }
            });
        });
        
        observer.observe(modal, {
            attributes: true,
            attributeFilter: ['class']
        });
        
        // Store observer for cleanup
        if (!window._molstarModalObserver) {
            window._molstarModalObserver = observer;
        }
        
        // Wait a bit for modal to be visible
        await new Promise(resolve => setTimeout(resolve, 100));
        
        // Check if molstar is available
        if (typeof molstar === 'undefined') {
            console.error('[MolstarModal] Molstar library not loaded');
            viewerElement.innerHTML = '<div class="error-message" style="padding: 20px; text-align: center; color: #dc2626;">Molstar viewer를 로드할 수 없습니다. 페이지를 새로고침해주세요.</div>';
            return;
                }
        
        try {
            // Dispose existing viewer if exists
            if (molstarViewer) {
                try {
                    molstarViewer.dispose();
                } catch (error) {
                    console.warn('[MolstarModal] Error disposing previous viewer:', error);
                }
                molstarViewer = null;
            }
            
            // Clear viewer element for new viewer
            viewerElement.innerHTML = '';
            
            console.log('[MolstarModal] Creating viewer...');
            
            // Create new viewer
            molstarViewer = await molstar.Viewer.create('molstar-viewer', {
                layoutIsExpanded: false,
                layoutShowControls: true,
                layoutShowSequence: true,
                layoutShowLog: false,
                layoutShowLeftPanel: true,
                viewportShowExpand: true,
                viewportShowSelectionMode: false,
                viewportShowAnimation: false,
            });
            
            console.log('[MolstarModal] Viewer created:', molstarViewer);
            console.log('[MolstarModal] Loading PDB file from:', fileUrl);
            
            // Validate fileUrl
            if (!fileUrl || fileUrl.trim() === '') {
                throw new Error('파일 URL이 제공되지 않았습니다.');
            }
            
            // Load PDB file - try multiple methods
            let loadSuccess = false;
            
            // Method 1: Try loadStructureFromUrl (standard molstar API)
            if (typeof molstarViewer.loadStructureFromUrl === 'function') {
                try {
                    console.log('[MolstarModal] Method 1: Using loadStructureFromUrl...');
                    await molstarViewer.loadStructureFromUrl(fileUrl, 'pdb');
                    console.log('[MolstarModal] Structure loaded successfully via loadStructureFromUrl');
                    loadSuccess = true;
                } catch (urlError) {
                    console.warn('[MolstarModal] loadStructureFromUrl failed:', urlError);
                }
        }
        
            // Method 2: Fetch and load via plugin API
            if (!loadSuccess) {
                try {
                    console.log('[MolstarModal] Method 2: Fetching file and loading via plugin API...');
                    const response = await fetch(fileUrl);
                    
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    
                    const pdbContent = await response.text();
                    console.log('[MolstarModal] PDB file fetched, content length:', pdbContent.length);
                    
                    if (!pdbContent || pdbContent.trim().length === 0) {
                        throw new Error('PDB 파일 내용이 비어있습니다.');
            }
            
                    // Validate PDB content (should start with ATOM, HEADER, etc.)
                    const firstLine = pdbContent.trim().split('\n')[0];
                    console.log('[MolstarModal] First line of PDB:', firstLine.substring(0, 50));
                    
                    // Load via plugin API
                    const plugin = molstarViewer.plugin || molstarViewer;
                    if (plugin.managers && plugin.managers.structure && plugin.managers.structure.hierarchy) {
                        await plugin.managers.structure.hierarchy.load({
                            data: { data: pdbContent, format: 'pdb' },
                            name: fileName || 'structure'
                        });
                        console.log('[MolstarModal] Structure loaded via plugin hierarchy.load');
                        loadSuccess = true;
                    } else {
                        throw new Error('Plugin structure manager not available');
                    }
                } catch (fetchError) {
                    console.error('[MolstarModal] Fetch and load failed:', fetchError);
                }
            }
            
            if (!loadSuccess) {
                throw new Error('모든 로딩 방법이 실패했습니다. 파일 URL을 확인해주세요.');
            }
            
            // Wait for structure to be processed and rendered
            console.log('[MolstarModal] Waiting for structure to render...');
            await new Promise(resolve => setTimeout(resolve, 2000));
            
            // Auto-fit and center the structure
            try {
                const plugin = molstarViewer.plugin || molstarViewer;
                
                if (plugin.managers && plugin.managers.camera) {
                    // Reset camera
                    plugin.managers.camera.reset();
                    console.log('[MolstarModal] Camera reset');
                    
                    // Wait a bit more for structure to be fully ready
                    await new Promise(resolve => setTimeout(resolve, 1000));
                    
                    // Focus on structure
                    if (plugin.managers.structure && plugin.managers.structure.hierarchy) {
                        const current = plugin.managers.structure.hierarchy.current;
                        if (current && current.structures && current.structures.length > 0) {
                            const structure = current.structures[0];
                            if (structure && structure.boundary && structure.boundary.sphere) {
                                plugin.managers.camera.focusSphere(structure.boundary.sphere);
                                console.log('[MolstarModal] Structure focused on sphere');
                            } else {
                                // Try alternative focus method
                                plugin.managers.camera.reset();
                                console.log('[MolstarModal] Camera reset (alternative)');
        }
                        }
                    }
                }
            } catch (cameraError) {
                console.warn('[MolstarModal] Could not reset camera:', cameraError);
    }

            // Handle resize
            try {
                const plugin = molstarViewer.plugin || molstarViewer;
                if (plugin.canvas3d && typeof plugin.canvas3d.handleResize === 'function') {
                    plugin.canvas3d.handleResize();
                } else if (typeof molstarViewer.handleResize === 'function') {
                    molstarViewer.handleResize();
        }
            } catch (resizeError) {
                console.warn('[MolstarModal] Could not handle resize:', resizeError);
            }
            
            console.log('[MolstarModal] PDB file loaded and rendered successfully');
            
            console.log('[MolstarModal] PDB file loaded and rendered successfully');
        } catch (error) {
            console.error('[MolstarModal] Error loading PDB file:', error);
            viewerElement.innerHTML = `
                <div class="error-message" style="padding: 20px; text-align: center; color: #dc2626;">
                    <p style="font-weight: 600; margin-bottom: 0.5rem;">PDB 파일을 로드하는 중 오류가 발생했습니다</p>
                    <p style="font-size: 0.875rem; color: #6b7280;">${error.message || '알 수 없는 오류'}</p>
                    <p style="font-size: 0.75rem; color: #9ca3af; margin-top: 0.5rem;">파일 URL: ${fileUrl}</p>
                </div>
            `;
        }
    }

    // Close molstar modal
    function closeMolstarModal() {
        console.log('[MolstarModal] closeMolstarModal called - this should NOT happen when save modal opens');
        console.trace('[MolstarModal] Stack trace:');
        
        getModalElements();
        
        if (!modal) return;
        
        modal.classList.remove('active');
        
        // Dispose viewer if exists
        if (molstarViewer) {
            try {
                molstarViewer.dispose();
            } catch (error) {
                console.warn('[MolstarModal] Error disposing viewer:', error);
            }
            molstarViewer = null;
        }
        
        // Clear viewer content
        if (viewerElement) {
            viewerElement.innerHTML = '';
        }
        
        // Reset state
        loadedFiles = [];
        currentExperimentId = null;
    }

    // Open molstar modal with multiple PDB files
    async function openMolstarModalMultiple(files, experimentId = null) {
        // Store experiment ID
        if (experimentId) {
            currentExperimentId = experimentId;
        } else {
            currentExperimentId = window.currentExperimentId;
        }
        
        // Store loaded files
        loadedFiles = files.map(f => ({
            url: f.url,
            name: f.name
        }));
        if (!files || files.length === 0) {
            console.error('[MolstarModal] No files provided for multiple load');
            return;
        }

        console.log('[MolstarModal] Opening modal with multiple files:', files.length);
        
        // Open with first file first
        const firstFile = files[0];
        if (!firstFile || !firstFile.url || !firstFile.name) {
            console.error('[MolstarModal] First file is invalid:', firstFile);
            return;
        }

        // Open modal with first file
        await openMolstarModal(firstFile.url, firstFile.name);
        
        // Wait for first file to load
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        // Load remaining files
        if (files.length > 1 && molstarViewer) {
            console.log('[MolstarModal] Loading additional files:', files.length - 1);
            try {
                const plugin = molstarViewer.plugin || molstarViewer;
                
                for (let i = 1; i < files.length; i++) {
                    const file = files[i];
                    if (!file || !file.url) {
                        console.warn('[MolstarModal] Skipping invalid file at index', i, file);
                        continue;
                    }
                    
                    console.log(`[MolstarModal] Loading file ${i + 1}/${files.length}:`, file.name);
                    
                    try {
                        // Try loadStructureFromUrl for additional files
                        if (typeof molstarViewer.loadStructureFromUrl === 'function') {
                            await molstarViewer.loadStructureFromUrl(file.url, 'pdb');
                            console.log(`[MolstarModal] File ${i + 1} (${file.name}) loaded successfully`);
                        } else {
                            // Fallback: fetch and load
                            const response = await fetch(file.url);
                            if (response.ok) {
                                const pdbContent = await response.text();
                                if (plugin.managers && plugin.managers.structure && plugin.managers.structure.hierarchy) {
                                    await plugin.managers.structure.hierarchy.load({
                                        data: { data: pdbContent, format: 'pdb' },
                                        name: file.name || `Structure ${i + 1}`
                                    });
                                    console.log(`[MolstarModal] File ${i + 1} (${file.name}) loaded via plugin`);
                                }
                            }
                        }
                        
                        // Wait a bit between loads
                        await new Promise(resolve => setTimeout(resolve, 500));
                    } catch (fileError) {
                        console.error(`[MolstarModal] Error loading file ${i + 1}:`, fileError);
                    }
                }
                
                // Auto-fit after all files loaded
                await new Promise(resolve => setTimeout(resolve, 1000));
                try {
                    if (plugin.managers && plugin.managers.camera) {
                        plugin.managers.camera.reset();
                    }
                } catch (cameraError) {
                    console.warn('[MolstarModal] Could not reset camera after multiple loads:', cameraError);
                }
                
                console.log('[MolstarModal] All files loaded successfully');
            } catch (error) {
                console.error('[MolstarModal] Error loading multiple files:', error);
            }
        }
    }

    // Export to window immediately
    console.log('[MolstarModal] Assigning window.MolstarModal...');
    window.MolstarModal = {
        open: openMolstarModal,
        openMultiple: openMolstarModalMultiple,
        close: closeMolstarModal,
        init: initMolstarModal,
        isReady: function() {
            return isInitialized;
        }
    };
    console.log('[MolstarModal] window.MolstarModal assigned:', window.MolstarModal);

    // Initialize when DOM is ready
    function tryInit() {
        if (initMolstarModal()) {
            document.dispatchEvent(new Event('molstarModal:ready'));
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

    console.log('[MolstarModal] Script loaded, window.MolstarModal available');
})();
