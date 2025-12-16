from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count
from .models import Note, NoteComment
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

    login_email = request.user.email

    notes = (
        Note.objects
        .filter(created_id=login_email, status='E')
        .annotate(comment_count=Count('comments'))
        .order_by('-created_at')
    )

    if search:
        notes = notes.filter(title__icontains=search)

    if date_from:
        notes = notes.filter(created_at__date__gte=date_from)
    if date_to:
        notes = notes.filter(created_at__date__lte=date_to)

    paginator = Paginator(notes, per_page)
    page_obj = paginator.get_page(page)

    data = {
        'notes': [{
            'id': note.note_sid,
            'title': note.title,
            'content': (note.content[:100] + '...') if note.content else '',
            'date': note.created_at.strftime('%Y-%m-%d'),
            'shared': 0,
            'comments': note.comment_count,
            'tags': [tag.tag_name for tag in note.tags.all()],
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

            login_email = request.user.email

            note = Note.objects.create(
                title=title,
                content=data.get('content', ''),
                created_id=login_email,
                updated_id=login_email
            )
            return JsonResponse({'id': note.note_sid, 'status': 'created'})
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
@csrf_exempt
def api_note_update(request):
    """API: 노트 수정"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            note_id = data.get('id')
            title = data.get('title')

            if not note_id:
                return JsonResponse({'error': 'Note ID is required'}, status=400)
            if not title:
                return JsonResponse({'error': 'Title is required'}, status=400)

            try:
                note_id_int = int(note_id)
            except ValueError:
                return JsonResponse({'error': 'Invalid note ID'}, status=400)

            login_email = request.user.email

            note = Note.objects.get(
                note_sid=note_id_int,
                created_id=login_email,
                status='E'
            )
            note.title = title
            note.content = data.get('content', '')
            note.updated_id = login_email
            note.save()

            return JsonResponse({'id': note.note_sid, 'status': 'updated'})
        except Note.DoesNotExist:
            return JsonResponse({'error': 'Note not found'}, status=404)
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
        login_email = request.user.email

        note = Note.objects.get(
            note_sid=note_id,
            created_id=login_email,
            status='E'
        )
        data = {
            'id': note.note_sid,
            'title': note.title,
            'content': note.content or '',
            'date': note.created_at.strftime('%Y-%m-%d'),
            'author': request.user.get_full_name(),
            'shared': 0,
            'comments': note.comments.count(),
            'tags': [tag.tag_name for tag in note.tags.all()],
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
        login_email = request.user.email

        note = Note.objects.get(
            note_sid=note_id_int,
            created_id=login_email,
            status='E'
        )
        comments = NoteComment.objects.filter(note=note).order_by('-created_at')
        context = {
            'note': note,
            'comments': comments,
            'author': request.user.get_full_name(),
        }
        return render(request, 'note/note_detail.html', context)
    except ValueError:
        return render(request, 'note/note_detail.html', {'note': None, 'error': 'Invalid note ID'})
    except Note.DoesNotExist:
        return render(request, 'note/note_detail.html', {'note': None, 'error': 'Note not found'})


@login_required
def note_editor(request):
    """Note editor page view (create/edit) (인증 필수)."""
    note_id = request.GET.get('id')
    context = {
        'note_id': note_id,
        'is_edit_mode': note_id is not None,
    }
    return render(request, 'note/note_editor.html', context)


@login_required
@csrf_exempt
def api_note_add_comment(request):
    """API: 노트에 댓글 추가"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        note_id = data.get('note_id')
        highlighted_text = data.get('highlighted_text', '')
        comment_text = data.get('comment_text', '').strip()
        position_top = data.get('position_top', 0)

        if not note_id or not comment_text:
            return JsonResponse({'error': 'Note ID and comment text are required'}, status=400)

        login_email = request.user.email

        note = Note.objects.get(
            note_sid=note_id,
            created_id=login_email,
            status='E'
        )

        comment = NoteComment.objects.create(
            note=note,
            highlighted_text=highlighted_text,
            comment_text=comment_text,
            position_top=position_top,
            created_id=login_email,
            updated_id=login_email
        )

        return JsonResponse({
            'id': comment.comment_sid,
            'comment_text': comment.comment_text,
            'highlighted_text': comment.highlighted_text,
            'position_top': comment.position_top,
            'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'author': request.user.get_full_name(),
            'status': 'created'
        })
    except Note.DoesNotExist:
        return JsonResponse({'error': 'Note not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_note_comments(request):
    """API: 노트 댓글 목록 조회"""
    note_id_str = request.GET.get('note_id')
    if not note_id_str:
        return JsonResponse({'error': 'Note ID is required'}, status=400)

    try:
        note_id = int(note_id_str)
        login_email = request.user.email

        note = Note.objects.get(
            note_sid=note_id,
            created_id=login_email,
            status='E'
        )
        comments = NoteComment.objects.filter(note=note).order_by('-created_at')

        data = [{
            'id': comment.comment_sid,
            'highlighted_text': comment.highlighted_text,
            'comment_text': comment.comment_text,
            'position_top': comment.position_top,
            'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'author': request.user.get_full_name(),
        } for comment in comments]

        return JsonResponse({'comments': data})
    except Note.DoesNotExist:
        return JsonResponse({'error': 'Note not found'}, status=404)
    except ValueError:
        return JsonResponse({'error': 'Invalid note ID'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)