/* django_app/static/js/pages/note_detail.js */
// Note Detail Page JavaScript

// State variables
let selectedNoteId = null;
let isCommentSidebarOpen = true;
let selectedText = '';
let commentPosition = null;
let showCommentInput = false;
let activeCommentId = null;

let btnAddComment;

// DOM Elements
let noteDetailView, noteDetailWrapper;
let btnBack, noteDetailTitle, noteDetailAuthor, noteDetailDate, noteDetailTags;
let btnShareDetail, btnCommentToggle, btnAttachmentsScroll, btnEditNote;
let noteContentBox, noteContentText, noteAttachmentsSection, attachmentsList;
let commentSidebar, commentSidebarContent, btnCloseCommentSidebar;
let newCommentBox, selectedTextPreview, newCommentTextarea;
let btnCommentSubmit, btnCommentCancel, commentsList, commentsEmpty;

// Mock comments data
let comments = [];

// Mock attachments for detail view
const mockAttachments = [
    { id: 1, name: 'experiment_protocol_v2.pdf', size: '2.4MB', type: 'PDF' },
    { id: 2, name: 'data_analysis_results.xlsx', size: '1.8MB', type: 'Excel' },
    { id: 3, name: 'sample_images.zip', size: '15.2MB', type: 'Archive' },
];

// Mock note data (실제로는 API에서 가져옴)
const mockNoteData = {
    id: 1,
    title: 'CRISPR-Cas9 유전자 가위 기술을 활용한 유전자 편집 실험 결과 분석',
    date: '2025-11-30',
    author: 'Dr. Sarah Kim',
    content: `Eukaryotic cell(진핵세포)는 분명한 막으로 둘러싸인 핵과 다양한 세포 소기관을 지니는 진핵생물을 구성하는 기본 단위입니다.

**1. 진핵세포란 무엇인가?**

핵심 정의:
진핵세포는 유전물질(DNA)이 핵막으로 둘러싸인 '핵' 내에 저장되어 있는 세포입니다.

**2. 주요 구조적 특징**

핵(Nucleus):
이중막(핵막)으로 둘러싸여 있으며, 유전정보(염색체)가 저장 및 관리됩니다.`,
    shared: 3,
    comments: 5,
    tags: ['CRISPR', '유전자편집'],
};

// Initialize
function initNoteDetail() {
    // Get DOM elements
    noteDetailView = document.getElementById('noteDetailView');
    btnBack = document.getElementById('btnBack');
    noteDetailTitle = document.getElementById('noteDetailTitle');
    noteDetailAuthor = document.getElementById('noteDetailAuthor');
    noteDetailDate = document.getElementById('noteDetailDate');
    noteDetailTags = document.getElementById('noteDetailTags');
    btnShareDetail = document.getElementById('btnShareDetail');
    btnCommentToggle = document.getElementById('btnCommentToggle');
    btnAttachmentsScroll = document.getElementById('btnAttachmentsScroll');
    btnEditNote = document.getElementById('btnEditNote');
    noteContentBox = document.getElementById('noteContentBox');
    noteContentText = document.getElementById('noteContentText');
    noteAttachmentsSection = document.getElementById('noteAttachmentsSection');
    attachmentsList = document.getElementById('attachmentsList');
    commentSidebar = document.getElementById('commentSidebar');
    commentSidebarContent = document.getElementById('commentSidebarContent');
    btnCloseCommentSidebar = document.getElementById('btnCloseCommentSidebar');
    btnAddComment = document.getElementById('btnAddComment');
    newCommentBox = document.getElementById('newCommentBox');
    selectedTextPreview = document.getElementById('selectedTextPreview');
    newCommentTextarea = document.getElementById('newCommentTextarea');
    btnCommentSubmit = document.getElementById('btnCommentSubmit');
    btnCommentCancel = document.getElementById('btnCommentCancel');
    commentsList = document.getElementById('commentsList');
    commentsEmpty = document.getElementById('commentsEmpty');

    // Attach event listeners
    if (btnBack) btnBack.addEventListener('click', handleBackToList);
    if (btnShareDetail) btnShareDetail.addEventListener('click', handleShareNote);
    if (btnCommentToggle) btnCommentToggle.addEventListener('click', () => handleToggleCommentSidebar());
    if (btnAttachmentsScroll) btnAttachmentsScroll.addEventListener('click', scrollToAttachments);
    if (btnEditNote) btnEditNote.addEventListener('click', handleEditNote);
    if (btnCloseCommentSidebar)
        btnCloseCommentSidebar.addEventListener('click', () => handleToggleCommentSidebar(false));
    if (btnAddComment) btnAddComment.addEventListener('click', handleAddCommentClick);
    if (btnCommentSubmit) btnCommentSubmit.addEventListener('click', handleAddComment);
    if (btnCommentCancel) btnCommentCancel.addEventListener('click', handleCancelComment);
    if (noteContentBox) noteContentBox.addEventListener('mouseup', handleTextSelection);
    if (noteContentText) noteContentText.addEventListener('click', handleInlineCommentClick);

    // Get note ID from URL or window variable
    const urlParams = new URLSearchParams(window.location.search);
    selectedNoteId = parseInt(urlParams.get('id')) || window.noteId || 1;

    console.log('Selected note ID:', selectedNoteId);

    // Load note data
    loadNoteDetail(selectedNoteId);
}

