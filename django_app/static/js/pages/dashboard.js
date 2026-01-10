// Dashboard Page JavaScript Logic

// State management
let chatQuestion = "";
let showRecommendations = false;
let dropdownRef = null;

// Recommended questions data
const recommendedQuestions = [
    "BRCA1 유전자의 돌연변이와 유방암 위험도 관계는?",
    "CRISPR-Cas9의 off-target 효과를 최소화하는 방법은?",
    "mRNA 백신의 면역 반응 메커니즘을 설명해주세요",
    "단백질 정제 프로토콜 최적화 조건은?",
    "AlphaFold2와 RoseTTAFold의 정확도 비교",
];

// DOM elements
const chatQuestionInput = document.getElementById('chatQuestionInput');
const chatSubmitBtn = document.getElementById('chatSubmitBtn');
const recommendationsDropdown = document.getElementById('recommendationsDropdown');
const recommendationsList = document.getElementById('recommendationsList');
const closeRecommendationsBtn = document.getElementById('closeRecommendationsBtn');
const chatQuestionContainer = document.getElementById('chatQuestionContainer');

// Dummy data from React Dashboard
const dummyExperiments = [
    {
        id: 1,
        pipeline: "Customer Support Assistant",
        tools: ["RFdiffusion", "ProteinMPNN"],
        status: "진행중",
        created: "2일 전",
    },
    {
        id: 2,
        pipeline: "Legal Document Analyzer",
        tools: ["AlphaFold", "ColabFold", "DiffDock"],
        status: "준비",
        created: "1일 전",
    },
    {
        id: 3,
        pipeline: "Medical Diagnosis Helper",
        tools: ["ProteinMPNN", "AlphaFold"],
        status: "완료",
        created: "12시간 전",
    },
];

const dummyRecentNotes = [
    {
        id: 1,
        title: "CRISPR-Cas9 실험 결과 분석",
        date: "2025-11-30",
        shared: 3,
        comments: 5,
        tags: ["CRISPR", "유전자편집", "실험결과"],
    },
    {
        id: 2,
        title: "단백질 구조 예측 모델 비교",
        date: "2025-11-29",
        shared: 2,
        comments: 3,
        tags: ["단백질", "AlphaFold", "구조예측", "AI"],
    },
    {
        id: 3,
        title: "mRNA 백신 안정성 연구",
        date: "2025-11-28",
        shared: 5,
        comments: 8,
        tags: ["백신", "mRNA", "안정성"],
    },
    {
        id: 4,
        title: "암세포 증식 억제 메커니즘",
        date: "2025-11-27",
        shared: 1,
        comments: 2,
        tags: ["암연구", "세포생물학", "메커니즘"],
    },
    {
        id: 5,
        title: "면역 반응 분석 프로토콜",
        date: "2025-11-26",
        shared: 4,
        comments: 6,
        tags: ["면역학", "프로토콜", "분석", "실험"],
    },
];

const dummyRecentChats = [
    {
        id: 1,
        question: "BRCA1 유전자의 돌연변이와 유방암 위험도 관계",
        time: "30분 전",
    },
    {
        id: 2,
        question: "CRISPR-Cas9의 off-target 효과 최소화 방법",
        time: "2시간 전",
    },
    {
        id: 3,
        question: "mRNA 백신의 면역 반응 메커니즘",
        time: "5시간 전",
    },
    {
        id: 4,
        question: "단백질 정제 프로토콜 최적화 조건",
        time: "1일 전",
    },
    {
        id: 5,
        question: "AlphaFold2 vs RoseTTAFold 정확도 비교",
        time: "2일 전",
    },
];

// Status 코드 매핑: P: 예정, E: 진행중, F: 완료
const statusCodeMap = {
    'P': '예정',
    'E': '진행중',
    'F': '완료'
};

// Status 코드를 한글로 변환
function getStatusDisplay(statusCode) {
    const statusMap = {
        // Schedule 모델의 상태 코드
        'E': '예정',
        'R': '진행중',
        'C': '완료',
        // Schedule 모델의 status 프로퍼티 (영어)
        'scheduled': '예정',
        'in_progress': '진행중',
        'completed': '완료',
        // Legacy support
        'P': '예정',
        'F': '완료'
    };
    return statusMap[statusCode] || statusCode;
}

