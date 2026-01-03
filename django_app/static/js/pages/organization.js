// 조직 관리 페이지 JavaScript

let organizations = [];
let inviteEmails = [''];

// CSRF 토큰 가져오기
function getCsrfToken() {
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === 'csrftoken') {
            return value;
        }
    }
    // Try to get from meta tag
    const metaTag = document.querySelector('meta[name=csrf-token]');
    if (metaTag) {
        return metaTag.getAttribute('content');
    }
    return '';
}

// HTML 이스케이프
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 조직 목록 로드
async function loadOrganizations() {
    try {
        const response = await fetch('/api/organization/', {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
        });

        if (response.ok) {
            const data = await response.json();
            if (data.success) {
                organizations = data.organizations || [];
                renderOrganizations();
            } else {
                console.error('조직 목록 로드 실패:', data.error);
            }
        } else {
            console.error('조직 목록 로드 실패:', response.statusText);
        }
    } catch (error) {
        console.error('조직 목록 로드 중 오류:', error);
    }
}

// 조직 목록 렌더링
function renderOrganizations() {
    const container = document.getElementById('organizationsList');
    if (!container) return;
    
    container.innerHTML = '';
    
    if (organizations.length === 0) {
        container.innerHTML = `
            <div class="org-empty">
                <div class="org-empty-icon">
                    <i class="fa fa-building"></i>
                </div>
                <h3>아직 조직이 없습니다</h3>
                <p>새 조직을 만들어 팀원들과 협업을 시작하세요.</p>
            </div>
        `;
        return;
    }
    
    organizations.forEach(org => {
        const memberView = `
            <div class="org-card">
                <div class="org-card-header">
                    <div class="org-icon"><i class="fa fa-building"></i></div>
                    <div class="org-info">
                        <h2>${escapeHtml(org.name)}</h2>
                        <div class="org-meta">
                            <span><i class="fa fa-users"></i> ${org.members.length}명</span>
                            <span>${escapeHtml(org.createdAt)}</span>
                            <span class="role-badge ${org.role === "owner" ? "owner" : "member"}">
                                ${org.role === "owner" ? "소유자" : "멤버"}
                            </span>
                        </div>
                    </div>
                    <div class="org-card-actions">
                        ${org.role === 'owner' && (org.otherMembersCount === 0 || org.otherMembersCount === undefined) ? `
                            <button class="org-delete-btn" onclick="handleDeleteOrganization('${org.id}', '${escapeHtml(org.name)}')" title="조직 삭제">
                                <i class="fa fa-trash"></i>
                            </button>
                        ` : ''}
                        <button class="org-expand-btn" onclick="toggleOrgMembers('${org.id}')">
                            멤버 보기
                        </button>
                    </div>
                </div>
                <div class="org-members" id="org-members-${org.id}" style="display:none;">
                    <div class="org-members-header">
                        <h3>멤버 목록</h3>
                        ${org.role === 'owner' ? `
                            <button class="org-add-member-btn" onclick="openAddMemberModal('${org.id}')">
                                <i class="fa fa-user-plus"></i>
                                멤버 초대
                            </button>
                        ` : ''}
                    </div>
                    <div class="org-members-list">
                        ${org.members.map(m => `
                            <div class="org-member">
                                <div class="org-member-info-wrapper">
                                    ${m.avatar ? 
                                        `<img class="org-avatar" src="${escapeHtml(m.avatar)}" alt="${escapeHtml(m.name)}" />` :
                                        `<div class="org-avatar org-avatar-placeholder"><i class="fa fa-user"></i></div>`
                                    }
                                    <div class="org-member-info">
                                        <span class="org-member-name">${escapeHtml(m.name)}</span>
                                        <span class="org-member-email">${escapeHtml(m.email)}</span>
                                    </div>
                                </div>
                                ${org.role === 'owner' ? `
                                    <button class="org-remove-member-btn" onclick="handleRemoveMember('${org.id}', '${m.id}', '${escapeHtml(m.name)}')" title="멤버 제거">
                                        <i class="fa fa-user-minus"></i>
                                    </button>
                                ` : ''}
                            </div>
                        `).join('')}
                    </div>
                </div>
            </div>
        `;
        container.innerHTML += memberView;
    });
}

