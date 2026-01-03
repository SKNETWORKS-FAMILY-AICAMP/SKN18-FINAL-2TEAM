// Schedule Detail Modal Component JavaScript Logic

// State variables
let selectedScheduleData = null;

// DOM elements
const modalId = 'scheduleDetailModal';
const scheduleTitle = document.getElementById('scheduleTitle');
const scheduleTypeBadge = document.getElementById('scheduleTypeBadge');
const scheduleStatusSelect = document.getElementById('scheduleStatusSelect');
const scheduleDateTime = document.getElementById('scheduleDateTime');
const scheduleLocation = document.getElementById('scheduleLocation');
const scheduleDescription = document.getElementById('scheduleDescription');
const linkedNoteBtn = document.getElementById('linkedNoteBtn');
const scheduleEditBtn = document.getElementById('scheduleEditBtn');
const scheduleShareAddBtn = document.getElementById('scheduleShareAddBtn');
const scheduleShareEmptyBtn = document.getElementById('scheduleShareEmptyBtn');
const scheduleSharedList = document.getElementById('scheduleSharedList');
const scheduleSharedEmpty = document.getElementById('scheduleSharedEmpty');
const sharedCount = document.getElementById('sharedCount');

// Initialize modal
function initScheduleDetailModal() {
    console.log('[ScheduleDetailModal] initScheduleDetailModal called');
    const modal = document.getElementById(modalId);
    if (!modal) {
        console.error(`[ScheduleDetailModal] Modal with ID "${modalId}" not found`);
        return;
    }
    
    console.log('[ScheduleDetailModal] Modal found, setting up event listeners');
    
    // Status change handler
    if (scheduleStatusSelect) {
        scheduleStatusSelect.addEventListener('change', handleStatusChange);
    }
    
    // Linked note button
    if (linkedNoteBtn) {
        linkedNoteBtn.addEventListener('click', handleLinkedNoteClick);
    }
    
    // Edit button
    if (scheduleEditBtn) {
        scheduleEditBtn.addEventListener('click', handleEditClick);
    }
    
    // Share buttons
    if (scheduleShareAddBtn) {
        scheduleShareAddBtn.addEventListener('click', handleShareClick);
    }
    if (scheduleShareEmptyBtn) {
        scheduleShareEmptyBtn.addEventListener('click', handleShareClick);
    }
    
    // Modal events - use document level listener to catch all modal:open events
    document.addEventListener('modal:open', handleModalOpen);
    document.addEventListener('modal:close', handleModalClose);
    
    console.log('[ScheduleDetailModal] Event listeners attached');
}

// Handle modal open
function handleModalOpen(e) {
    console.log('[ScheduleDetailModal] handleModalOpen called', { 
        modalId: e.detail.modalId, 
        detail: e.detail,
        selectedScheduleData 
    });
    
    if (e.detail.modalId !== modalId) {
        console.log('[ScheduleDetailModal] Modal ID mismatch, ignoring');
        return;
    }
    
    // Get schedule ID from event detail or selectedScheduleData
    const scheduleId = e.detail.scheduleId || (selectedScheduleData && selectedScheduleData.id);
    console.log('[ScheduleDetailModal] Schedule ID:', scheduleId);
    
    if (scheduleId) {
        // Set selectedScheduleData if not already set
        if (!selectedScheduleData || selectedScheduleData.id !== scheduleId) {
            selectedScheduleData = { id: scheduleId };
            console.log('[ScheduleDetailModal] Set selectedScheduleData:', selectedScheduleData);
        }
        loadScheduleDetail();
    } else if (selectedScheduleData && selectedScheduleData.id) {
        console.log('[ScheduleDetailModal] Using existing selectedScheduleData');
        loadScheduleDetail();
    } else {
        console.error('[ScheduleDetailModal] Schedule ID not provided');
    }
}

// Handle modal close
function handleModalClose(e) {
    if (e.detail.modalId !== modalId) return;
    selectedScheduleData = null;
}

