import json
import urllib.parse
from datetime import timedelta
from pathlib import Path
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import requests

from .forms import LoginForm, SignUpForm
from .models import CustomUser, UserSettings, LinkedAccount
from apps.core.utils.s3_utils import upload_file_to_s3, get_s3_url, generate_s3_key


def index(request):
    """
    루트 URL 처리
    - 인증됨: 대시보드로 리디렉트
    - 인증 안됨: 로그인 페이지로 리디렉트
    """
    if request.user.is_authenticated:
        return redirect('dashboard:dashboard')
    return redirect('accounts:login')


@csrf_protect
@require_http_methods(["GET", "POST"])
def login_view(request):
    """
    로그인 뷰
    """
    # 이미 로그인한 사용자는 대시보드로
    if request.user.is_authenticated:
        return redirect('dashboard:dashboard')
    
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            
            # Remember me 처리
            if not form.cleaned_data.get('remember_me'):
                # 브라우저 종료 시 세션 만료
                request.session.set_expiry(0)
            else:
                # 2주간 세션 유지
                request.session.set_expiry(60 * 60 * 24 * 14)
            
            login(request, user)
            
            # 마지막 로그인 시간 업데이트
            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])
            
            messages.success(request, f'환영합니다, {user.get_full_name()}님!')
            
            # next 파라미터가 있으면 해당 페이지로, 없으면 대시보드로
            next_url = request.GET.get('next') or request.POST.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('dashboard:dashboard')
        else:
            messages.error(request, '이메일 또는 비밀번호가 올바르지 않습니다.')
    else:
        form = LoginForm(request)
    
    return render(request, 'accounts/login.html', {
        'form': form,
        'next': request.GET.get('next', ''),
    })


@login_required
def logout_view(request):
    """
    로그아웃 뷰
    """
    logout(request)
    messages.info(request, '로그아웃되었습니다.')
    return redirect('accounts:login')


@csrf_protect
@require_http_methods(["GET", "POST"])
def signup_view(request):
    """
    회원가입 뷰
    """
    # 이미 로그인한 사용자는 대시보드로
    if request.user.is_authenticated:
        return redirect('dashboard:dashboard')
    
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # 기본 사용자 설정 생성
            UserSettings.objects.create(user=user)
            
            messages.success(request, '회원가입이 완료되었습니다. 로그인해주세요.')
            return redirect('accounts:login')
        else:
            messages.error(request, '입력 정보를 확인해주세요.')
    else:
        form = SignUpForm()
    
    return render(request, 'accounts/signup.html', {
        'form': form,
    })


@csrf_protect
@require_http_methods(["GET", "POST"])
def password_reset_view(request):
    """
    비밀번호 재설정 요청 뷰
    """
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = CustomUser.objects.get(email=email)
            # TODO: 이메일 발송 로직 구현
            messages.success(request, '비밀번호 재설정 링크가 이메일로 발송되었습니다.')
        except CustomUser.DoesNotExist:
            # 보안을 위해 같은 메시지 표시
            messages.success(request, '비밀번호 재설정 링크가 이메일로 발송되었습니다.')
        return redirect('accounts:login')
    
    return render(request, 'accounts/password_reset.html')


@login_required
def profile_view(request):
    """
    프로필 뷰
    """
    # 연동된 계정 정보 가져오기
    linked_accounts = LinkedAccount.objects.filter(user=request.user)
    google_account = linked_accounts.filter(provider='google').first()
    
    return render(request, 'accounts/profile.html', {
        'user': request.user,
        'linked_accounts': linked_accounts,
        'google_account': google_account,
    })


@login_required
def organization_view(request):
    """
    조직 관리 뷰 (organization 앱의 뷰로 리디렉션)
    """
    from apps.organization.views import organization_view as org_view
    return org_view(request)


@login_required
@require_http_methods(["GET", "PATCH"])
def profile_api(request):
    """
    프로필 API 엔드포인트
    GET /api/profile/ - 프로필 정보 조회
    PATCH /api/profile/ - 프로필 정보 업데이트
    """
    if request.method == 'GET':
        user = request.user
        return JsonResponse({
            'success': True,
            'data': {
                'display_name': user.full_name or user.email,
                'full_name': user.full_name or '',
                'email': user.email,
                'phone_number': user.phone_number or '',
                'organization': user.company or '',
            }
        })
    
    elif request.method == 'PATCH':
        try:
            data = json.loads(request.body)
            user = request.user
            
            # 업데이트할 필드들
            if 'display_name' in data:
                # display_name은 full_name으로 저장
                user.full_name = data['display_name']
            if 'full_name' in data:
                user.full_name = data['full_name']
            if 'email' in data:
                # 이메일 중복 체크
                new_email = data['email']
                if new_email != user.email:
                    if CustomUser.objects.filter(email=new_email).exists():
                        return JsonResponse({
                            'success': False,
                            'error': '이미 사용 중인 이메일입니다.'
                        }, status=400)
                    user.email = new_email
            if 'phone_number' in data:
                user.phone_number = data['phone_number']
            if 'organization' in data:
                user.company = data['organization']
            
            user.save()
            
            return JsonResponse({
                'success': True,
                'message': '프로필이 업데이트되었습니다.'
            })
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': '잘못된 JSON 형식입니다.'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


