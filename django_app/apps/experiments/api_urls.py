from django.urls import path
from . import views

app_name = "experiments_api"

urlpatterns = [
    # /api/experiments/ -> apps.experiments.views.experiments_api
    path("", views.experiments_api, name="api_experiments"),
    path(
        "uniprot/search/",
        views.uniprot_search_api,
        name="api_uniprot_search",
    ),
]
