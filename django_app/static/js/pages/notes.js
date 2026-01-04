// Notes List Page JavaScript

// State variables
let currentPage = 1;
let searchQuery = "";
let selectedDateRange = undefined;
let notesPerPage = 10;
let viewMode = 'card';
let myNotesOnly = false;

// DOM Elements
let notesListView;
let btnCreateNote, btnCreateNoteBottom;
let notesGrid, notesTableContainer, notesTableBody, paginationControls;
let searchInput, notesPerPageSelect;
let btnCardView, btnTableView;
// Date filter elements
let btnDateFilter, dateFilterText, dateFilterPopover, dateFilterCalendar, dateFilterActions, btnDateReset;
// Search buttons
let btnResetSearch, btnSearch;
// My notes only checkbox
let chkMyNotesOnly;
// window.airDatepickerInstance는 window 객체에 저장 (중복 초기화 방지 및 디버깅용)

// Notes data state
let notes = [];
let isLoadingNotes = false;

// Initialize
function initNotes() {
    // Get DOM elements
    notesListView = document.getElementById('notesListView');
    btnCreateNote = document.getElementById('btnCreateNote');
    btnCreateNoteBottom = document.getElementById('btnCreateNoteBottom');
    notesGrid = document.getElementById('notesGrid');
    notesTableContainer = document.getElementById('notesTableContainer');
    notesTableBody = document.getElementById('notesTableBody');
    paginationControls = document.getElementById('paginationControls');
    searchInput = document.getElementById('searchInput');
    notesPerPageSelect = document.getElementById('notesPerPageSelect');
    btnCardView = document.getElementById('btnCardView');
    btnTableView = document.getElementById('btnTableView');
    // Date filter elements
    btnDateFilter = document.getElementById('btnDateFilter');
    dateFilterText = document.getElementById('dateFilterText');
    dateFilterPopover = document.getElementById('dateFilterPopover');
    dateFilterCalendar = document.getElementById('dateFilterCalendar');
    dateFilterActions = document.getElementById('dateFilterActions');
    btnDateReset = document.getElementById('btnDateReset');
    // Search buttons
    btnResetSearch = document.getElementById('btnResetSearch');
    btnSearch = document.getElementById('btnSearch');
    // My notes only checkbox
    chkMyNotesOnly = document.getElementById('chkMyNotesOnly');

    // Attach event listeners
    if (btnCreateNote) btnCreateNote.addEventListener('click', handleCreateNote);
    if (btnCreateNoteBottom) btnCreateNoteBottom.addEventListener('click', handleCreateNote);
    if (searchInput) {
        // Enter 키로 검색 실행
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                handleSearchSubmit();
            }
        });
    }
    if (notesPerPageSelect) notesPerPageSelect.addEventListener('change', handleNotesPerPageChange);
    if (btnCardView) btnCardView.addEventListener('click', () => handleViewModeChange('card'));
    if (btnTableView) btnTableView.addEventListener('click', () => handleViewModeChange('table'));
    // Date filter event listeners
    if (btnDateFilter) btnDateFilter.addEventListener('click', handleToggleDateFilter);
    if (btnDateReset) btnDateReset.addEventListener('click', handleResetDateFilter);
    // Search button event listeners
    if (btnResetSearch) btnResetSearch.addEventListener('click', handleResetAllFilters);
    if (btnSearch) btnSearch.addEventListener('click', handleSearchSubmit);
    // My notes only checkbox event listener
    if (chkMyNotesOnly) {
        chkMyNotesOnly.addEventListener('change', handleMyNotesOnlyChange);
    }
    
    // Initialize AirDatepicker
    initDateFilter();

    // Load user settings and apply view mode
    loadUserSettings().then(() => {
        // Render initial state
        renderNotesList();
        renderPagination();

        // Load notes from API
        loadNotesFromApi();
    });
}

