// Note Detail Page JavaScript

// State variables
let selectedNoteId = null;
let isCommentSidebarOpen = true;
let selectedText = "";
let commentPosition = null;
let showCommentInput = false;
let activeCommentId = null;
let editingCommentId = null;  // 수정 중인 댓글 ID

// DOM Elements
let noteDetailView, noteDetailWrapper;
let btnBack, noteDetailTitle, noteDetailAuthor, noteDetailDate, noteDetailTags;
let btnShareDetail, btnCommentToggle, btnAttachmentsScroll, btnEditNote, btnDeleteNote;
let noteContentBox, noteContentText, noteAttachmentsSection, attachmentsList;
let commentSidebar, commentSidebarContent, btnCloseCommentSidebar;
let newCommentBox, selectedTextPreview, newCommentTextarea;
let btnCommentSubmit, btnCommentCancel, commentsList, commentsEmpty;

// Note data state
let noteData = null;
let comments = [];
let attachments = [];
let isLoadingNote = false;

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
    btnDeleteNote = document.getElementById('btnDeleteNote');
    noteContentBox = document.getElementById('noteContentBox');
    noteContentText = document.getElementById('noteContentText');
    noteAttachmentsSection = document.getElementById('noteAttachmentsSection');
    attachmentsList = document.getElementById('attachmentsList');
    commentSidebar = document.getElementById('commentSidebar');
    commentSidebarContent = document.getElementById('commentSidebarContent');
    btnCloseCommentSidebar = document.getElementById('btnCloseCommentSidebar');
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
    if (btnDeleteNote) btnDeleteNote.addEventListener('click', handleDeleteNote);
    if (btnCloseCommentSidebar) btnCloseCommentSidebar.addEventListener('click', () => handleToggleCommentSidebar(false));
    if (btnCommentSubmit) btnCommentSubmit.addEventListener('click', handleAddComment);
    if (btnCommentCancel) btnCommentCancel.addEventListener('click', handleCancelComment);
    if (noteContentBox) noteContentBox.addEventListener('mouseup', handleTextSelection);

    // Get note ID from URL
    const urlParams = new URLSearchParams(window.location.search);
    selectedNoteId = urlParams.get('id') || 1;

    // Load note data
    loadNoteDetail(selectedNoteId);
}

// Load note detail from API
async function loadNoteDetail(noteId) {
    if (isLoadingNote) return;
    if (!noteId) {
        console.error('[NoteDetail] Note ID is required');
        if (window.notyf) {
            window.notyf.error('노트 ID가 필요합니다.');
        }
        return;
    }
    
    isLoadingNote = true;
    
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
            noteData = data.note;
            comments = data.note.comments_list || [];
            attachments = data.note.attachments || [];
            
            renderNoteDetail(noteData);
            renderAttachmentsDetail(attachments);
            renderComments();
            
            // Open comment sidebar by default
            handleToggleCommentSidebar(true);
        } else {
            throw new Error(data.error || '노트 데이터를 불러올 수 없습니다.');
        }
    } catch (error) {
        console.error('[NoteDetail] Error loading note:', error);
        if (window.notyf) {
            window.notyf.error(error.message || '노트를 불러오는 중 오류가 발생했습니다.');
        }
        
        // 에러 발생 시 목록으로 돌아가기
        setTimeout(() => {
            window.location.href = '/notes/';
        }, 2000);
    } finally {
        isLoadingNote = false;
    }
}

// Render note detail
function renderNoteDetail(note) {
    if (!note) return;
    
    if (noteDetailTitle) noteDetailTitle.textContent = note.title || '제목 없음';
    if (noteDetailDate) noteDetailDate.textContent = note.date || '';
    if (noteDetailAuthor) noteDetailAuthor.textContent = note.author || '';
    
    // Content는 HTML이므로 innerHTML 사용 (CKEditor에서 생성된 HTML)
    if (noteContentText) {
        noteContentText.innerHTML = note.content || '';
    }
    
    // Render tags
    if (noteDetailTags) {
        const tags = note.tags || [];
        noteDetailTags.innerHTML = tags.map(tag => 
            `<span class="meta-tag">${escapeHtml(tag)}</span>`
        ).join('');
    }

    // Update counts
    const shareCountEl = document.getElementById('shareCount');
    if (shareCountEl) shareCountEl.textContent = note.shared || 0;
    
    const commentCountEl = document.getElementById('commentCount');
    if (commentCountEl) commentCountEl.textContent = note.comments || 0;
    
    const attachmentCountEl = document.getElementById('attachmentCount');
    if (attachmentCountEl) attachmentCountEl.textContent = attachments.length || 0;
    
    // 공유된 노트인 경우 수정/삭제 버튼 숨기기
    const isShared = note.is_shared || false;
    if (isShared) {
        // 수정 버튼 숨기기
        if (btnEditNote) {
            btnEditNote.style.display = 'none';
        }
        // 삭제 버튼 숨기기
        if (btnDeleteNote) {
            const deleteSection = btnDeleteNote.closest('.note-delete-section');
            if (deleteSection) {
                deleteSection.style.display = 'none';
            }
        }
        // 공유 버튼 숨기기 (공유받은 노트는 공유할 수 없음)
        if (btnShareDetail) {
            btnShareDetail.style.display = 'none';
        }
    } else {
        // 내 노트인 경우 모든 버튼 표시
        if (btnEditNote) {
            btnEditNote.style.display = '';
        }
        if (btnDeleteNote) {
            const deleteSection = btnDeleteNote.closest('.note-delete-section');
            if (deleteSection) {
                deleteSection.style.display = '';
            }
        }
        if (btnShareDetail) {
            btnShareDetail.style.display = '';
        }
    }
}

