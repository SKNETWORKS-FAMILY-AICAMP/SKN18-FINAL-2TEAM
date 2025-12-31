// Note Editor Page JavaScript

// State variables
let editingNoteId = null;
let isEditMode = false;
let noteTitle = "";
let noteContent = "";
let noteTags = "";
let isBookmarkSidebarOpen = true;
let openBookmarkCategories = {};
let attachedFiles = [];
let fileIdCounter = 1;
let attachedCharts = [];
let chartIdCounter = 1;
let isBookmarkEditMode = false;
let isAddingBookmarkCategory = false;
let addingBookmarkToCategoryId = null;
let newCategoryName = '';
let newBookmarkTitle = '';
let newBookmarkUrl = '';

// CKEditor5 instance
let editorInstance = null;

// Tagify instance
let tagifyInstance = null;

// DOM Elements
let noteEditorView, noteEditorWrapper;
let editorTitle, btnCancelNote, btnSaveNote;
let btnShareNote, btnBookmarkToggle;
let noteTitleInput, noteTagsInput;
let btnFileAttach, btnGraphAttach, attachedFilesList;
let bookmarkSidebar, bookmarkContent;
let bookmarkApiUrl = "/api/bookmarks/";
let bookmarkCategories = [];
let bookmarksLoading = false;
let bookmarksError = null;
let btnBookmarkEditToggle, btnBookmarkAddCategory;
let bookmarkAddCategoryForm, bookmarkNewCategoryName;
let btnBookmarkSaveCategory, btnBookmarkCancelCategory;

// Initialize
function initNoteEditor() {
    // Get DOM elements
    noteEditorView = document.getElementById('noteEditorView');
    editorTitle = document.getElementById('editorTitle');
    btnCancelNote = document.getElementById('btnCancelNote');
    btnSaveNote = document.getElementById('btnSaveNote');
    btnShareNote = document.getElementById('btnShareNote');
    btnBookmarkToggle = document.getElementById('btnBookmarkToggle');
    noteTitleInput = document.getElementById('noteTitleInput');
    noteTagsInput = document.getElementById('noteTagsInput');
    btnFileAttach = document.getElementById('btnFileAttach');
    btnGraphAttach = document.getElementById('btnGraphAttach');
    attachedFilesList = document.getElementById('attachedFilesList');
    bookmarkSidebar = document.getElementById('bookmarkSidebar');
    bookmarkContent = document.getElementById('bookmarkContent');
    btnBookmarkEditToggle = document.getElementById('btnBookmarkEditToggle');
    btnBookmarkAddCategory = document.getElementById('btnBookmarkAddCategory');
    bookmarkAddCategoryForm = document.getElementById('bookmarkAddCategoryForm');
    bookmarkNewCategoryName = document.getElementById('bookmarkNewCategoryName');
    btnBookmarkSaveCategory = document.getElementById('btnBookmarkSaveCategory');
    btnBookmarkCancelCategory = document.getElementById('btnBookmarkCancelCategory');
    if (bookmarkSidebar && bookmarkSidebar.dataset.bookmarkApiUrl) {
        bookmarkApiUrl = bookmarkSidebar.dataset.bookmarkApiUrl;
    }
    applyBookmarkSidebarState();

    // Attach event listeners
    if (btnCancelNote) btnCancelNote.addEventListener('click', handleCancelNote);
    if (btnSaveNote) btnSaveNote.addEventListener('click', handleSaveNote);
    if (btnShareNote) btnShareNote.addEventListener('click', handleShareNote);
    if (btnBookmarkToggle) btnBookmarkToggle.addEventListener('click', handleToggleBookmark);
    if (btnFileAttach) btnFileAttach.addEventListener('click', handleFileAttach);
    if (btnGraphAttach) btnGraphAttach.addEventListener('click', handleGraphAttach);
    if (btnBookmarkEditToggle) btnBookmarkEditToggle.addEventListener('click', handleToggleBookmarkEditMode);
    if (btnBookmarkAddCategory) btnBookmarkAddCategory.addEventListener('click', handleShowAddCategoryForm);
    if (btnBookmarkSaveCategory) btnBookmarkSaveCategory.addEventListener('click', handleAddCategory);
    if (btnBookmarkCancelCategory) btnBookmarkCancelCategory.addEventListener('click', handleCancelAddCategory);
    if (bookmarkNewCategoryName) {
        bookmarkNewCategoryName.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                handleAddCategory();
            }
        });
    }

    // Check if editing existing note (에디터 초기화 전에 설정)
    const urlParams = new URLSearchParams(window.location.search);
    editingNoteId = urlParams.get('id');
    
    if (editingNoteId) {
        isEditMode = true;
        if (editorTitle) editorTitle.textContent = '노트 수정';
    }

    // Initialize Tagify
    initTagify();

    // Initialize CKEditor5
    initCKEditor();

    // Render bookmarks
    renderBookmarks();
    renderAttachedFiles();
    loadBookmarks();
}

