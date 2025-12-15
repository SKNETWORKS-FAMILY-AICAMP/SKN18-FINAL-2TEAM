from django.shortcuts import render
from django.contrib.auth.decorators import login_required


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
