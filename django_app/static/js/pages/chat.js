// Chat Page JavaScript Logic

// State variables
let message = "";
let activeChatId = null;
let editingChatId = null;
let editingTitle = "";
let selectedFilter = "";
let isAutoMode = true;
let showRecommendations = false;
let showPlusModal = false;
let showFilterTooltip = false;
let messages = [];
let references = [];
let selectedReferences = [];
let selectedReferenceId = null;
let showBookmarkModal = false;
let showReferenceSelectionModal = false;
let showGraphSummaryModal = false;
let showPaperGraphModal = false;
let referenceSearchQuery = "";
let currentPage = 1;
const itemsPerPage = 5;
let openMenuId = null;
let attachedImages = [];
let attachedTables = [];
let attachedExperiments = [];
let fileInputRef = null;

const chatList = [];

// Chat messages for each chat
const chatMessagesData = {};

// Mock references data (9 references like React)
const mockReferences = [];

// Recommended questions - 카테고리별로 저장
let recommendedQuestionsByCategory = {
    'P': [], // 논문
    'C': [], // 임상
    'T': [], // 프로토콜
    'S': [], // 시뮬레이션
    'R': []  // 결과 해석
};

// DOM elements
const chatMessagesList = document.getElementById('chatMessages');
const emptyState = document.getElementById('emptyState');
const messagesView = document.getElementById('messagesView');
const inputArea = document.getElementById('inputArea');
const chatInputField = document.getElementById('chatInputField');
const chatInputFieldBottom = document.getElementById('chatInputFieldBottom');
const sendBtn = document.getElementById('sendBtn');
const sendBtnBottom = document.getElementById('sendBtnBottom');
const recommendationsDropdown = document.getElementById('recommendationsDropdown');
const recommendationsList = document.getElementById('recommendationsList');
const closeRecommendationsBtn = document.getElementById('closeRecommendationsBtn');
const autoModeToggle = document.getElementById('autoModeToggle');
const autoModeToggleBottom = document.getElementById('autoModeToggleBottom');
const filterBtns = document.querySelectorAll('.filter-btn');
const referencesList = document.getElementById('referencesList');
const referencesCount = document.getElementById('referencesCount');
const saveReferencesBtn = document.getElementById('saveReferencesBtn');
const referencesSidebar = document.getElementById('referencesSidebar');
const attachBtn = document.getElementById('attachBtn');
const attachBtnBottom = document.getElementById('attachBtnBottom');
const plusDropdown = document.getElementById('plusDropdown');
const plusDropdownBottom = document.getElementById('plusDropdownBottom');
const filterControls = document.getElementById('filterControls');
const filterControlsBottom = document.getElementById('filterControlsBottom');
const fileInput = document.getElementById('fileInput');
const fileInputBottom = document.getElementById('fileInputBottom');

// Initialize chat page
function initChatAI() {
    // Initialize filter buttons state
    updateFilterButtonsState();

    // Load chat list
    loadChatList();
    
    // Load recommended questions
    loadRecommendedQuestions();

    // Listen for subsidebar events
    document.addEventListener('subsidebar:newChat', handleNewChat);
    document.addEventListener('subsidebar:itemClick', (e) => {
        handleChatSelect(parseInt(e.detail.itemId));
    });
    document.addEventListener('subsidebar:itemMenuClick', (e) => {
        handleChatMenuClick(parseInt(e.detail.itemId));
    });

    // Load chat if chatId is in URL
    const urlParams = new URLSearchParams(window.location.search);
    const chatId = urlParams.get('id');
    if (chatId) {
        loadChat(parseInt(chatId));
    } else {
        // Show empty state
        references = [];
        renderReferences();
    }

    // Event listeners
    if (chatInputField) {
        chatInputField.addEventListener('input', handleInputChange);
        chatInputField.addEventListener('focus', handleInputFocus);
        chatInputField.addEventListener('keydown', handleInputKeydown);
    }

    if (chatInputFieldBottom) {
        chatInputFieldBottom.addEventListener('input', handleInputChange);
        chatInputFieldBottom.addEventListener('keydown', handleInputKeydown);
    }

    if (sendBtn) {
        sendBtn.addEventListener('click', handleSend);
    }

    if (sendBtnBottom) {
        sendBtnBottom.addEventListener('click', handleSend);
    }

    if (closeRecommendationsBtn) {
        closeRecommendationsBtn.addEventListener('click', closeRecommendations);
    }

    // Auto mode toggle handlers - Shoelace switch 사용
    // Shoelace switch는 sl-change 이벤트를 사용하고, customElements.whenDefined으로 컴포넌트가 로드될 때까지 기다림
    customElements.whenDefined('sl-switch').then(async () => {
        const autoModeToggleEl = document.getElementById('autoModeToggle');
        if (autoModeToggleEl) {
            // 초기 상태 설정
            await autoModeToggleEl.updateComplete;
            autoModeToggleEl.checked = isAutoMode;
            
            // 초기 상태에 맞춰 filter-btn 상태 업데이트
            updateFilterButtonsState();
            
            autoModeToggleEl.addEventListener('sl-change', (e) => {
                toggleAutoMode(e.target.checked);
            });
        }

        const autoModeToggleBottomEl = document.getElementById('autoModeToggleBottom');
        if (autoModeToggleBottomEl) {
            // 초기 상태 설정
            await autoModeToggleBottomEl.updateComplete;
            autoModeToggleBottomEl.checked = isAutoMode;
            
            autoModeToggleBottomEl.addEventListener('sl-change', (e) => {
                toggleAutoMode(e.target.checked);
            });
        }
    });

    // Filter buttons - DOM 요소를 다시 가져와서 확실히 존재하는지 확인
    const filterBtnsEls = document.querySelectorAll('.filter-btn');
    filterBtnsEls.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const filter = e.currentTarget.getAttribute('data-filter');
            handleFilterSelect(filter);
        });
    });

    // Message action buttons
    attachMessageActionHandlers();

    // Reference handlers
    attachReferenceHandlers();

    // Plus button handlers
    attachPlusButtonHandlers();
    
    // File input handlers
    if (fileInput) {
        fileInput.addEventListener('change', handleImageSelect);
    }
    if (fileInputBottom) {
        fileInputBottom.addEventListener('change', handleImageSelect);
    }
    
    // Modal event listeners
    document.addEventListener('table:attached', handleTableAttached);
    document.addEventListener('experiment:attached', handleExperimentAttached);
    
    // Initial render of attached items
    renderAttachedItems();

    // Filter tooltip handlers
    // Filter tooltip은 Shoelace tooltip으로 자동 처리됨

    // Render recommendations
    renderRecommendations();

    // Load references
    loadReferences();

    // Click outside handlers
    attachClickOutsideHandlers();
}

