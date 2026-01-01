// Profile Page JavaScript Logic

// State variables
let fullName = '';
let email = '';
let phoneNumber = '';
let organization = '';
let selectedAvatarFile = null; // 선택된 프로필 이미지 파일 (업로드 전까지 보관)
let originalValues = {}; // 초기값 저장

// DOM elements
const fullNameInput = document.getElementById('fullName');
const emailInput = document.getElementById('email');
const phoneNumberInput = document.getElementById('phoneNumber');
const organizationInput = document.getElementById('organization');
const avatarEditBtn = document.getElementById('avatarEditBtn');
const linkGoogleBtn = document.getElementById('linkGoogleBtn');
const saveProfileBtn = document.getElementById('saveProfileBtn');
const resetProfileBtn = document.getElementById('resetProfileBtn');

// Initialize profile page
function initProfile() {
    // Load current values and save original values
    if (fullNameInput) {
        fullName = fullNameInput.value || '';
        originalValues.fullName = fullName;
        fullNameInput.addEventListener('input', (e) => {
            fullName = e.target.value;
        });
    }

    if (emailInput) {
        email = emailInput.value || '';
        originalValues.email = email;
        // Email is readonly, no need to listen for input changes
    }

    if (phoneNumberInput) {
        phoneNumber = phoneNumberInput.value || '';
        originalValues.phoneNumber = phoneNumber;
        phoneNumberInput.addEventListener('input', (e) => {
            phoneNumber = e.target.value;
        });
    }

    if (organizationInput) {
        organization = organizationInput.value || '';
        originalValues.organization = organization;
        organizationInput.addEventListener('input', (e) => {
            organization = e.target.value;
        });
    }

    // Save original avatar URL
    const avatarImg = document.querySelector('.avatar-img');
    if (avatarImg) {
        originalValues.avatarUrl = avatarImg.src;
    } else {
        originalValues.avatarUrl = null;
    }

    // Avatar edit button handler
    if (avatarEditBtn) {
        avatarEditBtn.addEventListener('click', handleAvatarEdit);
    }

    // Google link button handler
    if (linkGoogleBtn) {
        linkGoogleBtn.addEventListener('click', handleGoogleLink);
    }

    // Save button handler
    if (saveProfileBtn) {
        saveProfileBtn.addEventListener('click', handleSaveProfile);
    }

    // Reset button handler
    if (resetProfileBtn) {
        resetProfileBtn.addEventListener('click', handleResetProfile);
    }
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

            // Preview image (업로드는 하지 않고 미리보기만)
            const reader = new FileReader();
            reader.onload = (e) => {
                const avatarFrame = document.querySelector('.avatar-frame');
                if (avatarFrame) {
                    // Remove placeholder if exists
                    const placeholder = avatarFrame.querySelector('.avatar-placeholder');
                    if (placeholder) {
                        placeholder.remove();
                    }
                    
                    // Add or update image
                    let avatarImg = avatarFrame.querySelector('.avatar-img');
                    if (!avatarImg) {
                        avatarImg = document.createElement('img');
                        avatarImg.className = 'avatar-img';
                        avatarImg.alt = 'Avatar';
                        avatarFrame.appendChild(avatarImg);
                    }
                    avatarImg.src = e.target.result;
                }
            };
            reader.readAsDataURL(file);

            // 파일을 변수에 저장 (수정하기 버튼 클릭 시 업로드)
            selectedAvatarFile = file;
        }
    });

    document.body.appendChild(fileInput);
    fileInput.click();
    document.body.removeChild(fileInput);
}

// Upload avatar (Promise 반환)
function uploadAvatar(file) {
    return new Promise((resolve, reject) => {
        const formData = new FormData();
        formData.append('avatar', file);

        fetch('/api/profile/avatar/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
            },
            body: formData,
        })
        .then(response => {
            // 응답이 JSON인지 확인
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                return response.text().then(text => {
                    throw new Error(`서버 응답이 JSON이 아닙니다: ${text.substring(0, 100)}`);
                });
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                console.log('Avatar uploaded successfully');
                // Update avatar URL if provided
                if (data.avatar_url) {
                    const avatarFrame = document.querySelector('.avatar-frame');
                    if (avatarFrame) {
                        // Remove placeholder if exists
                        const placeholder = avatarFrame.querySelector('.avatar-placeholder');
                        if (placeholder) {
                            placeholder.remove();
                        }
                        
                        // Add or update image
                        let avatarImg = avatarFrame.querySelector('.avatar-img');
                        if (!avatarImg) {
                            avatarImg = document.createElement('img');
                            avatarImg.className = 'avatar-img';
                            avatarImg.alt = 'Avatar';
                            avatarFrame.appendChild(avatarImg);
                        }
                        avatarImg.src = data.avatar_url;
                        // 원본 값 업데이트
                        originalValues.avatarUrl = data.avatar_url;
                    }
                }
                resolve(true);
            } else {
                reject(new Error(data.error || '알 수 없는 오류'));
            }
        })
        .catch(error => {
            console.error('Error uploading avatar:', error);
            reject(error);
        });
    });
}