@login_required
@require_http_methods(["POST"])
def profile_avatar_api(request):
    """
    프로필 아바타 업로드 API
    POST /api/profile/avatar/ - 프로필 사진 업로드
    S3 저장소: s3://skn18-file-uploads/profiles/{user_id}/{email}.{확장자}
    """
    if 'avatar' not in request.FILES:
        return JsonResponse({
            'success': False,
            'error': '파일이 제공되지 않았습니다.'
        }, status=400)
    
    file = request.FILES['avatar']
    
    # 파일 크기 검증 (5MB)
    if file.size > 5 * 1024 * 1024:
        return JsonResponse({
            'success': False,
            'error': '파일 크기는 5MB 이하여야 합니다.'
        }, status=400)
    
    # 파일 타입 검증
    if not file.content_type.startswith('image/'):
        return JsonResponse({
            'success': False,
            'error': '이미지 파일만 업로드할 수 있습니다.'
        }, status=400)
    
    try:
        user = request.user
        
        # 파일 확장자 추출
        file_name = file.name
        file_ext = Path(file_name).suffix.lower()
        
        # 지원하는 이미지 확장자 확인
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        if file_ext not in allowed_extensions:
            return JsonResponse({
                'success': False,
                'error': f'지원하지 않는 파일 형식입니다. 지원 형식: {", ".join(allowed_extensions)}'
            }, status=400)
        
        # S3 키 생성: profiles/{user_id}/{email}.{확장자}
        s3_key = generate_s3_key(
            prefix='profiles',
            user_id=str(user.user_id),
            filename=file_name,
            use_email=True,
            email=user.email
        )
        
        # S3에 파일 업로드 (ACL 없이, 버킷 정책으로 접근 제어)
        success, error_msg = upload_file_to_s3(
            file=file,
            s3_key=s3_key,
            content_type=file.content_type,
            acl=None  # ACL 비활성화된 버킷이므로 None
        )
        
        if not success:
            return JsonResponse({
                'success': False,
                'error': error_msg or '파일 업로드에 실패했습니다.'
            }, status=500)
        
        # S3 URL 생성
        s3_url = get_s3_url(s3_key)
        
        # 사용자 모델의 img_url 필드 업데이트 (zs_user.img_url)
        user.img_url = s3_url
        user.save(update_fields=['img_url'])  # 특정 필드만 업데이트하여 성능 최적화
        
        return JsonResponse({
            'success': True,
            'avatar_url': s3_url,
            'message': '프로필 사진이 업로드되었습니다.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET", "DELETE"])
def linked_accounts_api(request):
    """
    연동된 계정 API
    GET /api/profile/linked-accounts/ - 연동된 계정 목록 조회
    DELETE /api/profile/linked-accounts/?provider=google - 연동 해제
    """
    if request.method == 'GET':
        user = request.user
        linked_accounts = LinkedAccount.objects.filter(user=user)
        
        accounts_data = []
        for account in linked_accounts:
            accounts_data.append({
                'provider': account.provider,
                'provider_display_name': account.get_provider_display(),
                'provider_user_id': account.provider_user_id,
                'created_at': account.created_at.isoformat() if account.created_at else None,
                'is_token_expired': account.is_token_expired(),
            })
        
        return JsonResponse({
            'success': True,
            'linked_accounts': accounts_data
        })
    
    elif request.method == 'DELETE':
        provider = request.GET.get('provider')
        if not provider:
            return JsonResponse({
                'success': False,
                'error': 'provider 파라미터가 필요합니다.'
            }, status=400)
        
        try:
            linked_account = LinkedAccount.objects.get(user=request.user, provider=provider)
            provider_display = linked_account.get_provider_display()
            linked_account.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'{provider_display} 계정 연동이 해제되었습니다.'
            })
        except LinkedAccount.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': '연동된 계정을 찾을 수 없습니다.'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