// Load user settings and apply
async function loadUserSettings() {
    const savedViewMode = await loadNotesViewMode();
    viewMode = savedViewMode;
    
    // Apply view mode to UI
    if (btnCardView && btnTableView) {
        if (viewMode === 'card') {
            btnCardView.classList.add('active');
            btnTableView.classList.remove('active');
        } else {
            btnCardView.classList.remove('active');
            btnTableView.classList.add('active');
        }
    }
    
    // Apply view mode display
    if (notesGrid && notesTableContainer) {
        if (viewMode === 'card') {
            notesGrid.style.display = 'grid';
            notesTableContainer.style.display = 'none';
        } else {
            notesGrid.style.display = 'none';
            notesTableContainer.style.display = 'block';
        }
    }
}

// Load notes via API
async function loadNotesFromApi() {
    if (isLoadingNotes) return;
    isLoadingNotes = true;
    
    try {
        // Build query parameters
        const params = new URLSearchParams();
        if (myNotesOnly) {
            params.append('my_notes_only', 'true');
        }
        if (searchQuery && searchQuery.trim()) {
            params.append('search', searchQuery.trim());
        }
        // 날짜 필터 파라미터 추가
        if (selectedDateRange?.from) {
            const fromDate = selectedDateRange.from;
            const fromStr = `${fromDate.getFullYear()}-${String(fromDate.getMonth() + 1).padStart(2, '0')}-${String(fromDate.getDate()).padStart(2, '0')}`;
            params.append('date_from', fromStr);
        }
        if (selectedDateRange?.to) {
            const toDate = selectedDateRange.to;
            const toStr = `${toDate.getFullYear()}-${String(toDate.getMonth() + 1).padStart(2, '0')}-${String(toDate.getDate()).padStart(2, '0')}`;
            params.append('date_to', toStr);
        }
        
        const url = '/api/notes/' + (params.toString() ? '?' + params.toString() : '');
        console.log('[Notes] Loading notes from API:', url);
        
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
            },
        });
        
        if (!response.ok) {
            throw new Error(`Failed to load notes: ${response.status}`);
        }
        
        const data = await response.json();
        const apiNotes = Array.isArray(data?.results) ? data.results : (Array.isArray(data) ? data : []);
        console.log('[Notes] Loaded notes count:', apiNotes.length);
        notes = apiNotes.map(normalizeApiNote);
    } catch (error) {
        console.error('Error loading notes:', error);
    } finally {
        isLoadingNotes = false;
        renderNotesList();
        renderPagination();
    }
}

function normalizeApiNote(note) {
    return {
        id: note?.id ?? null,
        title: note?.title || '제목 없음',
        content: note?.content || '',
        contentPreview: note?.contentPreview || '',  // 백엔드에서 제공하는 텍스트 미리보기
        date: note?.date || '',
        author: note?.author || '',
        shared: typeof note?.shared === 'number' ? note.shared : 0,
        comments: typeof note?.comments === 'number' ? note.comments : 0,
        isPublic: Boolean(note?.is_public),
        isShared: Boolean(note?.is_shared),  // 공유받은 노트인지 여부
        tags: Array.isArray(note?.tags) ? note.tags : [],
    };
}

// Handle create note - redirect to editor page
function handleCreateNote() {
    window.location.href = '/notes/editor/';
}

