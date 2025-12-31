from django.urls import path
from . import views
from . import views_runpod

app_name = "experiments_api"

urlpatterns = [
    # /api/experiments/ -> apps.experiments.views.experiments_api
    path("", views.experiments_api, name="api_experiments"),
    path("runpod/pipeline", views_runpod.rfdiffusion_runpod_api, name="api_runpod_rfdiffusion"),
]