// Handle input change
function handleInputChange(e) {
    message = e.target.value;
}

// Handle input focus
function handleInputFocus() {
    // 입력 필드가 비어있을 때 추천 질문 표시
    const primaryInputValue = chatInputField ? chatInputField.value.trim() : '';
    const secondaryInputValue = chatInputFieldBottom ? chatInputFieldBottom.value.trim() : '';
    const inputValue = primaryInputValue || secondaryInputValue || '';
    if (inputValue.length === 0) {
        showRecommendationsDropdown();
    }
}

// Handle input keydown
function handleInputKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
    } else if (e.key === 'Escape') {
        closeRecommendations();
    }
}

// Handle send message
async function handleSend() {
    const inputTop = chatInputField ? chatInputField.value.trim() : '';
    const inputBottom = chatInputFieldBottom ? chatInputFieldBottom.value.trim() : '';
    const input = inputTop || inputBottom || message.trim();
    
    if (!input) {
        return;
    }

    // Hide empty state and show messages view
    if (emptyState) {
        emptyState.style.display = 'none';
    }
    if (messagesView) {
        messagesView.style.display = 'block';
    }
    if (inputArea) {
        inputArea.style.display = 'block';
    }

    // Add user message
    const userMessage = {
        role: 'user',
        content: input,
        timestamp: new Date().toISOString(),
    };
    messages.push(userMessage);
    renderMessages();

    // Clear input
    if (chatInputField) chatInputField.value = "";
    if (chatInputFieldBottom) chatInputFieldBottom.value = "";
    message = "";

    // Close recommendations
    closeRecommendations();

    // Send to API
    try {
        const response = await fetch('/api/chat/send/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: input,
                chat_id: activeChatId,
                filter: selectedFilter,
                auto_mode: isAutoMode,
            }),
        });

        if (response.ok) {
            const data = await response.json();
            
            // Add assistant message
            const assistantMessage = {
                role: 'assistant',
                content: data.response,
                message_id: data.message_id,
                timestamp: new Date().toISOString(),
            };
            messages.push(assistantMessage);
            
            // Update references
            if (data.references) {
                references = data.references;
            } 
            // else if (activeChatId === 1) {
            //     // Use mock references for chat 1
            //     references = mockReferences;
            // } 
            else {
                references = [];
            }
            renderReferences();
            
            renderMessages();
        } else {
            const error = await response.json();
            console.error('Error sending message:', error);
            
            // Show error message
            const errorMessage = {
                role: 'assistant',
                content: '죄송합니다. 오류가 발생했습니다. 다시 시도해주세요.',
                is_error: true,
            };
            messages.push(errorMessage);
            renderMessages();
        }
    } catch (error) {
        console.error('Error sending message:', error);
        
        // Show error message
        const errorMessage = {
            role: 'assistant',
            content: '네트워크 오류가 발생했습니다. 다시 시도해주세요.',
            is_error: true,
        };
        messages.push(errorMessage);
        renderMessages();
    }
}

// Load chat
async function loadChat(chatId) {
    try {
        // Show loading state
        if (messagesView) {
            messagesView.innerHTML = '<div class="empty-state"><p>로딩 중...</p></div>';
            messagesView.style.display = 'block';
        }
        if (emptyState) {
            emptyState.style.display = 'none';
        }
        if (inputArea) {
            inputArea.style.display = 'block';
        }
        
        const response = await fetch(`/chat/api/chats/${chatId}/`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
        });

        if (response.ok) {
            const data = await response.json();
            activeChatId = chatId;
            
            // Format messages
            messages = (data.messages || []).map(msg => ({
                role: msg.role,
                content: msg.content,
                message_id: msg.id,
                sort_order: msg.sort_order,
                created_at: msg.created_at,
                paper_graphs: msg.paper_graphs || [], // Include paper_graphs data
            }));
            
            // Format references
            references = (data.references || []).map(ref => ({
                id: ref.id,
                source: ref.source,
                badge: ref.badge,
                title: ref.title,
                description: ref.description,
                journal: ref.journal,
                link: ref.link,
                pmid: ref.pmid,
                date: ref.date,
                authors: ref.authors,
            }));
            
            // Show messages view
            if (emptyState) {
                emptyState.style.display = 'none';
            }
            if (messagesView) {
                messagesView.style.display = 'block';
            }
            if (inputArea) {
                inputArea.style.display = 'block';
            }
            
            renderMessages();
            renderReferences();
        } else {
            console.error('Failed to load chat:', response.status);
            if (messagesView) {
                messagesView.innerHTML = '<div class="empty-state"><p>채팅을 불러오는데 실패했습니다.</p></div>';
            }
        }
    } catch (error) {
        console.error('Error loading chat:', error);
        if (messagesView) {
            messagesView.innerHTML = '<div class="empty-state"><p>채팅을 불러오는데 실패했습니다.</p></div>';
        }
    }
}

