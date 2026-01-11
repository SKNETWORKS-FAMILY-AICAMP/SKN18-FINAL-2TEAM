// Experiment Content Selection Modal Component JavaScript Logic
console.log('[ExperimentContentSelectionModal] ===== Script file loading... =====');

(function() {
    'use strict';

    console.log('[ExperimentContentSelectionModal] IIFE starting...');

    // State variables
    let selectedContents = [];
    let allContents = [];
    let currentExperimentId = null;
    let isInitialized = false;
    let noteOption = 'existing'; // 'existing' | 'new'
    let selectedNoteId = null;
    let newNoteName = '';
    let allNotes = [];
    let selectedTool = null; // Currently selected tool in sidebar
    let tabButtons = null;
    let tabContents = null;

    // DOM elements
    const modalId = 'experimentContentSelectionModal';
    let modal = null;
    let contentList = null;
    let confirmBtn = null;
    let closeBtns = null;
    let existingNoteSelect = null;
    let newNoteNameInput = null;
    let noteOptionRadios = null;
    let existingNoteSection = null;
    let newNoteSection = null;
    let selectAllCheckbox = null;
    let toolSidebar = null;
    let selectedCountEl = null;

    // Get DOM elements
    function getModalElements() {
        modal = document.getElementById(modalId);
        contentList = document.getElementById('contentSelectionList');
        confirmBtn = document.getElementById('confirmContentSelectionBtn');
        closeBtns = modal ? modal.querySelectorAll('[data-action="close"]') : null;
        existingNoteSelect = document.getElementById('existingNoteSelect');
        newNoteNameInput = document.getElementById('newNoteNameInput');
        noteOptionRadios = modal ? modal.querySelectorAll('input[name="noteOption"]') : null;
        existingNoteSection = document.getElementById('existingNoteSection');
        newNoteSection = document.getElementById('newNoteSection');
        selectAllCheckbox = document.getElementById('selectAllContentFiles');
        toolSidebar = document.getElementById('contentToolSidebar');
        selectedCountEl = document.getElementById('selectedContentCount');
        tabButtons = modal ? modal.querySelectorAll('.content-tab-btn') : null;
        tabContents = modal ? modal.querySelectorAll('.content-tab-content') : null;
    }

    // Escape HTML
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Initialize modal
    function initContentSelectionModal() {
        if (isInitialized) return true;

        getModalElements();

        if (!modal) {
            console.warn('[ExperimentContentSelectionModal] Modal element not found');
            return false;
        }

        // Close button handlers
        if (closeBtns) {
            closeBtns.forEach(btn => {
                btn.addEventListener('click', closeContentSelectionModal);
            });
        }

        // Overlay click handler
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeContentSelectionModal();
            }
        });

        // Confirm button handler
        if (confirmBtn) {
            confirmBtn.addEventListener('click', handleConfirm);
        }

        // Note option radio handlers
        if (noteOptionRadios) {
            noteOptionRadios.forEach(radio => {
                radio.addEventListener('change', handleNoteOptionChange);
            });
        }

        // Existing note select handler
        if (existingNoteSelect) {
            existingNoteSelect.addEventListener('change', handleNoteSelectChange);
        }

        // New note name input handler
        if (newNoteNameInput) {
            newNoteNameInput.addEventListener('input', handleNewNoteNameChange);
        }

        // Select all handler
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', handleSelectAll);
        }

        // Tab switching handlers
        if (tabButtons) {
            tabButtons.forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const tabName = e.currentTarget.getAttribute('data-tab');
                    switchTab(tabName);
                });
            });
        }

        isInitialized = true;
        console.log('[ExperimentContentSelectionModal] Initialized successfully');
        return true;
    }

    // Switch between tabs
    function switchTab(tabName) {
        if (!tabButtons || !tabContents) {
            getModalElements();
        }
        
        // Update tab buttons
        if (tabButtons) {
            tabButtons.forEach(btn => {
                if (btn.getAttribute('data-tab') === tabName) {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            });
        }
        
        // Update tab contents
        if (tabContents) {
            tabContents.forEach(content => {
                if (content.id === `${tabName}-tab`) {
                    content.classList.add('active');
                } else {
                    content.classList.remove('active');
                }
            });
        }

        // Load notes if switching to note selection tab
        if (tabName === 'note-selection' && allNotes.length === 0) {
            loadNotes();
        }
    }

    // Handle select all
    function handleSelectAll(e) {
        const isChecked = e.target.checked;
        
        // Get files for current tool
        const currentToolFiles = selectedTool 
            ? allContents.filter(c => c.tool === selectedTool && c.type !== 'tool-group')
            : allContents.filter(c => c.type !== 'tool-group');
        
        if (isChecked) {
            // Add all current tool files to selection
            currentToolFiles.forEach(content => {
                const contentIdStr = String(content.id);
                if (!selectedContents.find(c => String(c.id) === contentIdStr)) {
                    selectedContents.push(content);
                }
            });
        } else {
            // Remove all current tool files from selection
            const currentToolFileIdStrs = currentToolFiles.map(c => String(c.id));
            selectedContents = selectedContents.filter(c => !currentToolFileIdStrs.includes(String(c.id)));
        }
        
        // Update all checkboxes in current view
        if (contentList) {
            contentList.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
                const contentIdStr = checkbox.getAttribute('data-content-id');
                if (currentToolFiles.some(c => String(c.id) === contentIdStr)) {
                    checkbox.checked = isChecked;
                    const item = contentList.querySelector(`[data-content-id="${escapeHtml(contentIdStr)}"]`);
                    if (item) {
                        if (isChecked) {
                            item.classList.add('selected');
                        } else {
                            item.classList.remove('selected');
                        }
                    }
                }
            });
        }
        
        console.log('[ExperimentContentSelectionModal] Select all:', isChecked, 'Total selected:', selectedContents.length);
        updateSelectedCount();
        updateConfirmButton();
    }

    // Update selected count
    function updateSelectedCount() {
        // Ensure element is found
        if (!selectedCountEl) {
            getModalElements();
        }
        
        if (selectedCountEl) {
            selectedCountEl.textContent = selectedContents.length;
            console.log('[ExperimentContentSelectionModal] Updated selected count:', selectedContents.length);
        } else {
            console.warn('[ExperimentContentSelectionModal] selectedCountEl not found');
        }
        
        // Update select all checkbox state
        if (selectAllCheckbox && allContents.length > 0) {
            const currentToolFiles = selectedTool 
                ? allContents.filter(c => c.tool === selectedTool && c.type !== 'tool-group')
                : allContents.filter(c => c.type !== 'tool-group');
            const selectedInCurrentTool = selectedContents.filter(c => 
                currentToolFiles.some(f => String(f.id) === String(c.id))
            ).length;
            
            selectAllCheckbox.checked = currentToolFiles.length > 0 && selectedInCurrentTool === currentToolFiles.length;
            selectAllCheckbox.indeterminate = 
                selectedInCurrentTool > 0 && selectedInCurrentTool < currentToolFiles.length;
        }
    }

    // Handle note option change
    function handleNoteOptionChange(e) {
        noteOption = e.target.value;
        console.log('[ExperimentContentSelectionModal] Note option changed to:', noteOption);
        
        if (noteOption === 'existing') {
            if (existingNoteSection) existingNoteSection.style.display = 'block';
            if (newNoteSection) newNoteSection.style.display = 'none';
            newNoteName = '';
            if (newNoteNameInput) newNoteNameInput.value = '';
        } else {
            if (existingNoteSection) existingNoteSection.style.display = 'none';
            if (newNoteSection) newNoteSection.style.display = 'block';
            selectedNoteId = null;
            if (existingNoteSelect) existingNoteSelect.value = '';
        }
        
        updateConfirmButton();
    }

    // Handle note select change
    function handleNoteSelectChange(e) {
        selectedNoteId = e.target.value;
        console.log('[ExperimentContentSelectionModal] Selected note ID:', selectedNoteId);
        updateConfirmButton();
    }

    // Handle new note name change
    function handleNewNoteNameChange(e) {
        newNoteName = e.target.value.trim();
        console.log('[ExperimentContentSelectionModal] New note name:', newNoteName);
        updateConfirmButton();
    }

    // Load experiment contents (files grouped by tool)
    async function loadExperimentContents(experimentId) {
        if (!experimentId) {
            console.error('[ExperimentContentSelectionModal] No experiment ID provided');
            return [];
        }

        try {
            const response = await fetch(`/api/experiments/${experimentId}/files/`, {
                method: 'GET',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'Content-Type': 'application/json',
                },
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            const files = data.results || data || [];

            // Group files by tool
            const groupedByTool = {};
            files.forEach(file => {
                const fileName = file.name || file.filename || file.result_name || 'Unknown';
                const tool = extractToolFromFileName(fileName);
                
                if (!groupedByTool[tool]) {
                    groupedByTool[tool] = [];
                }
                
                // Only include files with valid ID (to use proxy URL, avoid S3 direct access)
                const fileId = file.id || file.result_sid || file.file_id;
                if (fileId) {
                    groupedByTool[tool].push({
                        id: fileId,
                        name: fileName,
                        type: file.type || file.file_type || file.result_type || 'FILE',
                        tool: tool,
                        date: file.date || file.created_at,
                        url: `/api/experiments/results/${fileId}/file/`,
                    });
                }
            });

            // Convert files to content items (only individual files, no tool-groups)
            // Only include files with valid ID (to use proxy URL, avoid S3 direct access)
            const contents = [];
            files.forEach(file => {
                const fileName = file.name || file.filename || file.result_name || 'Unknown';
                const fileId = file.id || file.result_sid || file.file_id;
                
                // Only add files with valid ID to avoid S3 direct access issues
                if (fileId) {
                    contents.push({
                        id: fileId,
                        type: 'file',
                        name: fileName,
                        fileType: file.type || file.file_type || file.result_type || 'FILE',
                        tool: extractToolFromFileName(fileName),
                        date: file.date || file.created_at,
                        url: `/api/experiments/results/${fileId}/file/`,
                    });
                } else {
                    console.warn('[ExperimentContentSelectionModal] Skipping file without ID:', fileName);
                }
            });

            return contents;
        } catch (error) {
            console.error('[ExperimentContentSelectionModal] Failed to load contents:', error);
            return [];
        }
    }

    // Extract tool name from file name (same logic as experiment.js)
    function extractToolFromFileName(fileName) {
        if (!fileName) {
            return '기타';
        }
        
        const nameLower = fileName.toLowerCase();
        
        // AlphaFold 패턴
        if (nameLower.includes('alphafold') || nameLower.includes('af_') || nameLower.includes('af-') || nameLower.startsWith('af ')) {
            return 'AlphaFold3';
        } 
        // ProteinMPNN 패턴
        else if (nameLower.includes('mpnn') || nameLower.includes('proteinmpnn') || nameLower.includes('protein_mpnn') || nameLower.includes('protein mpnn')) {
            return 'ProteinMPNN';
        } 
        // RFdiffusion 패턴
        else if (nameLower.includes('rfdiffusion') || nameLower.includes('rf_') || nameLower.includes('rf-') || nameLower.startsWith('rf ')) {
            return 'RFdiffusion';
        }
        
        return '기타';
    }

    // Get tool display name (same logic as experiment.js)
    function getToolDisplayName(toolName) {
        const displayNames = {
            'AlphaFold3': 'AlphaFold3',
            'ProteinMPNN': 'ProteinMPNN',
            'RFdiffusion': 'RFdiffusion',
            '기타': '기타'
        };
        return displayNames[toolName] || toolName;
    }

    // Format content date
    function formatContentDate(dateString) {
        if (!dateString) return '';
        try {
            const date = new Date(dateString);
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            const hours = date.getHours();
            const minutes = String(date.getMinutes()).padStart(2, '0');
            const ampm = hours >= 12 ? '오후' : '오전';
            const displayHours = hours % 12 || 12;
            
            return `${year}. ${month}. ${day}. ${ampm} ${displayHours}:${minutes}`;
        } catch (e) {
            return dateString;
        }
    }

    // Group contents by tool
    function groupContentsByTool(contents) {
        const grouped = {};
        contents.forEach(content => {
            const tool = content.tool || '기타';
            if (!grouped[tool]) {
                grouped[tool] = [];
            }
            grouped[tool].push(content);
        });
        return grouped;
    }

    // Render tool sidebar
    function renderToolSidebar() {
        if (!toolSidebar) {
            getModalElements();
        }
        if (!toolSidebar) {
            console.warn('[ExperimentContentSelectionModal] toolSidebar element not found');
            return;
        }
        
        const grouped = groupContentsByTool(allContents.filter(c => c.type !== 'tool-group'));
        const tools = Object.keys(grouped).sort();
        
        if (tools.length === 0) {
            toolSidebar.innerHTML = '';
            return;
        }
        
        // Select first tool if none selected
        if (!selectedTool && tools.length > 0) {
            selectedTool = tools[0];
        }
        
        toolSidebar.innerHTML = tools.map(tool => {
            const count = grouped[tool].length;
            const isActive = selectedTool === tool;
            
            return `
                <button 
                    class="content-tool-item ${isActive ? 'active' : ''}" 
                    data-tool="${escapeHtml(tool)}"
                >
                    <span class="content-tool-name">${escapeHtml(getToolDisplayName(tool))}</span>
                    <span class="content-tool-count">${count}</span>
                </button>
            `;
        }).join('');
        
        // Attach tool selection handlers
        toolSidebar.querySelectorAll('.content-tool-item').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const tool = e.currentTarget.getAttribute('data-tool');
                selectTool(tool);
            });
        });
    }

    // Select a tool and render its files
    function selectTool(tool) {
        selectedTool = tool;
        renderToolSidebar();
        renderContentList(allContents);
        updateSelectedCount();
    }

    // Render content list
    function renderContentList(contents) {
        if (!contentList) {
            getModalElements();
        }
        if (!contentList) {
            console.warn('[ExperimentContentSelectionModal] contentList element not found');
            return;
        }

        if (!contents || contents.length === 0) {
            contentList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-file-alt empty-icon"></i>
                    <p class="empty-text">저장할 컨텐츠가 없습니다</p>
                </div>
            `;
            return;
        }

        // Filter by selected tool (only show files, not tool-groups)
        const filesOnly = contents.filter(c => c.type !== 'tool-group');
        const filteredFiles = selectedTool 
            ? filesOnly.filter(c => (c.tool || '기타') === selectedTool)
            : filesOnly;

        if (filteredFiles.length === 0) {
            contentList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-file-alt empty-icon"></i>
                    <p class="empty-text">선택한 도구에 컨텐츠가 없습니다</p>
                </div>
            `;
            updateSelectedCount();
            return;
        }

        contentList.innerHTML = filteredFiles.map(content => {
            const contentIdStr = String(content.id);
            const isSelected = selectedContents.some(c => String(c.id) === contentIdStr);
            const fileDate = content.date || '';
            const formattedDate = fileDate ? formatContentDate(fileDate) : '';
            
            return `
                <label class="content-item ${isSelected ? 'selected' : ''}" data-content-id="${escapeHtml(contentIdStr)}">
                    <div class="content-item-content">
                        <div class="content-item-header">
                            <input 
                                type="checkbox" 
                                ${isSelected ? 'checked' : ''}
                                data-content-id="${escapeHtml(contentIdStr)}"
                                class="content-checkbox"
                            />
                            <h4 class="content-item-name">${escapeHtml(content.name)}</h4>
                        </div>
                        <div class="content-item-meta">
                            <span class="content-item-tool">${escapeHtml(content.tool || '기타')}</span>
                            <span class="content-item-type">${escapeHtml(content.fileType || 'FILE')}</span>
                            ${formattedDate ? `<span class="content-item-date">${escapeHtml(formattedDate)}</span>` : ''}
                        </div>
                    </div>
                </label>
            `;
        }).join('');

        // Attach checkbox handlers
        contentList.querySelectorAll('.content-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const contentIdStr = e.target.getAttribute('data-content-id');
                // Find content by comparing IDs (handle both string and number types)
                const content = allContents.find(c => String(c.id) === String(contentIdStr));
                if (!content) {
                    console.warn('[ExperimentContentSelectionModal] Content not found for ID:', contentIdStr);
                    return;
                }
                
                const isSelected = e.target.checked;
                handleContentToggle(content.id, isSelected);
            });
        });

        updateConfirmButton();
    }

    // Handle content toggle
    function handleContentToggle(contentId, isSelected) {
        // Normalize ID to string for comparison
        const contentIdStr = String(contentId);
        const content = allContents.find(c => String(c.id) === contentIdStr);
        if (!content) {
            console.warn('[ExperimentContentSelectionModal] Content not found for ID:', contentId);
            return;
        }

        if (isSelected) {
            if (!selectedContents.find(c => String(c.id) === contentIdStr)) {
                selectedContents.push(content);
                console.log('[ExperimentContentSelectionModal] Added content to selection:', contentId, 'Total:', selectedContents.length);
            }
        } else {
            const beforeLength = selectedContents.length;
            selectedContents = selectedContents.filter(c => String(c.id) !== contentIdStr);
            console.log('[ExperimentContentSelectionModal] Removed content from selection:', contentId, 'Before:', beforeLength, 'After:', selectedContents.length);
        }

        // Update UI
        const item = contentList ? contentList.querySelector(`[data-content-id="${escapeHtml(contentIdStr)}"]`) : null;
        if (item) {
            if (isSelected) {
                item.classList.add('selected');
            } else {
                item.classList.remove('selected');
            }
        }

        console.log('[ExperimentContentSelectionModal] Selected contents count:', selectedContents.length);
        updateSelectedCount();
        updateConfirmButton();
    }

    // Update confirm button state
    function updateConfirmButton() {
        if (!confirmBtn) {
            getModalElements();
        }
        if (!confirmBtn) return;

        const hasSelectedContent = selectedContents.length > 0;
        let hasValidNote = false;

        if (noteOption === 'existing') {
            hasValidNote = selectedNoteId && selectedNoteId !== '';
        } else {
            hasValidNote = newNoteName.length > 0;
        }

        confirmBtn.disabled = !hasSelectedContent || !hasValidNote;
    }

    // Format selected content to HTML for note
    function formatContentForNote(contents) {
        if (!contents || contents.length === 0) return '';

        const timestamp = new Date().toLocaleString('ko-KR', { 
            year: 'numeric', 
            month: '2-digit', 
            day: '2-digit', 
            hour: '2-digit', 
            minute: '2-digit' 
        });

        let html = `<p><strong>[실험 결과 저장 - ${timestamp}]</strong></p>`;
        html += '<div style="margin: 15px 0;">';

        contents.forEach(content => {
            if (content.type === 'tool-group') {
                html += `<h3 style="margin: 15px 0 10px 0; color: #2563eb;">${escapeHtml(content.displayName)} (${content.fileCount}개 파일)</h3>`;
                if (content.files && content.files.length > 0) {
                    html += '<ul style="margin: 10px 0; padding-left: 20px;">';
                    content.files.forEach(file => {
                        html += `<li style="margin: 5px 0;">${escapeHtml(file.name)} <span style="color: #6b7280; font-size: 0.875rem;">(${escapeHtml(file.type)})</span></li>`;
                    });
                    html += '</ul>';
                }
            } else {
                html += `<div style="margin: 10px 0; padding: 10px; background: #f9fafb; border-radius: 0.5rem;">`;
                html += `<p style="margin: 0 0 5px 0;"><strong>${escapeHtml(content.name)}</strong></p>`;
                html += `<p style="margin: 0; font-size: 0.875rem; color: #6b7280;">타입: ${escapeHtml(content.fileType)}</p>`;
                if (content.url) {
                    // Ensure we use proxy URL (never use S3 direct URL)
                    const fileId = content.id;
                    const proxyUrl = fileId ? `/api/experiments/results/${fileId}/file/` : content.url;
                    console.log('[ExperimentContentSelectionModal] Formatting content for note:', {
                        name: content.name,
                        id: fileId,
                        originalUrl: content.url,
                        proxyUrl: proxyUrl
                    });
                    // 파일명을 링크 텍스트로 사용
                    html += `<p style="margin: 5px 0 0 0;"><a href="${escapeHtml(proxyUrl)}" target="_blank" rel="noopener noreferrer" style="color: #2563eb; text-decoration: underline;">${escapeHtml(content.name)}</a></p>`;
                }
                html += `</div>`;
            }
        });

        html += '</div>';
        return html;
    }

    // Load notes from API
    async function loadNotes() {
        try {
            // Build API URL with query parameters (same as save_to_note_modal.js)
            const params = new URLSearchParams();
            params.append('my_notes_only', 'true'); // 내 노트만 조회
            
            const apiUrl = `/api/notes/?${params.toString()}`;
            
            const response = await fetch(apiUrl, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin',
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            
            console.log('[ExperimentContentSelectionModal] API 응답 데이터:', data);
            
            // Check for data.results (same format as save_to_note_modal.js)
            if (data.status === 'success' && Array.isArray(data.results)) {
                // Transform API response to match expected format
                allNotes = data.results.map(note => ({
                    id: note.id,
                    title: note.title,
                    date: note.date,
                    tags: note.tags || [],
                }));
            } else if (data.status === 'success' && data.notes) {
                // Fallback to data.notes if data.results doesn't exist
                allNotes = data.notes;
            } else if (Array.isArray(data)) {
                allNotes = data;
            } else {
                allNotes = [];
            }

            console.log('[ExperimentContentSelectionModal] 변환된 노트 목록:', allNotes);
            console.log('[ExperimentContentSelectionModal] 노트 개수:', allNotes.length);

            // Populate select dropdown
            if (existingNoteSelect) {
                existingNoteSelect.innerHTML = '<option value="">노트를 선택하세요</option>';
                allNotes.forEach(note => {
                    const option = document.createElement('option');
                    option.value = note.id || note.note_id;
                    option.textContent = note.title || note.name;
                    existingNoteSelect.appendChild(option);
                });
            }

            console.log('[ExperimentContentSelectionModal] Loaded notes:', allNotes.length);
        } catch (error) {
            console.error('[ExperimentContentSelectionModal] Failed to load notes:', error);
            allNotes = [];
            // Show error in dropdown
            if (existingNoteSelect) {
                existingNoteSelect.innerHTML = '<option value="">노트를 불러올 수 없습니다</option>';
            }
        }
    }

    // Handle confirm
    async function handleConfirm() {
        // Check which tab is active
        const activeTab = tabContents ? Array.from(tabContents).find(tab => tab.classList.contains('active')) : null;
        const isContentTab = activeTab && activeTab.id === 'content-files-tab';
        const isNoteTab = activeTab && activeTab.id === 'note-selection-tab';

        // If on content tab, switch to note tab
        if (isContentTab) {
            if (selectedContents.length === 0) {
                if (window.notyf) {
                    window.notyf.warning('저장할 컨텐츠를 선택해주세요.');
                }
                return;
            }
            // Switch to note selection tab
            switchTab('note-selection');
            return;
        }

        // If on note tab, proceed with save
        if (isNoteTab) {
            if (selectedContents.length === 0) {
                if (window.notyf) {
                    window.notyf.warning('저장할 컨텐츠를 선택해주세요.');
                }
                return;
            }

            // Validate note selection
            if (noteOption === 'existing' && (!selectedNoteId || selectedNoteId === '')) {
                if (window.notyf) {
                    window.notyf.warning('노트를 선택해주세요.');
                }
                return;
            }

            if (noteOption === 'new' && !newNoteName.trim()) {
                if (window.notyf) {
                    window.notyf.warning('새 노트의 제목을 입력해주세요.');
                }
                return;
            }
        } else {
            // Default: check both
            if (selectedContents.length === 0) {
                if (window.notyf) {
                    window.notyf.warning('저장할 컨텐츠를 선택해주세요.');
                }
                return;
            }

            // Validate note selection
            if (noteOption === 'existing' && (!selectedNoteId || selectedNoteId === '')) {
                if (window.notyf) {
                    window.notyf.warning('노트를 선택해주세요.');
                }
                return;
            }

            if (noteOption === 'new' && !newNoteName.trim()) {
                if (window.notyf) {
                    window.notyf.warning('새 노트의 제목을 입력해주세요.');
                }
                return;
            }
        }

        // Format content for note
        const contentHtml = formatContentForNote(selectedContents);

        // Disable confirm button during save
        if (confirmBtn) {
            confirmBtn.disabled = true;
            confirmBtn.textContent = '저장 중...';
        }

        try {
            if (noteOption === 'existing') {
                // Save to existing note
                const selectedNote = allNotes.find(n => (n.id || n.note_id) == selectedNoteId);
                if (!selectedNote) {
                    throw new Error('선택한 노트를 찾을 수 없습니다.');
                }

                // Get existing note content
                const getResponse = await fetch(`/api/notes/${selectedNoteId}/`, {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    credentials: 'same-origin',
                });

                if (!getResponse.ok) {
                    throw new Error('노트 정보를 불러올 수 없습니다.');
                }

                const getData = await getResponse.json();
                if (getData.status !== 'success' || !getData.note) {
                    throw new Error('노트 정보를 불러올 수 없습니다.');
                }

                const noteData = getData.note;
                const existingContent = noteData.content || '';

                const separator = '<hr style="margin: 20px 0; border: none; border-top: 1px solid #e0e0e0;"/>';
                const newContent = existingContent 
                    ? existingContent + separator + contentHtml
                    : contentHtml;

                const formData = new FormData();
                formData.append('title', noteData.title || '');
                formData.append('content', newContent);
                formData.append('tags', JSON.stringify(noteData.tags || []));

                const updateResponse = await fetch(`/api/notes/${selectedNoteId}/update/`, {
                    method: 'PUT',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                    },
                    credentials: 'same-origin',
                    body: formData,
                });

                if (!updateResponse.ok) {
                    const errorData = await updateResponse.json().catch(() => ({ error: '알 수 없는 오류가 발생했습니다.' }));
                    throw new Error(errorData.error || `HTTP error! status: ${updateResponse.status}`);
                }

                const data = await updateResponse.json();

                if (data.status === 'success') {
                    if (window.notyf) {
                        window.notyf.success(`"${selectedNote.title}" 노트에 저장했습니다.`);
                    }
                    closeContentSelectionModal();
                } else {
                    throw new Error(data.error || '저장에 실패했습니다.');
                }

            } else {
                // Create new note
                const formData = new FormData();
                formData.append('title', newNoteName.trim());
                formData.append('content', contentHtml);
                formData.append('tags', JSON.stringify([]));

                const createResponse = await fetch('/api/notes/create/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                    },
                    credentials: 'same-origin',
                    body: formData,
                });

                if (!createResponse.ok) {
                    const errorData = await createResponse.json().catch(() => ({ error: '알 수 없는 오류가 발생했습니다.' }));
                    throw new Error(errorData.error || `HTTP error! status: ${createResponse.status}`);
                }

                const data = await createResponse.json();

                if (data.status === 'success') {
                    if (window.notyf) {
                        window.notyf.success(`"${newNoteName.trim()}" 노트를 생성했습니다.`);
                    }
                    closeContentSelectionModal();
                } else {
                    throw new Error(data.error || '저장에 실패했습니다.');
                }
            }
        } catch (error) {
            console.error('[ExperimentContentSelectionModal] Failed to save:', error);
            if (window.notyf) {
                window.notyf.error(error.message || '저장 중 오류가 발생했습니다.');
            }
            if (confirmBtn) {
                confirmBtn.disabled = false;
                confirmBtn.textContent = '확인';
                updateConfirmButton();
            }
        }
    }

    // Open modal
    async function openContentSelectionModal(experimentId) {
        console.log('[ExperimentContentSelectionModal] openContentSelectionModal called with experimentId:', experimentId);
        
        if (!initContentSelectionModal()) {
            console.error('[ExperimentContentSelectionModal] Failed to initialize');
            return;
        }

        // Ensure modal element is available
        if (!modal) {
            getModalElements();
        }
        
        if (!modal) {
            console.error('[ExperimentContentSelectionModal] Modal element not found');
            if (window.notyf) {
                window.notyf.error('모달을 찾을 수 없습니다. 페이지를 새로고침해주세요.');
            }
            return;
        }

        currentExperimentId = experimentId;
        selectedContents = [];

        // Show loading state
        if (contentList) {
            contentList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-spinner fa-spin empty-icon"></i>
                    <p class="empty-text">컨텐츠를 불러오는 중...</p>
                </div>
            `;
        }

        // Load contents
        allContents = await loadExperimentContents(experimentId);
        
        // Render tool sidebar first (with error handling)
        try {
            if (typeof renderToolSidebar === 'function') {
                renderToolSidebar();
            } else {
                console.error('[ExperimentContentSelectionModal] renderToolSidebar is not a function');
                // Fallback: render content list without sidebar
                renderContentList(allContents);
            }
        } catch (error) {
            console.error('[ExperimentContentSelectionModal] Error rendering tool sidebar:', error);
            // Continue with content list rendering even if sidebar fails
        }
        
        // Then render content list (filtered by selected tool)
        try {
            renderContentList(allContents);
        } catch (error) {
            console.error('[ExperimentContentSelectionModal] Error rendering content list:', error);
        }

        // Load notes (with error handling)
        try {
            await loadNotes();
        } catch (error) {
            console.error('[ExperimentContentSelectionModal] Error loading notes:', error);
            // Continue even if notes fail to load
        }

        // Reset state
        selectedContents = [];
        noteOption = 'existing';
        selectedNoteId = null;
        newNoteName = '';
        selectedTool = null;
        if (existingNoteSelect) existingNoteSelect.value = '';
        if (newNoteNameInput) newNoteNameInput.value = '';
        if (existingNoteSection) existingNoteSection.style.display = 'block';
        if (newNoteSection) newNoteSection.style.display = 'none';
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = false;
            selectAllCheckbox.indeterminate = false;
        }
        if (noteOptionRadios) {
            noteOptionRadios.forEach(radio => {
                if (radio.value === 'existing') radio.checked = true;
                else radio.checked = false;
            });
        }
        
        // Switch to content tab
        switchTab('content-files');

        updateSelectedCount();
        updateConfirmButton();

        // Show modal (always show even if there were errors)
        try {
            if (modal) {
                // Remove inline display style and explicitly set display
                modal.style.display = 'flex';
                modal.classList.add('active');
                document.body.style.overflow = 'hidden';
                console.log('[ExperimentContentSelectionModal] Modal opened, display set to flex, active class added');
            } else {
                console.error('[ExperimentContentSelectionModal] Modal element not found when trying to open');
                getModalElements();
                if (modal) {
                    modal.style.display = 'flex';
                    modal.classList.add('active');
                    document.body.style.overflow = 'hidden';
                    console.log('[ExperimentContentSelectionModal] Modal found after re-fetch, opened');
                } else {
                    console.error('[ExperimentContentSelectionModal] Modal still not found after re-fetch');
                    if (window.notyf) {
                        window.notyf.error('모달을 찾을 수 없습니다. 페이지를 새로고침해주세요.');
                    }
                }
            }
        } catch (error) {
            console.error('[ExperimentContentSelectionModal] Error showing modal:', error);
            // Try to show modal anyway
            if (modal) {
                modal.style.display = 'flex';
                modal.classList.add('active');
            }
        }
    }

    // Close modal
    function closeContentSelectionModal() {
        if (modal) {
            modal.classList.remove('active');
            // Set display to none after animation
            setTimeout(() => {
                if (modal && !modal.classList.contains('active')) {
                    modal.style.display = 'none';
                }
            }, 200);
            document.body.style.overflow = '';
        }

        // Reset state
        selectedContents = [];
        allContents = [];
        currentExperimentId = null;
        noteOption = 'existing';
        selectedNoteId = null;
        newNoteName = '';
        selectedTool = null;
        if (confirmBtn) {
            confirmBtn.disabled = true;
            confirmBtn.textContent = '확인';
        }
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = false;
            selectAllCheckbox.indeterminate = false;
        }
        if (selectedCountEl) {
            selectedCountEl.textContent = '0';
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

    // Export to window
    window.ExperimentContentSelectionModal = {
        open: openContentSelectionModal,
        close: closeContentSelectionModal,
        init: initContentSelectionModal,
    };

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            initContentSelectionModal();
        });
    } else {
        initContentSelectionModal();
    }

    console.log('[ExperimentContentSelectionModal] Script loaded, window.ExperimentContentSelectionModal available');
})();
