// django_app/static/js/pages/note_detail.js

// =====================
// State variables
// =====================
let selectedNoteId = null;
let isCommentSidebarOpen = true;
let selectedText = '';
let commentPosition = null;
let showCommentInput = false;
let activeCommentId = null;
let btnAddComment;

// =====================
// DOM Elements
// =====================
let noteDetailView;
let btnBack, noteDetailTitle, noteDetailAuthor, noteDetailDate, noteDetailTags;
let btnShareDetail, btnCommentToggle, btnAttachmentsScroll, btnEditNote;
let noteContentBox, noteContentText, noteAttachmentsSection, attachmentsList;
let commentSidebar, commentSidebarContent, btnCloseCommentSidebar;
let newCommentBox, selectedTextPreview, newCommentTextarea;
let btnCommentSubmit, btnCommentCancel, commentsList, commentsEmpty;

// =====================
// Comment state (서버 기준)
// =====================
let comments = [];

// =====================
// Initialize
// =====================
function initNoteDetail() {
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

    if (btnBack) btnBack.addEventListener('click', handleBackToList);
    if (btnCommentToggle) btnCommentToggle.addEventListener('click', () => handleToggleCommentSidebar());
    if (btnCloseCommentSidebar) btnCloseCommentSidebar.addEventListener('click', () => handleToggleCommentSidebar(false));
    if (btnAddComment) btnAddComment.addEventListener('click', handleAddCommentClick);
    if (btnCommentSubmit) btnCommentSubmit.addEventListener('click', handleAddComment);
    if (btnCommentCancel) btnCommentCancel.addEventListener('click', handleCancelComment);
    if (btnEditNote) btnEditNote.addEventListener('click', handleEditNote);
    if (noteContentBox) noteContentBox.addEventListener('mouseup', handleTextSelection);

    const urlParams = new URLSearchParams(window.location.search);
    selectedNoteId = parseInt(urlParams.get('id')) || window.noteId;

    loadNoteDetail(selectedNoteId);
}

// =====================
// Load note detail
// =====================
async function loadNoteDetail(noteId) {
    const response = await fetch(`/notes/api/detail/?id=${noteId}`);
    const note = await response.json();
    renderNoteDetail(note);
    await loadComments(noteId);
    handleToggleCommentSidebar(true);
}

// =====================
// Load comments (최신순)
// =====================
async function loadComments(noteId) {
    const response = await fetch(`/notes/api/comments/?note_id=${noteId}`);
    const data = await response.json();

    comments = (data.comments || []).map(comment => ({
        id: comment.id,
        highlightedText: comment.highlighted_text,
        comment: comment.comment_text,
        author: comment.author,
        avatar: 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=100&h=100&fit=crop',
        time: comment.created_at,
        position: comment.position_top,
    }));

    renderComments();
    updateCommentCount();
}

// =====================
// Add comment
// =====================
function handleAddComment() {
    const commentText = newCommentTextarea.value.trim();
    const highlighted = selectedText.trim();

    if (!commentText) {
        alert('댓글 내용을 입력해주세요.');
        newCommentTextarea.focus();
        return;
    }

    if (!highlighted) {
        alert('하이라이트된 텍스트가 없습니다. 텍스트를 선택한 후 댓글을 작성해주세요.');
        return;
    }

    btnCommentSubmit.disabled = true;

    fetch('/notes/api/add_comment/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken(),
        },
        body: JSON.stringify({
            note_id: selectedNoteId,
            highlighted_text: highlighted,
            comment_text: commentText,
            position_top: commentPosition ? commentPosition.top : 0,
        }),
    })
        .then(response => response.json())
        .then(data => {
            btnCommentSubmit.disabled = false;

            if (data.status === 'created') {
                newCommentBox.style.display = 'none';
                newCommentTextarea.value = '';
                selectedText = '';
                selectedTextPreview.textContent = '';
                window.getSelection().removeAllRanges();

                loadComments(selectedNoteId);
            } else {
                alert(data.error || '댓글 등록에 실패했습니다.');
            }
        })
        .catch(err => {
            btnCommentSubmit.disabled = false;
            console.error(err);
            alert('오류가 발생했습니다.');
        });
}

// =====================
// Render helpers
// =====================
function renderNoteDetail(note) {
    noteDetailTitle.textContent = note.title;
    noteDetailAuthor.textContent = note.author;
    noteDetailDate.textContent = note.date;
    noteContentText.innerHTML = note.content || '';
}

function renderComments() {
    if (comments.length === 0 && !showCommentInput) {
        commentsList.innerHTML = '';
        commentsEmpty.style.display = 'block';
        return;
    }

    commentsEmpty.style.display = 'none';
    commentsList.innerHTML = comments.map(c => `
        <div class="comment-item">
            ${c.highlightedText ? `
                <div class="comment-highlighted-text">
                    "${escapeHtml(c.highlightedText)}"
                </div>` : ''}
            <div class="comment-header">
                <img src="${c.avatar}" class="comment-avatar" />
                <div>
                    <p class="comment-author-name">${escapeHtml(c.author)}</p>
                    <p class="comment-time">${escapeHtml(c.time)}</p>
                </div>
            </div>
            <p class="comment-content">${escapeHtml(c.comment)}</p>
        </div>
    `).join('');

    commentSidebarContent.scrollTop = 0;
}

function updateCommentCount() {
    const el = document.getElementById('commentCount');
    if (el) el.textContent = comments.length;
}

// =====================
// UI handlers
// =====================
function handleAddCommentClick() {
    showCommentInput = true;
    newCommentBox.style.display = 'block';
    newCommentTextarea.focus();
}

function handleCancelComment() {
    showCommentInput = false;
    newCommentBox.style.display = 'none';
    newCommentTextarea.value = '';
    selectedText = '';
    selectedTextPreview.textContent = '';
    window.getSelection().removeAllRanges();
}

function handleToggleCommentSidebar(force) {
    isCommentSidebarOpen = force !== undefined ? force : !isCommentSidebarOpen;
    commentSidebar.classList.toggle('hidden', !isCommentSidebarOpen);
}

function handleBackToList() {
    window.location.href = '/notes/';
}

// 핵심: 텍스트 선택시 선택된 텍스트 업데이트 및 UI 표시
function handleTextSelection() {
    const selection = window.getSelection();
    if (!selection) return;
    const text = selection.toString().trim();

    if (text.length > 0 && noteContentText.contains(selection.anchorNode)) {
        selectedText = text;
        selectedTextPreview.textContent = text;
        newCommentBox.style.display = 'block';
        newCommentTextarea.value = '';
        newCommentTextarea.focus();

        if (commentSidebar.classList.contains('hidden')) {
            handleToggleCommentSidebar(true);
        }
    } else {
        selectedText = '';
        selectedTextPreview.textContent = '';
        newCommentBox.style.display = 'none';
    }
}

function getCSRFToken() {
    const csrfTokenElem = document.querySelector('[name=csrfmiddlewaretoken]');
    return csrfTokenElem ? csrfTokenElem.value : '';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function handleEditNote() {
    // 현재 선택된 노트 ID를 쿼리 파라미터로 넘겨 편집 페이지로 이동
    window.location.href = `/notes/editor/?id=${selectedNoteId}`;
}

// =====================
// Init
// =====================
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNoteDetail);
} else {
    initNoteDetail();
}