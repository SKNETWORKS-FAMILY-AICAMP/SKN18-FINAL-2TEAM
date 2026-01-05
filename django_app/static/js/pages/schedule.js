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
let activeCalendarIds = new Set();
let calendarsLoaded = false;
let currentFetchRange = null;

// FullCalendar instance
let calendar = null;

// DOM elements
const scheduleSidebar = document.getElementById('scheduleSidebar');
const scheduleRoot = document.querySelector('.schedule-container');
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

// ✅ 추가: 최신일정 가져오기 버튼
const refreshLatestBtn = document.getElementById('refreshLatestBtn');

const viewModeBtns = document.querySelectorAll('.view-mode-btn[data-view]');
let isGoogleConnected = scheduleRoot?.dataset.googleConnected === 'true';

// Initialize schedule page
function initSchedule() {
    initFullCalendar();
    loadUserCalendars();
    initInvitationDrawer();
    // 초기 로드 시 badge 업데이트
    setTimeout(() => {
        loadInvitationBadge();
    }, 500);

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

    // ✅ 추가: 최신일정 가져오기 버튼 이벤트
    if (refreshLatestBtn) {
        refreshLatestBtn.addEventListener('click', handleRefreshLatest);
    }

    // View mode buttons
    viewModeBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const view = e.currentTarget.getAttribute('data-view');
            setViewMode(view);
        });
    });

    // Schedule item handlers
    attachScheduleItemHandlers();

    // Status change handlers
    attachStatusChangeHandlers();

    // Add calendar button handler
    const addCalendarBtn = document.getElementById('addCalendarBtn');
    if (addCalendarBtn) {
        addCalendarBtn.addEventListener('click', handleAddCalendar);
    }

    // Manage calendar button handler
    const manageCalendarBtn = document.getElementById('manageCalendarBtn');
    if (manageCalendarBtn) {
        manageCalendarBtn.addEventListener('click', handleManageCalendar);
    }

    if (isGoogleConnected) {
        syncGoogleEvents({ rangeFromCalendar: true }).catch(() => {});
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
            currentDate = calendar.getDate();
            updateCalendarTitle();
        },

        events: fetchEvents
    });

    calendar.render();

    // ✅ 다른 모듈이 접근할 수 있게 노출(선택)
    window.fullCalendarInstance = calendar;

    // ✅ 최초 렌더 직후에도 제목 한 번 맞춰주기
    updateCalendarTitle();

    // Force FullCalendar to recalculate height after rendering
    setTimeout(() => {
        if (calendar) {
            calendar.updateSize();
        }
    }, 100);
}

function getDefaultRange() {
    const now = new Date();
    const start = new Date(now);
    start.setMonth(start.getMonth() - 1);
    const end = new Date(now);
    end.setMonth(end.getMonth() + 2);
    return { start, end };
}

async function requestSchedules(range) {
    const effectiveRange = range || getDefaultRange();
    const params = new URLSearchParams();
    if (effectiveRange.start) {
        params.set('timeMin', effectiveRange.start.toISOString());
    }
    if (effectiveRange.end) {
        params.set('timeMax', effectiveRange.end.toISOString());
    }

    const response = await fetch(`${API_BASE}/api/schedules/?${params.toString()}`, {
        method: 'GET',
        headers: {
            'X-CSRFToken': getCsrfToken(),
            'Content-Type': 'application/json',
        },
    });

    if (!response.ok) {
        throw new Error('failed_to_fetch_schedules');
    }

    const data = await response.json();
    schedules = data.results || data || [];
    renderScheduleList();
    return schedules;
}

async function fetchEvents(fetchInfo, successCallback, failureCallback) {
    try {
        currentFetchRange = {
            start: fetchInfo.start,
            end: fetchInfo.end,
        };

        await requestSchedules(currentFetchRange);
        const events = convertSchedulesToEvents(schedules);
        successCallback(events);
    } catch (error) {
        console.error('Error fetching events:', error);
        failureCallback(error);
    }
}

