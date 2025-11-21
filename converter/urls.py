# urls.py
from django.urls import path
from .views import StreamIOS , HLSSource , HLSFileServe

urlpatterns = [
    path("stream/ios", StreamIOS.as_view()),
    path("hls", HLSSource.as_view()),
    path("hls/<str:folder>/<str:filename>", HLSFileServe.as_view()),
]
