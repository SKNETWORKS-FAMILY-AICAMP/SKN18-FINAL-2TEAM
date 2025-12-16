// Schedule Page JavaScript Logic

// ✅ Base URL (schedule 앱이 /schedule 하위에 붙어있으니 통일)
const API_BASE = '/schedule';

// State variables
let currentDate = new Date();
let viewMode = 'month'; // 'day' | 'week' | 'month'
let selectedSchedule = null;
let scheduleSearchQuery = "";

// Calendar data (will be loaded from API)
let schedules = [];
let userCalendars = [];

// FullCalendar instance
let calendar = null;

// DOM elements
const scheduleSidebar = document.getElementById('scheduleSidebar');
const scheduleSearchInput = document.getElementById('scheduleSearchInput');
const addScheduleBtn = document.getElementById('addScheduleBtn');
const googleCalendarBtn = document.getElementById('googleCalendarBtn');
const calendarList = document.getElementById('calendarList');
const scheduleList = document.getElementById('scheduleList');
const calendarTitle = document.getElementById('calendarTitle');
const calendarContent = document.getElementById('calendarContent');
const fullcalendarEl = document.getElementById('fullcalendar');
const todayBtn = document.getElementById('todayBtn');
const prevBtn = document.getElementById('prevBtn');
const nextBtn = document.getElementById('nextBtn');
const viewModeBtns = document.querySelectorAll('.view-mode-btn[data-view]');

// Initialize schedule page
function initSchedule() {
    // Initialize FullCalendar
    initFullCalendar();

    // Load initial data
    loadSchedules();
    loadUserCalendars();

    // Event listeners
    if (scheduleSearchInput) {
        scheduleSearchInput.addEventListener('input', handleScheduleSearch);
    }

    if (addScheduleBtn) {
        addScheduleBtn.addEventListener('click', handleAddSchedule);
    }

    if (googleCalendarBtn) {
        googleCalendarBtn.addEventListener('click', handleGoogleCalendarConnect);
    }

    if (todayBtn) {
        todayBtn.addEventListener('click', handleToday);
    }

    if (prevBtn) {
        prevBtn.addEventListener('click', handlePrevious);
    }

    if (nextBtn) {
        nextBtn.addEventListener('click', handleNext);
    }

    // View mode buttons
    viewModeBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const view = e.currentTarget.getAttribute('data-view');
            setViewMode(view);
        });
    });

    // Calendar visibility toggles
    attachCalendarToggleHandlers();

    // Schedule item handlers
    attachScheduleItemHandlers();

    // Status change handlers
    attachStatusChangeHandlers();
    
    // Add calendar button handler
    const addCalendarBtn = document.getElementById('addCalendarBtn');
    if (addCalendarBtn) {
        addCalendarBtn.addEventListener('click', handleAddCalendar);
    }
}

// Initialize FullCalendar
function initFullCalendar() {
    if (!fullcalendarEl || typeof window.Calendar === 'undefined') {
        console.error('FullCalendar library not loaded');
        return;
    }

    calendar = new window.Calendar(fullcalendarEl, {
        initialView: 'dayGridMonth',
        locale: 'ko',
        headerToolbar: false, // We use custom header
        height: '100%', // Fill available height
        firstDay: 0, // Sunday
        dayMaxEvents: 3, // Show max 3 events per day in month view
        moreLinkText: function(n) {
            return '+' + n + ' 더보기';
        },
        moreLinkClick: 'popover',
        eventDisplay: 'block',
        eventTimeFormat: {
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        },
        dayCellContent: function(info) {
            const numericText = info.dayNumberText.replace(/\D/g, '') || info.dayNumberText;
            return { html: `<span class="fc-daygrid-day-number">${numericText}</span>` };
        },
        slotMinTime: '00:00:00',
        slotMaxTime: '24:00:00',
        slotDuration: '01:00:00',
        allDaySlot: true,
        contentHeight: 'auto',
        aspectRatio: 1.35,

        eventClick: function(info) {
            const scheduleId = info.event.id;
            if (window.ScheduleDetailModal && window.ScheduleDetailModal.open) {
                window.ScheduleDetailModal.open(scheduleId);
            } else {
                handleScheduleClick(scheduleId);
            }
        },

        dateClick: function(info) {
            const date = formatDate(info.date);
            if (window.ScheduleAddModal && window.ScheduleAddModal.open) {
                window.ScheduleAddModal.open(date);
            } else {
                handleDayClick(date);
            }
        },

        datesSet: function(info) {
            currentDate = info.start;
            updateCalendarTitle();
        },

        // ✅ 핵심: eventSources 2개(내 일정 + 구글 이벤트)
        eventSources: [
            // (1) 내 일정(DB schedules) - 기존 로직 그대로
            {
                id: 'local-schedules',
                events: function(fetchInfo, successCallback, failureCallback) {
                    try {
                        const events = convertSchedulesToEvents(schedules);
                        successCallback(events);
                    } catch (e) {
                        console.error('Error building local schedule events:', e);
                        failureCallback(e);
                    }
                }
            },

            // (2) 구글 캘린더 이벤트 - 백엔드: /schedule/api/google-events/
            // FullCalendar가 start/end를 자동으로 쿼리스트링으로 붙여줌 (?start=...&end=...)
            {
                id: 'google-events',
                url: `${API_BASE}/api/google-events/`,
                method: 'GET',
                // ✅ 인증 쿠키가 필요하니 same-origin (대부분 기본이지만 명시)
                extraParams: function() {
                    return {}; // 필요 시 확장
                },
                failure: function(err) {
                    // 연결 안 되어 있으면 401/400 날 수 있음 → 조용히 처리
                    console.warn('Google events load failed:', err);
                }
                // headers 옵션은 FullCalendar 버전에 따라 동작이 다를 수 있어서 일단 생략
                // (CSRF는 GET이라 보통 불필요)
            }
        ]
    });

    calendar.render();

    // ✅ 다른 모듈이 접근할 수 있게 노출(선택)
    window.fullCalendarInstance = calendar;

    // Force FullCalendar to recalculate height after rendering
    setTimeout(() => {
        if (calendar) {
            calendar.updateSize();
        }
    }, 100);
}

