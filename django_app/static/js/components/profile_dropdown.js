// Profile Dropdown Component - Common JavaScript Logic

(function() {
    'use strict';

    // Initialize profile dropdown
    function initProfileDropdown(config) {
        const {
            buttonId,
            dropdownId,
            overlayId,
            positionType = 'header' // 'header' or 'sidebar'
        } = config;

        const profileBtn = document.getElementById(buttonId);
        const profileDropdown = document.getElementById(dropdownId);
        const profileOverlay = overlayId ? document.getElementById(overlayId) : null;

        if (!profileBtn || !profileDropdown) {
            console.warn(`Profile dropdown elements not found: ${buttonId}, ${dropdownId}`);
            return;
        }

        let showProfileDropdown = false;

        // Overlay click handler (header only)
        if (profileOverlay) {
            profileOverlay.addEventListener('click', () => {
                closeProfileDropdown();
            });
        }

        // Button click handler
        profileBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            toggleProfileDropdown();
        });

        // Click outside handler
        document.addEventListener('click', (e) => {
            if (showProfileDropdown && 
                !profileDropdown.contains(e.target) && 
                !profileBtn.contains(e.target)) {
                closeProfileDropdown();
            }
        });

        // Toggle profile dropdown
        function toggleProfileDropdown() {
            showProfileDropdown = !showProfileDropdown;
            
            if (showProfileDropdown) {
                profileDropdown.classList.add('show');
                if (profileOverlay) {
                    profileOverlay.classList.add('show');
                }

                // For sidebar, calculate position
                if (positionType === 'sidebar') {
                    const rect = profileBtn.getBoundingClientRect();
                    profileDropdown.style.position = 'fixed';
                    profileDropdown.style.left = (rect.right + 8) + 'px';
                    profileDropdown.style.bottom = (window.innerHeight - rect.bottom) + 'px';
                    profileDropdown.style.top = 'auto';
                    profileDropdown.style.right = 'auto';
                }
            } else {
                closeProfileDropdown();
            }
        }

        // Close profile dropdown
        function closeProfileDropdown() {
            showProfileDropdown = false;
            if (profileDropdown) {
                profileDropdown.classList.remove('show');
            }
            if (profileOverlay) {
                profileOverlay.classList.remove('show');
            }
        }

        // Export close function for external use
        return {
            toggle: toggleProfileDropdown,
            close: closeProfileDropdown
        };
    }

    // Initialize header profile dropdown
    function initHeaderProfileDropdown() {
        const profileBtn = document.getElementById('profileBtn');
        if (profileBtn) {
            initProfileDropdown({
                buttonId: 'profileBtn',
                dropdownId: 'profileDropdown',
                overlayId: 'profileDropdownOverlay',
                positionType: 'header'
            });
        }
    }

    // Initialize sidebar profile dropdown
    function initSidebarProfileDropdown() {
        const sidebarProfileBtn = document.getElementById('sidebarProfileBtn');
        if (sidebarProfileBtn) {
            initProfileDropdown({
                buttonId: 'sidebarProfileBtn',
                dropdownId: 'sidebarProfileDropdown',
                overlayId: null,
                positionType: 'sidebar'
            });
        }
    }

    // Initialize when DOM is ready
    function init() {
        initHeaderProfileDropdown();
        initSidebarProfileDropdown();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Export for use in other modules
    if (typeof window !== 'undefined') {
        window.ProfileDropdownComponent = {
            init: initProfileDropdown,
            initHeader: initHeaderProfileDropdown,
            initSidebar: initSidebarProfileDropdown
        };
    }
})();