// 멤버 목록 토글
window.toggleOrgMembers = function(orgId) {
    const section = document.getElementById('org-members-' + orgId);
    if (section) {
        const isVisible = section.style.display !== 'none';
        section.style.display = isVisible ? 'none' : 'block';
        
        // 버튼 텍스트 변경
        const buttons = document.querySelectorAll(`.org-expand-btn`);
        buttons.forEach(btn => {
            if (btn.onclick && btn.onclick.toString().includes(orgId)) {
                btn.textContent = isVisible ? '멤버 보기' : '접기';
            }
        });
    }
};

// ---------- 조직 생성 모달 ----------
const createBtn = document.getElementById('createOrgBtn');
const modalBackdrop = document.getElementById('orgModalBackdrop');
const closeModalBtn = document.getElementById('closeOrgModal');
const submitModalBtn = document.getElementById('submitOrgModalBtn');
const cancelModalBtn = document.getElementById('cancelOrgModalBtn');
const orgNameInput = document.getElementById('orgNameInput');
const inviteEmailsWrapper = document.getElementById('inviteEmailsWrapper');
const addInviteFieldBtn = document.getElementById('addInviteFieldBtn');

function openOrgModal() {
    if (modalBackdrop) {
        modalBackdrop.style.display = 'flex';
        renderInviteFields();
    }
}

function closeOrgModal() {
    if (modalBackdrop) {
        modalBackdrop.style.display = 'none';
    }
    if (orgNameInput) {
        orgNameInput.value = '';
    }
    inviteEmails = [''];
    renderInviteFields();
}

if (createBtn) {
    createBtn.addEventListener('click', openOrgModal);
}
if (closeModalBtn) {
    closeModalBtn.addEventListener('click', closeOrgModal);
}
if (cancelModalBtn) {
    cancelModalBtn.addEventListener('click', closeOrgModal);
}

// 모달 배경 클릭 시 닫기
if (modalBackdrop) {
    modalBackdrop.addEventListener('click', function(e) {
        if (e.target === modalBackdrop) {
            closeOrgModal();
        }
    });
}

// 초대 이메일 필드 렌더링
function renderInviteFields() {
    if (!inviteEmailsWrapper) return;
    
    let html = '';
    inviteEmails.forEach((email, idx) => {
        html += `<div class="org-invite-field">
      <input type="email" value="${escapeHtml(email)}" placeholder="이메일 주소" onchange="updateInviteEmail(${idx}, this.value)" class="org-input"/>
      ${inviteEmails.length > 1 ? `<button onclick="removeInviteField(${idx})" class="org-invite-remove-btn"><i class="fa fa-times"></i></button>` : ''}
    </div>`;
    });
    inviteEmailsWrapper.innerHTML = html;
}

window.updateInviteEmail = function(idx, val) {
    if (idx >= 0 && idx < inviteEmails.length) {
        inviteEmails[idx] = val;
    }
};

window.removeInviteField = function(idx) {
    if (inviteEmails.length > 1 && idx >= 0 && idx < inviteEmails.length) {
        inviteEmails.splice(idx, 1);
        renderInviteFields();
    }
};

if (addInviteFieldBtn) {
    addInviteFieldBtn.addEventListener('click', function() {
        inviteEmails.push('');
        renderInviteFields();
    });
}

