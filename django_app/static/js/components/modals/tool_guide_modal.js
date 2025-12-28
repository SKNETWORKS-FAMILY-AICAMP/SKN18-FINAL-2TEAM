// Tool Guide Modal JavaScript

(function() {
    'use strict';

const modalId = 'toolGuideModal';
let currentTool = null;

// DOM elements (will be initialized when DOM is ready)
let modal = null;
let modalTitle = null;
let modalSubtitle = null;
let overviewEl = null;
let usageList = null;
let tipsEl = null;
let addToPipelineBtn = null;
let modalClickHandler = null; // Modal click handler for event delegation

// Initialize DOM elements
function initDOMElements() {
    modal = document.getElementById(modalId);
    modalTitle = document.getElementById('toolGuideModalTitle');
    modalSubtitle = document.getElementById('toolGuideModalSubtitle');
    overviewEl = document.getElementById('toolGuideOverview');
    usageList = document.getElementById('toolGuideUsageList');
    tipsEl = document.getElementById('toolGuideTips');
    addToPipelineBtn = document.getElementById('toolGuideAddToPipelineBtn');
    
    return !!modal; // Return true if modal was found
}

// Setup modal event listeners (called when modal opens)
function setupModalEventListeners() {
    if (!modal) {
        console.error('[ToolGuideModal] Modal not found in setupModalEventListeners');
        return;
    }

    // Close button
    const closeBtn = modal.querySelector('.modal-close-btn');
    if (closeBtn) {
        // Remove existing listeners
        const newCloseBtn = closeBtn.cloneNode(true);
        closeBtn.parentNode.replaceChild(newCloseBtn, closeBtn);
        newCloseBtn.addEventListener('click', () => {
            closeModal();
        });
    }

    // Remove existing modal click handler if any
    if (modalClickHandler) {
        modal.removeEventListener('click', modalClickHandler);
    }
    
    // Event delegation for modal clicks (handles overlay, buttons, etc.)
    modalClickHandler = (e) => {
        // Check if clicked element or its parent is the add to pipeline button
        const clickedBtn = e.target.closest('#toolGuideAddToPipelineBtn');
        const isButton = e.target.id === 'toolGuideAddToPipelineBtn';
        const isButtonIcon = e.target.closest('#toolGuideAddToPipelineBtn i');
        const isButtonChild = e.target.closest('#toolGuideAddToPipelineBtn');
        const isButtonText = e.target.parentElement?.id === 'toolGuideAddToPipelineBtn';
        
        if (clickedBtn || isButton || isButtonIcon || isButtonChild || isButtonText) {
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
            handleAddToPipeline();
            return false;
        }
        
        // Handle overlay click
        if (e.target === modal) {
            closeModal();
        }
    };
    modal.addEventListener('click', modalClickHandler, true);
    modal.addEventListener('click', modalClickHandler, false);

    // Footer close button
    const footerCloseBtn = modal.querySelector('[data-action="close"]');
    if (footerCloseBtn) {
        // Remove existing listeners
        const newFooterCloseBtn = footerCloseBtn.cloneNode(true);
        footerCloseBtn.parentNode.replaceChild(newFooterCloseBtn, footerCloseBtn);
        newFooterCloseBtn.addEventListener('click', () => {
            closeModal();
        });
    }

    // Add to pipeline button - use attachButtonEventListeners function
    const btn = document.getElementById('toolGuideAddToPipelineBtn');
    
    if (btn) {
        attachButtonEventListeners(btn);
    } else {
        console.error('[ToolGuideModal] addToPipelineBtn NOT FOUND in DOM!');
    }
}

// Initialize modal (for initial setup)
function initToolGuideModal() {
    // Initialize DOM elements if not already done
    if (!modal) {
        initDOMElements();
    }
    if (!modal) {
        console.warn('[ToolGuideModal] Modal element not found in initToolGuideModal');
        return false;
    }
    
    // Event listeners will be set up when modal opens
    return true;
}

// Open modal
function openToolGuideModal(tool) {
    // Ensure DOM elements are initialized
    if (!modal) {
        initDOMElements();
    }
    if (!modal || !tool) {
        console.error('[ToolGuideModal] Modal or tool data not available', { modal, tool });
        return;
    }

    currentTool = tool;
    
    // Re-initialize DOM elements when modal opens
    initDOMElements();
    
    // Update title immediately (UI first)
    if (modalTitle) {
        modalTitle.textContent = `${tool.name} 사용 가이드`;
    }
    if (modalSubtitle) {
        modalSubtitle.textContent = tool.category || '';
    }

    // Show modal FIRST (UI appears immediately)
    modal.classList.add('active');
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    
    // Setup event listeners FIRST (before updating button content)
    setupModalEventListeners();
    
    // Show loading state
    showLoadingState();
    
    // Load guide content asynchronously (API call or render existing data)
    loadGuideContent(tool);
}

// Show loading state in modal
function showLoadingState() {
    if (overviewEl) {
        overviewEl.textContent = '가이드를 불러오는 중...';
    }
    
    if (usageList) {
        usageList.innerHTML = '<div class="guide-loading">로딩 중...</div>';
    }
    
    if (tipsEl) {
        tipsEl.textContent = '';
    }
}

// Load guide content (async - can be API call or immediate render)
async function loadGuideContent(tool) {
    // Check if guide data already exists in tool object
    if (tool.guide && tool.guide.overview) {
        // Render immediately if guide data exists
        renderGuideContent(tool);
        return;
    }
    
    // If guide data doesn't exist, try to fetch from API
    try {
        // Try to fetch guide from API endpoint
        // Note: Adjust API endpoint based on your backend implementation
        const toolId = tool.id || tool.name;
        const apiEndpoint = `/api/tools/${toolId}/guide/` || `/api/tools/${encodeURIComponent(tool.name)}/guide/`;
        
        const response = await fetch(apiEndpoint, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
        });
        
        if (response.ok) {
            const guideData = await response.json();
            
            // Merge guide data with tool object
            tool.guide = guideData.guide || guideData;
            
            // Render guide content
            renderGuideContent(tool);
        } else {
            // Fallback: render with available data or default message
            renderGuideContent(tool);
        }
    } catch (error) {
        console.error('[ToolGuideModal] Error fetching guide from API:', error);
        // Fallback: render with available data or default message
        renderGuideContent(tool);
    }
}

// Close modal
function closeModal() {
    if (!modal) return;
    
    // Remove active class and hide modal
    modal.classList.remove('active');
    modal.style.display = 'none';
    document.body.style.overflow = '';
    currentTool = null;
}

// Render guide content
function renderGuideContent(tool) {
    // Overview
    if (overviewEl) {
        overviewEl.textContent = tool.guide?.overview || tool.description || '';
    }

    // Usage steps
    if (usageList && tool.guide?.usage) {
        usageList.innerHTML = tool.guide.usage.map((step, index) => {
            // Remove leading number if present
            const stepText = step.replace(/^\d+\.\s*/, '');
            return `
                <div class="guide-step">
                    <div class="guide-step-number">${index + 1}</div>
                    <p class="guide-step-text">${escapeHtml(stepText)}</p>
                </div>
            `;
        }).join('');
    }

    // Tips
    if (tipsEl) {
        tipsEl.textContent = tool.guide?.tips || '';
    }

    // Update add to pipeline button text based on selection status
    updateAddToPipelineButton(tool);
}

// Attach event listeners to button (reusable function)
function attachButtonEventListeners(buttonElement) {
    if (!buttonElement) {
        console.error('[ToolGuideModal] Cannot attach listeners to null button');
        return;
    }
    
    // Clone to remove any existing listeners
    const newBtn = buttonElement.cloneNode(true);
    buttonElement.parentNode.replaceChild(newBtn, buttonElement);
    
    // Store reference
    addToPipelineBtn = newBtn;
    
    // Create click handler
    const clickHandler = (e) => {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        handleAddToPipeline();
        return false;
    };
    
    // Add all event listeners with multiple phases and options
    newBtn.addEventListener('click', clickHandler, true); // Capture phase
    newBtn.addEventListener('click', clickHandler, false); // Bubble phase
    
    // Store handler reference for debugging
    newBtn._toolGuideClickHandler = clickHandler;
    
    // Also add touch events for mobile
    newBtn.addEventListener('touchend', (e) => {
        e.preventDefault();
        e.stopPropagation();
        handleAddToPipeline();
    }, true);
    
    // Force button to be clickable
    newBtn.style.pointerEvents = 'auto';
    newBtn.style.cursor = 'pointer';
    newBtn.setAttribute('tabindex', '0');
    
    // Add keyboard support
    newBtn.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            handleAddToPipeline();
        }
    });
    
    return newBtn;
}

