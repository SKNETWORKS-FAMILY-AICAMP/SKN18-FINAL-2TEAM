import json
import re
import logging
from html import unescape
from urllib.parse import quote
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db import transaction, connection
from django.db.models import Count, OuterRef, Subquery, Value, CharField, Q
from django.db.models.functions import Coalesce
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema

logger = logging.getLogger(__name__)

from .models import Note, NoteTag, NoteAttachment, NoteShare, NoteComment
from apps.core.utils.s3_utils import (
    upload_file_to_s3,
    generate_note_attachment_s3_key
)

User = get_user_model()

# 파일 크기 제한: 1GB
MAX_FILE_SIZE = 1024 * 1024 * 1024  # 1GB in bytes

def _get_user_identifier(user):
    """사용자 식별자를 반환합니다."""
    return str(user.user_id) if hasattr(user, 'user_id') else str(user.pk)


def strip_html_tags(html_content):
    """
    HTML 태그를 제거하고 텍스트만 반환
    
    Args:
        html_content: HTML 문자열
    
    Returns:
        HTML 태그가 제거된 순수 텍스트
    """
    if not html_content:
        return ''
    
    # HTML 태그 제거
    text = re.sub(r'<[^>]+>', '', html_content)
    # HTML 엔티티 디코딩 (&lt; -> <, &amp; -> & 등)
    text = unescape(text)
    # 연속된 공백을 하나로 통합
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def generate_content_preview(content, max_length=200):
    """
    HTML 콘텐츠에서 텍스트만 추출하여 미리보기 생성
    
    Args:
        content: HTML 문자열
        max_length: 최대 길이 (기본값: 200)
    
    Returns:
        HTML 태그가 제거되고 길이가 제한된 텍스트
    """
    text = strip_html_tags(content)
    if len(text) > max_length:
        return text[:max_length]
    return text


@login_required
def index(request):
    """노트 목록 페이지 뷰"""
    return render(request, 'note/notes.html')


@login_required
def note_detail(request):
    """노트 상세 페이지 뷰"""
    return render(request, 'note/note_detail.html')


