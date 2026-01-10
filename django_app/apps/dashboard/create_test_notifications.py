"""
알림 테스트 데이터 생성 스크립트
Django shell에서 실행하거나 manage.py로 실행할 수 있습니다.

사용법:
    python django_app/manage.py shell
    >>> from apps.dashboard.create_test_notifications import create_test_notifications
    >>> create_test_notifications('user_id_here')
    
또는:
    python django_app/manage.py shell < django_app/apps/dashboard/create_test_notifications.py
"""
from django.utils import timezone
from datetime import timedelta
from apps.dashboard.models import Notification


def create_test_notifications(user_id, count=10):
    """
    테스트용 알림 데이터 생성
    
    Args:
        user_id: 알림을 생성할 사용자 ID
        count: 생성할 알림 개수 (기본값: 10)
    """
    notification_types = [
        ('E', '실험'),
        ('M', '미팅'),
        ('A', '분석'),
        ('S', '세미나'),
        ('N', '노트'),
        ('C', '채팅'),
        ('SYS', '시스템'),
    ]
    
    sample_notifications = [
        {
            'type': 'E',
            'title': 'PCR 실험 완료',
            'message': 'Customer Support Assistant 파이프라인이 완료되었습니다.',
        },
        {
            'type': 'M',
            'title': '일정 알림',
            'message': '주간 연구 진행 보고 미팅이 30분 후 시작됩니다.',
        },
        {
            'type': 'N',
            'title': '노트 공유',
            'message': 'Dr. John이 "CRISPR-Cas9 실험 결과 분석" 노트를 공유했습니다.',
        },
        {
            'type': 'C',
            'title': '채팅 답변',
            'message': 'EGFR 변이 단백질 질문에 대한 AI 분석이 완료되었습니다.',
        },
        {
            'type': 'SYS',
            'title': '시스템 업데이트',
            'message': 'AlphaFold3 모델이 업데이트되었습니다.',
        },
        {
            'type': 'A',
            'title': '분석 완료',
            'message': '단백질 서열 분석이 완료되었습니다. 결과를 확인해주세요.',
        },
        {
            'type': 'E',
            'title': '실험 진행 중',
            'message': '실험 #1234가 현재 진행 중입니다. (진행률: 75%)',
        },
        {
            'type': 'M',
            'title': '미팅 리마인더',
            'message': '오늘 오후 3시 연구팀 미팅이 예정되어 있습니다.',
        },
    ]
    
    created_count = 0
    now = timezone.now()
    
    for i in range(count):
        # 샘플 데이터를 순환하며 사용
        sample = sample_notifications[i % len(sample_notifications)]
        
        # 시간을 다양하게 설정 (최근부터 과거로)
        hours_ago = i * 2  # 0시간 전, 2시간 전, 4시간 전...
        created_at = now - timedelta(hours=hours_ago)
        
        # 일부는 읽음 처리
        read_yn = 'Y' if i % 3 == 0 else 'N'  # 3개 중 1개는 읽음
        
        notification = Notification.objects.create(
            user_id=user_id,
            notification_type=sample['type'],
            title=f"{sample['title']} ({i+1})",
            message=sample['message'],
            read_yn=read_yn,
            created_at=created_at,
        )
        created_count += 1
        print(f"✅ 알림 생성: {notification.title} (읽음: {read_yn})")
    
    print(f"\n🎉 총 {created_count}개의 테스트 알림이 생성되었습니다!")
    print(f"   사용자 ID: {user_id}")
    print(f"   미읽음 알림: {Notification.objects.filter(user_id=user_id, read_yn='N').count()}개")
    print(f"   읽음 알림: {Notification.objects.filter(user_id=user_id, read_yn='Y').count()}개")


if __name__ == '__main__':
    # 직접 실행 시 예시
    print("=" * 60)
    print("알림 테스트 데이터 생성 스크립트")
    print("=" * 60)
    print("\n사용법:")
    print("1. Django shell에서 실행:")
    print("   python django_app/manage.py shell")
    print("   >>> from apps.dashboard.create_test_notifications import create_test_notifications")
    print("   >>> create_test_notifications('your_user_id', 10)")
    print("\n2. 또는 아래 코드를 shell에서 직접 실행하세요.")
    print("\n" + "=" * 60)