// Load note detail
async function loadNoteDetail(noteId) {
    console.log('Loading note detail for ID:', noteId);
    try {
        const response = await fetch(`/notes/api/detail/?id=${noteId}`);
        console.log('API response status:', response.status);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const note = await response.json();
        console.log('Loaded note data:', note);

        renderNoteDetail(note);
        renderAttachmentsDetail(mockAttachments); // TODO: 실제 첨부파일 API 추가
        await loadComments(noteId);

        // Open comment sidebar by default
        handleToggleCommentSidebar(true);
    } catch (error) {
        console.error('Failed to load note:', error);
        // 에러 시 빈 상태 표시 또는 에러 메시지
        if (window.notyf) {
            window.notyf.error('노트를 불러오는데 실패했습니다.');
        }
        // 에러 메시지를 페이지에 표시
        const noteContentText = document.getElementById('noteContentText');
        if (noteContentText) {
            noteContentText.textContent = '노트를 불러오는데 실패했습니다. 다시 시도해주세요.';
        }
    }
}

// Load comments for the note
async function loadComments(noteId) {
    console.log('Loading comments for note ID:', noteId);
    try {
        const response = await fetch(`/notes/api/comments/?note_id=${noteId}`);
        console.log('Comments API response status:', response.status);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        console.log('Loaded comments data:', data);
        comments = (data.comments || []).map((comment) => ({
            id: comment.id,
            highlightedText: comment.highlighted_text,
            comment: comment.comment_text,
            author: comment.author,
            avatar: 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=100&h=100&fit=crop', // 기본 아바타
            time: comment.created_at,
            position: comment.position_top,
        }));
        console.log('Processed comments:', comments);
        renderComments();
        updateCommentCount();
    } catch (error) {
        console.error('Failed to load comments:', error);
        comments = [];
        renderComments();
    }
}

// Update comment count in UI
function updateCommentCount() {
    const commentCountEl = document.getElementById('commentCount');
    if (commentCountEl) {
        commentCountEl.textContent = comments.length;
    }
}

// Get CSRF token
function getCSRFToken() {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
    return csrfToken ? csrfToken.value : '';
}

// Render note detail
function renderNoteDetail(note) {
    if (!note) return;

    console.log('Rendering note:', note);
    console.log('Note content:', note.content);

    if (noteDetailTitle) noteDetailTitle.textContent = note.title;
    if (noteDetailDate) noteDetailDate.textContent = note.date;
    if (noteDetailAuthor) noteDetailAuthor.textContent = note.author;

    if (noteContentText) {
        console.log('Setting innerHTML:', note.content);
        noteContentText.innerHTML = note.content || '';
        console.log('innerHTML set to:', noteContentText.innerHTML);
    }

    // Render tags
    if (noteDetailTags) {
        noteDetailTags.innerHTML = note.tags
            .map((tag) => `<span class="meta-tag">${escapeHtml(tag)}</span>`)
            .join('');
    }

    // Update counts
    const shareCountEl = document.getElementById('shareCount');
    if (shareCountEl) shareCountEl.textContent = note.shared;

    const commentCountEl = document.getElementById('commentCount');
    if (commentCountEl) commentCountEl.textContent = comments.length;

    const attachmentCountEl = document.getElementById('attachmentCount');
    if (attachmentCountEl) attachmentCountEl.textContent = mockAttachments.length;
}

