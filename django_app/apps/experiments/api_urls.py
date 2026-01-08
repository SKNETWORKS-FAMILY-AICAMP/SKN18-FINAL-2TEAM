from django.urls import path
from . import views
from . import views_runpod
from . import views_uniprot

app_name = "experiments_api"

urlpatterns = [
    # /api/experiments/ -> apps.experiments.views.experiments_api
    path("", views.experiments_api, name="api_experiments"),
    path("runpod/rfdiffusion/", views_runpod.rfdiffusion_runpod_api, name="api_runpod_rfdiffusion"),
    path("runpod/health/", views_runpod.runpod_api_health, name="api_runpod_health"),
    path("runpod/run/", views_runpod.runpod_api_run, name="api_runpod_run"),
    path("uniprot/search/", views_uniprot.uniprot_search_api, name="api_uniprot_search"),
    path("uniprot/detail/<str:accession>/", views_uniprot.uniprot_detail_api, name="api_uniprot_detail"),
    path("<int:experiment_sid>/files/", views.experiment_result_files_api, name="api_experiment_files"),
    path("results/<int:result_sid>/file/", views.experiment_result_file_proxy, name="api_experiment_result_file_proxy"),

]
