// Notes List Page JavaScript

// State variables
let currentPage = 1;
let searchQuery = "";
let selectedDateRange = undefined;
let notesPerPage = 10;
let viewMode = 'card';

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
    
    // Initialize AirDatepicker
    initDateFilter();

    // Render initial state
    renderNotesList();
    renderPagination();

    // Load notes from API
    loadNotesFromApi();
}

// Load notes via API
async function loadNotesFromApi() {
    if (isLoadingNotes) return;
    isLoadingNotes = true;
    
    try {
        const response = await fetch('/api/notes/', {
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
        date: note?.date || '',
        author: note?.author || '',
        shared: typeof note?.shared === 'number' ? note.shared : 0,
        comments: typeof note?.comments === 'number' ? note.comments : 0,
        isPublic: Boolean(note?.is_public),
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
    
    // 페이지 초기화 및 리렌더링
    currentPage = 1;
    renderNotesList();
    renderPagination();
}

// Handle search submit (검색 버튼 클릭 시)
function handleSearchSubmit() {
    searchQuery = searchInput?.value || "";
    currentPage = 1;
    renderNotesList();
    renderPagination();
    
    // 날짜 필터 팝오버 닫기
    if (dateFilterPopover) {
        dateFilterPopover.style.display = 'none';
    }
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
        const previewContent = getNoteContentPreview(note.content);
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
        const contentLines = note.content.split('\n');
        const firstLine = contentLines[0] || '';
        const contentPreview = firstLine.length > 100 ? firstLine.substring(0, 100) + '...' : firstLine;
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
            <td class="table-cell-author">${escapeHtml(note.author || '-')}</td>
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

// Filter notes
function filterNotes() {
    let filtered = [...notes];
    
    if (searchQuery) {
        const query = searchQuery.toLowerCase();
        filtered = filtered.filter(note => 
            note.title.toLowerCase().includes(query) ||
            note.content.toLowerCase().includes(query) ||
            (note.author && note.author.toLowerCase().includes(query)) ||
            note.tags.some(tag => tag.toLowerCase().includes(query))
        );
    }
    
    if (selectedDateRange?.from) {
        const fromDate = new Date(selectedDateRange.from);
        fromDate.setHours(0, 0, 0, 0);
        
        const toDate = selectedDateRange.to ? new Date(selectedDateRange.to) : new Date(selectedDateRange.from);
        toDate.setHours(23, 59, 59, 999);
        
        filtered = filtered.filter(note => {
            const noteDate = new Date(note.date);
            noteDate.setHours(0, 0, 0, 0);
            return noteDate >= fromDate && noteDate <= toDate;
        });
    }
    
    return filtered;
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
function handleViewModeChange(mode) {
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
    
    renderNotesList();
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
