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

// 마지막 알림 ID 추적 (새 알림 감지용)
let lastFetchedNotificationId = null;

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
            // 새 실험 알림이 있으면 해당 실험 업데이트
            if (data.notifications && data.notifications.length > 0) {
                const latestNotification = data.notifications[0];
                const isNewNotification = lastFetchedNotificationId === null || 
                                         latestNotification.id !== lastFetchedNotificationId;
                
                if (isNewNotification && latestNotification.notification_type === 'E' && latestNotification.related_sid) {
                    const experimentId = latestNotification.related_sid;
                    console.log(`[Header] New experiment notification detected in fetch: experiment ${experimentId}`);
                    
                    // 실험 페이지가 있으면 해당 실험 업데이트
                    if (window.ExperimentPage && window.ExperimentPage.updateExperimentFromNotification) {
                        window.ExperimentPage.updateExperimentFromNotification(experimentId);
                    }
                    
                    // 대시보드 페이지가 있으면 해당 실험 업데이트
                    if (window.DashboardPage && window.DashboardPage.updateDashboardExperimentFromNotification) {
                        window.DashboardPage.updateDashboardExperimentFromNotification(experimentId);
                    }
                    
                    lastFetchedNotificationId = latestNotification.id;
                } else if (isNewNotification) {
                    // 실험 알림이 아니어도 마지막 알림 ID 업데이트
                    lastFetchedNotificationId = latestNotification.id;
                }
            }
            
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
    // 마지막 알림 ID 추적 (새 알림 감지용)
    let lastNotificationId = null;
    
    // 실험 알림 감지를 위한 더 빠른 주기 (5초)
    function checkExperimentNotifications() {
        // 완료된 실험의 사이드바가 열려있으면 알림 요청 완전히 스킵
        const sidebar = document.getElementById('experimentResultSidebar');
        const isSidebarOpen = sidebar && 
                             sidebar.style.display !== 'none' && 
                             sidebar.style.display !== '' &&
                             sidebar.style.display !== 'hidden';
        
        if (isSidebarOpen) {
            // 사이드바가 열려있으면 실험 상태를 직접 확인
            const statusElement = document.getElementById('experimentResultStatus');
            const progressText = document.getElementById('experimentResultProgressText');
            
            // 상태가 '완료'이거나 진행률이 100%이면 알림 체크 스킵
            const statusText = statusElement ? statusElement.textContent.trim() : '';
            const progressValue = progressText ? parseInt(progressText.textContent.replace('%', '')) : 0;
            const isCompleted = statusText === '완료' || progressValue === 100 || window.currentExperimentIsCompleted === true;
            
            if (isCompleted) {
                // 완료된 실험의 사이드바가 열려있으면 알림 체크 완전히 스킵
                return;
            }
        }
        
        // 사이드바가 열려있지 않거나 완료되지 않은 경우에만 알림 체크
        fetch('/api/notifications/?limit=10', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
        })
        .then(response => response.json())
        .then(data => {
            if (data.success && data.notifications && data.notifications.length > 0) {
                // 실험 알림만 필터링
                const experimentNotifications = data.notifications.filter(notif => 
                    notif.notification_type === 'E' && notif.related_sid
                );
                
                // 새 실험 알림이 있으면 해당 실험 업데이트
                experimentNotifications.forEach(notif => {
                    const isNewNotification = lastNotificationId === null || 
                                             notif.id > lastNotificationId;
                    
                    if (isNewNotification) {
                        const experimentId = notif.related_sid;
                        console.log(`[Header] New experiment notification detected: experiment ${experimentId}, notification_id=${notif.id}`);
                        
                        // 실험 페이지가 있으면 해당 실험 업데이트
                        if (window.ExperimentPage && window.ExperimentPage.updateExperimentFromNotification) {
                            window.ExperimentPage.updateExperimentFromNotification(experimentId);
                        }
                        
                        // 대시보드 페이지가 있으면 해당 실험 업데이트
                        if (window.DashboardPage && window.DashboardPage.updateDashboardExperimentFromNotification) {
                            window.DashboardPage.updateDashboardExperimentFromNotification(experimentId);
                        }
                        
                        // 마지막 알림 ID 업데이트
                        if (lastNotificationId === null || notif.id > lastNotificationId) {
                            lastNotificationId = notif.id;
                        }
                    }
                });
            }
        })
        .catch(error => {
            console.error('Error checking experiment notifications:', error);
        });
    }
    
    // 실험 알림은 5초마다 체크 (더 빠른 반응성)
    window.__experimentNotificationCheckInterval = setInterval(checkExperimentNotifications, 5000);
    
    // 30초마다 알림 카운트만 업데이트 (드롭다운이 열려있지 않을 때)
    notificationRefreshInterval = setInterval(() => {
        // 완료된 실험의 사이드바가 열려있으면 알림 요청 스킵
        const sidebar = document.getElementById('experimentResultSidebar');
        const isSidebarOpen = sidebar && 
                             sidebar.style.display !== 'none' && 
                             sidebar.style.display !== '' &&
                             sidebar.style.display !== 'hidden';
        const isCompleted = window.currentExperimentIsCompleted === true;
        
        if (isSidebarOpen && isCompleted) {
            console.log('[Header] Skipping notification count update - completed experiment sidebar is open', {
                sidebarOpen: isSidebarOpen,
                isCompleted: isCompleted,
                currentExperimentId: window.currentExperimentId
            });
            return;
        }
        
        if (!showNotificationDropdown) {
            // 최신 알림 1개를 가져와서 카운트만 업데이트
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
                    
                    // 마지막 알림 ID 업데이트
                    if (data.notifications && data.notifications.length > 0) {
                        const latestNotification = data.notifications[0];
                        if (lastNotificationId === null || latestNotification.id > lastNotificationId) {
                            lastNotificationId = latestNotification.id;
                        }
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
    // 실험 알림 체크 인터벌도 정리 (전역 변수로 관리 필요)
    if (window.__experimentNotificationCheckInterval) {
        clearInterval(window.__experimentNotificationCheckInterval);
        window.__experimentNotificationCheckInterval = null;
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