// Handle Google account link
function handleGoogleLink() {
    // Redirect to Google OAuth
    window.location.href = '/accounts/google/login/';
}

// Handle save profile (수정하기 버튼 클릭)
async function handleSaveProfile() {
    // 버튼 비활성화
    if (saveProfileBtn) {
        saveProfileBtn.disabled = true;
        saveProfileBtn.textContent = '저장 중...';
    }

    try {
        // 1. 프로필 이미지가 선택된 경우 먼저 업로드
        if (selectedAvatarFile) {
            const avatarUploadSuccess = await uploadAvatar(selectedAvatarFile);
            if (!avatarUploadSuccess) {
                throw new Error('프로필 이미지 업로드에 실패했습니다.');
            }
            // 업로드 성공 후 파일 변수 초기화
            selectedAvatarFile = null;
        }

        // 2. 프로필 정보 업데이트
        const data = {
            full_name: fullName,
            // email is readonly, don't send it in update request
            phone_number: phoneNumber,
            organization: organization,
        };

        const response = await fetch('/api/profile/', {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
            body: JSON.stringify(data),
        });

        // 응답이 JSON인지 확인
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const text = await response.text();
            throw new Error(`서버 응답이 JSON이 아닙니다: ${text.substring(0, 100)}`);
        }

        const result = await response.json();
        
        if (result.success) {
            // 원본 값 업데이트
            originalValues.fullName = fullName;
            originalValues.phoneNumber = phoneNumber;
            originalValues.organization = organization;
            
            // 성공 메시지
            alert('프로필이 성공적으로 업데이트되었습니다.');
        } else {
            throw new Error(result.error || '알 수 없는 오류');
        }
    } catch (error) {
        console.error('Error updating profile:', error);
        alert('프로필 업데이트 중 오류가 발생했습니다: ' + error.message);
    } finally {
        // 버튼 활성화
        if (saveProfileBtn) {
            saveProfileBtn.disabled = false;
            saveProfileBtn.textContent = '수정하기';
        }
    }
}

// Handle reset profile (초기화 버튼 클릭)
function handleResetProfile() {
    if (!confirm('수정한 내용을 모두 취소하고 원래 값으로 되돌리시겠습니까?')) {
        return;
    }

    // 입력 필드 초기화
    if (fullNameInput) {
        fullNameInput.value = originalValues.fullName || '';
        fullName = originalValues.fullName || '';
    }

    if (phoneNumberInput) {
        phoneNumberInput.value = originalValues.phoneNumber || '';
        phoneNumber = originalValues.phoneNumber || '';
    }

    if (organizationInput) {
        organizationInput.value = originalValues.organization || '';
        organization = originalValues.organization || '';
    }

    // 프로필 이미지 초기화
    selectedAvatarFile = null;
    const avatarFrame = document.querySelector('.avatar-frame');
    if (avatarFrame) {
        const avatarImg = avatarFrame.querySelector('.avatar-img');
        if (originalValues.avatarUrl) {
            // 원본 이미지로 복원
            if (avatarImg) {
                avatarImg.src = originalValues.avatarUrl;
            } else {
                // 이미지가 없었던 경우 img 태그 생성
                const img = document.createElement('img');
                img.className = 'avatar-img';
                img.alt = 'Avatar';
                img.src = originalValues.avatarUrl;
                avatarFrame.appendChild(img);
            }
            // Placeholder 제거
            const placeholder = avatarFrame.querySelector('.avatar-placeholder');
            if (placeholder) {
                placeholder.remove();
            }
        } else {
            // 원본에 이미지가 없었던 경우 placeholder로 복원
            if (avatarImg) {
                avatarImg.remove();
            }
            const placeholder = document.createElement('div');
            placeholder.className = 'avatar-placeholder';
            const icon = document.createElement('i');
            icon.className = 'fa-solid fa-user';
            placeholder.appendChild(icon);
            avatarFrame.appendChild(placeholder);
        }
    }
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
        handleSaveProfile,
        handleResetProfile,
    };
}
