"""
테스트용 사용자 생성 스크립트

사용법:
    python django_app/manage.py shell < django_app/apps/dashboard/create_test_users.py
    
또는:
    python django_app/manage.py shell
    >>> exec(open('django_app/apps/dashboard/create_test_users.py').read())
"""
from apps.account.models import CustomUser
from django.contrib.auth import get_user_model

print("=" * 60)
print("테스트 사용자 생성")
print("=" * 60)

# 기존 사용자 확인
existing_users = CustomUser.objects.all()
print(f"\n📊 현재 사용자 수: {existing_users.count()}")

if existing_users.count() >= 2:
    print("\n✅ 이미 2명 이상의 사용자가 있습니다.")
    print("\n현재 사용자 목록:")
    for i, user in enumerate(existing_users[:5], 1):
        print(f"   {i}. {user.email} ({user.user_id})")
    print("\n추가 사용자를 생성하시겠습니까? (기본값: N)")
else:
    print("\n⚠️  사용자가 2명 미만입니다. 테스트용 사용자를 생성합니다.")

# 테스트 사용자 1 (사용자 A)
test_user_a_email = "test_user_a@example.com"
test_user_a_password = "test1234!"

user_a, created_a = CustomUser.objects.get_or_create(
    email=test_user_a_email,
    defaults={
        'full_name': '테스트 사용자 A',
        'status': 'E',
    }
)

if created_a:
    user_a.set_password(test_user_a_password)
    user_a.save()
    print(f"\n✅ 사용자 A 생성됨:")
    print(f"   이메일: {test_user_a_email}")
    print(f"   비밀번호: {test_user_a_password}")
    print(f"   User ID: {user_a.user_id}")
else:
    print(f"\n⚠️  사용자 A 이미 존재: {test_user_a_email}")
    if not user_a.check_password(test_user_a_password):
        user_a.set_password(test_user_a_password)
        user_a.save()
        print(f"   비밀번호를 '{test_user_a_password}'로 업데이트했습니다.")

# 테스트 사용자 2 (사용자 B)
test_user_b_email = "test_user_b@example.com"
test_user_b_password = "test1234!"

user_b, created_b = CustomUser.objects.get_or_create(
    email=test_user_b_email,
    defaults={
        'full_name': '테스트 사용자 B',
        'status': 'E',
    }
)

if created_b:
    user_b.set_password(test_user_b_password)
    user_b.save()
    print(f"\n✅ 사용자 B 생성됨:")
    print(f"   이메일: {test_user_b_email}")
    print(f"   비밀번호: {test_user_b_password}")
    print(f"   User ID: {user_b.user_id}")
else:
    print(f"\n⚠️  사용자 B 이미 존재: {test_user_b_email}")
    if not user_b.check_password(test_user_b_password):
        user_b.set_password(test_user_b_password)
        user_b.save()
        print(f"   비밀번호를 '{test_user_b_password}'로 업데이트했습니다.")

print("\n" + "=" * 60)
print("생성 완료!")
print("=" * 60)
print("\n📝 테스트 계정 정보:")
print(f"   사용자 A: {test_user_a_email} / {test_user_a_password}")
print(f"   사용자 B: {test_user_b_email} / {test_user_b_password}")
print("\n💡 이제 웹 UI에서 로그인하여 알림 기능을 테스트할 수 있습니다!")
print("\n✅ 테스트 사용자 생성 완료!")