import json
from pathlib import Path
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
from django.http import JsonResponse

from .forms import LoginForm, SignUpForm
from .models import CustomUser, UserSettings
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
    return render(request, 'accounts/profile.html', {
        'user': request.user,
    })


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