// Convert schedules to FullCalendar events
function convertSchedulesToEvents(schedules) {
    return schedules.map(schedule => {
        const startDate = new Date(schedule.start_datetime);
        const endDate = schedule.end_datetime
            ? new Date(schedule.end_datetime)
            : new Date(startDate.getTime() + 60 * 60 * 1000);

        return {
            id: String(schedule.id),
            title: schedule.title,
            start: startDate.toISOString(),
            end: endDate.toISOString(),
            color: schedule.color || getScheduleColor(schedule.type || schedule.get_type_display),
            backgroundColor: schedule.color || getScheduleColor(schedule.type || schedule.get_type_display),
            borderColor: schedule.color || getScheduleColor(schedule.type || schedule.get_type_display),
            extendedProps: {
                type: schedule.type || schedule.get_type_display,
                status: schedule.status,
                description: schedule.description || '',
                location: schedule.location || '',
                hasNote: schedule.linked_note ? true : false,
                noteId: schedule.linked_note ? (schedule.linked_note.id || schedule.linked_note) : null
            },
            display: 'block'
        };
    });
}

// Get schedule color based on type
function getScheduleColor(type) {
    const colorMap = {
        '실험': '#3b82f6',
        '미팅': '#a855f7',
        '분석': '#f97316',
        '세미나': '#ec4899',
        '일정': '#10b981'
    };
    return colorMap[type] || '#3b82f6';
}

// Load schedules from API
async function loadSchedules() {
    try {
        const response = await fetch(`${API_BASE}/api/schedules/`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
        });

        if (response.ok) {
            const data = await response.json();
            schedules = data.results || data;
            renderScheduleList();
            refreshCalendar(); // ✅ local + google 둘 다 refetch 됨
        }
    } catch (error) {
        console.error('Error loading schedules:', error);
    }
}

// Load user calendars from API
async function loadUserCalendars() {
    try {
        // ⚠️ 이 API는 너 프로젝트에 따라 다를 수 있음(없으면 404)
        const response = await fetch('/api/calendars/', {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
        });

        if (response.ok) {
            const data = await response.json();
            userCalendars = data.results || data;
        }
    } catch (error) {
        console.error('Error loading calendars:', error);
    }
}

// Handle schedule search
function handleScheduleSearch(e) {
    scheduleSearchQuery = e.target.value.toLowerCase().trim();
    renderScheduleList();
}

// Handle add schedule
function handleAddSchedule() {
    const urlParams = new URLSearchParams(window.location.search);
    const dateParam = urlParams.get('date');

    if (window.ScheduleAddModal && window.ScheduleAddModal.open) {
        window.ScheduleAddModal.open(dateParam);
    } else {
        window.location.href = `${API_BASE}/create/` + (dateParam ? `?date=${dateParam}` : '');
    }
}