// Render messages
function renderMessages() {
    if (!messagesView) return;

    messagesView.innerHTML = messages.map((msg, index) => {
        if (msg.role === 'user') {
            return `
                <div class="message-item">
                    <div class="message-user">
                        <div class="message-content-user">
                            <div class="message-bubble-user">
                                <p>${escapeHtml(msg.content)}</p>
                            </div>
                        </div>
                        <div class="message-avatar user-avatar">U</div>
                    </div>
                </div>
            `;
        } else {
            // Check if this message has paper_graphs
            const hasPaperGraphs = msg.paper_graphs && Array.isArray(msg.paper_graphs) && msg.paper_graphs.length > 0;
            const showPaperGraphBtn = hasPaperGraphs;
            
            // Check if this is the last message for experiment button
            const isLastMessage = index === messages.length - 1;
            const showExperimentBtn = activeChatId === 2 && isLastMessage;
            
            return `
                <div class="message-item">
                    <div class="message-assistant">
                        <div class="message-avatar assistant-avatar">AI</div>
                        <div class="message-content-assistant">
                            <div class="markdown-content" data-message-index="${index}">
                                ${msg.is_error ? `<p style="color: #dc2626;">${escapeHtml(msg.content)}</p>` : (window.MarkdownUtils ? window.MarkdownUtils.render(msg.content || '') : escapeHtml(msg.content))}
                            </div>
                            ${!msg.is_error ? `
                            ${showPaperGraphBtn ? `
                            <div class="message-special-actions">
                                <button class="special-action-btn" data-action="paper-graph" data-message-id="${msg.message_id || index}">
                                    <i class="fas fa-chart-bar"></i>
                                    관련 논문 상세 보기
                                </button>
                            </div>
                            ` : ''}
                            ${showExperimentBtn ? `
                            <div class="message-special-actions">
                                <button class="special-action-btn" data-action="experiment">
                                    <i class="fas fa-flask"></i>
                                    실험하기
                                </button>
                            </div>
                            ` : ''}
                            <div class="message-actions">
                                <div class="message-actions-left">
                                    <button class="action-btn" title="복사" data-action="copy" data-message-id="${msg.message_id || index}">
                                        <i class="fas fa-copy"></i>
                                    </button>
                                    <button class="action-btn" title="좋아요" data-action="like" data-message-id="${msg.message_id || index}">
                                        <i class="fas fa-thumbs-up"></i>
                                    </button>
                                    <button class="action-btn" title="싫어요" data-action="dislike" data-message-id="${msg.message_id || index}">
                                        <i class="fas fa-thumbs-down"></i>
                                    </button>
                                </div>
                                <div class="message-actions-right">
                                    <button class="action-btn-text" data-action="save-to-note" data-message-id="${msg.message_id || index}">
                                        <i class="fa-solid fa-note-sticky"></i>
                                        <span>노트에 저장</span>
                                    </button>
                                    <button class="action-btn-text" data-action="graph-summary" data-message-id="${msg.message_id || index}">
                                        <i class="fas fa-chart-bar"></i>
                                        <span>그래프 요약</span>
                                    </button>
                                </div>
                            </div>
                            ` : ''}
                        </div>
                    </div>
                </div>
            `;
        }
    }).join('');

    // Scroll to bottom
    if (chatMessagesList) {
        chatMessagesList.scrollTop = chatMessagesList.scrollHeight;
    }

    // Process Mermaid charts in markdown content
    if (window.MermaidChart) {
        messagesView.querySelectorAll('.markdown-content').forEach(container => {
            window.MermaidChart.renderAll(container);
        });
    }

    // Show/hide references sidebar based on messages and references
    if (referencesSidebar) {
        if (messages.length > 0 && references.length > 0) {
            referencesSidebar.style.display = 'flex';
        } else {
            referencesSidebar.style.display = 'none';
        }
    }

    // Re-attach handlers
    attachMessageActionHandlers();
}

// Load recommended questions from API
async function loadRecommendedQuestions() {
    try {
        const response = await fetch('/chat/api/recommended-questions/');
        if (!response.ok) {
            throw new Error('Failed to load recommended questions');
        }
        const data = await response.json();
        
        // 카테고리별로 질문 저장
        recommendedQuestionsByCategory = data.questions_by_category || {
            'P': [],
            'C': [],
            'T': [],
            'S': [],
            'R': []
        };
        
        // 각 카테고리별로 렌더링
        renderRecommendationsByCategory();
    } catch (error) {
        console.error('Error loading recommended questions:', error);
        // 에러 발생 시 빈 배열로 초기화
        recommendedQuestionsByCategory = {
            'P': [],
            'C': [],
            'T': [],
            'S': [],
            'R': []
        };
        renderRecommendationsByCategory();
    }
}

// Render recommendations by category
function renderRecommendationsByCategory() {
    const categoryMap = {
        'P': 'recommendationsListP',
        'C': 'recommendationsListC',
        'T': 'recommendationsListT',
        'S': 'recommendationsListS',
        'R': 'recommendationsListR'
    };
    
    // 각 카테고리별로 렌더링
    Object.keys(categoryMap).forEach(category => {
        const listEl = document.getElementById(categoryMap[category]);
        if (!listEl) {
            console.warn(`Recommendations list element not found for category ${category}`);
            return;
        }
        
        const questions = recommendedQuestionsByCategory[category] || [];
        
        if (questions.length === 0) {
            listEl.innerHTML = '<div class="recommendation-empty">추천 질문이 없습니다.</div>';
            return;
        }
        
        listEl.innerHTML = questions.map((question, index) => {
            return `
                <div class="recommendation-item" data-question-id="${question.id}" data-category="${category}">
                    ${escapeHtml(question.text)}
                </div>
            `;
        }).join('');
        
        // Attach click handlers
        const recommendationItems = listEl.querySelectorAll('.recommendation-item');
        recommendationItems.forEach(item => {
            item.addEventListener('click', (e) => {
                const questionId = e.currentTarget.getAttribute('data-question-id');
                const category = e.currentTarget.getAttribute('data-category');
                selectRecommendation(questionId, category);
            });
        });
    });
}

// Render recommendations (legacy function for backward compatibility)
function renderRecommendations() {
    // API에서 데이터를 로드하고 렌더링
    loadRecommendedQuestions();
}

// Select recommendation
function selectRecommendation(questionId, category) {
    const questions = recommendedQuestionsByCategory[category] || [];
    const question = questions.find(q => q.id == questionId);
    
    if (question) {
        const questionText = question.text;
        if (chatInputField) {
            chatInputField.value = questionText;
        }
        if (chatInputFieldBottom) {
            chatInputFieldBottom.value = questionText;
        }
        message = questionText;
        closeRecommendations();
        // Auto send after a short delay
        setTimeout(() => {
            handleSend();
        }, 100);
    }
}

// Show recommendations dropdown
function showRecommendationsDropdown() {
    const recommendationsDropdownEl = document.getElementById('recommendationsDropdown');
    if (recommendationsDropdownEl) {
        // 추천 질문이 로드되지 않았다면 API에서 로드
        const hasData = Object.values(recommendedQuestionsByCategory).some(questions => questions.length > 0);
        if (!hasData) {
            loadRecommendedQuestions();
        }
        recommendationsDropdownEl.style.display = 'block';
        showRecommendations = true;
    }
}

// Close recommendations
function closeRecommendations() {
    const recommendationsDropdownEl = document.getElementById('recommendationsDropdown');
    if (recommendationsDropdownEl) {
        recommendationsDropdownEl.style.display = 'none';
        showRecommendations = false;
    }
}