// 조직 생성 제출
if (submitModalBtn) {
    submitModalBtn.addEventListener('click', async function() {
        const orgName = orgNameInput ? orgNameInput.value.trim() : '';
        
        if (!orgName) {
            Swal.fire({
                icon: 'warning',
                title: '입력 필요',
                text: '조직 이름을 입력해주세요.',
                confirmButtonText: '확인'
            });
            return;
        }
        
        // 유효한 이메일만 필터링
        const validEmails = inviteEmails
            .map(email => email.trim())
            .filter(email => email && email.includes('@'));
        
        // 버튼 비활성화
        submitModalBtn.disabled = true;
        submitModalBtn.textContent = '생성 중...';
        
        try {
            const response = await fetch('/api/organization/create/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    name: orgName,
                    invite_emails: validEmails
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // 성공 시 조직 목록 새로고침
                await loadOrganizations();
                closeOrgModal();
                
                // 상세 메시지 구성
                let messageText = data.message || '조직이 생성되었습니다.';
                
                // 중복 초대나 이미 멤버인 경우가 있으면 추가 정보 표시
                if (data.duplicate_invitations && data.duplicate_invitations.length > 0) {
                    messageText += `\n\n이미 초대 대기 중: ${data.duplicate_invitations.join(', ')}`;
                }
                if (data.already_members && data.already_members.length > 0) {
                    messageText += `\n\n이미 멤버: ${data.already_members.join(', ')}`;
                }
                
                Swal.fire({
                    icon: 'success',
                    title: '조직 생성 완료',
                    text: messageText,
                    confirmButtonText: '확인'
                });
            } else {
                Swal.fire({
                    icon: 'error',
                    title: '조직 생성 실패',
                    text: data.error || '알 수 없는 오류가 발생했습니다.',
                    confirmButtonText: '확인'
                });
            }
        } catch (error) {
            console.error('조직 생성 중 오류:', error);
            Swal.fire({
                icon: 'error',
                title: '오류 발생',
                text: '조직 생성 중 오류가 발생했습니다.',
                confirmButtonText: '확인'
            });
        } finally {
            // 버튼 활성화
            submitModalBtn.disabled = false;
            submitModalBtn.textContent = '조직 만들기';
        }
    });
}

// ---------- 초대 목록 관련 ----------
let invitations = [];

// 초대 목록 로드
async function loadInvitations() {
    const container = document.getElementById('invitationsList');
    if (!container) return;
    
    container.innerHTML = '<div class="org-invitations-loading">로딩 중...</div>';
    
    try {
        const response = await fetch('/api/organization/invitations/', {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
        });

        if (response.ok) {
            const data = await response.json();
            if (data.success) {
                invitations = data.invitations || [];
                renderInvitations();
            } else {
                container.innerHTML = '<div class="org-invitations-empty">초대 목록을 불러올 수 없습니다.</div>';
            }
        } else {
            container.innerHTML = '<div class="org-invitations-empty">초대 목록을 불러올 수 없습니다.</div>';
        }
    } catch (error) {
        console.error('초대 목록 로드 중 오류:', error);
        container.innerHTML = '<div class="org-invitations-empty">초대 목록을 불러올 수 없습니다.</div>';
    }
}

// 초대 목록 렌더링
function renderInvitations() {
    const container = document.getElementById('invitationsList');
    
    if (!container) return;
    
    if (invitations.length === 0) {
        container.innerHTML = `
            <div class="org-invitations-empty">
                <div class="org-invitations-empty-icon">
                    <i class="fa fa-envelope"></i>
                </div>
                <p class="org-invitations-empty-title">받은 초대가 없습니다</p>
                <p class="org-invitations-empty-subtitle">조직 초대를 받으면 여기에 표시됩니다</p>
            </div>
        `;
        return;
    }
    
    let html = '';
    invitations.forEach(invitation => {
        const invitedBy = invitation.invited_by || {};
        const invitedByName = invitedBy.name || '알 수 없음';
        const invitedByAvatar = invitedBy.avatar || '';
        const memberCount = invitation.member_count || 0;
        
        html += `
            <div class="org-invitation-item" data-invitation-id="${invitation.id}">
                <div class="org-invitation-header">
                    <div class="org-invitation-icon">
                        <i class="fa fa-building"></i>
                    </div>
                    <div class="org-invitation-org-info">
                        <div class="org-invitation-org-name">${escapeHtml(invitation.organization_name)}</div>
                        <div class="org-invitation-member-count">${memberCount}명의 멤버</div>
                    </div>
                </div>
                <div class="org-invitation-inviter">
                    ${invitedByAvatar ? 
                        `<img class="org-invitation-avatar" src="${escapeHtml(invitedByAvatar)}" alt="${escapeHtml(invitedByName)}" />` :
                        `<div class="org-invitation-avatar org-invitation-avatar-placeholder"><i class="fa fa-user"></i></div>`
                    }
                    <div class="org-invitation-inviter-info">
                        <div class="org-invitation-inviter-name">${escapeHtml(invitedByName)}님이 초대했습니다</div>
                        <div class="org-invitation-inviter-date">${escapeHtml(invitation.invited_at)}</div>
                    </div>
                </div>
                <div class="org-invitation-actions">
                    <button 
                        class="org-invitation-accept-btn" 
                        onclick="handleInvitationAccept('${invitation.id}')"
                        data-invitation-id="${invitation.id}"
                    >
                        <i class="fa fa-check"></i>
                        수락
                    </button>
                    <button 
                        class="org-invitation-reject-btn" 
                        onclick="handleInvitationReject('${invitation.id}')"
                        data-invitation-id="${invitation.id}"
                    >
                        <i class="fa fa-times-circle"></i>
                        거부
                    </button>
                </div>
            </div>
        `;
    });
    container.innerHTML = html;
}

