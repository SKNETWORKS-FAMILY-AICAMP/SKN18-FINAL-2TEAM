from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # 인증
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup_view, name='signup'),
    
    # 비밀번호
    path('password-reset/', views.password_reset_view, name='password_reset'),
    
    # 프로필
    path('profile/', views.profile_view, name='profile'),
    
    # Google OAuth (로그인 및 연동)
    path('google/login/', views.google_login_start, name='google_login_start'),
    path('google/login/callback/', views.google_profile_callback, name='google_profile_callback'),
    path('google/link/', views.google_profile_login, name='google_profile_login'),  # 프로필 연동용 (로그인한 사용자)
]