// Toggle auto mode
// Shoelace switch는 checked 상태를 직접 전달받음
function toggleAutoMode(checked) {
    isAutoMode = checked !== undefined ? checked : !isAutoMode;
    
    // DOM 요소를 함수 내부에서 다시 가져와서 확실히 존재하는지 확인
    const autoModeToggleEl = document.getElementById('autoModeToggle');
    const autoModeToggleBottomEl = document.getElementById('autoModeToggleBottom');
    const toggles = [autoModeToggleEl, autoModeToggleBottomEl];
    
    // Shoelace switch의 checked 속성 업데이트
    toggles.forEach(toggle => {
        if (toggle && toggle.tagName === 'SL-SWITCH') {
            toggle.checked = isAutoMode;
        }
    });

    // Update filter buttons state
    updateFilterButtonsState();
    
    // Update selected filter
    if (isAutoMode) {
        selectedFilter = '';
        handleFilterSelect('');
    }
}

// Update filter buttons state based on auto mode
function updateFilterButtonsState() {
    // DOM 요소를 함수 내부에서 다시 가져와서 확실히 존재하는지 확인
    const filterBtnsEls = document.querySelectorAll('.filter-btn');
    filterBtnsEls.forEach(btn => {
        if (isAutoMode) {
            btn.disabled = true;
            btn.classList.add('disabled');
        } else {
            btn.disabled = false;
            btn.classList.remove('disabled');
        }
    });
}

// Handle filter select
function handleFilterSelect(filter) {
    if (isAutoMode) {
        return; // Don't allow filter selection in auto mode
    }
    
    selectedFilter = selectedFilter === filter ? "" : filter;
    
    // DOM 요소를 함수 내부에서 다시 가져와서 확실히 존재하는지 확인
    const filterBtnsEls = document.querySelectorAll('.filter-btn');
    filterBtnsEls.forEach(btn => {
        const btnFilter = btn.getAttribute('data-filter');
        if (btnFilter === selectedFilter) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
}

// Handle new chat
function handleNewChat() {
    activeChatId = null;
    messages = [];
    message = "";
    editingChatId = null;
    editingTitle = "";
    
    // Show empty state
    if (emptyState) emptyState.style.display = 'flex';
    if (messagesView) messagesView.style.display = 'none';
    if (inputArea) inputArea.style.display = 'none';
    
    // Clear input
    if (chatInputField) chatInputField.value = "";
    if (chatInputFieldBottom) chatInputFieldBottom.value = "";
    
    // Load mock references
    references = mockReferences;
    renderReferences();
    
    // Update URL
    window.history.pushState({}, '', '/chat/');
}

// Handle chat select
function handleChatSelect(chatId) {
    // Load chat from API
    loadChat(chatId);
    
    // Update URL
    window.history.pushState({}, '', `/chat/?id=${chatId}`);
}

// Handle chat menu click
function handleChatMenuClick(chatId) {
    openMenuId = openMenuId === chatId ? null : chatId;
    renderChatMenu(chatId);
}

// Render chat menu
function renderChatMenu(chatId) {
    // Remove existing menus
    document.querySelectorAll('.chat-menu-dropdown').forEach(menu => menu.remove());
    
    if (openMenuId !== chatId) return;
    
    const chatItem = document.querySelector(`.chat-item[data-item-id="${chatId}"]`);
    if (!chatItem) return;
    
    const menuBtn = chatItem.querySelector('.chat-menu-btn');
    if (!menuBtn) return;
    
    const rect = menuBtn.getBoundingClientRect();
    const menu = document.createElement('div');
    menu.className = 'chat-menu-dropdown';
    menu.style.cssText = `
        position: fixed;
        right: ${window.innerWidth - rect.right + 8}px;
        top: ${rect.bottom + 4}px;
        width: 10rem;
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 0.5rem;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1);
        z-index: 1000;
        overflow: hidden;
    `;
    
    menu.innerHTML = `
        <button class="chat-menu-item" data-action="pin">
            <i class="fa fa-thumbtack"></i>
            <span>Pin Chat</span>
        </button>
        <button class="chat-menu-item" data-action="edit">
            <i class="fa fa-pencil"></i>
            <span>Edit</span>
        </button>
        <button class="chat-menu-item" data-action="archive">
            <i class="fa fa-archive"></i>
            <span>Archive</span>
        </button>
        <button class="chat-menu-item" data-action="delete">
            <i class="fa fa-trash"></i>
            <span>Delete</span>
        </button>
    `;
    
    document.body.appendChild(menu);
    
    // Attach menu handlers
    menu.querySelectorAll('.chat-menu-item').forEach(item => {
        item.addEventListener('click', (e) => {
            const action = item.getAttribute('data-action');
            handleChatMenuAction(action, chatId);
            menu.remove();
            openMenuId = null;
        });
    });
    
    // Close on outside click
    setTimeout(() => {
        document.addEventListener('click', function closeMenu(e) {
            if (!menu.contains(e.target) && !menuBtn.contains(e.target)) {
                menu.remove();
                openMenuId = null;
                document.removeEventListener('click', closeMenu);
            }
        });
    }, 0);
}

// Handle chat menu action
function handleChatMenuAction(action, chatId) {
    switch (action) {
        case 'pin':
            // TODO: Implement pin API call
            // Close menu
            openMenuId = null;
            document.querySelectorAll('.chat-menu-dropdown').forEach(menu => menu.remove());
            
            // Show toast notification
            if (window.notyf) {
                try {
                    window.notyf.success('채팅이 고정되었습니다.');
                } catch (error) {
                    console.error('Notyf error:', error);
                    alert('채팅이 고정되었습니다.');
                }
            } else {
                console.warn('Notyf is not initialized');
                alert('채팅이 고정되었습니다.');
            }
            break;
        case 'edit':
            editingChatId = chatId;
            const chat = chatList.find(c => c.id === chatId);
            editingTitle = chat ? chat.title : '';
            renderChatEdit(chatId);
            break;
        case 'archive':
            // TODO: Implement archive API call
            // Close menu
            openMenuId = null;
            document.querySelectorAll('.chat-menu-dropdown').forEach(menu => menu.remove());
            
            // Show toast notification
            if (window.notyf) {
                try {
                    window.notyf.success('채팅이 보관되었습니다.');
                } catch (error) {
                    console.error('Notyf error:', error);
                    alert('채팅이 보관되었습니다.');
                }
            } else {
                console.warn('Notyf is not initialized');
                alert('채팅이 보관되었습니다.');
            }
            break;
        case 'delete':
            // Use SweetAlert2 for confirmation
            if (window.Swal) {
                window.Swal.fire({
                    title: '삭제 하시겠습니까?',
                    text: '이 작업은 되돌릴 수 없습니다.',
                    icon: 'warning',
                    showCancelButton: true,
                    confirmButtonColor: '#dc2626',
                    cancelButtonColor: '#6b7280',
                    confirmButtonText: '삭제',
                    cancelButtonText: '취소',
                    reverseButtons: true
                }).then((result) => {
                    if (result.isConfirmed) {
                        // TODO: Implement delete API call
                        // For now, remove from local list
                        const index = chatList.findIndex(c => c.id === chatId);
                        if (index > -1) {
                            chatList.splice(index, 1);
                        }
                        
                        // Re-render chat list
                        if (window.SubSidebarComponent && window.SubSidebarComponent.renderItems) {
                            window.SubSidebarComponent.renderItems(chatList);
                        }
                        
                        // If deleted chat was active, clear it
                        if (activeChatId === chatId) {
                            handleNewChat();
                        }
                        
                        if (window.notyf) {
                            window.notyf.success('채팅이 삭제되었습니다.');
                        }
                    }
                });
            } else {
                // Fallback to confirm if SweetAlert2 is not available
                if (confirm('삭제 하시겠습니까?')) {
                    // TODO: Implement delete
                    if (window.notyf) {
                        window.notyf.success('채팅이 삭제되었습니다.');
                    }
                }
            }
            break;
    }
}

// Render chat edit
function renderChatEdit(chatId) {
    const chatItem = document.querySelector(`.chat-item[data-item-id="${chatId}"]`);
    if (!chatItem) return;
    
    chatItem.innerHTML = `
        <div class="chat-edit-mode">
            <input type="text" class="chat-edit-input" value="${escapeHtml(editingTitle)}" id="chatEditInput${chatId}">
            <div class="chat-edit-actions">
                <button class="chat-edit-save" data-chat-id="${chatId}">저장</button>
                <button class="chat-edit-cancel" data-chat-id="${chatId}">취소</button>
            </div>
        </div>
    `;
    
    const input = document.getElementById(`chatEditInput${chatId}`);
    if (input) {
        input.focus();
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                handleSaveChatTitle(chatId);
            } else if (e.key === 'Escape') {
                handleCancelEdit(chatId);
            }
        });
    }
    
    const saveBtn = chatItem.querySelector('.chat-edit-save');
    const cancelBtn = chatItem.querySelector('.chat-edit-cancel');
    if (saveBtn) {
        saveBtn.addEventListener('click', () => {
            console.log('Chat edit 저장 clicked', chatId);
            handleSaveChatTitle(chatId);
        });
    }
    if (cancelBtn) {
        cancelBtn.addEventListener('click', () => {
            console.log('Chat edit 취소 clicked', chatId);
            handleCancelEdit(chatId);
        });
    }
}

