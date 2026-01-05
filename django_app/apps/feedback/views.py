from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from .models import Feedback

CATEGORY_ALIASES = {
    "general": Feedback.Category.GENERAL,
    "g": Feedback.Category.GENERAL,
    "bug": Feedback.Category.BUG,
    "b": Feedback.Category.BUG,
    "feature": Feedback.Category.FEATURE,
    "f": Feedback.Category.FEATURE,
    "improvement": Feedback.Category.IMPROVEMENT,
    "i": Feedback.Category.IMPROVEMENT,
}


def _normalize_category(value: str) -> str:
    """
    Convert UI category strings to the single-character DB code.
    Defaults to GENERAL if parsing fails.
    """
    if not value:
        return Feedback.Category.GENERAL

    normalized = str(value).strip().lower()
    if not normalized:
        return Feedback.Category.GENERAL

    # Accept already-normalized single character values by returning uppercase
    if len(normalized) == 1 and normalized.upper() in dict(Feedback.Category.choices):
        return normalized.upper()

    return CATEGORY_ALIASES.get(normalized, Feedback.Category.GENERAL)


def _get_user_identifier(user) -> str:
    """Return a consistent identifier for audit columns."""
    if hasattr(user, "user_id"):
        return str(user.user_id)
    return str(user.pk)


@extend_schema(
    summary="피드백 저장",
    description="사용자가 입력한 피드백을 t_feedback 테이블에 저장합니다.",
    tags=["Feedback"],
    request={
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "피드백 카테고리 (general, bug, feature, improvement)",
                "example": "bug",
            },
            "feedback": {
                "type": "string",
                "description": "피드백 내용",
                "example": "노트에서 이미지가 보이지 않습니다.",
            },
        },
        "required": ["feedback"],
    },
    responses={
        201: {
            "type": "object",
            "properties": {
                "status": {"type": "string", "example": "success"},
                "message": {"type": "string", "example": "피드백이 저장되었습니다."},
                "feedback": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "category": {"type": "string", "example": "B"},
                        "category_label": {"type": "string", "example": "버그 리포트"},
                    },
                },
            },
        },
        400: {
            "type": "object",
            "properties": {"status": {"type": "string"}, "error": {"type": "string"}},
        },
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def submit_feedback(request):
    """
    피드백을 DB에 저장하는 API.
    """
    feedback_content = (request.data.get("feedback") or "").strip()
    if not feedback_content:
        return Response(
            {"status": "error", "error": "피드백 내용을 입력해주세요."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    category_value = _normalize_category(request.data.get("category"))
    user_identifier = _get_user_identifier(request.user)

    feedback_instance = Feedback.objects.create(
        category=category_value,
        feedback_content=feedback_content,
        created_id=user_identifier,
        updated_id=user_identifier,
    )

    return Response(
        {
            "status": "success",
            "message": "피드백이 저장되었습니다.",
            "feedback": {
                "id": feedback_instance.feedback_sid,
                "category": feedback_instance.category,
                "category_label": feedback_instance.get_category_display(),
            },
        },
        status=status.HTTP_201_CREATED,
    )
