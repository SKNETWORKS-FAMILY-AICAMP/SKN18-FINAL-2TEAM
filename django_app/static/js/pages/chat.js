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
let activeSectionFilter = null; // 'favorites', 'archived', or null
let messages = [];
let references = [];
let allReferences = []; // 전체 참고문헌 (메시지별 그룹화용)
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
let isComposing = false; // IME 조합 상태 (macOS 한글 입력 중복 전송 방지)
let currentTypingAnimation = null; // 현재 실행 중인 타이핑 애니메이션 제어

let chatList = [];

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
        allReferences = [];
        renderReferences();
    }

    // Event listeners
    if (chatInputField) {
        chatInputField.addEventListener('input', handleInputChange);
        chatInputField.addEventListener('focus', handleInputFocus);
        chatInputField.addEventListener('keydown', handleInputKeydown);
        // macOS 한글 IME 중복 전송 방지
        chatInputField.addEventListener('compositionstart', () => {
            isComposing = true;
        });
        chatInputField.addEventListener('compositionend', () => {
            isComposing = false;
        });
    }

    if (chatInputFieldBottom) {
        chatInputFieldBottom.addEventListener('input', handleInputChange);
        chatInputFieldBottom.addEventListener('keydown', handleInputKeydown);
        // macOS 한글 IME 중복 전송 방지
        chatInputFieldBottom.addEventListener('compositionstart', () => {
            isComposing = true;
        });
        chatInputFieldBottom.addEventListener('compositionend', () => {
            isComposing = false;
        });
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

    // Section buttons (Favorites, Archived)
    const sectionBtns = document.querySelectorAll('[data-section]');
    sectionBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopImmediatePropagation(); // Prevent subsidebar.js handler from firing
            const section = btn.getAttribute('data-section');
            handleSectionSelect(section);
            // Remove focus to prevent blue outline
            e.currentTarget.blur();
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
    // macOS 한글 입력 시 IME 조합 중에는 Enter를 무시 (중복 전송 방지)
    if (e.key === 'Enter' && !e.shiftKey && !isComposing) {
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
    
    // 타이핑 애니메이션 중이면 즉시 완료
    if (currentTypingAnimation) {
        skipTypingAnimation();
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

    // 새로운 질문을 보낼 때 이전 레퍼런스 모달 숨기기
    references = [];
    if (referencesSidebar) {
        referencesSidebar.style.display = 'none';
    }
    renderReferences();

    // 목적: AI 응답 대기 중 사용자에게 로딩 상태 표시
    // AI 로딩 메시지 추가 (애니메이션 효과와 함께 표시됨)
    const loadingMessage = {
        role: 'assistant',
        content: 'AI가 응답을 작성하는 중입니다',
        is_loading: true,  // 로딩 메시지 식별용 플래그
    };
    messages.push(loadingMessage);
    renderMessages();

    // Send to API - 랭그래프의 응답을 화면으로 쏴줌
    try {
        // 목적: 새 채팅과 기존 채팅 모두 처리 가능한 통합 엔드포인트 사용
        const apiUrl = activeChatId
            ? `/chat/api/chats/${activeChatId}/messages/`  // 기존 채팅에 메시지 추가
            : '/chat/api/chats/messages/';  // 새 채팅 생성

        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                content: input,
            }),
        });

        if (response.ok) {
            const data = await response.json();

            // 목적: AI 응답을 받았으므로 로딩 메시지 제거
            messages = messages.filter(m => !m.is_loading);

            // 목적: 새 채팅 생성 시 chat_id 저장 및 URL 업데이트
            if (!activeChatId && data.chat_id) {
                activeChatId = data.chat_id;
                // URL을 업데이트하여 새로고침해도 같은 채팅 유지
                window.history.pushState({}, '', `/chat/?id=${activeChatId}`);
                // 서브사이드바에 새 채팅 표시
                loadChatList();
            }

            // 목적: 서버에서 받은 메시지(사용자 + AI)로 로컬 메시지 업데이트
            if (data.messages && Array.isArray(data.messages) && data.messages.length >= 2) {
                // 마지막 사용자 메시지를 서버 응답으로 교체 (message_id 포함)
                messages[messages.length - 1] = {
                    role: data.messages[0].role,
                    content: data.messages[0].content,
                    message_id: data.messages[0].id,
                    timestamp: data.messages[0].created_at,
                };

                // AI 응답 메시지 추가 (타이핑 애니메이션용으로 빈 상태로 시작)
                const aiContent = data.messages[1].content;
                const assistantMessage = {
                    role: data.messages[1].role,
                    content: '',  // 타이핑 애니메이션으로 채워질 예정
                    message_id: data.messages[1].id,
                    timestamp: data.messages[1].created_at,
                };
                messages.push(assistantMessage);
                
                // 참고문헌을 먼저 추가 (타이핑 애니메이션 중에도 보이도록)
                if (data.references && Array.isArray(data.references)) {
                    const newRefs = data.references.map(ref => ({
                        ...ref,
                        message_id: data.messages[1].id
                    }));
                    allReferences = [...allReferences, ...newRefs];
                }
                
                // 타이핑 애니메이션 시작 (비동기)
                const messageIndex = messages.length - 1;
                typeWriterEffect(aiContent, messageIndex, 40).then(() => {
                    // 타이핑 완료 후 참고문헌 업데이트
                    updateVisibleReferences();
                });
                
                // 일단 렌더링 (빈 메시지, 레퍼런스는 스트리밍 완료 후 표시)
                renderMessages();
            } else if (data.error) {
                // AI generation failed, but user message was saved
                console.error('AI generation error:', data.error);
                renderMessages();
            }
        } else {
            // 목적: 에러 발생 시에도 로딩 메시지 제거
            messages = messages.filter(m => !m.is_loading);

            const error = await response.json();
            console.error('Error sending message:', error);

            // Show error message
            const errorMessage = {
                role: 'assistant',
                content: error.error || '죄송합니다. 오류가 발생했습니다. 다시 시도해주세요.',
                is_error: true,
            };
            messages.push(errorMessage);
            renderMessages();
        }
    } catch (error) {
        // 목적: 네트워크 오류 시에도 로딩 메시지 제거
        messages = messages.filter(m => !m.is_loading);

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
            
            // Format references (전체 참고문헌 저장)
            allReferences = (data.references || []).map(ref => ({
                id: ref.id,
                ref_id: ref.ref_id,  // 참고문헌 번호 (UI 표시용)
                message_id: ref.message_id,  // 메시지 ID (필터링용)
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
            updateVisibleReferences(); // 스크롤 기반 참고문헌 업데이트
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
/**
 * 타이핑 애니메이션 효과로 메시지를 점진적으로 표시
 * @param {string} fullText - 전체 텍스트
 * @param {number} messageIndex - 메시지 배열 인덱스
 * @param {number} speed - 타이핑 속도 (밀리초, 기본값: 20ms)
 * @returns {Promise<void>}
 */
async function typeWriterEffect(fullText, messageIndex, speed = 20) {
    return new Promise((resolve) => {
        let currentIndex = 0;
        const message = messages[messageIndex];
        
        // 이미 타이핑 중이면 중단
        if (currentTypingAnimation) {
            clearInterval(currentTypingAnimation);
        }
        
        // 타이핑 애니메이션 시작
        message.is_typing = true;
        message.content = '';
        message.fullText = fullText; // 전체 텍스트 저장 (중단 시 사용)
        renderMessages();
        
        currentTypingAnimation = setInterval(() => {
            if (currentIndex < fullText.length) {
                // 한 글자씩 추가 (한글 등 유니코드 문자 처리)
                const char = fullText[currentIndex];
                message.content += char;
                currentIndex++;
                
                // 메시지만 업데이트 (전체 렌더링 비용 절감)
                renderMessages();
                
                // 스크롤을 맨 아래로 자동 이동
                if (messagesView) {
                    messagesView.scrollTop = messagesView.scrollHeight;
                }
            } else {
                // 타이핑 완료
                clearInterval(currentTypingAnimation);
                currentTypingAnimation = null;
                message.is_typing = false;
                delete message.fullText;
                renderMessages();
                resolve();
            }
        }, speed);
    });
}

/**
 * 타이핑 애니메이션 중단 (즉시 전체 텍스트 표시)
 */
function stopTypingAnimation() {
    if (currentTypingAnimation) {
        clearInterval(currentTypingAnimation);
        currentTypingAnimation = null;
        
        // 타이핑 중인 메시지 찾아서 완료 처리
        const typingMessage = messages.find(m => m.is_typing);
        if (typingMessage) {
            typingMessage.is_typing = false;
            
            // 전체 텍스트로 즉시 업데이트
            if (typingMessage.fullText) {
                typingMessage.content = typingMessage.fullText;
                delete typingMessage.fullText;
            }
            
            renderMessages();
        }
    }
}

/**
 * 타이핑 애니메이션 스킵 (ESC 키 또는 클릭으로 즉시 완료)
 */
function skipTypingAnimation() {
    stopTypingAnimation();
    
    // 참고문헌도 즉시 업데이트
    updateVisibleReferences();
}

function renderMessages() {
    if (!messagesView) return;

    messagesView.innerHTML = messages.map((msg, index) => {
        if (msg.role === 'user') {
            return `
                <div class="message-item" data-message-id="${msg.message_id || ''}">
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
            // 목적: AI 응답 대기 중 로딩 상태를 애니메이션과 함께 표시
            if (msg.is_loading) {
                return `
                    <div class="message-item" data-message-id="${msg.message_id || ''}">
                        <div class="message-assistant">
                            <div class="message-avatar assistant-avatar">AI</div>
                            <div class="message-content-assistant message-loading">
                                <div class="markdown-content">
                                    <p>${escapeHtml(msg.content)}<span class="typing-indicator"><span>.</span><span>.</span><span>.</span></span></p>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            }
            
            // 타이핑 애니메이션 중: 마크다운 렌더링
            if (msg.is_typing) {
                const renderedContent = window.MarkdownUtils ? window.MarkdownUtils.render(msg.content || '') : escapeHtml(msg.content);
                return `
                    <div class="message-item" data-message-id="${msg.message_id || ''}">
                        <div class="message-assistant">
                            <div class="message-avatar assistant-avatar">AI</div>
                            <div class="message-content-assistant">
                                <div class="markdown-content">
                                    ${renderedContent}
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            }

            // Check if this message has paper_graphs
            const hasPaperGraphs = msg.paper_graphs && Array.isArray(msg.paper_graphs) && msg.paper_graphs.length > 0;
            const showPaperGraphBtn = hasPaperGraphs;

            // Check if this is the last message for experiment button
            const isLastMessage = index === messages.length - 1;
            const showExperimentBtn = activeChatId === 2 && isLastMessage;

            return `
                <div class="message-item" data-message-id="${msg.message_id || ''}">
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
                                    <button class="action-btn" title="복사" data-action="copy" data-message-index="${index}">
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
    // 스트리밍 중일 때는 레퍼런스 사이드바 숨기기
    if (referencesSidebar) {
        // 스트리밍 중이면 레퍼런스 숨김
        if (currentTypingAnimation) {
            referencesSidebar.style.display = 'none';
        } else if (messages.length > 0 && references.length > 0) {
            referencesSidebar.style.display = 'flex';
        } else {
            referencesSidebar.style.display = 'none';
        }
    }

    // Re-attach handlers
    attachMessageActionHandlers();

    // Attach scroll event listener for dynamic reference updates
    if (chatMessagesList) {
        // Remove existing listener to avoid duplicates
        chatMessagesList.removeEventListener('scroll', handleMessagesScroll);
        chatMessagesList.addEventListener('scroll', handleMessagesScroll);
    }
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

// Handle section select (Favorites, Archived) - with toggle
async function handleSectionSelect(section) {
    try {
        console.log('handleSectionSelect called with section:', section);
        console.log('Current activeSectionFilter:', activeSectionFilter);

        // Toggle logic: if same section clicked, deactivate it
        if (activeSectionFilter === section) {
            activeSectionFilter = null;
            console.log('Deactivating section filter, loading all chats');
        } else {
            activeSectionFilter = section;
            console.log('Activating section filter:', section);
        }

        console.log('New activeSectionFilter:', activeSectionFilter);

        // Update button styles IMMEDIATELY before fetch
        updateSectionButtonStyles();

        // Fetch chat list
        let url = '/chat/api/chats/';
        if (activeSectionFilter) {
            url += `?section=${activeSectionFilter}`;
        }

        const response = await fetch(url);
        if (response.ok) {
            const data = await response.json();
            chatList = data.items || [];

            // Render chat list
            if (window.SubSidebarComponent && window.SubSidebarComponent.renderItems) {
                window.SubSidebarComponent.renderItems(chatList);
            }

            // Update section counts from server data
            if (data.counts) {
                updateSectionCounts(data.counts);
            }

            // Update button styles AGAIN after render to ensure it sticks
            setTimeout(() => {
                updateSectionButtonStyles();
            }, 10);
        }
    } catch (error) {
        console.error('Error loading section:', error);
    }
}

// Update section button styles based on activeSectionFilter
function updateSectionButtonStyles() {
    console.log('updateSectionButtonStyles called, activeSectionFilter:', activeSectionFilter);
    const sectionBtns = document.querySelectorAll('[data-section]');
    console.log('Found section buttons:', sectionBtns.length);
    sectionBtns.forEach(btn => {
        const section = btn.getAttribute('data-section');
        if (section === activeSectionFilter) {
            console.log('Adding active class to section:', section);
            btn.classList.add('active');
            btn.setAttribute('data-active', 'true'); // Also set data attribute for persistence
        } else {
            console.log('Removing active class from section:', section);
            btn.classList.remove('active');
            btn.removeAttribute('data-active');
        }
    });

    // Force a reflow to ensure styles are applied
    sectionBtns.forEach(btn => {
        void btn.offsetHeight; // Trigger reflow
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

    // Clear references
    references = [];
    allReferences = [];
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

    // Get current chat state
    const chat = chatList.find(c => c.id === chatId);
    const isFavorite = chat && chat.favorite === 'Y';

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
        <button class="chat-menu-item" data-action="favorite">
            <span>📌</span>
            <span>${isFavorite ? 'Unfavorite' : 'Favorite'}</span>
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
        case 'favorite':
            toggleFavorite(chatId);
            break;
        case 'edit':
            editingChatId = chatId;
            const chat = chatList.find(c => c.id === chatId);
            editingTitle = chat ? chat.title : '';
            renderChatEdit(chatId);
            break;
        case 'archive':
            toggleArchive(chatId);
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
                        // Call delete API
                        deleteChat(chatId);
                    }
                });
            } else {
                // Fallback to confirm if SweetAlert2 is not available
                if (confirm('삭제 하시겠습니까?')) {
                    deleteChat(chatId);
                }
            }
            break;
    }
}

// Delete chat function
async function deleteChat(chatId) {
    try {
        const response = await fetch(`/chat/api/chats/${chatId}/delete/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        const data = await response.json();

        if (data.success) {
            // Remove from local list
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
        } else {
            throw new Error(data.error || '삭제 실패');
        }
    } catch (error) {
        console.error('Delete chat error:', error);
        if (window.notyf) {
            window.notyf.error('채팅 삭제 중 오류가 발생했습니다.');
        }
    }
}

// Toggle favorite status
async function toggleFavorite(chatId) {
    try {
        // Close menu
        openMenuId = null;
        document.querySelectorAll('.chat-menu-dropdown').forEach(menu => menu.remove());

        const response = await fetch(`/chat/api/chats/${chatId}/favorite/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
        });

        if (response.ok) {
            const data = await response.json();

            // Update chat list item UI
            const chat = chatList.find(c => c.id === chatId);
            if (chat) {
                chat.favorite = data.favorite;
            }

            // Reload chat list to reflect favorite status
            await loadChatList();

            // Show notification
            if (window.notyf) {
                window.notyf.success(data.message);
            }
        } else {
            const error = await response.json();
            if (window.notyf) {
                window.notyf.error(error.error || 'Favorite 상태 변경에 실패했습니다.');
            }
        }
    } catch (error) {
        console.error('Error toggling favorite:', error);
        if (window.notyf) {
            window.notyf.error('Favorite 상태 변경 중 오류가 발생했습니다.');
        }
    }
}

// Toggle archive status
async function toggleArchive(chatId) {
    try {
        // Close menu
        openMenuId = null;
        document.querySelectorAll('.chat-menu-dropdown').forEach(menu => menu.remove());

        const response = await fetch(`/chat/api/chats/${chatId}/archive/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
        });

        if (response.ok) {
            const data = await response.json();

            // Update chat list item UI
            const chat = chatList.find(c => c.id === chatId);
            if (chat) {
                chat.archived = data.archived === 'Y';
            }

            // Reload chat list to reflect archived status
            await loadChatList();

            // Show notification
            if (window.notyf) {
                window.notyf.success(data.message);
            }
        } else {
            const error = await response.json();
            if (window.notyf) {
                window.notyf.error(error.error || 'Archive 상태 변경에 실패했습니다.');
            }
        }
    } catch (error) {
        console.error('Error toggling archive:', error);
        if (window.notyf) {
            window.notyf.error('Archive 상태 변경 중 오류가 발생했습니다.');
        }
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
async function handleSaveChatTitle(chatId) {
    const input = document.getElementById(`chatEditInput${chatId}`);
    if (!input) return;

    const newTitle = input.value.trim();
    if (!newTitle) {
        if (window.notyf) {
            window.notyf.error('제목을 입력해주세요.');
        }
        return;
    }

    try {
        // Send PATCH request to backend
        const response = await fetch(`/chat/api/chats/${chatId}/title/`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({ title: newTitle })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || '제목 저장에 실패했습니다.');
        }

        const data = await response.json();

        // Update chat list with response data
        const chat = chatList.find(c => c.id === chatId);
        if (chat) {
            chat.title = data.title;
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
    } catch (error) {
        console.error('Error saving chat title:', error);
        if (window.notyf) {
            window.notyf.error(error.message || '제목 저장 중 오류가 발생했습니다.');
        }
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
        // Build URL with active section filter if any
        let url = '/chat/api/chats/';
        if (activeSectionFilter) {
            url += `?section=${activeSectionFilter}`;
        }

        const response = await fetch(url);
        if (response.ok) {
            const data = await response.json();
            chatList = data.items || [];

            // Render chat list
            if (window.SubSidebarComponent && window.SubSidebarComponent.renderItems) {
                window.SubSidebarComponent.renderItems(chatList);
            }

            // Update section counts from server data
            if (data.counts) {
                updateSectionCounts(data.counts);
            }

            // Update section button styles to reflect current filter
            // Use setTimeout to ensure DOM has been updated
            setTimeout(() => {
                updateSectionButtonStyles();
            }, 0);
        }
    } catch (error) {
        console.error('Error loading chat list:', error);
    }
}

// Update section counts (Favorites, Archived)
function updateSectionCounts(counts) {
    console.log('Updating section counts:', counts);

    // Update favorites count
    const favoritesCountEl = document.querySelector('[data-section="favorites"] .section-count');
    if (favoritesCountEl && counts) {
        favoritesCountEl.textContent = counts.favorites || 0;
    }

    // Update archived count
    const archivedCountEl = document.querySelector('[data-section="archived"] .section-count');
    if (archivedCountEl && counts) {
        archivedCountEl.textContent = counts.archived || 0;
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
        // 웹서치 참고문헌 여부 확인
        const isWebSource = ref.source === 'Web';
        const sourceIcon = isWebSource ? '<i class="fas fa-globe"></i> ' : '';

        return `
            <div class="reference-item" data-reference-id="${ref.id}">
                <button class="reference-bookmark-btn" data-reference-id="${ref.id}" title="북마크에 저장">
                    <i class="fas fa-bookmark"></i>
                </button>
                <div class="reference-content">
                    <div class="reference-number">${ref.ref_id || ref.id}</div>
                    <div class="reference-details">
                        <div class="reference-meta">
                            <span class="reference-source">${sourceIcon}${escapeHtml(ref.source || 'Unknown')}</span>
                            ${ref.badge ? `<span class="reference-badge">${escapeHtml(ref.badge)}</span>` : ''}
                        </div>
                        <h3 class="reference-title">${escapeHtml(ref.title)}</h3>
                        ${ref.description ? `<p class="reference-description">${escapeHtml(ref.description)}</p>` : ''}
                        <div class="reference-info">
                            ${ref.link ? `
                            <div class="reference-info-item">
                                <i class="fas fa-link"></i>
                                <a href="${escapeHtml(ref.link)}" target="_blank" rel="noopener noreferrer" class="reference-link">${escapeHtml(ref.link)}</a>
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
    console.log('Attaching handlers to', actionBtns?.length || 0, 'buttons');
    if (actionBtns) {
        actionBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                const action = btn.getAttribute('data-action');
                // For copy action, use index; for others, use message_id
                const messageId = btn.getAttribute('data-message-index') || btn.getAttribute('data-message-id');
                console.log('Button clicked:', { action, messageId, btn });
                handleMessageAction(action, messageId);
            });
        });
    }
}

// Handle message action
function handleMessageAction(action, messageId) {
    console.log('handleMessageAction called:', { action, messageId, messagesLength: messages.length });
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
        default:
            console.error('Unknown action:', action);
    }
}

// Copy message
function copyMessage(messageIdOrIndex) {
    console.log('copyMessage called with:', messageIdOrIndex, 'type:', typeof messageIdOrIndex);

    // Parse as index (should always be a number or string number)
    const messageIndex = parseInt(messageIdOrIndex);

    if (isNaN(messageIndex) || messageIndex < 0 || messageIndex >= messages.length) {
        console.error('Invalid message index:', messageIdOrIndex, 'Available messages:', messages.length);
        if (window.notyf) {
            window.notyf.error('복사할 메시지를 찾을 수 없습니다.');
        }
        return;
    }

    const message = messages[messageIndex];

    if (!message || !message.content) {
        console.error('Message has no content:', message);
        if (window.notyf) {
            window.notyf.error('복사할 메시지가 없습니다.');
        }
        return;
    }

    // Get text content - if it's markdown, try to get plain text from rendered element
    let textToCopy = message.content;

    // Try to get plain text from rendered markdown element if available
    const messageElement = messagesView?.querySelector(`[data-message-index="${messageIndex}"]`);
    if (messageElement) {
        // Get text content from the rendered markdown element
        const textContent = messageElement.textContent || messageElement.innerText;
        if (textContent && textContent.trim()) {
            textToCopy = textContent.trim();
        }
    }

    console.log('Copying message:', { index: messageIndex, contentLength: textToCopy.length, preview: textToCopy.substring(0, 50) + '...' });

    // Use Clipboard API
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(textToCopy).then(() => {
            console.log('Copy successful');
            if (window.notyf) {
                window.notyf.success('메시지가 복사되었습니다.');
            }
        }).catch((error) => {
            console.error('Clipboard API failed:', error);
            // Fallback to old method
            fallbackCopyTextToClipboard(textToCopy);
        });
    } else {
        console.log('Clipboard API not available, using fallback');
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
        
        // 타이핑 중인 메시지 클릭 시 애니메이션 스킵
        if (currentTypingAnimation && e.target.closest('.message-item')) {
            const typingMessage = messages.find(m => m.is_typing);
            if (typingMessage) {
                skipTypingAnimation();
            }
        }
    });
    
    // ESC 키로 타이핑 애니메이션 스킵
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && currentTypingAnimation) {
            skipTypingAnimation();
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

// Handle messages scroll to update visible references
function handleMessagesScroll() {
    updateVisibleReferences();
}

// Update visible references based on currently visible messages
function updateVisibleReferences() {
    if (!chatMessagesList || !allReferences || allReferences.length === 0) {
        // No references to show
        references = [];
        renderReferences();
        return;
    }

    // Get AI message items only (exclude user messages)
    const aiMessageItems = chatMessagesList.querySelectorAll('.message-item .message-assistant');

    if (aiMessageItems.length === 0) {
        references = [];
        renderReferences();
        return;
    }

    // Define target area in viewport (30% - 70% from top)
    const container = chatMessagesList;
    const containerRect = container.getBoundingClientRect();
    const targetAreaTop = containerRect.top + containerRect.height * 0.3;
    const targetAreaBottom = containerRect.top + containerRect.height * 0.7;
    const targetAreaCenter = (targetAreaTop + targetAreaBottom) / 2;

    // Find the closest AI message to the target area center
    let closestMessageId = null;
    let closestDistance = Infinity;

    aiMessageItems.forEach(aiMsg => {
        const messageItem = aiMsg.closest('.message-item');
        const messageId = messageItem?.getAttribute('data-message-id');

        if (!messageId) return;

        const rect = messageItem.getBoundingClientRect();
        const messageCenter = (rect.top + rect.bottom) / 2;

        // Check if message is visible in viewport
        if (rect.bottom > containerRect.top && rect.top < containerRect.bottom) {
            // Calculate distance from target area center
            const distance = Math.abs(messageCenter - targetAreaCenter);

            if (distance < closestDistance) {
                closestDistance = distance;
                closestMessageId = parseInt(messageId);
            }
        }
    });

    // Filter references for the closest message only
    if (closestMessageId) {
        const visibleRefs = allReferences.filter(ref => ref.message_id === closestMessageId);
        references = visibleRefs;
    } else {
        references = [];
    }

    renderReferences();
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