// Update add to pipeline button
function updateAddToPipelineButton(tool) {
    // Re-fetch button from DOM in case it was replaced
    const btn = document.getElementById('toolGuideAddToPipelineBtn');
    if (!btn) {
        console.error('[ToolGuideModal] addToPipelineBtn not found in updateAddToPipelineButton!');
        return;
    }
    
    const isSelected = window.ExperimentPage && 
                      window.ExperimentPage.selectedTools && 
                      window.ExperimentPage.selectedTools.includes(tool.id);
    
    // Update button content using innerHTML (this will remove event listeners)
    if (isSelected) {
        btn.innerHTML = '<i class="fas fa-times"></i> 파이프라인에서 제거';
    } else {
        btn.innerHTML = '<i class="fas fa-plus"></i> 파이프라인에 추가';
    }
    
    // CRITICAL: Re-attach event listeners after innerHTML change
    // innerHTML changes remove all event listeners, so we must re-attach them
    attachButtonEventListeners(btn);
}

// Handle add to pipeline (always add, never remove)
function handleAddToPipeline() {
    if (!currentTool) {
        console.error('[ToolGuideModal] No currentTool available!');
        return;
    }

    // Check if tool is already selected
    let isAlreadySelected = false;
    if (window.ExperimentPage && window.ExperimentPage.selectedTools) {
        isAlreadySelected = window.ExperimentPage.selectedTools.includes(currentTool.id);
    } else if (typeof selectedTools !== 'undefined' && Array.isArray(selectedTools)) {
        // Fallback: check global selectedTools if ExperimentPage.selectedTools is not available
        isAlreadySelected = selectedTools.includes(currentTool.id);
    }

    // If already selected, just close modal (no notyf message)
    if (isAlreadySelected) {
        // Close modal immediately (no notyf message)
        closeModal();
        return;
    }

    // Tool is not selected, so close modal first, then add it
    // Save tool info before closing modal (closeModal sets currentTool to null)
    const toolToAdd = {
        id: currentTool.id,
        name: currentTool.name
    };
    
    // Close modal first
    closeModal();
    
    // Then add the tool after a short delay to ensure modal is closed
    if (window.ExperimentPage && window.ExperimentPage.toggleToolSelection) {
        // Use setTimeout to ensure modal close animation completes
        setTimeout(() => {
            // Since tool is not selected, toggleToolSelection will add it
            window.ExperimentPage.toggleToolSelection(toolToAdd.id);
            
            // Verify the tool was added and show notification
            // Use a longer delay to ensure toggleToolSelection has completed
            setTimeout(() => {
                let isNowSelected = false;
                
                // Check window.ExperimentPage.selectedTools (now using getter)
                if (window.ExperimentPage && window.ExperimentPage.selectedTools) {
                    isNowSelected = window.ExperimentPage.selectedTools.includes(toolToAdd.id);
                }
                
                // Show success notification
                if (window.notyf) {
                    if (isNowSelected) {
                        window.notyf.success(`${toolToAdd.name}이(가) 파이프라인에 추가되었습니다.`);
                    } else {
                        console.warn('[ToolGuideModal] Tool was not added. Current selectedTools:', window.ExperimentPage?.selectedTools);
                        window.notyf.error(`${toolToAdd.name}을(를) 파이프라인에 추가하는데 실패했습니다.`);
                    }
                }
            }, 50); // Additional delay to ensure state is updated
        }, 100); // Small delay to ensure modal is closed
    } else {
        console.error('[ToolGuideModal] ExperimentPage.toggleToolSelection not available!');
        if (window.notyf) {
            window.notyf.error('도구 선택 기능을 사용할 수 없습니다.');
        }
    }
}

