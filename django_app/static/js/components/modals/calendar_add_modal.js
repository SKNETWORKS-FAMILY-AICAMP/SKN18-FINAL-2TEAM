// Calendar Add Modal Component JavaScript Logic
(function() {
    'use strict';

    // DOM elements
    const modalId = 'calendarAddModal';
    let createCalendarBtn = null;
    let connectGoogleCalendarBtn = null;
    const calendarColorPool = [
        '#3b82f6',
        '#8b5cf6',
        '#10b981',
        '#f97316',
        '#ec4899',
        '#ef4444',
        '#6366f1',
        '#14b8a6'
    ];

    // Initialize modal
    function initCalendarAddModal() {
        const modal = document.getElementById(modalId);
        if (!modal) return;
        
        createCalendarBtn = document.getElementById('createCalendarBtn');
        connectGoogleCalendarBtn = document.getElementById('connectGoogleCalendarBtn');
        
        // Create calendar button
        if (createCalendarBtn) {
            createCalendarBtn.addEventListener('click', handleCreateCalendar);
        }
        
        // Connect Google Calendar button
        if (connectGoogleCalendarBtn) {
            connectGoogleCalendarBtn.addEventListener('click', handleConnectGoogleCalendar);
        }
        
        // Modal close handlers
        const closeBtn = modal.querySelector('.modal-close-btn');
        const closeActionBtn = modal.querySelector('[data-action="close"]');
        
        if (closeBtn) {
            closeBtn.addEventListener('click', closeModal);
        }
        
        if (closeActionBtn) {
            closeActionBtn.addEventListener('click', closeModal);
        }
        
        // Close on overlay click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeModal();
            }
        });
    }

    // Handle create calendar
    function handleCreateCalendar() {
        // Use SweetAlert2 for input
        if (window.Swal) {
            window.Swal.fire({
                title: '새 캘린더 생성',
                text: '캘린더 이름을 입력하세요',
                input: 'text',
                inputPlaceholder: '캘린더 이름',
                showCancelButton: true,
                confirmButtonText: '생성',
                cancelButtonText: '취소',
                confirmButtonColor: '#2563eb',
                cancelButtonColor: '#6b7280',
                reverseButtons: true,
                inputValidator: (value) => {
                    if (!value || !value.trim()) {
                        return '캘린더 이름을 입력해주세요';
                    }
                    if (value.trim().length > 100) {
                        return '캘린더 이름은 100자 이하여야 합니다';
                    }
                }
            }).then((result) => {
                if (result.isConfirmed && result.value) {
                    const trimmedName = result.value.trim();
                    const color = calendarColorPool[Math.floor(Math.random() * calendarColorPool.length)];

                    // Dispatch custom event for calendar creation
                    document.dispatchEvent(new CustomEvent('calendar:add', {
                        detail: {
                            name: trimmedName,
                            color: color,
                            visible: true
                        }
                    }));

                    // Show success notification
                    if (window.notyf) {
                        window.notyf.success(`"${trimmedName}" 캘린더가 생성되었습니다.`);
                    }

                    closeModal();
                }
            });
        } else {
            // Fallback to prompt if SweetAlert2 is not available
            const name = prompt('새 캘린더 이름을 입력하세요:');
            if (!name || !name.trim()) {
                return;
            }

            const trimmedName = name.trim();
            const color = calendarColorPool[Math.floor(Math.random() * calendarColorPool.length)];

            document.dispatchEvent(new CustomEvent('calendar:add', {
                detail: {
                    name: trimmedName,
                    color: color,
                    visible: true
                }
            }));

            if (window.notyf) {
                window.notyf.success(`"${trimmedName}" 캘린더가 생성되었습니다.`);
            }

            closeModal();
        }
    }

    // Handle connect Google Calendar
    function handleConnectGoogleCalendar() {
        closeModal();

        document.dispatchEvent(new CustomEvent('calendar:add:connect-google'));
        
        // Open Google Calendar modal
        if (window.Modal && window.Modal.open) {
            window.Modal.open('googleCalendarModal');
        } else if (window.GoogleCalendarModal && window.GoogleCalendarModal.open) {
            window.GoogleCalendarModal.open();
        } else {
            // Fallback: try to find and open Google Calendar modal
            const googleModal = document.getElementById('googleCalendarModal');
            if (googleModal) {
                googleModal.classList.add('active');
                document.body.style.overflow = 'hidden';
            }
        }
    }

    // Open modal
    function openCalendarAddModal() {
        const modal = document.getElementById(modalId);
        if (modal) {
            if (window.Modal && window.Modal.open) {
                window.Modal.open(modalId);
            } else {
                modal.style.display = 'flex';
                modal.classList.add('active');
                document.body.style.overflow = 'hidden';
            }
        }
    }

    // Close modal
    function closeModal() {
        const modal = document.getElementById(modalId);
        if (modal) {
            if (window.Modal && window.Modal.close) {
                window.Modal.close(modalId);
            } else {
                modal.style.display = 'none';
                modal.classList.remove('active');
                document.body.style.overflow = '';
            }
        }
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initCalendarAddModal);
    } else {
        initCalendarAddModal();
    }

    // Export for use in other modules
    if (typeof window !== 'undefined') {
        window.CalendarAddModal = {
            open: openCalendarAddModal,
            close: closeModal,
        };
    }
})();
