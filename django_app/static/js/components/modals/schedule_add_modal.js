// Schedule Add Modal Component JavaScript Logic
(function() {
  'use strict';

  const API_BASE = '/schedule';

  let noteSearchQuery = '';
  let showNoteDropdown = false;
  let selectedNoteId = null;
  let sharedEmails = [];
  let prefillDate = null;

  let googleCalendarsForSelect = [];

  let customRepeatInterval = 1;
  let customRepeatUnit = 'week';
  let selectedWeekDays = [];
  let repeatEndType = 'never';

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

  // ✅ 이거 하나만 선언 (중복 금지)
  const targetCalendarSelect = document.getElementById('targetCalendarSelect');

  let allNotes = [];

  function initScheduleAddModal() {
    // form
    if (scheduleAddForm) {
      scheduleAddForm.addEventListener('submit', handleFormSubmit);
    }

    // note search
    if (scheduleNoteSearchInput) {
      scheduleNoteSearchInput.addEventListener('input', handleNoteSearch);
      scheduleNoteSearchInput.addEventListener('focus', () => {
        showNoteDropdown = true;
        renderNoteDropdown();
      });
    }

    // all day
    if (scheduleIsAllDay) {
      scheduleIsAllDay.addEventListener('change', handleAllDayChange);
    }

    // repeat
    if (scheduleRepeatSelect) {
      scheduleRepeatSelect.addEventListener('change', handleRepeatTypeChange);
    }

    // custom repeat
    if (customRepeatIntervalInput) customRepeatIntervalInput.addEventListener('input', handleCustomRepeatChange);
    if (customRepeatUnitSelect) customRepeatUnitSelect.addEventListener('change', handleCustomRepeatChange);
    if (weekDayButtons) weekDayButtons.forEach(btn => btn.addEventListener('click', handleWeekDayToggle));
    if (repeatEndRadios) repeatEndRadios.forEach(r => r.addEventListener('change', handleRepeatEndChange));
    if (repeatEndDateInput) repeatEndDateInput.addEventListener('change', updateCustomRepeatSummary);
    if (repeatEndCountInput) repeatEndCountInput.addEventListener('input', updateCustomRepeatSummary);

    // share
    if (scheduleAddShareBtn) scheduleAddShareBtn.addEventListener('click', handleShareClick);

    // save
    if (scheduleAddSaveBtn) scheduleAddSaveBtn.addEventListener('click', handleSaveClick);

    // ✅ 모달 이벤트: "modal element"가 아니라 document에서 잡자 (핵심)
    document.addEventListener('modal:open', handleModalOpen, true);
    document.addEventListener('modal:close', handleModalClose, true);

    // ✅ select 클릭/포커스 때도 다시 로드 (모달 이벤트가 안 잡혀도 커버)
    if (targetCalendarSelect) {
      targetCalendarSelect.addEventListener('focus', loadGoogleCalendarsForTargetSelect);
      targetCalendarSelect.addEventListener('click', loadGoogleCalendarsForTargetSelect);
    }

    // click outside dropdown
    document.addEventListener('click', (e) => {
      if (scheduleNoteSearchInput && scheduleNoteDropdown) {
        if (!scheduleNoteSearchInput.contains(e.target) && !scheduleNoteDropdown.contains(e.target)) {
          showNoteDropdown = false;
          scheduleNoteDropdown.style.display = 'none';
        }
      }
    });

    loadNotes();
  }

  async function loadGoogleCalendarsForTargetSelect() {
    if (!targetCalendarSelect) return;

    console.log('[ScheduleAddModal] loadGoogleCalendarsForTargetSelect called');

    try {
      const url = `${API_BASE}/api/google-calendar/calendars/`;
      console.log('[ScheduleAddModal] fetching:', url);

      const res = await fetch(url, {
        method: 'GET',
        credentials: 'same-origin',
        headers: {
          'X-CSRFToken': getCsrfToken(),
          'Content-Type': 'application/json',
        },
      });

      console.log('[ScheduleAddModal] calendars status:', res.status);

      if (!res.ok) {
        googleCalendarsForSelect = [];
        renderTargetCalendarOptions();
        return;
      }

      const data = await res.json();
      googleCalendarsForSelect = data.results || data || [];
      console.log('[ScheduleAddModal] calendars payload:', googleCalendarsForSelect);

      renderTargetCalendarOptions();
    } catch (err) {
      console.error('[ScheduleAddModal] calendars fetch error:', err);
      googleCalendarsForSelect = [];
      renderTargetCalendarOptions();
    }
  }

  function renderTargetCalendarOptions() {
    if (!targetCalendarSelect) return;

    targetCalendarSelect.innerHTML = '';

    const localOpt = document.createElement('option');
    localOpt.value = 'local';
    localOpt.textContent = '내 일정(웹 캘린더)';
    localOpt.selected = true;
    targetCalendarSelect.appendChild(localOpt);

    if (!googleCalendarsForSelect || googleCalendarsForSelect.length === 0) {
      return;
    }

    const selected = googleCalendarsForSelect.filter(c => !!c.selected);
    const unselected = googleCalendarsForSelect.filter(c => !c.selected);
    const ordered = [...selected, ...unselected];

    ordered.forEach(cal => {
      const calendarId = cal.calendar_id || cal.email || cal.id;
      if (!calendarId) return;

      const name = cal.name || cal.summary || 'Google Calendar';

      const opt = document.createElement('option');
      opt.value = `google:${String(calendarId)}`;
      opt.textContent = cal.selected ? name : `${name} (미선택)`;

      targetCalendarSelect.appendChild(opt);
    });

    console.log('[ScheduleAddModal] renderTargetCalendarOptions done. option count:', targetCalendarSelect.options.length);
  }

  function handleModalOpen(e) {
    // ✅ e.detail.modalId 기반이면 그대로, 아니면 fallback
    const openedId = e?.detail?.modalId;
    if (openedId && openedId !== modalId) return;

    console.log('[ScheduleAddModal] modal open detected:', openedId);

    const urlParams = new URLSearchParams(window.location.search);
    const dateParam = urlParams.get('date') || prefillDate;

    if (dateParam) {
      prefillDate = dateParam;
      if (scheduleStartDate) scheduleStartDate.value = dateParam;
      if (scheduleEndDate) scheduleEndDate.value = dateParam;
    } else {
      const today = new Date().toISOString().split('T')[0];
      if (scheduleStartDate) scheduleStartDate.value = today;
      if (scheduleEndDate) scheduleEndDate.value = today;
    }

    resetForm();

    if (scheduleIsAllDay) handleAllDayChange({ target: scheduleIsAllDay });

    if (scheduleRepeatSelect) handleRepeatTypeChange({ target: scheduleRepeatSelect });
    updateCustomRepeatSummary();

    // ✅ 여기서도 로드
    loadGoogleCalendarsForTargetSelect();
  }

  function handleModalClose(e) {
    const closedId = e?.detail?.modalId;
    if (closedId && closedId !== modalId) return;
    resetForm();
    prefillDate = null;
  }

  function resetForm() {
    if (scheduleAddForm) scheduleAddForm.reset();

    noteSearchQuery = '';
    showNoteDropdown = false;
    selectedNoteId = null;
    sharedEmails = [];

    customRepeatInterval = 1;
    customRepeatUnit = 'week';
    selectedWeekDays = [];
    repeatEndType = 'never';

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

    if (targetCalendarSelect) targetCalendarSelect.value = 'local';
  }

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

  function handleNoteSearch(e) {
    noteSearchQuery = e.target.value.toLowerCase().trim();
    showNoteDropdown = true;
    renderNoteDropdown();
  }

  function renderNoteDropdown() {
    if (!scheduleNoteDropdown) return;

    if (!showNoteDropdown) {
      scheduleNoteDropdown.style.display = 'none';
      return;
    }

    const filteredNotes = noteSearchQuery
      ? allNotes.filter(note => note.title && note.title.toLowerCase().includes(noteSearchQuery))
      : allNotes.slice(0, 10);

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

    if (!isAllDay) {
      if (scheduleStartTime && !scheduleStartTime.value) scheduleStartTime.value = '09:00';
      if (scheduleEndTime && !scheduleEndTime.value) scheduleEndTime.value = '18:00';
    }
  }

  function handleRepeatTypeChange(e) {
    const repeatType = e.target.value;
    const showCustom = repeatType === 'custom';

    if (scheduleCustomRepeatPanel) scheduleCustomRepeatPanel.style.display = showCustom ? 'block' : 'none';

    if (scheduleAddGrid) {
      if (showCustom) {
        scheduleAddGrid.classList.remove('grid-cols-2');
        scheduleAddGrid.classList.add('grid-cols-3');
      } else {
        scheduleAddGrid.classList.remove('grid-cols-3');
        scheduleAddGrid.classList.add('grid-cols-2');
      }
    }

    if (scheduleAddModalContainer) {
      if (showCustom) {
        scheduleAddModalContainer.classList.add('modal-large');
        scheduleAddModalContainer.classList.remove('modal-medium');
      } else {
        scheduleAddModalContainer.classList.remove('modal-large');
        scheduleAddModalContainer.classList.add('modal-medium');
      }
    }

    if (showCustom) updateCustomRepeatSummary();
  }

  function handleCustomRepeatChange() {
    if (customRepeatIntervalInput) customRepeatInterval = parseInt(customRepeatIntervalInput.value) || 1;

    if (customRepeatUnitSelect) {
      customRepeatUnit = customRepeatUnitSelect.value;
      if (weekDaysSelection) weekDaysSelection.style.display = customRepeatUnit === 'week' ? 'block' : 'none';
    }
    updateCustomRepeatSummary();
  }

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

    if (repeatEndType === 'count') {
      const count = repeatEndCountInput ? (parseInt(repeatEndCountInput.value) || 10) : 10;
      summary += `, ${count}회 반복`;
    }

    customRepeatSummary.textContent = summary;
  }

  function handleShareClick() {
    if (window.ShareModal && window.ShareModal.open) {
      window.ShareModal.onShare = (selectedMembers) => {
        if (selectedMembers && selectedMembers.length > 0) {
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
      if (window.notyf) window.notyf.error('공유 모달을 로드할 수 없습니다. 페이지를 새로고침해주세요.');
    }
  }

  function handleSaveClick(e) {
    e.preventDefault();
    handleFormSubmit(e);
  }

  async function handleFormSubmit(e) {
    e.preventDefault();
    if (!scheduleAddForm) return;

    const isAllDay = scheduleIsAllDay?.checked || false;

    const scheduleData = {
      title: scheduleTitleInput?.value || '',
      description: scheduleDescriptionInput?.value || '',
      location: scheduleLocationInput?.value || '',
      start_datetime: isAllDay
        ? `${scheduleStartDate?.value || ''}T00:00:00`
        : `${scheduleStartDate?.value || ''}T${scheduleStartTime?.value || '00:00'}:00`,
      end_datetime: isAllDay
        ? `${scheduleEndDate?.value || ''}T23:59:59`
        : `${scheduleEndDate?.value || ''}T${scheduleEndTime?.value || '00:00'}:00`,
      type: scheduleTypeSelect?.value || 'experiment',
      status: scheduleStatusSelectAdd?.value || 'scheduled',
      repeat: scheduleRepeatSelect?.value || 'none',
      notification: scheduleNotificationSelect?.value || 'none',
      linked_note_id: scheduleLinkedNoteId?.value || null,
      shared_emails: sharedEmails,
    };

    if (!scheduleData.title.trim()) {
      if (window.notyf) window.notyf.error('제목을 입력해주세요.');
      return;
    }

    const target = targetCalendarSelect ? targetCalendarSelect.value : 'local';

    try {
      const response = await fetch(`${API_BASE}/api/schedules/`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'X-CSRFToken': getCsrfToken(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ...scheduleData, target_calendar: target }),
      });

      if (response.ok) {
        if (window.notyf) window.notyf.success('일정이 등록되었습니다.');
        if (window.Modal) window.Modal.close(modalId);

        if (window.SchedulePage) {
          if (window.SchedulePage.loadSchedules) window.SchedulePage.loadSchedules();
          if (window.SchedulePage.refreshCalendar) window.SchedulePage.refreshCalendar();
        }
      } else {
        const error = await response.json().catch(() => ({}));
        console.error('Failed to create schedule:', error);
        if (window.notyf) window.notyf.error(error.detail || '일정 등록에 실패했습니다.');
      }
    } catch (error) {
      console.error('Error creating schedule:', error);
      if (window.notyf) window.notyf.error('일정 등록 중 오류가 발생했습니다.');
    }
  }

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

  function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // init
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initScheduleAddModal);
  } else {
    initScheduleAddModal();
  }

  if (typeof window !== 'undefined') {
    window.ScheduleAddModal = {
      open: (date = null) => {
        prefillDate = date;
        if (window.Modal) window.Modal.open(modalId);
      },
      init: initScheduleAddModal,
    };
  }
})();
