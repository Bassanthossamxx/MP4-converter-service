# urls.py
from django.urls import path
from .views import StreamIOS , HLSSource , HLSFileServe

urlpatterns = [
    path("stream/mp4", StreamIOS.as_view()),
    path("stream/hls", HLSSource.as_view()),
    path("stream/hls/<str:folder>/<str:filename>", HLSFileServe.as_view()),
]