// Status 코드를 CSS 클래스로 변환
function getStatusClass(statusCode) {
    const classMap = {
        // Schedule 모델의 상태 코드
        'E': 'p',  // 예정
        'R': 'e',  // 진행중
        'C': 'f',  // 완료
        // Schedule 모델의 status 프로퍼티 (영어)
        'scheduled': 'p',  // 예정
        'in_progress': 'e',  // 진행중
        'completed': 'f',  // 완료
        // Legacy support
        'P': 'p',
        'F': 'f'
    };
    // 영어 값이 오면 하이픈을 언더스코어로 처리
    const normalizedCode = statusCode ? statusCode.toString().replace(/-/g, '_') : statusCode;
    return classMap[normalizedCode] || (statusCode ? statusCode.toLowerCase().replace(/_/g, '-') : 'p');
}

const dummyTodaySchedule = [
    {
        id: 1,
        title: "PCR 반응 조건 최적화",
        status: "E",  // 진행중
        startDate: "2023/05/11",
        endDate: "2023/05/17",
        linkedNote: "PCR 실험 프로토콜",
    },
    {
        id: 2,
        title: "주간 연구 진행 보고",
        status: "P",  // 예정
        startDate: "2023/08/03",
        endDate: "2023/08/12",
        linkedNote: null,
    },
    {
        id: 3,
        title: "세포 배양 관찰",
        status: "F",  // 완료
        startDate: "2022/12/01",
        endDate: "2022/12/13",
        linkedNote: "세포 배양 기록",
    },
    {
        id: 4,
        title: "시퀀싱 데이터 검토",
        status: "E",  // 진행중
        startDate: "2023/08/22",
        endDate: "2023/09/01",
        linkedNote: "NGS 분석 결과",
    },
    {
        id: 5,
        title: "최신 논문 리뷰",
        status: "P",  // 예정
        startDate: "2023/09/19",
        endDate: "2023/09/25",
        linkedNote: null,
    },
];

// Initialize dashboard
function initDashboard() {
    // Render recommended questions
    renderRecommendations();

    // Render dummy data if containers are empty
    renderDummyData();
    
    // Convert server-rendered times to Korean format
    convertServerRenderedTimes();
    
    // 대시보드도 자동 업데이트 없음 (화면 새로고침 필요)

    // Event listeners
    if (chatQuestionInput) {
        chatQuestionInput.addEventListener('input', handleChatInput);
        chatQuestionInput.addEventListener('focus', handleChatInputFocus);
        chatQuestionInput.addEventListener('keydown', handleChatInputKeydown);
    }

    if (chatSubmitBtn) {
        chatSubmitBtn.addEventListener('click', handleChatSubmit);
    }

    if (closeRecommendationsBtn) {
        closeRecommendationsBtn.addEventListener('click', closeRecommendations);
    }

    // Click outside handler
    document.addEventListener('click', handleClickOutside);

    // Item click handlers
    attachItemClickHandlers();
}

// Render recommended questions
function renderRecommendations() {
    if (!recommendationsList) return;

    recommendationsList.innerHTML = recommendedQuestions.map((question, index) => {
        return `
            <div class="recommendation-item" data-question-index="${index}">
                ${escapeHtml(question)}
            </div>
        `;
    }).join('');

    // Attach click handlers to recommendation items
    const recommendationItems = recommendationsList.querySelectorAll('.recommendation-item');
    recommendationItems.forEach(item => {
        item.addEventListener('click', (e) => {
            const index = parseInt(e.currentTarget.getAttribute('data-question-index'));
            selectRecommendation(index);
        });
    });
}

// Handle chat input
function handleChatInput(e) {
    chatQuestion = e.target.value;
}

// Handle chat input focus
function handleChatInputFocus() {
    if (chatQuestion.length === 0) {
        showRecommendationsDropdown();
    }
}

// Handle chat input keydown
function handleChatInputKeydown(e) {
    if (e.key === 'Enter') {
        e.preventDefault();
        handleChatSubmit();
    } else if (e.key === 'Escape') {
        closeRecommendations();
    }
}

