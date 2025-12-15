from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
from .models import Note
import json

@login_required
def index(request):
    """Notes list page view"""
    return render(request, 'note/notes.html')

@login_required
def api_notes_list(request):
    """API: 노트 리스트 조회"""
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 10))
    search = request.GET.get('search', '')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # 해당 계정의 노트만 조회 (labnote_project 참고)
    notes = Note.objects.filter(owner=request.user, status='E')
    
    # 검색 필터
    if search:
        notes = notes.filter(title__icontains=search)
    
    # 날짜 필터
    if date_from:
        notes = notes.filter(created_at__date__gte=date_from)
    if date_to:
        notes = notes.filter(created_at__date__lte=date_to)
    
    # 페이징
    paginator = Paginator(notes, per_page)
    page_obj = paginator.get_page(page)
    
    data = {
        'notes': [{
            'id': note.note_sid,
            'title': note.title,
            'content': note.content[:100] + '...' if note.content else '',
            'date': note.created_at.strftime('%Y-%m-%d'),
            'shared': 0,  # 공유 로직 추가 시 구현
            'comments': 0,  # 댓글 기능 추가 시 구현
            'tags': [tag.name for tag in note.tags.all()],
        } for note in page_obj],
        'total_pages': paginator.num_pages,
        'current_page': page,
        'total_count': paginator.count
    }
    
    return JsonResponse(data)

@login_required
@csrf_exempt
def api_note_create(request):
    """API: 노트 생성"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            title = data.get('title')
            if not title:
                return JsonResponse({'error': 'Title is required'}, status=400)
            note = Note.objects.create(
                owner=request.user,
                title=title,
                content=data.get('content', ''),
                created_id=request.user.user_id,
                updated_id=request.user.user_id
            )
            return JsonResponse({'id': note.note_sid, 'status': 'created'})
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@login_required
def api_note_detail(request):
    """API: 노트 상세 조회"""
    note_id_str = request.GET.get('id')
    if not note_id_str:
        return JsonResponse({'error': 'Note ID is required'}, status=400)
    
    try:
        note_id = int(note_id_str)
    except ValueError:
        return JsonResponse({'error': 'Invalid note ID'}, status=400)
    
    try:
        note = Note.objects.get(note_sid=note_id, owner=request.user, status='E')
        data = {
            'id': note.note_sid,
            'title': note.title,
            'content': note.content or '',
            'date': note.created_at.strftime('%Y-%m-%d'),
            'author': note.owner.get_full_name() or note.owner.email,
            'shared': 0,  # 공유 로직 추가 시 구현
            'comments': 0,  # 댓글 기능 추가 시 구현
            'tags': [tag.name for tag in note.tags.all()],
        }
        return JsonResponse(data)
    except Note.DoesNotExist:
        return JsonResponse({'error': 'Note not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def note_detail(request):
    """Note detail page view (인증 필수)."""
    note_id = request.GET.get('id')
    if not note_id:
        return render(request, 'note/note_detail.html', {'note': None, 'error': 'Note ID is required'})
    
    try:
        note_id_int = int(note_id)
        note = Note.objects.get(note_sid=note_id_int, owner=request.user, status='E')
        context = {
            'note': note,
        }
        return render(request, 'note/note_detail.html', context)
    except ValueError:
        return render(request, 'note/note_detail.html', {'note': None, 'error': 'Invalid note ID'})
    except Note.DoesNotExist:
        return render(request, 'note/note_detail.html', {'note': None, 'error': 'Note not found'})

@login_required
def note_editor(request):
    """Note editor page view (create/edit) (인증 필수)."""
    note_id = request.GET.get('id')  # None이면 새 노트 생성, 있으면 수정
    context = {
        'note_id': note_id,
        'is_edit_mode': note_id is not None,
    }
    return render(request, 'note/note_editor.html', context)