// Initialize date filter with AirDatepicker
function initDateFilter() {
    if (!dateFilterCalendar || !window.AirDatepicker) return;

    // 기존 인스턴스가 있으면 파괴 (중복 초기화 방지)
    window.airDatepickerInstance?.destroy();

    // Get Korean locale
    const localeKo = window.AirDatepickerLocaleKo || {
        days: ['일요일', '월요일', '화요일', '수요일', '목요일', '금요일', '토요일'],
        daysShort: ['일', '월', '화', '수', '목', '금', '토'],
        daysMin: ['일', '월', '화', '수', '목', '금', '토'],
        months: ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월'],
        monthsShort: ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월'],
        today: '오늘',
        clear: '초기화',
        dateFormat: 'yyyy-MM-dd',
        firstDay: 0
    };

    window.airDatepickerInstance = new window.AirDatepicker(dateFilterCalendar, {
        locale: localeKo,
        range: true,                    // Range selection 활성화
        multipleDatesSeparator: ' ~ ',
        dateFormat: 'yyyy-MM-dd',
        inline: true,                   // 인라인 모드
        // visible: true,                  // 항상 표시
        buttons: false,                 // 버튼 숨김 (별도 초기화 버튼 사용)
        // 2개월 표시 설정
        visibleMonths: 2,
        // monthsField: 'months',
        classes: 'notes-date-range-picker',
        onSelect: function({ date, formattedDate, datepicker }) {
            if (Array.isArray(date) && date.length > 0) {
                selectedDateRange = {
                    from: date[0],
                    to: date[1] || null
                };
                updateDateFilterText();
                
                // 범위 선택 완료 시
                if (date.length === 2) {
                    if (dateFilterActions) dateFilterActions.style.display = 'block';
                } else {
                    if (dateFilterActions) dateFilterActions.style.display = 'none';
                }
            } else if (date) {
                // 단일 날짜 선택
                selectedDateRange = {
                    from: date,
                    to: null
                };
                updateDateFilterText();
                if (dateFilterActions) dateFilterActions.style.display = 'none';
            } else {
                selectedDateRange = undefined;
                updateDateFilterText();
                if (dateFilterActions) dateFilterActions.style.display = 'none';
            }
            
            // 날짜 선택/초기화 시 페이지 초기화 및 리렌더링
            currentPage = 1;
            renderNotesList();
            renderPagination();
        }
    });

    // 2개월 표시를 위한 추가 스타일 적용
    // setTimeout(() => {
    //     const container = dateFilterCalendar.querySelector('.air-datepicker');
    //     if (container) {
    //         container.style.setProperty('--adp-width', '600px');
    //     }
    // }, 0);
}

// Handle toggle date filter
function handleToggleDateFilter(e) {
    e.stopPropagation();
    if (!dateFilterPopover) return;

    const isOpen = dateFilterPopover.style.display !== 'none';
    
    if (isOpen) {
        dateFilterPopover.style.display = 'none';
    } else {
        dateFilterPopover.style.display = 'block';
        
        // 레이아웃 확정 후 datepicker 업데이트 (visibleMonths 적용을 위해)
        requestAnimationFrame(() => {
            window.airDatepickerInstance?.update();
        });
        
        setTimeout(() => {
            document.addEventListener('click', handleClickOutsideDateFilter, true);
        }, 0);
    }
}

// Handle click outside date filter
function handleClickOutsideDateFilter(e) {
    if (!dateFilterPopover || !btnDateFilter) return;
    
    if (!dateFilterPopover.contains(e.target) && !btnDateFilter.contains(e.target)) {
        dateFilterPopover.style.display = 'none';
        document.removeEventListener('click', handleClickOutsideDateFilter, true);
    }
}

// Handle reset date filter (inside popover)
function handleResetDateFilter() {
    if (window.airDatepickerInstance) {
        window.airDatepickerInstance.clear();
    }
    selectedDateRange = undefined;
    updateDateFilterText();
    if (dateFilterActions) dateFilterActions.style.display = 'none';
    
    // 페이지 초기화 및 API 호출 (날짜 필터 초기화 후 전체 데이터 조회)
    currentPage = 1;
    loadNotesFromApi();
}

// Handle reset all filters (날짜 + 검색어 모두 초기화)
function handleResetAllFilters() {
    // 날짜 필터 초기화
    if (window.airDatepickerInstance) {
        window.airDatepickerInstance.clear();
    }
    selectedDateRange = undefined;
    updateDateFilterText();
    if (dateFilterActions) dateFilterActions.style.display = 'none';
    
    // 검색어 초기화
    searchQuery = "";
    if (searchInput) {
        searchInput.value = "";
    }
    
    // 내 노트만 필터 초기화
    myNotesOnly = false;
    if (chkMyNotesOnly) {
        chkMyNotesOnly.checked = false;
    }
    
    // 페이지 초기화 및 리렌더링
    currentPage = 1;
    loadNotesFromApi();
}

// Handle search submit (검색 버튼 클릭 시)
function handleSearchSubmit() {
    if (!searchInput) {
        console.error('[Notes] searchInput element not found');
        return;
    }
    
    searchQuery = searchInput.value.trim();
    console.log('[Notes] Search submitted:', searchQuery);
    
    currentPage = 1;
    loadNotesFromApi();
    
    // 날짜 필터 팝오버 닫기
    if (dateFilterPopover) {
        dateFilterPopover.style.display = 'none';
    }
}

