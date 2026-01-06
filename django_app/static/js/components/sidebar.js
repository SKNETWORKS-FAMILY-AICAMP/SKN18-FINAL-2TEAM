// HelixOps Sidebar JavaScript
// Based on assets/htmls/sidebar.js

(function() {
    'use strict';

    let currentPage = null;

    // Initialize
    function init() {
        setupMenuItems();
        setupSettingsButton();
        setupFeedbackButton();
    }

    // Setup menu items
    function setupMenuItems() {
        const menuItems = document.querySelectorAll('.sidebar-nav .sidebar-item[data-menu-id]');
        
        menuItems.forEach(item => {
            item.addEventListener('click', function(e) {
                const menuId = this.getAttribute('data-menu-id');
                if (menuId) {
                    navigateToPage(menuId);
                }
            });
        });

        // Set current page from active menu item
        const activeItem = document.querySelector('.sidebar-item.active[data-menu-id]');
        if (activeItem) {
            currentPage = activeItem.getAttribute('data-menu-id');
        }
    }

    // Navigate to page
    function navigateToPage(page) {
        currentPage = page;
        
        // Update active state
        const menuItems = document.querySelectorAll('.sidebar-nav .sidebar-item[data-menu-id]');
        menuItems.forEach(item => {
            if (item.getAttribute('data-menu-id') === page) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
    }

    // Setup settings button
    function setupSettingsButton() {
        const settingsBtn = document.querySelector('.sidebar-bottom .sidebar-item[data-menu-id="settings"]');
        if (settingsBtn) {
            settingsBtn.addEventListener('click', function(e) {
                e.preventDefault();
                console.log('Settings clicked');
                // 여기에 설정 모달 열기 로직을 추가하세요
            });
        }
    }

    // Setup feedback button
    function setupFeedbackButton() {
        const feedbackBtn = document.querySelector('.sidebar-bottom .sidebar-item[data-menu-id="feedback"]');
        if (feedbackBtn) {
            feedbackBtn.addEventListener('click', function(e) {
                e.preventDefault();
                console.log('Feedback clicked');
                
                // Prefer FeedbackModal API if available
                if (window.FeedbackModal && typeof window.FeedbackModal.open === 'function') {
                    window.FeedbackModal.open();
                } else if (window.Modal && typeof window.Modal.open === 'function') {
                    window.Modal.open('feedbackModal');
                } else {
                    const modal = document.getElementById('feedbackModal');
                    if (modal) {
                        modal.classList.add('active');
                        document.body.style.overflow = 'hidden';
                    } else {
                        console.warn('[Sidebar] feedbackModal element not found');
                    }
                }
            });
        }
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Export for use in other modules
    if (typeof window !== 'undefined') {
        window.SidebarComponent = {
            navigateToPage,
            getCurrentPage: function() { return currentPage; },
            isMenuActive: function(menuId) { return currentPage === menuId; }
        };
    }
})();
