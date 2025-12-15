// Login Page JavaScript Logic

// State variables
let showPassword = false;
let isLoading = false;

// DOM elements
const loginForm = document.getElementById('loginForm');
const passwordInput = document.getElementById('id_password');
const passwordToggle = document.getElementById('passwordToggle');
const submitBtn = document.getElementById('submitBtn');
const submitText = document.getElementById('submitText');
const submitLoading = document.getElementById('submitLoading');
const emailInput = document.getElementById('id_username');

// Initialize login page
function initLogin() {
    console.log('[Login] Initializing login page...');
    console.log('[Login] Current URL:', window.location.href);
    
    // Password toggle handler
    if (passwordToggle && passwordInput) {
        passwordToggle.addEventListener('click', togglePasswordVisibility);
    }

    // Form submit handler
    if (loginForm) {
        console.log('[Login] Form element found:', {
            id: loginForm.id,
            action: loginForm.action,
            method: loginForm.method,
            hasCsrfToken: !!document.querySelector('[name=csrfmiddlewaretoken]')
        });
        loginForm.addEventListener('submit', handleSubmit);
    } else {
        console.error('[Login] Form element not found!');
    }

    // Auto-focus email input
    if (emailInput) {
        emailInput.focus();
    }

    // Enter key handler
    if (emailInput) {
        emailInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                console.log('[Login] Enter key pressed in email input, focusing password');
                e.preventDefault();
                if (passwordInput) {
                    passwordInput.focus();
                }
            }
        });
    }

    if (passwordInput) {
        passwordInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !isLoading) {
                console.log('[Login] Enter key pressed in password input, submitting form');
                // Don't prevent default - let the form submit naturally
                // The handleSubmit function will be called by the form's submit event
            }
        });
    }
}

// Toggle password visibility
function togglePasswordVisibility() {
    if (!passwordInput || !passwordToggle) return;

    showPassword = !showPassword;
    const icon = passwordToggle.querySelector('i');

    if (showPassword) {
        passwordInput.type = 'text';
        if (icon) {
            icon.classList.remove('fa-eye');
            icon.classList.add('fa-eye-slash');
        }
    } else {
        passwordInput.type = 'password';
        if (icon) {
            icon.classList.remove('fa-eye-slash');
            icon.classList.add('fa-eye');
        }
    }
}

// Handle form submit
async function handleSubmit(e) {
    console.log('[Login] Form submit triggered');
    
    if (isLoading) {
        console.log('[Login] Already loading, preventing duplicate submission');
        e.preventDefault();
        return;
    }

    // Basic validation
    if (!emailInput || !passwordInput) {
        console.error('[Login] Form inputs not found');
        e.preventDefault();
        return;
    }

    const email = emailInput.value.trim();
    const password = passwordInput.value;

    if (!email) {
        console.warn('[Login] Email validation failed: empty email');
        e.preventDefault();
        showError('이메일을 입력해주세요.');
        emailInput.focus();
        return;
    }

    if (!isValidEmail(email)) {
        console.warn('[Login] Email validation failed: invalid format', email);
        e.preventDefault();
        showError('올바른 이메일 형식이 아닙니다.');
        emailInput.focus();
        return;
    }

    if (!password) {
        console.warn('[Login] Password validation failed: empty password');
        e.preventDefault();
        showError('비밀번호를 입력해주세요.');
        passwordInput.focus();
        return;
    }

    console.log('[Login] Validation passed, setting loading state');
    
    // Set loading state
    isLoading = true;
    setLoadingState(true);

    // Log form submission details
    const formAction = loginForm.action || loginForm.getAttribute('action');
    const formMethod = loginForm.method || 'POST';
    const csrfToken = getCsrfToken();
    
    console.log('[Login] Form submission details:', {
        action: formAction,
        method: formMethod,
        hasCsrfToken: !!csrfToken,
        csrfTokenLength: csrfToken ? csrfToken.length : 0,
        email: email
    });

    // Monitor page navigation
    let navigationDetected = false;
    const navigationTimeout = setTimeout(() => {
        if (!navigationDetected) {
            console.error('[Login] Page navigation not detected after 3 seconds. Form may not have been submitted.');
            console.error('[Login] Current URL:', window.location.href);
            console.error('[Login] Form action:', formAction);
            console.error('[Login] Form method:', formMethod);
            setLoadingState(false);
            isLoading = false;
        }
    }, 3000);

    // Detect page navigation
    const beforeUnloadHandler = () => {
        navigationDetected = true;
        console.log('[Login] Page navigation detected (beforeunload)');
        clearTimeout(navigationTimeout);
        window.removeEventListener('beforeunload', beforeUnloadHandler);
    };
    window.addEventListener('beforeunload', beforeUnloadHandler);

    // Monitor network requests using Performance API
    const navigationObserver = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
            if (entry.name.includes('login') || entry.name.includes('accounts')) {
                console.log('[Login] Network request detected:', {
                    name: entry.name,
                    type: entry.entryType,
                    startTime: entry.startTime,
                    duration: entry.duration
                });
            }
        }
    });
    
    try {
        navigationObserver.observe({ entryTypes: ['navigation', 'resource'] });
    } catch (e) {
        console.warn('[Login] PerformanceObserver not supported:', e);
    }

    console.log('[Login] Allowing form to submit naturally (no preventDefault)...');
    
    // Force form submission if it doesn't happen naturally
    // Use a small delay to ensure all event handlers have run
    setTimeout(() => {
        // Check if we're still on the login page (form didn't submit)
        if (window.location.pathname.includes('/login') || window.location.pathname.includes('/accounts/login')) {
            console.warn('[Login] Form may not have submitted naturally, checking form state...');
            console.warn('[Login] Form element:', loginForm);
            console.warn('[Login] Form action:', loginForm?.action);
            console.warn('[Login] Form method:', loginForm?.method);
            
            // Try to submit the form explicitly as a last resort
            // This bypasses submit event handlers, so only use if natural submission failed
            if (loginForm && !navigationDetected) {
                console.log('[Login] Attempting explicit form submission...');
                // Create a new submit event and dispatch it
                const submitEvent = new Event('submit', { bubbles: true, cancelable: true });
                const submitted = loginForm.dispatchEvent(submitEvent);
                console.log('[Login] Submit event dispatched, cancelled:', !submitted);
                
                if (!submitted) {
                    console.error('[Login] Form submission was cancelled by another event handler!');
                } else {
                    // If event wasn't cancelled but form still didn't submit, use form.submit()
                    setTimeout(() => {
                        if (!navigationDetected && (window.location.pathname.includes('/login') || window.location.pathname.includes('/accounts/login'))) {
                            console.warn('[Login] Form still not submitted, using form.submit() as last resort');
                            loginForm.submit();
                        }
                    }, 500);
                }
            }
        }
    }, 200);
    
    // 폼이 자연스럽게 제출되도록 허용 (CSRF 토큰 포함)
    // e.preventDefault()를 호출하지 않으면 기본 폼 제출이 진행됨
}

