// Settings Modal Component JavaScript Logic

// State variables
let settings = {
    notifications: true,
    emailAlerts: true,
    darkMode: false,
    language: 'ko',
    autoSave: true
};

// DOM elements
const modalId = 'settingsModal';
const notificationsToggle = document.getElementById('notificationsToggle');
const emailAlertsToggle = document.getElementById('emailAlertsToggle');
const darkModeToggle = document.getElementById('darkModeToggle');
const autoSaveToggle = document.getElementById('autoSaveToggle');
const languageSelect = document.getElementById('languageSelect');
const saveSettingsBtn = document.getElementById('saveSettingsBtn');

// Initialize modal
function initSettingsModal() {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    
    // Load settings
    loadSettings();
    updateUI();
    
    // Toggle handlers
    if (notificationsToggle) {
        notificationsToggle.addEventListener('change', (e) => {
            toggleNotification();
        });
    }
    
    if (emailAlertsToggle) {
        emailAlertsToggle.addEventListener('change', (e) => {
            toggleEmailAlerts();
        });
    }
    
    // Dark mode toggle removed from React component, but keeping for backward compatibility
    if (darkModeToggle) {
        darkModeToggle.addEventListener('change', (e) => {
            toggleDarkMode();
        });
    }
    
    if (autoSaveToggle) {
        autoSaveToggle.addEventListener('change', (e) => {
            toggleAutoSave();
        });
    }
    
    if (languageSelect) {
        languageSelect.addEventListener('change', (e) => {
            setLanguage(e.target.value);
        });
    }
    
    // Footer button handlers
    const footer = modal.querySelector('.modal-footer');
    if (footer) {
        footer.addEventListener('click', (e) => {
            const action = e.target.closest('[data-action]')?.getAttribute('data-action');
            if (action === 'close') {
                closeSettingsModal();
            } else if (action === 'save') {
                handleSave();
            }
        });
    }
    
    // Listen for modal open event
    document.addEventListener('modal:open', (e) => {
        if (e.detail.modalId === modalId) {
            loadSettings();
            updateUI();
        }
    });
    
    // Listen for modal close event
    document.addEventListener('modal:close', (e) => {
        if (e.detail.modalId === modalId) {
            // Reload settings to discard changes
            loadSettings();
            updateUI();
        }
    });
}

// Update UI from settings
function updateUI() {
    if (notificationsToggle) {
        notificationsToggle.checked = settings.notifications;
    }
    if (emailAlertsToggle) {
        emailAlertsToggle.checked = settings.emailAlerts;
    }
    // Dark mode toggle removed from React component
    if (darkModeToggle) {
        darkModeToggle.checked = settings.darkMode || false;
    }
    if (autoSaveToggle) {
        autoSaveToggle.checked = settings.autoSave;
    }
    if (languageSelect) {
        languageSelect.value = settings.language;
    }
}

// Toggle notification
function toggleNotification() {
    settings.notifications = !settings.notifications;
}

// Toggle email alerts
function toggleEmailAlerts() {
    settings.emailAlerts = !settings.emailAlerts;
}

// Toggle dark mode (removed from React component, but keeping for backward compatibility)
function toggleDarkMode() {
    // React component doesn't have dark mode, but keeping function for backward compatibility
    if (darkModeToggle) {
        settings.darkMode = darkModeToggle.checked;
    }
}

// Toggle auto save
function toggleAutoSave() {
    settings.autoSave = !settings.autoSave;
}

// Set language
function setLanguage(lang) {
    settings.language = lang;
}

// Update setting
function updateSetting(key, value) {
    settings = {
        ...settings,
        [key]: value
    };
}

// Handle save
async function handleSave() {
    // Save to localStorage
    if (typeof localStorage !== 'undefined') {
        localStorage.setItem('helixops_settings', JSON.stringify(settings));
    }
    
    // Save to backend via API
    try {
        const response = await fetch('/api/settings/', {
            method: 'PUT',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(settings),
        });
        
        if (response.ok) {
            // Show success message
            if (window.notyf) {
                window.notyf.success('설정이 저장되었습니다.');
            }
            
            // Close modal
            closeSettingsModal();
            
            // Trigger custom event
            const event = new CustomEvent('settings:saved', {
                detail: settings
            });
            document.dispatchEvent(event);
        } else {
            throw new Error('Failed to save settings');
        }
    } catch (error) {
        console.error('Error saving settings:', error);
        
        // Still save to localStorage as fallback
        if (typeof localStorage !== 'undefined') {
            localStorage.setItem('helixops_settings', JSON.stringify(settings));
        }
        
        if (window.notyf) {
            window.notyf.error('설정 저장에 실패했습니다.');
        }
    }
}

// Load settings from storage
function loadSettings() {
    // Load from localStorage first
    if (typeof localStorage !== 'undefined') {
        const saved = localStorage.getItem('helixops_settings');
        if (saved) {
            try {
                const parsed = JSON.parse(saved);
                settings = { ...settings, ...parsed };
            } catch (e) {
                console.error('Failed to load settings from localStorage:', e);
            }
        }
    }
    
    // Load from backend via API
    fetch('/api/settings/', {
        method: 'GET',
        headers: {
            'X-CSRFToken': getCsrfToken(),
            'Content-Type': 'application/json',
        },
    })
    .then(response => {
        if (response.ok) {
            return response.json();
        }
        throw new Error('Failed to load settings');
    })
    .then(data => {
        if (data && typeof data === 'object') {
            settings = { ...settings, ...data };
            updateUI();
        }
    })
    .catch(error => {
        console.error('Error loading settings from API:', error);
        // Use localStorage settings as fallback
        updateUI();
    });
}

// Open modal
function openSettingsModal() {
    if (window.Modal) {
        window.Modal.open(modalId);
    }
    loadSettings();
    updateUI();
}

// Close modal
function closeSettingsModal() {
    if (window.Modal) {
        window.Modal.close(modalId);
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

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSettingsModal);
} else {
    initSettingsModal();
}

// Load settings on page load
if (typeof window !== 'undefined') {
    loadSettings();
    updateUI();
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.SettingsModal = {
        open: openSettingsModal,
        close: closeSettingsModal,
        loadSettings,
        handleSave,
        toggleNotification,
        toggleEmailAlerts,
        toggleDarkMode,
        toggleAutoSave,
        setLanguage,
        updateSetting,
        getSettings: () => ({ ...settings }),
    };
}
