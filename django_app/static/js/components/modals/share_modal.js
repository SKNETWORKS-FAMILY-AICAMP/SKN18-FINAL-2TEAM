// Share Modal for Notes
(function() {
    'use strict';

    // State
    let selectedMembers = [];
    let shareSearchQuery = '';
    let selectedOrg = 'all';
    let shareModalTab = 'find';
    let organizations = [];
    let uniqueMembers = [];  // 중복 제거된 전체 멤버 목록
    let alreadySharedUsers = [];
    let currentNoteId = null;
    let currentScheduleId = null;
    let shareContext = 'editor';  // 'editor', 'detail', or 'schedule'

    // DOM Elements
    let shareModal = null;
    let shareModalCloseBtn = null;
    let shareModalTitle = null;
    let shareTabFind = null;
    let shareTabShared = null;
    let shareTabContentFind = null;
    let shareTabContentShared = null;
    let shareSearchSection = null;
    let shareSearchInput = null;
    let shareOrgTabs = null;
    let shareSelectedPreview = null;
    let shareSelectedCount = null;
    let shareSelectedMembersList = null;
    let shareClearAllBtn = null;
    let shareMembersList = null;
    let shareExternalInvite = null;
    let shareExternalEmail = null;
    let shareInviteExternalBtn = null;
    let shareSharedList = null;
    let shareModalFooter = null;
    let shareFooterInfo = null;
    let shareModalShareBtn = null;
    let shareModalCancelBtn = null;
    let isScheduleOwner = false;

    // API URL
    const organizationApiUrl = '/api/organization/';

    // Initialize
    function initShareModal() {
        console.log('[ShareModal] initShareModal called');
        shareModal = document.getElementById('shareModal');
        console.log('[ShareModal] shareModal element:', shareModal);
        shareModalCloseBtn = document.getElementById('shareModalCloseBtn');
        shareModalTitle = document.getElementById('shareModalTitle');
        shareTabFind = document.getElementById('shareTabFind');
        shareTabShared = document.getElementById('shareTabShared');
        shareTabContentFind = document.getElementById('shareTabContentFind');
        shareTabContentShared = document.getElementById('shareTabContentShared');
        shareSearchSection = document.getElementById('shareSearchSection');
        shareSearchInput = document.getElementById('shareSearchInput');
        shareOrgTabs = document.getElementById('shareOrgTabs');
        shareSelectedPreview = document.getElementById('shareSelectedPreview');
        shareSelectedCount = document.getElementById('shareSelectedCount');
        shareSelectedMembersList = document.getElementById('shareSelectedMembersList');
        shareClearAllBtn = document.getElementById('shareClearAllBtn');
        shareMembersList = document.getElementById('shareMembersList');
        shareExternalInvite = document.getElementById('shareExternalInvite');
        shareExternalEmail = document.getElementById('shareExternalEmail');
        shareInviteExternalBtn = document.getElementById('shareInviteExternalBtn');
        shareSharedList = document.getElementById('shareSharedList');
        shareModalFooter = document.getElementById('shareModalFooter');
        shareFooterInfo = document.getElementById('shareFooterInfo');
        shareModalShareBtn = document.getElementById('shareModalShareBtn');
        shareModalCancelBtn = document.getElementById('shareModalCancelBtn');

        // Attach event listeners
        if (shareModalCloseBtn) {
            shareModalCloseBtn.addEventListener('click', closeModal);
        }
        if (shareModalCancelBtn) {
            shareModalCancelBtn.addEventListener('click', closeModal);
        }
        if (shareTabFind) {
            shareTabFind.addEventListener('click', () => switchTab('find'));
        }
        if (shareTabShared) {
            shareTabShared.addEventListener('click', () => switchTab('shared'));
        }
        if (shareSearchInput) {
            shareSearchInput.addEventListener('input', handleSearch);
        }
        if (shareClearAllBtn) {
            shareClearAllBtn.addEventListener('click', clearAllSelection);
        }
        if (shareModalShareBtn) {
            shareModalShareBtn.addEventListener('click', handleShare);
        }
        if (shareInviteExternalBtn) {
            shareInviteExternalBtn.addEventListener('click', handleInviteExternal);
        }

        // Close on overlay click
        if (shareModal) {
            shareModal.addEventListener('click', (e) => {
                if (e.target === shareModal) {
                    closeModal();
                }
            });
        }

        // Load organizations from API
        loadOrganizations();
    }

    // Load organizations from API
    async function loadOrganizations() {
        try {
            const response = await fetch(organizationApiUrl, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin',
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            
            if (data.success && data.organizations) {
                // Transform API response to match expected format
                organizations = data.organizations.map(org => ({
                    id: org.id,
                    name: org.name,
                    members: org.members.map(member => ({
                        id: member.id,
                        name: member.name,
                        email: member.email,
                        avatar: member.avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(member.name)}&background=random`,
                        role: member.role || 'Member'
                    }))
                }));
                
                // 중복 제거된 전체 멤버 목록 저장
                if (data.uniqueMembers && Array.isArray(data.uniqueMembers)) {
                    uniqueMembers = data.uniqueMembers.map(member => ({
                        id: member.id,
                        name: member.name,
                        email: member.email,
                        avatar: member.avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(member.name)}&background=random`,
                        role: 'Member'  // uniqueMembers에는 role 정보가 없으므로 기본값 사용
                    }));
                } else {
                    // uniqueMembers가 없으면 기존 방식으로 중복 제거 (하위 호환)
                    const membersMap = new Map();
                    organizations.forEach(org => {
                        org.members.forEach(member => {
                            if (!membersMap.has(member.id)) {
                                membersMap.set(member.id, member);
                            }
                        });
                    });
                    uniqueMembers = Array.from(membersMap.values());
                }
                
                // Re-render if modal is open
                if (shareModal && shareModal.classList.contains('active')) {
                    renderOrgTabs();
                    renderMembersList();
                }
            } else {
                console.error('[ShareModal] Failed to load organizations:', data);
                organizations = [];
                uniqueMembers = [];
            }
        } catch (error) {
            console.error('[ShareModal] Error loading organizations:', error);
            organizations = [];
            if (window.notyf) {
                window.notyf.error('조직 목록을 불러오는 중 오류가 발생했습니다.');
            }
        }
    }

    // Open modal
    async function openModal(resourceId, orgs, sharedUsers, title, context) {
        console.log('[ShareModal] openModal called with:', { resourceId, orgs, sharedUsers, title, context });
        console.log('[ShareModal] shareModal element:', shareModal);
        console.log('[ShareModal] shareModalTitle element:', shareModalTitle);
        
        // Re-query if not found (in case it was loaded dynamically)
        if (!shareModal) {
            console.log('[ShareModal] shareModal is null, re-querying...');
            shareModal = document.getElementById('shareModal');
            console.log('[ShareModal] Re-queried shareModal:', shareModal);
        }
        
        shareContext = context || 'editor';  // 기본값은 'editor'
        
        // context에 따라 resourceId를 적절한 변수에 할당
        if (shareContext === 'schedule') {
            currentScheduleId = resourceId;
            currentNoteId = null;
        } else {
            currentNoteId = resourceId;
            currentScheduleId = null;
        }
        
        console.log('[ShareModal] Set currentNoteId:', currentNoteId, 'currentScheduleId:', currentScheduleId, 'shareContext:', shareContext);
        if (orgs) organizations = orgs;
        if (sharedUsers) {
            alreadySharedUsers = sharedUsers;
        } else if (currentNoteId && shareContext !== 'schedule') {
            // noteId가 있으면 API로 공유된 사용자 목록 가져오기
            await loadSharedUsers(currentNoteId);
        } else if (currentScheduleId && shareContext === 'schedule') {
            // scheduleId가 있으면 API로 공유된 사용자 목록 가져오기
            await loadSharedScheduleUsers(currentScheduleId);
        }
        
        // Set title
        if (shareModalTitle && title) {
            shareModalTitle.textContent = title;
        } else if (title) {
            // Re-query title element
            shareModalTitle = document.getElementById('shareModalTitle');
            if (shareModalTitle) shareModalTitle.textContent = title;
        }

        // Reset state
        selectedMembers = [];
        shareSearchQuery = '';
        selectedOrg = 'all';
        shareModalTab = 'find';

        // Update UI
        if (shareSearchInput) shareSearchInput.value = '';
        if (shareModal) {
            console.log('[ShareModal] Adding active class to show modal');
            shareModal.classList.add('active');
        } else {
            console.error('[ShareModal] Cannot open modal - shareModal element not found!');
        }
        
        // Load organizations if not already loaded or if orgs not provided
        if (!orgs && organizations.length === 0) {
            await loadOrganizations();
            renderOrgTabs();
            renderMembersList();
            renderSharedUsers();
            updateSelectedPreview();
            switchTab('find');
        } else {
            // Render immediately if data is available
        renderOrgTabs();
        renderMembersList();
        renderSharedUsers();
        updateSelectedPreview();
        switchTab('find');
        }

        // Lock body scroll
        document.body.style.overflow = 'hidden';
    }

    // Load shared users from API
    async function loadSharedUsers(noteId) {
        console.log('[ShareModal] loadSharedUsers called for noteId:', noteId);
        try {
            const response = await fetch(`/api/notes/${noteId}/`, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json',
                },
                credentials: 'same-origin'
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            console.log('[ShareModal] Loaded note data:', data);

            if (data.status === 'success' && data.note && data.note.shared_users_list) {
                alreadySharedUsers = data.note.shared_users_list;
                console.log('[ShareModal] Loaded shared users:', alreadySharedUsers);
            } else {
                alreadySharedUsers = [];
                console.log('[ShareModal] No shared users found');
            }
        } catch (error) {
            console.error('[ShareModal] Error loading shared users:', error);
            alreadySharedUsers = [];
        }
    }

    // Load shared schedule users from API
    async function loadSharedScheduleUsers(scheduleId) {
        console.log('[ShareModal] loadSharedScheduleUsers called for scheduleId:', scheduleId);
        try {
            const response = await fetch(`/schedule/api/schedules/${scheduleId}/shared/`, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                credentials: 'same-origin'
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            console.log('[ShareModal] Loaded schedule shared users data:', data);

            if (typeof data.is_owner !== 'undefined') {
                isScheduleOwner = Boolean(data.is_owner);
            } else {
                isScheduleOwner = false;
            }

            if (data.results) {
                alreadySharedUsers = data.results;
                console.log('[ShareModal] Loaded shared schedule users:', alreadySharedUsers);
            } else {
                alreadySharedUsers = [];
                console.log('[ShareModal] No shared schedule users found');
            }
        } catch (error) {
            console.error('[ShareModal] Error loading shared schedule users:', error);
            alreadySharedUsers = [];
            isScheduleOwner = false;
        }
    }

    // Close modal
    function closeModal() {
        if (shareModal) {
            shareModal.classList.remove('active');
        }
        document.body.style.overflow = '';
        
        // Reset state
        selectedMembers = [];
        shareSearchQuery = '';
        selectedOrg = 'all';
        shareModalTab = 'find';
        // Note: currentNoteId, currentScheduleId, shareContext는 다음 openModal 호출 시 설정됨
    }

    // Switch tab
    function switchTab(tab) {
        shareModalTab = tab;
        
        if (tab === 'find') {
            if (shareTabFind) shareTabFind.classList.add('active');
            if (shareTabShared) shareTabShared.classList.remove('active');
            if (shareSearchSection) shareSearchSection.style.display = 'block';
            if (shareTabContentFind) shareTabContentFind.style.display = 'block';
            if (shareTabContentShared) shareTabContentShared.style.display = 'none';
            if (shareModalFooter) shareModalFooter.style.display = 'flex';
        } else {
            if (shareTabFind) shareTabFind.classList.remove('active');
            if (shareTabShared) shareTabShared.classList.add('active');
            if (shareSearchSection) shareSearchSection.style.display = 'none';
            if (shareTabContentFind) shareTabContentFind.style.display = 'none';
            if (shareTabContentShared) shareTabContentShared.style.display = 'block';
            if (shareModalFooter) shareModalFooter.style.display = 'none';
        }
    }

    // Handle search
    function handleSearch(e) {
        shareSearchQuery = e.target.value;
        renderMembersList();
        
        // Show external invite if email format
        if (shareSearchInput && shareSearchQuery.includes('@') && getFilteredMembers().length === 0) {
            if (shareExternalInvite) shareExternalInvite.style.display = 'block';
            if (shareExternalEmail) shareExternalEmail.textContent = shareSearchQuery;
        } else {
            if (shareExternalInvite) shareExternalInvite.style.display = 'none';
        }
    }

    // Get filtered members
    function getFilteredMembers() {
        // 기본적으로 중복 제거된 전체 멤버 목록 사용
        let filtered = uniqueMembers.length > 0 ? uniqueMembers : organizations.flatMap(org => org.members);

        // Filter by organization
        if (selectedOrg !== 'all') {
            const org = organizations.find(o => o.id.toString() === selectedOrg);
            filtered = org ? org.members : [];
        }

        // Filter by search query
        if (shareSearchQuery.trim()) {
            filtered = filtered.filter(
                member =>
                    member.name.toLowerCase().includes(shareSearchQuery.toLowerCase()) ||
                    member.email.toLowerCase().includes(shareSearchQuery.toLowerCase())
            );
        }

        // 이미 공유된 사용자 제외
        if (alreadySharedUsers && alreadySharedUsers.length > 0) {
            const sharedUserIds = alreadySharedUsers.map(user => String(user.id));
            filtered = filtered.filter(member => !sharedUserIds.includes(String(member.id)));
            console.log('[ShareModal] Filtered out shared users. Remaining:', filtered.length);
        }

        return filtered;
    }

    // Render organization tabs
    function renderOrgTabs() {
        if (!shareOrgTabs) return;

        let html = `
            <button class="org-tab-btn ${selectedOrg === 'all' ? 'active' : ''}" data-org="all">
                전체
            </button>
        `;

        organizations.forEach(org => {
            html += `
                <button class="org-tab-btn ${selectedOrg === org.id.toString() ? 'active' : ''}" data-org="${org.id}">
                    ${escapeHtml(org.name)}
                </button>
            `;
        });

        shareOrgTabs.innerHTML = html;

        // Attach click listeners
        shareOrgTabs.querySelectorAll('.org-tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                selectedOrg = btn.getAttribute('data-org');
                renderOrgTabs();
                renderMembersList();
            });
        });
    }

    // Render members list
    function renderMembersList() {
        if (!shareMembersList) return;

        const filtered = getFilteredMembers();

        if (filtered.length === 0) {
            shareMembersList.innerHTML = `
                <div class="share-empty-state">
                    <i class="fa-solid fa-search"></i>
                    <p>검색 결과가 없습니다</p>
                    <p>다른 검색어를 시도해보세요</p>
                </div>
            `;
            return;
        }

        shareMembersList.innerHTML = filtered.map(member => {
            // member.id는 문자열일 수 있으므로 문자열로 비교
            const memberIdStr = String(member.id);
            const isSelected = selectedMembers.some(id => String(id) === memberIdStr);
            const hasAvatar = member.avatar && member.avatar.trim() !== '';
            const avatarStyle = hasAvatar ? `style="background-image: url('${escapeHtml(member.avatar)}');"` : '';
            const avatarHtml = `<div class="profile-avatar profile-avatar-placeholder" ${avatarStyle}>
                    <i class="fa-solid fa-user"></i>
                   </div>`;
            
            return `
                <div class="share-member-item ${isSelected ? 'selected' : ''}" data-member-id="${member.id}">
                    <input type="checkbox" ${isSelected ? 'checked' : ''} />
                    ${avatarHtml}
                    <div class="member-info">
                        <div class="member-name">${escapeHtml(member.name)}</div>
                        <div class="member-email">${escapeHtml(member.email)}</div>
                        <div class="member-role">${escapeHtml(member.role || 'Member')}</div>
                    </div>
                </div>
            `;
        }).join('');

        // Attach click listeners
        shareMembersList.querySelectorAll('.share-member-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (e.target.type === 'checkbox') return;
                const memberId = item.getAttribute('data-member-id');
                toggleMemberSelection(memberId);
            });
        });

        // Attach checkbox listeners
        shareMembersList.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const memberId = e.target.closest('.share-member-item').getAttribute('data-member-id');
                toggleMemberSelection(memberId);
            });
        });
    }

    // Toggle member selection
    function toggleMemberSelection(memberId) {
        // memberId를 문자열로 정규화하여 비교
        const memberIdStr = String(memberId);
        const isSelected = selectedMembers.some(id => String(id) === memberIdStr);
        
        if (isSelected) {
            selectedMembers = selectedMembers.filter(id => String(id) !== memberIdStr);
        } else {
            selectedMembers = [...selectedMembers, memberIdStr];
        }
        renderMembersList();
        updateSelectedPreview();
        updateShareButton();
    }

    // Clear all selection
    function clearAllSelection() {
        selectedMembers = [];
        renderMembersList();
        updateSelectedPreview();
        updateShareButton();
    }

    // Update selected preview
    function updateSelectedPreview() {
        if (!shareSelectedPreview || !shareSelectedCount || !shareSelectedMembersList) return;

        if (selectedMembers.length === 0) {
            shareSelectedPreview.style.display = 'none';
            return;
        }

        shareSelectedPreview.style.display = 'block';
        shareSelectedCount.textContent = `${selectedMembers.length}명 선택됨`;

        // 중복 제거된 전체 멤버 목록 사용
        const allMembers = uniqueMembers.length > 0 ? uniqueMembers : organizations.flatMap(org => org.members);
        shareSelectedMembersList.innerHTML = selectedMembers.map(memberId => {
            const member = allMembers.find(m => m.id === memberId);
            if (!member) return '';
            return `
                <div class="selected-member-chip">
                    <img src="${escapeHtml(member.avatar)}" alt="${escapeHtml(member.name)}" class="chip-avatar" onerror="this.src='https://ui-avatars.com/api/?name=${encodeURIComponent(member.name)}&background=random';" />
                    <span class="chip-member-name">${escapeHtml(member.name)}</span>
                    <button class="btn-remove-member" data-member-id="${memberId}">
                        <i class="fa-solid fa-times"></i>
                    </button>
                </div>
            `;
        }).join('');

        // Attach remove button listeners
        shareSelectedMembersList.querySelectorAll('.btn-remove-member').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const memberId = btn.getAttribute('data-member-id');
                toggleMemberSelection(memberId);
            });
        });
    }

    // Update share button
    function updateShareButton() {
        if (!shareModalShareBtn) return;
        
        if (selectedMembers.length === 0) {
            shareModalShareBtn.disabled = true;
        } else {
            shareModalShareBtn.disabled = false;
        }

        if (shareFooterInfo) {
            if (selectedMembers.length > 0) {
                shareFooterInfo.textContent = `${selectedMembers.length}명에게 공유됩니다`;
            } else {
                shareFooterInfo.textContent = '';
            }
        }
    }

    // Render shared users
    function renderSharedUsers() {
        if (!shareSharedList) return;

        if (alreadySharedUsers.length === 0) {
            shareSharedList.innerHTML = `
                <div class="share-empty-state">
                    <i class="fa-solid fa-users"></i>
                    <p>공유된 사용자가 없습니다</p>
                </div>
            `;
            return;
        }

        shareSharedList.innerHTML = alreadySharedUsers.map(user => {
            const displayName = escapeHtml(user.name || user.full_name || user.email || user.user_id || '사용자');
            const displayEmail = escapeHtml(user.email || user.user_id || '');
            const displayRole = escapeHtml(user.role || (user.is_owner ? '소유자' : '공유자'));
            const sharedDate = formatSharedDate(user.sharedDate || user.created_at);
            const userIdValue = user.user_id || user.id || user.email;
            const avatarSrc = escapeHtml(
                user.avatar ||
                `https://ui-avatars.com/api/?name=${encodeURIComponent(displayName)}&background=random`
            );

            const isPending = user.status === 'pending';
            const statusBadge = isPending
                ? '<span class="shared-status pending">대기중</span>'
                : '<span class="shared-status accepted">공유됨</span>';

            const removeButton = (
                shareContext === 'schedule' &&
                isScheduleOwner &&
                userIdValue &&
                !isPending
            ) ? `<button class="btn-remove-share" data-user-id="${escapeHtml(String(userIdValue))}">
                    공유 해제
                </button>` : '';

            return `
            <div class="share-shared-item${isPending ? ' pending' : ''}">
                <img src="${avatarSrc}" alt="${displayName}" class="shared-avatar" onerror="this.src='https://ui-avatars.com/api/?name=${encodeURIComponent(displayName)}&background=random';" />
                <div class="shared-info">
                    <div class="shared-name">${displayName}</div>
                    <div class="shared-email">${displayEmail}</div>
                    <div class="shared-role">${displayRole}</div>
                    ${statusBadge}
                </div>
                <div class="shared-date-info">
                    <div class="shared-date-label">공유일</div>
                    <div class="shared-date-value">${sharedDate}</div>
                </div>
                ${removeButton}
            </div>
        `;
        }).join('');

        // Attach remove share button listeners
        shareSharedList.querySelectorAll('.btn-remove-share').forEach(btn => {
            btn.addEventListener('click', async () => {
                const userId = btn.getAttribute('data-user-id');
                await removeSharedUser(userId);
            });
        });
    }

    // Handle share
    async function handleShare() {
        console.log('[ShareModal] handleShare called');
        console.log('[ShareModal] selectedMembers:', selectedMembers);
        console.log('[ShareModal] shareContext:', shareContext);
        console.log('[ShareModal] currentNoteId:', currentNoteId);
        console.log('[ShareModal] currentScheduleId:', currentScheduleId);
        
        if (selectedMembers.length === 0) {
            console.log('[ShareModal] No members selected, returning');
            return;
        }

        // 선택한 멤버의 전체 정보 가져오기
        const allMembers = uniqueMembers.length > 0 ? uniqueMembers : organizations.flatMap(org => org.members);
        const selectedMemberDetails = selectedMembers.map(memberId => {
            return allMembers.find(m => String(m.id) === String(memberId));
        }).filter(member => member !== undefined); // undefined 제거

        console.log('[ShareModal] selectedMemberDetails:', selectedMemberDetails);

        // context에 따라 다르게 처리
        if (shareContext === 'schedule' && currentScheduleId) {
            console.log('[ShareModal] Context is schedule, calling performShareSchedule');
            // schedule: 바로 공유 API 호출
            await performShareSchedule(currentScheduleId, selectedMemberDetails);
        } else if (shareContext === 'detail' && currentNoteId) {
            console.log('[ShareModal] Context is detail, calling performShareNote');
            // note_detail: 바로 공유 API 호출
            await performShareNote(currentNoteId, selectedMemberDetails);
        } else {
            console.log('[ShareModal] Context is editor or no resourceId, using callback');
            console.log('[ShareModal] shareContext:', shareContext, 'currentNoteId:', currentNoteId, 'currentScheduleId:', currentScheduleId);
            // note_editor: 콜백으로 전달 (노트 저장 시 함께 저장)
            if (window.ShareModal && window.ShareModal.onShare) {
                console.log('[ShareModal] Calling onShare callback');
                window.ShareModal.onShare(selectedMembers, selectedMemberDetails);
            } else {
                console.log('[ShareModal] onShare callback not found');
            }
        }

        closeModal();
    }

    // Get CSRF token helper
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Perform share schedule (API 호출)
    async function performShareSchedule(scheduleId, selectedMemberDetails) {
        console.log('[ShareModal] performShareSchedule called');
        console.log('[ShareModal] scheduleId:', scheduleId);
        console.log('[ShareModal] selectedMemberDetails:', selectedMemberDetails);
        
        try {
            const csrfToken = getCookie('csrftoken');
            console.log('[ShareModal] CSRF Token:', csrfToken ? 'Found' : 'Not found');
            
            const apiUrl = `/schedule/api/schedules/${scheduleId}/shared/`;
            const requestBody = {
                sharedMembers: selectedMemberDetails
            };
            
            console.log('[ShareModal] API URL:', apiUrl);
            console.log('[ShareModal] Request body:', requestBody);

            const response = await fetch(apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                credentials: 'same-origin',
                body: JSON.stringify(requestBody)
            });

            console.log('[ShareModal] Response status:', response.status);
            console.log('[ShareModal] Response ok:', response.ok);

            const data = await response.json();
            console.log('[ShareModal] Response data:', data);

            if (!response.ok) {
                throw new Error(data.error || '일정 공유에 실패했습니다.');
            }

            if (data.status === 'success') {
                console.log('[ShareModal] Share successful');
                if (window.notyf) {
                    window.notyf.success(selectedMemberDetails.length + '명과 공유되었습니다.');
                }
                
                // 공유된 사용자 목록 다시 로드
                if (scheduleId) {
                    await loadSharedScheduleUsers(scheduleId);
                    renderSharedUsers();
                    renderMembersList();  // 이미 공유된 사용자 제외를 위해 다시 렌더링
                }
                
                // 콜백 호출 (일정 상세 정보 다시 로드 등)
                if (window.ShareModal && window.ShareModal.onShare) {
                    console.log('[ShareModal] Calling onShare callback after successful share');
                    window.ShareModal.onShare(selectedMembers, selectedMemberDetails);
                }
                document.dispatchEvent(new CustomEvent('schedule:sharedUpdated', {
                    detail: { scheduleId }
                }));
            } else {
                throw new Error(data.error || '응답 데이터가 올바르지 않습니다.');
            }
        } catch (error) {
            console.error('[ShareModal] Failed to share schedule:', error);
            console.error('[ShareModal] Error details:', {
                message: error.message,
                stack: error.stack
            });
            if (window.notyf) {
                window.notyf.error(error.message || '일정 공유에 실패했습니다.');
            }
        }
    }

    // Perform share note (API 호출)
    async function performShareNote(noteId, selectedMemberDetails) {
        console.log('[ShareModal] performShareNote called');
        console.log('[ShareModal] noteId:', noteId);
        console.log('[ShareModal] selectedMemberDetails:', selectedMemberDetails);
        
        try {
            const csrfToken = getCookie('csrftoken');
            console.log('[ShareModal] CSRF Token:', csrfToken ? 'Found' : 'Not found');
            
            const apiUrl = `/api/notes/${noteId}/share/`;
            const requestBody = {
                sharedMembers: selectedMemberDetails
            };
            
            console.log('[ShareModal] API URL:', apiUrl);
            console.log('[ShareModal] Request body:', requestBody);

            const response = await fetch(apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                credentials: 'same-origin',
                body: JSON.stringify(requestBody)
            });

            console.log('[ShareModal] Response status:', response.status);
            console.log('[ShareModal] Response ok:', response.ok);

            const data = await response.json();
            console.log('[ShareModal] Response data:', data);

            if (!response.ok) {
                throw new Error(data.error || '노트 공유에 실패했습니다.');
            }

            if (data.status === 'success') {
                console.log('[ShareModal] Share successful');
                if (window.notyf) {
                    window.notyf.success(selectedMemberDetails.length + '명과 공유되었습니다.');
                }
                
                // 공유된 사용자 목록 다시 로드
                if (noteId) {
                    await loadSharedUsers(noteId);
                    renderSharedUsers();
                    renderMembersList();  // 이미 공유된 사용자 제외를 위해 다시 렌더링
                }
                
                // 콜백 호출 (노트 상세 정보 다시 로드 등)
                if (window.ShareModal && window.ShareModal.onShare) {
                    console.log('[ShareModal] Calling onShare callback after successful share');
                    window.ShareModal.onShare(selectedMembers, selectedMemberDetails);
                }
            } else {
                throw new Error(data.error || '응답 데이터가 올바르지 않습니다.');
            }
        } catch (error) {
            console.error('[ShareModal] Failed to share note:', error);
            console.error('[ShareModal] Error details:', {
                message: error.message,
                stack: error.stack
            });
            if (window.notyf) {
                window.notyf.error(error.message || '노트 공유에 실패했습니다.');
            } else {
                alert(error.message || '노트 공유에 실패했습니다.');
            }
        }
    }

    // Handle invite external
    function handleInviteExternal() {
        if (!shareSearchQuery || !shareSearchQuery.includes('@')) return;

        // TODO: Implement external invite API call
        if (window.notyf) {
            window.notyf.success(shareSearchQuery + '로 초대 메일이 전송되었습니다.');
        }

        closeModal();
    }

    // Remove shared user
    async function removeSharedUser(userId) {
        if (!userId || !currentScheduleId || !isScheduleOwner) return;

        const confirmed = await confirmShareRemoval();
        if (!confirmed) return;

        try {
            const response = await fetch(`/schedule/api/schedules/${currentScheduleId}/shared/?user_id=${encodeURIComponent(userId)}`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin',
            });

            const data = await response.json().catch(() => ({}));

            if (response.ok) {
                alreadySharedUsers = alreadySharedUsers.filter(u => {
                    const uid = u.user_id || u.id || u.email;
                    return String(uid) !== String(userId);
                });
                renderSharedUsers();
                if (window.notyf) {
                    window.notyf.success(data.message || '공유가 해제되었습니다.');
                }
                if (window.ShareModal && window.ShareModal.onShare) {
                    window.ShareModal.onShare([], []);
                }
                document.dispatchEvent(new CustomEvent('schedule:sharedUpdated', {
                    detail: { scheduleId: currentScheduleId }
                }));
            } else {
                const message = data.error || '공유 해제에 실패했습니다.';
                if (window.notyf) {
                    window.notyf.error(message);
                } else {
                    alert(message);
                }
            }
        } catch (error) {
            console.error('[ShareModal] Failed to remove shared user:', error);
            if (window.notyf) {
                window.notyf.error('공유 해제 중 오류가 발생했습니다.');
            } else {
                alert('공유 해제 중 오류가 발생했습니다.');
            }
        }
    }

    async function confirmShareRemoval() {
        if (window.Swal) {
            const result = await window.Swal.fire({
                title: '공유 해제',
                text: '선택한 사용자와의 공유를 해제하시겠습니까?',
                icon: 'warning',
                showCancelButton: true,
                confirmButtonText: '해제',
                cancelButtonText: '취소',
                confirmButtonColor: '#ef4444',
                cancelButtonColor: '#6b7280',
            });
            return result.isConfirmed;
        }
        return confirm('선택한 사용자와의 공유를 해제하시겠습니까?');
    }

    function formatSharedDate(dateString) {
        if (!dateString) return '-';
        const date = new Date(dateString);
        if (isNaN(date.getTime())) return '-';
        return date.toLocaleString('ko-KR', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    // Escape HTML
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Get all members from all organizations (helper for external use)
    function getAllMembers() {
        // 중복 제거된 전체 멤버 목록 반환
        return uniqueMembers.length > 0 ? uniqueMembers : organizations.flatMap(org => org.members);
    }

    // Export to window (IIFE 내부에서 즉시 실행)
    console.log('[ShareModal] Setting window.ShareModal');
    window.ShareModal = {
        open: openModal,
        close: closeModal,
        toggleMemberSelection,
        removeSharedUser,
        _getAllMembers: getAllMembers,
        onShare: null // Will be set by parent
    };
    console.log('[ShareModal] window.ShareModal set:', window.ShareModal);

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            console.log('[ShareModal] DOMContentLoaded - initializing...');
            initShareModal();
        });
    } else {
        console.log('[ShareModal] DOM already ready - initializing...');
        initShareModal();
    }
})();