// 초대 수락
window.handleInvitationAccept = async function(invitationId) {
    const button = document.querySelector(`.org-invitation-accept-btn[data-invitation-id="${invitationId}"]`);
    const rejectButton = document.querySelector(`.org-invitation-reject-btn[data-invitation-id="${invitationId}"]`);
    
    if (button && button.disabled) return;
    
    if (button) {
        button.disabled = true;
        button.innerHTML = '처리 중...';
    }
    if (rejectButton) {
        rejectButton.disabled = true;
    }
    
    try {
        const response = await fetch(`/api/organization/invitations/${invitationId}/respond/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                action: 'accept'
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            Swal.fire({
                icon: 'success',
                title: '초대 수락',
                text: data.message || '초대를 수락했습니다.',
                confirmButtonText: '확인'
            });
            // 초대 목록 새로고침
            await loadInvitations();
            // 조직 목록도 새로고침 (새 조직이 추가되었을 수 있음)
            await loadOrganizations();
        } else {
            Swal.fire({
                icon: 'error',
                title: '초대 수락 실패',
                text: data.error || '알 수 없는 오류가 발생했습니다.',
                confirmButtonText: '확인'
            });
            if (button) button.disabled = false;
            if (rejectButton) rejectButton.disabled = false;
            if (button) button.innerHTML = '<i class="fa fa-check"></i> 수락';
        }
    } catch (error) {
        console.error('초대 수락 중 오류:', error);
        Swal.fire({
            icon: 'error',
            title: '오류 발생',
            text: '초대 수락 중 오류가 발생했습니다.',
            confirmButtonText: '확인'
        });
        if (button) button.disabled = false;
        if (rejectButton) rejectButton.disabled = false;
        if (button) button.innerHTML = '<i class="fa fa-check"></i> 수락';
    }
};

// 초대 거부
window.handleInvitationReject = async function(invitationId) {
    const button = document.querySelector(`.org-invitation-reject-btn[data-invitation-id="${invitationId}"]`);
    const acceptButton = document.querySelector(`.org-invitation-accept-btn[data-invitation-id="${invitationId}"]`);
    
    if (button && button.disabled) return;
    
    const result = await Swal.fire({
        icon: 'question',
        title: '초대 거부',
        text: '정말 이 초대를 거부하시겠습니까?',
        showCancelButton: true,
        confirmButtonText: '거부',
        cancelButtonText: '취소',
        confirmButtonColor: '#dc2626',
        cancelButtonColor: '#6b7280'
    });
    
    if (!result.isConfirmed) {
        return;
    }
    
    if (button) {
        button.disabled = true;
        button.innerHTML = '처리 중...';
    }
    if (acceptButton) {
        acceptButton.disabled = true;
    }
    
    try {
        const response = await fetch(`/api/organization/invitations/${invitationId}/respond/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                action: 'reject'
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            Swal.fire({
                icon: 'success',
                title: '초대 거부',
                text: data.message || '초대를 거부했습니다.',
                confirmButtonText: '확인'
            });
            // 초대 목록 새로고침
            await loadInvitations();
        } else {
            Swal.fire({
                icon: 'error',
                title: '초대 거부 실패',
                text: data.error || '알 수 없는 오류가 발생했습니다.',
                confirmButtonText: '확인'
            });
            if (button) button.disabled = false;
            if (acceptButton) acceptButton.disabled = false;
            if (button) button.innerHTML = '<i class="fa fa-times-circle"></i> 거부';
        }
    } catch (error) {
        console.error('초대 거부 중 오류:', error);
        Swal.fire({
            icon: 'error',
            title: '오류 발생',
            text: '초대 거부 중 오류가 발생했습니다.',
            confirmButtonText: '확인'
        });
        if (button) button.disabled = false;
        if (acceptButton) acceptButton.disabled = false;
        if (button) button.innerHTML = '<i class="fa fa-times-circle"></i> 거부';
    }
};

