// Invitation Accept Modal Component JavaScript Logic

// State variables
let currentInvitationId = null;
let onSuccessCallback = null;

// DOM elements
const modalId = 'invitationAcceptModal';
const modal = document.getElementById(modalId);
const calendarSelect = document.getElementById('calendarSelect');
const acceptBtn = document.getElementById('acceptInvitationBtn');
const closeBtn = modal?.querySelector('.modal-close-btn');

// Initialize modal
function initInvitationAcceptModal() {
    if (!modal) {
        console.error(`[InvitationAcceptModal] Modal with ID "${modalId}" not found`);
        return;
    }
    
    // Close button
    if (closeBtn) {
        closeBtn.addEventListener('click', closeModal);
    }
    
    // Cancel button
    const cancelBtn = modal.querySelector('[data-action="close"]');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', closeModal);
    }
    
    // Accept button
    if (acceptBtn) {
        acceptBtn.addEventListener('click', handleAccept);
    }
    
    // Modal overlay click to close
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeModal();
        }
    });
    
    // Modal events
    document.addEventListener('modal:open', handleModalOpen);
    document.addEventListener('modal:close', handleModalClose);
}

// Handle modal open
function handleModalOpen(e) {
    if (e.detail.modalId !== modalId) return;
    
    currentInvitationId = e.detail.invitationId;
    loadCalendars();
}

// Handle modal close
function handleModalClose(e) {
    if (e.detail.modalId !== modalId) return;
    currentInvitationId = null;
    if (calendarSelect) {
        calendarSelect.value = '';
    }
}

// Load calendars
async function loadCalendars() {
    if (!calendarSelect) return;
    
    try {
        const response = await fetch('/api/calendars/', {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
        });
        
        if (response.ok) {
            const data = await response.json();
            // API는 {"results": [...]} 형태로 반환
            const calendars = Array.isArray(data?.results) ? data.results : (Array.isArray(data) ? data : []);
            
            console.log('[InvitationAcceptModal] Loaded calendars:', calendars);
            
            // 구글 캘린더 제외 (source_type이 'google'이 아닌 캘린더만)
            const localCalendars = calendars.filter(cal => {
                return cal.source_type !== 'google' && cal.source_type !== 'GOOGLE';
            });
            
            console.log('[InvitationAcceptModal] Filtered local calendars:', localCalendars);
            
            calendarSelect.innerHTML = '<option value="">캘린더를 선택하세요</option>' +
                localCalendars.map(cal => `
                    <option value="${cal.id}">${escapeHtml(cal.name || '')}</option>
                `).join('');
        } else {
            console.error('Failed to load calendars, status:', response.status);
            calendarSelect.innerHTML = '<option value="">캘린더를 불러올 수 없습니다</option>';
        }
    } catch (error) {
        console.error('Error loading calendars:', error);
        calendarSelect.innerHTML = '<option value="">캘린더를 불러올 수 없습니다</option>';
    }
}

// Handle accept
async function handleAccept() {
    if (!currentInvitationId) return;
    
    const calendarId = calendarSelect?.value;
    if (!calendarId) {
        if (window.notyf) {
            window.notyf.error('캘린더를 선택해주세요.');
        }
        return;
    }
    
    try {
        const response = await fetch(`/schedule/api/invitations/${currentInvitationId}/accept/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                calendar_id: parseInt(calendarId)
            }),
        });
        
        if (response.ok) {
            const data = await response.json();
            if (window.notyf) {
                window.notyf.success(data.message || '초대를 수락했습니다.');
            }
            
            // Close modal
            closeModal();
            
            // Reload invitations
            if (window.InvitationsList && window.InvitationsList.load) {
                await window.InvitationsList.load();
            }
            
            // Refresh calendar
            if (window.SchedulePage) {
                if (window.SchedulePage.refreshCalendar) {
                    window.SchedulePage.refreshCalendar();
                }
                if (window.SchedulePage.loadSchedules) {
                    window.SchedulePage.loadSchedules();
                }
            }
            
            // Call success callback if provided
            if (onSuccessCallback && typeof onSuccessCallback === 'function') {
                onSuccessCallback();
            }
            onSuccessCallback = null;
        } else {
            const error = await response.json().catch(() => ({ error: 'Unknown error' }));
            if (window.notyf) {
                window.notyf.error(error.error || '초대 수락에 실패했습니다.');
            }
        }
    } catch (error) {
        console.error('Error accepting invitation:', error);
        if (window.notyf) {
            window.notyf.error('초대 수락 중 오류가 발생했습니다.');
        }
    }
}

// Close modal
function closeModal() {
    if (window.Modal && window.Modal.close) {
        window.Modal.close(modalId);
    } else {
        modal?.classList.remove('active');
        document.body.style.overflow = '';
    }
}

// Open modal
function openInvitationAcceptModal(invitationId, onSuccess) {
    onSuccessCallback = onSuccess || null;
    if (window.Modal && window.Modal.open) {
        window.Modal.open(modalId, { invitationId: invitationId });
    } else {
        modal?.classList.add('active');
        document.body.style.overflow = 'hidden';
        const event = new CustomEvent('modal:open', {
            detail: { modalId: modalId, invitationId: invitationId }
        });
        document.dispatchEvent(event);
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
    const metaTag = document.querySelector('meta[name=csrf-token]');
    if (metaTag) {
        return metaTag.getAttribute('content');
    }
    return '';
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
    document.addEventListener('DOMContentLoaded', initInvitationAcceptModal);
} else {
    initInvitationAcceptModal();
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.InvitationAcceptModal = {
        open: openInvitationAcceptModal,
        init: initInvitationAcceptModal,
    };
    // Also export as global function for easier access
    window.openInvitationAcceptModal = openInvitationAcceptModal;
}

