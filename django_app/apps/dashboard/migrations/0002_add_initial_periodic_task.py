# Generated manually for django_celery_beat initial schedule
from django.db import migrations


def create_initial_periodic_task(apps, schema_editor):
    """
    기존 CELERY_BEAT_SCHEDULE 설정을 데이터베이스에 마이그레이션
    check-schedule-reminders 작업을 5분마다 실행하는 스케줄 생성
    """
    try:
        # django_celery_beat 모델 가져오기
        IntervalSchedule = apps.get_model('django_celery_beat', 'IntervalSchedule')
        PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
        
        # 5분 간격 스케줄 생성 (이미 존재하면 가져오기)
        # 마이그레이션에서는 문자열 값 'minutes'를 직접 사용
        schedule, created = IntervalSchedule.objects.get_or_create(
            every=5,
            period='minutes',
        )
        
        # 주기적 작업 생성 또는 업데이트
        try:
            task = PeriodicTask.objects.get(name='check-schedule-reminders')
            # 이미 존재하는 경우 task 경로 업데이트 (notification 앱으로 이동했으므로)
            if task.task != 'apps.notification.tasks.check_schedule_reminders':
                task.task = 'apps.notification.tasks.check_schedule_reminders'
                task.interval = schedule
                task.save()
                print(f"Updated periodic task: {task.name} (task path updated to notification app)")
            else:
                print(f"Periodic task already exists with correct path: {task.name}")
        except PeriodicTask.DoesNotExist:
            # 새로 생성
            task = PeriodicTask.objects.create(
                name='check-schedule-reminders',
                task='apps.notification.tasks.check_schedule_reminders',
                interval=schedule,
                enabled=True,
                description='일정 리마인더 확인 작업 (5분마다 실행)',
            )
            print(f"Created periodic task: {task.name}")
            
    except LookupError:
        # django_celery_beat가 아직 마이그레이션되지 않은 경우 무시
        # (이 마이그레이션은 django_celery_beat 마이그레이션 이후에 실행됨)
        print("django_celery_beat models not found. Skipping initial periodic task creation.")
    except Exception as e:
        # 기타 오류 발생 시 로그만 출력하고 계속 진행
        print(f"Error creating periodic task: {e}")
        import traceback
        traceback.print_exc()


def reverse_initial_periodic_task(apps, schema_editor):
    """마이그레이션 롤백 시 주기적 작업 삭제"""
    try:
        PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
        IntervalSchedule = apps.get_model('django_celery_beat', 'IntervalSchedule')
        
        # 주기적 작업 삭제
        PeriodicTask.objects.filter(name='check-schedule-reminders').delete()
        
        # 5분 간격 스케줄 삭제 (다른 작업에서 사용하지 않는 경우에만)
        interval = IntervalSchedule.objects.filter(every=5, period='minutes').first()
        if interval and not PeriodicTask.objects.filter(interval=interval).exists():
            interval.delete()
            
    except LookupError:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0001_initial'),
        # django_celery_beat의 모든 마이그레이션이 완료되어야 함
        # 실제 배포 시 django_celery_beat 마이그레이션이 먼저 실행됨
        # Django가 자동으로 마이그레이션 순서를 관리하므로 '__first__' 사용
        ('django_celery_beat', '__first__'),
    ]

    operations = [
        migrations.RunPython(
            create_initial_periodic_task,
            reverse_initial_periodic_task,
        ),
    ]
