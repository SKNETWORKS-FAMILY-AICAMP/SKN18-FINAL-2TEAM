// Molstar Modal Component JavaScript Logic
console.log('[MolstarModal] ===== Script file loading... =====');

(function() {
    'use strict';
    
    console.log('[MolstarModal] IIFE starting...');

    // State variables
    let isInitialized = false;
    let molstarViewer = null; // Molstar viewer instance

    // DOM elements
    const modalId = 'molstarModal';
    let modal = null;
    let viewerContainer = null;
    let viewerElement = null;
    let modalTitle = null;
    let modalSubtitle = null;

    // Get DOM elements
    function getModalElements() {
        modal = document.getElementById(modalId);
        viewerContainer = document.getElementById('molstar-viewer-container');
        viewerElement = document.getElementById('molstar-viewer');
        modalTitle = document.getElementById('molstarModalTitle');
        modalSubtitle = document.getElementById('molstarModalSubtitle');
    }

    // Initialize modal
    function initMolstarModal() {
        if (isInitialized) return true;
        
        getModalElements();
        
        if (!modal) {
            console.warn('[MolstarModal] Modal element not found');
            return false;
        }
        
        // Close button handlers
        const closeBtns = modal.querySelectorAll('[data-action="close"]');
        closeBtns.forEach(btn => {
            btn.addEventListener('click', closeMolstarModal);
        });
        
        // Close on overlay click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeMolstarModal();
            }
        });
        
        isInitialized = true;
        console.log('[MolstarModal] Initialized successfully');
        return true;
    }

    // Open molstar modal with PDB file
    async function openMolstarModal(fileUrl, fileName) {
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
        
        // Update modal title
        if (modalSubtitle && fileName) {
            modalSubtitle.textContent = fileName;
        }
        
        // Show loading state
        viewerElement.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 100%; flex-direction: column; gap: 1rem;"><div class="spinner" style="border: 4px solid #f3f4f6; border-top: 4px solid #2563eb; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite;"></div><p style="color: #6b7280; font-size: 0.875rem;">PDB 파일을 로드하는 중...</p></div>';
        
        // Add spinner animation if not exists
        if (!document.getElementById('molstar-spinner-style')) {
            const style = document.createElement('style');
            style.id = 'molstar-spinner-style';
            style.textContent = '@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }';
            document.head.appendChild(style);
        }
        
        // Show modal first
        modal.classList.add('active');
        
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
    }

    // Export to window immediately
    console.log('[MolstarModal] Assigning window.MolstarModal...');
    window.MolstarModal = {
        open: openMolstarModal,
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