def google_login_start(request):
    """
    Google OAuth 로그인 시작 (로그인하지 않은 사용자도 사용 가능)
    """
    # 동적으로 redirect_uri 생성 (request의 호스트 사용)
    scheme = 'https' if request.is_secure() else 'http'
    host = request.get_host()
    redirect_uri = f"{scheme}://{host}/accounts/google/login/callback/"
    
    # 환경 변수로 설정된 값이 있으면 우선 사용
    if settings.GOOGLE_REDIRECT_URIS.get('profile'):
        env_uri = settings.GOOGLE_REDIRECT_URIS['profile']
        if env_uri.startswith('http'):
            redirect_uri = env_uri
    
    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",  # 프로필 연동용 스코프
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "select_account",  # 계정 선택 화면 표시
    }
    
    # 로그인 상태에 따라 state 설정
    if request.user.is_authenticated:
        params["state"] = "profile"  # 연동용
    else:
        params["state"] = "login"  # 로그인용
    
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    return redirect(url)


@login_required
def google_profile_login(request):
    """
    프로필 연동용 Google OAuth 시작 (로그인한 사용자 전용)
    """
    # 이미 연동되어 있는지 확인
    if LinkedAccount.objects.filter(user=request.user, provider='google').exists():
        messages.info(request, '이미 Google 계정이 연동되어 있습니다.')
        return redirect('accounts:profile')
    
    # google_login_start로 리디렉션 (state=profile로 처리됨)
    return google_login_start(request)


