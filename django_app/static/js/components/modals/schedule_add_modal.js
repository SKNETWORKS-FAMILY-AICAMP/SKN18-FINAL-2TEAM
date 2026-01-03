// Schedule Add Modal Component JavaScript Logic
(function() {
  'use strict';

  const API_BASE = '/schedule';

  let noteSearchQuery = '';
  let showNoteDropdown = false;
  let selectedNoteId = null;
  let sharedEmails = [];
  let prefillDate = null;

  let availableCalendarsForSelect = [];

  let customRepeatInterval = 1;
  let customRepeatUnit = 'week';
  let selectedWeekDays = [];
  let repeatEndType = 'never';
  let repeatEndDate = '';
  let repeatEndCount = 10;

  // DOM elements
  const modalId = 'scheduleAddModal';
  const scheduleAddForm = document.getElementById('scheduleAddForm');
  const scheduleTitleInput = document.getElementById('scheduleTitleInput');
  const scheduleDescriptionInput = document.getElementById('scheduleDescriptionInput');
  const scheduleLocationInput = document.getElementById('scheduleLocationInput');
  const scheduleNoteSearchInput = document.getElementById('scheduleNoteSearchInput');
  const scheduleNoteDropdown = document.getElementById('scheduleNoteDropdown');
  const scheduleLinkedNoteId = document.getElementById('scheduleLinkedNoteId');
  const scheduleIsAllDay = document.getElementById('scheduleIsAllDay');
  const scheduleStartDate = document.getElementById('scheduleStartDate');
  const scheduleStartTime = document.getElementById('scheduleStartTime');
  const scheduleEndDate = document.getElementById('scheduleEndDate');
  const scheduleEndTime = document.getElementById('scheduleEndTime');
  const scheduleRepeatSelect = document.getElementById('scheduleRepeatSelect');
  const scheduleTypeSelect = document.getElementById('scheduleTypeSelect');
  const scheduleStatusSelectAdd = document.getElementById('scheduleStatusSelectAdd');
  const scheduleAddShareBtn = document.getElementById('scheduleAddShareBtn');
  const sharedEmailsDisplay = document.getElementById('sharedEmailsDisplay');
  const sharedEmailsCount = document.getElementById('sharedEmailsCount');
  const scheduleAddSaveBtn = document.getElementById('scheduleAddSaveBtn');
  const scheduleNotificationSelect = document.getElementById('scheduleNotificationSelect');
  const scheduleCustomRepeatPanel = document.getElementById('scheduleCustomRepeatPanel');
  const scheduleAddGrid = document.getElementById('scheduleAddGrid');
  const scheduleAddModalContainer = document.getElementById('scheduleAddModalContainer');
  const customRepeatIntervalInput = document.getElementById('customRepeatInterval');
  const customRepeatUnitSelect = document.getElementById('customRepeatUnit');
  const weekDaysSelection = document.getElementById('weekDaysSelection');
  const weekDayButtons = document.querySelectorAll('.week-day-btn');
  const repeatEndRadios = document.querySelectorAll('input[name="repeatEnd"]');
  const repeatEndDateInput = document.getElementById('repeatEndDate');
  const repeatEndCountInput = document.getElementById('repeatEndCount');
  const customRepeatSummary = document.getElementById('customRepeatSummary');
  const calendarAddInlineBtn = document.getElementById('openCalendarAddInlineBtn');

  // ✅ 이거 하나만 선언 (중복 금지)
  const targetCalendarSelect = document.getElementById('targetCalendarSelect');

  let allNotes = [];

// Initialize modal
  function initScheduleAddModal() {
    // Form submission
    if (scheduleAddForm) {
      scheduleAddForm.addEventListener('submit', handleFormSubmit);
    }

    if (scheduleNoteSearchInput) {
      scheduleNoteSearchInput.addEventListener('input', handleNoteSearch);
      scheduleNoteSearchInput.addEventListener('focus', () => {
        if (scheduleNoteSearchInput.value.length > 0) {
          // 입력값이 있으면 → 드롭다운 표시
          showNoteDropdown = true;
          renderNoteDropdown();
        } else if (allNotes.length > 0) {
          // 입력값이 비어있고 노트가 이미 로드됨 → 전체 노트 표시
          noteSearchQuery = '';
          showNoteDropdown = true;
          renderNoteDropdown();
        } else {
          // 노트가 아직 로드되지 않은 경우 → 드롭다운 표시 안 함
          showNoteDropdown = false;
        }
      });
    }

    // All day checkbox
    if (scheduleIsAllDay) {
      scheduleIsAllDay.addEventListener('change', handleAllDayChange);
    }

    // Repeat select change
    if (scheduleRepeatSelect) {
      scheduleRepeatSelect.addEventListener('change', handleRepeatTypeChange);
    }

    // Custom repeat settings
    if (customRepeatIntervalInput) {
        customRepeatIntervalInput.addEventListener('input', handleCustomRepeatChange);
    }
    if (customRepeatUnitSelect) {
        customRepeatUnitSelect.addEventListener('change', handleCustomRepeatChange);
    }
    if (weekDayButtons) {
        weekDayButtons.forEach(btn => {
            btn.addEventListener('click', handleWeekDayToggle);
        });
    }
    if (repeatEndRadios) {
        repeatEndRadios.forEach(radio => {
            radio.addEventListener('change', handleRepeatEndChange);
        });
    }
    if (repeatEndDateInput) {
        repeatEndDateInput.addEventListener('change', updateCustomRepeatSummary);
    }
    if (repeatEndCountInput) {
        repeatEndCountInput.addEventListener('input', updateCustomRepeatSummary);
    }

    // Share button
    if (scheduleAddShareBtn) {
        scheduleAddShareBtn.addEventListener('click', handleShareClick);
    }

    // save
    if (scheduleAddSaveBtn) scheduleAddSaveBtn.addEventListener('click', handleSaveClick);

    // ✅ 모달 이벤트: "modal element"가 아니라 document에서 잡자 (핵심)
    document.addEventListener('modal:open', handleModalOpen, true);
    document.addEventListener('modal:close', handleModalClose, true);

    // ✅ select 클릭/포커스 때도 다시 로드 (모달 이벤트가 안 잡혀도 커버)
    if (targetCalendarSelect) {
      targetCalendarSelect.addEventListener('focus', loadUserCalendarsForTargetSelect);
      targetCalendarSelect.addEventListener('click', loadUserCalendarsForTargetSelect);
    }

    // click outside dropdown
    document.addEventListener('click', (e) => {
      if (scheduleNoteSearchInput && scheduleNoteDropdown) {
            if (!scheduleNoteSearchInput.contains(e.target) && 
                !scheduleNoteDropdown.contains(e.target)) {
        showNoteDropdown = false;
        scheduleNoteDropdown.style.display = 'none';
      }
     }
    });

    document.addEventListener('calendar:add', async () => {
      await loadUserCalendarsForTargetSelect();
    });

    if (calendarAddInlineBtn) {
      calendarAddInlineBtn.addEventListener('click', () => {
        if (window.CalendarAddModal && window.CalendarAddModal.open) {
          window.CalendarAddModal.open();
        } else if (window.Modal) {
          window.Modal.open('calendarAddModal');
        }
      });
    }

    loadUserCalendarsForTargetSelect();
    loadNotes();
  }

  async function loadUserCalendarsForTargetSelect() {
    if (!targetCalendarSelect) return;

    try {
      const res = await fetch('/api/calendars/', {
        method: 'GET',
        credentials: 'same-origin',
        headers: {
          'X-CSRFToken': getCsrfToken(),
          'Content-Type': 'application/json',
        },
      });

      if (!res.ok) {
        availableCalendarsForSelect = [];
      } else {
        const data = await res.json();
        availableCalendarsForSelect = Array.isArray(data?.results) ? data.results : (Array.isArray(data) ? data : []);
      }
    } catch (err) {
      console.error('[ScheduleAddModal] user calendar fetch error:', err);
      availableCalendarsForSelect = [];
    }

    renderTargetCalendarOptions();
  }

  function renderTargetCalendarOptions() {
    if (!targetCalendarSelect) return;

    targetCalendarSelect.innerHTML = '';

    if (!availableCalendarsForSelect.length) {
      const placeholder = document.createElement('option');
      placeholder.value = '';
      placeholder.textContent = '등록된 캘린더가 없습니다';
      targetCalendarSelect.appendChild(placeholder);
      targetCalendarSelect.disabled = true;
      return;
    }

    targetCalendarSelect.disabled = false;

    availableCalendarsForSelect.forEach((calendar, index) => {
      const opt = document.createElement('option');
      opt.value = calendar.id;
      opt.textContent = calendar.source_type === 'google'
        ? `${calendar.name || 'Google Calendar'} (Google)`
        : (calendar.name || '내 캘린더');
      if (index === 0) {
        opt.selected = true;
      }
      targetCalendarSelect.appendChild(opt);
    });
  }

  function handleModalOpen(e) {
    // ✅ e.detail.modalId 기반이면 그대로, 아니면 fallback
    const openedId = e?.detail?.modalId;
    if (openedId && openedId !== modalId) return;

    console.log('[ScheduleAddModal] modal open detected:', openedId);

    // 항상 초기화 먼저
    resetForm();

    const urlParams = new URLSearchParams(window.location.search);
    const dateParam = urlParams.get('date') || prefillDate;

    if (dateParam) {
      prefillDate = dateParam;
      if (scheduleIsAllDay) {
        scheduleIsAllDay.checked = true;
        handleAllDayChange({ target: scheduleIsAllDay });
      }
      if (scheduleStartDate) {
        scheduleStartDate.value = dateParam;
      }
      if (scheduleEndDate) {
        scheduleEndDate.value = dateParam;
      }
      if (scheduleStartTime) scheduleStartTime.value = '';
      if (scheduleEndTime) scheduleEndTime.value = '';
    } else {
      if (scheduleIsAllDay) {
        scheduleIsAllDay.checked = false;
        handleAllDayChange({ target: scheduleIsAllDay });
      }

      const now = new Date();
      const start = new Date(now.getTime() + 60 * 60 * 1000);
      const end = new Date(start.getTime() + 60 * 60 * 1000);

      const startDateStr = start.toISOString().split('T')[0];
      const endDateStr = end.toISOString().split('T')[0];
      const startTimeStr = start.toTimeString().slice(0, 5);
      const endTimeStr = end.toTimeString().slice(0, 5);

      if (scheduleStartDate) scheduleStartDate.value = startDateStr;
      if (scheduleEndDate) scheduleEndDate.value = endDateStr;
      if (scheduleStartTime) scheduleStartTime.value = startTimeStr;
      if (scheduleEndTime) scheduleEndTime.value = endTimeStr;
    }

    if (scheduleIsAllDay && !scheduleIsAllDay.checked) {
      handleAllDayChange({ target: scheduleIsAllDay });
    }

    if (scheduleRepeatSelect) handleRepeatTypeChange({ target: scheduleRepeatSelect });
    updateCustomRepeatSummary();

    // ✅ 여기서도 로드
    loadUserCalendarsForTargetSelect();
  }

  function handleModalClose(e) {
    const closedId = e?.detail?.modalId;
    if (closedId && closedId !== modalId) return;
    resetForm();
    prefillDate = null;
  }

  // Reset form
  function resetForm() {
    if (scheduleAddForm) {
        scheduleAddForm.reset();
    }
    noteSearchQuery = '';
    showNoteDropdown = false;
    selectedNoteId = null;
    sharedEmails = [];

    // Reset custom repeat state
    customRepeatInterval = 1;
    customRepeatUnit = 'week';
    selectedWeekDays = [];
    repeatEndType = 'never';
    repeatEndDate = '';
    repeatEndCount = 10;

    if (scheduleNoteDropdown) scheduleNoteDropdown.style.display = 'none';
    if (sharedEmailsDisplay) sharedEmailsDisplay.style.display = 'none';
    if (scheduleLinkedNoteId) scheduleLinkedNoteId.value = '';
    if (scheduleNoteSearchInput) scheduleNoteSearchInput.value = '';
    if (scheduleCustomRepeatPanel) scheduleCustomRepeatPanel.style.display = 'none';

    if (scheduleAddGrid) {
      scheduleAddGrid.classList.remove('grid-cols-3');
      scheduleAddGrid.classList.add('grid-cols-2');
    }
    if (scheduleAddModalContainer) {
      scheduleAddModalContainer.classList.remove('modal-large');
      scheduleAddModalContainer.classList.add('modal-medium');
    }

    if (targetCalendarSelect) {
      const firstOption = targetCalendarSelect.querySelector('option');
      if (firstOption) {
        targetCalendarSelect.value = firstOption.value;
      } else {
        targetCalendarSelect.value = '';
      }
    }
  }

  // Load notes
  async function loadNotes() {
    try {
      const response = await fetch('/api/notes/', {
        method: 'GET',
        credentials: 'same-origin',
        headers: {
          'X-CSRFToken': getCsrfToken(),
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        allNotes = data.results || data || [];
      } else {
        allNotes = [];
      }
    } catch (error) {
      console.error('Error loading notes:', error);
      allNotes = [];
    }
  }

// Handle note search
  function handleNoteSearch(e) {
    noteSearchQuery = e.target.value.toLowerCase().trim();
    showNoteDropdown = true; // Always show dropdown when typing
    renderNoteDropdown();
  }

// Render note dropdown
  function renderNoteDropdown() {
    if (!scheduleNoteDropdown) return;

    if (!showNoteDropdown) {
      scheduleNoteDropdown.style.display = 'none';
      return;
    }

    // Filter notes based on search query
    const filteredNotes = noteSearchQuery
        ? allNotes.filter(note =>
            note.title && note.title.toLowerCase().includes(noteSearchQuery)
          )
        : allNotes.slice(0, 10); // Show first 10 notes if no search query

    if (filteredNotes.length === 0) {
      scheduleNoteDropdown.innerHTML = '<div class="note-dropdown-empty">검색 결과가 없습니다</div>';
    } else {
      scheduleNoteDropdown.innerHTML = filteredNotes.slice(0, 10).map(note => `
        <div class="note-dropdown-item" data-note-id="${note.id}">
          <i class="fas fa-file-lines"></i>
          <div>
            <p class="note-dropdown-title">${escapeHtml(note.title || 'Untitled')}</p>
            <p class="note-dropdown-date">${note.created_at ? formatDate(note.created_at) : ''}</p>
          </div>
        </div>
      `).join('');

      scheduleNoteDropdown.querySelectorAll('.note-dropdown-item').forEach(item => {
        item.addEventListener('click', (ev) => {
          ev.stopPropagation();
          const noteId = item.getAttribute('data-note-id');
          const note = filteredNotes.find(n => String(n.id) === String(noteId));
          if (note) {
            selectedNoteId = noteId;
            if (scheduleNoteSearchInput) scheduleNoteSearchInput.value = note.title || 'Untitled';
            if (scheduleLinkedNoteId) scheduleLinkedNoteId.value = noteId;
            showNoteDropdown = false;
            scheduleNoteDropdown.style.display = 'none';
          }
        });
      });
    }

    scheduleNoteDropdown.style.display = 'block';
  }

  function handleAllDayChange(e) {
    const isAllDay = e.target.checked;
    if (scheduleStartTime) scheduleStartTime.style.display = isAllDay ? 'none' : 'block';
    if (scheduleEndTime) scheduleEndTime.style.display = isAllDay ? 'none' : 'block';

    if (isAllDay) {
      if (scheduleStartTime) scheduleStartTime.value = '00:00';
      if (scheduleEndTime) scheduleEndTime.value = '23:59';
    } else {
      if (scheduleStartTime && !scheduleStartTime.value) scheduleStartTime.value = '09:00';
      if (scheduleEndTime && !scheduleEndTime.value) scheduleEndTime.value = '18:00';
    }
  }

  // Handle repeat type change
  function handleRepeatTypeChange(e) {
    const repeatType = e.target.value;
    const showCustom = repeatType === 'custom';

    if (scheduleCustomRepeatPanel) scheduleCustomRepeatPanel.style.display = showCustom ? 'block' : 'none';

    // Change grid columns (2 -> 3 or 3 -> 2)
    if (scheduleAddGrid) {
      if (showCustom) {
        scheduleAddGrid.classList.remove('grid-cols-2');
        scheduleAddGrid.classList.add('grid-cols-3');
      } else {
        scheduleAddGrid.classList.remove('grid-cols-3');
        scheduleAddGrid.classList.add('grid-cols-2');
      }
    }

    // Change modal container size
    if (scheduleAddModalContainer) {
      if (showCustom) {
        scheduleAddModalContainer.classList.add('modal-large');
        scheduleAddModalContainer.classList.remove('modal-medium');
      } else {
        scheduleAddModalContainer.classList.remove('modal-large');
        scheduleAddModalContainer.classList.add('modal-medium');
      }
    }

    // Update custom repeat summary when showing
    if (showCustom) {
        updateCustomRepeatSummary();
    }
  }

  // Handle custom repeat change
  function handleCustomRepeatChange() {
    if (customRepeatIntervalInput) customRepeatInterval = parseInt(customRepeatIntervalInput.value) || 1;

    if (customRepeatUnitSelect) {
      customRepeatUnit = customRepeatUnitSelect.value;
      if (weekDaysSelection) weekDaysSelection.style.display = customRepeatUnit === 'week' ? 'block' : 'none';
    }
    updateCustomRepeatSummary();
  }

  // Handle week day toggle
  function handleWeekDayToggle(e) {
    const day = parseInt(e.target.getAttribute('data-day'));
    const idx = selectedWeekDays.indexOf(day);

    if (idx > -1) {
      selectedWeekDays.splice(idx, 1);
      e.target.classList.remove('active');
    } else {
      selectedWeekDays.push(day);
      selectedWeekDays.sort();
      e.target.classList.add('active');
    }
    updateCustomRepeatSummary();
  }

  // Handle repeat end change
  function handleRepeatEndChange(e) {
    repeatEndType = e.target.value;

    if (repeatEndDateInput) repeatEndDateInput.style.display = repeatEndType === 'date' ? 'block' : 'none';
    const repeatCountContainer = document.querySelector('.repeat-count-input');
    if (repeatCountContainer) repeatCountContainer.style.display = repeatEndType === 'count' ? 'flex' : 'none';

    updateCustomRepeatSummary();
  }

  function updateCustomRepeatSummary() {
    if (!customRepeatSummary) return;

    const weekDaysKorean = ['일', '월', '화', '수', '목', '금', '토'];
    let summary = '';

    if (customRepeatInterval > 1) summary += customRepeatInterval;

    if (customRepeatUnit === 'day') {
      summary += customRepeatInterval > 1 ? '일' : '매일';
    } else if (customRepeatUnit === 'week') {
      summary += customRepeatInterval > 1 ? '주' : '매주';
      if (selectedWeekDays.length > 0) {
        summary += ` (${selectedWeekDays.map(d => weekDaysKorean[d]).join(', ')})`;
      } else {
        summary += ' (요일 미선택)';
      }
    } else if (customRepeatUnit === 'month') {
      summary += customRepeatInterval > 1 ? '개월' : '매월';
    } else if (customRepeatUnit === 'year') {
      summary += customRepeatInterval > 1 ? '년' : '매년';
    }

    summary += ' 반복';

    // End type
    if (repeatEndType === 'date' && repeatEndDateInput?.value) {
      repeatEndDate = repeatEndDateInput.value;
      summary += `, ${repeatEndDate}까지`;
    } else if (repeatEndType === 'count') {
      const count = repeatEndCountInput ? (parseInt(repeatEndCountInput.value) || 10) : 10;
      repeatEndCount = count;
      summary += `, ${count}회 반복`;
    }

    customRepeatSummary.textContent = summary;
  }

// Handle share click
  function handleShareClick() {
    if (window.ShareModal && window.ShareModal.open) {
      console.log('[ScheduleAddModal] Opening ShareModal...');
      // 공유 완료시 콜백
      window.ShareModal.onShare = (selectedMembers) => {
        // 선택된 멤버 이메일을 공유 목록에 추가
        if (selectedMembers && selectedMembers.length > 0) {
          // ShareModal에서 선택된 멤버의 이메일을 가져와서 추가
          const allMembers = window.ShareModal._getAllMembers ? window.ShareModal._getAllMembers() : [];
          selectedMembers.forEach(memberId => {
            const member = allMembers.find(m => m.id === memberId);
            if (member && member.email && !sharedEmails.includes(member.email)) {
              sharedEmails.push(member.email);
            }
          });
          updateSharedEmailsDisplay(sharedEmails);
        }
      };
      window.ShareModal.open(null, null, null, '일정 공유');
    } else {
      console.warn('ShareModal not loaded. Please refresh the page.');
      if (window.notyf) {
          window.notyf.error('공유 모달을 로드할 수 없습니다. 페이지를 새로고침해주세요.');
      }
    }
  }

  // Handle save click
  function handleSaveClick(e) {
    e.preventDefault();
    handleFormSubmit(e);
  }

  // Handle form submit
  async function handleFormSubmit(e) {
    e.preventDefault();
    
    if (!scheduleAddForm) return;
    
    // 스케줄 저장 시 추후 필요
    const formData = new FormData(scheduleAddForm);
    const isAllDay = scheduleIsAllDay?.checked || false;
    
    const repeatType = scheduleRepeatSelect?.value || 'none';

    let recurrencePayload = null;
    if (repeatType !== 'none') {
      const freqMap = {
        daily: 'DAILY',
        weekly: 'WEEKLY',
        monthly: 'MONTHLY',
        yearly: 'YEARLY',
        custom: customRepeatUnitSelect?.value === 'year' ? 'YEARLY'
          : customRepeatUnitSelect?.value === 'month' ? 'MONTHLY'
          : customRepeatUnitSelect?.value === 'day' ? 'DAILY'
          : 'WEEKLY',
      };

      const baseFreq = repeatType === 'custom'
        ? (customRepeatUnitSelect?.value || 'week')
        : repeatType;

      const untilStr = repeatEndType === 'date' && repeatEndDateInput?.value
        ? `${repeatEndDateInput.value}T23:59:59`
        : null;

      const countValue = repeatEndType === 'count'
        ? (repeatEndCountInput ? parseInt(repeatEndCountInput.value || '10', 10) : 10)
        : null;

      const monthDay = scheduleStartDate?.value
        ? new Date(scheduleStartDate.value).getDate()
        : null;

      recurrencePayload = {
        freq: freqMap[baseFreq] || freqMap.weekly,
        interval: repeatType === 'custom'
          ? parseInt(customRepeatIntervalInput?.value || '1', 10)
          : 1,
        week_days: (repeatType === 'weekly' || baseFreq === 'week') ? selectedWeekDays : [],
        month_days: baseFreq === 'month' && monthDay ? [monthDay] : [],
        until: untilStr,
        count: countValue,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Seoul',
      };
    }

    const scheduleData = {
      title: scheduleTitleInput?.value || '',
      description: scheduleDescriptionInput?.value || '',
      location: scheduleLocationInput?.value || '',
      is_all_day: isAllDay,
      start_datetime: isAllDay
        ? `${scheduleStartDate?.value || ''}T00:00:00`
        : `${scheduleStartDate?.value || ''}T${scheduleStartTime?.value || '00:00'}:00`,
      end_datetime: isAllDay
        ? `${scheduleEndDate?.value || ''}T23:59:59`
        : `${scheduleEndDate?.value || ''}T${scheduleEndTime?.value || '00:00'}:00`,
      type: scheduleTypeSelect?.value || 'experiment',
      status: scheduleStatusSelectAdd?.value || 'scheduled',
      recurrence: recurrencePayload,
      notification: scheduleNotificationSelect?.value || 'none',
      linked_note_id: scheduleLinkedNoteId?.value || null,
      shared_emails: sharedEmails,
    };

    // Validation
    if (!scheduleData.title.trim()) {
        if (window.notyf) {
            window.notyf.error('제목을 입력해주세요.');
        }
      return;
    }
    
    if (!scheduleData.start_datetime || !scheduleData.end_datetime) {
      if (window.notyf) {
          window.notyf.error('날짜를 입력해주세요.');
      }
      return;
  }

    const selectedCalendarId = targetCalendarSelect ? targetCalendarSelect.value : '';
    if (!selectedCalendarId) {
      if (window.notyf) {
        window.notyf.error('캘린더를 선택해주세요.');
      }
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/api/schedules/`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'X-CSRFToken': getCsrfToken(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ...scheduleData, calendar_id: parseInt(selectedCalendarId, 10) || selectedCalendarId }),
      });

      if (response.ok) {
        // 용도: 서버 응답에서 생성된 일정의 상세 객체를 받아옴 (추후 활용 가능)
        const data = await response.json();
        
        if (window.notyf) {
            window.notyf.success('일정이 등록되었습니다.');
        }
        
        // Close modal
        if (window.Modal) {
            window.Modal.close(modalId);
        }
            
        // Refresh calendar and list
        if (window.SchedulePage) {
          if (window.SchedulePage.loadSchedules) {
              window.SchedulePage.loadSchedules();
          }
          if (window.SchedulePage.refreshCalendar) {
              window.SchedulePage.refreshCalendar();
          }
        }
      } else {
        const error = await response.json().catch(() => ({}));
        console.error('Failed to create schedule:', error);
        if (window.notyf) {
            window.notyf.error(error.detail || '일정 등록에 실패했습니다.');
        }
      }
    } catch (error) {
      console.error('Error creating schedule:', error);
      if (window.notyf) {
          window.notyf.error('일정 등록 중 오류가 발생했습니다.');
      }
    }
  }

  // Update shared emails display
  function updateSharedEmailsDisplay(emails) {
    sharedEmails = emails || [];
    if (sharedEmailsDisplay && sharedEmailsCount) {
      if (sharedEmails.length > 0) {
        sharedEmailsDisplay.style.display = 'block';
        sharedEmailsCount.textContent = String(sharedEmails.length);
      } else {
        sharedEmailsDisplay.style.display = 'none';
      }
    }
  }

  function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' });
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

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initScheduleAddModal);
  } else {
    initScheduleAddModal();
  }

  // Export for use in other modules
  if (typeof window !== 'undefined') {
    window.ScheduleAddModal = {
      open: (date = null) => {
        prefillDate = date;
        if (window.Modal) window.Modal.open(modalId);
      },
      updateSharedEmails: updateSharedEmailsDisplay,
      get sharedEmails() { return sharedEmails; },
      init: initScheduleAddModal,
    };
  }
})();
