"""
테스트 유저 생성 관리 명령어

사용법:
    python manage.py create_test_users
"""
from django.core.management.base import BaseCommand
from apps.account.models import CustomUser


class Command(BaseCommand):
    help = 'Create test users A and B for testing'

    def handle(self, *args, **options):
        """테스트 유저 A와 B 생성"""
        
        # 테스트 유저 A
        try:
            user_a, created = CustomUser.objects.get_or_create(
                email='testuser.a@example.com',
                defaults={
                    'full_name': '테스트 유저 A',
                    'company': '테스트 회사 A',
                    'status': CustomUser.Status.ENABLED,
                    'is_active': True,
                }
            )
            if created:
                user_a.set_password('test1234')
                user_a.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ 테스트 유저 A 생성 완료\n'
                        f'  - Email: {user_a.email}\n'
                        f'  - Password: test1234\n'
                        f'  - User ID: {user_a.user_id}\n'
                        f'  - Full Name: {user_a.full_name}'
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠ 테스트 유저 A가 이미 존재합니다: {user_a.email}'
                    )
                )
                # 비밀번호 업데이트
                user_a.set_password('test1234')
                user_a.save()
                self.stdout.write('  - 비밀번호를 "test1234"로 업데이트했습니다.')
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ 테스트 유저 A 생성 실패: {e}')
            )
            import traceback
            traceback.print_exc()
        
        self.stdout.write('')
        
        # 테스트 유저 B
        try:
            user_b, created = CustomUser.objects.get_or_create(
                email='testuser.b@example.com',
                defaults={
                    'full_name': '테스트 유저 B',
                    'company': '테스트 회사 B',
                    'status': CustomUser.Status.ENABLED,
                    'is_active': True,
                }
            )
            if created:
                user_b.set_password('test1234')
                user_b.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ 테스트 유저 B 생성 완료\n'
                        f'  - Email: {user_b.email}\n'
                        f'  - Password: test1234\n'
                        f'  - User ID: {user_b.user_id}\n'
                        f'  - Full Name: {user_b.full_name}'
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠ 테스트 유저 B가 이미 존재합니다: {user_b.email}'
                    )
                )
                # 비밀번호 업데이트
                user_b.set_password('test1234')
                user_b.save()
                self.stdout.write('  - 비밀번호를 "test1234"로 업데이트했습니다.')
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ 테스트 유저 B 생성 실패: {e}')
            )
            import traceback
            traceback.print_exc()
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== 생성 완료 ==='))
        self.stdout.write('\n로그인 정보:')
        self.stdout.write('유저 A:')
        self.stdout.write('  Email: testuser.a@example.com')
        self.stdout.write('  Password: test1234')
        self.stdout.write('\n유저 B:')
        self.stdout.write('  Email: testuser.b@example.com')
        self.stdout.write('  Password: test1234')