@login_required
def note_editor(request):
    """노트 편집기 페이지 뷰"""
    return render(request, 'note/note_editor.html')


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
                            'contentPreview': {'type': 'string', 'description': 'HTML 태그가 제거된 텍스트 미리보기 (최대 150자)'},
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

    # Query parameters
    my_notes_only = request.GET.get('my_notes_only', 'false').lower() == 'true'
    search_query = request.GET.get('search', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    
    # 쿼리 파라미터 로그
    logger.info(f'[NotesListAPI] Request - user_id: {user_identifier}, my_notes_only: {my_notes_only}, search_query: "{search_query}", date_from: "{date_from}", date_to: "{date_to}"')
    logger.info(f'[NotesListAPI] Query parameters: {dict(request.GET)}')

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
    
    # 내가 만든 노트 또는 나에게 공유된 노트 조회
    if my_notes_only:
        # 내 노트만 조회
        base_filter = Q(created_id=user_identifier)
    else:
        # 내가 만든 노트 또는 나에게 공유된 노트 조회
        base_filter = Q(created_id=user_identifier) | Q(shares__user_id=user_identifier)
    
    notes_qs = (
        Note.objects.filter(
            base_filter,
            status='E'  # 사용 중인 노트만 조회
        )
        .distinct()  # 중복 제거 (내가 만든 노트가 나에게도 공유된 경우)
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
    )
    
    # 검색 쿼리 적용 (제목, 내용, 작성자 이름, 태그)
    if search_query:
        # 작성자 이름 검색을 위한 User 조인
        author_search_filter = (
            Q(created_id__in=User.objects.filter(
                Q(full_name__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(user_id__icontains=search_query)
            ).values_list('user_id', flat=True))
        )
        
        search_filter = (
            Q(title__icontains=search_query) |
            Q(content__icontains=search_query) |
            author_search_filter |
            Q(tags__tag_name__icontains=search_query)
        )
        notes_qs = notes_qs.filter(search_filter).distinct()
    
    # 날짜 필터 적용
    if date_from:
        try:
            from_date = parse_date(date_from)
            if from_date:
                notes_qs = notes_qs.filter(created_at__gte=from_date)
        except (ValueError, TypeError):
            pass  # 잘못된 날짜 형식은 무시
    
    if date_to:
        try:
            to_date = parse_date(date_to)
            if to_date:
                # 날짜 범위의 끝까지 포함하기 위해 다음 날 00:00:00 미만
                from datetime import datetime, timedelta
                to_datetime = timezone.make_aware(
                    datetime.combine(to_date + timedelta(days=1), datetime.min.time())
                )
                notes_qs = notes_qs.filter(created_at__lt=to_datetime)
        except (ValueError, TypeError):
            pass  # 잘못된 날짜 형식은 무시
    
    notes_qs = notes_qs.order_by('-created_at')
    
    # SQL 쿼리 로그 출력
    logger.info(f'[NotesListAPI] SQL Query: {str(notes_qs.query)}')
    logger.info(f'[NotesListAPI] Query count before execution: {notes_qs.count()}')
    
    results = []
    for note in notes_qs:
        tags = [tag.tag_name for tag in note.tags.all()]
        
        # DB에 저장된 content_preview 사용 (없으면 동적 생성)
        if note.content_preview:
            content_preview = note.content_preview
        else:
            # 기존 노트의 경우 동적 생성 (하위 호환성)
            content_text = strip_html_tags(note.content or '')
            content_preview = content_text[:200] if len(content_text) > 200 else content_text
        
        # 내가 만든 노트인지 공유받은 노트인지 구분
        is_shared = note.created_id != user_identifier
        
        results.append({
            'id': note.note_sid,
            'title': note.title,
            'content': note.content or '',
            'contentPreview': content_preview,
            'date': note.created_at.strftime('%Y-%m-%d') if note.created_at else '',
            'author': note.author_name or '',
            'shared': note.shared_count or 0,
            'comments': note.comment_count or 0,
            'is_public': note.is_public,
            'is_shared': is_shared,  # 공유받은 노트인지 여부
            'tags': tags,
        })
    
    # 결과 로그
    logger.info(f'[NotesListAPI] Response - Total results: {len(results)}')
    
    return Response({
        'status': 'success',
        'results': results,
    })


@extend_schema(
    summary="노트 생성",
    description="새로운 노트를 생성합니다.",
    tags=["Notes"],
    request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'title': {'type': 'string'},
                'content': {'type': 'string'},
                'tags': {'type': 'string', 'description': 'JSON 배열 문자열'},
                'sharedMembers': {'type': 'string', 'description': 'JSON 배열 문자열'},
                'file_0': {'type': 'string', 'format': 'binary'},
            }
        }
    },
    responses={
        201: {
            'type': 'object',
            'properties': {
                'status': {'type': 'string', 'example': 'success'},
                'message': {'type': 'string'},
                'note': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'integer'},
                        'title': {'type': 'string'},
                    }
                }
            }
        }
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def note_create_api(request):
    """노트 생성 API"""
    user_identifier = _get_user_identifier(request.user)
    
    try:
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        
        if not title:
            return Response(
                {'status': 'error', 'error': '제목을 입력해주세요.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            # 노트 생성
            note = Note.objects.create(
                title=title,
                content=content,
                content_preview=generate_content_preview(content),
                created_id=user_identifier,
                updated_id=user_identifier,
                status='E'
            )
            
            # 태그 처리
            tags_json = request.POST.get('tags', '[]')
            try:
                tags = json.loads(tags_json) if tags_json else []
            except json.JSONDecodeError:
                tags = []
            
            for index, tag_name in enumerate(tags[:5]):  # 최대 5개
                if tag_name and tag_name.strip():
                    NoteTag.objects.create(
                        note=note,
                        tag_name=tag_name.strip(),
                        sort_order=index,
                        created_id=user_identifier
                    )
            
            # 파일 첨부 처리
            uploaded_files = []
            file_keys = [key for key in request.FILES.keys() if key.startswith('file_')]
            
            for file_key in file_keys:
                file = request.FILES[file_key]
                
                # 파일 크기 검증 (1GB)
                if file.size > MAX_FILE_SIZE:
                    raise ValueError(f'파일 크기가 1GB를 초과합니다: {file.name}')
                
                # 파일명 가져오기
                file_name_key = f'{file_key}_name'
                original_filename = request.POST.get(file_name_key, file.name)
                
                # S3 키 생성
                s3_key = generate_note_attachment_s3_key(user_identifier, original_filename)
                
                # S3 업로드
                success, error_msg = upload_file_to_s3(
                    file=file,
                    s3_key=s3_key,
                    content_type=file.content_type
                )
                
                if not success:
                    raise ValueError(f'파일 업로드 실패: {error_msg}')
                
                # DB에 저장
                attachment = NoteAttachment.objects.create(
                    note=note,
                    file_name=original_filename,
                    file_size=file.size,
                    file_type=file.content_type,
                    file_path=s3_key,
                    created_id=user_identifier,
                    updated_id=user_identifier
                )
                
                uploaded_files.append({
                    'id': attachment.attachment_sid,
                    'name': original_filename,
                    'size': file.size,
                    'type': file.content_type,
                    's3_key': s3_key
                })
            
            # 공유 멤버 처리
            shared_members_json = request.POST.get('sharedMembers', '[]')
            try:
                shared_members = json.loads(shared_members_json) if shared_members_json else []
            except json.JSONDecodeError:
                shared_members = []
            
            for member in shared_members:
                if member.get('id'):
                    NoteShare.objects.create(
                        note=note,
                        user_id=str(member['id']),
                        created_id=user_identifier
                    )
            
            return Response({
                'status': 'success',
                'message': '노트가 저장되었습니다.',
                'note': {
                    'id': note.note_sid,
                    'title': note.title
                },
                'uploaded_files': uploaded_files
            }, status=status.HTTP_201_CREATED)
            
    except ValueError as e:
        return Response(
            {'status': 'error', 'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'status': 'error', 'error': f'노트 저장 중 오류가 발생했습니다: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    summary="노트 수정",
    description="기존 노트를 수정합니다.",
    tags=["Notes"],
    request={
        'multipart/form-data': {
            'type': 'object',
            'properties': {
                'title': {'type': 'string'},
                'content': {'type': 'string'},
                'tags': {'type': 'string', 'description': 'JSON 배열 문자열'},
                'sharedMembers': {'type': 'string', 'description': 'JSON 배열 문자열'},
            }
        }
    },
    responses={
        200: {
            'type': 'object',
            'properties': {
                'status': {'type': 'string', 'example': 'success'},
                'message': {'type': 'string'},
                'note': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'integer'},
                        'title': {'type': 'string'},
                    }
                }
            }
        }
    }
)
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def note_update_api(request, note_id):
    """노트 수정 API"""
    user_identifier = _get_user_identifier(request.user)
    
    try:
        # 노트 조회 및 권한 확인
        try:
            note = Note.objects.get(
                note_sid=note_id,
                status='E',
                created_id=user_identifier
            )
        except Note.DoesNotExist:
            return Response(
                {'status': 'error', 'error': '노트를 찾을 수 없습니다.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        with transaction.atomic():
            # 제목과 내용 업데이트
            title = request.POST.get('title', '').strip()
            content = request.POST.get('content', '').strip()
            
            if not title:
                return Response(
                    {'status': 'error', 'error': '제목을 입력해주세요.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            note.title = title
            note.content = content
            note.content_preview = generate_content_preview(content)
            note.updated_id = user_identifier
            note.save()
            
            # 태그 업데이트 (기존 태그 삭제 후 재생성)
            NoteTag.objects.filter(note=note).delete()
            tags_json = request.POST.get('tags', '[]')
            try:
                tags = json.loads(tags_json) if tags_json else []
            except json.JSONDecodeError:
                tags = []
            
            for index, tag_name in enumerate(tags[:5]):  # 최대 5개
                if tag_name and tag_name.strip():
                    NoteTag.objects.create(
                        note=note,
                        tag_name=tag_name.strip(),
                        sort_order=index,
                        created_id=user_identifier
                    )
        
        # 새로 첨부된 파일 처리
        uploaded_files = []
        file_keys = [key for key in request.FILES.keys() if key.startswith('file_')]
        
        for file_key in file_keys:
            file = request.FILES[file_key]
            
            # 파일 크기 검증 (1GB)
            if file.size > MAX_FILE_SIZE:
                raise ValueError(f'파일 크기가 1GB를 초과합니다: {file.name}')
            
            # 파일명 가져오기
            file_name_key = f'{file_key}_name'
            original_filename = request.POST.get(file_name_key, file.name)
            
            # S3 키 생성
            s3_key = generate_note_attachment_s3_key(user_identifier, original_filename)
            
            # S3 업로드
            success, error_msg = upload_file_to_s3(
                file=file,
                s3_key=s3_key,
                content_type=file.content_type
            )
            
            if not success:
                raise ValueError(f'파일 업로드 실패: {error_msg}')
            
            # DB에 저장
            attachment = NoteAttachment.objects.create(
                note=note,
                file_name=original_filename,
                file_size=file.size,
                file_type=file.content_type,
                file_path=s3_key,
                created_id=user_identifier,
                updated_id=user_identifier
            )
            
            uploaded_files.append({
                'id': attachment.attachment_sid,
                'name': original_filename,
                'size': file.size,
                'type': file.content_type,
                's3_key': s3_key
            })
        
        # 공유 멤버 업데이트 (기존 공유 정보 삭제 후 재생성)
        NoteShare.objects.filter(note=note).delete()
        shared_members_json = request.POST.get('sharedMembers', '[]')
        try:
            shared_members = json.loads(shared_members_json) if shared_members_json else []
        except json.JSONDecodeError:
            shared_members = []
        
        for member in shared_members:
            if member.get('id'):
                NoteShare.objects.create(
                    note=note,
                    user_id=str(member['id']),
                    created_id=user_identifier
                )
        
        return Response({
            'status': 'success',
            'message': '노트가 수정되었습니다.',
            'note': {
                'id': note.note_sid,
                'title': note.title,
                'updated_at': note.updated_at.isoformat() if note.updated_at else None
            },
            'uploaded_files': uploaded_files
        }, status=status.HTTP_200_OK)
        
    except ValueError as e:
        return Response(
            {'status': 'error', 'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'status': 'error', 'error': f'노트 수정 중 오류가 발생했습니다: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    summary="노트 상세 조회",
    description="노트의 상세 정보를 조회합니다.",
    tags=["Notes"],
    responses={
        200: {
            'type': 'object',
            'properties': {
                'status': {'type': 'string', 'example': 'success'},
                'note': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'integer'},
                        'title': {'type': 'string'},
                        'content': {'type': 'string'},
                        'date': {'type': 'string'},
                        'author': {'type': 'string'},
                        'tags': {'type': 'array', 'items': {'type': 'string'}},
                        'shared': {'type': 'integer'},
                        'comments': {'type': 'integer'},
                        'is_public': {'type': 'boolean'},
                        'attachments': {'type': 'array'},
                        'comments_list': {'type': 'array'},
                    }
                }
            }
        }
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def note_detail_api(request, note_id):
    """노트 상세 조회 API"""
    user_identifier = _get_user_identifier(request.user)
    
    try:
        # 노트 조회 및 권한 확인 (본인이 작성한 노트 또는 나에게 공유된 노트 조회 가능)
        try:
            note = Note.objects.select_related().prefetch_related(
                'tags', 'attachments', 'comments', 'shares'
            ).filter(
                note_sid=note_id,
                status='E'
            ).filter(
                Q(created_id=user_identifier) | Q(shares__user_id=user_identifier)
            ).distinct().first()
            
            if not note:
                return Response(
                    {'status': 'error', 'error': '노트를 찾을 수 없습니다.'},
                    status=status.HTTP_404_NOT_FOUND
                )
        except Note.DoesNotExist:
            return Response(
                {'status': 'error', 'error': '노트를 찾을 수 없습니다.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # 내가 만든 노트인지 공유받은 노트인지 확인
        is_shared = note.created_id != user_identifier
        
        # 작성자 이름 및 프로필 이미지 조회
        author_avatar = ''
        try:
            author_user = User.objects.get(user_id=note.created_id)
            author_name = author_user.full_name or author_user.email or note.created_id
            author_avatar = author_user.img_url or ''
        except User.DoesNotExist:
            author_name = note.created_id
            author_avatar = ''
        
        # 작성자 아바타 URL (없으면 빈 문자열, 프론트엔드에서 플레이스홀더 표시)
        author_avatar_url = author_avatar if author_avatar else ''
        
        # 태그 목록
        tags = [tag.tag_name for tag in note.tags.all()]
        
        # 첨부 파일 목록
        attachments = []
        for attachment in note.attachments.all():
            attachments.append({
                'id': attachment.attachment_sid,
                'name': attachment.file_name,
                'size': attachment.file_size or 0,
                'type': attachment.file_type or '',
                'path': attachment.file_path or '',
                'created_at': attachment.created_at.isoformat() if attachment.created_at else None
            })
        
        # 댓글 목록 (노트에 등록된 모든 댓글 조회, status='E'인 것만)
        comments_list = []
        for comment in note.comments.filter(status='E').order_by('position_top', 'created_at'):
            # 댓글 작성자 정보
            try:
                comment_author = User.objects.get(user_id=comment.created_id)
                comment_author_name = comment_author.full_name or comment_author.email or comment.created_id
                comment_author_avatar = comment_author.img_url or ''
            except User.DoesNotExist:
                comment_author_name = comment.created_id
                comment_author_avatar = ''
            
            # 본인이 작성한 댓글인지 확인
            is_mine = str(comment.created_id) == user_identifier
            
            # 시간 표시 (상대 시간)
            time_ago = ''
            if comment.created_at:
                now = timezone.now()
                diff = now - comment.created_at
                if diff.days > 0:
                    time_ago = f'{diff.days}일 전'
                elif diff.seconds >= 3600:
                    hours = diff.seconds // 3600
                    time_ago = f'{hours}시간 전'
                elif diff.seconds >= 60:
                    minutes = diff.seconds // 60
                    time_ago = f'{minutes}분 전'
                else:
                    time_ago = '방금 전'
            
            # 아바타 URL (없으면 빈 문자열, 프론트엔드에서 플레이스홀더 표시)
            avatar_url = comment_author_avatar if comment_author_avatar else ''
            
            comments_list.append({
                'id': comment.comment_sid,
                'highlighted_text': comment.highlighted_text or '',
                'comment': comment.comment_text,
                'author': comment_author_name,
                'avatar': avatar_url,
                'time': time_ago,
                'position': comment.position_top or 0,
                'created_at': comment.created_at.isoformat() if comment.created_at else None,
                'is_mine': is_mine  # 본인이 작성한 댓글인지 여부
            })
        
        # 공유 수, 댓글 수 (status='E'인 댓글만 카운트)
        shared_count = note.shares.count()
        comment_count = note.comments.filter(status='E').count()
        
        # 공유된 사용자 목록
        shared_users_list = []
        for share in note.shares.all():
            try:
                shared_user = User.objects.get(user_id=share.user_id)
                shared_user_name = shared_user.full_name or shared_user.email or share.user_id
                shared_user_avatar = shared_user.img_url or ''
                shared_user_email = shared_user.email or ''
            except User.DoesNotExist:
                shared_user_name = share.user_id
                shared_user_avatar = ''
                shared_user_email = ''
            
            # 아바타 URL 생성
            avatar_url = shared_user_avatar
            if not avatar_url:
                avatar_url = f'https://ui-avatars.com/api/?name={quote(shared_user_name)}&background=random'
            
            # 공유일
            shared_date = share.created_at.strftime('%Y년 %m월 %d일') if share.created_at else ''
            
            shared_users_list.append({
                'id': share.user_id,
                'name': shared_user_name,
                'email': shared_user_email,
                'avatar': avatar_url,
                'role': 'Member',
                'sharedDate': shared_date
            })
        
        return Response({
            'status': 'success',
            'note': {
                'id': note.note_sid,
                'title': note.title,
                'content': note.content or '',
                'date': note.created_at.strftime('%Y-%m-%d') if note.created_at else '',
                'author': author_name,
                'author_avatar': author_avatar_url,
                'tags': tags,
                'shared': shared_count,
                'comments': comment_count,
                'is_public': note.is_public,
                'is_shared': is_shared,  # 공유받은 노트인지 여부
                'attachments': attachments,
                'comments_list': comments_list,
                'shared_users_list': shared_users_list  # 공유된 사용자 목록 추가
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'status': 'error', 'error': f'노트 조회 중 오류가 발생했습니다: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    summary="노트 삭제",
    description="노트를 삭제합니다 (소프트 삭제).",
    tags=["Notes"],
    responses={
        200: {
            'type': 'object',
            'properties': {
                'status': {'type': 'string', 'example': 'success'},
                'message': {'type': 'string'},
            }
        }
    }
)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def note_delete_api(request, note_id):
    """노트 삭제 API (소프트 삭제)"""
    user_identifier = _get_user_identifier(request.user)
    
    try:
        # 노트 조회 및 권한 확인
        try:
            note = Note.objects.get(
                note_sid=note_id,
                status='E',
                created_id=user_identifier
            )
        except Note.DoesNotExist:
            return Response(
                {'status': 'error', 'error': '노트를 찾을 수 없습니다.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        with transaction.atomic():
            # 소프트 삭제 (status를 'R'로 변경)
            note.status = 'R'
            note.updated_id = user_identifier
            note.save()
        
        return Response({
            'status': 'success',
            'message': '노트가 삭제되었습니다.'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'status': 'error', 'error': f'노트 삭제 중 오류가 발생했습니다: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    summary="댓글 추가",
    description="노트에 댓글을 추가합니다.",
    tags=["Notes"],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'comment_text': {'type': 'string'},
                'highlighted_text': {'type': 'string', 'description': '선택된 텍스트 (선택사항)'},
                'position_top': {'type': 'integer', 'description': '댓글 위치 (선택사항)'},
            },
            'required': ['comment_text']
        }
    },
    responses={
        201: {
            'type': 'object',
            'properties': {
                'status': {'type': 'string', 'example': 'success'},
                'message': {'type': 'string'},
                'comment': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'integer'},
                        'comment_text': {'type': 'string'},
                        'author': {'type': 'string'},
                        'time': {'type': 'string'},
                    }
                }
            }
        }
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def comment_create_api(request, note_id):
    """댓글 추가 API"""
    user_identifier = _get_user_identifier(request.user)
    
    try:
        # 노트 조회 및 권한 확인 (소유자 또는 공유받은 사용자)
        try:
            note = Note.objects.filter(
                note_sid=note_id,
                status='E'
            ).filter(
                Q(created_id=user_identifier) | Q(shares__user_id=user_identifier)
            ).distinct().first()
            
            if not note:
                return Response(
                    {'status': 'error', 'error': '노트를 찾을 수 없습니다.'},
                    status=status.HTTP_404_NOT_FOUND
                )
        except Note.DoesNotExist:
            return Response(
                {'status': 'error', 'error': '노트를 찾을 수 없습니다.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # 요청 데이터 파싱
        if request.content_type == 'application/json':
            data = request.data
        else:
            data = request.POST
        
        comment_text = data.get('comment_text', '').strip()
        highlighted_text = data.get('highlighted_text', '').strip()[:500]  # 최대 500자
        position_top = data.get('position_top', 0)
        
        if not comment_text:
            return Response(
                {'status': 'error', 'error': '댓글 내용을 입력해주세요.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            # 댓글 생성
            comment = NoteComment.objects.create(
                note=note,
                comment_text=comment_text,
                highlighted_text=highlighted_text if highlighted_text else None,
                position_top=position_top,
                created_id=user_identifier,
                updated_id=user_identifier
            )
            
            # 댓글 작성자 정보
            try:
                comment_author = User.objects.get(user_id=user_identifier)
                comment_author_name = comment_author.full_name or comment_author.email or user_identifier
                comment_author_avatar = comment_author.img_url or ''
            except User.DoesNotExist:
                comment_author_name = user_identifier
                comment_author_avatar = ''
            
            # 시간 표시 (상대 시간)
            time_ago = '방금 전'
            if comment.created_at:
                now = timezone.now()
                diff = now - comment.created_at
                if diff.days > 0:
                    time_ago = f'{diff.days}일 전'
                elif diff.seconds >= 3600:
                    hours = diff.seconds // 3600
                    time_ago = f'{hours}시간 전'
                elif diff.seconds >= 60:
                    minutes = diff.seconds // 60
                    time_ago = f'{minutes}분 전'
            
            # 아바타 URL (없으면 빈 문자열, 프론트엔드에서 플레이스홀더 표시)
            avatar_url = comment_author_avatar if comment_author_avatar else ''
            
            return Response({
                'status': 'success',
                'message': '댓글이 추가되었습니다.',
                'comment': {
                    'id': comment.comment_sid,
                    'highlighted_text': comment.highlighted_text or '',
                    'comment': comment.comment_text,
                    'author': comment_author_name,
                    'avatar': avatar_url,
                    'time': time_ago,
                    'position': comment.position_top or 0,
                    'created_at': comment.created_at.isoformat() if comment.created_at else None
                }
            }, status=status.HTTP_201_CREATED)
            
    except Exception as e:
        return Response(
            {'status': 'error', 'error': f'댓글 추가 중 오류가 발생했습니다: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    summary="댓글 수정",
    description="댓글을 수정합니다.",
    tags=["Notes"],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'comment_text': {'type': 'string'},
            },
            'required': ['comment_text']
        }
    },
    responses={
        200: {
            'type': 'object',
            'properties': {
                'status': {'type': 'string', 'example': 'success'},
                'message': {'type': 'string'},
                'comment': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'integer'},
                        'comment_text': {'type': 'string'},
                    }
                }
            }
        }
    }
)
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def comment_update_api(request, note_id, comment_id):
    """댓글 수정 API"""
    user_identifier = _get_user_identifier(request.user)
    
    try:
        # 노트 조회 및 권한 확인 (소유자 또는 공유받은 사용자)
        try:
            note = Note.objects.filter(
                note_sid=note_id,
                status='E'
            ).filter(
                Q(created_id=user_identifier) | Q(shares__user_id=user_identifier)
            ).distinct().first()
            
            if not note:
                return Response(
                    {'status': 'error', 'error': '노트를 찾을 수 없습니다.'},
                    status=status.HTTP_404_NOT_FOUND
                )
        except Note.DoesNotExist:
            return Response(
                {'status': 'error', 'error': '노트를 찾을 수 없습니다.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # 댓글 조회 및 권한 확인 (본인이 작성한 댓글만 수정 가능)
        try:
            comment = NoteComment.objects.get(
                comment_sid=comment_id,
                note=note,
                created_id=user_identifier
            )
        except NoteComment.DoesNotExist:
            return Response(
                {'status': 'error', 'error': '댓글을 찾을 수 없거나 수정 권한이 없습니다.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # 요청 데이터 파싱
        if request.content_type == 'application/json':
            data = request.data
        else:
            data = request.POST
        
        comment_text = data.get('comment_text', '').strip()
        
        if not comment_text:
            return Response(
                {'status': 'error', 'error': '댓글 내용을 입력해주세요.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            # 댓글 수정
            comment.comment_text = comment_text
            comment.updated_id = user_identifier
            comment.save()
            
            # 댓글 작성자 정보
            try:
                comment_author = User.objects.get(user_id=user_identifier)
                comment_author_name = comment_author.full_name or comment_author.email or user_identifier
                comment_author_avatar = comment_author.img_url or ''
            except User.DoesNotExist:
                comment_author_name = user_identifier
                comment_author_avatar = ''
            
            # 시간 표시 (상대 시간)
            time_ago = ''
            if comment.created_at:
                now = timezone.now()
                diff = now - comment.created_at
                if diff.days > 0:
                    time_ago = f'{diff.days}일 전'
                elif diff.seconds >= 3600:
                    hours = diff.seconds // 3600
                    time_ago = f'{hours}시간 전'
                elif diff.seconds >= 60:
                    minutes = diff.seconds // 60
                    time_ago = f'{minutes}분 전'
                else:
                    time_ago = '방금 전'
            
            # 아바타 URL (없으면 빈 문자열, 프론트엔드에서 플레이스홀더 표시)
            avatar_url = comment_author_avatar if comment_author_avatar else ''
            
            return Response({
                'status': 'success',
                'message': '댓글이 수정되었습니다.',
                'comment': {
                    'id': comment.comment_sid,
                    'highlighted_text': comment.highlighted_text or '',
                    'comment': comment.comment_text,
                    'author': comment_author_name,
                    'avatar': avatar_url,
                    'time': time_ago,
                    'position': comment.position_top or 0,
                    'created_at': comment.created_at.isoformat() if comment.created_at else None,
                    'is_mine': True  # 수정 API는 본인 댓글만 수정 가능하므로 항상 True
                }
            }, status=status.HTTP_200_OK)
            
    except Exception as e:
        return Response(
            {'status': 'error', 'error': f'댓글 수정 중 오류가 발생했습니다: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    summary="댓글 삭제",
    description="댓글을 삭제합니다.",
    tags=["Notes"],
    responses={
        200: {
            'type': 'object',
            'properties': {
                'status': {'type': 'string', 'example': 'success'},
                'message': {'type': 'string'},
            }
        }
    }
)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def comment_delete_api(request, note_id, comment_id):
    """댓글 삭제 API"""
    user_identifier = _get_user_identifier(request.user)
    
    try:
        # 노트 조회 및 권한 확인 (소유자 또는 공유받은 사용자)
        try:
            note = Note.objects.filter(
                note_sid=note_id,
                status='E'
            ).filter(
                Q(created_id=user_identifier) | Q(shares__user_id=user_identifier)
            ).distinct().first()
            
            if not note:
                return Response(
                    {'status': 'error', 'error': '노트를 찾을 수 없습니다.'},
                    status=status.HTTP_404_NOT_FOUND
                )
        except Note.DoesNotExist:
            return Response(
                {'status': 'error', 'error': '노트를 찾을 수 없습니다.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # 댓글 조회 및 권한 확인 (본인이 작성한 댓글만 삭제 가능)
        try:
            comment = NoteComment.objects.get(
                comment_sid=comment_id,
                note=note,
                created_id=user_identifier,
                status='E'  # 사용 중인 댓글만 삭제 가능
            )
        except NoteComment.DoesNotExist:
            return Response(
                {'status': 'error', 'error': '댓글을 찾을 수 없거나 삭제 권한이 없습니다.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        with transaction.atomic():
            # Soft delete (status를 'R'로 변경)
            comment.status = 'R'
            comment.updated_id = user_identifier
            comment.save()
        
        return Response({
            'status': 'success',
            'message': '댓글이 삭제되었습니다.'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'status': 'error', 'error': f'댓글 삭제 중 오류가 발생했습니다: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    summary="노트 공유",
    description="노트를 다른 사용자와 공유합니다.",
    tags=["Notes"],
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'sharedMembers': {'type': 'array', 'items': {'type': 'object'}},
            },
            'required': ['sharedMembers']
        }
    },
    responses={
        200: {
            'type': 'object',
            'properties': {
                'status': {'type': 'string', 'example': 'success'},
                'message': {'type': 'string'},
            }
        }
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def note_share_api(request, note_id):
    """노트 공유 API"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f'[NoteShareAPI] API called - note_id: {note_id}, user: {request.user}')
    logger.info(f'[NoteShareAPI] Request method: {request.method}')
    logger.info(f'[NoteShareAPI] Content-Type: {request.content_type}')
    
    user_identifier = _get_user_identifier(request.user)
    logger.info(f'[NoteShareAPI] User identifier: {user_identifier}')
    
    try:
        # 노트 조회 및 권한 확인
        try:
            note = Note.objects.get(
                note_sid=note_id,
                status='E',
                created_id=user_identifier
            )
            logger.info(f'[NoteShareAPI] Note found: {note.note_sid}, title: {note.title}')
        except Note.DoesNotExist:
            logger.error(f'[NoteShareAPI] Note not found - note_id: {note_id}, user: {user_identifier}')
            return Response(
                {'status': 'error', 'error': '노트를 찾을 수 없습니다.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # 요청 데이터 파싱
        if request.content_type == 'application/json':
            data = request.data
            logger.info(f'[NoteShareAPI] Request data (JSON): {data}')
        else:
            data = request.POST
            logger.info(f'[NoteShareAPI] Request data (POST): {data}')
        
        shared_members_json = data.get('sharedMembers', '[]')
        logger.info(f'[NoteShareAPI] shared_members_json: {shared_members_json}')
        
        try:
            shared_members = json.loads(shared_members_json) if isinstance(shared_members_json, str) else shared_members_json
            logger.info(f'[NoteShareAPI] Parsed shared_members: {shared_members}')
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f'[NoteShareAPI] Failed to parse shared_members: {e}')
            shared_members = []
        
        with transaction.atomic():
            # 공유 멤버 업데이트 (기존 공유 정보 삭제 후 재생성)
            existing_shares = NoteShare.objects.filter(note=note)
            existing_count = existing_shares.count()
            logger.info(f'[NoteShareAPI] Existing shares count: {existing_count}')
            existing_shares.delete()
            
            created_count = 0
            for member in shared_members:
                if member.get('id'):
                    NoteShare.objects.create(
                        note=note,
                        user_id=str(member['id']),
                        created_id=user_identifier
                    )
                    created_count += 1
                    logger.info(f'[NoteShareAPI] Created share for user_id: {member["id"]}')
            
            logger.info(f'[NoteShareAPI] Created {created_count} new shares')
        
        logger.info(f'[NoteShareAPI] Share successful - note_id: {note_id}, shared_count: {created_count}')
        return Response({
            'status': 'success',
            'message': '노트가 공유되었습니다.'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f'[NoteShareAPI] Error occurred: {str(e)}', exc_info=True)
        return Response(
            {'status': 'error', 'error': f'노트 공유 중 오류가 발생했습니다: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