// Initialize Tagify for tags input
function initTagify() {
    if (!noteTagsInput || !window.Tagify) {
        console.warn('[NoteEditor] Tagify not available or noteTagsInput not found');
        return;
    }

    // 기존 인스턴스가 있으면 파괴 (중복 초기화 방지)
    if (tagifyInstance) {
        tagifyInstance.destroy();
        tagifyInstance = null;
    }

    tagifyInstance = new window.Tagify(noteTagsInput, {
        maxTags: 5,
        placeholder: '태그 추가 (최대 5개)',
        delimiters: ',| ',  // 쉼표 또는 스페이스로 구분
        trim: true,
        dropdown: {
            enabled: 0,  // 자동완성 비활성화 (추후 활성화 가능)
            maxItems: 10,
            closeOnSelect: true,
            highlightFirst: true
        },
        callbacks: {
            add: (e) => {
                console.log('[NoteEditor] Tag added:', e.detail.data.value);
            },
            remove: (e) => {
                console.log('[NoteEditor] Tag removed:', e.detail.data.value);
            },
            invalid: (e) => {
                if (window.notyf) {
                    window.notyf.error('태그는 최대 5개까지 추가할 수 있습니다.');
                }
            }
        }
    });

    console.log('[NoteEditor] Tagify initialized successfully');
}

