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

    // All notes (will use mock data)
    let allNotes = [...allMockNotes];

    // DOM elements
    const modalId = 'saveToNoteModal';
    let tabGroup = null;
    let noteSearchInput = null;
    let notesList = null;
    let notesPagination = null;
    let newNoteNameInput = null;
    let saveNoteBtn = null;

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

        // Search input
        if (noteSearchInput) {
            noteSearchInput.addEventListener('input', (e) => {
                setNoteSearchQuery(e.target.value);
                currentPage = 1; // Reset to page 1 on search
                renderNotesList();
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

    // Load notes (use mock data)
    function loadNotes() {
        allNotes = [...allMockNotes];
        currentPage = 1;
        selectedNote = null;
        renderNotesList();
    }

    // Filter notes by search query
    function getFilteredNotes() {
        if (!noteSearchQuery.trim()) {
            return allNotes;
        }

        const query = noteSearchQuery.toLowerCase();
        return allNotes.filter(note =>
            note.title.toLowerCase().includes(query) ||
            (note.category && note.category.toLowerCase().includes(query))
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
    function handleSave() {
        if (saveToNoteOption === 'existing' && selectedNote) {
            const saveData = {
                option: 'existing',
                noteId: selectedNote.id,
                noteTitle: selectedNote.title,
            };

            // Dispatch event
            document.dispatchEvent(new CustomEvent('saveToNote:save', { detail: saveData }));

            // Call callback if provided
            if (saveToNoteContext && typeof saveToNoteContext.onSave === 'function') {
                saveToNoteContext.onSave('existing', selectedNote.title);
            }

            closeSaveToNoteModal();
        } else if (saveToNoteOption === 'new' && newNoteName.trim()) {
            const saveData = {
                option: 'new',
                noteName: newNoteName.trim(),
            };

            // Dispatch event
            document.dispatchEvent(new CustomEvent('saveToNote:save', { detail: saveData }));

            // Call callback if provided
            if (saveToNoteContext && typeof saveToNoteContext.onSave === 'function') {
                saveToNoteContext.onSave('new', newNoteName.trim());
            }

            closeSaveToNoteModal();
        }
    }

    // Reset state
    function resetState() {
        saveToNoteOption = 'existing';
        selectedNote = null;
        newNoteName = '';
        noteSearchQuery = '';
        currentPage = 1;
        saveToNoteContext = null;

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
        console.log('[SaveToNoteModal] Opening modal...');

        // Ensure initialization
        if (!isInitialized) {
            initSaveToNoteModal();
        }

        const modal = document.getElementById(modalId);
        if (!modal) {
            console.error('[SaveToNoteModal] Modal element not found');
            return;
        }

        // Store context
        saveToNoteContext = data;

        // Update title and description if provided
        if (data && data.title) {
            const titleEl = document.getElementById('saveToNoteModalTitle');
            if (titleEl) titleEl.textContent = data.title;
        }
        if (data && data.description) {
            const descEl = document.getElementById('saveToNoteModalDescription');
            if (descEl) descEl.textContent = data.description;
        }

        // Reset and load notes
        resetState();
        loadNotes();
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