function handleGoogleCalendarConnect() {
    if (window.Modal) {
        window.Modal.open('googleCalendarModal');

        // ⭐ 핵심: 모달 열자마자 강제로 캘린더 목록 로드
        if (window.GoogleCalendarModal && window.GoogleCalendarModal.reload) {
            window.GoogleCalendarModal.reload();
        }
    } else {
        window.location.href = `${API_BASE}/google/login/`;
    }
}

// Handle add calendar button click
function handleAddCalendar() {
    if (window.CalendarAddModal && window.CalendarAddModal.open) {
        window.CalendarAddModal.open();
    } else if (window.Modal) {
        window.Modal.open('calendarAddModal');
    }
}

// Handle today button
function handleToday() {
    if (calendar) {
        calendar.today();
        currentDate = new Date();
        updateCalendarTitle();
    }
}

// Handle previous navigation
function handlePrevious() {
    if (calendar) {
        calendar.prev();
    }
}

// Handle next navigation
function handleNext() {
    if (calendar) {
        calendar.next();
    }
}

// Set view mode
function setViewMode(mode) {
    viewMode = mode;

    viewModeBtns.forEach(btn => {
        btn.classList.remove('active');
        if (btn.getAttribute('data-view') === mode) {
            btn.classList.add('active');
        }
    });

    if (calendar) {
        let fullcalendarView;
        switch(mode) {
            case 'day':
                fullcalendarView = 'timeGridDay';
                break;
            case 'week':
                fullcalendarView = 'timeGridWeek';
                break;
            case 'month':
            default:
                fullcalendarView = 'dayGridMonth';
                break;
        }
        calendar.changeView(fullcalendarView);
        updateCalendarTitle();
    }
}

// Update calendar title
function updateCalendarTitle() {
    if (!calendarTitle || !calendar) return;

    const view = calendar.view;
    const start = view.activeStart;
    const end = view.activeEnd;

    if (viewMode === 'day') {
        const year = start.getFullYear();
        const month = start.getMonth() + 1;
        const day = start.getDate();
        calendarTitle.textContent = `${year}년 ${month}월 ${day}일`;
    } else if (viewMode === 'week') {
        const year = start.getFullYear();
        const month = start.getMonth() + 1;
        const day = start.getDate();
        const endDay = end.getDate();
        calendarTitle.textContent = `${year}년 ${month}월 ${day}일 - ${endDay}일`;
    } else {
        const year = start.getFullYear();
        const month = start.getMonth() + 1;
        calendarTitle.textContent = `${year}년 ${month}월`;
    }
}

// Refresh calendar events
function refreshCalendar() {
    if (calendar) {
        // ✅ eventSources 전체 재조회 (local function + google url 둘 다)
        calendar.refetchEvents();

        setTimeout(() => {
            if (calendar) {
                calendar.updateSize();
            }
        }, 50);
    }
}

// Format date as YYYY-MM-DD
function formatDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

// Render schedule list
function renderScheduleList() {
    if (!scheduleList) return;

    let filteredSchedules = schedules;

    if (scheduleSearchQuery) {
        filteredSchedules = schedules.filter(s =>
            s.title.toLowerCase().includes(scheduleSearchQuery) ||
            (s.description && s.description.toLowerCase().includes(scheduleSearchQuery))
        );
    }

    if (filteredSchedules.length === 0) {
        scheduleList.innerHTML = '<div class="empty-state"><p>일정이 없습니다.</p></div>';
        return;
    }

    filteredSchedules.sort((a, b) => new Date(a.start_datetime) - new Date(b.start_datetime));

    scheduleList.innerHTML = filteredSchedules.map(schedule => {
        const startDate = new Date(schedule.start_datetime);
        const dateStr = startDate.toLocaleDateString('ko-KR', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        });
        const timeStr = startDate.toLocaleTimeString('ko-KR', {
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        });

        return `
            <div class="schedule-list-item" data-schedule-id="${schedule.id}">
                <div class="schedule-list-header">
                    <div class="schedule-list-title" data-schedule-id="${schedule.id}">
                        <p>${escapeHtml(schedule.title)}</p>
                        <div class="schedule-list-meta">
                            <i class="fas fa-clock"></i>
                            <span>${dateStr} ${timeStr}</span>
                        </div>
                    </div>
                    ${schedule.linked_note ? `<i class="fas fa-file-lines" data-note-id="${schedule.linked_note}"></i>` : ''}
                </div>
                <div class="schedule-list-footer">
                    <span class="schedule-type">${schedule.get_type_display || schedule.type || '일정'}</span>
                    <select class="status-select status-${schedule.status}" data-schedule-id="${schedule.id}">
                        <option value="scheduled" ${schedule.status === 'scheduled' ? 'selected' : ''}>예정</option>
                        <option value="in_progress" ${schedule.status === 'in_progress' ? 'selected' : ''}>진행중</option>
                        <option value="completed" ${schedule.status === 'completed' ? 'selected' : ''}>완료</option>
                    </select>
                </div>
            </div>
        `;
    }).join('');

    attachScheduleItemHandlers();
    attachStatusChangeHandlers();
}

