from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Count, OuterRef, Subquery, Value, CharField
from django.db.models.functions import Coalesce
from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from .models import Note

User = get_user_model()


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


@extend_schema(
    summary="노트 목록 조회",
    description="사용자의 노트 목록을 반환합니다.",
    tags=["Notes"],
    responses={
        200: {
            'type': 'object',
            'properties': {
                'status': {'type': 'string', 'example': 'success'},
                'results': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'string'},
                            'title': {'type': 'string'},
                            'content': {'type': 'string'},
                            'date': {'type': 'string', 'format': 'date'},
                            'author': {'type': 'string'},
                            'shared': {'type': 'integer'},
                            'comments': {'type': 'integer'},
                            'is_public': {'type': 'boolean'},
                            'tags': {'type': 'array', 'items': {'type': 'string'}},
                        }
                    }
                }
            }
        }
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notes_list_api(request):
    """노트 목록을 JSON으로 반환."""
    user_identifier = str(request.user.user_id) if hasattr(request.user, 'user_id') else str(request.user.pk)

    # zs_user.user_name(=CustomUser.full_name)을 created_id와 연결해 작성자 이름을 조회하되
    # 이름이 없으면 이메일/아이디를 순차적으로 사용
    author_name_subquery = (
        User.objects.filter(user_id=OuterRef('created_id'))
        .annotate(
            display_name=Coalesce(
                'full_name',
                'email',
                'user_id',
                output_field=CharField()
            )
        )
        .values('display_name')[:1]
    )
    
    notes_qs = (
        Note.objects.filter(created_id=user_identifier)
        .annotate(
            shared_count=Count('shares', distinct=True),
            comment_count=Count('comments', distinct=True),
            author_name=Coalesce(
                Subquery(author_name_subquery),
                Value(''),
                output_field=CharField()
            ),
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
            'author': note.author_name or '',
            'shared': note.shared_count or 0,
            'comments': note.comment_count or 0,
            'is_public': note.is_public,
            'tags': tags,
        })
    
    return Response({
        'status': 'success',
        'results': results,
    })