// Set loading state
function setLoadingState(loading) {
    isLoading = loading;
    console.log('[Login] Loading state changed:', loading);

    if (submitBtn) {
        submitBtn.disabled = loading;
        console.log('[Login] Submit button disabled:', loading);
    }

    if (submitText && submitLoading) {
        if (loading) {
            submitText.style.display = 'none';
            submitLoading.style.display = 'inline-flex';
            console.log('[Login] Showing loading indicator');
        } else {
            submitText.style.display = 'inline';
            submitLoading.style.display = 'none';
            console.log('[Login] Hiding loading indicator');
        }
    }
}

// Validate email format
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

// Show error message
function showError(message) {
    console.error('[Login] Error:', message);
    
    // Remove existing error messages
    const existingErrors = document.querySelectorAll('.error-message');
    existingErrors.forEach(error => {
        if (!error.closest('.form-group')) {
            error.remove();
        }
    });

    // Create error message element
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.setAttribute('role', 'alert');
    errorDiv.textContent = message;

    // Insert before form
    if (loginForm) {
        loginForm.parentNode.insertBefore(errorDiv, loginForm);
        console.log('[Login] Error message displayed to user');
    }

    // Auto-remove after 5 seconds
    setTimeout(() => {
        errorDiv.remove();
    }, 5000);
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
    // Try to get from meta tag
    const metaTag = document.querySelector('meta[name=csrf-token]');
    if (metaTag) {
        return metaTag.getAttribute('content');
    }
    return '';
}

// Intercept network requests to monitor login API calls
function setupNetworkMonitoring() {
    // Monitor fetch requests
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        const url = args[0];
        if (typeof url === 'string' && (url.includes('login') || url.includes('accounts'))) {
            console.log('[Login] Fetch request detected:', {
                url: url,
                method: args[1]?.method || 'GET',
                timestamp: new Date().toISOString()
            });
        }
        return originalFetch.apply(this, args)
            .then(response => {
                if (typeof args[0] === 'string' && (args[0].includes('login') || args[0].includes('accounts'))) {
                    console.log('[Login] Fetch response received:', {
                        url: args[0],
                        status: response.status,
                        statusText: response.statusText,
                        ok: response.ok
                    });
                }
                return response;
            })
            .catch(error => {
                if (typeof args[0] === 'string' && (args[0].includes('login') || args[0].includes('accounts'))) {
                    console.error('[Login] Fetch request failed:', {
                        url: args[0],
                        error: error.message
                    });
                }
                throw error;
            });
    };

    // Monitor XMLHttpRequest
    const originalXHROpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url, ...rest) {
        if (typeof url === 'string' && (url.includes('login') || url.includes('accounts'))) {
            console.log('[Login] XMLHttpRequest detected:', {
                method: method,
                url: url,
                timestamp: new Date().toISOString()
            });
            
            this.addEventListener('load', function() {
                console.log('[Login] XMLHttpRequest response:', {
                    url: url,
                    status: this.status,
                    statusText: this.statusText,
                    readyState: this.readyState
                });
            });
            
            this.addEventListener('error', function() {
                console.error('[Login] XMLHttpRequest error:', {
                    url: url,
                    status: this.status
                });
            });
        }
        return originalXHROpen.apply(this, [method, url, ...rest]);
    };
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    console.log('[Login] DOM is loading, waiting for DOMContentLoaded');
    document.addEventListener('DOMContentLoaded', () => {
        console.log('[Login] DOMContentLoaded fired');
        setupNetworkMonitoring();
        initLogin();
    });
} else {
    console.log('[Login] DOM already ready, initializing immediately');
    setupNetworkMonitoring();
    initLogin();
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.LoginPage = {
        initLogin,
        togglePasswordVisibility,
        handleSubmit,
    };
}
