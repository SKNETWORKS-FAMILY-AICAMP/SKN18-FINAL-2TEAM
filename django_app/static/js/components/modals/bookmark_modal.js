// Bookmark Modal JavaScript

let selectedCategory = null;
let selectedCategorySid = null;
let categories = [];
let showNewCategoryInput = false;
let currentReferenceData = null; // 현재 저장할 참조문헌 데이터 (단일)
let currentReferences = null; // 현재 저장할 참조문헌 데이터 (다중)
let isMultipleMode = false; // 다중 저장 모드 여부

// Initialize bookmark modal
function initBookmarkModal() {
    const bookmarkModal = document.getElementById('bookmarkModal');
    if (!bookmarkModal) return;

    const bookmarkCategories = document.getElementById('bookmarkCategories');
    const newCategoryBtn = document.getElementById('newCategoryBtn');
    const newCategoryInput = document.getElementById('newCategoryInput');
    const newCategoryName = document.getElementById('newCategoryName');
    const createCategoryBtn = document.getElementById('createCategoryBtn');
    const cancelCategoryBtn = document.getElementById('cancelCategoryBtn');
    const saveBookmarkBtn = document.getElementById('saveBookmarkBtn');
    const bookmarkCount = document.getElementById('bookmarkCount');

    // Render categories
    function renderCategories() {
        if (!bookmarkCategories) return;
        
        if (categories.length === 0) {
            bookmarkCategories.innerHTML = '<div class="empty-state"><p>폴더가 없습니다. 새 폴더를 만들어주세요.</p></div>';
            return;
        }
        
        bookmarkCategories.innerHTML = categories.map(category => {
            const isSelected = selectedCategorySid === category.category_sid;
            return `
                <button class="bookmark-category-item ${isSelected ? 'selected' : ''}" data-category-sid="${category.category_sid}">
                    <i class="fas fa-folder"></i>
                    <span>${escapeHtml(category.category_name)}</span>
                    ${isSelected ? '<i class="fas fa-check check-icon"></i>' : ''}
                </button>
            `;
        }).join('');

        // Attach click handlers
        bookmarkCategories.querySelectorAll('.bookmark-category-item').forEach(item => {
            item.addEventListener('click', () => {
                selectedCategorySid = parseInt(item.getAttribute('data-category-sid'));
                selectedCategory = categories.find(cat => cat.category_sid === selectedCategorySid);
                renderCategories();
                updateSaveButton();
            });
        });
    }

    // Update save button state
    function updateSaveButton() {
        if (saveBookmarkBtn) {
            saveBookmarkBtn.disabled = !selectedCategorySid;
        }
    }

    // Update bookmark count
    function updateBookmarkCount() {
        if (bookmarkCount) {
            if (isMultipleMode && currentReferences && currentReferences.length > 0) {
                bookmarkCount.textContent = `(${currentReferences.length}개)`;
            } else if (currentReferenceData) {
                bookmarkCount.textContent = `(1개)`;
            } else {
                bookmarkCount.textContent = '';
            }
        }
    }

    // New category handlers
    if (newCategoryBtn) {
        newCategoryBtn.addEventListener('click', () => {
            showNewCategoryInput = true;
            if (newCategoryInput) {
                newCategoryInput.style.display = 'flex';
            }
            if (newCategoryName) {
                newCategoryName.focus();
            }
        });
    }

    // Create category function
    async function createCategory() {
        const name = newCategoryName?.value.trim();
        if (!name) {
            if (window.notyf) {
                window.notyf.error('폴더 이름을 입력해주세요.');
            }
            return;
        }

        // 중복 체크
        if (categories.some(cat => cat.category_name === name)) {
            if (window.notyf) {
                window.notyf.error('이미 존재하는 폴더 이름입니다.');
            }
            return;
        }

        try {
            const response = await fetch('/api/bookmarks/categories/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    category_name: name,
                }),
            });

            const data = await response.json();
            if (response.ok && data.status === 'success') {
                // 새 카테고리를 목록에 추가
                categories.push(data.category);
                selectedCategorySid = data.category.category_sid;
                selectedCategory = data.category;
                showNewCategoryInput = false;
                if (newCategoryInput) {
                    newCategoryInput.style.display = 'none';
                }
                if (newCategoryName) {
                    newCategoryName.value = '';
                }
                renderCategories();
                updateSaveButton();
                if (window.notyf) {
                    window.notyf.success(`"${name}" 폴더가 생성되었습니다.`);
                }
            } else {
                throw new Error(data.error || '폴더 생성에 실패했습니다.');
            }
        } catch (error) {
            console.error('Error creating category:', error);
            if (window.notyf) {
                window.notyf.error(error.message || '폴더 생성 중 오류가 발생했습니다.');
            }
        }
    }

    if (createCategoryBtn) {
        createCategoryBtn.addEventListener('click', createCategory);
    }

    // Enter key support for new category input
    if (newCategoryName) {
        newCategoryName.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                createCategory();
            }
        });
    }

    if (cancelCategoryBtn) {
        cancelCategoryBtn.addEventListener('click', () => {
            showNewCategoryInput = false;
            if (newCategoryInput) {
                newCategoryInput.style.display = 'none';
            }
            if (newCategoryName) {
                newCategoryName.value = '';
            }
        });
    }

    // Save bookmark (단일 또는 다중)
    if (saveBookmarkBtn) {
        saveBookmarkBtn.addEventListener('click', async () => {
            if (!selectedCategorySid) {
                if (window.notyf) {
                    window.notyf.error('폴더를 선택해주세요.');
                }
                return;
            }

            // 다중 모드인지 확인
            if (isMultipleMode && currentReferences && currentReferences.length > 0) {
                // 여러 참고 문헌 저장
                await saveMultipleBookmarks(currentReferences);
            } else if (currentReferenceData) {
                // 단일 참고 문헌 저장
                await saveSingleBookmark(currentReferenceData);
            } else {
                if (window.notyf) {
                    window.notyf.error('저장할 참조문헌 정보가 없습니다.');
                }
                return;
            }
        });
    }

    // 단일 북마크 저장
    async function saveSingleBookmark(referenceData) {
        try {
            // 북마크 URL 처리: "PubMed : {pmid}" 형식을 실제 URL로 변환
            let bookmarkUrl = referenceData.link || referenceData.url || '';
            
            // "PubMed : {pmid}" 형식 감지 및 변환
            if (bookmarkUrl.startsWith('PubMed : ')) {
                const pmid = bookmarkUrl.replace('PubMed : ', '').trim();
                bookmarkUrl = `https://pubmed.ncbi.nlm.nih.gov/${pmid}/`;
            }
            // pmid 필드가 있고 link가 없거나 "PubMed :" 형식인 경우
            else if (referenceData.pmid && (!bookmarkUrl || bookmarkUrl.startsWith('PubMed :'))) {
                bookmarkUrl = `https://pubmed.ncbi.nlm.nih.gov/${referenceData.pmid}/`;
            }
            
            // 북마크 저장 API 호출
            const response = await fetch('/api/bookmarks/bookmarks/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    category_sid: selectedCategorySid,
                    title: referenceData.title || '제목 없음',
                    bookmark_url: bookmarkUrl,
                    description: referenceData.description || '',
                }),
            });

            const data = await response.json();
            if (response.ok && data.status === 'success') {
                if (window.notyf) {
                    window.notyf.success(`참조 문헌을 "${selectedCategory?.category_name || '선택한 폴더'}"에 저장했습니다.`);
                }
                if (window.Modal) {
                    window.Modal.close('bookmarkModal');
                }
                resetBookmarkModal();
            } else {
                throw new Error(data.error || '북마크 저장에 실패했습니다.');
            }
        } catch (error) {
            console.error('Error saving bookmark:', error);
            if (window.notyf) {
                window.notyf.error(error.message || '북마크 저장 중 오류가 발생했습니다.');
            }
        }
    }

    // 다중 북마크 저장
    async function saveMultipleBookmarks(references) {
        if (!references || references.length === 0) {
            if (window.notyf) {
                window.notyf.error('저장할 참조문헌이 없습니다.');
            }
            return;
        }

        try {
            let successCount = 0;
            let failCount = 0;
            const errors = [];

            // 각 참고 문헌을 순차적으로 저장
            for (const ref of references) {
                try {
                    // 북마크 URL 처리
                    let bookmarkUrl = ref.link || ref.url || '';
                    
                    if (bookmarkUrl.startsWith('PubMed : ')) {
                        const pmid = bookmarkUrl.replace('PubMed : ', '').trim();
                        bookmarkUrl = `https://pubmed.ncbi.nlm.nih.gov/${pmid}/`;
                    } else if (ref.pmid && (!bookmarkUrl || bookmarkUrl.startsWith('PubMed :'))) {
                        bookmarkUrl = `https://pubmed.ncbi.nlm.nih.gov/${ref.pmid}/`;
                    }
                    
                    const response = await fetch('/api/bookmarks/bookmarks/', {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': getCsrfToken(),
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            category_sid: selectedCategorySid,
                            title: ref.title || '제목 없음',
                            bookmark_url: bookmarkUrl,
                            description: ref.description || '',
                        }),
                    });

                    const data = await response.json();
                    if (response.ok && data.status === 'success') {
                        successCount++;
                    } else {
                        failCount++;
                        errors.push(ref.title || '제목 없음');
                    }
                } catch (error) {
                    failCount++;
                    errors.push(ref.title || '제목 없음');
                    console.error('Error saving bookmark:', error);
                }
            }

            // 결과 메시지 표시
            if (successCount > 0) {
                if (window.notyf) {
                    if (failCount === 0) {
                        window.notyf.success(`${successCount}개의 참조 문헌을 "${selectedCategory?.category_name || '선택한 폴더'}"에 저장했습니다.`);
                    } else {
                        window.notyf.success(`${successCount}개 저장 완료, ${failCount}개 실패`);
                    }
                }
            } else {
                if (window.notyf) {
                    window.notyf.error('모든 북마크 저장에 실패했습니다.');
                }
            }

            // 모달 닫기
            if (window.Modal) {
                window.Modal.close('bookmarkModal');
            }
            resetBookmarkModal();
        } catch (error) {
            console.error('Error saving bookmarks:', error);
            if (window.notyf) {
                window.notyf.error('북마크 저장 중 오류가 발생했습니다.');
            }
        }
    }

    // 북마크 모달 상태 초기화
    function resetBookmarkModal() {
        selectedCategory = null;
        selectedCategorySid = null;
        currentReferenceData = null;
        currentReferences = null;
        isMultipleMode = false;
        renderCategories();
        updateSaveButton();
        updateBookmarkCount();
    }

    // Load categories from API
    async function loadCategories() {
        try {
            const response = await fetch('/api/bookmarks/', {
                method: 'GET',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'Content-Type': 'application/json',
                },
            });
            if (response.ok) {
                const data = await response.json();
                if (data.status === 'success' && data.results) {
                    // API 응답 구조에 맞게 변환
                    categories = data.results.map(cat => ({
                        category_sid: cat.category_sid,
                        category_name: cat.category_name,
                    }));
                    renderCategories();
                }
            }
        } catch (error) {
            console.error('Error loading categories:', error);
            renderCategories();
        }
    }

    // Initialize
    loadCategories();
    renderCategories();
    updateSaveButton();
    updateBookmarkCount();

    // Listen for modal open event
    document.addEventListener('modal:open', (e) => {
        if (e.detail.modalId === 'bookmarkModal') {
            selectedCategory = null;
            selectedCategorySid = null;
            
            // 모달 열 때 참조문헌 데이터 받기
            if (e.detail.references && Array.isArray(e.detail.references)) {
                // 다중 참고 문헌 모드
                currentReferences = e.detail.references;
                currentReferenceData = null;
                isMultipleMode = true;
            } else if (e.detail.referenceData) {
                // 단일 참고 문헌 모드
                currentReferenceData = e.detail.referenceData;
                currentReferences = null;
                isMultipleMode = false;
            } else {
                // 데이터 없음
                currentReferenceData = null;
                currentReferences = null;
                isMultipleMode = false;
            }
            
            loadCategories(); // 최신 카테고리 목록 다시 로드
            renderCategories();
            updateSaveButton();
            updateBookmarkCount();
        }
    });
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

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initBookmarkModal);
} else {
    initBookmarkModal();
}
