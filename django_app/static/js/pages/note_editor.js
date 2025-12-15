/* django_app/static/js/pages/note_editor.js */
// Note Editor Page JavaScript

// State variables
let editingNoteId = null;
let isEditMode = false;
let isSaving = false;
let isLoading = false;

let noteTitle = '';
let noteContent = '';
let noteTags = '';
let isBookmarkSidebarOpen = false;
let openBookmarkCategories = {};
let attachedFiles = [];
let fileIdCounter = 1;

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

// Bookmarks data (sample)
const bookmarks = [
    {
        category: '실험 프로토콜',
        items: [
            { id: 1, title: 'CRISPR 표준 프로토콜', url: 'https://example.com/crispr-protocol' },
            { id: 2, title: 'PCR 실험 가이드', url: 'https://example.com/pcr-guide' },
            { id: 3, title: 'Western Blot 절차', url: 'https://example.com/western-blot' }
        ]
    },
    {
        category: '논문 자료',
        items: [
            { id: 4, title: 'AlphaFold2 원문', url: 'https://example.com/alphafold2' },
            { id: 5, title: 'mRNA 백신 연구', url: 'https://example.com/mrna-vaccine' },
            { id: 6, title: 'CRISPR 최신 리뷰', url: 'https://example.com/crispr-review' }
        ]
    },
    {
        category: '데이터베이스',
        items: [
            { id: 7, title: 'PubMed', url: 'https://pubmed.ncbi.nlm.nih.gov/' },
            { id: 8, title: 'UniProt', url: 'https://www.uniprot.org/' },
            { id: 9, title: 'GenBank', url: 'https://www.ncbi.nlm.nih.gov/genbank/' }
        ]
    },
    {
        category: '분석 도구',
        items: [
            { id: 10, title: 'BLAST Search', url: 'https://blast.ncbi.nlm.nih.gov/' },
            { id: 11, title: 'Protein Structure Viewer', url: 'https://example.com/structure-viewer' }
        ]
    }
];

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

    // Attach event listeners
    if (btnCancelNote) btnCancelNote.addEventListener('click', handleCancelNote);
    if (btnSaveNote) btnSaveNote.addEventListener('click', handleSaveNote);
    if (btnShareNote) btnShareNote.addEventListener('click', handleShareNote);
    if (btnBookmarkToggle) btnBookmarkToggle.addEventListener('click', handleToggleBookmark);
    if (btnFileAttach) btnFileAttach.addEventListener('click', handleFileAttach);
    if (btnGraphAttach) btnGraphAttach.addEventListener('click', handleGraphAttach);

    // Check if editing existing note (before editor init)
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
}

