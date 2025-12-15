// Bookmark Modal JavaScript

let selectedCategory = null;
let categories = ['전체', 'Research Papers', 'Clinical Trials', 'Protocols', 'My Favorites'];
let showNewCategoryInput = false;

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

    // Render categories
    function renderCategories() {
        if (!bookmarkCategories) return;
        
        bookmarkCategories.innerHTML = categories.map(category => {
            const isSelected = selectedCategory === category;
            return `
                <button class="bookmark-category-item ${isSelected ? 'selected' : ''}" data-category="${category}">
                    <i class="fas fa-folder"></i>
                    <span>${escapeHtml(category)}</span>
                    ${isSelected ? '<i class="fas fa-check check-icon"></i>' : ''}
                </button>
            `;
        }).join('');

        // Attach click handlers
        bookmarkCategories.querySelectorAll('.bookmark-category-item').forEach(item => {
            item.addEventListener('click', () => {
                selectedCategory = item.getAttribute('data-category');
                renderCategories();
                updateSaveButton();
            });
        });
    }

    // Update save button state
    function updateSaveButton() {
        if (saveBookmarkBtn) {
            saveBookmarkBtn.disabled = !selectedCategory;
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

    if (createCategoryBtn) {
        createCategoryBtn.addEventListener('click', () => {
            const name = newCategoryName?.value.trim();
            if (name && !categories.includes(name)) {
                categories.push(name);
                selectedCategory = name;
                showNewCategoryInput = false;
                if (newCategoryInput) {
                    newCategoryInput.style.display = 'none';
                }
                if (newCategoryName) {
                    newCategoryName.value = '';
                }
                renderCategories();
                updateSaveButton();
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

    // Save bookmark
    if (saveBookmarkBtn) {
        saveBookmarkBtn.addEventListener('click', () => {
            if (selectedCategory) {
                // TODO: API call to save bookmark
                if (window.notyf) {
                    window.notyf.success(`참조 문헌을 "${selectedCategory}" 폴더에 저장했습니다.`);
                }
                if (window.Modal) {
                    window.Modal.close('bookmarkModal');
                }
                selectedCategory = null;
                renderCategories();
                updateSaveButton();
            }
        });
    }

    // Load categories from API
    async function loadCategories() {
        try {
            const response = await fetch('/api/bookmarks/categories/', {
                method: 'GET',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'Content-Type': 'application/json',
                },
            });
            if (response.ok) {
                const data = await response.json();
                categories = data.categories || categories;
                renderCategories();
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

    // Listen for modal open event
    document.addEventListener('modal:open', (e) => {
        if (e.detail.modalId === 'bookmarkModal') {
            selectedCategory = null;
            renderCategories();
            updateSaveButton();
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