// Handle chat submit
function handleChatSubmit() {
    const question = chatQuestionInput?.value.trim() || chatQuestion.trim();
    
    if (!question) {
        // Show recommendations if input is empty
        showRecommendationsDropdown();
        return;
    }

    // Navigate to chat page with question
    const chatUrl = `/chat/?question=${encodeURIComponent(question)}`;
    window.location.href = chatUrl;
}

// Show recommendations dropdown
function showRecommendationsDropdown() {
    if (recommendationsDropdown) {
        recommendationsDropdown.style.display = 'block';
        showRecommendations = true;
        dropdownRef = recommendationsDropdown;
    }
}

// Close recommendations dropdown
function closeRecommendations() {
    if (recommendationsDropdown) {
        recommendationsDropdown.style.display = 'none';
        showRecommendations = false;
    }
}

// Select recommendation
function selectRecommendation(index) {
    if (index >= 0 && index < recommendedQuestions.length) {
        const question = recommendedQuestions[index];
        if (chatQuestionInput) {
            chatQuestionInput.value = question;
            chatQuestion = question;
            // Focus on input field after setting value
            chatQuestionInput.focus();
        }
        closeRecommendations();
        // No auto submit - user must press Enter or click submit button
    }
}

// Handle click outside
function handleClickOutside(event) {
    if (showRecommendations && dropdownRef && !dropdownRef.contains(event.target) && 
        !chatQuestionContainer?.contains(event.target)) {
        closeRecommendations();
    }
}

// Render dummy data
async function renderDummyData() {
    // Check if data containers are empty and render dummy data
    const scheduleList = document.getElementById('scheduleList');
    const experimentTableBody = document.getElementById('experimentTableBody');
    const notesList = document.getElementById('notesList');
    const chatsList = document.getElementById('chatsList');

    // Load and render schedules from API
    if (scheduleList) {
        const schedules = await loadRecentSchedules();
        if (schedules.length > 0) {
            renderSchedules(scheduleList, schedules);
        } else if (scheduleList.querySelector('.empty-state')) {
            renderSchedules(scheduleList);
        }
    }

    // Load and render experiments from API
    if (experimentTableBody) {
        const experiments = await loadRecentExperiments();
        if (experiments.length > 0) {
            renderExperiments(experimentTableBody, experiments);
        } else if (experimentTableBody.querySelector('.empty-state')) {
            renderExperiments(experimentTableBody, []);
        }
    }

    // Render notes if empty
    if (notesList && notesList.querySelector('.empty-state')) {
        renderNotes(notesList);
    }

    // Render chats if empty
    if (chatsList && chatsList.querySelector('.empty-state')) {
        renderChats(chatsList);
    }
}

// Render schedules
function renderSchedules(container, schedules = null) {
    if (!container) return;
    
    // If no schedules provided, use dummy data
    const scheduleData = schedules || dummyTodaySchedule;
    
    if (scheduleData.length === 0) {
        container.innerHTML = '<div class="empty-state">일정이 없습니다.</div>';
        return;
    }
    
    container.innerHTML = scheduleData.map(schedule => {
        // API 응답 형식 또는 더미 데이터 형식 모두 지원
        const scheduleId = schedule.id || schedule.schedule_sid;
        const title = schedule.title || '';
        const linkedNote = schedule.linked_note || schedule.linkedNote;
        const status = schedule.status || schedule.schedule_status || 'E';
        const startDate = schedule.start_datetime ? new Date(schedule.start_datetime) : null;
        const endDate = schedule.end_datetime ? new Date(schedule.end_datetime) : null;
        
        const linkedNoteIcon = linkedNote 
            ? '<i class="far fa-file-lines"></i>' 
            : '';
        
        const statusDisplay = getStatusDisplay(status);
        const statusClass = getStatusClass(status);
        
        // 날짜 포맷팅
        let dateDisplay = '';
        if (startDate && endDate) {
            const startStr = `${startDate.getFullYear()}/${String(startDate.getMonth() + 1).padStart(2, '0')}/${String(startDate.getDate()).padStart(2, '0')}`;
            const endStr = `${endDate.getFullYear()}/${String(endDate.getMonth() + 1).padStart(2, '0')}/${String(endDate.getDate()).padStart(2, '0')}`;
            dateDisplay = `${startStr} ~ ${endStr}`;
        } else if (schedule.startDate && schedule.endDate) {
            // Legacy format
            dateDisplay = `${schedule.startDate} ~ ${schedule.endDate}`;
        }
        
        return `
            <div class="schedule-item" data-schedule-id="${scheduleId}">
                <div class="schedule-item-header">
                    <i class="far fa-calendar"></i>
                    <div class="schedule-item-title">
                        <p>${escapeHtml(title)}</p>
                    </div>
                    ${linkedNoteIcon}
                </div>
                <div class="schedule-item-footer">
                    <span class="status-badge status-${statusClass}">
                        ${escapeHtml(statusDisplay)}
                    </span>
                    <span class="schedule-date">
                        ${escapeHtml(dateDisplay)}
                    </span>
                </div>
            </div>
        `;
    }).join('');
}

