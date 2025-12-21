// Google Calendar Modal Component JavaScript Logic
(function() {
  'use strict';

  const API_BASE = "/schedule";

  // State variables
  let isGoogleConnected = false;
  let googleCalendars = [];
  let selectedGoogleCalendars = new Set();
  let calendarColors = {};
  let myCalendars = [];

  // DOM
  const modalId = "googleCalendarModal";
  const connectionStatusIndicator = document.getElementById("connectionStatusIndicator");
  const connectionStatusText = document.getElementById("connectionStatusText");
  const googleCalendarConnectBtn = document.getElementById("googleCalendarConnectBtn");
  const googleCalendarDisconnectBtn = document.getElementById("googleCalendarDisconnectBtn"); // ✅ 추가
  const googleCalendarList = document.getElementById("googleCalendarList");
  const myCalendarList = document.getElementById("myCalendarList");
  const googleCalendarSaveBtn = document.getElementById("googleCalendarSaveBtn");

  // ------------------------------------------------------------
  // Utils
  // ------------------------------------------------------------
  function getCsrfToken() {
    const cookies = document.cookie.split(";");
    for (let cookie of cookies) {
      const [name, value] = cookie.trim().split("=");
      if (name === "csrftoken") return value;
    }
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    if (metaTag) return metaTag.getAttribute("content");
    return "";
  }

  function escapeHtml(text) {
    if (!text) return "";
    const div = document.createElement("div");
    div.textContent = String(text);
    return div.innerHTML;
  }

  function normalizeHex(color, fallback = "#3b82f6") {
    if (!color || typeof color !== "string") return fallback;
    const c = color.trim();
    if (c.startsWith("#") && (c.length === 4 || c.length === 7)) return c;
    return fallback;
  }

  // ------------------------------------------------------------
  // API
  // ------------------------------------------------------------
  async function fetchGoogleStatus() {
    try {
      const res = await fetch(`${API_BASE}/api/google-calendar/status/`, {
        method: "GET",
        headers: {
          "X-CSRFToken": getCsrfToken(),
          "Content-Type": "application/json",
        },
      });

      if (!res.ok) {
        isGoogleConnected = false;
        renderConnectionStatus();
        return;
      }

      const data = await res.json();
      isGoogleConnected = !!data.connected;
      renderConnectionStatus();
    } catch (e) {
      console.warn("google status fetch failed:", e);
      isGoogleConnected = false;
      renderConnectionStatus();
    }
  }

  async function fetchGoogleCalendars() {
    if (!googleCalendarList) return;

    try {
      const res = await fetch(`${API_BASE}/api/google-calendar/calendars/`, {
        method: "GET",
        headers: {
          "X-CSRFToken": getCsrfToken(),
          "Content-Type": "application/json",
        },
      });

      if (!res.ok) {
        googleCalendars = [];
        selectedGoogleCalendars.clear();
        calendarColors = {};
        renderGoogleCalendars();
        return;
      }

      const data = await res.json();
      const rows = Array.isArray(data) ? data : (data.results || []);
      googleCalendars = rows.map((r) => {
        const id = r.id || r.calendar_id || r.email || "";
        const name = r.name || r.summary || "Google Calendar";
        const email = r.email || r.calendar_id || id;

        return {
          id,
          name,
          email,
          selected: !!r.selected,
          color: normalizeHex(r.color, "#3b82f6"),
        };
      });

      selectedGoogleCalendars.clear();
      calendarColors = {};
      googleCalendars.forEach((c) => {
        if (c.selected) selectedGoogleCalendars.add(c.id);
        calendarColors[c.id] = normalizeHex(c.color, "#3b82f6");
      });

      renderGoogleCalendars();
    } catch (e) {
      console.warn("google calendars fetch failed:", e);
      googleCalendars = [];
      selectedGoogleCalendars.clear();
      calendarColors = {};
      renderGoogleCalendars();
    }
  }

  async function saveGoogleCalendarsSelection() {
    const selectedIds = Array.from(selectedGoogleCalendars);

    const payload = {
      selected_calendar_ids: selectedIds,
      calendar_colors: calendarColors,
    };

    const res = await fetch(`${API_BASE}/api/google-calendar/calendars/`, {
      method: "POST",
      headers: {
        "X-CSRFToken": getCsrfToken(),
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const text = await res.text().catch(() => "");
    let json = {};
    try {
      json = text ? JSON.parse(text) : {};
    } catch {
      json = { raw: text };
    }

    if (!res.ok) {
      throw new Error(json.error || json.detail || "저장에 실패했습니다.");
    }

    return json;
  }

  // Load My Calendars
  async function fetchMyCalendars() {
    if (!myCalendarList) return;

    try {
      const res = await fetch('/api/calendars/', {
        method: 'GET',
        headers: {
          'X-CSRFToken': getCsrfToken(),
          'Content-Type': 'application/json',
        },
      });

      if (res.ok) {
        const data = await res.json();
        myCalendars = data.results || data;
        renderMyCalendars();
      }
    } catch (error) {
      console.error('Error loading my calendars:', error);
      myCalendars = [];
      renderMyCalendars();
    }
  }

  // ------------------------------------------------------------
  // Render
  // ------------------------------------------------------------
  function renderConnectionStatus() {
    if (!connectionStatusIndicator || !connectionStatusText) return;

    if (isGoogleConnected) {
      connectionStatusIndicator.classList.add("connected");
      connectionStatusText.textContent = "Google Calendar 연동됨";

      // ✅ 연동됨: 관리 버튼 보여주고, 연동 해제 버튼도 보여줌
      if (googleCalendarConnectBtn) {
        googleCalendarConnectBtn.style.display = "inline-flex";
        googleCalendarConnectBtn.textContent = "연동 관리";
      }
      if (googleCalendarDisconnectBtn) {
        googleCalendarDisconnectBtn.style.display = "inline-flex";
      }
    } else {
      connectionStatusIndicator.classList.remove("connected");
      connectionStatusText.textContent = "Google Calendar 미연동";

      // ✅ 미연동: 연결 버튼만 보여줌
      if (googleCalendarConnectBtn) {
        googleCalendarConnectBtn.style.display = "inline-flex";
        googleCalendarConnectBtn.textContent = "Google Calendar 연결";
      }
      if (googleCalendarDisconnectBtn) {
        googleCalendarDisconnectBtn.style.display = "none";
      }
    }
  }

  function renderGoogleCalendars() {
    if (!googleCalendarList) return;

    if (!isGoogleConnected) {
      googleCalendarList.innerHTML = `
        <div class="text-sm text-gray-500" style="padding: 8px 0;">
          Google Calendar가 연결되어 있지 않습니다.
        </div>
      `;
      return;
    }

    if (!googleCalendars || googleCalendars.length === 0) {
      googleCalendarList.innerHTML = `
        <div class="text-sm text-gray-500" style="padding: 8px 0;">
          불러올 캘린더가 없습니다.
        </div>
      `;
      return;
    }

    const selected = googleCalendars.filter((c) => selectedGoogleCalendars.has(c.id));
    const unselected = googleCalendars.filter((c) => !selectedGoogleCalendars.has(c.id));
    const ordered = [...selected, ...unselected];

    googleCalendarList.innerHTML = ordered
      .map((cal) => {
        const safeName = escapeHtml(cal.name);
        const safeEmail = escapeHtml(cal.email);
        const checked = selectedGoogleCalendars.has(cal.id) ? "checked" : "";
        const color = normalizeHex(calendarColors[cal.id], "#3b82f6");
        const safeId = escapeHtml(cal.id);

        return `
          <div class="google-calendar-item" data-calendar-id="${safeId}" style="
            display:flex; align-items:center; justify-content:space-between;
            gap:12px; padding:12px; border:1px solid #e5e7eb; border-radius:10px; margin-bottom:10px;
          ">
            <div style="display:flex; align-items:center; gap:12px; min-width:0;">
              <div class="google-calendar-dot" style="
                width:14px; height:14px; border-radius:999px; background:${color};
                flex:0 0 auto;
              "></div>
              <div style="min-width:0;">
                <div style="font-weight:700; color:#111827; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
                  ${safeName}
                </div>
                <div style="font-size:12px; color:#6b7280; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
                  ${safeEmail}
                </div>
              </div>
            </div>

            <div style="display:flex; align-items:center; gap:10px; flex:0 0 auto;">
              <input
                type="color"
                class="google-calendar-color"
                data-calendar-id="${safeId}"
                value="${color}"
                title="캘린더 색상"
                style="width:44px; height:26px; padding:0; border:1px solid #d1d5db; border-radius:6px; background:#fff; cursor:pointer;"
              />
              <input
                type="checkbox"
                class="google-calendar-checkbox"
                data-calendar-id="${safeId}"
                ${checked}
                style="width:18px; height:18px; cursor:pointer;"
              />
            </div>
          </div>
        `;
      })
      .join("");

    bindCalendarRowEvents();
  }

  function bindCalendarRowEvents() {
    document.querySelectorAll('input.google-calendar-checkbox[data-calendar-id]').forEach((cb) => {
      cb.addEventListener("change", (e) => {
        const calId = e.target.getAttribute("data-calendar-id");
        if (!calId) return;

        if (e.target.checked) selectedGoogleCalendars.add(calId);
        else selectedGoogleCalendars.delete(calId);
      });
    });

    document.querySelectorAll('input.google-calendar-color[data-calendar-id]').forEach((inp) => {
      inp.addEventListener("change", (e) => {
        const calId = e.target.getAttribute("data-calendar-id");
        if (!calId) return;

        const color = normalizeHex(e.target.value, "#3b82f6");
        calendarColors[calId] = color;

        const row = e.target.closest(".google-calendar-item");
        if (row) {
          const dot = row.querySelector(".google-calendar-dot");
          if (dot) dot.style.backgroundColor = color;
        }
      });
    });
  }

  // Render My Calendars
  function renderMyCalendars() {
    if (!myCalendarList) return;

    if (myCalendars.length === 0) {
      myCalendarList.innerHTML = '<p class="empty-text">캘린더가 없습니다.</p>';
      return;
    }

    myCalendarList.innerHTML = myCalendars.map(calendar => `
      <div class="my-calendar-item" style="
        display:flex; align-items:center; justify-content:space-between;
        gap:12px; padding:12px; border:1px solid #e5e7eb; border-radius:10px; margin-bottom:10px;
      ">
        <div style="display:flex; align-items:center; gap:12px; min-width:0;">
          <div class="calendar-color-indicator" style="
            width:14px; height:14px; border-radius:999px;
            background-color: ${normalizeHex(calendar.color, '#3b82f6')};
            flex:0 0 auto;
          "></div>
          <div style="min-width:0;">
            <p class="calendar-name" style="font-weight:700; color:#111827; margin:0;">
              ${escapeHtml(calendar.name || '')}
            </p>
          </div>
        </div>
        <input
          type="checkbox"
          class="my-calendar-checkbox"
          data-calendar-id="${calendar.id}"
          ${calendar.visible ? 'checked' : ''}
          style="width:18px; height:18px; cursor:pointer;"
        />
      </div>
    `).join('');

    // Attach checkbox handlers
    const checkboxes = myCalendarList.querySelectorAll('.my-calendar-checkbox');
    checkboxes.forEach(checkbox => {
      checkbox.addEventListener('change', async (e) => {
        const calendarId = parseInt(e.target.getAttribute('data-calendar-id'));
        const visible = e.target.checked;

        try {
          const response = await fetch(`/api/calendars/${calendarId}/`, {
            method: 'PATCH',
            headers: {
              'X-CSRFToken': getCsrfToken(),
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ visible }),
          });

          if (response.ok) {
            // Update local data
            const calendar = myCalendars.find(c => c.id === calendarId);
            if (calendar) {
              calendar.visible = visible;
            }
          }
        } catch (error) {
          console.error('Error updating calendar visibility:', error);
        }
      });
    });
  }

  // ------------------------------------------------------------
  // Handlers
  // ------------------------------------------------------------
  async function handleModalOpen(e) {
    if (!e?.detail || e.detail.modalId !== modalId) return;

    await fetchGoogleStatus();
    if (isGoogleConnected) {
      await fetchGoogleCalendars();
    } else {
      renderGoogleCalendars();
    }
    await fetchMyCalendars();
  }

  async function handleConnectClick() {
    // ✅ 연동 안 됨: OAuth 시작 / 연동 됨: 설정 관리로
    if (isGoogleConnected) {
      window.location.href = `${API_BASE}/google/settings/`;
    } else {
      window.location.href = `${API_BASE}/google/login/`;
    }
  }

  async function handleDisconnectClick() {
    // ✅ 연동 해제(우리 서비스에서 토큰/설정 삭제)
    window.location.href = `${API_BASE}/google/logout/`;
  }

  async function handleSaveClick() {
    try {
      await saveGoogleCalendarsSelection();

      if (window.notyf) window.notyf.success("저장되었습니다.");

      await fetchGoogleCalendars();

      if (window.SchedulePage) {
        if (window.SchedulePage.loadSchedules) window.SchedulePage.loadSchedules();
        if (window.SchedulePage.refreshCalendar) window.SchedulePage.refreshCalendar();
      }
    } catch (err) {
      console.error("save failed:", err);
      if (window.notyf) window.notyf.error(err.message || "저장에 실패했습니다.");
    }
  }

  // ------------------------------------------------------------
  // Init
  // ------------------------------------------------------------
  function initGoogleCalendarModal() {
    const modal = document.getElementById(modalId);
    if (!modal) return;

    modal.addEventListener("modal:open", handleModalOpen);

    if (googleCalendarConnectBtn) {
      googleCalendarConnectBtn.addEventListener("click", (e) => {
        e.preventDefault();
        handleConnectClick();
      });
    }

    if (googleCalendarDisconnectBtn) {
      googleCalendarDisconnectBtn.addEventListener("click", (e) => {
        e.preventDefault();
        handleDisconnectClick();
      });
    }

    if (googleCalendarSaveBtn) {
      googleCalendarSaveBtn.addEventListener("click", (e) => {
        e.preventDefault();
        handleSaveClick();
      });
    }

    fetchGoogleStatus();
    fetchMyCalendars();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initGoogleCalendarModal);
  } else {
    initGoogleCalendarModal();
  }

  if (typeof window !== "undefined") {
    window.GoogleCalendarModal = {
      init: initGoogleCalendarModal,
      reload: fetchGoogleCalendars,
      reloadMyCalendars: fetchMyCalendars,
      get selected() {
        return Array.from(selectedGoogleCalendars);
      },
      get colors() {
        return { ...calendarColors };
      },
    };
  }
})();
