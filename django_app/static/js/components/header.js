// Header Component JavaScript Logic

// State variables
let showNotificationDropdown = false;
let notificationRefreshInterval = null;

// DOM elements
const notificationBtn = document.getElementById('notificationBtn');
const notificationDropdown = document.getElementById('notificationDropdown');

// Initialize header functionality
function initHeader() {
    if (!notificationBtn || !notificationDropdown) {
        console.warn('Header notification elements not found');
        return;
    }

    // Notification dropdown toggle
    notificationBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleNotificationDropdown();
    });

    // Click outside handler
    document.addEventListener('click', (e) => {
        if (showNotificationDropdown && !notificationDropdown.contains(e.target) && !notificationBtn.contains(e.target)) {
            closeNotificationDropdown();
        }
    });

    // Notification item click handler (동적으로 추가되는 항목을 위해 이벤트 위임 사용)
    const notificationContent = document.getElementById('notificationContent');
    if (notificationContent) {
        notificationContent.addEventListener('click', (e) => {
            const item = e.target.closest('.notification-item[data-notification-id]');
            if (item) {
                const notificationId = item.getAttribute('data-notification-id');
                handleNotificationClick(notificationId);
            }
        });
    }

    // 주기적으로 알림 카운트 업데이트 (30초마다)
    startNotificationRefresh();
}

function toggleNotificationDropdown() {
    showNotificationDropdown = !showNotificationDropdown;
    if (showNotificationDropdown) {
        notificationDropdown.classList.add('show');
        // 드롭다운을 열 때마다 최신 알림 가져오기
        fetchNotifications();
    } else {
        notificationDropdown.classList.remove('show');
    }
}

function closeNotificationDropdown() {
    showNotificationDropdown = false;
    if (notificationDropdown) {
        notificationDropdown.classList.remove('show');
    }
}

// Handle notification click
function handleNotificationClick(notificationId) {
    // Mark as read via API
    fetch(`/api/notifications/${notificationId}/read/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCsrfToken(),
            'Content-Type': 'application/json',
        },
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update UI
            const item = document.querySelector(`[data-notification-id="${notificationId}"]`);
            if (item) {
                item.classList.remove('unread');
                const dot = item.querySelector('.unread-dot');
                if (dot) dot.remove();
            }
            
            // 서버에서 반환된 최신 unread_count로 업데이트
            if (data.unread_count !== undefined) {
                const countElement = document.getElementById('unreadCount');
                if (countElement) {
                    countElement.textContent = data.unread_count;
                }
                
                // 알림 점 표시/숨김
                const notificationDot = document.querySelector('.notification-dot');
                if (data.unread_count > 0) {
                    if (!notificationDot) {
                        const notificationBtn = document.getElementById('notificationBtn');
                        if (notificationBtn) {
                            const dot = document.createElement('span');
                            dot.className = 'notification-dot';
                            notificationBtn.appendChild(dot);
                        }
                    } else {
                        notificationDot.style.display = 'block';
                    }
                } else if (notificationDot) {
                    notificationDot.style.display = 'none';
                }
            } else {
                // fallback: 기존 방식으로 카운트 업데이트
                updateUnreadCount();
            }
        }
    })
    .catch(error => {
        console.error('Error marking notification as read:', error);
    });
}

// Fetch notifications from API
function fetchNotifications() {
    fetch('/api/notifications/', {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
        },
        credentials: 'include',
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            updateNotificationUI(data.unread_count, data.notifications);
        }
    })
    .catch(error => {
        console.error('Error fetching notifications:', error);
    });
}

// Update notification UI with fetched data
function updateNotificationUI(unreadCount, notifications) {
    // Update unread count
    const countElement = document.getElementById('unreadCount');
    if (countElement) {
        countElement.textContent = unreadCount;
    }
    
    // Update notification dot visibility
    const notificationDot = document.querySelector('.notification-dot');
    if (notificationDot) {
        notificationDot.style.display = unreadCount > 0 ? 'block' : 'none';
    } else if (unreadCount > 0) {
        // 알림 점이 없으면 생성
        const notificationBtn = document.getElementById('notificationBtn');
        if (notificationBtn) {
            const dot = document.createElement('span');
            dot.className = 'notification-dot';
            notificationBtn.appendChild(dot);
        }
    }
    
    // Update notification list
    const notificationContent = document.getElementById('notificationContent');
    if (notificationContent) {
        if (notifications.length === 0) {
            notificationContent.innerHTML = `
                <div class="notification-item">
                    <div class="notification-content">
                        <p class="notification-message">알림이 없습니다.</p>
                    </div>
                </div>
            `;
        } else {
            notificationContent.innerHTML = notifications.map(notif => `
                <div class="notification-item ${notif.unread ? 'unread' : ''}" data-notification-id="${notif.id}">
                    ${notif.unread ? '<span class="unread-dot"></span>' : ''}
                    <div class="notification-content">
                        <p class="notification-title">${escapeHtml(notif.title)}</p>
                        <p class="notification-message">${escapeHtml(notif.message)}</p>
                        <p class="notification-time">${escapeHtml(notif.time)}</p>
                    </div>
                </div>
            `).join('');
        }
    }
}

// Update unread count (기존 함수 유지 - 호환성)
function updateUnreadCount() {
    const unreadCount = document.querySelectorAll('.notification-item.unread').length;
    const countElement = document.getElementById('unreadCount');
    if (countElement) {
        countElement.textContent = unreadCount;
    }
    
    // Update notification dot visibility
    const notificationDot = document.querySelector('.notification-dot');
    if (notificationDot) {
        notificationDot.style.display = unreadCount > 0 ? 'block' : 'none';
    }
}

// Start periodic notification refresh
function startNotificationRefresh() {
    // 30초마다 알림 카운트만 업데이트 (드롭다운이 열려있지 않을 때)
    notificationRefreshInterval = setInterval(() => {
        if (!showNotificationDropdown) {
            // 카운트만 업데이트 (빠른 업데이트)
            fetch('/api/notifications/?limit=1', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include',
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // 카운트만 업데이트
                    const countElement = document.getElementById('unreadCount');
                    if (countElement) {
                        countElement.textContent = data.unread_count;
                    }
                    
                    // 알림 점 표시/숨김
                    const notificationDot = document.querySelector('.notification-dot');
                    if (data.unread_count > 0) {
                        if (!notificationDot) {
                            const notificationBtn = document.getElementById('notificationBtn');
                            if (notificationBtn) {
                                const dot = document.createElement('span');
                                dot.className = 'notification-dot';
                                notificationBtn.appendChild(dot);
                            }
                        }
                    } else if (notificationDot) {
                        notificationDot.style.display = 'none';
                    }
                }
            })
            .catch(error => {
                console.error('Error refreshing notification count:', error);
            });
        }
    }, 30000); // 30초마다
}

// Stop notification refresh
function stopNotificationRefresh() {
    if (notificationRefreshInterval) {
        clearInterval(notificationRefreshInterval);
        notificationRefreshInterval = null;
    }
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
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
    return '';
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initHeader);
} else {
    initHeader();
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.HeaderComponent = {
        toggleNotificationDropdown,
        closeNotificationDropdown,
        updateUnreadCount,
        fetchNotifications,
        startNotificationRefresh,
        stopNotificationRefresh,
    };
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    stopNotificationRefresh();
});