// 사이드바 닫기 버튼
const btnCloseInvitationsSidebar = document.getElementById('btnCloseInvitationsSidebar');
const invitationsSidebar = document.getElementById('invitationsSidebar');
if (btnCloseInvitationsSidebar && invitationsSidebar) {
    btnCloseInvitationsSidebar.addEventListener('click', function() {
        invitationsSidebar.classList.add('hidden');
    });
}

// ---------- 멤버 추가/제거 관련 ----------
let addMemberEmails = [''];
let selectedOrgIdForAddMember = null;

// 멤버 추가 모달 열기
window.openAddMemberModal = function(orgId) {
    selectedOrgIdForAddMember = orgId;
    const modal = document.getElementById('addMemberModalBackdrop');
    if (modal) {
        modal.style.display = 'flex';
        addMemberEmails = [''];
        renderAddMemberFields();
    }
};

// 멤버 추가 모달 닫기
function closeAddMemberModal() {
    const modal = document.getElementById('addMemberModalBackdrop');
    if (modal) {
        modal.style.display = 'none';
    }
    addMemberEmails = [''];
    selectedOrgIdForAddMember = null;
    renderAddMemberFields();
}

// 멤버 추가 이메일 필드 렌더링
function renderAddMemberFields() {
    const wrapper = document.getElementById('addMemberEmailsWrapper');
    if (!wrapper) return;
    
    let html = '';
    addMemberEmails.forEach((email, idx) => {
        html += `<div class="org-invite-field">
      <input type="email" value="${escapeHtml(email)}" placeholder="이메일 주소" onchange="updateAddMemberEmail(${idx}, this.value)" class="org-input"/>
      ${addMemberEmails.length > 1 ? `<button onclick="removeAddMemberField(${idx})" class="org-invite-remove-btn"><i class="fa fa-times"></i></button>` : ''}
    </div>`;
    });
    wrapper.innerHTML = html;
}

window.updateAddMemberEmail = function(idx, val) {
    if (idx >= 0 && idx < addMemberEmails.length) {
        addMemberEmails[idx] = val;
    }
};

window.removeAddMemberField = function(idx) {
    if (addMemberEmails.length > 1 && idx >= 0 && idx < addMemberEmails.length) {
        addMemberEmails.splice(idx, 1);
        renderAddMemberFields();
    }
};

// 멤버 추가 모달 이벤트 리스너
const closeAddMemberModalBtn = document.getElementById('closeAddMemberModal');
const cancelAddMemberModalBtn = document.getElementById('cancelAddMemberModalBtn');
const submitAddMemberModalBtn = document.getElementById('submitAddMemberModalBtn');
const addMemberEmailFieldBtn = document.getElementById('addMemberEmailFieldBtn');
const addMemberModalBackdrop = document.getElementById('addMemberModalBackdrop');

if (closeAddMemberModalBtn) {
    closeAddMemberModalBtn.addEventListener('click', closeAddMemberModal);
}
if (cancelAddMemberModalBtn) {
    cancelAddMemberModalBtn.addEventListener('click', closeAddMemberModal);
}
if (addMemberModalBackdrop) {
    addMemberModalBackdrop.addEventListener('click', function(e) {
        if (e.target === addMemberModalBackdrop) {
            closeAddMemberModal();
        }
    });
}
if (addMemberEmailFieldBtn) {
    addMemberEmailFieldBtn.addEventListener('click', function() {
        addMemberEmails.push('');
        renderAddMemberFields();
    });
}

