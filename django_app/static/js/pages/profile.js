// Profile Page JavaScript Logic

// State variables
let displayName = '';
let fullName = '';
let email = '';
let phoneNumber = '';
let organization = '';

// DOM elements
const displayNameInput = document.getElementById('displayName');
const fullNameInput = document.getElementById('fullName');
const emailInput = document.getElementById('email');
const phoneNumberInput = document.getElementById('phoneNumber');
const organizationInput = document.getElementById('organization');
const avatarEditBtn = document.getElementById('avatarEditBtn');
const linkGoogleBtn = document.getElementById('linkGoogleBtn');

// Initialize profile page
function initProfile() {
    // Load current values
    if (displayNameInput) {
        displayName = displayNameInput.value || '';
        displayNameInput.addEventListener('input', (e) => {
            displayName = e.target.value;
        });
    }

    if (fullNameInput) {
        fullName = fullNameInput.value || '';
        fullNameInput.addEventListener('input', (e) => {
            fullName = e.target.value;
        });
    }

    if (emailInput) {
        email = emailInput.value || '';
        emailInput.addEventListener('input', (e) => {
            email = e.target.value;
        });
    }

    if (phoneNumberInput) {
        phoneNumber = phoneNumberInput.value || '';
        phoneNumberInput.addEventListener('input', (e) => {
            phoneNumber = e.target.value;
        });
    }

    if (organizationInput) {
        organization = organizationInput.value || '';
        organizationInput.addEventListener('input', (e) => {
            organization = e.target.value;
        });
    }

    // Avatar edit button handler
    if (avatarEditBtn) {
        avatarEditBtn.addEventListener('click', handleAvatarEdit);
    }

    // Google link button handler
    if (linkGoogleBtn) {
        linkGoogleBtn.addEventListener('click', handleGoogleLink);
    }

    // Auto-save on blur (optional)
    const inputs = [displayNameInput, fullNameInput, emailInput, phoneNumberInput, organizationInput];
    inputs.forEach(input => {
        if (input) {
            input.addEventListener('blur', debounce(handleSave, 1000));
        }
    });
}

// Handle avatar edit
function handleAvatarEdit() {
    // Create file input
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = 'image/*';
    fileInput.style.display = 'none';

    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            // Validate file size (max 5MB)
            if (file.size > 5 * 1024 * 1024) {
                alert('파일 크기는 5MB 이하여야 합니다.');
                return;
            }

            // Validate file type
            if (!file.type.startsWith('image/')) {
                alert('이미지 파일만 업로드할 수 있습니다.');
                return;
            }

            // Preview image
            const reader = new FileReader();
            reader.onload = (e) => {
                const avatarImg = document.querySelector('.avatar-img');
                if (avatarImg) {
                    avatarImg.src = e.target.result;
                }
            };
            reader.readAsDataURL(file);

            // Upload to server
            uploadAvatar(file);
        }
    });

    document.body.appendChild(fileInput);
    fileInput.click();
    document.body.removeChild(fileInput);
}

// Upload avatar
function uploadAvatar(file) {
    const formData = new FormData();
    formData.append('avatar', file);

    fetch('/api/profile/avatar/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCsrfToken(),
        },
        body: formData,
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('Avatar uploaded successfully');
            // Update avatar URL if provided
            if (data.avatar_url) {
                const avatarImg = document.querySelector('.avatar-img');
                if (avatarImg) {
                    avatarImg.src = data.avatar_url;
                }
            }
        } else {
            alert('프로필 사진 업로드에 실패했습니다.');
        }
    })
    .catch(error => {
        console.error('Error uploading avatar:', error);
        alert('프로필 사진 업로드 중 오류가 발생했습니다.');
    });
}

// Handle Google account link
function handleGoogleLink() {
    // Redirect to Google OAuth
    window.location.href = '/accounts/google/login/';
}

// Handle save
function handleSave() {
    const data = {
        display_name: displayName,
        full_name: fullName,
        email: email,
        phone_number: phoneNumber,
        organization: organization,
    };

    fetch('/api/profile/', {
        method: 'PATCH',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify(data),
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('Profile updated successfully');
            // Optionally show success message
        } else {
            console.error('Failed to update profile:', data.error);
        }
    })
    .catch(error => {
        console.error('Error updating profile:', error);
    });
}

// Debounce function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
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
    document.addEventListener('DOMContentLoaded', initProfile);
} else {
    initProfile();
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.ProfilePage = {
        initProfile,
        handleAvatarEdit,
        handleGoogleLink,
        handleSave,
    };
}