// Escape HTML
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Debug function to check button event listeners
function debugButtonEventListeners() {
    console.log('[ToolGuideModal Debug] ====== Starting Debug Check ======');
    
    // Check if ToolGuideModal is available
    console.log('[ToolGuideModal Debug] window.ToolGuideModal exists:', typeof window.ToolGuideModal !== 'undefined');
    if (typeof window.ToolGuideModal !== 'undefined') {
        console.log('[ToolGuideModal Debug] window.ToolGuideModal:', window.ToolGuideModal);
    }
    
    // Check modal element
    const modalEl = document.getElementById('toolGuideModal');
    console.log('[ToolGuideModal Debug] Modal element exists:', !!modalEl);
    console.log('[ToolGuideModal Debug] Modal is visible:', modalEl ? window.getComputedStyle(modalEl).display !== 'none' : false);
    
    // Check button
    const btn = document.getElementById('toolGuideAddToPipelineBtn');
    if (!btn) {
        console.error('[ToolGuideModal Debug] Button not found!');
        console.error('[ToolGuideModal Debug] Searching in modal:', modalEl ? modalEl.querySelector('#toolGuideAddToPipelineBtn') : 'Modal not found');
        return;
    }
    
    console.log('[ToolGuideModal Debug] ====== Button Event Listener Check ======');
    console.log('[ToolGuideModal Debug] Button element:', btn);
    console.log('[ToolGuideModal Debug] Button ID:', btn.id);
    console.log('[ToolGuideModal Debug] Button classes:', btn.className);
    console.log('[ToolGuideModal Debug] Button innerHTML:', btn.innerHTML);
    console.log('[ToolGuideModal Debug] Button has stored handler:', !!btn._toolGuideClickHandler);
    console.log('[ToolGuideModal Debug] Button parent:', btn.parentElement);
    console.log('[ToolGuideModal Debug] Button is visible:', btn.offsetParent !== null);
    
    const computedStyle = window.getComputedStyle(btn);
    console.log('[ToolGuideModal Debug] Button computed styles:', {
        display: computedStyle.display,
        visibility: computedStyle.visibility,
        pointerEvents: computedStyle.pointerEvents,
        zIndex: computedStyle.zIndex,
        position: computedStyle.position,
        opacity: computedStyle.opacity,
        cursor: computedStyle.cursor
    });
    
    // Check button position
    const rect = btn.getBoundingClientRect();
    console.log('[ToolGuideModal Debug] Button bounding rect:', rect);
    console.log('[ToolGuideModal Debug] Button is in viewport:', rect.width > 0 && rect.height > 0);
    
    // Check if anything is covering the button
    const elementAtPoint = document.elementFromPoint(
        rect.left + rect.width / 2,
        rect.top + rect.height / 2
    );
    console.log('[ToolGuideModal Debug] Element at button center:', elementAtPoint);
    console.log('[ToolGuideModal Debug] Element at center is button?', elementAtPoint === btn || elementAtPoint?.closest('#toolGuideAddToPipelineBtn') === btn);
    if (elementAtPoint !== btn && !btn.contains(elementAtPoint)) {
        console.warn('[ToolGuideModal Debug] WARNING: Something is covering the button!', elementAtPoint);
    }
    
    // Check if Chrome DevTools getEventListeners is available
    if (window.getEventListeners && typeof window.getEventListeners === 'function') {
        try {
            const listeners = window.getEventListeners(btn);
            console.log('[ToolGuideModal Debug] Event listeners (Chrome DevTools):', listeners);
        } catch (e) {
            console.log('[ToolGuideModal Debug] Could not get event listeners:', e);
        }
    } else {
        console.log('[ToolGuideModal Debug] getEventListeners not available (use Chrome DevTools)');
    }
    
    // Check modal click handler
    console.log('[ToolGuideModal Debug] Modal click handler exists:', !!modalClickHandler);
    console.log('[ToolGuideModal Debug] Modal element:', modal);
    console.log('[ToolGuideModal Debug] Global addToPipelineBtn reference:', addToPipelineBtn);
    console.log('[ToolGuideModal Debug] Global addToPipelineBtn === btn?', addToPipelineBtn === btn);
    
    // Test click programmatically
    console.log('[ToolGuideModal Debug] Testing programmatic click...');
    const testEvent = new MouseEvent('click', {
        bubbles: true,
        cancelable: true,
        view: window,
        button: 0
    });
    btn.dispatchEvent(testEvent);
    
    // Also test with different event types
    console.log('[ToolGuideModal Debug] Testing mousedown...');
    btn.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }));
    
    console.log('[ToolGuideModal Debug] ====== End Debug Check ======');
}

    // Export to window immediately (like SaveToNoteModal)
    window.ToolGuideModal = {
        open: openToolGuideModal,
        close: closeModal,
        init: initToolGuideModal,
        initDOMElements: initDOMElements,
        debug: debugButtonEventListeners, // Add debug function
    };
    
    // Also add a global debug function for easier access
    window.debugToolGuideModal = debugButtonEventListeners;
    
    // Initialize when DOM is ready
    function tryInit() {
        if (initDOMElements() && initToolGuideModal()) {
            // Dispatch custom event to signal that ToolGuideModal is ready
            const event = new CustomEvent('toolGuideModalReady', {
                detail: { ToolGuideModal: window.ToolGuideModal }
            });
            document.dispatchEvent(event);
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
