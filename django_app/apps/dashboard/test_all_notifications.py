"""
알림 기능 통합 테스트 스크립트

사용법:
    python django_app/manage.py shell < django_app/apps/dashboard/test_all_notifications.py
    
또는:
    python django_app/manage.py shell
    >>> exec(open('django_app/apps/dashboard/test_all_notifications.py').read())
"""
from apps.account.models import CustomUser
from apps.dashboard.models import Notification
from apps.dashboard.notification_utils import (
    create_schedule_share_notification,
    create_organization_invitation_notification,
    create_schedule_reminder_notification,
    create_experiment_start_notification,
    create_experiment_tool_complete_notification,
    create_experiment_complete_notification,
    create_note_share_notification,
    get_user_display_name
)
from apps.schedule.models import Schedule, UserCalendar
from apps.notes.models import Note
from apps.experiments.models import Experiment
from django.utils import timezone
from datetime import timedelta

print("=" * 60)
print("알림 기능 통합 테스트 시작")
print("=" * 60)

# 사용자 준비
user_a = CustomUser.objects.first()

if not user_a:
    print("❌ 사용자가 없습니다. 먼저 사용자를 생성하세요.")
    print("   python manage.py createsuperuser")
    exit()

# 사용자 B 찾기 (최소 2명 필요)
user_b = CustomUser.objects.exclude(user_id=user_a.user_id).first()

if not user_b:
    print("⚠️  테스트를 위해 최소 2명의 사용자가 필요합니다.")
    print(f"   현재 사용자: {user_a.email if user_a else 'None'}")
    print("\n   사용자 B를 생성하거나,")
    print("   아래 명령어로 테스트 사용자를 생성하세요:")
    print("   python manage.py createsuperuser")
    print("\n   또는 단일 사용자로 알림 생성 테스트를 계속할까요? (Y/N)")
    print("   (단일 사용자는 일정 리마인더, 실험 알림만 테스트 가능)")
    
    # 단일 사용자 모드로 진행할지 확인
    import sys
    # 자동 실행 시에는 단일 사용자로 진행
    user_b = user_a
    print(f"   → 단일 사용자 모드로 진행 (사용자 A와 B가 동일)")
else:
    print(f"   ✅ 사용자 B 찾음: {user_b.email if user_b else user_b.user_id}")

print(f"\n✅ 사용자 A: {get_user_display_name(user_a)} ({user_a.user_id})")
print(f"✅ 사용자 B: {get_user_display_name(user_b)} ({user_b.user_id})")

# 테스트 전 알림 개수 확인
initial_count = Notification.objects.filter(user_id=user_b.user_id).count()
print(f"\n📊 초기 알림 개수 (사용자 B): {initial_count}")

# 1. 일정 공유 알림 테스트
print("\n1️⃣  일정 공유 알림 테스트")
try:
    schedule = Schedule.objects.filter(created_id=user_a.user_id).first()
    if schedule:
        create_schedule_share_notification(
            schedule_title=schedule.title,
            shared_user_id=user_b.user_id,
            owner_name=get_user_display_name(user_a),
            schedule_id=schedule.schedule_sid
        )
        print("   ✅ 일정 공유 알림 생성 성공")
    else:
        print("   ⚠️  일정이 없어서 스킵")
except Exception as e:
    print(f"   ❌ 실패: {e}")

# 2. 조직 초대 알림 테스트
print("\n2️⃣  조직 초대 알림 테스트")
try:
    create_organization_invitation_notification(
        organization_name="테스트 조직",
        invited_user_id=user_b.user_id,
        inviter_name=get_user_display_name(user_a),
        organization_id=1
    )
    print("   ✅ 조직 초대 알림 생성 성공")
except Exception as e:
    print(f"   ❌ 실패: {e}")

# 3. 일정 리마인더 알림 테스트
print("\n3️⃣  일정 리마인더 알림 테스트")
try:
    schedule = Schedule.objects.filter(created_id=user_a.user_id).first()
    if schedule:
        create_schedule_reminder_notification(
            schedule_title=schedule.title,
            user_id=user_a.user_id,
            schedule_id=schedule.schedule_sid,
            reminder_minutes=15
        )
        print("   ✅ 일정 리마인더 알림 생성 성공")
    else:
        print("   ⚠️  일정이 없어서 스킵")
except Exception as e:
    print(f"   ❌ 실패: {e}")

# 4. 실험 시작 알림 테스트
print("\n4️⃣  실험 시작 알림 테스트")
try:
    experiment = Experiment.objects.filter(created_id=user_a.user_id).first()
    if experiment:
        create_experiment_start_notification(
            experiment_title=experiment.pipeline_name,
            user_id=user_a.user_id,
            experiment_id=experiment.experiment_sid
        )
        print("   ✅ 실험 시작 알림 생성 성공")
    else:
        print("   ⚠️  실험이 없어서 스킵")
except Exception as e:
    print(f"   ❌ 실패: {e}")

# 5. 실험 도구 완료 알림 테스트
print("\n5️⃣  실험 도구 완료 알림 테스트")
try:
    experiment = Experiment.objects.filter(created_id=user_a.user_id).first()
    if experiment:
        create_experiment_tool_complete_notification(
            experiment_title=experiment.pipeline_name,
            tool_name="RFdiffusion",
            user_id=user_a.user_id,
            experiment_id=experiment.experiment_sid
        )
        print("   ✅ 실험 도구 완료 알림 생성 성공")
    else:
        print("   ⚠️  실험이 없어서 스킵")
except Exception as e:
    print(f"   ❌ 실패: {e}")

# 6. 실험 완료 알림 테스트
print("\n6️⃣  실험 완료 알림 테스트")
try:
    experiment = Experiment.objects.filter(created_id=user_a.user_id).first()
    if experiment:
        create_experiment_complete_notification(
            experiment_title=experiment.pipeline_name,
            user_id=user_a.user_id,
            experiment_id=experiment.experiment_sid
        )
        print("   ✅ 실험 완료 알림 생성 성공")
    else:
        print("   ⚠️  실험이 없어서 스킵")
except Exception as e:
    print(f"   ❌ 실패: {e}")

# 7. 노트 공유 알림 테스트
print("\n7️⃣  노트 공유 알림 테스트")
try:
    note = Note.objects.filter(created_id=user_a.user_id).first()
    if note:
        create_note_share_notification(
            note_title=note.title,
            shared_user_id=user_b.user_id,
            owner_name=get_user_display_name(user_a),
            note_id=note.note_sid
        )
        print("   ✅ 노트 공유 알림 생성 성공")
    else:
        print("   ⚠️  노트가 없어서 스킵")
except Exception as e:
    print(f"   ❌ 실패: {e}")

# 최종 알림 개수 확인
final_count = Notification.objects.filter(user_id=user_b.user_id).count()
new_notifications = final_count - initial_count

print("\n" + "=" * 60)
print("테스트 결과 요약")
print("=" * 60)
print(f"📊 사용자 B의 새 알림: {new_notifications}개")
print(f"📊 총 알림 개수: {final_count}개")

# 생성된 알림 목록
print("\n📋 생성된 알림 목록 (최근 10개):")
notifications = Notification.objects.filter(
    user_id=user_b.user_id
).order_by('-created_at')[:10]

for i, notif in enumerate(notifications, 1):
    status = "🔴" if notif.read_yn == 'N' else "⚪"
    print(f"   {i}. {status} [{notif.get_notification_type_display()}] {notif.title}")
    print(f"      {notif.message}")

print("\n✅ 테스트 완료!")