// Share Modal for Notes
(function() {
    'use strict';

    // State
    let selectedMembers = [];
    let shareSearchQuery = '';
    let selectedOrg = 'all';
    let shareModalTab = 'find';
    let organizations = [];
    let alreadySharedUsers = [];
    let currentNoteId = null;

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

    // Mock data (matching the image)
    const mockOrganizations = [
        {
            id: 1,
            name: 'BioProtia Research Lab',
            members: [
                { id: 1, name: 'Dr. Sarah Kim', email: 'sarah.kim@bioprotia.com', avatar: 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=100&h=100&fit=crop', role: 'Principal Investigator' },
                { id: 2, name: 'Dr. John Lee', email: 'john.lee@bioprotia.com', avatar: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=100&h=100&fit=crop', role: 'Senior Researcher' },
                { id: 3, name: 'Dr. Emily Chen', email: 'emily.chen@bioprotia.com', avatar: 'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=100&h=100&fit=crop', role: 'Researcher' },
                { id: 4, name: 'Dr. Michael Park', email: 'michael.park@bioprotia.com', avatar: 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=100&h=100&fit=crop', role: 'Postdoc' }
            ]
        },
        {
            id: 2,
            name: 'Genomics Division',
            members: [
                { id: 5, name: 'Dr. Lisa Wang', email: 'lisa.wang@bioprotia.com', avatar: 'https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=100&h=100&fit=crop', role: 'Division Head' },
                { id: 6, name: 'Dr. David Kim', email: 'david.kim@bioprotia.com', avatar: 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=100&h=100&fit=crop', role: 'Senior Scientist' },
                { id: 7, name: 'Dr. Anna Lee', email: 'anna.lee@bioprotia.com', avatar: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&h=100&fit=crop', role: 'Research Scientist' },
                { id: 8, name: 'Dr. James Park', email: 'james.park@bioprotia.com', avatar: 'https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=100&h=100&fit=crop', role: 'Lab Manager' }
            ]
        }
    ];

    const mockAlreadySharedUsers = [
        { id: 1, name: 'Dr. Sarah Kim', email: 'sarah.kim@bioprotia.com', avatar: 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=100&h=100&fit=crop', role: 'Principal Investigator', sharedDate: '2025-12-10' },
        { id: 3, name: 'Dr. Emily Chen', email: 'emily.chen@bioprotia.com', avatar: 'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=100&h=100&fit=crop', role: 'Researcher', sharedDate: '2025-12-08' }
    ];

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

        // Load organizations (mock for now)
        organizations = mockOrganizations;
        alreadySharedUsers = mockAlreadySharedUsers;
    }

    // Open modal
    function openModal(noteId, orgs, sharedUsers, title) {
        console.log('[ShareModal] openModal called with:', { noteId, orgs, sharedUsers, title });
        console.log('[ShareModal] shareModal element:', shareModal);
        console.log('[ShareModal] shareModalTitle element:', shareModalTitle);
        
        // Re-query if not found (in case it was loaded dynamically)
        if (!shareModal) {
            console.log('[ShareModal] shareModal is null, re-querying...');
            shareModal = document.getElementById('shareModal');
            console.log('[ShareModal] Re-queried shareModal:', shareModal);
        }
        
        currentNoteId = noteId;
        if (orgs) organizations = orgs;
        if (sharedUsers) alreadySharedUsers = sharedUsers;
        
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
        
        // Render
        renderOrgTabs();
        renderMembersList();
        renderSharedUsers();
        updateSelectedPreview();
        switchTab('find');

        // Lock body scroll
        document.body.style.overflow = 'hidden';
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
        const allMembers = organizations.flatMap(org => org.members);
        let filtered = allMembers;

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
            const isSelected = selectedMembers.includes(member.id);
            return `
                <div class="share-member-item ${isSelected ? 'selected' : ''}" data-member-id="${member.id}">
                    <input type="checkbox" ${isSelected ? 'checked' : ''} />
                    <img src="${escapeHtml(member.avatar)}" alt="${escapeHtml(member.name)}" class="member-avatar" onerror="this.src='https://ui-avatars.com/api/?name=${encodeURIComponent(member.name)}&background=random';" />
                    <div class="member-info">
                        <div class="member-name">${escapeHtml(member.name)}</div>
                        <div class="member-email">${escapeHtml(member.email)}</div>
                        <div class="member-role">${escapeHtml(member.role)}</div>
                    </div>
                </div>
            `;
        }).join('');

        // Attach click listeners
        shareMembersList.querySelectorAll('.share-member-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (e.target.type === 'checkbox') return;
                const memberId = parseInt(item.getAttribute('data-member-id'));
                toggleMemberSelection(memberId);
            });
        });

        // Attach checkbox listeners
        shareMembersList.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const memberId = parseInt(e.target.closest('.share-member-item').getAttribute('data-member-id'));
                toggleMemberSelection(memberId);
            });
        });
    }

    // Toggle member selection
    function toggleMemberSelection(memberId) {
        if (selectedMembers.includes(memberId)) {
            selectedMembers = selectedMembers.filter(id => id !== memberId);
        } else {
            selectedMembers = [...selectedMembers, memberId];
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

        const allMembers = organizations.flatMap(org => org.members);
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
                const memberId = parseInt(btn.getAttribute('data-member-id'));
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

        shareSharedList.innerHTML = alreadySharedUsers.map(user => `
            <div class="share-shared-item">
                <img src="${escapeHtml(user.avatar)}" alt="${escapeHtml(user.name)}" class="shared-avatar" onerror="this.src='https://ui-avatars.com/api/?name=${encodeURIComponent(user.name)}&background=random';" />
                <div class="shared-info">
                    <div class="shared-name">${escapeHtml(user.name)}</div>
                    <div class="shared-email">${escapeHtml(user.email)}</div>
                    <div class="shared-role">${escapeHtml(user.role)}</div>
                </div>
                <div class="shared-date-info">
                    <div class="shared-date-label">공유일</div>
                    <div class="shared-date-value">${escapeHtml(user.sharedDate)}</div>
                </div>
                <button class="btn-remove-share" data-user-id="${user.id}">
                    공유 해제
                </button>
            </div>
        `).join('');

        // Attach remove share button listeners
        shareSharedList.querySelectorAll('.btn-remove-share').forEach(btn => {
            btn.addEventListener('click', () => {
                const userId = parseInt(btn.getAttribute('data-user-id'));
                removeSharedUser(userId);
            });
        });
    }

    // Handle share
    function handleShare() {
        if (selectedMembers.length === 0) return;

        // Callback to parent
        if (window.ShareModal && window.ShareModal.onShare) {
            window.ShareModal.onShare(selectedMembers);
        }

        // Show success message
        if (window.notyf) {
            window.notyf.success(`${selectedMembers.length}명에게 공유되었습니다.`);
        }

        closeModal();
    }

    // Handle invite external
    function handleInviteExternal() {
        if (!shareSearchQuery || !shareSearchQuery.includes('@')) return;

        // TODO: Implement external invite API call
        if (window.notyf) {
            window.notyf.success(`${shareSearchQuery}로 초대 메일이 전송되었습니다.`);
        }

        closeModal();
    }

    // Remove shared user
    function removeSharedUser(userId) {
        // TODO: Implement remove share API call
        alreadySharedUsers = alreadySharedUsers.filter(u => u.id !== userId);
        renderSharedUsers();
        
        if (window.notyf) {
            window.notyf.success('공유가 해제되었습니다.');
        }
    }

    // Escape HTML
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

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

    // Get all members from all organizations (helper for external use)
    function getAllMembers() {
        return organizations.flatMap(org => org.members);
    }

    // Export to window
    window.ShareModal = {
        open: openModal,
        close: closeModal,
        toggleMemberSelection,
        removeSharedUser,
        _getAllMembers: getAllMembers,
        onShare: null // Will be set by parent
    };
})();
