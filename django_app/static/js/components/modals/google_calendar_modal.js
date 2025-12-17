// google_calendar_modal.js
(function () {
  "use strict";

  // ✅ schedule 앱 Base URL (네 프로젝트 기준)
  const API_BASE = "/schedule";

  // State
  let isGoogleConnected = false;
  let googleCalendars = []; // [{ id, name, email, selected, color }]
  let selectedGoogleCalendars = new Set(); // calendar_id set
  let calendarColors = {}; // { [calendar_id]: "#RRGGBB" }

  // DOM
  const modalId = "googleCalendarModal";
  const connectionStatusIndicator = document.getElementById("connectionStatusIndicator");
  const connectionStatusText = document.getElementById("connectionStatusText");
  const googleCalendarConnectBtn = document.getElementById("googleCalendarConnectBtn");
  const googleCalendarList = document.getElementById("googleCalendarList");
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
    // allow #RGB or #RRGGBB
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

      // state sync
      selectedGoogleCalendars.clear();
      calendarColors = {};
      googleCalendars.forEach((c) => {
        if (c.selected) selectedGoogleCalendars.add(c.id);
        calendarColors[c.id] = normalizeHex(c.color, "#3b82f6");
      });

      console.log("✅ fetchGoogleCalendars() loaded:", {
        count: googleCalendars.length,
        selected: Array.from(selectedGoogleCalendars),
        colors: { ...calendarColors },
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

    // ✅ payload: selected + calendar_colors 같이 보냄
    const payload = {
      selected_calendar_ids: selectedIds,
      calendar_colors: calendarColors,
    };

    console.log("📤 SAVE payload:", JSON.parse(JSON.stringify(payload)));

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

    console.log("📥 SAVE response:", { ok: res.ok, status: res.status, json });

    if (!res.ok) {
      throw new Error(json.error || json.detail || "저장에 실패했습니다.");
    }

    return json;
  }

  // ------------------------------------------------------------
  // Render
  // ------------------------------------------------------------
  function renderConnectionStatus() {
    if (!connectionStatusIndicator || !connectionStatusText) return;

    if (isGoogleConnected) {
      connectionStatusIndicator.classList.add("connected");
      connectionStatusText.textContent = "Google Calendar 연동됨";
      if (googleCalendarConnectBtn) {
        googleCalendarConnectBtn.textContent = "연동 관리";
      }
    } else {
      connectionStatusIndicator.classList.remove("connected");
      connectionStatusText.textContent = "Google Calendar 미연동";
      if (googleCalendarConnectBtn) {
        googleCalendarConnectBtn.textContent = "Google Calendar 연결";
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

    // ✅ selected 먼저, unselected 나중
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
              <!-- ✅ 색상 선택 -->
              <input
                type="color"
                class="google-calendar-color"
                data-calendar-id="${safeId}"
                value="${color}"
                title="캘린더 색상"
                style="width:44px; height:26px; padding:0; border:1px solid #d1d5db; border-radius:6px; background:#fff; cursor:pointer;"
              />
              <!-- ✅ 체크박스 -->
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

    // Events bind
    bindCalendarRowEvents();
  }

  function bindCalendarRowEvents() {
    // checkbox change
    document.querySelectorAll('input.google-calendar-checkbox[data-calendar-id]').forEach((cb) => {
      cb.addEventListener("change", (e) => {
        const calId = e.target.getAttribute("data-calendar-id");

        console.log("☑️ CHECK change fired", { calId, checked: e.target.checked });

        if (!calId) return;

        if (e.target.checked) selectedGoogleCalendars.add(calId);
        else selectedGoogleCalendars.delete(calId);

        console.log("✅ selectedGoogleCalendars now:", Array.from(selectedGoogleCalendars));
      });
    });

    // color change
    document.querySelectorAll('input.google-calendar-color[data-calendar-id]').forEach((inp) => {
      inp.addEventListener("change", (e) => {
        const calId = e.target.getAttribute("data-calendar-id");

        console.log("🎨 COLOR CHANGE fired", {
          calId,
          raw: e.target.value,
        });

        if (!calId) {
          console.warn("⚠️ COLOR CHANGE: calId is missing (data-calendar-id 없음)");
          return;
        }

        const color = normalizeHex(e.target.value, "#3b82f6");
        calendarColors[calId] = color;

        console.log("✅ calendarColors updated", { calId, color, calendarColors: { ...calendarColors } });

        // 왼쪽 dot 색도 같이 갱신 (row 안에서만)
        const row = e.target.closest(".google-calendar-item");
        if (row) {
          const dot = row.querySelector(".google-calendar-dot");
          if (dot) dot.style.backgroundColor = color;
          else console.warn("⚠️ dot element not found (.google-calendar-dot 없음)");
        } else {
          console.warn("⚠️ row not found (.google-calendar-item 없음)");
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
  }

  function handleModalClose(e) {
    if (!e?.detail || e.detail.modalId !== modalId) return;
    // 필요하면 state reset 가능
  }

  async function handleConnectClick() {
    // 연결 버튼은 보통 백엔드 OAuth 시작 URL로 이동
    window.location.href = `${API_BASE}/google/login/`;
  }

  async function handleSaveClick() {
    try {
      await saveGoogleCalendarsSelection();

      if (window.notyf) window.notyf.success("저장되었습니다.");

      // 저장 후 최신값 다시 불러오기 (DB 반영 확인)
      await fetchGoogleCalendars();

      // 캘린더 화면 갱신 (FullCalendar reload)
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

    // modal open/close (너희 Modal 시스템 이벤트)
    modal.addEventListener("modal:open", handleModalOpen);
    modal.addEventListener("modal:close", handleModalClose);

    // connect btn
    if (googleCalendarConnectBtn) {
      googleCalendarConnectBtn.addEventListener("click", (e) => {
        e.preventDefault();
        handleConnectClick();
      });
    }

    // save btn
    if (googleCalendarSaveBtn) {
      googleCalendarSaveBtn.addEventListener("click", (e) => {
        e.preventDefault();
        handleSaveClick();
      });
    }

    // 초기 status 한 번
    fetchGoogleStatus();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initGoogleCalendarModal);
  } else {
    initGoogleCalendarModal();
  }

  // expose
  if (typeof window !== "undefined") {
    window.GoogleCalendarModal = {
      init: initGoogleCalendarModal,
      reload: fetchGoogleCalendars,
      get selected() {
        return Array.from(selectedGoogleCalendars);
      },
      get colors() {
        return { ...calendarColors };
      },
    };
  }
})();