// Handle my notes only checkbox change
function handleMyNotesOnlyChange() {
    myNotesOnly = chkMyNotesOnly?.checked || false;
    currentPage = 1;
    loadNotesFromApi();
}

// Update date filter text
function updateDateFilterText() {
    if (!dateFilterText) return;

    if (selectedDateRange?.from) {
        const fromDate = selectedDateRange.from;
        const fromStr = `${fromDate.getFullYear()}. ${String(fromDate.getMonth() + 1).padStart(2, '0')}. ${String(fromDate.getDate()).padStart(2, '0')}`;
        
        if (selectedDateRange.to) {
            const toDate = selectedDateRange.to;
            const toStr = `${toDate.getFullYear()}. ${String(toDate.getMonth() + 1).padStart(2, '0')}. ${String(toDate.getDate()).padStart(2, '0')}`;
            dateFilterText.textContent = `${fromStr} - ${toStr}`;
        } else {
            dateFilterText.textContent = fromStr;
        }
    } else {
        dateFilterText.textContent = '날짜 검색';
    }
}

// Render notes list
function renderNotesList() {
    const filteredNotes = filterNotes();
    const currentNotes = getCurrentNotes(filteredNotes);

    if (viewMode === 'card') {
        renderCardView(currentNotes);
    } else {
        renderTableView(currentNotes);
    }
}

// Render card view
function renderCardView(currentNotes) {
    if (!notesGrid || !notesTableContainer) return;

    notesGrid.style.display = 'grid';
    notesTableContainer.style.display = 'none';

    if (currentNotes.length === 0) {
        const filteredNotes = filterNotes();
        if (filteredNotes.length === 0) {
            notesGrid.innerHTML = `
                <div class="empty-state" style="grid-column: 1 / -1; text-align: center; padding: 3rem;">
                    <p style="color: #6b7280; font-size: 0.875rem;">검색 조건에 맞는 노트가 없습니다.</p>
                </div>
            `;
        } else {
            notesGrid.innerHTML = `
                <div class="empty-state" style="grid-column: 1 / -1; text-align: center; padding: 3rem;">
                    <p style="color: #6b7280; font-size: 0.875rem;">이 페이지에 표시할 노트가 없습니다.</p>
                </div>
            `;
        }
        return;
    }

    notesGrid.innerHTML = currentNotes.map(note => {
        // 백엔드에서 제공하는 contentPreview 사용 (없으면 기존 함수 사용)
        const previewContent = note.contentPreview || getNoteContentPreview(note.content);
        const lockIcon = note.isPublic ? 'fa-lock-open' : 'fa-lock';
        const lockStateClass = note.isPublic ? 'lock-public' : 'lock-private';
        const lockTooltip = note.isPublic ? '모두가 검색할 수 있는 공개 노트 입니다' : '비공개 노트 입니다';
        return `
        <div class="note-card" data-note-id="${note.id}">
            <h3 class="note-title">${escapeHtml(note.title)}</h3>
            <p class="note-content">${escapeHtml(previewContent)}</p>
            <div class="note-tags">
                ${note.tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}
            </div>
            <div class="note-footer">
                <div class="note-author-date author-date">
                    ${note.author ? `
                        <span class="author-label">${escapeHtml(note.author)}</span>
                        ${note.isShared ? `<span class="shared-badge">[공유]</span>` : ''}
                        <span class="author-separator">|</span>
                    ` : ''}
                    <span class="note-date date-label">${escapeHtml(note.date)}</span>
                </div>
                <div class="note-stats">
                    <span class="stat">
                        <i class="fas fa-share-nodes"></i>
                        ${note.shared}
                    </span>
                    <span class="stat">
                        <i class="fas fa-comment-dots"></i>
                        ${note.comments}
                    </span>
                    <span class="stat stat-lock ${lockStateClass}" data-tooltip="${lockTooltip}">
                        <i class="fas ${lockIcon}"></i>
                    </span>
                </div>
            </div>
        </div>
    `;
    }).join('');

    // Attach click listeners
    const noteCards = notesGrid.querySelectorAll('.note-card');
    noteCards.forEach(card => {
        card.addEventListener('click', () => {
            const noteId = parseInt(card.getAttribute('data-note-id'));
            openNoteDetail(noteId);
        });
    });
}

