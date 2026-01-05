// Save to Note Modal Component JavaScript Logic
console.log('[SaveToNoteModal] ===== Script file loading... =====');

(function() {
    'use strict';

    console.log('[SaveToNoteModal] IIFE starting...');

    // State variables
    let saveToNoteOption = 'existing'; // 'existing' | 'new'
    let selectedNote = null;
    let newNoteName = '';
    let noteSearchQuery = '';
    let currentPage = 1;
    let saveToNoteContext = null;
    let isInitialized = false;
    const ITEMS_PER_PAGE = 5;

    // Mock notes data - matching React component
    const allMockNotes = [
        { id: 1, title: '진핵세포 연구 노트', date: '2025-11-28', category: '세포생물학' },
        { id: 2, title: 'EGFR 실험 자료', date: '2025-11-27', category: '단백질' },
        { id: 3, title: '약물 설계 관련', date: '2025-11-26', category: '약물개발' },
        { id: 4, title: '단백질 구조 분석', date: '2025-11-25', category: '단백질' },
        { id: 5, title: '임상 연구 메모', date: '2025-11-24', category: '임상' },
        { id: 6, title: 'CRISPR 유전자 편집', date: '2025-11-23', category: '유전학' },
        { id: 7, title: 'RNA 서열 분석', date: '2025-11-22', category: '분자생물학' },
        { id: 8, title: '면역학 실험 기록', date: '2025-11-21', category: '면역학' },
        { id: 9, title: '세포 배양 프로토콜', date: '2025-11-20', category: '세포생물학' },
        { id: 10, title: '항체 정제 과정', date: '2025-11-19', category: '단백질' },
        { id: 11, title: '유전체 시퀀싱 데이터', date: '2025-11-18', category: '유전학' },
        { id: 12, title: 'PCR 실험 결과', date: '2025-11-17', category: '분자생물학' },
        { id: 13, title: '암세포 분석 노트', date: '2025-11-16', category: '종양학' },
        { id: 14, title: '신약 후보 물질 탐색', date: '2025-11-15', category: '약물개발' },
        { id: 15, title: '바이오마커 연구', date: '2025-11-14', category: '진단' },
    ];

    // All notes (will be loaded from API)
    let allNotes = [];

    // DOM elements
    const modalId = 'saveToNoteModal';
    let tabGroup = null;
    let noteSearchInput = null;
    let notesList = null;
    let notesPagination = null;
    let newNoteNameInput = null;
    let saveNoteBtn = null;
    let isLoadingNotes = false;

    // Get DOM elements
    function getModalElements() {
        tabGroup = document.getElementById('saveToNoteTabGroup');
        noteSearchInput = document.getElementById('noteSearchInput');
        notesList = document.getElementById('notesList');
        notesPagination = document.getElementById('notesPagination');
        newNoteNameInput = document.getElementById('newNoteName');
        saveNoteBtn = document.getElementById('saveNoteBtn');
    }

    // Initialize modal
    function initSaveToNoteModal() {
        if (isInitialized) return true;

        const modal = document.getElementById(modalId);
        if (!modal) {
            console.warn('[SaveToNoteModal] Modal element not found');
            return false;
        }

        // Get DOM elements
        getModalElements();

        // Close button handler
        const closeBtns = modal.querySelectorAll('[data-action="close"]');
        closeBtns.forEach(btn => {
            btn.addEventListener('click', closeSaveToNoteModal);
        });

        // Shoelace tab change handler
        if (tabGroup) {
            customElements.whenDefined('sl-tab-group').then(() => {
                tabGroup.addEventListener('sl-tab-show', (e) => {
                    const panelName = e.detail.name;
                    setSaveToNoteOption(panelName === 'existing' ? 'existing' : 'new');
                });
            });
        }

        // Search input with debounce
        let searchTimeout = null;
        if (noteSearchInput) {
            noteSearchInput.addEventListener('input', (e) => {
                const query = e.target.value;
                setNoteSearchQuery(query);
                currentPage = 1; // Reset to page 1 on search
                
                // Debounce API calls (500ms delay)
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    loadNotes(query);
                }, 500);
            });
        }

        // New note name input
        if (newNoteNameInput) {
            newNoteNameInput.addEventListener('input', (e) => {
                newNoteName = e.target.value;
                updateSaveButtonState();
            });
        }

        // Save button handler
        if (saveNoteBtn) {
            saveNoteBtn.addEventListener('click', handleSave);
        }

        isInitialized = true;
        console.log('[SaveToNoteModal] Initialized successfully');
        return true;
    }

    // Load notes from API
    async function loadNotes(searchQuery = '') {
        if (isLoadingNotes) return;
        
        isLoadingNotes = true;
        
        // Show loading state
        if (notesList) {
            notesList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-spinner fa-spin empty-icon"></i>
                    <p class="empty-text">노트 목록을 불러오는 중...</p>
                </div>
            `;
        }
        
        try {
            // Build API URL with query parameters
            const params = new URLSearchParams();
            if (searchQuery) {
                params.append('search', searchQuery);
            }
            params.append('my_notes_only', 'true'); // 내 노트만 조회
            
            const apiUrl = `/api/notes/?${params.toString()}`;
            
            const response = await fetch(apiUrl, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin',
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.status === 'success' && Array.isArray(data.results)) {
                // Transform API response to match expected format
                allNotes = data.results.map(note => ({
                    id: note.id,
                    title: note.title,
                    date: note.date,
                    category: note.tags && note.tags.length > 0 ? note.tags[0] : '', // 첫 번째 태그를 카테고리로 사용
                    tags: note.tags || [],
                }));
                
        currentPage = 1;
        selectedNote = null;
        renderNotesList();
            } else {
                throw new Error('Invalid response format');
            }
        } catch (error) {
            console.error('[SaveToNoteModal] Failed to load notes:', error);
            
            // Show error state
            if (notesList) {
                notesList.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-exclamation-triangle empty-icon"></i>
                        <p class="empty-text">노트 목록을 불러오는데 실패했습니다</p>
                        <p class="empty-hint">${error.message}</p>
                        <button class="retry-btn" onclick="window.SaveToNoteModal && window.SaveToNoteModal.loadNotes()">
                            다시 시도
                        </button>
                    </div>
                `;
            }
            
            // Fallback to empty array
            allNotes = [];
            renderNotesList();
        } finally {
            isLoadingNotes = false;
        }
    }

        // Filter notes by search query (client-side filtering for pagination)
    // Note: API already filters by search query, but we filter again for client-side pagination
    function getFilteredNotes() {
        if (!noteSearchQuery.trim()) {
            return allNotes;
        }

        const query = noteSearchQuery.toLowerCase();
        return allNotes.filter(note =>
            note.title.toLowerCase().includes(query) ||
            (note.category && note.category.toLowerCase().includes(query)) ||
            (note.tags && note.tags.some(tag => tag.toLowerCase().includes(query)))
        );
    }

    // Calculate pagination
    function getPaginatedNotes() {
        const filtered = getFilteredNotes();
        const totalPages = Math.ceil(filtered.length / ITEMS_PER_PAGE);
        const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
        const endIndex = startIndex + ITEMS_PER_PAGE;
        const paginated = filtered.slice(startIndex, endIndex);

        return {
            notes: paginated,
            totalPages,
            startIndex,
            endIndex,
            total: filtered.length,
        };
    }

    // Render notes list
    function renderNotesList() {
        if (!notesList) {
            getModalElements();
        }
        if (!notesList) return;

        const { notes, totalPages, total, startIndex, endIndex } = getPaginatedNotes();

        if (notes.length === 0) {
            notesList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-file-alt empty-icon"></i>
                    <p class="empty-text">검색 결과가 없습니다</p>
                    <p class="empty-hint">다른 검색어를 입력해보세요</p>
                </div>
            `;
            renderPagination(0, 0);
            return;
        }

        notesList.innerHTML = notes.map(note => {
            const isSelected = selectedNote && selectedNote.title === note.title;
            return `
                <button class="note-item ${isSelected ? 'selected' : ''}" data-note-id="${note.id}" data-note-title="${escapeHtml(note.title)}">
                    <i class="fas fa-file-alt note-icon"></i>
                    <div class="note-item-content">
                        <p class="note-item-title">${escapeHtml(note.title)}</p>
                        <div class="note-item-meta">
                            <span class="note-date">${note.date}</span>
                            <span class="note-meta-separator">•</span>
                            <span class="note-category">${escapeHtml(note.category)}</span>
                        </div>
                    </div>
                    ${isSelected ? `
                        <svg class="note-checkmark" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                        </svg>
                    ` : ''}
                </button>
            `;
        }).join('');

        // Attach click handlers
        notesList.querySelectorAll('.note-item').forEach(item => {
            item.addEventListener('click', () => {
                const noteId = parseInt(item.getAttribute('data-note-id'));
                const note = allNotes.find(n => n.id === noteId);
                if (note) {
                    setSelectedNote(note);
                    renderNotesList();
                }
            });
        });

        renderPagination(totalPages, total);
    }

    // Render pagination
    function renderPagination(totalPages, total) {
        if (!notesPagination) {
            getModalElements();
        }
        if (!notesPagination) return;

        const { startIndex, endIndex } = getPaginatedNotes();
        const filtered = getFilteredNotes();

        if (totalPages <= 0) {
            notesPagination.innerHTML = '';
            return;
        }

        const pages = [];
        for (let i = 1; i <= totalPages; i++) {
            pages.push(i);
        }

        notesPagination.innerHTML = `
            <div class="pagination-info-left">
                총 ${filtered.length}개 중 ${startIndex + 1}-${Math.min(endIndex, filtered.length)}개 표시
            </div>
            <div class="pagination-controls">
                <button class="pagination-btn pagination-btn-nav" ${currentPage === 1 ? 'disabled' : ''} data-page="${currentPage - 1}">
                    <i class="fas fa-chevron-left"></i>
                </button>
                ${pages.map(page => `
                    <button class="pagination-btn pagination-btn-number ${page === currentPage ? 'active' : ''}" data-page="${page}">
                        ${page}
                    </button>
                `).join('')}
                <button class="pagination-btn pagination-btn-nav" ${currentPage === totalPages ? 'disabled' : ''} data-page="${currentPage + 1}">
                    <i class="fas fa-chevron-right"></i>
                </button>
            </div>
        `;

        // Attach pagination handlers
        notesPagination.querySelectorAll('.pagination-btn[data-page]').forEach(btn => {
            btn.addEventListener('click', () => {
                if (btn.disabled) return;
                const page = parseInt(btn.getAttribute('data-page'));
                handlePageChange(page);
            });
        });
    }

    // Set save option
    function setSaveToNoteOption(option) {
        saveToNoteOption = option;
        // Clear selection when switching tabs
        selectedNote = null;
        newNoteName = '';

        if (newNoteNameInput) {
            newNoteNameInput.value = '';
        }

        // Focus on new note input when switching to 'new' tab
        if (option === 'new' && newNoteNameInput) {
            setTimeout(() => newNoteNameInput.focus(), 100);
        }

        updateSaveButtonState();
    }

    // Set selected note
    function setSelectedNote(note) {
        selectedNote = note;
        updateSaveButtonState();
    }

    // Set search query
    function setNoteSearchQuery(query) {
        noteSearchQuery = query;
    }

    // Handle page change
    function handlePageChange(page) {
        currentPage = page;
        selectedNote = null;
        renderNotesList();
    }

    // Update save button state
    function updateSaveButtonState() {
        if (!saveNoteBtn) {
            getModalElements();
        }
        if (!saveNoteBtn) return;

        const isDisabled = (saveToNoteOption === 'existing' && !selectedNote) ||
                           (saveToNoteOption === 'new' && !newNoteName.trim());

        saveNoteBtn.disabled = isDisabled;
    }

    // Handle save
    async function handleSave() {
        const messageId = saveToNoteContext?.messageId;
        
        if (!messageId) {
            console.error('[SaveToNoteModal] messageId가 없습니다.');
            if (window.notyf) {
                window.notyf.error('메시지 ID를 찾을 수 없습니다.');
            }
            return;
        }
        
        // Save button 비활성화 (중복 요청 방지)
        if (saveNoteBtn) {
            saveNoteBtn.disabled = true;
            saveNoteBtn.textContent = '저장 중...';
        }
        
        try {
        if (saveToNoteOption === 'existing' && selectedNote) {
                // 기존 노트에 추가
                const response = await fetch('/api/notes/save-message/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify({
                        message_id: parseInt(messageId),
                        option: 'existing',
                        note_id: selectedNote.id,
                    }),
                });
                
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ error: '알 수 없는 오류가 발생했습니다.' }));
                    throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
                }
                
                const data = await response.json();
                
                if (data.status === 'success') {
                    // Dispatch event
                    document.dispatchEvent(new CustomEvent('saveToNote:save', { 
                        detail: {
                option: 'existing',
                noteId: selectedNote.id,
                noteTitle: selectedNote.title,
                            data: data
                        }
                    }));

            // Call callback if provided
            if (saveToNoteContext && typeof saveToNoteContext.onSave === 'function') {
                saveToNoteContext.onSave('existing', selectedNote.title);
            }

            closeSaveToNoteModal();
                } else {
                    throw new Error(data.error || '저장에 실패했습니다.');
                }
                
        } else if (saveToNoteOption === 'new' && newNoteName.trim()) {
                // 신규 노트 생성
                const response = await fetch('/api/notes/save-message/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify({
                        message_id: parseInt(messageId),
                        option: 'new',
                        note_name: newNoteName.trim(),
                    }),
                });
                
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ error: '알 수 없는 오류가 발생했습니다.' }));
                    throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
                }
                
                const data = await response.json();
                
                if (data.status === 'success') {
                    // Dispatch event
                    document.dispatchEvent(new CustomEvent('saveToNote:save', { 
                        detail: {
                option: 'new',
                noteName: newNoteName.trim(),
                            data: data
                        }
                    }));

            // Call callback if provided
            if (saveToNoteContext && typeof saveToNoteContext.onSave === 'function') {
                saveToNoteContext.onSave('new', newNoteName.trim());
            }

            closeSaveToNoteModal();
                } else {
                    throw new Error(data.error || '저장에 실패했습니다.');
                }
            }
        } catch (error) {
            console.error('[SaveToNoteModal] Failed to save:', error);
            if (window.notyf) {
                window.notyf.error(error.message || '노트 저장 중 오류가 발생했습니다.');
            }
        } finally {
            // Save button 재활성화
            if (saveNoteBtn) {
                saveNoteBtn.disabled = false;
                saveNoteBtn.textContent = '저장';
                updateSaveButtonState(); // 상태에 따라 다시 비활성화할 수 있음
            }
        }
    }

    // Reset state
    function resetState() {
        saveToNoteOption = 'existing';
        selectedNote = null;
        newNoteName = '';
        noteSearchQuery = '';
        currentPage = 1;
        // saveToNoteContext는 reset하지 않음 (messageId 보존을 위해)

        if (noteSearchInput) noteSearchInput.value = '';
        if (newNoteNameInput) newNoteNameInput.value = '';

        // Reset tab to existing
        if (tabGroup) {
            const existingTab = tabGroup.querySelector('sl-tab[panel="existing"]');
            if (existingTab) {
                existingTab.click();
            }
        }
    }

    // Open modal
    function openSaveToNoteModal(data = null) {
        console.log('[SaveToNoteModal] Opening modal...', data);

        // Ensure initialization
        if (!isInitialized) {
            initSaveToNoteModal();
        }

        const modal = document.getElementById(modalId);
        if (!modal) {
            console.error('[SaveToNoteModal] Modal element not found');
            return;
        }

        // Store context (data 전체를 저장하여 messageId 보존)
        saveToNoteContext = data ? { ...data } : null;
        
        // 디버깅: 저장된 context 확인
        console.log('[SaveToNoteModal] saveToNoteContext:', saveToNoteContext);
        console.log('[SaveToNoteModal] messageId:', saveToNoteContext?.messageId);

        // Update title and description if provided
        if (data && data.title) {
            const titleEl = document.getElementById('saveToNoteModalTitle');
            if (titleEl) titleEl.textContent = data.title;
        }
        if (data && data.description) {
            const descEl = document.getElementById('saveToNoteModalDescription');
            if (descEl) descEl.textContent = data.description;
        }

        // Save context temporarily before reset
        const tempContext = data ? { ...data } : null;
        
        // Reset state (이 함수는 saveToNoteContext를 null로 초기화함)
        resetState();
        
        // Restore context after reset (messageId 보존)
        saveToNoteContext = tempContext;
        console.log('[SaveToNoteModal] Context 복원됨:', saveToNoteContext);
        console.log('[SaveToNoteModal] messageId:', saveToNoteContext?.messageId);
        
        // Load notes from API (search query will be empty initially)
        loadNotes('');
        updateSaveButtonState();

        modal.classList.add('active');
        console.log('[SaveToNoteModal] Modal opened');
    }

    // Close modal
    function closeSaveToNoteModal() {
        const modal = document.getElementById(modalId);
        if (!modal) return;

        modal.classList.remove('active');
        resetState();
    }

    // Escape HTML
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Export to window immediately
    console.log('[SaveToNoteModal] Assigning window.SaveToNoteModal...');
    window.SaveToNoteModal = {
        open: openSaveToNoteModal,
        close: closeSaveToNoteModal,
        init: initSaveToNoteModal,
        loadNotes: loadNotes,
        isReady: function() {
            return isInitialized;
        }
    };
    console.log('[SaveToNoteModal] window.SaveToNoteModal assigned:', window.SaveToNoteModal);

    // Initialize when DOM is ready
    function tryInit() {
        if (initSaveToNoteModal()) {
            document.dispatchEvent(new Event('saveToNoteModal:ready'));
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

    console.log('[SaveToNoteModal] Script loaded, window.SaveToNoteModal available');
})();