// Render attachments detail
function renderAttachmentsDetail(attachments) {
    if (!attachmentsList) return;

    if (attachments.length === 0) {
        attachmentsList.innerHTML = '';
        if (document.getElementById('attachmentsCount')) {
            document.getElementById('attachmentsCount').textContent = '0';
        }
        return;
    }

    attachmentsList.innerHTML = attachments
        .map(
            (file) => `
        <div class="attachment-item">
            <i class="fas fa-file-alt"></i>
            <div class="attachment-info">
                <span class="attachment-name">${escapeHtml(file.name)}</span>
                <span class="attachment-meta">${file.size} • ${file.type}</span>
            </div>
            <button class="btn-attachment-download" onclick="window.NoteDetailPage.handleDownloadAttachment(${file.id})">
                다운로드
            </button>
        </div>
    `,
        )
        .join('');

    if (document.getElementById('attachmentsCount')) {
        document.getElementById('attachmentsCount').textContent = attachments.length;
    }
}

// Handle back to list
function handleBackToList() {
    window.location.href = '/notes/';
}

// Handle share note
function handleShareNote() {
    if (window.ShareModal && typeof window.ShareModal.open === 'function') {
        window.ShareModal.onShare = (selectedMembers) => {
            if (window.notyf) {
                window.notyf.success(`${selectedMembers.length}명과 공유되었습니다.`);
            }
        };
        window.ShareModal.open(selectedNoteId);
    } else {
        if (window.notyf) {
            window.notyf.info('공유 기능은 곧 제공될 예정입니다.');
        }
    }
}

// Handle toggle comment sidebar
function handleToggleCommentSidebar(forceValue) {
    if (forceValue !== undefined) {
        isCommentSidebarOpen = forceValue;
    } else {
        isCommentSidebarOpen = !isCommentSidebarOpen;
    }

    if (commentSidebar) {
        if (isCommentSidebarOpen) {
            commentSidebar.classList.remove('hidden');
        } else {
            commentSidebar.classList.add('hidden');
        }
    }

    if (btnCommentToggle) {
        if (isCommentSidebarOpen) {
            btnCommentToggle.classList.add('active');
        } else {
            btnCommentToggle.classList.remove('active');
        }
    }
}

// Scroll to attachments
function scrollToAttachments() {
    if (noteAttachmentsSection) {
        noteAttachmentsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

// Handle edit note
function handleEditNote() {
    window.location.href = `/notes/editor/?id=${selectedNoteId}`;
}

// Handle add comment button click
function handleAddCommentClick() {
    console.log('Add comment button clicked');
    selectedText = '';
    commentPosition = null;
    showCommentInput = true;

    if (newCommentBox) {
        newCommentBox.style.display = 'block';
        if (selectedTextPreview) {
            selectedTextPreview.textContent = '';
        }
        if (newCommentTextarea) {
            newCommentTextarea.placeholder = '댓글 작성...';
            setTimeout(() => newCommentTextarea.focus(), 100);
        }
    }

    // 댓글 입력창을 바로 보이게 하고 빈 상태 문구를 숨김
    renderComments();
    handleToggleCommentSidebar(true);
}

// Handle text selection
function handleTextSelection(e) {
    const selection = window.getSelection();
    const text = selection ? selection.toString().trim() : '';

    if (text && text.length > 0) {
        const range = selection ? selection.getRangeAt(0) : null;
        const rect = range ? range.getBoundingClientRect() : null;
        const containerRect = noteContentBox ? noteContentBox.getBoundingClientRect() : null;

        if (rect && containerRect) {
            selectedText = text;
            commentPosition = { top: rect.top - containerRect.top };
            showCommentInput = true;

            if (newCommentBox) {
                newCommentBox.style.display = 'block';
                const previewText = text.length > 50 ? text.substring(0, 50) + '...' : text;
                if (selectedTextPreview) {
                    selectedTextPreview.textContent = `"${previewText}"`;
                }
                if (newCommentTextarea) {
                    newCommentTextarea.placeholder = '선택한 텍스트에 대한 댓글 작성...';
                    setTimeout(() => newCommentTextarea.focus(), 100);
                }
            }
        }
    }
}

// Handle inline comment trigger inside content
function handleInlineCommentClick(e) {
    const trigger = e.target.closest('[data-open-comments]');
    if (!trigger) return;

    e.preventDefault();
    handleToggleCommentSidebar(true);

    const commentId = trigger.getAttribute('data-comment-id');
    if (commentId) {
        setActiveComment(parseInt(commentId, 10));
    }

    if (btnAddComment) {
        btnAddComment.focus();
    }
}

// Handle add comment
function handleAddComment() {
    const commentText = newCommentTextarea ? newCommentTextarea.value.trim() : '';

    if (!commentText) {
        if (window.notyf) {
            window.notyf.error('댓글을 입력해주세요.');
        }
        return;
    }

    console.log('Adding comment for note ID:', selectedNoteId);

    // Prepare data
    const commentData = {
        note_id: selectedNoteId,
        highlighted_text: selectedText || '',
        comment_text: commentText,
        position_top: commentPosition ? commentPosition.top : 0,
    };

    console.log('Comment data:', commentData);

    // Send to API
    fetch('/notes/api/add_comment/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken(),
        },
        body: JSON.stringify(commentData),
    })
        .then((response) => {
            console.log('API response status:', response.status);
            return response.json();
        })
        .then((data) => {
            console.log('API response data:', data);
            if (data.error) {
                throw new Error(data.error);
            }

            // Add to local comments array
            const newComment = {
                id: data.id,
                highlightedText: data.highlighted_text,
                comment: data.comment_text,
                author: data.author,
                time: '방금 전',
                position: data.position_top,
            };
            comments.push(newComment);

            // Reset form
            selectedText = '';
            commentPosition = null;
            showCommentInput = false;
            if (newCommentTextarea) newCommentTextarea.value = '';
            if (newCommentBox) newCommentBox.style.display = 'none';

            // Update UI
            renderComments();
            updateCommentCount();

            if (window.notyf) {
                window.notyf.success('댓글이 추가되었습니다.');
            }
        })
        .catch((error) => {
            console.error('Failed to add comment:', error);
            if (window.notyf) {
                window.notyf.error('댓글 추가에 실패했습니다.');
            }
        });
}