// Initialize CKEditor5 using bundled version from window.CKEditor
function initCKEditor() {
    const editorElement = document.getElementById('noteContentEditor');
    if (!editorElement) {
        console.error('[NoteEditor] CKEditor element #noteContentEditor not found');
        return;
    }

    // Check if CKEditor is available from bundle (window.CKEditor)
    if (!window.CKEditor) {
        console.error('[NoteEditor] window.CKEditor not available');
        editorElement.innerHTML = '<p style="color: #ef4444; padding: 1rem;">에디터를 로드할 수 없습니다. 페이지를 새로고침해주세요.</p>';
        return;
    }

    console.log('[NoteEditor] Initializing CKEditor5 with bundled version...');
    console.log('[NoteEditor] Available CKEditor exports:', Object.keys(window.CKEditor));

    // CKEditor5 모듈에서 필요한 클래스 가져오기
    const {
        ClassicEditor,
        Essentials,
        Bold,
        Italic,
        Underline,
        Strikethrough,
        Paragraph,
        Heading,
        Link,
        List,
        BlockQuote,
        Table,
        TableToolbar,
        Alignment,
        Indent,
        Image,
        ImageToolbar,
        ImageCaption,
        ImageStyle,
        ImageUpload,
        Base64UploadAdapter,
        CodeBlock,
        HorizontalLine,
        Highlight,
        Font,
        MediaEmbed
    } = window.CKEditor;

    // ClassicEditor가 있는지 확인
    if (!ClassicEditor) {
        console.error('[NoteEditor] ClassicEditor not found in window.CKEditor');
        editorElement.innerHTML = '<p style="color: #ef4444; padding: 1rem;">에디터 클래스를 찾을 수 없습니다.</p>';
        return;
    }

    // 사용 가능한 플러그인만 필터링
    const availablePlugins = [
        Essentials,
        Bold,
        Italic,
        Underline,
        Strikethrough,
        Paragraph,
        Heading,
        Link,
        List,
        BlockQuote,
        Table,
        TableToolbar,
        Alignment,
        Indent,
        Image,
        ImageToolbar,
        ImageCaption,
        ImageStyle,
        ImageUpload,
        Base64UploadAdapter,
        CodeBlock,
        HorizontalLine,
        Highlight,
        Font,
        MediaEmbed
    ].filter(plugin => plugin !== undefined);

    console.log('[NoteEditor] Using plugins:', availablePlugins.length);

    ClassicEditor.create(editorElement, {
        licenseKey: 'GPL', // GPL 오픈소스 라이선스 사용
        plugins: availablePlugins,
        toolbar: {
            items: [
                'heading',
                '|',
                'bold',
                'italic',
                'underline',
                'strikethrough',
                '|',
                'fontSize',
                'fontColor',
                '|',
                'alignment',
                '|',
                'bulletedList',
                'numberedList',
                'outdent',
                'indent',
                '|',
                'blockQuote',
                'insertTable',
                'codeBlock',
                'horizontalLine',
                '|',
                'link',
                'uploadImage',
                'mediaEmbed',
                '|',
                'highlight',
                '|',
                'undo',
                'redo'
            ],
            shouldNotGroupWhenFull: true
        },
        heading: {
            options: [
                { model: 'paragraph', title: '본문', class: 'ck-heading_paragraph' },
                { model: 'heading1', view: 'h1', title: '제목 1', class: 'ck-heading_heading1' },
                { model: 'heading2', view: 'h2', title: '제목 2', class: 'ck-heading_heading2' },
                { model: 'heading3', view: 'h3', title: '제목 3', class: 'ck-heading_heading3' }
            ]
        },
        table: {
            contentToolbar: ['tableColumn', 'tableRow', 'mergeTableCells']
        },
        image: {
            toolbar: [
                'imageTextAlternative',
                'toggleImageCaption',
                'imageStyle:inline',
                'imageStyle:block',
                'imageStyle:side'
            ]
        },
        placeholder: '연구 내용을 작성하세요. 실험 방법, 결과, 분석 내용 등을 자유롭게 기록할 수 있습니다.',
        language: 'ko'
    })
    .then(editor => {
        editorInstance = editor;
        console.log('[NoteEditor] CKEditor5 initialized successfully');
        
        // 편집 모드인 경우 데이터 로드
        if (editingNoteId) {
            loadNoteForEdit(editingNoteId);
        }
    })
    .catch(error => {
        console.error('[NoteEditor] CKEditor5 initialization failed:', error);
        editorElement.innerHTML = `<p style="color: #ef4444; padding: 1rem;">에디터 초기화 실패: ${error.message}</p>`;
    });
}

// Load note for editing
function loadNoteForEdit(noteId) {
    // TODO: API 호출로 노트 데이터 가져오기
    // 현재는 mock 데이터 사용
    const mockNote = {
        id: noteId,
        title: 'CRISPR-Cas9 유전자 가위 기술',
        content: '<h2>유전자 편집 실험 결과</h2><p>CRISPR-Cas9 시스템을 이용한 유전자 편집 실험을 진행하였습니다.</p><h3>실험 방법</h3><ul><li>가이드 RNA 설계</li><li>Cas9 단백질 발현</li><li>표적 유전자 편집</li></ul><h3>결과</h3><p>목표 유전자에서 <strong>95%의 편집 효율</strong>을 달성하였습니다.</p>',
        tags: ['CRISPR', '유전자편집']
    };

    if (noteTitleInput) noteTitleInput.value = mockNote.title;
    
    // Tagify에 태그 설정
    if (tagifyInstance) {
        tagifyInstance.removeAllTags();
        tagifyInstance.addTags(mockNote.tags);
    } else if (noteTagsInput) {
        noteTagsInput.value = mockNote.tags.join(', ');
    }
    
    // CKEditor에 컨텐츠 설정
    if (editorInstance) {
        editorInstance.setData(mockNote.content);
    }
}

