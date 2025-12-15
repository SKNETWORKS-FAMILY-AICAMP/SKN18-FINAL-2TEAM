from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def index(request):
    """
    Dashboard 메인 페이지 뷰
    인증된 사용자만 접근 가능
    """
    # TODO: 모델이 구현되면 실제 데이터를 가져오도록 수정
    # from apps.schedule.models import Schedule
    # from apps.experiments.models import Experiment
    # from apps.notes.models import Note
    # from apps.chat.models import Chat

    notifications = [
        {
            "id": 1,
            "title": "PCR 실험 완료",
            "message": "Customer Support Assistant 파이프라인이 완료되었습니다.",
            "time": "5분 전",
            "unread": True,
        },
        {
            "id": 2,
            "title": "일정 알림",
            "message": "주간 연구 진행 보고 미팅이 30분 후 시작됩니다.",
            "time": "25분 전",
            "unread": True,
        },
        {
            "id": 3,
            "title": "노트 공유",
            "message": 'Dr. John이 "CRISPR-Cas9 실험 결과 분석" 노트를 공유했습니다.',
            "time": "1시간 전",
            "unread": False,
        },
        {
            "id": 4,
            "title": "채팅 답변",
            "message": "EGFR 변이 단백질 질문에 대한 AI 분석이 완료되었습니다.",
            "time": "2시간 전",
            "unread": False,
        },
        {
            "id": 5,
            "title": "시스템 업데이트",
            "message": "AlphaFold3 모델이 업데이트되었습니다.",
            "time": "1일 전",
            "unread": False,
        },
    ]

    context = {
        "important_schedules": [],  # Schedule.objects.filter(is_important=True).order_by('-start_date')[:5]
        "recent_experiments": [],  # Experiment.objects.order_by('-created_at')[:10]
        "recent_notes": [],  # Note.objects.order_by('-created_at')[:10]
        "recent_chats": [],  # Chat.objects.order_by('-created_at')[:10]
        "notifications": notifications,
        "unread_notifications_count": sum(
            1 for notification in notifications if notification["unread"]
        ),
        # header_user is now provided by context processor, no need to pass it here
    }

    return render(request, "dashboard/dashboard.html", context)
