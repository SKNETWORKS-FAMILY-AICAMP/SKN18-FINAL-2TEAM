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
let openBookmarkCategoryMenuId = null;
let editingCategoryId = null;
let openBookmarkMenuId = null; // {categoryId_bookmarkId: true}
let editingBookmarkId = null; // {categoryId_bookmarkId: true}
let selectedShareMembers = []; // 공유할 사용자 정보 저장

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
        if (btnSaveNote) btnSaveNote.textContent = '수정';
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

// Show HTML preview in a modal or new window
function showHtmlPreview(htmlContent) {
    if (!htmlContent || !htmlContent.trim()) {
        if (window.notyf) {
            window.notyf.info('미리볼 내용이 없습니다.');
        }
        return;
    }

    // Use SweetAlert2 for modal if available, otherwise use window.open
    if (window.Swal) {
        window.Swal.fire({
            title: 'HTML 미리보기',
            html: `
                <div style="text-align: left;">
                    <div style="margin-bottom: 1rem;">
                        <button id="btnViewRendered" class="swal2-confirm swal2-styled" style="margin-right: 0.5rem; background-color: #3b82f6;">
                            렌더링된 HTML 보기
                        </button>
                        <button id="btnViewSource" class="swal2-confirm swal2-styled" style="background-color: #10b981;">
                            HTML 소스 보기
                        </button>
                    </div>
                    <div id="htmlPreviewContent" style="max-height: 60vh; overflow-y: auto; padding: 1rem; border: 1px solid #ddd; border-radius: 4px; background: #fff; text-align: left;">
                        ${htmlContent}
                    </div>
                    <textarea id="htmlSourceTextarea" style="display: none; width: 100%; min-height: 300px; font-family: monospace; padding: 0.5rem; border: 1px solid #ddd; border-radius: 4px; background: #f9fafb; font-size: 12px; white-space: pre-wrap; word-wrap: break-word;">${escapeHtml(htmlContent)}</textarea>
                </div>
            `,
            width: '90%',
            showConfirmButton: true,
            confirmButtonText: '닫기',
            didOpen: () => {
                const btnViewRendered = document.getElementById('btnViewRendered');
                const btnViewSource = document.getElementById('btnViewSource');
                const previewContent = document.getElementById('htmlPreviewContent');
                const sourceTextarea = document.getElementById('htmlSourceTextarea');

                if (btnViewRendered && btnViewSource && previewContent && sourceTextarea) {
                    btnViewRendered.addEventListener('click', () => {
                        previewContent.style.display = 'block';
                        sourceTextarea.style.display = 'none';
                        btnViewRendered.style.backgroundColor = '#3b82f6';
                        btnViewSource.style.backgroundColor = '#6b7280';
                    });

                    btnViewSource.addEventListener('click', () => {
                        previewContent.style.display = 'none';
                        sourceTextarea.style.display = 'block';
                        btnViewRendered.style.backgroundColor = '#6b7280';
                        btnViewSource.style.backgroundColor = '#10b981';
                    });

                    // Default to rendered view
                    btnViewRendered.style.backgroundColor = '#3b82f6';
                    btnViewSource.style.backgroundColor = '#6b7280';
                }
            }
        });
    } else {
        // Fallback: 새 창으로 열기
        const previewWindow = window.open('', '_blank', 'width=900,height=700');
        if (previewWindow) {
            previewWindow.document.write(`
                <!DOCTYPE html>
                <html>
                <head>
                    <title>HTML 미리보기</title>
                    <meta charset="UTF-8">
                    <style>
                        body { 
                            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                            padding: 2rem; 
                            max-width: 1200px; 
                            margin: 0 auto; 
                            background: #f9fafb;
                        }
                        .preview-container {
                            background: white;
                            border: 1px solid #e5e7eb;
                            border-radius: 8px;
                            padding: 2rem;
                            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                        }
                        .tabs {
                            display: flex;
                            margin-bottom: 1rem;
                            border-bottom: 2px solid #e5e7eb;
                        }
                        .tab {
                            padding: 0.75rem 1.5rem;
                            cursor: pointer;
                            border: none;
                            background: none;
                            font-size: 14px;
                            font-weight: 500;
                            color: #6b7280;
                            border-bottom: 2px solid transparent;
                            margin-bottom: -2px;
                        }
                        .tab.active {
                            color: #3b82f6;
                            border-bottom-color: #3b82f6;
                        }
                        .tab-content {
                            display: none;
                        }
                        .tab-content.active {
                            display: block;
                        }
                        #renderedContent {
                            line-height: 1.6;
                        }
                        #sourceContent {
                            font-family: 'Courier New', monospace;
                            font-size: 12px;
                            white-space: pre-wrap;
                            word-wrap: break-word;
                            background: #f9fafb;
                            padding: 1rem;
                            border-radius: 4px;
                            border: 1px solid #e5e7eb;
                            max-height: 500px;
                            overflow-y: auto;
                        }
                        img {
                            max-width: 100%;
                            height: auto;
                        }
                    </style>
                </head>
                <body>
                    <div class="preview-container">
                        <div class="tabs">
                            <button class="tab active" onclick="showTab('rendered')">렌더링된 HTML</button>
                            <button class="tab" onclick="showTab('source')">HTML 소스</button>
                        </div>
                        <div id="renderedContent" class="tab-content active">
                            ${htmlContent}
                        </div>
                        <div id="sourceContent" class="tab-content"></div>
                    </div>
                    <script>
                        function showTab(tabName) {
                            // Update tabs
                            document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
                            document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
                            
                            if (tabName === 'rendered') {
                                document.querySelectorAll('.tab')[0].classList.add('active');
                                document.getElementById('renderedContent').classList.add('active');
                            } else {
                                document.querySelectorAll('.tab')[1].classList.add('active');
                                const sourceContent = document.getElementById('sourceContent');
                                sourceContent.textContent = ${JSON.stringify(htmlContent)};
                                sourceContent.classList.add('active');
                            }
                        }
                    </script>
                </body>
                </html>
            `);
            previewWindow.document.close();
        }
    }
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
        MediaEmbed,
        SourceEditing
    } = window.CKEditor;

    // Plugin과 ButtonView는 선택적으로 가져오기 (없을 수 있음)
    const Plugin = window.CKEditor.Plugin;
    const ButtonView = window.CKEditor.ButtonView;

    // ClassicEditor가 있는지 확인
    if (!ClassicEditor) {
        console.error('[NoteEditor] ClassicEditor not found in window.CKEditor');
        editorElement.innerHTML = '<p style="color: #ef4444; padding: 1rem;">에디터 클래스를 찾을 수 없습니다.</p>';
        return;
    }

    // HTML 미리보기 커스텀 플러그인 정의 (Plugin과 ButtonView가 있을 경우에만)
    let HtmlPreviewPlugin = undefined;
    if (Plugin && ButtonView) {
        HtmlPreviewPlugin = class extends Plugin {
            static get pluginName() {
                return 'HtmlPreview';
            }

            init() {
                const editor = this.editor;

                editor.ui.componentFactory.add('htmlPreview', locale => {
                    const view = new ButtonView(locale);

                    view.set({
                        label: 'HTML 미리보기',
                        tooltip: true,
                        icon: '<svg viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path d="M3 3h14v14H3V3zm1 1v12h12V4H4zm2 2h8v1H6V6zm0 2h8v1H6V8zm0 2h5v1H6v-1zm0 2h8v1H6v-1z"/></svg>'
                    });

                    view.on('execute', () => {
                        const htmlContent = editor.getData();
                        showHtmlPreview(htmlContent);
                    });

                    return view;
                });
            }
        };
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
        MediaEmbed,
        SourceEditing,
        HtmlPreviewPlugin
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
                'sourceEditing',
                ...(HtmlPreviewPlugin ? ['htmlPreview'] : []),
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
        
        // HTML 미리보기 플러그인이 없을 경우, 에디터 초기화 후 버튼 추가
        if (!HtmlPreviewPlugin && editor && editor.ui && editor.ui.componentFactory) {
            // 에디터가 초기화된 후에 직접 버튼 추가 시도
            // 이 부분은 SourceEditing 플러그인이 작동하는지 확인 후 필요시 추가
            console.log('[NoteEditor] HtmlPreviewPlugin not available, using alternative method if needed');
        }
        
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
async function loadNoteForEdit(noteId) {
    if (!noteId) {
        console.error('[NoteEditor] Note ID is required for editing');
        if (window.notyf) {
            window.notyf.error('노트 ID가 필요합니다.');
        }
        return;
    }

    try {
        const response = await fetch(`/api/notes/${noteId}/`, {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
            },
            credentials: 'same-origin'
        });

        if (!response.ok) {
            if (response.status === 404) {
                throw new Error('노트를 찾을 수 없습니다.');
            }
            throw new Error(`Failed to load note: ${response.status}`);
        }

        const data = await response.json();

        if (data.status === 'success' && data.note) {
            const note = data.note;

            // 제목 설정
            if (noteTitleInput) {
                noteTitleInput.value = note.title || '';
            }

            // 태그 설정
            const tags = note.tags || [];
    if (tagifyInstance) {
        tagifyInstance.removeAllTags();
                if (tags.length > 0) {
                    tagifyInstance.addTags(tags);
                }
    } else if (noteTagsInput) {
                noteTagsInput.value = tags.join(', ');
    }
    
    // CKEditor에 컨텐츠 설정
    if (editorInstance) {
                editorInstance.setData(note.content || '');
            }

            // 기존 첨부 파일 로드
            if (note.attachments && Array.isArray(note.attachments)) {
                attachedFiles = note.attachments.map((attachment) => ({
                    id: fileIdCounter++,
                    name: attachment.name || '',
                    size: formatFileSize(attachment.size || 0), // 포맷팅된 크기
                    sizeBytes: attachment.size || 0, // 원본 바이트 크기
                    file: null, // 기존 파일은 서버에 있으므로 File 객체 없음
                    attachmentId: attachment.id, // 기존 첨부 파일 ID 저장
                    s3Key: attachment.path || '',
                    isExisting: true // 기존 파일 표시
                }));
                renderAttachedFiles();
            }

            // 기존 공유 멤버 정보 로드 (API에서 제공하는 경우)
            // Note: 현재 API 응답에 sharedMembers 정보가 없을 수 있으므로
            // 별도 API 호출이 필요할 수 있습니다.
            // 일단 빈 배열로 초기화 (추후 API 확장 시 구현)
            selectedShareMembers = [];

            if (window.notyf) {
                window.notyf.success('노트를 불러왔습니다.');
            }
        } else {
            throw new Error(data.error || '노트 데이터를 불러올 수 없습니다.');
        }
    } catch (error) {
        console.error('[NoteEditor] Error loading note for edit:', error);
        if (window.notyf) {
            window.notyf.error(error.message || '노트를 불러오는 중 오류가 발생했습니다.');
        }
        
        // 에러 발생 시 목록으로 돌아가기
        setTimeout(() => {
            window.location.href = '/notes/';
        }, 2000);
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

    // 편집 모드일 때는 상세 페이지로, 새로 작성할 때는 목록으로 이동
    const redirectUrl = isEditMode && editingNoteId 
        ? `/notes/detail/?id=${editingNoteId}`
        : '/notes/';

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
                    window.location.href = redirectUrl;
                }
            });
        } else {
            // Fallback to confirm if SweetAlert2 is not available
            if (confirm('작성 중인 내용이 저장되지 않습니다. 정말 취소하시겠습니까?')) {
                window.location.href = redirectUrl;
            }
        }
    } else {
        // No content, just navigate
        window.location.href = redirectUrl;
    }
}

