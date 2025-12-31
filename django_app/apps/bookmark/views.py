from django.db.models import Prefetch, Max
from django.db import transaction, IntegrityError, IntegrityError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema

from .models import Bookmark, BookmarkCategory, BookmarkMap


def _get_user_identifier(user):
    """사용자 식별자를 반환합니다."""
    return str(user.user_id) if hasattr(user, 'user_id') else str(user.pk)


@extend_schema(
    summary="북마크 목록 조회",
    description="t_bookmark 및 t_bookmark_category 데이터를 조회해 카테고리별 북마크를 반환합니다.",
    tags=["Bookmark"],
    responses={
        200: {
            "type": "object",
            "properties": {
                "status": {"type": "string", "example": "success"},
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "category_sid": {"type": "integer"},
                            "category_name": {"type": "string"},
                            "bookmark_count": {"type": "integer"},
                            "bookmarks": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "bookmark_sid": {"type": "integer"},
                                        "title": {"type": "string"},
                                        "url": {"type": "string"},
                                        "description": {"type": "string"},
                                    },
                                },
                            },
                        },
                    },
                },
            },
        }
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def bookmark_list_api(request):
    """
    북마크 카테고리와 해당 북마크 목록을 반환합니다.
    """

    user_identifier = _get_user_identifier(request.user)

    categories = (
        BookmarkCategory.objects.filter(status='E', created_id=user_identifier)
        .prefetch_related(
            Prefetch(
                "bookmarks",
                queryset=Bookmark.objects.filter(
                    status='E',
                    created_id=user_identifier,
                ).order_by("title"),
            )
        )
        .order_by("sort_order", "category_sid")
    )

    results = []
    for category in categories:
        bookmarks = [
            {
                "bookmark_sid": bookmark.bookmark_sid,
                "title": bookmark.title,
                "url": bookmark.bookmark_url,
                "description": bookmark.description or "",
            }
            for bookmark in category.bookmarks.all()
        ]

        results.append(
            {
                "category_sid": category.category_sid,
                "category_name": category.category_name,
                "bookmark_count": len(bookmarks),
                "bookmarks": bookmarks,
            }
        )

    return Response({"status": "success", "results": results})