// Attach calendar toggle handlers
function attachCalendarToggleHandlers() {
    const calendarCheckboxes = calendarList?.querySelectorAll('input[type="checkbox"]');
    calendarCheckboxes?.forEach(checkbox => {
        checkbox.addEventListener('change', async (e) => {
            const calendarId = e.target.getAttribute('data-calendar-id');
            const visible = e.target.checked;

            try {
                await fetch(`/api/calendars/${calendarId}/`, {
                    method: 'PATCH',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ visible }),
                });

                refreshCalendar();
            } catch (error) {
                console.error('Error updating calendar visibility:', error);
            }
        });
    });
}

// Attach schedule item handlers
function attachScheduleItemHandlers() {
    const scheduleItems = scheduleList?.querySelectorAll('.schedule-list-item');
    scheduleItems?.forEach(item => {
        item.addEventListener('click', (e) => {
            if (!e.target.closest('.status-select')) {
                const scheduleId = item.getAttribute('data-schedule-id');
                handleScheduleClick(scheduleId);
            }
        });
    });

    const scheduleTitles = scheduleList?.querySelectorAll('.schedule-list-title');
    scheduleTitles?.forEach(title => {
        title.addEventListener('click', (e) => {
            e.stopPropagation();
            const scheduleId = title.getAttribute('data-schedule-id');
            handleScheduleClick(scheduleId);
        });
    });

    const noteIcons = scheduleList?.querySelectorAll('.fa-file-lines[data-note-id]');
    noteIcons?.forEach(icon => {
        icon.addEventListener('click', (e) => {
            e.stopPropagation();
            const noteId = icon.getAttribute('data-note-id');
            window.location.href = `/notes/${noteId}/`;
        });
    });
}

// Attach status change handlers
function attachStatusChangeHandlers() {
    const statusSelects = scheduleList?.querySelectorAll('.status-select');
    statusSelects?.forEach(select => {
        select.addEventListener('change', async (e) => {
            const scheduleId = select.getAttribute('data-schedule-id');
            const newStatus = select.value;

            try {
                const response = await fetch(`${API_BASE}/api/schedules/${scheduleId}/`, {
                    method: 'PATCH',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ status: newStatus }),
                });

                if (response.ok) {
                    const schedule = schedules.find(s => String(s.id) === String(scheduleId));
                    if (schedule) schedule.status = newStatus;

                    select.className = `status-select status-${newStatus}`;

                    if (window.notyf) {
                        const statusText = {
                            'scheduled': '예정',
                            'in_progress': '진행중',
                            'completed': '완료'
                        }[newStatus] || newStatus;
                        window.notyf.success(`일정 상태가 "${statusText}"으로 변경되었습니다.`);
                    }

                    refreshCalendar();
                } else {
                    if (window.notyf) window.notyf.error('일정 상태 변경에 실패했습니다.');
                }
            } catch (error) {
                console.error('Error updating schedule status:', error);
            }
        });
    });
}

// Handle schedule click
function handleScheduleClick(scheduleId) {
    if (window.ScheduleDetailModal && window.ScheduleDetailModal.open) {
        window.ScheduleDetailModal.open(scheduleId);
    } else {
        window.location.href = `${API_BASE}/${scheduleId}/`;
    }
}

// Handle day click
function handleDayClick(date) {
    if (window.ScheduleAddModal && window.ScheduleAddModal.open) {
        window.ScheduleAddModal.open(date);
    } else {
        window.location.href = `${API_BASE}/create/?date=${date}`;
    }
}

// Get CSRF token
function getCsrfToken() {
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === 'csrftoken') return value;
    }
    const metaTag = document.querySelector('meta[name=csrf-token]');
    if (metaTag) return metaTag.getAttribute('content');
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
    document.addEventListener('DOMContentLoaded', initSchedule);
} else {
    initSchedule();
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.SchedulePage = {
        initSchedule,
        loadSchedules,
        refreshCalendar,
        setViewMode,
        handleToday,
        handlePrevious,
        handleNext,
    };
}