// Handle save note
async function handleSaveNote() {
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

    // 파일 크기 검증 (1GB = 1073741824 bytes)
    const MAX_FILE_SIZE = 1024 * 1024 * 1024; // 1GB
    const oversizedFiles = attachedFiles.filter(file => {
        // 새로 첨부한 파일(file.file) 또는 기존 파일의 크기 확인
        const fileSize = file.file ? file.file.size : (file.sizeBytes || 0);
        if (fileSize > MAX_FILE_SIZE) {
            return true;
        }
        return false;
    });

    if (oversizedFiles.length > 0) {
        if (window.notyf) {
            window.notyf.error(`파일 크기가 1GB를 초과합니다: ${oversizedFiles.map(f => f.name).join(', ')}`);
        } else {
            alert(`파일 크기가 1GB를 초과합니다: ${oversizedFiles.map(f => f.name).join(', ')}`);
        }
        return;
    }

    try {
        // FormData 생성
        const formData = new FormData();
        formData.append('title', title);
        formData.append('content', content);
        formData.append('tags', JSON.stringify(tags));
        formData.append('sharedMembers', JSON.stringify(selectedShareMembers));

        // 첨부 파일 추가
        attachedFiles.forEach((fileData, index) => {
            if (fileData.file) {
                formData.append(`file_${index}`, fileData.file);
                formData.append(`file_${index}_name`, fileData.name);
            }
        });

        // API 엔드포인트 결정
            const apiUrl = isEditMode
                ? `/api/notes/${editingNoteId}/update/`
                : '/api/notes/create/';
        
        const method = isEditMode ? 'PUT' : 'POST';

        // 저장 버튼 비활성화
        if (btnSaveNote) {
            btnSaveNote.disabled = true;
            const originalText = btnSaveNote.textContent;
            btnSaveNote.textContent = '저장 중...';
        }

        // API 호출
        const response = await fetch(apiUrl, {
            method: method,
            body: formData,
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            credentials: 'same-origin'
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || '노트 저장에 실패했습니다.');
        }

        if (data.status === 'success') {
    if (window.notyf) {
        window.notyf.success(isEditMode ? '노트가 수정되었습니다.' : '노트가 저장되었습니다.');
    }

            // 상태 초기화
            selectedShareMembers = [];
            attachedFiles = [];
            attachedCharts = [];

            // 편집 모드일 때는 상세 페이지로, 새로 작성할 때는 목록으로 이동
            const redirectUrl = isEditMode && editingNoteId 
                ? `/notes/detail/?id=${editingNoteId}`
                : '/notes/';

    setTimeout(() => {
                window.location.href = redirectUrl;
    }, 1000);
        } else {
            throw new Error(data.error || '응답 데이터가 올바르지 않습니다.');
        }
    } catch (error) {
        console.error('[NoteEditor] Failed to save note:', error);
        if (window.notyf) {
            window.notyf.error(error.message || '노트 저장에 실패했습니다.');
        } else {
            alert(error.message || '노트 저장에 실패했습니다.');
        }
    } finally {
        // 저장 버튼 활성화
        if (btnSaveNote) {
            btnSaveNote.disabled = false;
            btnSaveNote.textContent = isEditMode ? '수정' : '저장';
        }
    }
}

