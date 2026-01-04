from django.urls import path
from . import views

app_name = 'organization'

urlpatterns = [
    path('', views.organization_list_api, name='list'),
    path('create/', views.organization_create_api, name='create'),
    path('<int:organization_id>/', views.organization_delete_api, name='delete'),
    path('<int:organization_id>/members/', views.organization_add_member_api, name='add_member'),
    path('<int:organization_id>/members/<str:member_id>/', views.organization_remove_member_api, name='remove_member'),
    path('invitations/', views.invitation_list_api, name='invitations'),
    path('invitations/<uuid:invitation_id>/respond/', views.invitation_respond_api, name='invitation_respond'),
]

