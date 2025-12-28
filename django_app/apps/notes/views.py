from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Count

from .models import Note


@login_required
def index(request):
    """Notes list page view (인증 필수)."""
    context = {
        # 필요한 컨텍스트 데이터 추가
    }
    return render(request, 'note/notes.html', context)


@login_required
def note_detail(request):
    """Note detail page view (인증 필수)."""
    note_id = request.GET.get('id')
    context = {
        'note_id': note_id,
    }
    return render(request, 'note/note_detail.html', context)


@login_required
def note_editor(request):
    """Note editor page view (create/edit) (인증 필수)."""
    note_id = request.GET.get('id')  # None이면 새 노트 생성, 있으면 수정
    context = {
        'note_id': note_id,
        'is_edit_mode': note_id is not None,
    }
    return render(request, 'note/note_editor.html', context)


@login_required
@require_GET
def notes_list_api(request):
    """노트 목록을 JSON으로 반환."""
    user_identifier = str(request.user.user_id) if hasattr(request.user, 'user_id') else str(request.user.pk)
    
    notes_qs = (
        Note.objects.filter(created_id=user_identifier)
        .annotate(
            shared_count=Count('shares', distinct=True),
            comment_count=Count('comments', distinct=True),
        )
        .prefetch_related('tags')
        .order_by('-created_at')
    )
    
    results = []
    for note in notes_qs:
        tags = [tag.tag_name for tag in note.tags.all()]
        results.append({
            'id': note.note_sid,
            'title': note.title,
            'content': note.content or '',
            'date': note.created_at.strftime('%Y-%m-%d') if note.created_at else '',
            'shared': note.shared_count or 0,
            'comments': note.comment_count or 0,
            'tags': tags,
        })
    
    return JsonResponse({
        'status': 'success',
        'results': results,
    })
