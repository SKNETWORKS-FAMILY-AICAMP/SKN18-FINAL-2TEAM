// Header Component JavaScript Logic

// State variables
let showNotificationDropdown = false;

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

    // Notification item click handler
    const notificationItems = document.querySelectorAll('.notification-item[data-notification-id]');
    notificationItems.forEach(item => {
        item.addEventListener('click', () => {
            const notificationId = item.getAttribute('data-notification-id');
            handleNotificationClick(notificationId);
        });
    });
}

function toggleNotificationDropdown() {
    showNotificationDropdown = !showNotificationDropdown;
    if (showNotificationDropdown) {
        notificationDropdown.classList.add('show');
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
                updateUnreadCount();
            }
        }
    })
    .catch(error => {
        console.error('Error marking notification as read:', error);
    });
}

// Update unread count
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
    };
}
