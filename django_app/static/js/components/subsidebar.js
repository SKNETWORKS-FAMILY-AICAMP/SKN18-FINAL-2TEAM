// SubSidebar Component JavaScript Logic

// Configuration for different sidebar types
const sidebarConfigs = {
    chat: {
        title: '채팅',
        searchPlaceholder: 'Search chats...',
        listTitle: '내 채팅',
    },
    schedule: {
        title: '일정 목록',
        searchPlaceholder: '일정 검색...',
        listTitle: '내 일정',
    },
    notes: {
        title: '노트 목록',
        searchPlaceholder: '노트 검색...',
        listTitle: '내 노트',
    },
    experiment: {
        title: '도구 가이드',
        searchPlaceholder: '도구 검색...',
        listTitle: '도구 목록',
    },
};

// Fallback mock data (used when API endpoints are not available)
const mockSubsidebarItems = [
    {
        id: 1,
        title: 'Eukaryotic cell이 뭐야?',
        preview: '세포 구조와 특징을 요약한 채팅입니다.',
    },
    {
        id: 2,
        title: 'EGFR 변이 단백질 시뮬레이션',
        preview: '후보 약물 도킹 및 상호작용 분석 기록입니다.',
    },
    {
        id: 3,
        title: '임상 프로토콜 검토',
        preview: '임상 2상 설계와 관련된 피드백이 포함되어 있습니다.',
    },
];

// State variables
let currentSidebarType = 'chat';
let subsidebarSearchQuery = '';
let filteredItems = [];

// DOM elements
const subsidebar = document.getElementById('subsidebar');
const searchInput = document.getElementById('subsidebarSearchInput');
const chatListElement = document.getElementById('chatList');
const newChatBtn = document.getElementById('newChatBtn');
const sectionItems = document.querySelectorAll('.section-item[data-section]');

// Initialize subsidebar functionality
function initSubsidebar(type = 'chat') {
    if (!subsidebar) {
        console.warn('Subsidebar element not found');
        return;
    }

    currentSidebarType = type;
    const config = getSidebarConfig(type);

    // Update title and placeholder if elements exist
    const titleElement = subsidebar.querySelector('.subsidebar-header h2');
    if (titleElement) {
        titleElement.textContent = config.title;
    }

    if (searchInput) {
        searchInput.placeholder = config.searchPlaceholder;
    }

    // Search input handler
    if (searchInput) {
        searchInput.addEventListener('input', handleSearch);
    }

    // New chat button handler
    if (newChatBtn) {
        newChatBtn.addEventListener('click', handleNewChat);
    }

    // Section item handlers
    sectionItems.forEach(item => {
        item.addEventListener('click', (e) => {
            const section = e.currentTarget.getAttribute('data-section');
            handleSectionClick(section);
        });
    });

    // Load initial data
    loadItems();
}

// Get sidebar config by type
function getSidebarConfig(type) {
    return sidebarConfigs[type] || {
        title: 'Sidebar',
        searchPlaceholder: 'Search...',
        listTitle: '목록',
    };
}

// Handle search input
function handleSearch(e) {
    subsidebarSearchQuery = e.target.value.toLowerCase().trim();
    filterItems();
}

// Filter items based on search query
function filterItems() {
    if (!chatListElement) return;

    const items = chatListElement.querySelectorAll('.chat-item');
    let visibleCount = 0;

    items.forEach(item => {
        const title = item.querySelector('.chat-item-title')?.textContent.toLowerCase() || '';
        const preview = item.querySelector('.chat-item-preview')?.textContent.toLowerCase() || '';
        const matches = !subsidebarSearchQuery || title.includes(subsidebarSearchQuery) || preview.includes(subsidebarSearchQuery);

        if (matches) {
            item.style.display = '';
            visibleCount++;
        } else {
            item.style.display = 'none';
        }
    });

    // Show empty state if no results
    const emptyState = chatListElement.querySelector('.empty-state');
    if (visibleCount === 0 && !emptyState) {
        const emptyDiv = document.createElement('div');
        emptyDiv.className = 'empty-state';
        emptyDiv.innerHTML = '<p>검색 결과가 없습니다.</p>';
        chatListElement.appendChild(emptyDiv);
    } else if (visibleCount > 0 && emptyState) {
        emptyState.remove();
    }
}

// Handle new chat button click
function handleNewChat() {
    // Trigger custom event for page-level handling
    const event = new CustomEvent('subsidebar:newChat', {
        detail: { type: currentSidebarType }
    });
    document.dispatchEvent(event);

    // Or navigate directly
    if (currentSidebarType === 'chat') {
        window.location.href = '/chat/new/';
    }
}

// Handle section click (favorites, archived)
function handleSectionClick(section) {
    // Update active state
    sectionItems.forEach(item => {
        item.classList.remove('active');
        if (item.getAttribute('data-section') === section) {
            item.classList.add('active');
        }
    });

    // Trigger custom event
    const event = new CustomEvent('subsidebar:sectionChange', {
        detail: { section, type: currentSidebarType }
    });
    document.dispatchEvent(event);

    // Load items for section
    loadItems(section);
}

