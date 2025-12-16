/* django_app/static/js/pages/note_detail.js */

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
    if (!commentText) return;

    fetch('/notes/api/add_comment/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken(),
        },
        body: JSON.stringify({
            note_id: selectedNoteId,
            highlighted_text: selectedText || '',
            comment_text: commentText,
            position_top: commentPosition ? commentPosition.top : 0,
        }),
    })
        .then(() => loadComments(selectedNoteId))
        .then(() => {
            selectedText = '';
            commentPosition = null;
            showCommentInput = false;
            newCommentTextarea.value = '';
            newCommentBox.style.display = 'none';
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

    // ⭐ 핵심 수정 부분
    // 최신 댓글이 바로 보이도록 스크롤을 맨 위로 이동
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
}

function handleToggleCommentSidebar(force) {
    isCommentSidebarOpen = force !== undefined ? force : !isCommentSidebarOpen;
    commentSidebar.classList.toggle('hidden', !isCommentSidebarOpen);
}

function handleBackToList() {
    window.location.href = '/notes/';
}

function handleTextSelection() {}

function getCSRFToken() {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
    return csrfToken ? csrfToken.value : '';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// =====================
// Init
// =====================
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNoteDetail);
} else {
    initNoteDetail();
}