// Initialize Tagify for tags input
function initTagify() {
    if (!noteTagsInput || !window.Tagify) {
        console.warn('[NoteEditor] Tagify not available or noteTagsInput not found');
        return;
    }

    // Destroy existing instance to prevent duplicates
    if (tagifyInstance) {
        tagifyInstance.destroy();
        tagifyInstance = null;
    }

    tagifyInstance = new window.Tagify(noteTagsInput, {
        maxTags: 5,
        placeholder: '태그 추가 (최대 5개)',
        delimiters: ',| ',
        trim: true,
        dropdown: {
            enabled: 0,
            maxItems: 10,
            closeOnSelect: true,
            highlightFirst: true
        },
        callbacks: {
            add: (e) => console.log('[NoteEditor] Tag added:', e.detail.data.value),
            remove: (e) => console.log('[NoteEditor] Tag removed:', e.detail.data.value),
            invalid: () => {
                if (window.notyf) window.notyf.error('태그는 최대 5개까지 추가할 수 있습니다.');
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

    if (!window.CKEditor) {
        console.error('[NoteEditor] window.CKEditor not available');
        editorElement.innerHTML = '<p style="color: #ef4444; padding: 1rem;">에디터를 로드할 수 없습니다. 페이지를 새로고침해주세요.</p>';
        return;
    }

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

    if (!ClassicEditor) {
        console.error('[NoteEditor] ClassicEditor not found in window.CKEditor');
        editorElement.innerHTML = '<p style="color: #ef4444; padding: 1rem;">에디터 클래스를 찾을 수 없습니다.</p>';
        return;
    }

    const availablePlugins = [
        Essentials, Bold, Italic, Underline, Strikethrough,
        Paragraph, Heading, Link, List, BlockQuote,
        Table, TableToolbar, Alignment, Indent,
        Image, ImageToolbar, ImageCaption, ImageStyle, ImageUpload,
        Base64UploadAdapter, CodeBlock, HorizontalLine, Highlight, Font, MediaEmbed
    ].filter(Boolean);

    ClassicEditor.create(editorElement, {
        licenseKey: 'GPL',
        plugins: availablePlugins,
        toolbar: {
            items: [
                'heading', '|',
                'bold', 'italic', 'underline', 'strikethrough', '|',
                'fontSize', 'fontColor', '|',
                'alignment', '|',
                'bulletedList', 'numberedList', 'outdent', 'indent', '|',
                'blockQuote', 'insertTable', 'codeBlock', 'horizontalLine', '|',
                'link', 'uploadImage', 'mediaEmbed', '|',
                'highlight', '|',
                'undo', 'redo'
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
        table: { contentToolbar: ['tableColumn', 'tableRow', 'mergeTableCells'] },
        image: { toolbar: ['imageTextAlternative', 'toggleImageCaption', 'imageStyle:inline', 'imageStyle:block', 'imageStyle:side'] },
        placeholder: '연구 내용을 작성하세요... 실험 방법, 결과, 분석 내용 등을 자유롭게 기록할 수 있습니다.',
        language: 'ko'
    })
        .then(editor => {
            editorInstance = editor;
            console.log('[NoteEditor] CKEditor5 initialized successfully');

            // Load data in edit mode
            if (editingNoteId) {
                loadNoteForEdit(editingNoteId);
            }
        })
        .catch(error => {
            console.error('[NoteEditor] CKEditor5 initialization failed:', error);
            editorElement.innerHTML = `<p style="color: #ef4444; padding: 1rem;">에디터 초기화 실패: ${error.message}</p>`;
        });
}

// Load note for editing (real API)
async function loadNoteForEdit(noteId) {
    if (isLoading) return;
    isLoading = true;
    try {
        const resp = await fetch(`/notes/api/detail/?id=${noteId}`);
        if (!resp.ok) throw new Error(`Failed to load note: ${resp.status}`);
        const note = await resp.json();

        // title
        if (noteTitleInput) noteTitleInput.value = note.title || '';

        // tags
        const tagList = Array.isArray(note.tags) ? note.tags : [];
        if (tagifyInstance) {
            tagifyInstance.removeAllTags();
            tagifyInstance.addTags(tagList);
        } else if (noteTagsInput) {
            noteTagsInput.value = tagList.join(', ');
        }

        // content
        if (editorInstance) {
            editorInstance.setData(note.content || '');
        }

    } catch (err) {
        console.error('[NoteEditor] loadNoteForEdit error:', err);
        if (window.notyf) window.notyf.error('노트 불러오기에 실패했습니다.');
    } finally {
        isLoading = false;
    }
}

// Handle cancel note
function handleCancelNote() {
    const editorContent = editorInstance ? editorInstance.getData().trim() : '';
    const hasTags = tagifyInstance ? tagifyInstance.value.length > 0 : (noteTagsInput && noteTagsInput.value.trim());
    const hasContent =
        (noteTitleInput && noteTitleInput.value.trim()) ||
        editorContent ||
        hasTags ||
        attachedFiles.length > 0;

    if (hasContent) {
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
            if (confirm('작성 중인 내용이 저장되지 않습니다. 정말 취소하시겠습니까?')) {
                window.location.href = '/notes/';
            }
        }
    } else {
        window.location.href = '/notes/';
    }
}

// Handle save note (create or update)
async function handleSaveNote() {
    if (isSaving) return;
    const title = noteTitleInput?.value.trim() || '';
    const content = editorInstance ? editorInstance.getData().trim() : '';

    // tags
    let tags = [];
    if (tagifyInstance) {
        tags = tagifyInstance.value.map(tag => tag.value);
    } else {
        const tagsStr = noteTagsInput?.value.trim() || '';
        tags = tagsStr.split(',').map(t => t.trim()).filter(t => t.length > 0).slice(0, 5);
    }

    if (!title) {
        if (window.notyf) window.notyf.error('제목을 입력해주세요.');
        else alert('제목을 입력해주세요.');
        if (noteTitleInput) noteTitleInput.focus();
        return;
    }

    const noteData = {
        title: title,
        content: content,
        tags: tags,
        attachedFiles: attachedFiles
    };

    const isUpdate = isEditMode && editingNoteId;
    const url = isUpdate ? '/notes/api/update/' : '/notes/api/create/';
    const method = isUpdate ? 'POST' : 'POST'; // 백엔드가 PUT/PATCH이면 변경
    if (isUpdate) noteData.id = editingNoteId;

    try {
        isSaving = true;
        const response = await fetch(url, {
            method,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
            },
            body: JSON.stringify(noteData)
        });

        if (!response.ok) throw new Error('Failed to save note');

        const result = await response.json();
        console.log('Note saved:', result);

        if (window.notyf) {
            window.notyf.success(isUpdate ? '노트가 수정되었습니다.' : '노트가 저장되었습니다.');
        }

        setTimeout(() => {
            if (isUpdate) {
                window.location.href = `/notes/detail/?id=${editingNoteId}`;
            } else {
                window.location.href = '/notes/?refresh=true';
            }
        }, 600);
    } catch (error) {
        console.error('Error saving note:', error);
        if (window.notyf) window.notyf.error('노트 저장에 실패했습니다.');
        else alert('노트 저장에 실패했습니다.');
    } finally {
        isSaving = false;
    }
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

    if (bookmarkSidebar) {
        if (isBookmarkSidebarOpen) bookmarkSidebar.classList.remove('hidden');
        else bookmarkSidebar.classList.add('hidden');
    }

    if (btnBookmarkToggle) {
        if (isBookmarkSidebarOpen) btnBookmarkToggle.classList.add('active');
        else btnBookmarkToggle.classList.remove('active');
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
            insertChartToEditor(chartData);
        });
    } else {
        if (window.notyf) window.notyf.error('그래프 생성 모달을 로드할 수 없습니다.');
        console.error('[NoteEditor] GraphCreateModal not available');
    }
}

// Insert chart to CKEditor
function insertChartToEditor(chartData) {
    if (!editorInstance) {
        if (window.notyf) window.notyf.error('에디터가 초기화되지 않았습니다.');
        return;
    }

    const chartHtml = `
        <figure class="chart-figure">
            <img src="${chartData.imageDataUrl}" alt="${escapeHtml(chartData.title)}" style="max-width: 100%; height: auto;" />
            <figcaption>${escapeHtml(chartData.title)}</figcaption>
        </figure>
    `;

    const currentContent = editorInstance.getData();
    editorInstance.setData(currentContent + chartHtml);
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

    if (attachedCount) {
        attachedCount.textContent = attachedFiles.length > 0 ? `${attachedFiles.length}개 첨부됨` : '';
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

// Render bookmarks
function renderBookmarks() {
    if (!bookmarkContent) return;

    bookmarkContent.innerHTML = bookmarks.map((category, index) => `
        <div class="bookmark-category">
            <button class="bookmark-category-header" onclick="window.NoteEditorPage.toggleBookmarkCategory(${index})">
                <i class="fas ${openBookmarkCategories[index] ? 'fa-chevron-down' : 'fa-chevron-right'}"></i>
                <i class="fas fa-folder"></i>
                <span class="bookmark-category-title">${escapeHtml(category.category)}</span>
                <span class="bookmark-category-count">(${category.items.length})</span>
            </button>
            ${openBookmarkCategories[index] ? `
                <div class="bookmark-items">
                    ${category.items.map(item => `
                        <div class="bookmark-item">
                            <div class="bookmark-item-header">
                                <i class="fas fa-file-alt"></i>
                                <span class="bookmark-item-title">${escapeHtml(item.title)}</span>
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
        if (window.notyf) window.notyf.error('에디터가 초기화되지 않았습니다.');
        return;
    }

    const currentContent = editorInstance.getData();
    const referenceHtml = `<p><strong>📌 참고 자료:</strong> <a href="${url}" target="_blank" rel="noopener noreferrer">${escapeHtml(title)}</a></p>`;
    editorInstance.setData(currentContent + referenceHtml);
    editorInstance.focus();

    if (window.notyf) window.notyf.success('북마크가 노트에 추가되었습니다.');
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNoteEditor);
} else {
    initNoteEditor();
}

// Export to window
window.NoteEditorPage = {
    handleFileRemove,
    toggleBookmarkCategory,
    addBookmarkToNote,
};