// Load items (chat list, schedule list, etc.)
function loadItems(section = null) {
    if (!chatListElement) return;

    // Show loading state
    chatListElement.innerHTML = '<div class="empty-state"><p>로딩 중...</p></div>';

    // Fetch data from API
    const url = getApiUrl(currentSidebarType, section);
    
    fetch(url, {
        method: 'GET',
        headers: {
            'X-CSRFToken': getCsrfToken(),
            'Content-Type': 'application/json',
        },
    })
    .then(async (response) => {
        if (!response.ok) {
            console.error(`Subsidebar API returned ${response.status}, falling back to mock data. URL: ${url}`);
            const errorText = await response.text();
            console.error('Error response:', errorText);
            return null;
        }
        try {
            const data = await response.json();
            console.log('Subsidebar API response:', data);
            return data;
        } catch (jsonError) {
            console.error('Failed to parse subsidebar response JSON, falling back to mock data.', jsonError);
            return null;
        }
    })
    .then(data => {
        if (!data) {
            console.warn('No data received, using mock data.');
            renderItems(mockSubsidebarItems);
            return;
        }
        
        const items = Array.isArray(data.items) ? data.items : (Array.isArray(data) ? data : []);
        console.log('Processed items:', items);
        
        if (items && items.length > 0) {
            console.log(`Rendering ${items.length} items from API.`);
            renderItems(items);
        } else {
            console.warn('Subsidebar API returned no items, showing empty state.');
            if (chatListElement) {
                chatListElement.innerHTML = '<div class="empty-state"><p>항목이 없습니다.</p></div>';
            }
        }
    })
    .catch(error => {
        console.error('Error loading items, using mock data instead.', error);
        console.error('Error details:', error.message, error.stack);
        renderItems(mockSubsidebarItems);
    });
}

// Get API URL based on type and section
function getApiUrl(type, section) {
    const baseUrls = {
        chat: '/chat/api/chats/',
        schedule: '/api/schedules/',
        notes: '/api/notes/',
        experiment: '/api/tools/',
    };

    let url = baseUrls[type] || '/api/items/';
    
    if (section) {
        url += `?section=${section}`;
    }

    return url;
}

// Render items to the list
function renderItems(items) {
    if (!chatListElement) return;

    if (items.length === 0) {
        chatListElement.innerHTML = '<div class="empty-state"><p>항목이 없습니다.</p></div>';
        return;
    }

    chatListElement.innerHTML = items.map(item => {
        const isActive = item.id === getCurrentItemId();
        return `
            <div class="chat-item ${isActive ? 'active' : ''}" data-item-id="${item.id}">
                <div class="chat-item-content">
                    <div class="chat-item-text">
                        <p class="chat-item-title">${escapeHtml(item.title)}</p>
                        <p class="chat-item-preview">${escapeHtml(item.preview || '')}</p>
                    </div>
                    <button class="chat-menu-btn" data-item-id="${item.id}">
                        <i class="fas fa-ellipsis-vertical"></i>
                    </button>
                </div>
            </div>
        `;
    }).join('');

    // Attach click handlers
    attachItemHandlers();
}

// Attach click handlers to items
function attachItemHandlers() {
    const items = chatListElement.querySelectorAll('.chat-item');
    items.forEach(item => {
        item.addEventListener('click', (e) => {
            // Don't trigger if clicking menu button
            if (e.target.closest('.chat-menu-btn')) {
                return;
            }
            // Ignore clicks while the item is in inline edit mode
            if (e.target.closest('.chat-edit-mode')) {
                return;
            }

            const itemId = item.getAttribute('data-item-id');
            handleItemClick(itemId);
        });
    });

    // Menu button handlers
    const menuButtons = chatListElement.querySelectorAll('.chat-menu-btn');
    menuButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const itemId = btn.getAttribute('data-item-id');
            handleItemMenuClick(itemId);
        });
    });
}

// Handle item click
function handleItemClick(itemId) {
    // Update active state
    const items = chatListElement.querySelectorAll('.chat-item');
    items.forEach(item => {
        item.classList.remove('active');
        if (item.getAttribute('data-item-id') === itemId) {
            item.classList.add('active');
        }
    });

    // Trigger custom event
    const event = new CustomEvent('subsidebar:itemClick', {
        detail: { itemId, type: currentSidebarType }
    });
    document.dispatchEvent(event);
}

// Handle item menu button click
function handleItemMenuClick(itemId) {
    // Trigger custom event for context menu
    const event = new CustomEvent('subsidebar:itemMenuClick', {
        detail: { itemId, type: currentSidebarType }
    });
    document.dispatchEvent(event);
}

// Get current item ID from URL or state
function getCurrentItemId() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('id') || null;
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
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

// Set sidebar type
function setSidebarType(type) {
    currentSidebarType = type;
    initSubsidebar(type);
}

// Get current sidebar type
function getSidebarType() {
    return currentSidebarType;
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        // Auto-detect type from data attribute or default to 'chat'
        const type = subsidebar?.getAttribute('data-type') || 'chat';
        initSubsidebar(type);
    });
} else {
    const type = subsidebar?.getAttribute('data-type') || 'chat';
    initSubsidebar(type);
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.SubSidebarComponent = {
        initSubsidebar,
        getSidebarConfig,
        setSidebarType,
        getSidebarType,
        loadItems,
        filterItems,
        handleNewChat,
        renderItems,
    };
}