// 멤버 추가 제출
if (submitAddMemberModalBtn) {
    submitAddMemberModalBtn.addEventListener('click', async function() {
        if (!selectedOrgIdForAddMember) return;
        
        const validEmails = addMemberEmails
            .map(email => email.trim().toLowerCase())
            .filter(email => email && email.includes('@'));
        
        if (validEmails.length === 0) {
            Swal.fire({
                icon: 'warning',
                title: '입력 필요',
                text: '최소 1명의 이메일을 입력해주세요.',
                confirmButtonText: '확인'
            });
            return;
        }
        
        submitAddMemberModalBtn.disabled = true;
        submitAddMemberModalBtn.textContent = '처리 중...';
        
        try {
            const response = await fetch(`/api/organization/${selectedOrgIdForAddMember}/members/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    invite_emails: validEmails
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // 상세 메시지 구성
                let messageText = data.message || '멤버 초대가 발송되었습니다.';
                
                // 중복 초대나 이미 멤버인 경우가 있으면 추가 정보 표시
                if (data.duplicate_invitations && data.duplicate_invitations.length > 0) {
                    messageText += `\n\n이미 초대 대기 중: ${data.duplicate_invitations.join(', ')}`;
                }
                if (data.already_members && data.already_members.length > 0) {
                    messageText += `\n\n이미 멤버: ${data.already_members.join(', ')}`;
                }
                
                Swal.fire({
                    icon: 'success',
                    title: '초대 발송 완료',
                    text: messageText,
                    confirmButtonText: '확인'
                });
                closeAddMemberModal();
                await loadOrganizations();
            } else {
                Swal.fire({
                    icon: 'error',
                    title: '초대 실패',
                    text: data.error || '알 수 없는 오류가 발생했습니다.',
                    confirmButtonText: '확인'
                });
            }
        } catch (error) {
            console.error('멤버 추가 중 오류:', error);
            Swal.fire({
                icon: 'error',
                title: '오류 발생',
                text: '멤버 추가 중 오류가 발생했습니다.',
                confirmButtonText: '확인'
            });
        } finally {
            submitAddMemberModalBtn.disabled = false;
            submitAddMemberModalBtn.textContent = '초대 보내기';
        }
    });
}

// 멤버 제거
window.handleRemoveMember = async function(orgId, memberId, memberName) {
    const result = await Swal.fire({
        icon: 'warning',
        title: '멤버 제거',
        html: `정말 <strong>${escapeHtml(memberName)}</strong>님을 조직에서 제거하시겠습니까?`,
        showCancelButton: true,
        confirmButtonText: '제거',
        cancelButtonText: '취소',
        confirmButtonColor: '#dc2626',
        cancelButtonColor: '#6b7280'
    });
    
    if (!result.isConfirmed) {
        return;
    }
    
    try {
        const response = await fetch(`/api/organization/${orgId}/members/${memberId}/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            Swal.fire({
                icon: 'success',
                title: '멤버 제거 완료',
                text: data.message || '멤버가 제거되었습니다.',
                confirmButtonText: '확인'
            });
            await loadOrganizations();
        } else {
            Swal.fire({
                icon: 'error',
                title: '멤버 제거 실패',
                text: data.error || '알 수 없는 오류가 발생했습니다.',
                confirmButtonText: '확인'
            });
        }
    } catch (error) {
        console.error('멤버 제거 중 오류:', error);
        Swal.fire({
            icon: 'error',
            title: '오류 발생',
            text: '멤버 제거 중 오류가 발생했습니다.',
            confirmButtonText: '확인'
        });
    }
};

// 조직 삭제
window.handleDeleteOrganization = async function(orgId, orgName) {
    const result = await Swal.fire({
        icon: 'warning',
        title: '조직 삭제',
        html: `정말 <strong>${escapeHtml(orgName)}</strong> 조직을 삭제하시겠습니까?<br><br>이 작업은 되돌릴 수 없습니다.`,
        showCancelButton: true,
        confirmButtonText: '삭제',
        cancelButtonText: '취소',
        confirmButtonColor: '#dc2626',
        cancelButtonColor: '#6b7280'
    });
    
    if (!result.isConfirmed) {
        return;
    }
    
    try {
        const response = await fetch(`/api/organization/${orgId}/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            Swal.fire({
                icon: 'success',
                title: '조직 삭제 완료',
                text: data.message || '조직이 삭제되었습니다.',
                confirmButtonText: '확인'
            });
            await loadOrganizations();
        } else {
            Swal.fire({
                icon: 'error',
                title: '조직 삭제 실패',
                text: data.error || '알 수 없는 오류가 발생했습니다.',
                confirmButtonText: '확인'
            });
        }
    } catch (error) {
        console.error('조직 삭제 중 오류:', error);
        Swal.fire({
            icon: 'error',
            title: '오류 발생',
            text: '조직 삭제 중 오류가 발생했습니다.',
            confirmButtonText: '확인'
        });
    }
};

// 페이지 로드 시 조직 목록 및 초대 목록 로드
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        loadOrganizations();
        loadInvitations();
    });
} else {
    loadOrganizations();
    loadInvitations();
}
