// Google Calendar Modal Component JavaScript Logic
(function () {
  'use strict';

  // ✅ A방식 Base URL
  const API_BASE = '/schedule';
  const modalId = 'googleCalendarModal';

  // State
  let isGoogleConnected = false;
  let selectedGoogleCalendars = [];
  let googleCalendars = [];
  let myCalendars = [];

  // ---- DOM helper (✅ 항상 최신 DOM을 잡는다) ----
  function el(id) {
    return document.getElementById(id);
  }

  function getModalEl() {
    return el(modalId);
  }

  // ---- Initialize ----
  function initGoogleCalendarModal() {
    const modal = getModalEl();
    if (!modal) return;

    // 버튼은 init 시점에 다시 연결
    const connectBtn = el('googleCalendarConnectBtn');
    const saveBtn = el('googleCalendarSaveBtn');

    if (connectBtn) connectBtn.addEventListener('click', handleConnect);
    if (saveBtn) saveBtn.addEventListener('click', handleSave);

    // (있으면) modal:open 이벤트도 받되, 없어도 reload로 해결 가능
    modal.addEventListener('modal:open', handleModalOpen);

    // 최초 상태 로드
    loadGoogleCalendarStatus();
  }

  function handleModalOpen(e) {
    // 이벤트 detail이 없거나 포맷이 달라도 안전하게 처리
    if (e?.detail?.modalId && e.detail.modalId !== modalId) return;
    reload(); // ✅ 모달 열리면 무조건 reload
  }

  // ✅ 외부(schedule.js)에서 호출할 수 있게 제공
  async function reload() {
    await loadGoogleCalendarStatus();

    // 연결되어 있으면 캘린더 목록 불러오기
    if (isGoogleConnected) {
      await loadGoogleCalendars();
    } else {
      // 연결 안 돼 있으면 안내 문구로 정리
      renderGoogleCalendars();
    }

    // 내 캘린더는 지금 404라서 실패해도 조용히
    await loadMyCalendars();
  }

  // ---- API calls ----
  async function loadGoogleCalendarStatus() {
    try {
      const response = await fetch(`${API_BASE}/api/google-calendar/status/`, {
        method: 'GET',
        headers: {
          'X-CSRFToken': getCsrfToken(),
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        isGoogleConnected = !!data.connected;
      } else {
        isGoogleConnected = false;
      }

      renderConnectionStatus();
    } catch (error) {
      console.error('Error loading Google Calendar status:', error);
      isGoogleConnected = false;
      renderConnectionStatus();
    }
  }

  async function loadGoogleCalendars() {
    try {
      const response = await fetch(`${API_BASE}/api/google-calendar/calendars/`, {
        method: 'GET',
        headers: {
          'X-CSRFToken': getCsrfToken(),
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        googleCalendars = data.results || data || [];

        // ✅ calendar id는 문자열로만 다룬다
        selectedGoogleCalendars = googleCalendars
          .filter(cal => cal.selected)
          .map(cal => String(cal.id));

      } else {
        googleCalendars = [];
        selectedGoogleCalendars = [];
      }

      renderGoogleCalendars();
    } catch (error) {
      console.error('Error loading Google Calendars:', error);
      googleCalendars = [];
      selectedGoogleCalendars = [];
      renderGoogleCalendars();
    }
  }

  async function loadMyCalendars() {
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
        myCalendars = data.results || data || [];
      } else {
        myCalendars = [];
      }

      renderMyCalendars();
    } catch (error) {
      myCalendars = [];
      renderMyCalendars();
    }
  }

  // ---- Render ----
  function renderConnectionStatus() {
    const indicator = el('connectionStatusIndicator');
    const text = el('connectionStatusText');
    const connectBtn = el('googleCalendarConnectBtn');

    if (indicator) {
      if (isGoogleConnected) {
        indicator.className = 'connection-status-indicator connected';
        indicator.innerHTML = '<i class="fas fa-check-circle"></i>';
      } else {
        indicator.className = 'connection-status-indicator disconnected';
        indicator.innerHTML = '';
      }
    }

    if (text) {
      text.textContent = isGoogleConnected
        ? 'Google Calendar 연결됨'
        : 'Google Calendar 연결 안 됨';
    }

    if (connectBtn) {
      connectBtn.style.display = isGoogleConnected ? 'none' : 'block';
    }
  }

  function renderGoogleCalendars() {
    const list = el('googleCalendarList');
    if (!list) return;

    if (!isGoogleConnected) {
      list.innerHTML = '<p class="empty-text">Google Calendar가 연결되어 있지 않습니다.</p>';
      return;
    }

    if (!googleCalendars || googleCalendars.length === 0) {
      list.innerHTML = '<p class="empty-text">연결된 캘린더가 없습니다.</p>';
      return;
    }

    list.innerHTML = googleCalendars.map(calendar => `
      <div class="google-calendar-item">
        <div class="calendar-color-indicator" style="background-color: ${calendar.color || '#3b82f6'};"></div>
        <div class="calendar-info">
          <p class="calendar-name">${escapeHtml(calendar.name || '')}</p>
          <p class="calendar-email">${escapeHtml(calendar.email || '')}</p>
        </div>
        <input
          type="checkbox"
          class="calendar-checkbox"
          data-calendar-id="${escapeHtml(String(calendar.id))}"
          ${selectedGoogleCalendars.includes(String(calendar.id)) ? 'checked' : ''}
        />
      </div>
    `).join('');

    // checkbox handler
    const checkboxes = list.querySelectorAll('.calendar-checkbox');
    checkboxes.forEach(cb => {
      cb.addEventListener('change', (e) => {
        const calendarId = String(e.target.getAttribute('data-calendar-id'));

        if (e.target.checked) {
          if (!selectedGoogleCalendars.includes(calendarId)) {
            selectedGoogleCalendars.push(calendarId);
          }
        } else {
          selectedGoogleCalendars = selectedGoogleCalendars.filter(id => id !== calendarId);
        }
      });
    });
  }

  function renderMyCalendars() {
    const list = el('myCalendarList');
    if (!list) return;

    if (!myCalendars || myCalendars.length === 0) {
      list.innerHTML = '<p class="empty-text">캘린더가 없습니다.</p>';
      return;
    }

    list.innerHTML = myCalendars.map(calendar => `
      <div class="my-calendar-item">
        <div class="calendar-color-indicator" style="background-color: ${calendar.color || '#3b82f6'};"></div>
        <div class="calendar-info">
          <p class="calendar-name">${escapeHtml(calendar.name || '')}</p>
        </div>
        <input
          type="checkbox"
          class="calendar-checkbox"
          data-calendar-id="${calendar.id}"
          ${calendar.visible ? 'checked' : ''}
        />
      </div>
    `).join('');
  }

  // ---- Actions ----
  async function handleConnect() {
    try {
      window.location.href = `${API_BASE}/google/login/`;
    } catch (error) {
      console.error('Error connecting Google Calendar:', error);
      if (window.notyf) window.notyf.error('Google Calendar 연결 중 오류가 발생했습니다.');
    }
  }

  async function handleSave() {
    try {
      const response = await fetch(`${API_BASE}/api/google-calendar/calendars/`, {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCsrfToken(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          selected_calendar_ids: selectedGoogleCalendars, // ✅ 문자열
        }),
      });

      if (response.ok) {
        if (window.notyf) window.notyf.success('설정이 저장되었습니다.');
        if (window.Modal) window.Modal.close(modalId);

        // 달력 리프레시
        if (window.SchedulePage && window.SchedulePage.refreshCalendar) {
          window.SchedulePage.refreshCalendar();
        }
      } else {
        const err = await response.json().catch(() => ({}));
        console.error('Failed to save settings:', err);
        if (window.notyf) window.notyf.error('설정 저장에 실패했습니다.');
      }
    } catch (error) {
      console.error('Error saving settings:', error);
      if (window.notyf) window.notyf.error('설정 저장 중 오류가 발생했습니다.');
    }
  }

  // ---- Utils ----
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

  // DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initGoogleCalendarModal);
  } else {
    initGoogleCalendarModal();
  }

  // ✅ 외부에서 reload 가능하게 export
  if (typeof window !== 'undefined') {
    window.GoogleCalendarModal = {
      init: initGoogleCalendarModal,
      reload,
    };
  }
})();