def google_profile_callback(request):
    """
    Google OAuth 콜백 (로그인 및 연동 모두 처리)
    state 파라미터로 구분:
    - "login": 로그인하지 않은 사용자의 Google 로그인
    - "profile": 로그인한 사용자의 계정 연동
    """
    if "error" in request.GET:
        error = request.GET.get("error")
        state = request.GET.get("state", "")
        if state == "login":
            messages.error(request, f'Google 로그인에 실패했습니다: {error}')
            return redirect('accounts:login')
        else:
            messages.error(request, f'Google 계정 연동에 실패했습니다: {error}')
            return redirect('accounts:profile')
    
    code = request.GET.get("code")
    if not code:
        state = request.GET.get("state", "")
        if state == "login":
            messages.error(request, '인증 코드를 받지 못했습니다.')
            return redirect('accounts:login')
        else:
            messages.error(request, '인증 코드를 받지 못했습니다.')
            return redirect('accounts:profile')
    
    state = request.GET.get("state", "")
    
    # 동적으로 redirect_uri 생성 (request의 호스트 사용)
    scheme = 'https' if request.is_secure() else 'http'
    host = request.get_host()
    redirect_uri = f"{scheme}://{host}/accounts/google/login/callback/"
    
    # 환경 변수로 설정된 값이 있으면 우선 사용
    if settings.GOOGLE_REDIRECT_URIS.get('profile'):
        env_uri = settings.GOOGLE_REDIRECT_URIS['profile']
        if env_uri.startswith('http'):
            redirect_uri = env_uri
    
    try:
        # 토큰 교환
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        
        res = requests.post(token_url, data=data, timeout=10)
        res.raise_for_status()
        token_info = res.json()
        
        access_token = token_info.get("access_token")
        if not access_token:
            if state == "login":
                messages.error(request, '액세스 토큰을 받지 못했습니다.')
                return redirect('accounts:login')
            else:
                messages.error(request, '액세스 토큰을 받지 못했습니다.')
                return redirect('accounts:profile')
        
        # 사용자 정보 가져오기
        user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        user_info_res = requests.get(user_info_url, headers=headers, timeout=10)
        user_info_res.raise_for_status()
        user_info = user_info_res.json()
        
        google_email = user_info.get('email', '')
        google_user_id = user_info.get('id', '')
        
        # 토큰 정보 추출
        refresh_token = token_info.get('refresh_token', '')
        expires_in = token_info.get('expires_in', 3600)
        token_expires_at = timezone.now() + timedelta(seconds=expires_in) if expires_in else None
        scope = token_info.get('scope', '')
        
        # state에 따라 처리 분기
        if state == "login":
            # 로그인 처리
            # 1. LinkedAccount에서 Google user_id로 사용자 찾기
            linked_account = LinkedAccount.objects.filter(
                provider='google',
                provider_user_id=google_user_id
            ).first()
            
            if linked_account:
                # 연동된 계정이 있으면 해당 사용자로 로그인
                user = linked_account.user
                login(request, user)
                messages.success(request, f'Google 계정({google_email})으로 로그인했습니다.')
                return redirect('dashboard:dashboard')
            
            # 2. Google 이메일로 기존 사용자 찾기
            try:
                user = CustomUser.objects.get(email=google_email)
                # 기존 사용자에 Google 계정 연동
                LinkedAccount.objects.update_or_create(
                    user=user,
                    provider='google',
                    defaults={
                        'provider_user_id': google_user_id,
                        'access_token': access_token,
                        'refresh_token': refresh_token,
                        'token_expires_at': token_expires_at,
                        'scope': scope,
                    }
                )
                login(request, user)
                messages.success(request, f'Google 계정({google_email})이 기존 계정과 연결되었습니다.')
                return redirect('dashboard:dashboard')
            except CustomUser.DoesNotExist:
                # 3. 새 사용자 생성
                # Google 이메일을 사용하여 새 계정 생성
                user = CustomUser.objects.create_user(
                    email=google_email,
                    password=None,  # OAuth 사용자는 비밀번호 없음
                    full_name=user_info.get('name', ''),
                )
                # OAuth 사용자는 비밀번호를 사용할 수 없도록 설정
                user.set_unusable_password()
                user.save()
                
                # LinkedAccount 생성
                LinkedAccount.objects.create(
                    user=user,
                    provider='google',
                    provider_user_id=google_user_id,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    token_expires_at=token_expires_at,
                    scope=scope,
                )
                
                login(request, user)
                messages.success(request, f'Google 계정({google_email})으로 새 계정이 생성되었습니다.')
                return redirect('dashboard:dashboard')
        
        else:
            # 연동 처리 (로그인한 사용자)
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            
            # 이미 다른 사용자에게 연동되어 있는지 확인
            existing_linked = LinkedAccount.objects.filter(
                provider='google',
                provider_user_id=google_user_id
            ).exclude(user=request.user).first()
            
            if existing_linked:
                messages.error(request, f'이 Google 계정({google_email})은 이미 다른 계정에 연동되어 있습니다.')
                return redirect('accounts:profile')
            
            # LinkedAccount에 저장
            LinkedAccount.objects.update_or_create(
                user=request.user,
                provider='google',
                defaults={
                    'provider_user_id': google_user_id,
                    'access_token': access_token,
                    'refresh_token': refresh_token,
                    'token_expires_at': token_expires_at,
                    'scope': scope,
                }
            )
            
            messages.success(request, 'Google 계정이 성공적으로 연동되었습니다.')
            return redirect('accounts:profile')
        
    except requests.RequestException as e:
        if state == "login":
            messages.error(request, f'Google API 호출 중 오류가 발생했습니다: {str(e)}')
            return redirect('accounts:login')
        else:
            messages.error(request, f'Google API 호출 중 오류가 발생했습니다: {str(e)}')
            return redirect('accounts:profile')
    except Exception as e:
        if state == "login":
            messages.error(request, f'로그인 중 오류가 발생했습니다: {str(e)}')
            return redirect('accounts:login')
        else:
            messages.error(request, f'계정 연동 중 오류가 발생했습니다: {str(e)}')
            return redirect('accounts:profile')


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def settings_api(request):
    """사용자 설정 조회 및 업데이트 API"""
    user = request.user
    
    # UserSettings 가져오기 또는 생성
    user_settings, created = UserSettings.objects.get_or_create(user=user)
    
    if request.method == 'GET':
        return Response({
            'status': 'success',
            'settings': {
                'notifications': user_settings.notifications,
                'email_alerts': user_settings.email_alerts,
                'dark_mode': user_settings.dark_mode,
                'language': user_settings.language,
                'notes_view_mode': user_settings.notes_view_mode,
            }
        }, status=status.HTTP_200_OK)
    
    elif request.method == 'PUT':
        data = request.data
        
        # 업데이트할 필드만 처리
        if 'notes_view_mode' in data:
            notes_view_mode = data.get('notes_view_mode', '').strip()
            if notes_view_mode in ['card', 'table']:
                user_settings.notes_view_mode = notes_view_mode
        
        if 'notifications' in data:
            user_settings.notifications = data.get('notifications', user_settings.notifications)
        if 'email_alerts' in data:
            user_settings.email_alerts = data.get('email_alerts', user_settings.email_alerts)
        if 'dark_mode' in data:
            user_settings.dark_mode = data.get('dark_mode', user_settings.dark_mode)
        if 'language' in data:
            user_settings.language = data.get('language', user_settings.language)
        
        user_settings.save()
        
        return Response({
            'status': 'success',
            'message': '설정이 저장되었습니다.',
            'settings': {
                'notifications': user_settings.notifications,
                'email_alerts': user_settings.email_alerts,
                'dark_mode': user_settings.dark_mode,
                'language': user_settings.language,
                'notes_view_mode': user_settings.notes_view_mode,
            }
        }, status=status.HTTP_200_OK)
