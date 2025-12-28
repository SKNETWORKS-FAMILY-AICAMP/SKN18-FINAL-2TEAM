"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path
from apps.account.views import index as root_index

urlpatterns = [
    # 루트 URL - 인증 상태에 따라 리디렉트
    path("", root_index, name="root"),
    
    # 인증 (accounts namespace)
    path("accounts/", include("apps.account.urls")),
    
    # 앱 URL
    path("dashboard/", include("apps.dashboard.urls")),
    path("chat/", include("apps.chat.urls")),
    path("schedule/", include("apps.schedule.urls")),
    path("experiments/", include("apps.experiments.urls")),
    path("notes/", include("apps.notes.urls")),
    
    # API endpoints
    path("api/experiments/", include("apps.experiments.api_urls")),
    path("api/notes/", include("apps.notes.api_urls")),
    
    # 관리자
    path("admin/", admin.site.urls),
]