// Handle save chat title
function handleSaveChatTitle(chatId) {
    const input = document.getElementById(`chatEditInput${chatId}`);
    if (!input) return;
    
    const newTitle = input.value.trim();
    if (!newTitle) {
        if (window.notyf) {
            window.notyf.error('제목을 입력해주세요.');
        }
        return;
    }
    
    // Update chat list
    const chat = chatList.find(c => c.id === chatId);
    if (chat) {
        chat.title = newTitle;
    }
    
    // Reset edit state
    editingChatId = null;
    editingTitle = "";
    openMenuId = null; // Close menu if open
    
    // Remove any open menus
    document.querySelectorAll('.chat-menu-dropdown').forEach(menu => menu.remove());
    
    // Re-render chat list to restore original state
    if (window.SubSidebarComponent && window.SubSidebarComponent.renderItems) {
        window.SubSidebarComponent.renderItems(chatList);
    }
    
    if (window.notyf) {
        window.notyf.success('제목이 저장되었습니다.');
    }
}

// Handle cancel edit
function handleCancelEdit(chatId) {
    // Reset edit state
    editingChatId = null;
    editingTitle = "";
    openMenuId = null; // Close menu if open
    
    // Remove any open menus
    document.querySelectorAll('.chat-menu-dropdown').forEach(menu => menu.remove());
    
    // Re-render chat list to restore original state
    if (window.SubSidebarComponent && window.SubSidebarComponent.renderItems) {
        window.SubSidebarComponent.renderItems(chatList);
    }
}

// Load chat list
async function loadChatList() {
    try {
        // TODO: Replace with API call
        // const response = await fetch('/api/chat/list/');
        // const data = await response.json();
        // chatList = data.chats;
        
        // For now, use mock data
        if (window.SubSidebarComponent && window.SubSidebarComponent.renderItems) {
            window.SubSidebarComponent.renderItems(chatList);
        }
    } catch (error) {
        console.error('Error loading chat list:', error);
    }
}

// Load references
async function loadReferences() {
    // References are loaded from context or API
    if (references.length > 0) {
        renderReferences();
    }
}

