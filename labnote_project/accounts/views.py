from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout
from .forms import CustomUserCreationForm

# 로그인 뷰
def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('/')  # 로그인 성공 시 이동할 페이지
    else:
        form = AuthenticationForm()
    
    return render(request, 'accounts/login.html', {'form': form})


# 로그아웃 뷰 (필요하면 사용)
def logout_view(request):
    logout(request)
    return redirect('accounts:login')


# 회원가입 뷰
def signup(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('accounts:login')
    else:
        form = CustomUserCreationForm()

    return render(request, 'accounts/signup.html', {'form': form})