// Load schedule detail
async function loadScheduleDetail() {
    console.log('[ScheduleDetailModal] loadScheduleDetail called', { selectedScheduleData });
    
    if (!selectedScheduleData || !selectedScheduleData.id) {
        console.error('[ScheduleDetailModal] No schedule ID provided', { selectedScheduleData });
        return;
    }
    
    const scheduleId = selectedScheduleData.id;
    console.log('[ScheduleDetailModal] Loading schedule detail for ID:', scheduleId);
    
    const apiUrl = `/schedule/api/schedules/${scheduleId}/`;
    console.log('[ScheduleDetailModal] API URL:', apiUrl);
    
    try {
        const response = await fetch(apiUrl, {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
        });
        
        console.log('[ScheduleDetailModal] API Response status:', response.status);
        
        if (response.ok) {
            const schedule = await response.json();
            console.log('[ScheduleDetailModal] Schedule data received:', schedule);
            renderScheduleDetail(schedule);
        } else {
            const error = await response.json().catch(() => ({ error: 'Unknown error' }));
            console.error('[ScheduleDetailModal] Failed to load schedule detail:', error);
            if (window.notyf) {
                window.notyf.error('일정을 불러오는데 실패했습니다.');
            }
        }
    } catch (error) {
        console.error('[ScheduleDetailModal] Error loading schedule detail:', error);
        if (window.notyf) {
            window.notyf.error('일정을 불러오는 중 오류가 발생했습니다.');
        }
    }
}

// Render schedule detail
function renderScheduleDetail(schedule) {
    selectedScheduleData = schedule;
    
    // Title and type
    if (scheduleTitle) {
        scheduleTitle.textContent = schedule.title || '';
    }
    if (scheduleTypeBadge) {
        scheduleTypeBadge.textContent = schedule.get_type_display || schedule.type || '일정';
    }
    
    // Status
    if (scheduleStatusSelect) {
        scheduleStatusSelect.value = schedule.status || 'scheduled';
        scheduleStatusSelect.className = `schedule-status-select status-${schedule.status || 'scheduled'}`;
    }
    
    // Date and time
    if (scheduleDateTime) {
        const isAllDay = schedule.is_all_day === true || schedule.is_all_day === 'Y';
        if (schedule.start_datetime) {
            if (isAllDay) {
                const startDateRaw = (schedule.start_datetime || '').split('T')[0];
                const endDateRaw = (schedule.end_datetime || schedule.start_datetime || '').split('T')[0];
                const startDisplay = formatDateOnlyFromISO(startDateRaw);
                const endDisplay = formatDateOnlyFromISO(endDateRaw);

                if (startDisplay && endDisplay && startDisplay !== endDisplay) {
                    scheduleDateTime.textContent = `${startDisplay} ~ ${endDisplay} · 하루 종일`;
                } else if (startDisplay) {
                    scheduleDateTime.textContent = `${startDisplay} · 하루 종일`;
                } else {
                    scheduleDateTime.textContent = '날짜 정보 없음';
                }
            } else {
                const startDate = new Date(schedule.start_datetime);
                const endDate = schedule.end_datetime ? new Date(schedule.end_datetime) : null;

                const startDateStr = startDate.toLocaleDateString('ko-KR', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                });
                const endDateStr = endDate
                    ? endDate.toLocaleDateString('ko-KR', {
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit',
                      })
                    : '';

                const startTimeStr = startDate.toLocaleTimeString('ko-KR', {
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: false,
                });
                const endTimeStr = endDate
                    ? endDate.toLocaleTimeString('ko-KR', {
                        hour: '2-digit',
                        minute: '2-digit',
                        hour12: false,
                      })
                    : '';
                const endSegment = endDate
                    ? `${endDateStr} ${endTimeStr}`.trim()
                    : '';
                const startSegment = `${startDateStr} ${startTimeStr}`.trim();
                scheduleDateTime.textContent = endSegment
                    ? `${startSegment} ~ ${endSegment}`
                    : startSegment;
            }
        } else {
            scheduleDateTime.textContent = '날짜 정보 없음';
        }
    }
    
    // Location
    if (scheduleLocation) {
        scheduleLocation.textContent = schedule.location || '장소 정보 없음';
    }
    
    // Description
    if (scheduleDescription) {
        scheduleDescription.textContent = schedule.description || '설명 없음';
    }
    
    // Linked note
    if (linkedNoteBtn) {
        if (schedule.linked_note) {
            linkedNoteBtn.style.display = 'flex';
            const noteId = schedule.linked_note.id || schedule.linked_note;
            linkedNoteBtn.setAttribute('data-note-id', noteId);
        } else {
            linkedNoteBtn.style.display = 'none';
        }
    }
    
    // Shared users - load from API if not in schedule data
    if (schedule.shared_with && schedule.shared_with.length > 0) {
        renderSharedUsers(schedule.shared_with);
    } else {
        // Try to load shared users from API
        loadSharedUsers(schedule.id);
    }
}