// Render references
function renderReferences() {
    if (!referencesList) return;

    // Show references sidebar if references exist and messages exist
    if (references.length > 0 && messages.length > 0 && referencesSidebar) {
        referencesSidebar.style.display = 'flex';
    } else if (referencesSidebar) {
        referencesSidebar.style.display = 'none';
    }

    if (references.length === 0) {
        referencesList.innerHTML = '<div class="empty-state"><p>참고 문헌이 없습니다.</p></div>';
        if (referencesCount) {
            referencesCount.textContent = '0';
        }
        return;
    }

    referencesList.innerHTML = references.map((ref) => {
        return `
            <div class="reference-item" data-reference-id="${ref.id}">
                <button class="reference-bookmark-btn" data-reference-id="${ref.id}" title="북마크에 저장">
                    <i class="fas fa-bookmark"></i>
                </button>
                <div class="reference-content">
                    <div class="reference-number">${ref.id}</div>
                    <div class="reference-details">
                        <div class="reference-meta">
                            <span class="reference-source">${escapeHtml(ref.source || 'Unknown')}</span>
                            ${ref.badge ? `<span class="reference-badge">${escapeHtml(ref.badge)}</span>` : ''}
                        </div>
                        <h3 class="reference-title">${escapeHtml(ref.title)}</h3>
                        ${ref.description ? `<p class="reference-description">${escapeHtml(ref.description)}</p>` : ''}
                        <div class="reference-info">
                            ${ref.link ? `
                            <div class="reference-info-item">
                                <i class="fas fa-link"></i>
                                <a href="#" class="reference-link">${escapeHtml(ref.link)}</a>
                            </div>
                            ` : ''}
                            ${ref.journal ? `
                            <div class="reference-info-item">
                                <i class="fas fa-file-lines"></i>
                                <span>${escapeHtml(ref.journal)}</span>
                                ${ref.journal.startsWith('www') ? '<i class="fas fa-external-link-alt"></i>' : ''}
                            </div>
                            ` : ''}
                            ${ref.date ? `
                            <div class="reference-info-item">
                                <i class="fas fa-calendar"></i>
                                <span>${escapeHtml(ref.date)}</span>
                            </div>
                            ` : ''}
                            ${ref.authors ? `
                            <div class="reference-info-item">
                                <i class="fas fa-user"></i>
                                <span>${escapeHtml(ref.authors)}</span>
                            </div>
                            ` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    if (referencesCount) {
        referencesCount.textContent = references.length;
    }

    // Re-attach handlers
    attachReferenceHandlers();
}

// Attach message action handlers
function attachMessageActionHandlers() {
    const actionBtns = messagesView ? messagesView.querySelectorAll('.action-btn, .action-btn-text, .special-action-btn') : null;
    if (actionBtns) {
        actionBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const action = btn.getAttribute('data-action');
                const messageId = btn.getAttribute('data-message-id');
                handleMessageAction(action, messageId);
            });
        });
    }
}

// Handle message action
function handleMessageAction(action, messageId) {
    switch (action) {
        case 'copy':
            copyMessage(messageId);
            break;
        case 'like':
            likeMessage(messageId);
            break;
        case 'dislike':
            dislikeMessage(messageId);
            break;
        case 'save-to-note':
            saveToNote(messageId);
            break;
        case 'graph-summary':
            showGraphSummary(messageId);
            break;
        case 'paper-graph':
            showPaperGraphModal = true;
            if (window.PaperGraphModal && window.PaperGraphModal.open) {
                window.PaperGraphModal.open();
            } else if (window.Modal && window.Modal.open) {
                window.Modal.open('paperGraphModal');
            }
            break;
        case 'experiment':
            window.location.href = '/experiments/';
            break;
    }
}

// Copy message
function copyMessage(messageId) {
    const message = messages.find(m => (m.message_id || m.id) === messageId);
    if (!message || !message.content) {
        if (window.notyf) {
            window.notyf.error('복사할 메시지가 없습니다.');
        }
        return;
    }
    
    // Get text content - if it's markdown, try to get plain text from rendered element
    let textToCopy = message.content;
    
    // Try to get plain text from rendered markdown element if available
    const messageElement = messagesView?.querySelector(`[data-message-index="${messages.indexOf(message)}"]`);
    if (messageElement) {
        // Get text content from the rendered markdown element
        const textContent = messageElement.textContent || messageElement.innerText;
        if (textContent && textContent.trim()) {
            textToCopy = textContent.trim();
        }
    }
    
    // Use Clipboard API
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(textToCopy).then(() => {
            if (window.notyf) {
                window.notyf.success('메시지가 복사되었습니다.');
            }
        }).catch((error) => {
            console.error('Failed to copy:', error);
            // Fallback to old method
            fallbackCopyTextToClipboard(textToCopy);
        });
    } else {
        // Fallback for older browsers
        fallbackCopyTextToClipboard(textToCopy);
    }
}

// Fallback copy function for older browsers
function fallbackCopyTextToClipboard(text) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-999999px';
    textArea.style.top = '-999999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        const successful = document.execCommand('copy');
        if (successful) {
            if (window.notyf) {
                window.notyf.success('메시지가 복사되었습니다.');
            }
        } else {
            if (window.notyf) {
                window.notyf.error('복사에 실패했습니다.');
            }
        }
    } catch (error) {
        console.error('Fallback copy failed:', error);
        if (window.notyf) {
            window.notyf.error('복사에 실패했습니다.');
        }
    } finally {
        document.body.removeChild(textArea);
    }
}

// Like message
async function likeMessage(messageId) {
    try {
        const response = await fetch(`/chat/api/messages/${messageId}/feedback/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                feedback_type: 'L'
            }),
        });
        
        if (response.ok) {
            const data = await response.json();
            // Handle success
            if (window.notyf) {
                if (data.action === 'removed') {
                    window.notyf.success('좋아요가 취소되었습니다.');
                } else {
                    window.notyf.success('좋아요를 눌렀습니다.');
                }
            }
        } else {
            const errorData = await response.json();
            console.error('Error liking message:', errorData);
            if (window.notyf) {
                window.notyf.error(errorData.error || '좋아요 처리 중 오류가 발생했습니다.');
            }
        }
    } catch (error) {
        console.error('Error liking message:', error);
        if (window.notyf) {
            window.notyf.error('좋아요 처리 중 오류가 발생했습니다.');
        }
    }
}

