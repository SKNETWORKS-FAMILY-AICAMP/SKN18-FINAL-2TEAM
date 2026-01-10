from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import logging

from apps.notification.models import Notification

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_list_api(request):
    """
    알림 목록 조회 API
    GET /api/notifications/
    """
    try:
        user = request.user
        user_id = getattr(user, 'user_id', None)
        
        if not user_id:
            return Response({
                'success': False,
                'error': '사용자 ID를 찾을 수 없습니다.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 미읽음 알림 개수
        unread_count = Notification.objects.filter(
            user_id=user_id,
            read_yn='N'
        ).count()
        
        # 최근 알림 목록 (최대 10개)
        limit = int(request.GET.get('limit', 10))
        notifications = Notification.objects.filter(
            user_id=user_id
        ).order_by('-created_at')[:limit]
        
        notifications_data = [
            {
                'id': notif.notification_sid,
                'title': notif.title,
                'message': notif.message,
                'time': notif.time,
                'unread': notif.unread,
                'notification_type': notif.notification_type,
                'related_sid': notif.related_sid,
                'created_at': notif.created_at.isoformat() if notif.created_at else None,
            }
            for notif in notifications
        ]
        
        return Response({
            'success': True,
            'unread_count': unread_count,
            'notifications': notifications_data,
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error fetching notifications: {str(e)}", exc_info=True)
        return Response({
            'success': False,
            'error': '알림 목록 조회 중 오류가 발생했습니다.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def notification_read_api(request, notification_id):
    """
    알림 읽음 처리 API
    POST /api/notifications/{notification_id}/read/
    """
    try:
        user = request.user
        notification = get_object_or_404(
            Notification,
            notification_sid=notification_id,
            user_id=user.user_id  # 본인의 알림만 읽을 수 있도록 검증
        )
        
        # 읽음 처리
        notification.read_yn = Notification.ReadStatus.READ
        notification.save()
        
        # 읽음 처리 후 최신 unread_count 계산
        unread_count = Notification.objects.filter(
            user_id=user.user_id,
            read_yn=Notification.ReadStatus.UNREAD
        ).count()
        
        logger.info(f"Notification {notification_id} marked as read by user {user.user_id}")
        
        return Response({
            'success': True,
            'message': '알림이 읽음 처리되었습니다.',
            'unread_count': unread_count  # 최신 unread_count 반환
        }, status=status.HTTP_200_OK)
        
    except Notification.DoesNotExist:
        return Response({
            'success': False,
            'error': '알림을 찾을 수 없습니다.'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error marking notification as read: {str(e)}")
        return Response({
            'success': False,
            'error': '알림 읽음 처리 중 오류가 발생했습니다.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
