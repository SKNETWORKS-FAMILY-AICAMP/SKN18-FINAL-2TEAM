// Calendar Manage Modal Component JavaScript Logic
(function() {
    'use strict';

    // DOM elements
    const modalId = 'calendarManageModal';
    let calendarManageList = null;
    let sortableInstance = null;

    // Initialize modal
    function initCalendarManageModal() {
        const modal = document.getElementById(modalId);
        if (!modal) return;
        
        calendarManageList = document.getElementById('calendarManageList');
        
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

        // Load calendars when modal opens
        modal.addEventListener('modal:open', loadCalendars);
    }

    // Load calendars from API
    async function loadCalendars() {
        if (!calendarManageList) return;

        try {
            const response = await fetch('/api/calendars/', {
                method: 'GET',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'Content-Type': 'application/json',
                },
            });

            let calendars = [];
            if (response.ok) {
                const data = await response.json();
                calendars = Array.isArray(data?.results) ? data.results : (Array.isArray(data) ? data : []);
            }

            renderCalendarList(calendars);
        } catch (error) {
            console.error('Error loading calendars:', error);
            if (window.notyf) {
                window.notyf.error('캘린더 목록을 불러오는데 실패했습니다.');
            }
            renderCalendarList([]);
        }
    }

    // Render calendar list
    function renderCalendarList(calendars) {
        if (!calendarManageList) return;

        if (!Array.isArray(calendars) || calendars.length === 0) {
            calendarManageList.innerHTML = `
                <div class="empty-state">
                    <p>등록된 캘린더가 없습니다</p>
                </div>
            `;
            return;
        }

        calendarManageList.innerHTML = calendars.map((calendar) => {
            const color = normalizeHexColor(calendar.color, '#3b82f6');
            const source = calendar.source_type || calendar.source || 'local';
            const isGoogle = source === 'google';
            
            return `
                <div class="calendar-manage-item" data-calendar-id="${calendar.id}">
                    <div class="calendar-manage-item-info">
                        <i class="fa-solid fa-grip-vertical calendar-manage-drag-handle" title="드래그하여 순서 변경"></i>
                        <div class="calendar-manage-color" style="background-color: ${color};"></div>
                        <span class="calendar-manage-name">${escapeHtml(calendar.name || '')}</span>
                        ${isGoogle ? '<i class="fa-brands fa-google calendar-manage-source-icon" title="Google Calendar"></i>' : ''}
                    </div>
                    ${!isGoogle ? `
                    <button 
                        class="calendar-manage-delete-btn" 
                        data-calendar-id="${calendar.id}"
                        title="캘린더 삭제"
                    >
                        <i class="fa-solid fa-trash"></i>
                    </button>
                    ` : ''}
                </div>
            `;
        }).join('');

        // Attach delete handlers
        attachDeleteHandlers();
        
        // Initialize SortableJS
        initSortable();
    }

    // Attach delete button handlers
    function attachDeleteHandlers() {
        const deleteBtns = calendarManageList?.querySelectorAll('.calendar-manage-delete-btn');
        deleteBtns?.forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const calendarId = btn.getAttribute('data-calendar-id');
                await handleDeleteCalendar(calendarId);
            });
        });
    }

    // Initialize SortableJS
    function initSortable() {
        if (!calendarManageList) return;
        
        // Destroy existing instance if any
        if (sortableInstance) {
            sortableInstance.destroy();
            sortableInstance = null;
        }

        // Check if Sortable is available
        if (typeof Sortable === 'undefined') {
            console.warn('SortableJS is not loaded');
            return;
        }

        // Create new Sortable instance
        sortableInstance = new Sortable(calendarManageList, {
            handle: '.calendar-manage-drag-handle',
            animation: 150,
            ghostClass: 'calendar-manage-item-ghost',
            chosenClass: 'calendar-manage-item-chosen',
            dragClass: 'calendar-manage-item-drag',
            onEnd: async function(evt) {
                // Save new order
                await saveCalendarOrder();
            }
        });
    }

    // Save calendar order
    async function saveCalendarOrder() {
        if (!calendarManageList) return;

        const items = calendarManageList.querySelectorAll('.calendar-manage-item');
        const orderUpdates = [];

        items.forEach((item, index) => {
            const calendarId = item.getAttribute('data-calendar-id');
            if (calendarId) {
                orderUpdates.push({
                    id: parseInt(calendarId),
                    sort_order: index
                });
            }
        });

        if (orderUpdates.length === 0) return;

        try {
            // Update each calendar's sort_order
            const updatePromises = orderUpdates.map(update => 
                fetch(`/api/calendars/${update.id}/`, {
                    method: 'PATCH',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ sort_order: update.sort_order }),
                })
            );

            const results = await Promise.all(updatePromises);
            const allSuccess = results.every(r => r.ok);

            if (allSuccess) {
                // Reload calendars in schedule page
                if (window.SchedulePage && window.SchedulePage.reloadCalendars) {
                    window.SchedulePage.reloadCalendars();
                }

                if (window.notyf) {
                    window.notyf.success('캘린더 순서가 저장되었습니다.');
                }
            } else {
                throw new Error('Some updates failed');
            }
        } catch (error) {
            console.error('Error saving calendar order:', error);
            if (window.notyf) {
                window.notyf.error('캘린더 순서 저장에 실패했습니다.');
            }
            // Reload to restore original order
            await loadCalendars();
        }
    }

    // Handle delete calendar
    async function handleDeleteCalendar(calendarId) {
        if (!calendarId) return;

        // Confirm deletion with warning about schedules
        let confirmed = false;
        if (window.Swal) {
            const result = await window.Swal.fire({
                title: '캘린더 삭제',
                html: '<div style="text-align: center; padding: 0 1rem;">' +
                      '<p style="margin-bottom: 0.5rem;">이 캘린더를 삭제하시겠습니까?</p>' +
                      '<p style="color: #ef4444; font-weight: 600; margin: 0.5rem 0;">' +
                      '캘린더에 속한 모든 일정도 함께 삭제됩니다.</p>' +
                      '</div>',
                icon: 'warning',
                showCancelButton: true,
                confirmButtonText: '삭제',
                cancelButtonText: '취소',
                confirmButtonColor: '#ef4444',
                cancelButtonColor: '#6b7280',
                reverseButtons: true,
            });
            confirmed = result.isConfirmed;
        } else {
            confirmed = confirm('이 캘린더를 삭제하시겠습니까?\n\n캘린더에 속한 모든 일정도 함께 삭제됩니다.');
        }

        if (!confirmed) return;

        try {
            const response = await fetch(`/api/calendars/${calendarId}/`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'Content-Type': 'application/json',
                },
            });

            if (response.ok) {
                const data = await response.json().catch(() => ({}));
                const deletedSchedules = data.deleted_schedules || 0;
                
                // Reload calendars
                await loadCalendars();
                
                // Reload calendars in schedule page
                if (window.SchedulePage && window.SchedulePage.reloadCalendars) {
                    window.SchedulePage.reloadCalendars();
                }
                
                // Refresh calendar to update schedule list
                if (window.SchedulePage && window.SchedulePage.refreshCalendar) {
                    window.SchedulePage.refreshCalendar();
                }

                if (window.notyf) {
                    if (deletedSchedules > 0) {
                        window.notyf.success(`캘린더와 일정 ${deletedSchedules}개가 삭제되었습니다.`);
                    } else {
                        window.notyf.success('캘린더가 삭제되었습니다.');
                    }
                }
            } else {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || 'failed_to_delete_calendar');
            }
        } catch (error) {
            console.error('Error deleting calendar:', error);
            if (window.notyf) {
                window.notyf.error('캘린더 삭제에 실패했습니다.');
            }
        }
    }

    // Open modal
    function openCalendarManageModal() {
        const modal = document.getElementById(modalId);
        if (modal) {
            // Load calendars before opening
            loadCalendars();
            
            if (window.Modal && window.Modal.open) {
                window.Modal.open(modalId);
            } else {
                modal.style.display = 'flex';
                modal.classList.add('active');
                document.body.style.overflow = 'hidden';
                
                // Trigger custom event
                modal.dispatchEvent(new CustomEvent('modal:open'));
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

    // Helper functions
    function getCsrfToken() {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrftoken') return value;
        }
        const metaTag = document.querySelector('meta[name=csrf-token]');
        if (metaTag) return metaTag.getAttribute('content');
        return '';
    }

    function normalizeHexColor(color, fallback = '#3b82f6') {
        if (!color || typeof color !== 'string') return fallback;
        const trimmed = color.trim();
        if (/^#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$/.test(trimmed)) {
            return trimmed;
        }
        return fallback;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initCalendarManageModal);
    } else {
        initCalendarManageModal();
    }

    // Export for use in other modules
    if (typeof window !== 'undefined') {
        window.CalendarManageModal = {
            open: openCalendarManageModal,
            close: closeModal,
            reload: loadCalendars,
        };
    }
})();