// Format file size
function formatFileSize(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

// Get file type from filename
function getFileType(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const typeMap = {
        'pdf': 'PDF',
        'doc': 'Word', 'docx': 'Word',
        'xls': 'Excel', 'xlsx': 'Excel',
        'ppt': 'PowerPoint', 'pptx': 'PowerPoint',
        'zip': 'Archive', 'rar': 'Archive', '7z': 'Archive',
        'jpg': 'Image', 'jpeg': 'Image', 'png': 'Image', 'gif': 'Image',
        'txt': 'Text',
        'csv': 'CSV'
    };
    return typeMap[ext] || ext.toUpperCase();
}

// Render attachments detail
function renderAttachmentsDetail(attachmentsData) {
    if (!attachmentsList) return;

    if (!attachmentsData || attachmentsData.length === 0) {
        attachmentsList.innerHTML = '';
        if (document.getElementById('attachmentsCount')) {
            document.getElementById('attachmentsCount').textContent = '0';
        }
        return;
    }

    attachmentsList.innerHTML = attachmentsData.map(file => {
        const fileSize = formatFileSize(file.size || 0);
        const fileType = file.type || getFileType(file.name || '');
        return `
        <div class="attachment-item">
            <i class="fas fa-file-alt"></i>
            <div class="attachment-info">
                <span class="attachment-name">${escapeHtml(file.name || '')}</span>
                <span class="attachment-meta">${fileSize} • ${fileType}</span>
            </div>
            <button class="btn-attachment-download" onclick="window.NoteDetailPage.handleDownloadAttachment(${file.id}, '${escapeHtml(file.path || '')}')">
                다운로드
            </button>
        </div>
        `;
    }).join('');

    if (document.getElementById('attachmentsCount')) {
        document.getElementById('attachmentsCount').textContent = attachmentsData.length;
    }
}

// Handle back to list
function handleBackToList() {
    window.location.href = '/notes/';
}

// Handle share note
function handleShareNote() {
    console.log('[NoteDetail] handleShareNote called');
    console.log('[NoteDetail] selectedNoteId:', selectedNoteId);
    console.log('[NoteDetail] ShareModal available:', window.ShareModal && typeof window.ShareModal.open === 'function');
    console.log('[NoteDetail] window.ShareModal:', window.ShareModal);
    
    // ShareModal이 로드될 때까지 대기
    function waitForShareModal(callback, maxAttempts = 20) {
        if (window.ShareModal && typeof window.ShareModal.open === 'function') {
            console.log('[NoteDetail] ShareModal is ready');
            callback();
        } else if (maxAttempts > 0) {
            console.log('[NoteDetail] Waiting for ShareModal to load...', maxAttempts);
            setTimeout(() => waitForShareModal(callback, maxAttempts - 1), 100);
        } else {
            console.error('[NoteDetail] ShareModal not available after waiting');
            console.error('[NoteDetail] window.ShareModal:', window.ShareModal);
            if (window.notyf && typeof window.notyf.error === 'function') {
                window.notyf.error('공유 기능을 불러오는 중입니다. 잠시 후 다시 시도해주세요.');
            } else {
                alert('공유 기능을 불러오는 중입니다. 잠시 후 다시 시도해주세요.');
            }
        }
    }
    
    waitForShareModal(() => {
        window.ShareModal.onShare = (selectedMemberIds, selectedMemberDetails) => {
            console.log('[NoteDetail] onShare callback called');
            console.log('[NoteDetail] selectedMemberIds:', selectedMemberIds);
            console.log('[NoteDetail] selectedMemberDetails:', selectedMemberDetails);
            // 공유 후 노트 다시 로드 (공유 수 업데이트)
            console.log('[NoteDetail] Reloading note detail');
            loadNoteDetail(selectedNoteId);
        };
        // context를 'detail'로 전달하여 바로 공유 API 호출하도록 설정
        console.log('[NoteDetail] Opening share modal with context: detail');
        window.ShareModal.open(selectedNoteId, null, null, '노트 공유', 'detail');
    });
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

// Handle delete note
function handleDeleteNote() {
    if (!selectedNoteId) {
        if (window.notyf) {
            window.notyf.error('노트 ID가 없습니다.');
        }
        return;
    }

    // SweetAlert2를 사용한 확인 다이얼로그
    if (window.Swal) {
        window.Swal.fire({
            title: '노트 삭제',
            html: `"<strong>${escapeHtml(noteData?.title || '이 노트')}</strong>"를 삭제하시겠습니까?<br><br>삭제된 노트는 복구할 수 없습니다.`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#dc2626',
            cancelButtonColor: '#6b7280',
            confirmButtonText: '삭제하기',
            cancelButtonText: '취소',
            reverseButtons: true
        }).then(async (result) => {
            if (result.isConfirmed) {
                await performDeleteNote(selectedNoteId);
            }
        });
    } else {
        // Fallback to confirm if SweetAlert2 is not available
        if (confirm(`"${noteData?.title || '이 노트'}"를 삭제하시겠습니까?\n\n삭제된 노트는 복구할 수 없습니다.`)) {
            performDeleteNote(selectedNoteId);
        }
    }
}

// Perform delete note
async function performDeleteNote(noteId) {
    try {

        const response = await fetch(`/api/notes/${noteId}/delete/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json',
            },
            credentials: 'same-origin'
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || '노트 삭제에 실패했습니다.');
        }

        if (data.status === 'success') {
            if (window.notyf) {
                window.notyf.success('노트가 삭제되었습니다.');
            }

            // 노트 목록으로 이동
            setTimeout(() => {
                window.location.href = '/notes/';
            }, 1000);
        } else {
            throw new Error(data.error || '응답 데이터가 올바르지 않습니다.');
        }
    } catch (error) {
        console.error('[NoteDetail] Failed to delete note:', error);
        if (window.notyf) {
            window.notyf.error(error.message || '노트 삭제에 실패했습니다.');
        } else {
            alert(error.message || '노트 삭제에 실패했습니다.');
        }
    }
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
            }

            handleToggleCommentSidebar(true);

            if (newCommentTextarea) {
                setTimeout(() => newCommentTextarea.focus(), 100);
            }
        }
    }
}

// Get CSRF token
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

// Handle add comment
async function handleAddComment() {
    const commentText = newCommentTextarea ? newCommentTextarea.value.trim() : '';

    if (!commentText) {
        if (window.notyf) {
            window.notyf.error('댓글을 입력해주세요.');
        }
        return;
    }

    if (!selectedNoteId) {
        if (window.notyf) {
            window.notyf.error('노트 ID가 없습니다.');
        }
        return;
    }

    try {
        const requestData = {
            comment_text: commentText,
            highlighted_text: selectedText || '',
            position_top: commentPosition ? commentPosition.top : 0
        };

        const response = await fetch(`/api/notes/${selectedNoteId}/comments/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            credentials: 'same-origin',
            body: JSON.stringify(requestData)
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || '댓글 추가에 실패했습니다.');
        }

        if (data.status === 'success' && data.comment) {
            // 새 댓글을 목록에 추가
            comments.push(data.comment);
            
            // UI 초기화
            selectedText = '';
            commentPosition = null;
            showCommentInput = false;
            if (newCommentTextarea) newCommentTextarea.value = '';
            if (newCommentBox) newCommentBox.style.display = 'none';

            // 댓글 목록 다시 렌더링
            renderComments();
            
            // 댓글 수 업데이트
            if (document.getElementById('commentCount')) {
                document.getElementById('commentCount').textContent = comments.length;
            }

            // 노트 상세 정보 다시 로드 (댓글 수 업데이트)
            await loadNoteDetail(selectedNoteId);

            if (window.notyf) {
                window.notyf.success('댓글이 추가되었습니다.');
            }
        } else {
            throw new Error(data.error || '응답 데이터가 올바르지 않습니다.');
        }
    } catch (error) {
        console.error('[NoteDetail] Failed to add comment:', error);
        if (window.notyf) {
            window.notyf.error(error.message || '댓글 추가에 실패했습니다.');
        } else {
            alert(error.message || '댓글 추가에 실패했습니다.');
        }
    }
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
    commentsList.innerHTML = comments.map(comment => {
        const highlightedText = comment.highlighted_text || comment.highlightedText || '';
        const commentText = comment.comment || comment.comment_text || '';
        const authorName = comment.author || '';
        const avatarUrl = comment.avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(authorName)}&background=random`;
        const timeAgo = comment.time || '';
        const commentId = comment.id || comment.comment_sid;
        const isMine = comment.is_mine === true;  // 본인이 작성한 댓글인지 확인
        const isEditing = editingCommentId === commentId;  // 수정 모드인지 확인
        
        return `
        <div class="comment-item ${activeCommentId === commentId ? 'active' : ''}" 
             onclick="${!isEditing ? `window.NoteDetailPage.setActiveComment(${commentId})` : ''}">
            ${highlightedText ? `<div class="comment-highlighted-text">"${escapeHtml(highlightedText)}"</div>` : ''}
            <div class="comment-header">
                <img src="${escapeHtml(avatarUrl)}" alt="${escapeHtml(authorName)}" class="comment-avatar" />
                <div class="comment-author-info">
                    <p class="comment-author-name">${escapeHtml(authorName)}</p>
                    <p class="comment-time">${escapeHtml(timeAgo)}</p>
                </div>
            </div>
            ${isEditing ? `
                <div class="comment-edit-box">
                    <textarea class="comment-edit-textarea" id="editCommentTextarea_${commentId}" rows="3">${escapeHtml(commentText)}</textarea>
                    <div class="comment-edit-actions">
                        <button class="btn-comment-submit" onclick="event.stopPropagation(); window.NoteDetailPage.handleSaveEditComment(${commentId})">
                            <i class="fa-solid fa-check"></i>
                            <span>저장</span>
                        </button>
                        <button class="btn-comment-cancel" onclick="event.stopPropagation(); window.NoteDetailPage.handleCancelEditComment()">
                            취소
                        </button>
                    </div>
                </div>
            ` : `
                <p class="comment-content">${escapeHtml(commentText)}</p>
                <div class="comment-actions-bar">
                    ${isMine ? `
                        <button class="comment-action-link" onclick="event.stopPropagation(); window.NoteDetailPage.handleEditComment(${commentId})">수정</button>
                        <button class="comment-action-link delete" onclick="event.stopPropagation(); window.NoteDetailPage.handleDeleteComment(${commentId})">삭제</button>
                    ` : ''}
                </div>
            `}
        </div>
        `;
    }).join('');
}

// Set active comment
function setActiveComment(commentId) {
    activeCommentId = commentId;
    renderComments();
}

// Handle edit comment (수정 모드 활성화)
function handleEditComment(commentId) {
    if (!selectedNoteId || !commentId) {
        if (window.notyf) {
            window.notyf.error('댓글 ID가 없습니다.');
        }
        return;
    }

    // 댓글 찾기
    const comment = comments.find(c => (c.id || c.comment_sid) === commentId);
    if (!comment) {
        if (window.notyf) {
            window.notyf.error('댓글을 찾을 수 없습니다.');
        }
        return;
    }

    // 본인이 작성한 댓글인지 확인
    if (!comment.is_mine) {
        if (window.notyf) {
            window.notyf.error('본인이 작성한 댓글만 수정할 수 있습니다.');
        }
        return;
    }

    // 수정 모드 활성화
    editingCommentId = commentId;
    renderComments();

    // textarea에 포커스
    setTimeout(() => {
        const textarea = document.getElementById(`editCommentTextarea_${commentId}`);
        if (textarea) {
            textarea.focus();
            textarea.setSelectionRange(textarea.value.length, textarea.value.length);
        }
    }, 100);
}

// Handle save edit comment (수정 저장)
async function handleSaveEditComment(commentId) {
    if (!selectedNoteId || !commentId) {
        if (window.notyf) {
            window.notyf.error('댓글 ID가 없습니다.');
        }
        return;
    }

    // textarea에서 수정된 텍스트 가져오기
    const textarea = document.getElementById(`editCommentTextarea_${commentId}`);
    if (!textarea) {
        if (window.notyf) {
            window.notyf.error('댓글 입력창을 찾을 수 없습니다.');
        }
        return;
    }

    const newText = textarea.value.trim();

    if (!newText) {
        if (window.notyf) {
            window.notyf.error('댓글 내용을 입력해주세요.');
        }
        return;
    }

    try {
        const response = await fetch(`/api/notes/${selectedNoteId}/comments/${commentId}/`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            credentials: 'same-origin',
            body: JSON.stringify({
                comment_text: newText
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || '댓글 수정에 실패했습니다.');
        }

        if (data.status === 'success' && data.comment) {
            // 댓글 목록에서 해당 댓글 업데이트
            const commentIndex = comments.findIndex(c => (c.id || c.comment_sid) === commentId);
            if (commentIndex !== -1) {
                // is_mine 필드 유지
                data.comment.is_mine = true;
                comments[commentIndex] = data.comment;
            }

            // 수정 모드 해제
            editingCommentId = null;

            // 댓글 목록 다시 렌더링
            renderComments();

            if (window.notyf) {
                window.notyf.success('댓글이 수정되었습니다.');
            }
        } else {
            throw new Error(data.error || '응답 데이터가 올바르지 않습니다.');
        }
    } catch (error) {
        console.error('[NoteDetail] Failed to update comment:', error);
        if (window.notyf) {
            window.notyf.error(error.message || '댓글 수정에 실패했습니다.');
        } else {
            alert(error.message || '댓글 수정에 실패했습니다.');
        }
    }
}

// Handle cancel edit comment (수정 취소)
function handleCancelEditComment() {
    editingCommentId = null;
    renderComments();
}

// Handle delete comment
async function handleDeleteComment(commentId) {
    if (!selectedNoteId || !commentId) {
        if (window.notyf) {
            window.notyf.error('댓글 ID가 없습니다.');
        }
        return;
    }

    // 댓글 찾기
    const comment = comments.find(c => (c.id || c.comment_sid) === commentId);
    if (!comment) {
        if (window.notyf) {
            window.notyf.error('댓글을 찾을 수 없습니다.');
        }
        return;
    }

    // SweetAlert2를 사용한 확인 다이얼로그
    if (window.Swal) {
        window.Swal.fire({
            title: '댓글 삭제',
            html: `댓글을 삭제하시겠습니까?<br><br>삭제된 댓글은 복구할 수 없습니다.`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#dc2626',
            cancelButtonColor: '#6b7280',
            confirmButtonText: '삭제하기',
            cancelButtonText: '취소',
            reverseButtons: true
        }).then(async (result) => {
            if (result.isConfirmed) {
                await performDeleteComment(commentId);
            }
        });
    } else {
        // Fallback to confirm if SweetAlert2 is not available
        if (confirm('댓글을 삭제하시겠습니까?\n\n삭제된 댓글은 복구할 수 없습니다.')) {
            await performDeleteComment(commentId);
        }
    }
}

// Perform delete comment
async function performDeleteComment(commentId) {
    try {
        const response = await fetch(`/api/notes/${selectedNoteId}/comments/${commentId}/delete/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json'
            },
            credentials: 'same-origin'
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || '댓글 삭제에 실패했습니다.');
        }

        if (data.status === 'success') {
            // 댓글 목록에서 해당 댓글 제거
            comments = comments.filter(c => (c.id || c.comment_sid) !== commentId);

            // 댓글 목록 다시 렌더링
            renderComments();

            // 댓글 수 업데이트
            if (document.getElementById('commentCount')) {
                document.getElementById('commentCount').textContent = comments.length;
            }

            // 노트 상세 정보 다시 로드 (댓글 수 업데이트)
            await loadNoteDetail(selectedNoteId);

            if (window.notyf) {
                window.notyf.success('댓글이 삭제되었습니다.');
            }
        } else {
            throw new Error(data.error || '응답 데이터가 올바르지 않습니다.');
        }
    } catch (error) {
        console.error('[NoteDetail] Failed to delete comment:', error);
        if (window.notyf) {
            window.notyf.error(error.message || '댓글 삭제에 실패했습니다.');
        } else {
            alert(error.message || '댓글 삭제에 실패했습니다.');
        }
    }
}

// Handle download attachment
function handleDownloadAttachment(fileId, filePath) {
    if (!filePath) {
        if (window.notyf) {
            window.notyf.error('파일 경로를 찾을 수 없습니다.');
        }
        return;
    }
    
    // S3 파일 다운로드 URL 생성 (백엔드에서 다운로드 엔드포인트 제공 필요)
    // 임시로 파일 경로를 사용
    const downloadUrl = `/api/notes/attachments/${fileId}/download/`;
    
    // 새 창에서 다운로드
    window.open(downloadUrl, '_blank');
    
    if (window.notyf) {
        window.notyf.info('파일 다운로드를 시작합니다.');
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
    handleEditComment,
    handleSaveEditComment,
    handleCancelEditComment,
    handleDeleteComment,
};