// Handle cancel note
function handleCancelNote() {
    const editorContent = editorInstance ? editorInstance.getData().trim() : '';
    const hasTags = tagifyInstance ? tagifyInstance.value.length > 0 : (noteTagsInput && noteTagsInput.value.trim());
    const hasContent = (noteTitleInput && noteTitleInput.value.trim()) ||
                       editorContent ||
                       hasTags ||
                       attachedFiles.length > 0;

    if (hasContent) {
        // Use SweetAlert2 for confirmation
        if (window.Swal) {
            window.Swal.fire({
                title: '취소하시겠습니까?',
                text: '작성 중인 내용이 저장되지 않습니다. 정말 취소하시겠습니까?',
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#dc2626',
                cancelButtonColor: '#6b7280',
                confirmButtonText: '취소하기',
                cancelButtonText: '계속 작성',
                reverseButtons: true
            }).then((result) => {
                if (result.isConfirmed) {
                    window.location.href = '/notes/';
                }
            });
        } else {
            // Fallback to confirm if SweetAlert2 is not available
            if (confirm('작성 중인 내용이 저장되지 않습니다. 정말 취소하시겠습니까?')) {
                window.location.href = '/notes/';
            }
        }
    } else {
        // No content, just navigate
        window.location.href = '/notes/';
    }
}

// Handle save note
function handleSaveNote() {
    const title = noteTitleInput?.value.trim() || "";
    const content = editorInstance ? editorInstance.getData().trim() : "";
    
    // Tagify에서 태그 값 가져오기
    let tags = [];
    if (tagifyInstance) {
        tags = tagifyInstance.value.map(tag => tag.value);
    } else {
        const tagsStr = noteTagsInput?.value.trim() || "";
        tags = tagsStr.split(',').map(t => t.trim()).filter(t => t.length > 0).slice(0, 5);
    }

    if (!title) {
        if (window.notyf) {
            window.notyf.error('제목을 입력해주세요.');
        } else {
            alert('제목을 입력해주세요.');
        }
        if (noteTitleInput) noteTitleInput.focus();
        return;
    }

    // TODO: API 호출로 저장
    const noteData = {
        id: editingNoteId || null,
        title: title,
        content: content,
        tags: tags,
        attachedFiles: attachedFiles,
        charts: attachedCharts,
    };
    
    console.log('Saving note:', noteData);

    if (window.notyf) {
        window.notyf.success(isEditMode ? '노트가 수정되었습니다.' : '노트가 저장되었습니다.');
    }

    // Redirect to notes list
    setTimeout(() => {
        window.location.href = '/notes/';
    }, 1000);
}

// Handle share note
function handleShareNote() {
    if (window.ShareModal && typeof window.ShareModal.open === 'function') {
        window.ShareModal.onShare = (selectedMembers) => {
            if (window.notyf) {
                window.notyf.success(`${selectedMembers.length}명과 공유되었습니다.`);
            }
        };
        window.ShareModal.open(editingNoteId);
    } else {
        if (window.notyf) {
            window.notyf.info('공유 기능은 곧 제공될 예정입니다.');
        }
    }
}

// Handle toggle bookmark sidebar
function handleToggleBookmark() {
    isBookmarkSidebarOpen = !isBookmarkSidebarOpen;
    applyBookmarkSidebarState();
}

function applyBookmarkSidebarState() {
    if (bookmarkSidebar) {
        if (isBookmarkSidebarOpen) {
            bookmarkSidebar.classList.remove('hidden');
        } else {
            bookmarkSidebar.classList.add('hidden');
        }
    }
    
    if (btnBookmarkToggle) {
        if (isBookmarkSidebarOpen) {
            btnBookmarkToggle.classList.add('active');
        } else {
            btnBookmarkToggle.classList.remove('active');
        }
    }
}

// Handle file attach
function handleFileAttach() {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.multiple = true;
    fileInput.addEventListener('change', (e) => {
        const files = Array.from(e.target.files);
        files.forEach(file => {
            const newFile = {
                id: fileIdCounter++,
                name: file.name,
                size: formatFileSize(file.size)
            };
            attachedFiles.push(newFile);
        });
        renderAttachedFiles();
    });
    fileInput.click();
}

// Handle graph attach - opens graph creation modal
function handleGraphAttach() {
    if (window.GraphCreateModal && typeof window.GraphCreateModal.open === 'function') {
        window.GraphCreateModal.open((chartData) => {
            // Insert chart into CKEditor
            insertChartToEditor(chartData);
        });
    } else {
        if (window.notyf) {
            window.notyf.error('그래프 생성 모달을 로드할 수 없습니다.');
        }
        console.error('[NoteEditor] GraphCreateModal not available');
    }
}