// Render table view
function renderTableView(currentNotes) {
    if (!notesTableContainer || !notesTableBody || !notesGrid) return;

    notesGrid.style.display = 'none';
    notesTableContainer.style.display = 'block';

    if (currentNotes.length === 0) {
        const filteredNotes = filterNotes();
        let message = '노트가 없습니다.';
        if (filteredNotes.length === 0 && (searchQuery || selectedDateRange)) {
            message = '검색 조건에 맞는 노트가 없습니다.';
        }
        notesTableBody.innerHTML = `
            <tr>
                <td colspan="6" style="text-align: center; padding: 3rem;">
                    <p style="color: #6b7280; font-size: 0.875rem;">${message}</p>
                </td>
            </tr>
        `;
        return;
    }

    // 페이지네이션 기반 시작 번호 계산
    const startIndex = (currentPage - 1) * notesPerPage;

    notesTableBody.innerHTML = currentNotes.map((note, index) => {
        const rowNumber = startIndex + index + 1;
        
        // 백엔드에서 제공하는 contentPreview 사용 (없으면 기존 방식 사용)
        let contentPreview = note.contentPreview || '';
        if (!contentPreview && note.content) {
            const contentLines = note.content.split('\n');
            const firstLine = contentLines[0] || '';
            contentPreview = firstLine.length > 100 ? firstLine.substring(0, 100) + '...' : firstLine;
        }
        // 테이블 뷰에서는 100자로 제한
        if (contentPreview.length > 100) {
            contentPreview = contentPreview.substring(0, 100) + '...';
        }
        
        const lockIcon = note.isPublic ? 'fa-lock-open' : 'fa-lock';
        const lockStateClass = note.isPublic ? 'lock-public' : 'lock-private';
        const lockTooltip = note.isPublic ? '모두가 검색할 수 있는 공개 노트 입니다' : '비공개 노트 입니다';
        
        return `
        <tr data-note-id="${note.id}">
            <td class="table-cell-no">${rowNumber}</td>
            <td class="table-cell-title">
                <h4>${escapeHtml(note.title)}</h4>
                <p>${escapeHtml(contentPreview)}</p>
            </td>
            <td class="table-cell-author">
                ${note.author ? escapeHtml(note.author) : '-'}
                ${note.isShared ? `<span class="shared-badge">[공유]</span>` : ''}
            </td>
            <td class="table-cell-date">${escapeHtml(note.date)}</td>
            <td class="table-cell-tags">
                ${note.tags.map(tag => `<span class="meta-tag">${escapeHtml(tag)}</span>`).join('')}
            </td>
            <td class="table-cell-shared">${note.shared}</td>
            <td class="table-cell-comments">${note.comments}</td>
            <td class="table-cell-visibility">
                <span class="lock-icon ${lockStateClass}" data-tooltip="${lockTooltip}">
                    <i class="fas ${lockIcon}"></i>
                </span>
            </td>
        </tr>
    `;
    }).join('');

    // Attach click listeners
    const tableRows = notesTableBody.querySelectorAll('tr[data-note-id]');
    tableRows.forEach(row => {
        row.addEventListener('click', () => {
            const noteId = parseInt(row.getAttribute('data-note-id'));
            openNoteDetail(noteId);
        });
    });
}

// Open note detail - redirect to detail page
function openNoteDetail(noteId) {
    window.location.href = `/notes/detail/?id=${noteId}`;
}

// Filter notes (서버에서 필터링 처리되므로 클라이언트 사이드 필터링 불필요)
function filterNotes() {
    // 모든 필터링은 서버에서 처리되므로 notes를 그대로 반환
    return [...notes];
}

// Get current notes for pagination
function getCurrentNotes(filteredNotes) {
    const indexOfLastNote = currentPage * notesPerPage;
    const indexOfFirstNote = indexOfLastNote - notesPerPage;
    return filteredNotes.slice(indexOfFirstNote, indexOfLastNote);
}