// Render experiments - matches experiment page style with Korean and dots
function renderExperiments(container, experiments = null) {
    if (!container) return;
    
    // experiments 인자가 없으면 빈 배열 처리
    const experimentsList = experiments && Array.isArray(experiments) && experiments.length > 0 
        ? experiments 
        : [];
    
    if (experimentsList.length === 0) {
        container.innerHTML = `
            <tr>
                <td colspan="4" class="empty-state">
                    <div class="empty-state">
                        <p class="empty-message">실험 내역이 없습니다</p>
                    </div>
                </td>
            </tr>
        `;
        return;
    }
    
    container.innerHTML = experimentsList.map(experiment => {
        // Handle both API response format and dummy data format
        const tools = experiment.tools || [];
        const toolsHtml = tools.map(tool => {
            const toolName = typeof tool === 'string' ? tool : (tool.name || tool.tool_name || tool);
            return `<span class="tool-tag">${escapeHtml(toolName)}</span>`;
        }).join('');
        
        // 상태 처리 - API에서 status_display를 제공하거나 상태 코드를 변환
        const statusCode = experiment.status || 'R';
        const rawStatusDisplay = experiment.status_display || 
                            (statusCode === 'C' ? '완료' :
                            statusCode === 'P' ? '진행중' :
                            statusCode === 'R' ? '준비' :
                            statusCode === 'F' ? '실패' :
                            statusCode === 'E' ? '활성' :
                            statusCode === 'D' ? '비활성' : statusCode);
        
        // '실패'를 '진행'으로 변경 (실험 페이지와 동일)
        const statusDisplay =
            rawStatusDisplay === 'Failed' || rawStatusDisplay === '실패'
                ? '진행'
                : (rawStatusDisplay === '준비' ? rawStatusDisplay : 
                    rawStatusDisplay === '진행중' ? rawStatusDisplay :
                    rawStatusDisplay === '완료' ? rawStatusDisplay :
                    rawStatusDisplay);
        
        // 상태 클래스 결정 (실험 페이지와 동일)
        const statusClass =
            statusDisplay === '완료'   ? 'status-completed' :
            statusDisplay === '진행'   ? 'status-progress' :
            statusDisplay === '진행중' ? 'status-progress' :
            statusDisplay === '준비'   ? 'status-ready' :
            statusDisplay === '활성'   ? 'status-ready' :
            statusDisplay === '비활성' ? 'status-ready' :
            'status-ready';
        
        const statusDotClass =
            statusDisplay === '완료'   ? 'status-dot-completed' :
            statusDisplay === '진행'   ? 'status-dot-progress' :
            statusDisplay === '진행중' ? 'status-dot-progress' :
            statusDisplay === '준비'   ? 'status-dot-ready' :
            statusDisplay === '활성'   ? 'status-dot-ready' :
            statusDisplay === '비활성' ? 'status-dot-ready' :
            'status-dot-ready';
        
        // 생성일 처리 - API 응답 또는 더미 데이터
        const createdAgo = experiment.created_at ? 
            formatTimeAgo(new Date(experiment.created_at)) : 
            (experiment.created || '알 수 없음');
        
        // 파이프라인 이름 처리
        const pipelineName = experiment.pipeline || experiment.pipeline_name || experiment.name || 'Unnamed Pipeline';
        
        // 진행률 처리 (API에서 직접 제공하거나 상태 코드 기반)
        const progress = experiment.progress !== undefined ? experiment.progress : 
                        (statusCode === 'C' ? 100 : 
                        statusCode === 'P' ? 65 : 
                        statusCode === 'R' ? 25 : 0);
        
        return `
            <tr data-experiment-id="${experiment.id || experiment.experiment_sid}" data-experiment-progress="${progress}">
                <td>${escapeHtml(pipelineName)}</td>
                <td>
                    <div class="tool-tags">
                        ${toolsHtml}
                    </div>
                </td>
                <td>
                    <span class="status-badge ${statusClass}">
                        <span class="status-dot ${statusDotClass}"></span>
                        ${escapeHtml(statusDisplay)}
                    </span>
                </td>
                <td>${escapeHtml(createdAgo)}</td>
            </tr>
        `;
    }).join('');
}

