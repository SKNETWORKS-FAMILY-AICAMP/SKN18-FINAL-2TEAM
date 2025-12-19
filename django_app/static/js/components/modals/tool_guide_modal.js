// Tool Guide Modal JavaScript

const modalId = 'toolGuideModal';
let currentTool = null;

// DOM elements
const modal = document.getElementById(modalId);
const modalTitle = document.getElementById('toolGuideModalTitle');
const modalSubtitle = document.getElementById('toolGuideModalSubtitle');
const overviewEl = document.getElementById('toolGuideOverview');
const usageList = document.getElementById('toolGuideUsageList');
const tipsEl = document.getElementById('toolGuideTips');
const addToPipelineBtn = document.getElementById('toolGuideAddToPipelineBtn');

// Initialize modal
function initToolGuideModal() {
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

    // Add to pipeline button
    addToPipelineBtn?.addEventListener('click', handleAddToPipeline);
}

// Open modal
function openToolGuideModal(tool) {
    if (!modal || !tool) return;

    currentTool = tool;

    // Update title
    if (modalTitle) {
        modalTitle.textContent = `${tool.name} 사용 가이드`;
    }
    if (modalSubtitle) {
        modalSubtitle.textContent = tool.category || '';
    }

    // Render guide content
    renderGuideContent(tool);

    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
}

// Close modal
function closeModal() {
    if (!modal) return;
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

// Update add to pipeline button
function updateAddToPipelineButton(tool) {
    if (!addToPipelineBtn) return;
    
    const isSelected = window.ExperimentPage && 
                      window.ExperimentPage.selectedTools && 
                      window.ExperimentPage.selectedTools.includes(tool.id);
    
    if (isSelected) {
        addToPipelineBtn.innerHTML = `
            <i class="fas fa-times"></i>
            파이프라인에서 제거
        `;
    } else {
        addToPipelineBtn.innerHTML = `
            <i class="fas fa-plus"></i>
            파이프라인에 추가
        `;
    }
}

// Handle add to pipeline
function handleAddToPipeline() {
    if (!currentTool) return;

    const isSelected = window.ExperimentPage && 
                      window.ExperimentPage.selectedTools && 
                      window.ExperimentPage.selectedTools.includes(currentTool.id);

    if (window.ExperimentPage && window.ExperimentPage.toggleToolSelection) {
        window.ExperimentPage.toggleToolSelection(currentTool.id);
    }

    if (window.notyf) {
        if (isSelected) {
            window.notyf.success(`${currentTool.name}이(가) 파이프라인에서 제거되었습니다.`);
        } else {
            window.notyf.success(`${currentTool.name}이(가) 파이프라인에 추가되었습니다.`);
        }
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
    document.addEventListener('DOMContentLoaded', initToolGuideModal);
} else {
    initToolGuideModal();
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.ToolGuideModal = {
        open: openToolGuideModal,
        close: closeModal,
        init: initToolGuideModal,
    };
}
