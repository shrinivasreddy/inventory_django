from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("api/export_all", views.api_export_all, name="api_export_all"),
    path("api/<str:key>/spec", views.api_spec, name="api_spec"),
    path("api/<str:key>/records", views.api_records, name="api_records"),
    path("api/<str:key>/records/<int:rec_id>", views.api_record_detail, name="api_record_detail"),
    path("api/<str:key>/options", views.api_options, name="api_options"),
    path("api/<str:key>/export", views.api_export, name="api_export"),
]