// Render notes
function renderNotes(container) {
    if (!container) return;
    
    container.innerHTML = dummyRecentNotes.map(note => {
        const tagsHtml = note.tags.slice(0, 5).map(tag => 
            `<span class="note-tag">#${escapeHtml(tag)}</span>`
        ).join('');
        
        return `
            <div class="note-item" data-note-id="${note.id}">
                <div class="note-content">
                    <div class="note-header">
                        <i class="far fa-file-lines"></i>
                        <div class="note-title-section">
                            <p class="note-title">${escapeHtml(note.title)}</p>
                            <div class="note-tags">
                                ${tagsHtml}
                            </div>
                        </div>
                    </div>
                    <div class="note-meta">
                        <span class="note-date">${escapeHtml(note.date)}</span>
                        <div class="note-stats">
                            <span class="note-stat">
                                <i class="fa fa-share-nodes"></i>
                                ${note.shared}
                            </span>
                            <span class="note-stat">
                                <i class="far fa-comment-dots"></i>
                                ${note.comments}
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// Render chats
function renderChats(container) {
    if (!container) return;
    
    container.innerHTML = dummyRecentChats.map(chat => {
        return `
            <div class="chat-item" data-chat-id="${chat.id}">
                <div class="chat-content">
                    <div class="chat-header">
                        <i class="far fa-comment-dots"></i>
                        <div class="chat-title-section">
                            <p class="chat-question">${escapeHtml(chat.question)}</p>
                        </div>
                    </div>
                    <div class="chat-meta">
                        <span class="chat-time">${escapeHtml(chat.time)}</span>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// Attach item click handlers
function attachItemClickHandlers() {
    // Schedule items
    const scheduleItems = document.querySelectorAll('.schedule-item');
    scheduleItems.forEach(item => {
        item.addEventListener('click', (e) => {
            // 캘린더 페이지로 이동
            window.location.href = '/schedule/';
        });
    });

    // Experiment table rows
    const experimentRows = document.querySelectorAll('.experiment-table tbody tr[data-experiment-id]');
    experimentRows.forEach(row => {
        row.addEventListener('click', (e) => {
            window.location.href = '/experiments/';
        });
    });

    // Note items
    const noteItems = document.querySelectorAll('.note-item[data-note-id]');
    noteItems.forEach(item => {
        item.addEventListener('click', (e) => {
            const noteId = e.currentTarget.getAttribute('data-note-id');
            if (noteId) {
                window.location.href = `/notes/detail/?id=${noteId}`;
            }
        });
    });

    // Chat items
    const chatItems = document.querySelectorAll('.chat-item[data-chat-id]');
    chatItems.forEach(item => {
        item.addEventListener('click', (e) => {
            const chatId = e.currentTarget.getAttribute('data-chat-id');
            if (chatId) {
                window.location.href = `/chat/?id=${chatId}`;
            } else {
                window.location.href = '/chat/';
            }
        });
    });
}

// Load dashboard data from API
async function loadDashboardData() {
    try {
        const response = await fetch('/api/dashboard/', {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
        });

        if (response.ok) {
            const data = await response.json();
            // Update UI with fresh data if needed
            // This can be used for real-time updates
            return data;
        }
    } catch (error) {
        console.error('Error loading dashboard data:', error);
    }
}

// Load recent schedules from API
async function loadRecentSchedules() {
    try {
        const now = new Date();
        const thirtyDaysAgo = new Date(now);
        thirtyDaysAgo.setDate(now.getDate() - 30);
        const ninetyDaysLater = new Date(now);
        ninetyDaysLater.setDate(now.getDate() + 90);

        const timeMin = thirtyDaysAgo.toISOString();
        const timeMax = ninetyDaysLater.toISOString();

        const response = await fetch(`/schedule/api/schedules/?timeMin=${encodeURIComponent(timeMin)}&timeMax=${encodeURIComponent(timeMax)}`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
        });

        if (response.ok) {
            const data = await response.json();
            const schedules = data.results || [];
            
            // 최근 일정 10개만 선택 (start_datetime 기준으로 정렬)
            const recentSchedules = schedules
                .sort((a, b) => new Date(a.start_datetime) - new Date(b.start_datetime))
                .slice(0, 10);
            
            return recentSchedules;
        } else {
            console.error('Error loading schedules:', response.statusText);
            return [];
        }
    } catch (error) {
        console.error('Error loading schedules:', error);
        return [];
    }
}

// Load recent experiments from API
async function loadRecentExperiments() {
    try {
        const response = await fetch('/api/experiments/', {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
        });

        if (response.ok) {
            const data = await response.json();
            const experiments = data.results || data || [];
            // 최근 10개만 반환 (대시보드용)
            return experiments.slice(0, 10);
        } else {
            console.error('Error loading experiments:', response.statusText);
            return [];
        }
    } catch (error) {
        console.error('Error loading experiments:', error);
        return [];
    }
}

// Format time ago (Korean format: "2일 전", "2시간 48분 전", "1분 전", "방금 전")
function formatTimeAgo(date) {
    if (!date) return '알 수 없음';
    
    const now = new Date();
    const diff = now - new Date(date);
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) {
        if (days === 1) return '1일 전';
        return `${days}일 전`;
    }
    if (hours > 0) {
        const remainingMinutes = minutes % 60;
        if (remainingMinutes > 0) {
            if (hours === 1) {
                return remainingMinutes === 1 ? '1시간 1분 전' : `1시간 ${remainingMinutes}분 전`;
            }
            return remainingMinutes === 1 ? `${hours}시간 1분 전` : `${hours}시간 ${remainingMinutes}분 전`;
        }
        if (hours === 1) return '1시간 전';
        return `${hours}시간 전`;
    }
    if (minutes > 0) {
        if (minutes === 1) return '1분 전';
        return `${minutes}분 전`;
    }
    return '방금 전';
}

// Convert server-rendered time to Korean format
function convertServerRenderedTimes() {
    const experimentTableBody = document.getElementById('experimentTableBody');
    if (!experimentTableBody) return;
    
    // Find all rows that have server-rendered data (not empty state)
    const rows = experimentTableBody.querySelectorAll('tr[data-experiment-id][data-created-at]');
    rows.forEach(row => {
        // Get the created date from data attribute
        const createdAt = row.getAttribute('data-created-at');
        if (createdAt) {
            // Get the created date cell (4th column or with class 'created-time')
            const createdCell = row.querySelector('td.created-time') || row.querySelector('td:nth-child(4)');
            if (createdCell) {
                // Convert to Korean format
                const koreanTime = formatTimeAgo(new Date(createdAt));
                createdCell.textContent = koreanTime;
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
    document.addEventListener('DOMContentLoaded', initDashboard);
} else {
    initDashboard();
}

// 대시보드의 특정 실험 행 업데이트 (알림 수신 시 사용)
async function updateExperimentRowInDashboard(experimentId, experimentData) {
    const experimentTableBody = document.getElementById('experimentTableBody');
    if (!experimentTableBody || !experimentId) return;
    
    const row = experimentTableBody.querySelector(`tr[data-experiment-id="${experimentId}"]`);
    if (!row) return;
    
    // 상태 코드 변환
    const statusCode = experimentData.status || 'R';
    const statusMap = {
        'C': '완료',
        'P': '진행중',
        'R': '준비',
        'F': '진행',
        'E': '활성',
        'D': '비활성'
    };
    const statusDisplay = statusMap[statusCode] || experimentData.status_display || '준비';
    
    // 상태 클래스 결정 (실험 페이지와 동일)
    const statusClass =
        statusDisplay === '완료'   ? 'status-completed' :
        statusDisplay === '진행'   ? 'status-progress' :
        statusDisplay === '진행중' ? 'status-progress' :
        statusDisplay === '준비'   ? 'status-ready' :
        statusDisplay === '활성'   ? 'status-ready' :
        statusDisplay === '비활성' ? 'status-ready' :
        'status-ready';
    
    const statusDotClass =
        statusDisplay === '완료'   ? 'status-dot-completed' :
        statusDisplay === '진행'   ? 'status-dot-progress' :
        statusDisplay === '진행중' ? 'status-dot-progress' :
        statusDisplay === '준비'   ? 'status-dot-ready' :
        statusDisplay === '활성'   ? 'status-dot-ready' :
        statusDisplay === '비활성' ? 'status-dot-ready' :
        'status-dot-ready';
    
    // 진행률 업데이트
    const progress = experimentData.progress !== undefined ? experimentData.progress : 
                    (statusCode === 'C' ? 100 : 
                    statusCode === 'P' ? 65 : 
                    statusCode === 'R' ? 25 : 0);
    
    // 상태 열 업데이트 (3번째 td)
    const statusCell = row.querySelector('td:nth-child(3)');
    if (statusCell) {
        statusCell.innerHTML = `
            <span class="status-badge ${statusClass}">
                <span class="status-dot ${statusDotClass}"></span>
                ${escapeHtml(statusDisplay)}
            </span>
        `;
    }
    
    // data 속성 업데이트
    row.setAttribute('data-experiment-progress', progress);
    
    console.log(`[updateExperimentRowInDashboard] Updated experiment ${experimentId}: progress=${progress}%, status=${statusDisplay}`);
}

// 알림 수신 시 대시보드의 특정 실험 업데이트
async function updateDashboardExperimentFromNotification(experimentId) {
    if (!experimentId) {
        console.warn('[updateDashboardExperimentFromNotification] Experiment ID is missing');
        return;
    }
    
    try {
        // 실험 파일 목록 API를 통해 최신 상태 가져오기
        const response = await fetch(`/api/experiments/${experimentId}/files/`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
        });

        if (response.ok) {
            const data = await response.json();
            const experiment = data.experiment || {};
            
            console.log(`[updateDashboardExperimentFromNotification] Updating experiment ${experimentId}: status=${experiment.status}, progress=${experiment.progress}%`);
            
            // 대시보드의 실험 목록 행 업데이트
            updateExperimentRowInDashboard(experimentId, {
                progress: experiment.progress,
                status: experiment.status,
                status_display: getDashboardStatusDisplay(experiment.status)
            });
        } else {
            console.error('[updateDashboardExperimentFromNotification] API request failed:', response.status, response.statusText);
        }
    } catch (error) {
        console.error('[updateDashboardExperimentFromNotification] Error:', error);
    }
}

// 대시보드용 상태 코드를 표시 텍스트로 변환하는 헬퍼 함수
function getDashboardStatusDisplay(statusCode) {
    const statusMap = {
        'C': '완료',
        'P': '진행중',
        'R': '준비',
        'F': '진행',
        'E': '활성',
        'D': '비활성',
        'completed': '완료',
        'in_progress': '진행중',
        'ready': '준비',
        'failed': '진행',
        'active': '활성',
        'inactive': '비활성'
    };
    return statusMap[statusCode] || '진행중';
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.DashboardPage = {
        initDashboard,
        handleChatSubmit,
        loadDashboardData,
        showRecommendationsDropdown,
        closeRecommendations,
        updateDashboardExperimentFromNotification, // 알림 수신 시 실험 업데이트
    };
}