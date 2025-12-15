from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone

from .forms import LoginForm, SignUpForm
from .models import CustomUser, UserSettings


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