@extend_schema(
    summary="북마크 카테고리 생성",
    description="새로운 북마크 카테고리를 생성합니다.",
    tags=["Bookmark"],
    request={
        "type": "object",
        "properties": {
            "category_name": {"type": "string", "description": "카테고리 이름"},
            "sort_order": {"type": "integer", "description": "정렬 순서 (선택)", "default": 0},
        },
        "required": ["category_name"],
    },
    responses={
        201: {
            "type": "object",
            "properties": {
                "status": {"type": "string", "example": "success"},
                "category": {
                    "type": "object",
                    "properties": {
                        "category_sid": {"type": "integer"},
                        "category_name": {"type": "string"},
                        "sort_order": {"type": "integer"},
                    },
                },
            },
        },
        400: {"type": "object", "properties": {"error": {"type": "string"}}},
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def bookmark_category_create_api(request):
    """
    북마크 카테고리를 생성합니다.
    """
    category_name = request.data.get("category_name", "").strip()
    
    if not category_name:
        return Response(
            {"status": "error", "error": "카테고리 이름은 필수입니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    user_identifier = _get_user_identifier(request.user)
    
    category_queryset = BookmarkCategory.objects.filter(
        status='E',
        created_id=user_identifier,
    )

    # 기존 카테고리와 이름 중복 체크 (사용자별 활성 상태인 것만 체크)
    if category_queryset.filter(category_name=category_name).exists():
        return Response(
            {"status": "error", "error": "이미 존재하는 카테고리 이름입니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    # sort_order 계산 (현재 최대값 + 1, 사용자별 활성 상태인 것만)
    max_sort_order = category_queryset.aggregate(
        max_order=Max('sort_order')
    )['max_order'] or 0
    
    try:
        category = BookmarkCategory.objects.create(
            category_name=category_name,
            sort_order=request.data.get("sort_order", max_sort_order + 1),
            status='E',
            created_id=user_identifier,
            updated_id=user_identifier,
        )
    except IntegrityError as e:
        # 시퀀스 문제인 경우 에러 메시지 반환
        return Response(
            {
                "status": "error",
                "error": "카테고리 생성 중 오류가 발생했습니다. 데이터베이스 시퀀스 문제일 수 있습니다. 관리자에게 문의하세요.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    
    return Response(
        {
            "status": "success",
            "category": {
                "category_sid": category.category_sid,
                "category_name": category.category_name,
                "sort_order": category.sort_order,
            },
        },
        status=status.HTTP_201_CREATED,
    )


@extend_schema(
    summary="북마크 생성",
    description="새로운 북마크를 생성하고 지정된 카테고리와 연결합니다.",
    tags=["Bookmark"],
    request={
        "type": "object",
        "properties": {
            "category_sid": {"type": "integer", "description": "카테고리 ID"},
            "title": {"type": "string", "description": "북마크 제목"},
            "bookmark_url": {"type": "string", "description": "북마크 URL"},
            "description": {"type": "string", "description": "북마크 설명 (선택)"},
        },
        "required": ["category_sid", "title", "bookmark_url"],
    },
    responses={
        201: {
            "type": "object",
            "properties": {
                "status": {"type": "string", "example": "success"},
                "bookmark": {
                    "type": "object",
                    "properties": {
                        "bookmark_sid": {"type": "integer"},
                        "title": {"type": "string"},
                        "url": {"type": "string"},
                        "description": {"type": "string"},
                    },
                },
            },
        },
        400: {"type": "object", "properties": {"error": {"type": "string"}}},
        404: {"type": "object", "properties": {"error": {"type": "string"}}},
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def bookmark_create_api(request):
    """
    북마크를 생성하고 카테고리와 연결합니다.
    """
    category_sid = request.data.get("category_sid")
    title = request.data.get("title", "").strip()
    bookmark_url = request.data.get("bookmark_url", "").strip()
    description = request.data.get("description", "").strip()
    
    if not category_sid:
        return Response(
            {"status": "error", "error": "카테고리 ID는 필수입니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    if not title:
        return Response(
            {"status": "error", "error": "북마크 제목은 필수입니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    if not bookmark_url:
        return Response(
            {"status": "error", "error": "북마크 URL은 필수입니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    user_identifier = _get_user_identifier(request.user)

    # 카테고리 존재 확인 (사용자별 활성 상태인 것만)
    try:
        category = BookmarkCategory.objects.get(
            category_sid=category_sid,
            status='E',
            created_id=user_identifier,
        )
    except BookmarkCategory.DoesNotExist:
        return Response(
            {"status": "error", "error": "존재하지 않는 카테고리입니다."},
            status=status.HTTP_404_NOT_FOUND,
        )
    
    # 북마크 생성
    bookmark = Bookmark.objects.create(
        title=title,
        bookmark_url=bookmark_url,
        description=description if description else None,
        status='E',
        created_id=user_identifier,
        updated_id=user_identifier,
    )
    
    # 북마크와 카테고리 연결 (BookmarkMap 생성)
    BookmarkMap.objects.create(
        bookmark=bookmark,
        category=category,
        created_id=user_identifier,
    )
    
    return Response(
        {
            "status": "success",
            "bookmark": {
                "bookmark_sid": bookmark.bookmark_sid,
                "title": bookmark.title,
                "url": bookmark.bookmark_url,
                "description": bookmark.description or "",
            },
        },
        status=status.HTTP_201_CREATED,
    )


@extend_schema(
    summary="북마크 카테고리 삭제",
    description="북마크 카테고리를 삭제합니다 (soft delete). status를 'R'로 변경하고, 카테고리 내 모든 북마크도 함께 'R'로 변경합니다.",
    tags=["Bookmark"],
    responses={
        200: {
            "type": "object",
            "properties": {
                "status": {"type": "string", "example": "success"},
                "message": {"type": "string"},
            },
        },
        404: {"type": "object", "properties": {"error": {"type": "string"}}},
    },
)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def bookmark_category_delete_api(request, category_sid):
    """
    북마크 카테고리를 삭제합니다 (soft delete).
    status를 'R'로 변경하고, 연결된 북마크도 함께 'R'로 변경합니다.
    """
    user_identifier = _get_user_identifier(request.user)

    try:
        category = BookmarkCategory.objects.get(
            category_sid=category_sid,
            status='E',
            created_id=user_identifier,
        )
    except BookmarkCategory.DoesNotExist:
        return Response(
            {"status": "error", "error": "존재하지 않는 카테고리입니다."},
            status=status.HTTP_404_NOT_FOUND,
        )
    
    category_name = category.category_name
    
    # 카테고리 status를 'R'로 변경
    category.status = 'R'
    category.updated_id = user_identifier
    category.save()
    
    # 연결된 북마크들도 'R'로 변경
    bookmarks = Bookmark.objects.filter(
        bookmark_maps__category=category,
        status='E',
        created_id=user_identifier,
    ).distinct()
    bookmarks.update(status='R', updated_id=user_identifier)
    
    return Response(
        {
            "status": "success",
            "message": f"카테고리 '{category_name}'가 삭제되었습니다.",
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(
    summary="북마크 삭제",
    description="북마크를 삭제합니다 (soft delete). status를 'R'로 변경합니다.",
    tags=["Bookmark"],
    responses={
        200: {
            "type": "object",
            "properties": {
                "status": {"type": "string", "example": "success"},
                "message": {"type": "string"},
            },
        },
        404: {"type": "object", "properties": {"error": {"type": "string"}}},
    },
)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def bookmark_delete_api(request, bookmark_sid):
    """
    북마크를 삭제합니다 (soft delete).
    status를 'R'로 변경합니다.
    """
    user_identifier = _get_user_identifier(request.user)

    try:
        bookmark = Bookmark.objects.get(
            bookmark_sid=bookmark_sid,
            status='E',
            created_id=user_identifier,
        )
    except Bookmark.DoesNotExist:
        return Response(
            {"status": "error", "error": "존재하지 않는 북마크입니다."},
            status=status.HTTP_404_NOT_FOUND,
        )
    
    bookmark_title = bookmark.title
    
    # 북마크 status를 'R'로 변경
    bookmark.status = 'R'
    bookmark.updated_id = user_identifier
    bookmark.save()
    
    return Response(
        {
            "status": "success",
            "message": f"북마크 '{bookmark_title}'가 삭제되었습니다.",
        },
        status=status.HTTP_200_OK,
    )