// Insert chart to CKEditor
function insertChartToEditor(chartData) {
    if (!editorInstance) {
        if (window.notyf) {
            window.notyf.error('에디터가 초기화되지 않았습니다.');
        }
        return;
    }

    const chartEntry = {
        id: chartIdCounter++,
        ...chartData,
    };
    attachedCharts.push(chartEntry);

    const chartDataJson = escapeHtml(JSON.stringify(chartEntry));

    // Create HTML for the chart
    const chartHtml = `
        <figure class="chart-figure" data-chart-id="${chartEntry.id}" data-chart='${chartDataJson}'>
            <img src="${chartEntry.imageDataUrl}" alt="${escapeHtml(chartEntry.title)}" style="max-width: 100%; height: auto;" />
            <figcaption>${escapeHtml(chartEntry.title)}</figcaption>
        </figure>
    `;

    // Get current content and append chart
    const currentContent = editorInstance.getData();
    editorInstance.setData(currentContent + chartHtml);
    
    // Focus editor
    editorInstance.focus();
}

// Handle file remove
function handleFileRemove(fileId) {
    attachedFiles = attachedFiles.filter(file => file.id !== fileId);
    renderAttachedFiles();
}

// Render attached files
function renderAttachedFiles() {
    const attachedCount = document.getElementById('attachedCount');
    
    // Update attached count display
    if (attachedCount) {
        if (attachedFiles.length > 0) {
            attachedCount.textContent = `${attachedFiles.length}개 첨부됨`;
        } else {
            attachedCount.textContent = '';
        }
    }

    if (!attachedFilesList) return;

    if (attachedFiles.length === 0) {
        attachedFilesList.innerHTML = '';
        return;
    }

    attachedFilesList.innerHTML = attachedFiles.map(file => `
        <div class="attached-file-item">
            <i class="fa-solid fa-file-alt"></i>
            <div class="attached-file-info">
                <span class="attached-file-name">${escapeHtml(file.name)}</span>
                <span class="attached-file-size">${file.size}</span>
            </div>
            <button class="btn-file-remove" onclick="window.NoteEditorPage.handleFileRemove(${file.id})">
                <i class="fa-solid fa-times"></i>
            </button>
        </div>
    `).join('');
}

// Format file size
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + 'B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB';
    return (bytes / (1024 * 1024)).toFixed(1) + 'MB';
}

// CKEditor5 handles toolbar internally - no custom toolbar needed

