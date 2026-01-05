// Reference Selection Modal JavaScript
console.log('[ReferenceSelectionModal] ===== Script file loading... =====');

(function() {
    'use strict';

    console.log('[ReferenceSelectionModal] IIFE starting...');

    // Mock data matching React component
    // TODO: 여기 database에서 조회하도록 수정 -> chat의 chat_message id를 통해서 t_chat_reference 에서 조회하도록 수정
    const allMockReferences = [
        {
            id: 1,
            source: 'PubMed',
            badge: '높은 관련성',
            title: 'The emerging view on the origin and early evolution of eukaryotic cells.',
            journal: 'Nature',
            link: 'PubMed : 39261613',
            date: '2024. 09. 12',
            authors: 'Vosseberg J et al.'
        },
        {
            id: 2,
            source: 'PubMed',
            badge: '높은 관련성',
            title: 'Eukaryotic cells.',
            journal: 'Curr Opin Cell Biol',
            link: 'PubMed : 21592757',
            date: '2011. 05. 20',
            authors: 'Hetzer M et al.'
        },
        {
            id: 3,
            source: 'Web',
            badge: '',
            title: 'Prokaryotes vs Eukaryotes: Key Cell Differences',
            journal: 'www.osmosis.org',
            link: '',
            date: '2025. 06. 08',
            authors: ''
        },
        {
            id: 4,
            source: 'Web',
            badge: '',
            title: 'Intro to eukaryotic cells (article)',
            journal: '',
            link: '',
            date: '',
            authors: ''
        },
        {
            id: 5,
            source: 'PubMed',
            badge: '높은 관련성',
            title: 'Cell structure and function in eukaryotic organisms',
            journal: 'Cell Biology Review',
            link: 'PubMed : 30154821',
            date: '2023. 03. 15',
            authors: 'Thompson A et al.'
        },
        {
            id: 6,
            source: 'PubMed',
            badge: '',
            title: 'Comparative genomics of eukaryotic cells',
            journal: 'Genome Research',
            link: 'PubMed : 28934567',
            date: '2022. 11. 08',
            authors: 'Martinez L et al.'
        },
        {
            id: 7,
            source: 'Web',
            badge: '',
            title: 'Eukaryotic Cell Biology - Comprehensive Guide',
            journal: 'www.cellbio.edu',
            link: '',
            date: '2024. 02. 20',
            authors: ''
        },
        {
            id: 8,
            source: 'PubMed',
            badge: '높은 관련성',
            title: 'Molecular mechanisms in eukaryotic cell division',
            journal: 'Molecular Cell',
            link: 'PubMed : 32456789',
            date: '2023. 07. 22',
            authors: 'Chen Y et al.'
        },
        {
            id: 9,
            source: 'PubMed',
            badge: '',
            title: 'Evolution and diversity of eukaryotic cells',
            journal: 'Evolution & Development',
            link: 'PubMed : 29876543',
            date: '2023. 05. 10',
            authors: 'Anderson R et al.'
        }
    ];

    // State
    let allReferences = [];
    let filteredReferences = [];
    let selectedReferences = [];
    let currentPage = 1;
    let isInitialized = false;
    let currentChatId = null;
    let currentMessageId = null;
    const itemsPerPage = 5;

    // DOM element references
    const modalId = 'referenceSelectionModal';
    let searchInput = null;
    let selectAllCheckbox = null;
    let referenceList = null;
    let pagination = null;
    let selectedCountEl = null;
    let saveBtn = null;

    // Get DOM elements
    function getModalElements() {
        searchInput = document.getElementById('referenceSearchInput');
        selectAllCheckbox = document.getElementById('selectAllReferences');
        referenceList = document.getElementById('referenceSelectionList');
        pagination = document.getElementById('referencePagination');
        selectedCountEl = document.getElementById('selectedCount');
        saveBtn = document.getElementById('saveSelectedReferencesBtn');
    }

    // Initialize modal
    function initReferenceSelectionModal() {
        if (isInitialized) return true;

        const modal = document.getElementById(modalId);
        if (!modal) {
            console.warn('[ReferenceSelectionModal] Modal element not found');
            return false;
        }

        getModalElements();

        // Close button handler
        const closeBtns = modal.querySelectorAll('[data-action="close"]');
        closeBtns.forEach(btn => {
            btn.addEventListener('click', closeReferenceSelectionModal);
        });

        // Search handler
        if (searchInput) {
            searchInput.addEventListener('input', () => {
                currentPage = 1;
                filterReferences();
            });
        }

        // Select all handler
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', handleSelectAll);
        }

        // Save handler
        if (saveBtn) {
            saveBtn.addEventListener('click', handleSave);
        }

        isInitialized = true;
        console.log('[ReferenceSelectionModal] Initialized successfully');
        return true;
    }

    // Filter references
    function filterReferences() {
        const query = searchInput?.value.toLowerCase() || '';
        filteredReferences = allReferences.filter(ref => {
            if (!query) return true;
            return (
                (ref.title || '').toLowerCase().includes(query) ||
                (ref.journal || '').toLowerCase().includes(query) ||
                (ref.authors || '').toLowerCase().includes(query) ||
                (ref.source || '').toLowerCase().includes(query)
            );
        });
        renderReferences();
        renderPagination();
        updateSelectAll();
    }

    // Render references
    function renderReferences() {
        if (!referenceList) {
            getModalElements();
        }
        if (!referenceList) return;

        const startIndex = (currentPage - 1) * itemsPerPage;
        const endIndex = startIndex + itemsPerPage;
        const currentPageRefs = filteredReferences.slice(startIndex, endIndex);

        if (currentPageRefs.length === 0) {
            referenceList.innerHTML = `
                <div class="ref-empty-state">
                    <p>검색 결과가 없습니다</p>
                </div>
            `;
            return;
        }

        referenceList.innerHTML = currentPageRefs.map(ref => {
            const isSelected = selectedReferences.includes(ref.id);
            return `
                <label class="ref-selection-item">
                    <input 
                        type="checkbox" 
                        ${isSelected ? 'checked' : ''}
                        data-reference-id="${ref.id}"
                        class="ref-checkbox"
                    />
                    <div class="ref-selection-content">
                        <div class="ref-selection-meta">
                            <span class="ref-selection-source">${escapeHtml(ref.source || 'Unknown')}</span>
                            ${ref.badge ? `<span class="ref-selection-badge">${escapeHtml(ref.badge)}</span>` : ''}
                        </div>
                        <h4 class="ref-selection-title">${escapeHtml(ref.title)}</h4>
                        ${ref.journal ? `<p class="ref-selection-journal">${escapeHtml(ref.journal)}</p>` : ''}
                        <div class="ref-selection-info">
                            ${ref.link ? `<span class="ref-selection-link">${escapeHtml(ref.link)}</span>` : ''}
                            ${ref.date ? `<span>${escapeHtml(ref.date)}</span>` : ''}
                            ${ref.authors ? `<span>${escapeHtml(ref.authors)}</span>` : ''}
                        </div>
                    </div>
                </label>
            `;
        }).join('');

        // Attach checkbox handlers
        referenceList.querySelectorAll('.ref-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const refId = parseInt(e.target.getAttribute('data-reference-id'));
                if (e.target.checked) {
                    if (!selectedReferences.includes(refId)) {
                        selectedReferences.push(refId);
                    }
                } else {
                    selectedReferences = selectedReferences.filter(id => id !== refId);
                }
                updateSelectedCount();
                updateSelectAll();
            });
        });
    }

    // Render pagination
    function renderPagination() {
        if (!pagination) {
            getModalElements();
        }
        if (!pagination) return;

        const totalPages = Math.ceil(filteredReferences.length / itemsPerPage);
        if (totalPages <= 1) {
            pagination.innerHTML = '';
            return;
        }

        pagination.innerHTML = `
            <button class="ref-pagination-btn" ${currentPage === 1 ? 'disabled' : ''} data-action="prev">이전</button>
            ${Array.from({ length: totalPages }, (_, i) => i + 1).map(page => `
                <button class="ref-pagination-page ${currentPage === page ? 'active' : ''}" data-page="${page}">${page}</button>
            `).join('')}
            <button class="ref-pagination-btn" ${currentPage === totalPages ? 'disabled' : ''} data-action="next">다음</button>
        `;

        // Attach pagination handlers
        pagination.querySelectorAll('.ref-pagination-btn, .ref-pagination-page').forEach(btn => {
            btn.addEventListener('click', () => {
                if (btn.disabled) return;
                const action = btn.getAttribute('data-action');
                const page = btn.getAttribute('data-page');
                const totalPages = Math.ceil(filteredReferences.length / itemsPerPage);
                
                if (action === 'prev') {
                    currentPage = Math.max(1, currentPage - 1);
                } else if (action === 'next') {
                    currentPage = Math.min(totalPages, currentPage + 1);
                } else if (page) {
                    currentPage = parseInt(page);
                }
                renderReferences();
                renderPagination();
                updateSelectAll();
            });
        });
    }

    // Handle select all
    function handleSelectAll(e) {
        const startIndex = (currentPage - 1) * itemsPerPage;
        const endIndex = startIndex + itemsPerPage;
        const currentPageRefs = filteredReferences.slice(startIndex, endIndex);
        const currentPageIds = currentPageRefs.map(ref => ref.id);

        if (e.target.checked) {
            currentPageIds.forEach(id => {
                if (!selectedReferences.includes(id)) {
                    selectedReferences.push(id);
                }
            });
        } else {
            selectedReferences = selectedReferences.filter(id => !currentPageIds.includes(id));
        }
        renderReferences();
        updateSelectedCount();
    }

    // Update select all checkbox state
    function updateSelectAll() {
        if (!selectAllCheckbox) return;
        const startIndex = (currentPage - 1) * itemsPerPage;
        const endIndex = startIndex + itemsPerPage;
        const currentPageRefs = filteredReferences.slice(startIndex, endIndex);
        const allSelected = currentPageRefs.length > 0 && currentPageRefs.every(ref => selectedReferences.includes(ref.id));
        selectAllCheckbox.checked = allSelected;
    }

    // Update selected count
    function updateSelectedCount() {
        if (!selectedCountEl) {
            getModalElements();
        }
        if (selectedCountEl) {
            selectedCountEl.textContent = selectedReferences.length;
        }
    }

    // Handle save
    async function handleSave() {
        if (selectedReferences.length === 0) {
            if (window.notyf) {
                window.notyf.error('저장할 참고 문헌을 선택해주세요.');
            }
            return;
        }

        // 선택한 참고 문헌들 가져오기
        const selectedRefs = allReferences.filter(ref => selectedReferences.includes(ref.id));
        
        // 북마크 모달 열기 (선택한 참고 문헌들을 전달)
        closeReferenceSelectionModal();
        
        // 북마크 모달에 여러 참고 문헌 전달
        if (window.Modal && window.Modal.open) {
            window.Modal.open('bookmarkModal', { 
                references: selectedRefs,
                isMultiple: true 
            });
        } else if (window.BookmarkModal && window.BookmarkModal.open) {
            window.BookmarkModal.open(selectedRefs);
        }
    }

    // Load references from API
    async function loadReferencesFromAPI(chatId, messageId) {
        try {
            // messageId가 있으면 쿼리 파라미터로 추가
            let url = `/chat/api/chats/${chatId}/references/`;
            if (messageId) {
                url += `?message_id=${messageId}`;
            }
            
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'Content-Type': 'application/json',
                },
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            if (data.status === 'success' && data.references) {
                // API 응답을 모달에서 사용하는 형식으로 변환
                allReferences = data.references.map(ref => ({
                    id: ref.id || ref.reference_sid,
                    reference_sid: ref.id || ref.reference_sid,
                    source: ref.source || 'Unknown',
                    badge: ref.badge || '',
                    title: ref.title || '',
                    journal: ref.journal || '',
                    link: ref.link || '',
                    url: ref.link || ref.url || '',
                    pmid: ref.pmid || '',
                    date: ref.date || '',
                    description: ref.description || '',
                    doi: ref.doi || '',
                }));
                
                console.log('[ReferenceSelectionModal] Loaded references:', allReferences.length);
                return true;
            } else {
                console.warn('[ReferenceSelectionModal] No references found or invalid response');
                allReferences = [];
                return false;
            }
        } catch (error) {
            console.error('[ReferenceSelectionModal] Error loading references:', error);
            if (window.notyf) {
                window.notyf.error('참고 문헌을 불러오는 중 오류가 발생했습니다.');
            }
            allReferences = [];
            return false;
        }
    }

    // Open modal
    async function openReferenceSelectionModal(chatId, messageId) {
        console.log('[ReferenceSelectionModal] Opening modal with chatId:', chatId, 'messageId:', messageId);

        if (!isInitialized) {
            initReferenceSelectionModal();
        }

        const modal = document.getElementById(modalId);
        if (!modal) {
            console.error('[ReferenceSelectionModal] Modal element not found');
            return;
        }

        // Reset state
        selectedReferences = [];
        currentPage = 1;
        if (searchInput) searchInput.value = '';
        currentChatId = chatId;
        currentMessageId = messageId;
        
        // Load references from API
        if (chatId) {
            const loadingSuccess = await loadReferencesFromAPI(chatId, messageId);
            if (!loadingSuccess && allReferences.length === 0) {
                // API 로드 실패 시 빈 상태 표시
                if (referenceList) {
                    referenceList.innerHTML = `
                        <div class="ref-empty-state">
                            <p>참고 문헌이 없습니다</p>
                        </div>
                    `;
                }
            }
        } else {
            console.warn('[ReferenceSelectionModal] No chatId provided, using empty references');
            allReferences = [];
        }
        
        filterReferences();
        updateSelectedCount();

        modal.classList.add('active');
        console.log('[ReferenceSelectionModal] Modal opened');
    }

    // Close modal
    function closeReferenceSelectionModal() {
        const modal = document.getElementById(modalId);
        if (!modal) return;
        modal.classList.remove('active');
    }

    // Escape HTML
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
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
        return '';
    }

    // Export to window immediately
    console.log('[ReferenceSelectionModal] Assigning window.ReferenceSelectionModal...');
    window.ReferenceSelectionModal = {
        open: openReferenceSelectionModal,
        close: closeReferenceSelectionModal,
        init: initReferenceSelectionModal,
        isReady: function() {
            return isInitialized;
        }
    };
    console.log('[ReferenceSelectionModal] window.ReferenceSelectionModal assigned:', window.ReferenceSelectionModal);

    // Initialize when DOM is ready
    function tryInit() {
        if (initReferenceSelectionModal()) {
            document.dispatchEvent(new Event('referenceSelectionModal:ready'));
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
        if (!tryInit()) {
            setTimeout(tryInit, 100);
        }
    }

    console.log('[ReferenceSelectionModal] Script loaded, window.ReferenceSelectionModal available');
})();
