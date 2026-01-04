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
    
    // 공유받은 일정인 경우 수정/삭제 버튼 비활성화
    const isSharedCopy = schedule.is_shared_copy || false;
    if (scheduleEditBtn) {
        if (isSharedCopy) {
            scheduleEditBtn.disabled = true;
            scheduleEditBtn.style.opacity = '0.5';
            scheduleEditBtn.style.cursor = 'not-allowed';
            scheduleEditBtn.title = '공유받은 일정은 수정할 수 없습니다';
        } else {
            scheduleEditBtn.disabled = false;
            scheduleEditBtn.style.opacity = '1';
            scheduleEditBtn.style.cursor = 'pointer';
            scheduleEditBtn.title = '';
        }
    }
    
    // 공유받은 일정 표시
    if (isSharedCopy && scheduleTitle) {
        const sharedBadge = document.createElement('span');
        sharedBadge.className = 'schedule-shared-badge';
        sharedBadge.textContent = '공유받은 일정';
        sharedBadge.style.cssText = 'font-size: 0.75rem; color: #6b7280; margin-left: 0.5rem;';
        if (!scheduleTitle.querySelector('.schedule-shared-badge')) {
            scheduleTitle.appendChild(sharedBadge);
        }
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
            // API 응답에서 소유자 정보와 현재 사용자 ID 저장
            if (data.is_owner !== undefined) {
                if (selectedScheduleData) {
                    selectedScheduleData.is_owner = data.is_owner;
                    selectedScheduleData.current_user_id = data.current_user_id;
                    selectedScheduleData.schedule_owner_id = data.schedule_owner_id;
                }
            }
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
        
        // 현재 사용자 ID와 소유자 정보 확인
        const currentUserId = selectedScheduleData?.current_user_id || getCurrentUserId();
        const isOwner = selectedScheduleData?.is_owner || (selectedScheduleData && selectedScheduleData.created_id === currentUserId);
        
        scheduleSharedList.innerHTML = sharedUsers.map((user, index) => {
            const userId = user.user_id || user.email || user.id;
            const isCurrentUser = userId === currentUserId;
            
            // 내 일정인 경우: 공유 제거 버튼
            // 내 일정이 아닌 경우: 자신에게만 일정 나가기 버튼 표시
            let actionButton = '';
            if (isOwner) {
                // 소유자: 모든 공유자에 대해 공유 제거 버튼
                actionButton = `
                    <button 
                        class="schedule-shared-remove-btn" 
                        data-user-id="${escapeHtml(userId)}"
                        title="공유 제거"
                    >
                        <i class="fa-solid fa-times"></i>
                    </button>
                `;
            } else if (isCurrentUser) {
                // 공유된 사용자: 자신에게만 일정 나가기 버튼
                actionButton = `
                    <button 
                        class="schedule-shared-leave-btn" 
                        title="일정에서 나가기"
                    >
                        <i class="fa-solid fa-sign-out-alt"></i>
                        <span>나가기</span>
                    </button>
                `;
            }
            
            return `
                <div class="schedule-shared-item">
                    <div class="schedule-shared-info">
                        <p class="schedule-shared-name">${escapeHtml(user.name || user.email || user.username || 'Unknown')}</p>
                        <p class="schedule-shared-email">${escapeHtml(user.email || userId || '')}</p>
                    </div>
                    ${actionButton}
                </div>
            `;
        }).join('');
        
        // 공유 제거 버튼 이벤트 리스너
        const removeBtns = scheduleSharedList.querySelectorAll('.schedule-shared-remove-btn');
        removeBtns.forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const userId = btn.getAttribute('data-user-id');
                await handleRemoveShare(userId);
            });
        });
        
        // 일정 나가기 버튼 이벤트 리스너
        const leaveBtn = scheduleSharedList.querySelector('.schedule-shared-leave-btn');
        if (leaveBtn) {
            leaveBtn.addEventListener('click', async (e) => {
                e.stopPropagation();
                await handleLeaveSchedule();
            });
        }
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

