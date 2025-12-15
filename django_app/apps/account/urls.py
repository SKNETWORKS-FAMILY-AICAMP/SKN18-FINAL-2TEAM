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
]
