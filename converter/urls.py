from django.urls import path
from .views import convert_view, status_view

urlpatterns = [
    path("convert", convert_view),
    path("status/<str:job_id>", status_view),
]