// Handle remove share (소유자가 공유 제거)
async function handleRemoveShare(userId) {
    if (!selectedScheduleData || !selectedScheduleData.id) return;
    
    // Confirm removal
    let confirmed = false;
    if (window.Swal) {
        const result = await window.Swal.fire({
            title: '공유 제거',
            text: '이 사용자와의 공유를 제거하시겠습니까?',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: '제거',
            cancelButtonText: '취소',
            confirmButtonColor: '#ef4444',
            cancelButtonColor: '#6b7280',
        });
        confirmed = result.isConfirmed;
    } else {
        confirmed = confirm('이 사용자와의 공유를 제거하시겠습니까?');
    }
    
    if (!confirmed) return;
    
    try {
        const response = await fetch(`/schedule/api/schedules/${selectedScheduleData.id}/shared/?user_id=${encodeURIComponent(userId)}`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
        });
        
        if (response.ok) {
            const data = await response.json();
            if (window.notyf) {
                window.notyf.success(data.message || '공유가 제거되었습니다.');
            }
            // Refresh shared users
            await loadSharedUsers(selectedScheduleData.id);
        } else {
            const error = await response.json().catch(() => ({ error: 'Unknown error' }));
            if (window.notyf) {
                window.notyf.error(error.error || '공유 제거에 실패했습니다.');
            }
        }
    } catch (error) {
        console.error('Error removing share:', error);
        if (window.notyf) {
            window.notyf.error('공유 제거 중 오류가 발생했습니다.');
        }
    }
}

// Handle leave schedule (공유된 사용자가 일정에서 나가기)
async function handleLeaveSchedule() {
    if (!selectedScheduleData || !selectedScheduleData.id) return;
    
    // Confirm leaving
    let confirmed = false;
    if (window.Swal) {
        const result = await window.Swal.fire({
            title: '일정에서 나가기',
            text: '이 일정에서 나가시겠습니까?',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: '나가기',
            cancelButtonText: '취소',
            confirmButtonColor: '#ef4444',
            cancelButtonColor: '#6b7280',
        });
        confirmed = result.isConfirmed;
    } else {
        confirmed = confirm('이 일정에서 나가시겠습니까?');
    }
    
    if (!confirmed) return;
    
    try {
        const response = await fetch(`/schedule/api/schedules/${selectedScheduleData.id}/shared/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
        });
        
        if (response.ok) {
            const data = await response.json();
            if (window.notyf) {
                window.notyf.success(data.message || '일정에서 나갔습니다.');
            }
            // Close modal and refresh calendar
            if (window.Modal && window.Modal.close) {
                window.Modal.close(modalId);
            }
            if (window.SchedulePage) {
                if (window.SchedulePage.refreshCalendar) {
                    window.SchedulePage.refreshCalendar();
                }
                if (window.SchedulePage.loadSchedules) {
                    window.SchedulePage.loadSchedules();
                }
            }
        } else {
            const error = await response.json().catch(() => ({ error: 'Unknown error' }));
            if (window.notyf) {
                window.notyf.error(error.error || '일정에서 나가기에 실패했습니다.');
            }
        }
    } catch (error) {
        console.error('Error leaving schedule:', error);
        if (window.notyf) {
            window.notyf.error('일정에서 나가는 중 오류가 발생했습니다.');
        }
    }
}

// Get current user ID
function getCurrentUserId() {
    // 여러 방법으로 현재 사용자 ID 가져오기 시도
    // 1. 메타 태그에서 가져오기
    const metaUserId = document.querySelector('meta[name=user-id]');
    if (metaUserId) {
        return metaUserId.getAttribute('content');
    }
    
    // 2. 전역 변수에서 가져오기
    if (window.currentUser && window.currentUser.user_id) {
        return window.currentUser.user_id;
    }
    
    // 3. 일정 데이터에서 created_id와 비교하여 추론
    // (임시 방법)
    return null;
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
