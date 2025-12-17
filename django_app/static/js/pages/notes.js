// Notes List Page JavaScript

// State variables
let currentPage = 1;
let searchQuery = "";
let selectedDateRange = undefined; // { from: Date, to?: Date }
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

// API에서 로드된 데이터 저장
let allNotes = [];

// API에서 데이터 로드
async function loadNotes() {
    try {
        const params = new URLSearchParams({
            page: currentPage,
            per_page: notesPerPage,
            search: searchQuery || ""
        });
        
        const safeFrom = normalizeDate(selectedDateRange?.from);
        const safeTo = normalizeDate(selectedDateRange?.to);

        if (safeFrom) {
            params.append('date_from', safeFrom.toISOString().split('T')[0]);
            if (safeTo) {
                params.append('date_to', safeTo.toISOString().split('T')[0]);
            }
        }
        
        // 디버깅: 쿼리 파라미터 확인
        console.log('loadNotes - searchQuery:', searchQuery);
        console.log('loadNotes - params.search:', params.get('search'));
        console.log('loadNotes - full URL:', `/notes/api/list/?${params}`);
        
        const response = await fetch(`/notes/api/list/?${params}`);
        const data = await response.json();
        
        allNotes = data.notes;
        renderNotesList();
        renderPagination(data.total_pages, data.current_page);
    } catch (error) {
        console.error('Failed to load notes:', error);
        // 에러 시 빈 상태 표시
        allNotes = [];
        renderNotesList();
        renderPagination(0, 1);
    }
}

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

    // Load initial data
    loadNotes();
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
        onSelect: function({ date }) {
            if (Array.isArray(date) && date.length > 0) {
                selectedDateRange = makeDateRange(date[0], date[1]);
                updateDateFilterText();
                
                // 범위 선택 완료 시
                if (date.length === 2 && selectedDateRange?.to) {
                    if (dateFilterActions) dateFilterActions.style.display = 'block';
                } else {
                    if (dateFilterActions) dateFilterActions.style.display = 'none';
                }
            } else if (date) {
                // 단일 날짜 선택
                selectedDateRange = makeDateRange(date, null);
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
    
    // 디버깅: 초기화 확인
    console.log('handleResetAllFilters - searchQuery:', searchQuery);
    console.log('handleResetAllFilters - searchInput.value:', searchInput?.value);
    
    // 뷰 모드 초기화 (카드 뷰로)
    viewMode = 'card';
    if (btnCardView && btnTableView) {
        btnCardView.classList.add('active');
        btnTableView.classList.remove('active');
    }
    
    // 페이지당 노트 개수 초기화 (10개로)
    notesPerPage = 10;
    if (notesPerPageSelect) {
        notesPerPageSelect.value = '10';
    }
    
    // 페이지 초기화 및 리로드
    currentPage = 1;
    loadNotes();
}

// Handle search submit (검색 버튼 클릭 시)
function handleSearchSubmit() {
    // 검색어를 입력창에서 가져오기 (trim으로 공백 제거)
    if (!searchInput) {
        console.error('searchInput element not found');
        return;
    }
    
    const inputValue = (searchInput.value || "").trim();
    searchQuery = inputValue;
    
    // 디버깅: 검색어 확인
    console.log('handleSearchSubmit - searchInput.value:', searchInput.value);
    console.log('handleSearchSubmit - inputValue (trimmed):', inputValue);
    console.log('handleSearchSubmit - searchQuery:', searchQuery);
    
    currentPage = 1;
    loadNotes();
    
    // 날짜 필터 팝오버 닫기
    if (dateFilterPopover) {
        dateFilterPopover.style.display = 'none';
    }
}

// Update date filter text
function updateDateFilterText() {
    if (!dateFilterText) return;

    const safeFrom = normalizeDate(selectedDateRange?.from);
    const safeTo = normalizeDate(selectedDateRange?.to);

    if (safeFrom) {
        const fromStr = formatDateDot(safeFrom);
        
        if (safeTo) {
            const toStr = formatDateDot(safeTo);
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
    if (viewMode === 'card') {
        renderCardView(allNotes);
    } else {
        renderTableView(allNotes);
    }
}

// Render card view
function renderCardView(currentNotes) {
    if (!notesGrid || !notesTableContainer) return;

    notesGrid.style.display = 'grid';
    notesTableContainer.style.display = 'none';

    if (currentNotes.length === 0) {
        notesGrid.innerHTML = `
            <div class="empty-state" style="grid-column: 1 / -1; text-align: center; padding: 3rem;">
                <p style="color: #6b7280; font-size: 0.875rem;">노트가 없습니다.</p>
            </div>
        `;
        return;
    }

    notesGrid.innerHTML = currentNotes.map(note => `
        <div class="note-card" data-note-id="${note.id}">
            <h3 class="note-title">${escapeHtml(note.title)}</h3>
            <p class="note-content">
                ${escapeHtml(getNotePreview(note.content, 120))}
                ${hasTable(note.content) ? '<span class="note-has-table"> 📊 표 포함</span>' : ''}
                ${hasImage(note.content) ? '<span class="note-has-image"> 🖼 이미지 포함</span>': ''}
            </p>

            <div class="note-tags">
                ${note.tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}
            </div>
            <div class="note-footer">
                <span class="note-date">${note.date}</span>
                <div class="note-stats">
                    <span class="stat">
                        <i class="fas fa-share-nodes"></i>
                        ${note.shared || 0}
                    </span>
                    <span class="stat">
                        <i class="fas fa-comment-dots"></i>
                        ${note.comments || 0}
                    </span>
                </div>
            </div>
        </div>
    `).join('');

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
        notesTableBody.innerHTML = `
            <tr>
                <td colspan="6" style="text-align: center; padding: 3rem;">
                    <p style="color: #6b7280; font-size: 0.875rem;">노트가 없습니다.</p>
                </td>
            </tr>
        `;
        return;
    }

    // 페이지네이션 기반 시작 번호 계산
    const startIndex = (currentPage - 1) * notesPerPage;

    notesTableBody.innerHTML = currentNotes.map((note, index) => {
        const rowNumber = startIndex + index + 1;
        const contentLines = stripHtml(note.content).split('\n');
        const firstLine = contentLines[0] || '';
        const contentPreview = firstLine.length > 50 ? firstLine.substring(0, 50) + '...' : firstLine;
        
        return `
        <tr data-note-id="${note.id}">
            <td class="table-cell-no">${rowNumber}</td>
            <td class="table-cell-title">
                <h4>${escapeHtml(note.title)}</h4>
                <p>${escapeHtml(contentPreview)}</p>
            </td>
            <td class="table-cell-date">${escapeHtml(note.date)}</td>
            <td class="table-cell-tags">
                ${note.tags.map(tag => `<span class="meta-tag">${escapeHtml(tag)}</span>`).join('')}
            </td>
            <td class="table-cell-shared">${note.shared || 0}</td>
            <td class="table-cell-comments">${note.comments || 0}</td>
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

// Render pagination
function renderPagination(totalPages, currentPageNum) {
    if (!paginationControls) return;

    if (totalPages <= 1) {
        paginationControls.innerHTML = '';
        return;
    }

    let paginationHTML = `
        <button class="pagination-btn" ${currentPageNum === 1 ? 'disabled' : ''} onclick="window.NotesPage.handlePageChange(${currentPageNum - 1})">
            <i class="fas fa-chevron-left"></i>
            <span>이전</span>
        </button>
        <div class="pagination-numbers">
    `;

    for (let i = 1; i <= totalPages; i++) {
        paginationHTML += `
            <button class="page-number ${i === currentPageNum ? 'active' : ''}" onclick="window.NotesPage.handlePageChange(${i})">
                ${i}
            </button>
        `;
    }

    paginationHTML += `
        </div>
        <button class="pagination-btn" ${currentPageNum === totalPages ? 'disabled' : ''} onclick="window.NotesPage.handlePageChange(${currentPageNum + 1})">
            <span>다음</span>
            <i class="fas fa-chevron-right"></i>
        </button>
    `;

    paginationControls.innerHTML = paginationHTML;
}

// Handle page change
function handlePageChange(pageNumber) {
    currentPage = pageNumber;
    loadNotes();
}

// Handle notes per page change
function handleNotesPerPageChange(e) {
    notesPerPage = parseInt(e.target.value);
    currentPage = 1;
    loadNotes();
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

function getNotePreview(html, maxLength = 120) {
    if (!html) return '';

    // 1. table / figure.table 제거
    let cleaned = html
        .replace(/<figure class="table">[\s\S]*?<\/figure>/gi, '')
        .replace(/<table[\s\S]*?<\/table>/gi, '');

    // 2. HTML → 텍스트
    const div = document.createElement('div');
    div.innerHTML = cleaned;
    let text = div.textContent || div.innerText || '';
    text = text.trim();

    // 3. 길이 제한
    if (text.length > maxLength) {
        text = text.slice(0, maxLength) + '…';
    }

    return text;
}

function hasTable(html) {
    return typeof html === 'string' && html.includes('<table');
}

function hasImage(html) {
    return typeof html === 'string' && (
        html.includes('<img') ||
        html.includes('figure class="image"')
    );
}


function stripHtml(html) {
    const div = document.createElement('div');
    div.innerHTML = html;
    return div.textContent || div.innerText || '';
}

// Safely normalize to Date instance; returns null if invalid
function normalizeDate(value) {
    if (!value) return null;
    if (value instanceof Date) return isNaN(value) ? null : value;
    const parsed = new Date(value);
    return isNaN(parsed) ? null : parsed;
}

// Make safe date range object from raw values
function makeDateRange(from, to) {
    const safeFrom = normalizeDate(from);
    const safeTo = normalizeDate(to);
    if (!safeFrom) return undefined;
    return {
        from: safeFrom,
        to: safeTo || null
    };
}

// Format date as "YYYY. MM. DD"
function formatDateDot(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}. ${m}. ${d}`;
}

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNotes);
} else {
    initNotes();
}

// 페이지 로드 시 URL 파라미터 체크 (editor에서 돌아온 경우)
const urlParams = new URLSearchParams(window.location.search);
if (urlParams.get('refresh') === 'true') {
    // URL에서 refresh 파라미터 제거
    const newUrl = window.location.pathname;
    window.history.replaceState({}, document.title, newUrl);
}

// Ensure UI updates when window becomes visible
document.addEventListener('visibilitychange', () => {
    if (!document.hidden && notesListView) {
        loadNotes();
    }
});

// Export to window
window.NotesPage = {
    handlePageChange,
};
