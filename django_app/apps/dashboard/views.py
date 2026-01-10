from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Count
import logging

from apps.experiments.models import Experiment
from apps.notes.models import Note
from apps.chat.models import Chat, ChatMessage
from apps.notification.models import Notification

logger = logging.getLogger(__name__)


@login_required
def index(request):
    """
    Dashboard 메인 페이지 뷰
    인증된 사용자만 접근 가능
    """
    user = request.user
    user_id = user.user_id
    
    # 디버깅: 로그인한 사용자 정보 확인
    logger.debug(f"Dashboard - Logged in user: {user.email}, user_id: {user_id}")

    # 실험 현황 (10건) - 현재 사용자가 생성한 실험만 조회
    recent_experiments = Experiment.objects.filter(
        created_id=user_id
    ).select_related().prefetch_related('tools').order_by('-created_at')[:10]
    
    # 디버깅: 실험 개수 확인
    logger.debug(f"Dashboard - Found {recent_experiments.count()} experiments for user_id: {user_id}")

    # 최근 연구 노트 (10건) - 현재 사용자가 생성한 노트만 조회
    recent_notes = Note.objects.filter(
        created_id=user_id,
        status='E'
    ).prefetch_related('tags').annotate(
        share_count=Count('shares'),
        comment_count=Count('comments')
    ).order_by('-created_at')[:10]
    
    # 디버깅: 노트 개수 확인
    logger.debug(f"Dashboard - Found {recent_notes.count()} notes for user_id: {user_id}")

    # 최근 AI 채팅 (10건) - 현재 사용자가 생성한 채팅만 조회
    # 첫 번째 사용자 메시지를 question으로 표시하기 위해 서브쿼리 사용
    recent_chats = Chat.objects.filter(
        created_id=user_id,
        status='E'
    ).order_by('-created_at')[:10]
    
    # 디버깅: 채팅 개수 및 상세 정보 확인
    # 주의: [:10] 슬라이싱 후에는 count()가 정확하지 않으므로 list로 변환 후 len() 사용
    chats_list = list(recent_chats)
    logger.debug(f"Dashboard - Found {len(chats_list)} chats for user_id: {user_id}")
    for chat in chats_list:
        logger.debug(f"Dashboard - Chat ID: {chat.chat_sid}, created_id: {chat.created_id}, title: {chat.title}")
    
    # 디버깅: 전체 채팅 개수 확인 (필터링 전)
    total_chats_count = Chat.objects.filter(status='E').count()
    user_chats_count = Chat.objects.filter(created_id=user_id, status='E').count()
    logger.debug(f"Dashboard - Total active chats: {total_chats_count}, User's chats: {user_chats_count}")

    # 각 채팅의 첫 번째 사용자 메시지를 가져와서 question 필드로 추가
    chats_with_question = []
    for chat in chats_list:
        first_user_message = ChatMessage.objects.filter(
            chat=chat,
            role='U'
        ).order_by('sort_order', 'created_at').first()
        
        # question이 없으면 title이나 preview를 사용
        if first_user_message:
            chat.question = first_user_message.content
        elif chat.title:
            chat.question = chat.title
        elif chat.preview:
            # preview가 너무 길면 앞부분만 사용
            chat.question = chat.preview[:100] + '...' if len(chat.preview) > 100 else chat.preview
        else:
            chat.question = '제목 없음'
        
        chats_with_question.append(chat)

    # notifications = [
    #     {
    #         "id": 1,
    #         "title": "PCR 실험 완료",
    #         "message": "Customer Support Assistant 파이프라인이 완료되었습니다.",
    #         "time": "5분 전",
    #         "unread": True,
    #     },
    #     {
    #         "id": 2,
    #         "title": "일정 알림",
    #         "message": "주간 연구 진행 보고 미팅이 30분 후 시작됩니다.",
    #         "time": "25분 전",
    #         "unread": True,
    #     },
    #     {
    #         "id": 3,
    #         "title": "노트 공유",
    #         "message": 'Dr. John이 "CRISPR-Cas9 실험 결과 분석" 노트를 공유했습니다.',
    #         "time": "1시간 전",
    #         "unread": False,
    #     },
    #     {
    #         "id": 4,
    #         "title": "채팅 답변",
    #         "message": "EGFR 변이 단백질 질문에 대한 AI 분석이 완료되었습니다.",
    #         "time": "2시간 전",
    #         "unread": False,
    #     },
    #     {
    #         "id": 5,
    #         "title": "시스템 업데이트",
    #         "message": "AlphaFold3 모델이 업데이트되었습니다.",
    #         "time": "1일 전",
    #         "unread": False,
    #     },
    # ]



    # 알림 조회 (최근 20건) - 현재 사용자의 알림만 조회
    notifications = Notification.objects.filter(
        user_id=user_id
    ).order_by('-created_at')[:20]
    
    # 템플릿에서 사용할 수 있도록 딕셔너리 형태로 변환
    notifications_list = []
    for notification in notifications:
        notifications_list.append({
            "id": notification.notification_sid,
            "title": notification.title,
            "message": notification.message,
            "time": notification.time,  # 모델의 @property 사용
            "unread": notification.unread,  # 모델의 @property 사용
        })
    
    # 미읽음 알림 개수
    unread_count = Notification.objects.filter(
        user_id=user_id,
        read_yn='N'
    ).count()

    context = {
        "important_schedules": [],  # Schedule.objects.filter(is_important=True).order_by('-start_date')[:5]
        "recent_experiments": recent_experiments,
        "recent_notes": recent_notes,
        "recent_chats": chats_with_question,
        "notifications": notifications_list,
        "unread_notifications_count": unread_count,
        # header_user is now provided by context processor, no need to pass it here
    }

    return render(request, "dashboard/dashboard.html", context)