// Load shared users
async function loadSharedUsers(scheduleId) {
    try {
        const response = await fetch(`/schedule/api/schedules/${scheduleId}/shared/`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
        });
        
        if (response.ok) {
            const data = await response.json();
            renderSharedUsers(data.results || data || []);
        } else {
            renderSharedUsers([]);
        }
    } catch (error) {
        console.error('Error loading shared users:', error);
        renderSharedUsers([]);
    }
}

// Render shared users
function renderSharedUsers(sharedUsers) {
    if (!scheduleSharedList || !scheduleSharedEmpty || !sharedCount) return;
    
    if (sharedUsers.length === 0) {
        scheduleSharedList.style.display = 'none';
        scheduleSharedEmpty.style.display = 'flex';
        sharedCount.textContent = '0';
    } else {
        scheduleSharedList.style.display = 'block';
        scheduleSharedEmpty.style.display = 'none';
        sharedCount.textContent = sharedUsers.length.toString();
        
        scheduleSharedList.innerHTML = sharedUsers.map((user, index) => `
            <div class="schedule-shared-item">
                <p class="schedule-shared-name">${escapeHtml(user.name || user.email || user.username || 'Unknown')}</p>
                <p class="schedule-shared-email">${escapeHtml(user.email || '')}</p>
            </div>
        `).join('');
    }
}

// Handle status change
async function handleStatusChange(e) {
    if (!selectedScheduleData) return;
    
    const newStatus = e.target.value;
    
    try {
        const response = await fetch(`/schedule/api/schedules/${selectedScheduleData.id}/`, {
            method: 'PATCH',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ status: newStatus }),
        });
        
        if (response.ok) {
            const statusText = {
                'scheduled': '예정',
                'in_progress': '진행중',
                'completed': '완료'
            }[newStatus] || newStatus;
            
            if (window.notyf) {
                window.notyf.success(`일정 상태가 "${statusText}"으로 변경되었습니다.`);
            }
            
            // Update local data
            selectedScheduleData.status = newStatus;
            e.target.className = `schedule-status-select status-${newStatus}`;
            
            // Refresh calendar and schedule list
            if (window.SchedulePage) {
                if (window.SchedulePage.refreshCalendar) {
                    window.SchedulePage.refreshCalendar();
                }
                if (window.SchedulePage.loadSchedules) {
                    window.SchedulePage.loadSchedules();
                }
            }
        } else {
            const error = await response.json();
            console.error('Failed to update status:', error);
            if (window.notyf) {
                window.notyf.error('상태 변경에 실패했습니다.');
            }
            // Revert select value
            e.target.value = selectedScheduleData.status || 'scheduled';
        }
    } catch (error) {
        console.error('Error updating status:', error);
        if (window.notyf) {
            window.notyf.error('상태 변경 중 오류가 발생했습니다.');
        }
    }
}