// Render pagination
function renderPagination() {
    if (!paginationControls) return;

    const filteredNotes = filterNotes();
    const totalPages = Math.ceil(filteredNotes.length / notesPerPage);

    if (totalPages <= 1) {
        paginationControls.innerHTML = '';
        return;
    }

    let paginationHTML = `
        <button class="pagination-btn" ${currentPage === 1 ? 'disabled' : ''} onclick="window.NotesPage.handlePageChange(${currentPage - 1})">
            <i class="fas fa-chevron-left"></i>
            <span>이전</span>
        </button>
        <div class="pagination-numbers">
    `;

    for (let i = 1; i <= totalPages; i++) {
        paginationHTML += `
            <button class="page-number ${i === currentPage ? 'active' : ''}" onclick="window.NotesPage.handlePageChange(${i})">
                ${i}
            </button>
        `;
    }

    paginationHTML += `
        </div>
        <button class="pagination-btn" ${currentPage === totalPages ? 'disabled' : ''} onclick="window.NotesPage.handlePageChange(${currentPage + 1})">
            <span>다음</span>
            <i class="fas fa-chevron-right"></i>
        </button>
    `;

    paginationControls.innerHTML = paginationHTML;
}

// Handle page change
function handlePageChange(pageNumber) {
    const filteredNotes = filterNotes();
    const totalPages = Math.ceil(filteredNotes.length / notesPerPage);
    
    if (pageNumber >= 1 && pageNumber <= totalPages) {
        currentPage = pageNumber;
        renderNotesList();
        renderPagination();
    }
}

// Handle notes per page change
function handleNotesPerPageChange(e) {
    notesPerPage = parseInt(e.target.value);
    currentPage = 1;
    renderNotesList();
    renderPagination();
}

// Handle view mode change
async function handleViewModeChange(mode) {
    viewMode = mode;
    
    if (btnCardView && btnTableView) {
        if (mode === 'card') {
            btnCardView.classList.add('active');
            btnTableView.classList.remove('active');
        } else {
            btnCardView.classList.remove('active');
            btnTableView.classList.add('active');
        }
    }
    
    // 설정 저장
    await saveNotesViewMode(mode);
    
    renderNotesList();
}

// Save notes view mode to user settings
async function saveNotesViewMode(mode) {
    try {
        const response = await fetch('/api/settings/', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            credentials: 'same-origin',
            body: JSON.stringify({
                notes_view_mode: mode
            })
        });
        
        if (!response.ok) {
            console.error('[Notes] Failed to save view mode setting');
        }
    } catch (error) {
        console.error('[Notes] Error saving view mode setting:', error);
    }
}

// Load notes view mode from user settings
async function loadNotesViewMode() {
    try {
        const response = await fetch('/api/settings/', {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
            },
            credentials: 'same-origin'
        });
        
        if (response.ok) {
            const data = await response.json();
            if (data.settings && data.settings.notes_view_mode) {
                return data.settings.notes_view_mode;
            }
        }
    } catch (error) {
        console.error('[Notes] Error loading view mode setting:', error);
    }
    
    // 기본값: card
    return 'card';
}

// Get CSRF token from cookie
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

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getNoteContentPreview(content) {
    if (!content) return '';
    const normalized = content.replace(/\r\n/g, '\n').trim();
    if (!normalized) return '';
    
    const lines = normalized.split('\n').filter(line => line.trim() !== '');
    const previewLines = [];
    for (const line of lines) {
        previewLines.push(line.trim());
        if (previewLines.length >= 3) {
            break;
        }
    }
    
    let preview = previewLines.join(' ');
    if (lines.length > 3 || normalized.length > preview.length) {
        preview = `${preview} ...`;
    }
    
    if (preview.length > 350) {
        preview = `${preview.slice(0, 350)} ...`;
    }
    
    return preview;
}

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNotes);
} else {
    initNotes();
}

// Ensure UI updates when window becomes visible
document.addEventListener('visibilitychange', () => {
    if (!document.hidden && notesListView) {
        renderNotesList();
        renderPagination();
    }
});

// Export to window
window.NotesPage = {
    handlePageChange,
};