// Handle share note
function handleShareNote() {
    if (window.ShareModal && typeof window.ShareModal.open === 'function') {
        window.ShareModal.onShare = (selectedMemberIds, selectedMemberDetails) => {
            // 선택한 사용자 정보 저장 (노트 저장 시 사용)
            selectedShareMembers = selectedMemberDetails || [];
            
            if (window.notyf) {
                window.notyf.success(`${selectedShareMembers.length}명이 선택되었습니다. 노트 저장 시 공유됩니다.`);
            }
        };
        window.ShareModal.open(editingNoteId, null, null, '노트 공유');
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
        if (files.length === 0) {
            return; // 파일이 선택되지 않은 경우
        }

        files.forEach(file => {
            const newFile = {
                id: fileIdCounter++,
                name: file.name,
                size: formatFileSize(file.size),
                sizeBytes: file.size, // 원본 바이트 크기 저장
                file: file,  // 파일 객체 저장 (업로드용)
                isExisting: false // 새 파일
            };
            attachedFiles.push(newFile);
        });
        renderAttachedFiles();

        // 파일 첨부 완료 메시지
        if (window.notyf) {
            if (files.length === 1) {
                window.notyf.success(`파일이 첨부되었습니다: ${files[0].name}`);
            } else {
                window.notyf.success(`${files.length}개의 파일이 첨부되었습니다.`);
            }
        }
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

    attachedFilesList.innerHTML = attachedFiles.map(file => {
        // 파일 크기 표시 (이미 포맷팅된 경우 그대로 사용, 아니면 포맷팅)
        const displaySize = file.size || (file.sizeBytes ? formatFileSize(file.sizeBytes) : '0B');
        // 기존 파일인지 새 파일인지 표시
        const fileLabel = file.isExisting ? ' (기존)' : '';
        
        return `
        <div class="attached-file-item">
            <i class="fa-solid fa-file-alt"></i>
            <div class="attached-file-info">
                <span class="attached-file-name">${escapeHtml(file.name)}${fileLabel}</span>
                <span class="attached-file-size">${displaySize}</span>
            </div>
            <button class="btn-file-remove" onclick="window.NoteEditorPage.handleFileRemove(${file.id})">
                <i class="fa-solid fa-times"></i>
            </button>
        </div>
        `;
    }).join('');
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
        openBookmarkCategoryMenuId = null;
        openBookmarkMenuId = null;
        editingBookmarkId = null;

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
                <button class="bookmark-category-header" onclick="${editingCategoryId === category.id ? 'event.stopPropagation();' : `window.NoteEditorPage.toggleBookmarkCategory(${index})`}">
                    <i class="fas ${openBookmarkCategories[index] ? 'fa-chevron-down' : 'fa-chevron-right'}"></i>
                    <i class="fas fa-folder"></i>
                    ${editingCategoryId === category.id ? `
                        <input
                            type="text"
                            id="bookmarkCategoryNameInput_${category.id}"
                            value="${escapeHtml(category.name)}"
                            class="bookmark-category-name-input"
                            onkeydown="if(event.key==='Enter') { event.preventDefault(); window.NoteEditorPage.saveCategoryName(${category.id}); } if(event.key==='Escape') { event.preventDefault(); window.NoteEditorPage.cancelEditCategoryName(); }"
                            onclick="event.stopPropagation();"
                        />
                    ` : `
                        <span class="bookmark-category-title">${escapeHtml(category.name)}</span>
                    `}
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
                <button class="btn-bookmark-category-menu" onclick="window.NoteEditorPage.toggleBookmarkCategoryMenu(${category.id}, event)" title="메뉴">
                    <i class="fas fa-ellipsis-vertical"></i>
                </button>
                ${openBookmarkCategoryMenuId === category.id ? `
                    <div class="bookmark-category-menu-popup" id="bookmarkCategoryMenu_${category.id}">
                        <button class="bookmark-category-menu-item" onclick="window.NoteEditorPage.editCategoryName(${category.id}, '${escapeHtml(category.name)}')">
                            <i class="fas fa-pen"></i>
                            <span>이름 수정</span>
                        </button>
                        <button class="bookmark-category-menu-item" onclick="window.NoteEditorPage.deleteBookmarkCategory(${category.id}, '${escapeHtml(category.name)}')">
                            <i class="fas fa-trash"></i>
                            <span>삭제</span>
                        </button>
                    </div>
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
                    ${category.bookmarks.map(item => {
                        const bookmarkKey = `${category.id}_${item.id}`;
                        const isEditing = editingBookmarkId === bookmarkKey;
                        const menuOpen = openBookmarkMenuId === bookmarkKey;
                        return `
                        <div class="bookmark-item">
                            <div class="bookmark-item-header">
                                <i class="fas fa-file-alt"></i>
                                ${isEditing ? `
                                    <div class="bookmark-edit-form">
                                        <input
                                            type="text"
                                            id="bookmarkEditTitle_${category.id}_${item.id}"
                                            value="${escapeHtml(item.title)}"
                                            class="bookmark-input"
                                            placeholder="북마크 제목..."
                                        />
                                        <input
                                            type="url"
                                            id="bookmarkEditUrl_${category.id}_${item.id}"
                                            value="${escapeHtml(item.url)}"
                                            class="bookmark-input"
                                            placeholder="URL (https://...)"
                                            onkeypress="if(event.key==='Enter') window.NoteEditorPage.saveBookmark(${category.id}, ${item.id})"
                                        />
                                    </div>
                                ` : `
                                    <span class="bookmark-item-title">${escapeHtml(item.title)}</span>
                                `}
                                ${isBookmarkEditMode ? `
                                    <button class="btn-bookmark-delete" onclick="window.NoteEditorPage.deleteBookmark(${category.id}, ${item.id}, '${escapeHtml(item.title)}')" title="북마크 삭제">
                                        <i class="fas fa-times"></i>
                                    </button>
                                ` : ''}
                                ${!isEditing ? `
                                    <button class="btn-bookmark-menu" onclick="window.NoteEditorPage.toggleBookmarkMenu(${category.id}, ${item.id}, event)" title="메뉴">
                                        <i class="fas fa-ellipsis-vertical"></i>
                                    </button>
                                ` : ''}
                                ${menuOpen ? `
                                    <div class="bookmark-menu-popup" id="bookmarkMenu_${category.id}_${item.id}">
                                        <button class="bookmark-menu-item" onclick="window.NoteEditorPage.openBookmarkInNewTab('${escapeHtml(item.url)}')">
                                            <i class="fas fa-external-link-alt"></i>
                                            <span>새 탭에서 열기</span>
                                        </button>
                                        <button class="bookmark-menu-item" onclick="window.NoteEditorPage.editBookmark(${category.id}, ${item.id}, '${escapeHtml(item.title)}', '${escapeHtml(item.url)}')">
                                            <i class="fas fa-pen"></i>
                                            <span>수정</span>
                                        </button>
                                        <button class="bookmark-menu-item" onclick="window.NoteEditorPage.deleteBookmark(${category.id}, ${item.id}, '${escapeHtml(item.title)}')">
                                            <i class="fas fa-trash"></i>
                                            <span>삭제</span>
                                        </button>
                                    </div>
                                ` : ''}
                            </div>
                            ${isEditing ? `
                                <div class="bookmark-form-actions">
                                    <button class="btn-bookmark-save" onclick="window.NoteEditorPage.saveBookmark(${category.id}, ${item.id})">저장</button>
                                    <button class="btn-bookmark-cancel" onclick="window.NoteEditorPage.cancelEditBookmark()">취소</button>
                                </div>
                            ` : `
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
                            `}
                        </div>
                    `;
                    }).join('')}
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
    // Reset menu and editing states when exiting edit mode
    if (!isBookmarkEditMode) {
        openBookmarkCategoryMenuId = null;
        openBookmarkMenuId = null;
        editingCategoryId = null;
        editingBookmarkId = null;
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
    
    // 해당 카테고리를 항상 열림 상태로 설정
    const categoryIndex = bookmarkCategories.findIndex(cat => cat.id === categoryId);
    if (categoryIndex !== -1) {
        openBookmarkCategories[categoryIndex] = true;
    }
    
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
        if (confirm('이 카테고리의 모든 북마크가 삭제됩니다. 삭제하시겠습니까?')) {
            await performDeleteCategory(categoryId);
        }
        return;
    }

    window.Swal.fire({
        title: '카테고리 삭제',
        html: '이 카테고리의 모든 북마크가 삭제됩니다. 삭제하시겠습니까?',
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
        const response = await fetch(bookmarkApiUrl + `categories/${categoryId}/delete/`, {
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
        const response = await fetch(bookmarkApiUrl + `bookmarks/${bookmarkId}/delete/`, {
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

// Toggle bookmark category menu
function toggleBookmarkCategoryMenu(categoryId, event) {
    if (event) {
        event.stopPropagation();
    }
    
    if (openBookmarkCategoryMenuId === categoryId) {
        openBookmarkCategoryMenuId = null;
    } else {
        openBookmarkCategoryMenuId = categoryId;
    }
    renderBookmarks();
    
    // 외부 클릭 시 메뉴 닫기
    if (openBookmarkCategoryMenuId !== null) {
        setTimeout(() => {
            const handleClickOutside = (e) => {
                const menu = document.getElementById(`bookmarkCategoryMenu_${categoryId}`);
                const menuBtn = e.target.closest('.btn-bookmark-category-menu');
                if (menu && !menu.contains(e.target) && !menuBtn) {
                    openBookmarkCategoryMenuId = null;
                    renderBookmarks();
                    document.removeEventListener('click', handleClickOutside);
                }
            };
            document.addEventListener('click', handleClickOutside);
        }, 0);
    }
}

// Toggle bookmark menu
function toggleBookmarkMenu(categoryId, bookmarkId, event) {
    if (event) {
        event.stopPropagation();
    }
    
    const bookmarkKey = `${categoryId}_${bookmarkId}`;
    
    if (openBookmarkMenuId === bookmarkKey) {
        openBookmarkMenuId = null;
    } else {
        openBookmarkMenuId = bookmarkKey;
    }
    
    renderBookmarks();
}

// Open bookmark in new tab
function openBookmarkInNewTab(url) {
    if (url) {
        window.open(url, '_blank', 'noopener,noreferrer');
    }
    openBookmarkMenuId = null;
    renderBookmarks();
}

// Edit bookmark
function editBookmark(categoryId, bookmarkId, currentTitle, currentUrl) {
    editingBookmarkId = `${categoryId}_${bookmarkId}`;
    openBookmarkMenuId = null;
    renderBookmarks();
    
    // Focus on title input after render
    setTimeout(() => {
        const titleInput = document.getElementById(`bookmarkEditTitle_${categoryId}_${bookmarkId}`);
        if (titleInput) {
            titleInput.focus();
            titleInput.select();
        }
    }, 0);
}

// Cancel edit bookmark
function cancelEditBookmark() {
    editingBookmarkId = null;
    renderBookmarks();
}

// Save bookmark
async function saveBookmark(categoryId, bookmarkId) {
    const titleInput = document.getElementById(`bookmarkEditTitle_${categoryId}_${bookmarkId}`);
    const urlInput = document.getElementById(`bookmarkEditUrl_${categoryId}_${bookmarkId}`);
    
    const newTitle = titleInput ? titleInput.value.trim() : '';
    const newUrl = urlInput ? urlInput.value.trim() : '';
    
    if (!newTitle) {
        if (window.notyf) {
            window.notyf.error('북마크 제목을 입력해주세요.');
        }
        return;
    }
    
    if (!newUrl) {
        if (window.notyf) {
            window.notyf.error('북마크 URL을 입력해주세요.');
        }
        return;
    }
    
    try {
        const response = await fetch(bookmarkApiUrl + `bookmarks/${bookmarkId}/`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            credentials: 'same-origin',
            body: JSON.stringify({
                title: newTitle,
                bookmark_url: newUrl,
            }),
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || '북마크 수정에 실패했습니다.');
        }
        
        if (data.status === 'success') {
            // 북마크 목록 새로고침하여 수정된 북마크 반영
            await loadBookmarks();
            
            editingBookmarkId = null;
            renderBookmarks();
            
            if (window.notyf) {
                window.notyf.success('북마크가 수정되었습니다.');
            }
        } else {
            throw new Error('응답 데이터가 올바르지 않습니다.');
        }
    } catch (error) {
        console.error('[NoteEditor] Failed to update bookmark:', error);
        if (window.notyf) {
            window.notyf.error(error.message || '북마크 수정에 실패했습니다.');
        }
    }
}

// Edit category name
function editCategoryName(categoryId, currentName) {
    editingCategoryId = categoryId;
    openBookmarkCategoryMenuId = null;
    renderBookmarks();
    
    // 편집 모드로 전환 후 입력 필드에 포커스
    setTimeout(() => {
        const input = document.getElementById(`bookmarkCategoryNameInput_${categoryId}`);
        if (input) {
            input.focus();
            input.select();
        }
    }, 100);
}

// Cancel edit category name
function cancelEditCategoryName() {
    editingCategoryId = null;
    renderBookmarks();
}

// Save category name
async function saveCategoryName(categoryId) {
    const input = document.getElementById(`bookmarkCategoryNameInput_${categoryId}`);
    const newName = input ? input.value.trim() : '';
    
    if (!newName) {
        if (window.notyf) {
            window.notyf.error('카테고리 이름을 입력해주세요.');
        }
        return;
    }
    
    try {
        const response = await fetch(bookmarkApiUrl + `categories/${categoryId}/`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            credentials: 'same-origin',
            body: JSON.stringify({ category_name: newName }),
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || '카테고리 이름 수정에 실패했습니다.');
        }
        
        if (data.status === 'success' && data.category) {
            // 북마크 목록 새로고침하여 수정된 카테고리 이름 반영
            await loadBookmarks();
            
            editingCategoryId = null;
            renderBookmarks();
            
            if (window.notyf) {
                window.notyf.success('카테고리 이름이 수정되었습니다.');
            }
        } else {
            throw new Error('응답 데이터가 올바르지 않습니다.');
        }
    } catch (error) {
        console.error('[NoteEditor] Failed to update category name:', error);
        if (window.notyf) {
            window.notyf.error(error.message || '카테고리 이름 수정에 실패했습니다.');
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
    toggleBookmarkCategoryMenu,
    editCategoryName,
    cancelEditCategoryName,
    saveCategoryName,
    toggleBookmarkMenu,
    openBookmarkInNewTab,
    editBookmark,
    cancelEditBookmark,
    saveBookmark,
};