// Handle cancel comment
function handleCancelComment() {
    selectedText = '';
    commentPosition = null;
    showCommentInput = false;

    if (newCommentTextarea) newCommentTextarea.value = '';
    if (newCommentBox) newCommentBox.style.display = 'none';
}

// Render comments
function renderComments() {
    console.log('Rendering comments:', comments);
    if (!commentsList || !commentsEmpty) return;

    if (newCommentBox) {
        if (showCommentInput) {
            newCommentBox.style.display = 'block';
        } else {
            newCommentBox.style.display = 'none';
        }
    }

    if (comments.length === 0 && !showCommentInput) {
        commentsList.innerHTML = '';
        if (commentsEmpty) commentsEmpty.style.display = 'block';
        return;
    }

    if (commentsEmpty) commentsEmpty.style.display = 'none';
    commentsList.innerHTML = comments
        .map(
            (comment) => `
        <div class="comment-item ${activeCommentId === comment.id ? 'active' : ''}" 
             onclick="window.NoteDetailPage.setActiveComment(${comment.id})">
            ${comment.highlightedText ? `<div class="comment-highlighted-text">"${escapeHtml(comment.highlightedText)}"</div>` : ''}
            <div class="comment-header">
                <img src="${escapeHtml(comment.avatar)}" alt="${escapeHtml(comment.author)}" class="comment-avatar" />
                <div class="comment-author-info">
                    <p class="comment-author-name">${escapeHtml(comment.author)}</p>
                    <p class="comment-time">${escapeHtml(comment.time)}</p>
                </div>
            </div>
            <p class="comment-content">${escapeHtml(comment.comment)}</p>
            <div class="comment-actions-bar">
                <button class="comment-action-link">답장</button>
                <button class="comment-action-link">수정</button>
                <button class="comment-action-link delete">삭제</button>
            </div>
        </div>
    `,
        )
        .join('');
}

// Set active comment
function setActiveComment(commentId) {
    activeCommentId = commentId;
    renderComments();
}

// Handle download attachment
function handleDownloadAttachment(fileId) {
    const file = mockAttachments.find((f) => f.id === fileId);
    if (!file) return;

    if (window.notyf) {
        window.notyf.info(`파일 다운로드: ${file.name}`);
    }
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNoteDetail);
} else {
    initNoteDetail();
}

// Export to window
window.NoteDetailPage = {
    setActiveComment,
    handleDownloadAttachment,
};