// Load bookmarks from API (t_bookmark)
async function loadBookmarks() {
    if (!bookmarkContent) return;

    bookmarksLoading = true;
    bookmarksError = null;
    renderBookmarks();

    try {
        const response = await fetch(bookmarkApiUrl, {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
            },
            credentials: 'same-origin',
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        const results = Array.isArray(data.results) ? data.results : [];

        bookmarkCategories = results.map((category) => ({
            id: category.category_sid,
            name: category.category_name,
            bookmarks: Array.isArray(category.bookmarks)
                ? category.bookmarks.map((bookmark) => ({
                    id: bookmark.bookmark_sid,
                    title: bookmark.title,
                    url: bookmark.url,
                    description: bookmark.description || '',
                }))
                : [],
        }));
        
        // Reset adding state when bookmarks are reloaded
        addingBookmarkToCategoryId = null;

        openBookmarkCategories = {};
    } catch (error) {
        console.error('[NoteEditor] Failed to load bookmarks:', error);
        bookmarksError = '북마크를 불러오지 못했습니다.';
        if (error && error.message) {
            bookmarksError += ` (${error.message})`;
        }
    } finally {
        bookmarksLoading = false;
        renderBookmarks();
    }
}

// Render bookmarks
function renderBookmarks() {
    if (!bookmarkContent) return;

    if (bookmarksLoading) {
        bookmarkContent.innerHTML = `
            <div class="bookmark-placeholder">
                <i class="fas fa-spinner fa-spin"></i>
                <span>북마크를 불러오는 중입니다...</span>
            </div>
        `;
        return;
    }

    if (bookmarksError) {
        bookmarkContent.innerHTML = `
            <div class="bookmark-placeholder error">
                <p>${escapeHtml(bookmarksError)}</p>
                <button class="btn-bookmark-retry" onclick="window.NoteEditorPage.reloadBookmarks()">
                    <i class="fas fa-redo"></i>
                    <span>다시 시도</span>
                </button>
            </div>
        `;
        return;
    }

    if (bookmarkCategories.length === 0) {
        bookmarkContent.innerHTML = `
            <div class="bookmark-placeholder">
                <i class="fas fa-info-circle"></i>
                <span>등록된 북마크가 없습니다.</span>
            </div>
        `;
        return;
    }

    bookmarkContent.innerHTML = bookmarkCategories.map((category, index) => `
        <div class="bookmark-category">
            <div class="bookmark-category-header-wrapper">
                <button class="bookmark-category-header" onclick="window.NoteEditorPage.toggleBookmarkCategory(${index})">
                    <i class="fas ${openBookmarkCategories[index] ? 'fa-chevron-down' : 'fa-chevron-right'}"></i>
                    <i class="fas fa-folder"></i>
                    <span class="bookmark-category-title">${escapeHtml(category.name)}</span>
                    <span class="bookmark-category-count">(${category.bookmarks.length})</span>
                </button>
                <button class="btn-bookmark-add-to-category" onclick="window.NoteEditorPage.showAddBookmarkForm(${category.id})" title="북마크 추가">
                    <i class="fas fa-plus"></i>
                </button>
                ${isBookmarkEditMode ? `
                    <button class="btn-bookmark-delete-category" onclick="window.NoteEditorPage.deleteBookmarkCategory(${category.id}, '${escapeHtml(category.name)}')" title="카테고리 삭제">
                        <i class="fas fa-times"></i>
                    </button>
                ` : ''}
            </div>
            ${openBookmarkCategories[index] ? `
                <div class="bookmark-items">
                    ${addingBookmarkToCategoryId === category.id ? `
                        <div class="bookmark-add-form">
                            <input
                                type="text"
                                id="bookmarkNewTitle_${category.id}"
                                placeholder="북마크 제목..."
                                class="bookmark-input"
                            />
                            <input
                                type="url"
                                id="bookmarkNewUrl_${category.id}"
                                placeholder="URL (https://...)"
                                class="bookmark-input"
                                onkeypress="if(event.key==='Enter') window.NoteEditorPage.addBookmark(${category.id})"
                            />
                            <div class="bookmark-form-actions">
                                <button class="btn-bookmark-save" onclick="window.NoteEditorPage.addBookmark(${category.id})">저장</button>
                                <button class="btn-bookmark-cancel" onclick="window.NoteEditorPage.cancelAddBookmark()">취소</button>
                            </div>
                        </div>
                    ` : ''}
                    ${category.bookmarks.map(item => `
                        <div class="bookmark-item">
                            <div class="bookmark-item-header">
                                <i class="fas fa-file-alt"></i>
                                <span class="bookmark-item-title">${escapeHtml(item.title)}</span>
                                ${isBookmarkEditMode ? `
                                    <button class="btn-bookmark-delete" onclick="window.NoteEditorPage.deleteBookmark(${category.id}, ${item.id}, '${escapeHtml(item.title)}')" title="북마크 삭제">
                                        <i class="fas fa-times"></i>
                                    </button>
                                ` : ''}
                            </div>
                            <div class="bookmark-item-actions">
                                <button class="btn-bookmark-add" onclick="window.NoteEditorPage.addBookmarkToNote('${escapeHtml(item.title)}', '${escapeHtml(item.url)}')">
                                    <i class="fas fa-plus-circle"></i>
                                    <span>노트에 추가</span>
                                </button>
                                <a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer" class="btn-bookmark-view">
                                    <i class="fas fa-external-link-alt"></i>
                                    <span>상세 보기</span>
                                </a>
                            </div>
                        </div>
                    `).join('')}
                </div>
            ` : ''}
        </div>
    `).join('');
}

// Toggle bookmark category
function toggleBookmarkCategory(index) {
    openBookmarkCategories[index] = !openBookmarkCategories[index];
    renderBookmarks();
}

// Add bookmark to note
function addBookmarkToNote(title, url) {
    if (!editorInstance) {
        if (window.notyf) {
            window.notyf.error('에디터가 초기화되지 않았습니다.');
        }
        return;
    }

    // 현재 에디터 내용 가져오기
    const currentContent = editorInstance.getData();
    
    // 참고 자료 HTML 추가
    const referenceHtml = `<p><strong>📌 참고 자료:</strong> <a href="${url}" target="_blank" rel="noopener noreferrer">${escapeHtml(title)}</a></p>`;
    
    // 에디터에 새 내용 설정
    editorInstance.setData(currentContent + referenceHtml);
    
    // 에디터에 포커스
    editorInstance.focus();
    
    if (window.notyf) {
        window.notyf.success('북마크가 노트에 추가되었습니다.');
    }
}

// Get CSRF Token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Escape HTML
function escapeHtml(text) {
    if (text === null || text === undefined) {
        return '';
    }

    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
    };

    return String(text).replace(/[&<>"']/g, (char) => map[char]);
}

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNoteEditor);
} else {
    initNoteEditor();
}

