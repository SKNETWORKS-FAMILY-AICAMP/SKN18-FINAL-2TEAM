from django.urls import path

from . import views

app_name = "feedback_api"

urlpatterns = [
    path("", views.submit_feedback, name="submit_feedback"),
]