// Dislike message
async function dislikeMessage(messageId) {
    try {
        const response = await fetch(`/chat/api/messages/${messageId}/feedback/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                feedback_type: 'D'
            }),
        });
        
        if (response.ok) {
            const data = await response.json();
            // Handle success
            if (window.notyf) {
                if (data.action === 'removed') {
                    window.notyf.success('싫어요가 취소되었습니다.');
                } else {
                    window.notyf.success('싫어요를 눌렀습니다.');
                }
            }
        } else {
            const errorData = await response.json();
            console.error('Error disliking message:', errorData);
            if (window.notyf) {
                window.notyf.error(errorData.error || '싫어요 처리 중 오류가 발생했습니다.');
            }
        }
    } catch (error) {
        console.error('Error disliking message:', error);
        if (window.notyf) {
            window.notyf.error('싫어요 처리 중 오류가 발생했습니다.');
        }
    }
}

// Save to note
function saveToNote(messageId) {
    showSaveToNotesModal = true;
    const normalizedId = String(messageId);
    const targetMessage = messages.find((msg, idx) => {
        const candidateId = msg.message_id != null ? String(msg.message_id) :
            msg.id != null ? String(msg.id) : String(idx);
        return candidateId === normalizedId;
    });
    // const previewText = targetMessage?.content
    //     ? targetMessage.content.replace(/\s+/g, ' ').trim()
    //     : '';
    // const description = previewText
    //     ? `선택한 응답: "${previewText.length > 80 ? `${previewText.slice(0, 80)}…` : previewText}"`
    //     : '결과를 노트에 저장하세요';

    if (window.SaveToNoteModal && window.SaveToNoteModal.open) {
        window.SaveToNoteModal.open({
            title: '노트에 저장',
            // description,
            messageId: normalizedId,
            onSave: (option, noteName) => {
                if (window.notyf) {
                    if (option === 'existing') {
                        window.notyf.success(`"${noteName}" 노트에 저장했습니다.`);
                    } else {
                        window.notyf.success(`"${noteName}" 노트를 생성하고 저장했습니다.`);
                    }
                }
            }
        });
    } else if (window.Modal && window.Modal.open) {
        window.Modal.open('saveToNoteModal');
    } else {
        // Fallback navigation
        window.location.href = `/notes/create/?message_id=${normalizedId}`;
    }
}

// Show graph summary
function showGraphSummary(messageId) {
    showGraphSummaryModal = true;
    
    // Find message content from current messages
    let messageContent = null;
    
    // Try to find from messages array (from loadChat)
    if (typeof messages !== 'undefined' && Array.isArray(messages)) {
        const message = messages.find(msg => 
            (msg.message_id || msg.id) == messageId || msg.message_sid == messageId
        );
        if (message) {
            messageContent = message.content || '';
        }
    }
    
    // If message not found, try to find from DOM
    if (!messageContent) {
        const messageElement = document.querySelector(`[data-message-id="${messageId}"]`)?.closest('.message-item');
        if (messageElement) {
            const contentElement = messageElement.querySelector('.markdown-content, .message-content-assistant, .message-bubble-assistant');
            if (contentElement) {
                // Try to get text content (strip HTML)
                messageContent = contentElement.textContent || contentElement.innerText || '';
            }
        }
    }
    
    if (window.GraphSummaryModal && window.GraphSummaryModal.open) {
        window.GraphSummaryModal.open(messageId, messageContent);
    } else if (window.Modal && window.Modal.open) {
        window.Modal.open('graphSummaryModal');
        // If GraphSummaryModal is not available, trigger load via event
        setTimeout(() => {
            const event = new CustomEvent('modal:open', {
                detail: { 
                    modalId: 'graphSummaryModal', 
                    messageId: messageId,
                    messageContent: messageContent 
                }
            });
            document.dispatchEvent(event);
        }, 100);
    }
}

// Attach reference handlers
function attachReferenceHandlers() {
    const bookmarkBtns = referencesList ? referencesList.querySelectorAll('.reference-bookmark-btn') : null;
    if (bookmarkBtns) {
        bookmarkBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const referenceId = btn.getAttribute('data-reference-id');
                toggleReferenceBookmark(referenceId, btn);
            });
        });
    }

    if (saveReferencesBtn) {
        saveReferencesBtn.addEventListener('click', handleSaveReferences);
    }
}

// Toggle reference bookmark
function toggleReferenceBookmark(referenceId, btn) {
    selectedReferenceId = referenceId;
    showBookmarkModal = true;
    if (window.Modal && window.Modal.open) {
        window.Modal.open('bookmarkModal');
    }
}

// Handle save references
function handleSaveReferences() {
    showReferenceSelectionModal = true;
    
    // Get current chat ID
    const chatId = activeChatId;
    
    console.log('[Chat] handleSaveReferences - activeChatId:', chatId);
    
    if (!chatId) {
        console.warn('[Chat] No chat ID available to load references');
        if (window.notyf) {
            window.notyf.error('채팅을 먼저 선택해주세요.');
        }
        return;
    }
    
    // Open reference selection modal with chat ID
    if (window.ReferenceSelectionModal && window.ReferenceSelectionModal.open) {
        console.log('[Chat] Opening ReferenceSelectionModal with chatId:', chatId);
        window.ReferenceSelectionModal.open(chatId);
    } else if (window.Modal && window.Modal.open) {
        console.log('[Chat] Fallback to window.Modal.open');
        window.Modal.open('referenceSelectionModal');
    } else {
        console.error('[Chat] Reference selection modal not available');
    }
}

// Attach plus button handlers
function attachPlusButtonHandlers() {
    if (attachBtn) {
        attachBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            showPlusModal = !showPlusModal;
            if (plusDropdown) {
                plusDropdown.style.display = showPlusModal ? 'block' : 'none';
            }
        });
    }

    if (attachBtnBottom) {
        attachBtnBottom.addEventListener('click', (e) => {
            e.stopPropagation();
            showPlusModal = !showPlusModal;
            if (plusDropdownBottom) {
                plusDropdownBottom.style.display = showPlusModal ? 'block' : 'none';
            }
        });
    }

    // Plus dropdown item handlers
    const plusDropdownItems = document.querySelectorAll('.plus-dropdown-item');
    plusDropdownItems.forEach(item => {
        item.addEventListener('click', (e) => {
            const action = item.getAttribute('data-action');
            handlePlusAction(action);
            showPlusModal = false;
            if (plusDropdown) plusDropdown.style.display = 'none';
            if (plusDropdownBottom) plusDropdownBottom.style.display = 'none';
        });
    });
}

// Handle plus action
function handlePlusAction(action) {
    switch (action) {
        case 'add-image':
            // Trigger file input click
            if (fileInput) {
                fileInput.click();
            } else if (fileInputBottom) {
                fileInputBottom.click();
            }
            break;
        case 'add-table':
            // Open table modal - Debug logging
            console.log('[Chat] add-table clicked');
            console.log('[Chat] window.TableModal:', window.TableModal);
            console.log('[Chat] typeof window.TableModal:', typeof window.TableModal);
            if (window.TableModal) {
                console.log('[Chat] TableModal.open:', window.TableModal.open);
                console.log('[Chat] typeof TableModal.open:', typeof window.TableModal.open);
            }
            
            if (window.TableModal && typeof window.TableModal.open === 'function') {
                console.log('[Chat] Calling TableModal.open()...');
                window.TableModal.open();
            } else {
                console.error('[Chat] TableModal is not available!');
                console.error('[Chat] Available window properties with "Modal":', 
                    Object.keys(window).filter(k => k.includes('Modal')));
            }
            break;
        case 'add-experiment':
            // Open experiment result modal
            console.log('[Chat] add-experiment clicked');
            console.log('[Chat] window.ExperimentResultModal:', window.ExperimentResultModal);
            
            if (window.ExperimentResultModal && typeof window.ExperimentResultModal.open === 'function') {
                console.log('[Chat] Calling ExperimentResultModal.open()...');
                window.ExperimentResultModal.open();
            } else {
                console.error('[Chat] ExperimentResultModal is not available!');
            }
            break;
    }
}

// Handle image file selection
function handleImageSelect(e) {
    const files = e.target.files;
    if (files && files.length > 0) {
        Array.from(files).forEach(file => {
            if (file.type.startsWith('image/')) {
                const imageData = {
                    id: Date.now() + Math.random(),
                    name: file.name,
                    size: file.size,
                    url: URL.createObjectURL(file),
                    file: file
                };
                attachedImages.push(imageData);
            }
        });
        renderAttachedItems();
        
        // Show success message (you can use toast library if available)
        console.log(`${files.length}개의 이미지가 첨부되었습니다`);
    }
    
    // Reset input
    if (e.target) {
        e.target.value = '';
    }
}

// Handle table attached event
function handleTableAttached(event) {
    const tableInfo = event.detail;
    attachedTables.push(tableInfo);
    renderAttachedItems();
    console.log('표가 첨부되었습니다');
}

// Handle experiment attached event
function handleExperimentAttached(event) {
    const experimentData = event.detail;
    attachedExperiments.push(experimentData);
    renderAttachedItems();
    console.log('실험 결과가 첨부되었습니다');
}

// Render attached items
function renderAttachedItems() {
    // Find attached items container or create one
    let attachedContainer = document.getElementById('attachedItems');
    if (!attachedContainer) {
        // Create container if it doesn't exist
        const inputWrapper = document.querySelector('.input-wrapper');
        if (inputWrapper) {
            attachedContainer = document.createElement('div');
            attachedContainer.id = 'attachedItems';
            attachedContainer.className = 'attached-items';
            inputWrapper.insertBefore(attachedContainer, inputWrapper.firstChild);
        }
    }
    
    if (!attachedContainer) return;
    
    const hasAttachments = attachedImages.length > 0 || attachedTables.length > 0 || attachedExperiments.length > 0;
    
    if (!hasAttachments) {
        attachedContainer.style.display = 'none';
        return;
    }
    
    attachedContainer.style.display = 'flex';
    attachedContainer.style.flexWrap = 'wrap';
    attachedContainer.style.gap = '0.5rem';
    attachedContainer.style.marginBottom = '0.5rem';
    attachedContainer.style.padding = '0.5rem';
    
    let html = '';
    
    // Attached Images
    attachedImages.forEach((img, index) => {
        html += `
            <div class="attached-item attached-image" data-index="${index}">
                <i class="fa-solid fa-image"></i>
                <span>${escapeHtml(img.name)}</span>
                <button class="attached-item-remove" data-type="image" data-index="${index}">
                    <i class="fa-solid fa-times"></i>
                </button>
            </div>
        `;
    });
    
    // Attached Tables
    attachedTables.forEach((table, index) => {
        html += `
            <div class="attached-item attached-table" data-index="${index}">
                <i class="fa-solid fa-table"></i>
                <span>표 (${table.rows}x${table.cols})</span>
                <button class="attached-item-remove" data-type="table" data-index="${index}">
                    <i class="fa-solid fa-times"></i>
                </button>
            </div>
        `;
    });
    
    // Attached Experiments
    attachedExperiments.forEach((exp, index) => {
        html += `
            <div class="attached-item attached-experiment" data-index="${index}">
                <i class="fa-solid fa-flask"></i>
                <span>${escapeHtml(exp.resultName)} (${escapeHtml(exp.resultType)})</span>
                <button class="attached-item-remove" data-type="experiment" data-index="${index}">
                    <i class="fa-solid fa-times"></i>
                </button>
            </div>
        `;
    });
    
    attachedContainer.innerHTML = html;
    
    // Attach remove handlers
    const removeBtns = attachedContainer.querySelectorAll('.attached-item-remove');
    removeBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const type = btn.getAttribute('data-type');
            const index = parseInt(btn.getAttribute('data-index'));
            removeAttachedItem(type, index);
        });
    });
}

// Remove attached item
function removeAttachedItem(type, index) {
    switch (type) {
        case 'image':
            if (attachedImages[index] && attachedImages[index].url) {
                URL.revokeObjectURL(attachedImages[index].url);
            }
            attachedImages.splice(index, 1);
            break;
        case 'table':
            attachedTables.splice(index, 1);
            break;
        case 'experiment':
            attachedExperiments.splice(index, 1);
            break;
    }
    renderAttachedItems();
}

// Filter tooltip은 이제 Shoelace tooltip으로 자동 처리됨
// 별도의 JavaScript 핸들러가 필요 없음

// Attach click outside handlers
function attachClickOutsideHandlers() {
    document.addEventListener('click', (e) => {
        // Close plus dropdown
        if (showPlusModal) {
            if (plusDropdown && !plusDropdown.contains(e.target) && attachBtn && !attachBtn.contains(e.target)) {
                showPlusModal = false;
                plusDropdown.style.display = 'none';
            }
            if (plusDropdownBottom && !plusDropdownBottom.contains(e.target) && attachBtnBottom && !attachBtnBottom.contains(e.target)) {
                showPlusModal = false;
                plusDropdownBottom.style.display = 'none';
            }
        }

        // Close recommendations
        if (showRecommendations) {
            const recommendationsDropdownEl = document.getElementById('recommendationsDropdown');
            if (recommendationsDropdownEl && !recommendationsDropdownEl.contains(e.target)) {
                const inputFocused = (chatInputField && chatInputField === document.activeElement) || 
                                     (chatInputFieldBottom && chatInputFieldBottom === document.activeElement);
                if (!inputFocused) {
                    closeRecommendations();
                }
            }
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
    // Try to get from meta tag
    const metaTag = document.querySelector('meta[name=csrf-token]');
    if (metaTag) {
        return metaTag.getAttribute('content');
    }
    return '';
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initChatAI);
} else {
    initChatAI();
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.ChatAIPage = {
        initChatAI,
        handleSend,
        loadChat,
        renderMessages,
        renderReferences,
        handleNewChat,
        handleChatSelect,
        handleChatMenuClick,
        chatList,
        chatMessages: chatMessagesData,
    };
}