// Toggle bookmark edit mode
function handleToggleBookmarkEditMode() {
    isBookmarkEditMode = !isBookmarkEditMode;
    if (btnBookmarkEditToggle) {
        if (isBookmarkEditMode) {
            btnBookmarkEditToggle.classList.add('active');
        } else {
            btnBookmarkEditToggle.classList.remove('active');
        }
    }
    renderBookmarks();
}

// Show add category form
function handleShowAddCategoryForm() {
    isAddingBookmarkCategory = true;
    if (bookmarkAddCategoryForm) {
        bookmarkAddCategoryForm.style.display = 'block';
    }
    if (bookmarkNewCategoryName) {
        bookmarkNewCategoryName.focus();
    }
}

// Cancel add category
function handleCancelAddCategory() {
    isAddingBookmarkCategory = false;
    newCategoryName = '';
    if (bookmarkAddCategoryForm) {
        bookmarkAddCategoryForm.style.display = 'none';
    }
    if (bookmarkNewCategoryName) {
        bookmarkNewCategoryName.value = '';
    }
}

// Add bookmark category
async function handleAddCategory() {
    const categoryName = bookmarkNewCategoryName ? bookmarkNewCategoryName.value.trim() : '';
    if (!categoryName) {
        if (window.notyf) {
            window.notyf.error('카테고리 이름을 입력해주세요.');
        }
        return;
    }

    try {
        const response = await fetch(bookmarkApiUrl + 'categories/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            credentials: 'same-origin',
            body: JSON.stringify({ category_name: categoryName }),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP ${response.status}`);
        }

        const data = await response.json();
        
        // 서버에서 새로고침하여 최신 데이터 가져오기
        await loadBookmarks();
        
        handleCancelAddCategory();
        
        if (window.notyf) {
            window.notyf.success('카테고리가 추가되었습니다.');
        }
    } catch (error) {
        console.error('[NoteEditor] Failed to add category:', error);
        if (window.notyf) {
            window.notyf.error(error.message || '카테고리 추가에 실패했습니다.');
        }
    }
}

// Show add bookmark form
function showAddBookmarkForm(categoryId) {
    addingBookmarkToCategoryId = categoryId;
    renderBookmarks();
    // Focus on title input after render
    setTimeout(() => {
        const titleInput = document.getElementById(`bookmarkNewTitle_${categoryId}`);
        if (titleInput) {
            titleInput.focus();
        }
    }, 100);
}

// Cancel add bookmark
function cancelAddBookmark() {
    addingBookmarkToCategoryId = null;
    newBookmarkTitle = '';
    newBookmarkUrl = '';
    renderBookmarks();
}

// Add bookmark
async function addBookmark(categoryId) {
    const titleInput = document.getElementById(`bookmarkNewTitle_${categoryId}`);
    const urlInput = document.getElementById(`bookmarkNewUrl_${categoryId}`);
    
    const title = titleInput ? titleInput.value.trim() : '';
    const url = urlInput ? urlInput.value.trim() : '';

    if (!title || !url) {
        if (window.notyf) {
            window.notyf.error('제목과 URL을 모두 입력해주세요.');
        }
        return;
    }

    try {
        const response = await fetch(bookmarkApiUrl + 'bookmarks/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            credentials: 'same-origin',
            body: JSON.stringify({
                category_sid: categoryId,
                title: title,
                bookmark_url: url,
            }),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP ${response.status}`);
        }

        // 서버에서 새로고침하여 최신 데이터 가져오기
        await loadBookmarks();
        
        cancelAddBookmark();
        
        if (window.notyf) {
            window.notyf.success('북마크가 추가되었습니다.');
        }
    } catch (error) {
        console.error('[NoteEditor] Failed to add bookmark:', error);
        if (window.notyf) {
            window.notyf.error(error.message || '북마크 추가에 실패했습니다.');
        }
    }
}

