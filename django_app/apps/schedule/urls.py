from django.urls import path
from . import views

app_name = "schedule"
urlpatterns = [
    path("", views.index, name="schedule"),
    # API endpoints
    path("api/schedules/", views.schedule_list, name="schedule_list"),
    path("api/schedules/<int:schedule_id>/", views.schedule_detail, name="schedule_detail"),
    path("api/schedules/<int:schedule_id>/shared/", views.schedule_shared_users, name="schedule_shared_users"),
]