// Handle linked note click
function handleLinkedNoteClick() {
    if (!selectedScheduleData || !selectedScheduleData.linked_note) return;
    
    const noteId = linkedNoteBtn.getAttribute('data-note-id');
    if (noteId) {
        window.location.href = `/notes/detail/?id=${noteId}`;
    }
}

// Handle edit click
function handleEditClick() {
    if (!selectedScheduleData) return;
    window.location.href = `/schedule/${selectedScheduleData.id}/edit/`;
}

// Handle share click
function handleShareClick() {
    console.log('[ScheduleDetailModal] handleShareClick called');
    console.log('[ScheduleDetailModal] window.ShareModal:', window.ShareModal);
    console.log('[ScheduleDetailModal] window.ShareModal.open:', window.ShareModal ? window.ShareModal.open : 'undefined');
    console.log('[ScheduleDetailModal] selectedScheduleData:', selectedScheduleData);
    
    if (window.ShareModal && window.ShareModal.open) {
        console.log('[ScheduleDetailModal] Opening ShareModal...');
        // 공유 완료시 콜백
        window.ShareModal.onShare = (selectedMembers) => {
            // Refresh shared users after sharing
            if (selectedScheduleData && selectedScheduleData.id) {
                loadSharedUsers(selectedScheduleData.id);
            }
        };
        // context를 'schedule'로 지정하여 일정 공유로 처리
        window.ShareModal.open(selectedScheduleData ? selectedScheduleData.id : null, null, null, '일정 공유', 'schedule');
    } else {
        console.warn('ShareModal not loaded. Please refresh the page.');
        if (window.notyf) {
            window.notyf.error('공유 모달을 로드할 수 없습니다. 페이지를 새로고침해주세요.');
        }
    }
}

// Open modal with schedule data
function openScheduleDetailModal(scheduleId) {
    console.log('[ScheduleDetailModal] openScheduleDetailModal called with scheduleId:', scheduleId);
    
    if (!scheduleId) {
        console.error('[ScheduleDetailModal] Schedule ID is required');
        if (window.notyf) {
            window.notyf.error('일정 ID가 필요합니다.');
        }
        return;
    }
    
    // Set selectedScheduleData before opening modal
    selectedScheduleData = { id: scheduleId };
    console.log('[ScheduleDetailModal] Set selectedScheduleData:', selectedScheduleData);
    
    // Open modal using Modal utility with scheduleId in options
    if (window.Modal && typeof window.Modal.open === 'function') {
        console.log('[ScheduleDetailModal] Opening modal via window.Modal.open');
        window.Modal.open(modalId, { scheduleId: scheduleId });
    } else {
        console.log('[ScheduleDetailModal] Fallback: opening modal directly');
        // Fallback: dispatch custom event directly
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
            const event = new CustomEvent('modal:open', {
                detail: { modalId: modalId, scheduleId: scheduleId }
            });
            console.log('[ScheduleDetailModal] Dispatching modal:open event:', event.detail);
            document.dispatchEvent(event);
        } else {
            console.error(`[ScheduleDetailModal] Modal with ID "${modalId}" not found`);
        }
    }
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
    const metaTag = document.querySelector('meta[name=csrf-token]');
    if (metaTag) {
        return metaTag.getAttribute('content');
    }
    return '';
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDateOnlyFromISO(dateString) {
    if (!dateString) return '';
    const [year, month, day] = dateString.split('-');
    if (!year || !month || !day) return dateString || '';
    const localDate = new Date(`${year}-${month}-${day}T00:00:00`);
    return localDate.toLocaleDateString('ko-KR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
    });
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initScheduleDetailModal);
} else {
    initScheduleDetailModal();
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.ScheduleDetailModal = {
        open: openScheduleDetailModal,
        init: initScheduleDetailModal,
    };
}
