// Invitations List Component JavaScript Logic

// State variables
let invitations = [];
let selectedInvitation = null;

// DOM elements
const invitationsSection = document.getElementById('invitationsSection');
const invitationsList = document.getElementById('invitationsList');
const invitationsEmpty = document.getElementById('invitationsEmpty');
const invitationCount = document.getElementById('invitationCount');

// Initialize invitations list
function initInvitationsList() {
    console.log('[InvitationsList] initInvitationsList called');
    loadInvitations();
    
    // 주기적으로 invitation 목록 새로고침 (선택사항)
    // setInterval(loadInvitations, 60000); // 1분마다
}

// Load invitations
async function loadInvitations() {
    try {
        const response = await fetch('/schedule/api/invitations/', {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
        });
        
        if (response.ok) {
            const data = await response.json();
            invitations = data.results || [];
            renderInvitations();
        } else {
            console.error('Failed to load invitations');
            invitations = [];
            renderInvitations();
        }
    } catch (error) {
        console.error('Error loading invitations:', error);
        invitations = [];
        renderInvitations();
    }
}

// Render invitations
function renderInvitations() {
    if (!invitationsList || !invitationsEmpty || !invitationCount || !invitationsSection) return;
    
    invitationCount.textContent = invitations.length.toString();
    
    if (invitations.length === 0) {
        invitationsList.style.display = 'none';
        invitationsEmpty.style.display = 'block';
        invitationsSection.style.display = 'none';
    } else {
        invitationsList.style.display = 'block';
        invitationsEmpty.style.display = 'none';
        invitationsSection.style.display = 'block';
        
        invitationsList.innerHTML = invitations.map(invitation => {
            const startDate = invitation.schedule_start_date 
                ? new Date(invitation.schedule_start_date).toLocaleDateString('ko-KR', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                })
                : '';
            
            return `
                <div class="invitation-item" data-invitation-id="${invitation.id}">
                    <div class="invitation-info">
                        <div class="invitation-title">${escapeHtml(invitation.schedule_title || '')}</div>
                        <div class="invitation-meta">
                            <span class="invitation-date">${startDate}</span>
                            <span class="invitation-separator">•</span>
                            <span class="invitation-sharer">${escapeHtml(invitation.sharer_id || '')}</span>
                        </div>
                    </div>
                    <div class="invitation-actions">
                        <button class="invitation-accept-btn" data-invitation-id="${invitation.id}">
                            수락
                        </button>
                        <button class="invitation-reject-btn" data-invitation-id="${invitation.id}">
                            거절
                        </button>
                    </div>
                </div>
            `;
        }).join('');
        
        // Attach event listeners
        attachInvitationHandlers();
    }
}

// Attach invitation button handlers
function attachInvitationHandlers() {
    const acceptBtns = invitationsList?.querySelectorAll('.invitation-accept-btn');
    const rejectBtns = invitationsList?.querySelectorAll('.invitation-reject-btn');
    
    acceptBtns?.forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const invitationId = btn.getAttribute('data-invitation-id');
            await handleAcceptInvitation(invitationId);
        });
    });
    
    rejectBtns?.forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const invitationId = btn.getAttribute('data-invitation-id');
            await handleRejectInvitation(invitationId);
        });
    });
}

// Handle accept invitation
async function handleAcceptInvitation(invitationId) {
    const invitation = invitations.find(inv => inv.id === parseInt(invitationId));
    if (!invitation) return;
    
    // Open calendar selection modal
    if (window.InvitationAcceptModal && window.InvitationAcceptModal.open) {
        window.InvitationAcceptModal.open(invitationId);
    } else {
        console.error('InvitationAcceptModal not loaded');
        if (window.notyf) {
            window.notyf.error('초대 수락 모달을 로드할 수 없습니다.');
        }
    }
}

// Handle reject invitation
async function handleRejectInvitation(invitationId) {
    // Confirm rejection
    let confirmed = false;
    if (window.Swal) {
        const result = await window.Swal.fire({
            title: '초대 거절',
            text: '이 초대를 거절하시겠습니까?',
            icon: 'question',
            showCancelButton: true,
            confirmButtonText: '거절',
            cancelButtonText: '취소',
            confirmButtonColor: '#ef4444',
            cancelButtonColor: '#6b7280',
        });
        confirmed = result.isConfirmed;
    } else {
        confirmed = confirm('이 초대를 거절하시겠습니까?');
    }
    
    if (!confirmed) return;
    
    try {
        const response = await fetch(`/schedule/api/invitations/${invitationId}/reject/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
        });
        
        if (response.ok) {
            const data = await response.json();
            if (window.notyf) {
                window.notyf.success(data.message || '초대를 거절했습니다.');
            }
            // Reload invitations
            await loadInvitations();
        } else {
            const error = await response.json().catch(() => ({ error: 'Unknown error' }));
            if (window.notyf) {
                window.notyf.error(error.error || '초대 거절에 실패했습니다.');
            }
        }
    } catch (error) {
        console.error('Error rejecting invitation:', error);
        if (window.notyf) {
            window.notyf.error('초대 거절 중 오류가 발생했습니다.');
        }
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

// Escape HTML to prevent XSS
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initInvitationsList);
} else {
    initInvitationsList();
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.InvitationsList = {
        load: loadInvitations,
        init: initInvitationsList,
    };
}