// Convert schedules to FullCalendar events
function convertSchedulesToEvents(schedules) {
    return schedules
        .filter(shouldShowSchedule)
        .map(schedule => {
        const startDate = schedule.start_datetime ? new Date(schedule.start_datetime) : new Date();
        const endDate = schedule.end_datetime
            ? new Date(schedule.end_datetime)
            : new Date(startDate.getTime() + 60 * 60 * 1000);
        const isAllDay = schedule.is_all_day === true || schedule.is_all_day === 'Y';

        const event = {
            id: String(schedule.id),
            title: schedule.title,
            color: schedule.color || getScheduleColor(schedule.type || schedule.get_type_display),
            backgroundColor: schedule.color || getScheduleColor(schedule.type || schedule.get_type_display),
            borderColor: schedule.color || getScheduleColor(schedule.type || schedule.get_type_display),
            extendedProps: {
                type: schedule.type || schedule.get_type_display,
                status: schedule.status,
                description: schedule.description || '',
                location: schedule.location || '',
                hasNote: schedule.linked_note ? true : false,
                noteId: schedule.linked_note ? (schedule.linked_note.id || schedule.linked_note) : null,
                source: schedule.source || 'local',
                calendarName: schedule.calendar_name || null,
            },
            display: 'block'
        };

        if (isAllDay) {
            event.allDay = true;
            event.display = 'auto';
            const startString = schedule.start_datetime
                ? schedule.start_datetime.split('T')[0]
                : formatDate(startDate);
            const endString = schedule.end_datetime
                ? schedule.end_datetime.split('T')[0]
                : startString;
            event.start = startString;
            // FullCalendar treats all-day end as exclusive, so +1 day
            const exclusiveEnd = new Date(endString);
            exclusiveEnd.setDate(exclusiveEnd.getDate() + 1);
            event.end = exclusiveEnd.toISOString().split('T')[0];
        } else {
            event.start = startDate.toISOString();
            event.end = endDate.toISOString();
        }

        return event;
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

function normalizeHexColor(color, fallback = '#3b82f6') {
    if (!color || typeof color !== 'string') return fallback;
    const trimmed = color.trim();
    if (/^#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$/.test(trimmed)) {
        return trimmed;
    }
    return fallback;
}

async function loadSchedules() {
    if (calendar) {
        calendar.refetchEvents();
        return;
    }

    try {
        await requestSchedules();
    } catch (error) {
        console.error('Error loading schedules:', error);
    }
}

// Load user calendars from API
async function loadUserCalendars() {
    try {
        const response = await fetch('/api/calendars/', {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
        });

        if (response.ok) {
            const data = await response.json();
            userCalendars = Array.isArray(data?.results) ? data.results : (Array.isArray(data) ? data : []);
        } else {
            userCalendars = [];
        }
    } catch (error) {
        console.error('Error loading calendars:', error);
        userCalendars = [];
    }

    calendarsLoaded = true;
    activeCalendarIds = new Set(
        userCalendars
            .filter(calendar => calendar.visible !== false)
            .map(calendar => String(calendar.id))
    );

    renderCalendarList();
    renderScheduleList();
    refreshCalendar();
}

function renderCalendarList() {
    if (!calendarList) return;

    if (!Array.isArray(userCalendars) || userCalendars.length === 0) {
        calendarList.innerHTML = `
            <div class="empty-state">
                <p>캘린더가 없습니다.</p>
            </div>
        `;
        return;
    }

    calendarList.innerHTML = userCalendars.map((calendar) => {
        const source = calendar.source_type || calendar.source || 'local';
        const color = normalizeHexColor(calendar.color);
        const isVisible = activeCalendarIds.has(String(calendar.id));
        return `
            <label
                class="calendar-item"
                data-calendar-id="${calendar.id}"
                data-calendar-source="${source}"
            >
                <input
                    type="checkbox"
                    data-calendar-id="${calendar.id}"
                    ${isVisible ? 'checked' : ''}
                />
                <div class="calendar-color" style="background-color: ${color};"></div>
                <span>${escapeHtml(calendar.name || '')}</span>
                ${source === 'google' ? '<i class="fa-brands fa-google calendar-source-icon" title="Google Calendar"></i>' : ''}
            </label>
        `;
    }).join('');

    attachCalendarToggleHandlers();
}

function isCalendarFilterActive() {
    return calendarsLoaded && userCalendars.length > 0;
}

function shouldShowSchedule(schedule) {
    if (!isCalendarFilterActive()) {
        return true;
    }

    if (activeCalendarIds.size === 0) {
        return false;
    }

    const userCalendarId = schedule.user_calendar_id || schedule.calendar_id;
    if (!userCalendarId) {
        return true;
    }
    return activeCalendarIds.has(String(userCalendarId));
}

async function syncGoogleEvents(options = {}) {
    if (!isGoogleConnected) return null;

    const { rangeFromCalendar = false } = options;
    const payload = {};

    if (rangeFromCalendar && calendar && calendar.view) {
        const view = calendar.view;
        if (view.currentStart) {
            payload.timeMin = view.currentStart.toISOString();
        }
        if (view.currentEnd) {
            payload.timeMax = view.currentEnd.toISOString();
        }
    }

    try {
        const response = await fetch(`${API_BASE}/api/google-events/sync/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
        });

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            throw new Error(data?.status || 'sync_failed');
        }

        if (data?.status === 'no_credentials') {
            isGoogleConnected = false;
        }

        return data;
    } catch (error) {
        console.error('Google sync failed:', error);
        throw error;
    }
}

// ✅ 추가: 최신일정 가져오기
async function handleRefreshLatest() {
    try {
        if (isGoogleConnected) {
            try {
                const result = await syncGoogleEvents({ rangeFromCalendar: true });
                if (result?.status === 'ok' && window.notyf) {
                    const syncedCount = result.synced ?? 0;
                    window.notyf.success(`Google 일정 ${syncedCount}건을 동기화했습니다.`);
                } else if (result?.status === 'no_calendars' && window.notyf) {
                    window.notyf.info('동기화할 Google 캘린더가 없습니다.');
                } else if (result?.status === 'no_credentials' && window.notyf) {
                    window.notyf.error('Google 계정 연동이 필요합니다.');
                }
            } catch (syncError) {
                if (window.notyf) {
                    window.notyf.error('Google 일정 동기화에 실패했습니다.');
                }
            }
        }

        await loadSchedules();

        if (window.notyf) window.notyf.success('최신 일정을 불러왔습니다.');
    } catch (e) {
        console.error('Error refreshing latest:', e);
        if (window.notyf) window.notyf.error('최신 일정 불러오기에 실패했습니다.');
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

        // 모달 열자마자 강제로 캘린더 목록 로드
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

// Handle manage calendar button click
function handleManageCalendar() {
    if (window.CalendarManageModal && window.CalendarManageModal.open) {
        window.CalendarManageModal.open();
    } else if (window.Modal) {
        window.Modal.open('calendarManageModal');
    }
}

// Handle today button
function handleToday() {
    if (calendar) {
        calendar.today();
        currentDate = calendar.getDate(); // ✅ 기준 날짜 갱신
        updateCalendarTitle();            // ✅ 제목 갱신
    }
}

// Handle previous navigation
function handlePrevious() {
    if (calendar) {
        calendar.prev();
        currentDate = calendar.getDate();
        updateCalendarTitle();
    }
}

// Handle next navigation
function handleNext() {
    if (calendar) {
        calendar.next();
        currentDate = calendar.getDate();
        updateCalendarTitle();
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
        currentDate = calendar.getDate();
        updateCalendarTitle();
    }
}

// ✅ 수정 핵심: 달력 제목은 "activeStart"가 아니라 "현재 보고 있는 기준 날짜"로 만든다
function updateCalendarTitle() {
    if (!calendarTitle || !calendar) return;

    const view = calendar.view;
    const base = calendar.getDate(); // ✅ 핵심

    if (viewMode === 'day') {
        const year = base.getFullYear();
        const month = base.getMonth() + 1;
        const day = base.getDate();
        calendarTitle.textContent = `${year}년 ${month}월 ${day}일`;
        return;
    }

    if (viewMode === 'week') {
        const start = view.currentStart; // 주 시작
        const end = new Date(view.currentEnd.getTime() - 24 * 60 * 60 * 1000); // currentEnd는 exclusive라 -1일
        const sY = start.getFullYear();
        const sM = start.getMonth() + 1;
        const sD = start.getDate();
        const eY = end.getFullYear();
        const eM = end.getMonth() + 1;
        const eD = end.getDate();

        if (sY === eY && sM === eM) {
            calendarTitle.textContent = `${sY}년 ${sM}월 ${sD}일 - ${eD}일`;
        } else if (sY === eY) {
            calendarTitle.textContent = `${sY}년 ${sM}월 ${sD}일 - ${eM}월 ${eD}일`;
        } else {
            calendarTitle.textContent = `${sY}년 ${sM}월 ${sD}일 - ${eY}년 ${eM}월 ${eD}일`;
        }
        return;
    }

    // month
    const year = base.getFullYear();
    const month = base.getMonth() + 1;
    calendarTitle.textContent = `${year}년 ${month}월`;
}

// Refresh calendar events
function refreshCalendar() {
    if (calendar) {
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

    filteredSchedules = filteredSchedules.filter(shouldShowSchedule);

    if (filteredSchedules.length === 0) {
        scheduleList.innerHTML = '<div class="empty-state"><p>표시할 일정이 없습니다.</p></div>';
        return;
    }

    filteredSchedules.sort((a, b) => new Date(a.start_datetime) - new Date(b.start_datetime));

    scheduleList.innerHTML = filteredSchedules.map(schedule => {
        const startDate = schedule.start_datetime ? new Date(schedule.start_datetime) : new Date();
        const validStart = !Number.isNaN(startDate.getTime());
        const dateStr = validStart ? startDate.toLocaleDateString('ko-KR', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        }) : '-';
        const timeStr = validStart ? startDate.toLocaleTimeString('ko-KR', {
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        }) : '';
        const isGoogle = schedule.source === 'google';
        const sourceBadge = isGoogle
            ? `<span class="schedule-source-badge"><i class="fa-brands fa-google"></i>Google</span>`
            : '';
        const calendarMeta = schedule.calendar_name
            ? `<div class="schedule-list-meta calendar-name-meta">
                    <i class="fa-regular fa-calendar"></i>
                    <span>${escapeHtml(schedule.calendar_name)}</span>
               </div>`
            : '';

        return `
            <div class="schedule-list-item" data-schedule-id="${schedule.id}" data-source="${schedule.source || 'local'}">
                <div class="schedule-list-header">
                    <div class="schedule-list-title" data-schedule-id="${schedule.id}">
                        <p>${escapeHtml(schedule.title)}</p>
                        <div class="schedule-list-meta">
                            <i class="fas fa-clock"></i>
                            <span>${dateStr} ${timeStr}</span>
                        </div>
                        ${calendarMeta}
                    </div>
                    ${schedule.linked_note ? `<i class="fas fa-file-lines" data-note-id="${schedule.linked_note}"></i>` : ''}
                </div>
                <div class="schedule-list-footer">
                    <div class="schedule-badges">
                        <span class="schedule-type">${schedule.get_type_display || schedule.type || '일정'}</span>
                        ${sourceBadge}
                    </div>
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

                if (visible) {
                    activeCalendarIds.add(String(calendarId));
                } else {
                    activeCalendarIds.delete(String(calendarId));
                }

                userCalendars = userCalendars.map(calendar =>
                    String(calendar.id) === String(calendarId)
                        ? { ...calendar, visible }
                        : calendar
                );

                refreshCalendar();
                renderScheduleList();
            } catch (error) {
                console.error('Error updating calendar visibility:', error);
                e.target.checked = !visible;
                if (window.notyf) {
                    window.notyf.error('캘린더 표시 상태를 변경할 수 없습니다.');
                }
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
            window.location.href = `/notes/detail/?id=${noteId}`;
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

document.addEventListener('calendar:add', async (event) => {
    const detail = event?.detail || {};
    const payload = {
        name: detail.name || '새 캘린더',
        color: detail.color || '#3b82f6',
        visible: detail.visible !== false,
        source_type: detail.source_type || 'local',
        external_id: detail.external_id || null,
    };

    try {
        const response = await fetch('/api/calendars/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            const errorPayload = await response.json().catch(() => ({}));
            throw new Error(errorPayload.error || 'failed_to_create_calendar');
        }

        await loadUserCalendars();
        if (window.notyf) {
            window.notyf.success('캘린더가 생성되었습니다.');
        }
    } catch (error) {
        console.error('Error creating calendar:', error);
        if (window.notyf) {
            window.notyf.error('캘린더 생성에 실패했습니다.');
        }
    }
});

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSchedule);
} else {
    initSchedule();
}

// Invitation Drawer Functions
function initInvitationDrawer() {
    const invitationListBtn = document.getElementById('invitationListBtn');
    const invitationDrawer = document.getElementById('invitationDrawer');
    
    if (!invitationListBtn || !invitationDrawer) return;
    
    invitationListBtn.addEventListener('click', () => {
        invitationDrawer.show();
        loadInvitationsForDrawer();
    });
    
    // Drawer가 열릴 때마다 초대 목록 새로고침
    invitationDrawer.addEventListener('sl-show', () => {
        loadInvitationsForDrawer();
    });
    
    // 초기 로드 시 badge 업데이트
    loadInvitationBadge();
}

async function loadInvitationBadge() {
    const badge = document.getElementById('invitationBadge');
    if (!badge) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/invitations/`);
        if (!response.ok) return;
        
        const data = await response.json();
        const invitations = data.results || [];
        
        if (invitations.length > 0) {
            badge.textContent = invitations.length;
            badge.style.display = 'flex';
        } else {
            badge.style.display = 'none';
        }
    } catch (error) {
        console.error('Error loading invitation badge:', error);
    }
}

async function loadInvitationsForDrawer() {
    const drawerContent = document.getElementById('invitationDrawerContent');
    const drawerEmpty = document.getElementById('invitationDrawerEmpty');
    const drawerCount = document.getElementById('invitationDrawerCount');
    const badge = document.getElementById('invitationBadge');
    
    try {
        const response = await fetch(`${API_BASE}/api/invitations/`);
        if (!response.ok) throw new Error('Failed to load invitations');
        
        const data = await response.json();
        const invitations = data.results || [];
        
        // Count badge 업데이트
        if (badge) {
            if (invitations.length > 0) {
                badge.textContent = invitations.length;
                badge.style.display = 'flex';
            } else {
                badge.style.display = 'none';
            }
        }
        
        // Drawer count 업데이트
        if (drawerCount) {
            drawerCount.textContent = invitations.length;
        }
        
        // Empty state
        if (invitations.length === 0) {
            if (drawerContent) drawerContent.style.display = 'none';
            if (drawerEmpty) drawerEmpty.style.display = 'flex';
            return;
        }
        
        if (drawerContent) drawerContent.style.display = 'block';
        if (drawerEmpty) drawerEmpty.style.display = 'none';
        
        // Render invitations
        if (drawerContent) {
            drawerContent.innerHTML = invitations.map(invitation => {
                const startDate = invitation.schedule_start_date 
                    ? new Date(invitation.schedule_start_date).toLocaleDateString('ko-KR')
                    : '';
                const endDate = invitation.schedule_end_date
                    ? new Date(invitation.schedule_end_date).toLocaleDateString('ko-KR')
                    : '';
                const location = invitation.schedule_location || '';
                
                // 공유자 정보 표시
                const sharerName = invitation.sharer_name || invitation.sharer_id || '알 수 없음';
                const sharerEmail = invitation.sharer_email || '';
                const sharerDisplay = sharerEmail 
                    ? `${escapeHtml(sharerName)} (${escapeHtml(sharerEmail)})`
                    : escapeHtml(sharerName);
                
                return `
                    <div class="invitation-drawer-item" data-invitation-id="${invitation.id}">
                        <div class="invitation-drawer-item-header">
                            <div>
                                <h4 class="invitation-drawer-item-title">${escapeHtml(invitation.schedule_title || '제목 없음')}</h4>
                                <p class="invitation-drawer-item-info">${sharerDisplay}님이 공유했습니다</p>
                            </div>
                        </div>
                        <div class="invitation-drawer-item-details">
                            ${startDate ? `
                                <div class="invitation-drawer-item-detail">
                                    <i class="fa-solid fa-calendar"></i>
                                    <span>${startDate}${endDate && endDate !== startDate ? ` ~ ${endDate}` : ''}</span>
                                </div>
                            ` : ''}
                            ${location ? `
                                <div class="invitation-drawer-item-detail">
                                    <i class="fa-solid fa-location-dot"></i>
                                    <span>${escapeHtml(location)}</span>
                                </div>
                            ` : ''}
                            ${invitation.schedule_description ? `
                                <div class="invitation-drawer-item-detail">
                                    <i class="fa-solid fa-file-lines"></i>
                                    <span>${escapeHtml(invitation.schedule_description)}</span>
                                </div>
                            ` : ''}
                        </div>
                        <div class="invitation-drawer-item-actions">
                            <button class="invitation-drawer-accept-btn" onclick="handleAcceptInvitationFromDrawer(${invitation.id})">
                                수락
                            </button>
                            <button class="invitation-drawer-reject-btn" onclick="handleRejectInvitationFromDrawer(${invitation.id})">
                                거절
                            </button>
                        </div>
                    </div>
                `;
            }).join('');
        }
    } catch (error) {
        console.error('Error loading invitations:', error);
        if (drawerContent) drawerContent.innerHTML = '<p style="color: #ef4444; padding: 1rem;">초대 목록을 불러오는 중 오류가 발생했습니다.</p>';
    }
}

async function handleAcceptInvitationFromDrawer(invitationId) {
    // invitation_accept_modal.js의 함수 사용
    // 여러 방법으로 함수 찾기 시도 (스크립트 로드 순서 문제 대응)
    let openModalFunc = null;
    
    // 1. window.openInvitationAcceptModal 확인
    if (typeof window.openInvitationAcceptModal === 'function') {
        openModalFunc = window.openInvitationAcceptModal;
    } 
    // 2. window.InvitationAcceptModal.open 확인
    else if (typeof window.InvitationAcceptModal !== 'undefined' && typeof window.InvitationAcceptModal.open === 'function') {
        openModalFunc = window.InvitationAcceptModal.open;
    }
    // 3. 약간의 지연 후 다시 시도 (스크립트 로드 지연 대응)
    else {
        // 100ms 후 다시 시도
        await new Promise(resolve => setTimeout(resolve, 100));
        
        if (typeof window.openInvitationAcceptModal === 'function') {
            openModalFunc = window.openInvitationAcceptModal;
        } else if (typeof window.InvitationAcceptModal !== 'undefined' && typeof window.InvitationAcceptModal.open === 'function') {
            openModalFunc = window.InvitationAcceptModal.open;
        }
    }
    
    if (openModalFunc) {
        openModalFunc(invitationId, () => {
            // 수락 후 drawer 새로고침
            loadInvitationsForDrawer();
            loadInvitationBadge();
            
            // SweetAlert2로 성공 메시지 (모달에서 이미 표시할 수도 있지만, 추가로 표시)
            if (typeof window.Swal !== 'undefined') {
                window.Swal.fire({
                    title: '수락 완료',
                    text: '초대를 수락했습니다.',
                    icon: 'success',
                    confirmButtonText: '확인',
                    timer: 2000,
                    timerProgressBar: true
                });
            }
        });
    } else {
        console.error('openInvitationAcceptModal function not found');
        console.log('Debug info:', {
            windowOpenInvitationAcceptModal: typeof window.openInvitationAcceptModal,
            windowInvitationAcceptModal: typeof window.InvitationAcceptModal
        });
        
        // 함수를 찾을 수 없으면 직접 모달 열기 및 초기화
        const modal = document.getElementById('invitationAcceptModal');
        if (modal) {
            // 모달 직접 열기
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
            
            // invitationId 저장 (전역 변수로)
            if (!window.currentInvitationId) {
                window.currentInvitationId = invitationId;
            }
            
            // 모달 이벤트 리스너 설정 (한 번만)
            if (!modal.dataset.initialized) {
                modal.dataset.initialized = 'true';
                
                // 캘린더 목록 로드
                loadCalendarsForInvitationModal();
                
                // 수락 버튼 이벤트
                const acceptBtn = document.getElementById('acceptInvitationBtn');
                if (acceptBtn) {
                    acceptBtn.onclick = async () => {
                        await handleAcceptInvitationDirect(invitationId);
                    };
                }
                
                // 닫기 버튼 이벤트
                const closeBtn = modal.querySelector('.modal-close-btn');
                if (closeBtn) {
                    closeBtn.onclick = () => {
                        modal.classList.remove('active');
                        document.body.style.overflow = '';
                    };
                }
                
                // 취소 버튼 이벤트
                const cancelBtn = modal.querySelector('[data-action="close"]');
                if (cancelBtn) {
                    cancelBtn.onclick = () => {
                        modal.classList.remove('active');
                        document.body.style.overflow = '';
                    };
                }
            }
        } else {
            // 모달이 없으면 에러 메시지
            if (typeof window.Swal !== 'undefined') {
                await window.Swal.fire({
                    title: '오류',
                    text: '초대 수락 기능을 사용할 수 없습니다. 페이지를 새로고침해주세요.',
                    icon: 'error',
                    confirmButtonText: '확인'
                });
            } else {
                alert('초대 수락 기능을 사용할 수 없습니다. 페이지를 새로고침해주세요.');
            }
        }
    }
}

// 캘린더 목록 로드 (모달용)
async function loadCalendarsForInvitationModal() {
    const calendarSelect = document.getElementById('calendarSelect');
    if (!calendarSelect) return;
    
    try {
        const response = await fetch('/api/calendars/', {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
        });
        
        if (response.ok) {
            const data = await response.json();
            // API는 {"results": [...]} 형태로 반환
            const calendars = Array.isArray(data?.results) ? data.results : (Array.isArray(data) ? data : []);
            
            // 구글 캘린더 제외 (source_type이 'google'이 아닌 캘린더만)
            const localCalendars = calendars.filter(cal => {
                return cal.source_type !== 'google' && cal.source_type !== 'GOOGLE';
            });
            
            calendarSelect.innerHTML = '<option value="">캘린더를 선택하세요</option>' +
                localCalendars.map(cal => `
                    <option value="${cal.id}">${escapeHtml(cal.name || '')}</option>
                `).join('');
        } else {
            console.error('Failed to load calendars');
            calendarSelect.innerHTML = '<option value="">캘린더를 불러올 수 없습니다</option>';
        }
    } catch (error) {
        console.error('Error loading calendars:', error);
        calendarSelect.innerHTML = '<option value="">캘린더를 불러올 수 없습니다</option>';
    }
}

// 초대 수락 직접 처리
async function handleAcceptInvitationDirect(invitationId) {
    const calendarSelect = document.getElementById('calendarSelect');
    if (!calendarSelect || !calendarSelect.value) {
        if (typeof window.Swal !== 'undefined') {
            await window.Swal.fire({
                title: '알림',
                text: '캘린더를 선택해주세요.',
                icon: 'warning',
                confirmButtonText: '확인'
            });
        } else {
            alert('캘린더를 선택해주세요.');
        }
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/invitations/${invitationId}/accept/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                calendar_id: parseInt(calendarSelect.value)
            }),
        });
        
        if (response.ok) {
            const data = await response.json();
            
            // 모달 닫기
            const modal = document.getElementById('invitationAcceptModal');
            if (modal) {
                modal.classList.remove('active');
                document.body.style.overflow = '';
            }
            
            // Drawer 새로고침
            loadInvitationsForDrawer();
            loadInvitationBadge();
            
            // 캘린더 새로고침
            if (window.SchedulePage) {
                if (window.SchedulePage.refreshCalendar) {
                    window.SchedulePage.refreshCalendar();
                }
                if (window.SchedulePage.loadSchedules) {
                    window.SchedulePage.loadSchedules();
                }
            }
            
            // SweetAlert2로 성공 메시지
            if (typeof window.Swal !== 'undefined') {
                await window.Swal.fire({
                    title: '수락 완료',
                    text: data.message || '초대를 수락했습니다.',
                    icon: 'success',
                    confirmButtonText: '확인',
                    timer: 2000,
                    timerProgressBar: true
                });
            }
        } else {
            const error = await response.json().catch(() => ({ error: 'Unknown error' }));
            if (typeof window.Swal !== 'undefined') {
                await window.Swal.fire({
                    title: '오류',
                    text: error.error || '초대 수락에 실패했습니다.',
                    icon: 'error',
                    confirmButtonText: '확인'
                });
            } else {
                alert(error.error || '초대 수락에 실패했습니다.');
            }
        }
    } catch (error) {
        console.error('Error accepting invitation:', error);
        if (typeof window.Swal !== 'undefined') {
            await window.Swal.fire({
                title: '오류',
                text: '초대 수락 중 오류가 발생했습니다.',
                icon: 'error',
                confirmButtonText: '확인'
            });
        } else {
            alert('초대 수락 중 오류가 발생했습니다.');
        }
    }
}

async function handleRejectInvitationFromDrawer(invitationId) {
    // SweetAlert2로 확인
    if (typeof window.Swal === 'undefined') {
        // SweetAlert가 없으면 기본 confirm 사용
        if (!confirm('초대를 거절하시겠습니까?')) return;
    } else {
        const result = await window.Swal.fire({
            title: '초대 거절',
            text: '정말로 이 초대를 거절하시겠습니까?',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#ef4444',
            cancelButtonColor: '#6b7280',
            confirmButtonText: '거절',
            cancelButtonText: '취소',
            reverseButtons: true
        });
        
        if (!result.isConfirmed) {
            return;
        }
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/invitations/${invitationId}/reject/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || 'Failed to reject invitation');
        }
        
        // Drawer 새로고침
        loadInvitationsForDrawer();
        loadInvitationBadge();
        
        // SweetAlert2로 성공 메시지
        if (typeof window.Swal !== 'undefined') {
            await window.Swal.fire({
                title: '거절 완료',
                text: '초대를 거절했습니다.',
                icon: 'success',
                confirmButtonText: '확인',
                timer: 2000,
                timerProgressBar: true
            });
        } else if (typeof notyf !== 'undefined') {
            notyf.success('초대를 거절했습니다.');
        }
    } catch (error) {
        console.error('Error rejecting invitation:', error);
        
        // SweetAlert2로 에러 메시지
        if (typeof window.Swal !== 'undefined') {
            await window.Swal.fire({
                title: '오류',
                text: error.message || '초대 거절 중 오류가 발생했습니다.',
                icon: 'error',
                confirmButtonText: '확인'
            });
        } else if (typeof notyf !== 'undefined') {
            notyf.error(error.message || '초대 거절 중 오류가 발생했습니다.');
        }
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.SchedulePage = {
        initSchedule,
        loadInvitationBadge,
        loadSchedules,
        refreshCalendar,
        reloadCalendars: loadUserCalendars,
        setViewMode,
        handleToday,
        handlePrevious,
        handleNext,
        handleRefreshLatest, // ✅ 추가
    };
}