// Delete bookmark category
async function deleteBookmarkCategory(categoryId, categoryName) {
    if (!window.Swal) {
        if (confirm(`"${categoryName}" 카테고리를 삭제하시겠습니까? 카테고리 내 모든 북마크도 함께 삭제됩니다.`)) {
            await performDeleteCategory(categoryId);
        }
        return;
    }

    window.Swal.fire({
        title: '카테고리 삭제',
        html: `"<strong>${escapeHtml(categoryName)}</strong>" 카테고리를 삭제하시겠습니까?<br><br>카테고리 내 모든 북마크도 함께 삭제됩니다.`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#dc2626',
        cancelButtonColor: '#6b7280',
        confirmButtonText: '삭제하기',
        cancelButtonText: '취소',
        reverseButtons: true
    }).then(async (result) => {
        if (result.isConfirmed) {
            await performDeleteCategory(categoryId);
        }
    });
}

// Perform delete category
async function performDeleteCategory(categoryId) {
    try {
        const response = await fetch(bookmarkApiUrl + `categories/${categoryId}/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
            },
            credentials: 'same-origin',
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP ${response.status}`);
        }

        // 서버에서 새로고침하여 최신 데이터 가져오기
        await loadBookmarks();
        
        if (window.notyf) {
            window.notyf.success('카테고리가 삭제되었습니다.');
        }
    } catch (error) {
        console.error('[NoteEditor] Failed to delete category:', error);
        if (window.notyf) {
            window.notyf.error(error.message || '카테고리 삭제에 실패했습니다.');
        }
    }
}

// Delete bookmark
async function deleteBookmark(categoryId, bookmarkId, bookmarkTitle) {
    if (!window.Swal) {
        if (confirm(`"${bookmarkTitle}" 북마크를 삭제하시겠습니까?`)) {
            await performDeleteBookmark(categoryId, bookmarkId);
        }
        return;
    }

    window.Swal.fire({
        title: '북마크 삭제',
        html: `"<strong>${escapeHtml(bookmarkTitle)}</strong>" 북마크를 삭제하시겠습니까?`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#dc2626',
        cancelButtonColor: '#6b7280',
        confirmButtonText: '삭제하기',
        cancelButtonText: '취소',
        reverseButtons: true
    }).then(async (result) => {
        if (result.isConfirmed) {
            await performDeleteBookmark(categoryId, bookmarkId);
        }
    });
}

// Perform delete bookmark
async function performDeleteBookmark(categoryId, bookmarkId) {
    try {
        const response = await fetch(bookmarkApiUrl + `bookmarks/${bookmarkId}/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
            },
            credentials: 'same-origin',
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP ${response.status}`);
        }

        // 서버에서 새로고침하여 최신 데이터 가져오기
        await loadBookmarks();
        
        if (window.notyf) {
            window.notyf.success('북마크가 삭제되었습니다.');
        }
    } catch (error) {
        console.error('[NoteEditor] Failed to delete bookmark:', error);
        if (window.notyf) {
            window.notyf.error(error.message || '북마크 삭제에 실패했습니다.');
        }
    }
}

// Export to window
window.NoteEditorPage = {
    handleFileRemove,
    toggleBookmarkCategory,
    addBookmarkToNote,
    reloadBookmarks: loadBookmarks,
    showAddBookmarkForm,
    cancelAddBookmark,
    addBookmark,
    deleteBookmarkCategory,
    deleteBookmark,
};
