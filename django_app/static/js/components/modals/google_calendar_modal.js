// Google Calendar Modal Component JavaScript Logic
(function() {
    'use strict';

    // State variables
    let isGoogleConnected = false;
    let selectedGoogleCalendars = [];
    let googleCalendars = [];
    let myCalendars = [];

    // DOM elements
    const modalId = 'googleCalendarModal';
    const connectionStatusIndicator = document.getElementById('connectionStatusIndicator');
    const connectionStatusText = document.getElementById('connectionStatusText');
    const googleCalendarConnectBtn = document.getElementById('googleCalendarConnectBtn');
    const googleCalendarList = document.getElementById('googleCalendarList');
    const myCalendarList = document.getElementById('myCalendarList');
    const googleCalendarSaveBtn = document.getElementById('googleCalendarSaveBtn');

// Initialize modal
function initGoogleCalendarModal() {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    
    // Connect button
    if (googleCalendarConnectBtn) {
        googleCalendarConnectBtn.addEventListener('click', handleConnect);
    }
    
    // Save button
    if (googleCalendarSaveBtn) {
        googleCalendarSaveBtn.addEventListener('click', handleSave);
    }
    
    // Modal events
    modal.addEventListener('modal:open', handleModalOpen);
    
    // Load initial state
    loadGoogleCalendarStatus();
}

// Handle modal open
function handleModalOpen(e) {
    if (e.detail.modalId !== modalId) return;
    loadGoogleCalendarStatus();
    loadGoogleCalendars();
    loadMyCalendars();
}

// Load Google Calendar connection status
async function loadGoogleCalendarStatus() {
    try {
        const response = await fetch('/api/google-calendar/status/', {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
        });
        
        if (response.ok) {
            const data = await response.json();
            isGoogleConnected = data.connected || false;
            renderConnectionStatus();
        }
    } catch (error) {
        console.error('Error loading Google Calendar status:', error);
        // Default to not connected
        isGoogleConnected = false;
        renderConnectionStatus();
    }
}

// Load Google Calendars
async function loadGoogleCalendars() {
    try {
        const response = await fetch('/api/google-calendar/calendars/', {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
        });
        
        if (response.ok) {
            const data = await response.json();
            googleCalendars = data.results || data;
            selectedGoogleCalendars = googleCalendars
                .filter(cal => cal.selected)
                .map(cal => cal.id);
            renderGoogleCalendars();
        }
    } catch (error) {
        console.error('Error loading Google Calendars:', error);
        googleCalendars = [];
        renderGoogleCalendars();
    }
}

// Load My Calendars
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
            myCalendars = data.results || data;
            renderMyCalendars();
        }
    } catch (error) {
        console.error('Error loading my calendars:', error);
        myCalendars = [];
        renderMyCalendars();
    }
}

// Render connection status
function renderConnectionStatus() {
    if (connectionStatusIndicator) {
        if (isGoogleConnected) {
            connectionStatusIndicator.className = 'connection-status-indicator connected';
            connectionStatusIndicator.innerHTML = '<i class="fas fa-check-circle"></i>';
        } else {
            connectionStatusIndicator.className = 'connection-status-indicator disconnected';
            connectionStatusIndicator.innerHTML = '';
        }
    }
    
    if (connectionStatusText) {
        connectionStatusText.textContent = isGoogleConnected 
            ? 'Google Calendar 연결됨' 
            : 'Google Calendar 연결 안 됨';
    }
    
    if (googleCalendarConnectBtn) {
        googleCalendarConnectBtn.style.display = isGoogleConnected ? 'none' : 'block';
    }
}

// Render Google Calendars
function renderGoogleCalendars() {
    if (!googleCalendarList) return;
    
    if (googleCalendars.length === 0) {
        googleCalendarList.innerHTML = '<p class="empty-text">연결된 캘린더가 없습니다.</p>';
        return;
    }
    
    googleCalendarList.innerHTML = googleCalendars.map(calendar => `
        <div class="google-calendar-item">
            <div class="calendar-color-indicator" style="background-color: ${calendar.color || '#3b82f6'};"></div>
            <div class="calendar-info">
                <p class="calendar-name">${escapeHtml(calendar.name || '')}</p>
                <p class="calendar-email">${escapeHtml(calendar.email || '')}</p>
            </div>
            <input
                type="checkbox"
                class="calendar-checkbox"
                data-calendar-id="${calendar.id}"
                ${selectedGoogleCalendars.includes(calendar.id) ? 'checked' : ''}
            />
        </div>
    `).join('');
    
    // Attach checkbox handlers
    const checkboxes = googleCalendarList.querySelectorAll('.calendar-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.addEventListener('change', (e) => {
            const calendarId = parseInt(e.target.getAttribute('data-calendar-id'));
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

// Render My Calendars
function renderMyCalendars() {
    if (!myCalendarList) return;
    
    if (myCalendars.length === 0) {
        myCalendarList.innerHTML = '<p class="empty-text">캘린더가 없습니다.</p>';
        return;
    }
    
    myCalendarList.innerHTML = myCalendars.map(calendar => `
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
    
    // Attach checkbox handlers
    const checkboxes = myCalendarList.querySelectorAll('.calendar-checkbox');
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

// Handle connect
async function handleConnect() {
    try {
        // Redirect to Google OAuth
        window.location.href = '/schedule/google-connect/';
    } catch (error) {
        console.error('Error connecting Google Calendar:', error);
        if (window.notyf) {
            window.notyf.error('Google Calendar 연결 중 오류가 발생했습니다.');
        }
    }
}

// Handle save
async function handleSave() {
    try {
        // Save selected Google Calendars
        const response = await fetch('/api/google-calendar/calendars/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                selected_calendar_ids: selectedGoogleCalendars,
            }),
        });
        
        if (response.ok) {
            if (window.notyf) {
                window.notyf.success('설정이 저장되었습니다.');
            }
            
            // Close modal
            if (window.Modal) {
                window.Modal.close(modalId);
            }
            
            // Refresh calendar
            if (window.SchedulePage && window.SchedulePage.refreshCalendar) {
                window.SchedulePage.refreshCalendar();
            }
        } else {
            const error = await response.json();
            console.error('Failed to save settings:', error);
            if (window.notyf) {
                window.notyf.error('설정 저장에 실패했습니다.');
            }
        }
    } catch (error) {
        console.error('Error saving settings:', error);
        if (window.notyf) {
            window.notyf.error('설정 저장 중 오류가 발생했습니다.');
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

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initGoogleCalendarModal);
} else {
    initGoogleCalendarModal();
}

    // Export for use in other modules
    if (typeof window !== 'undefined') {
        window.GoogleCalendarModal = {
            init: initGoogleCalendarModal,
        };
    }
})();
