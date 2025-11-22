from django.http import StreamingHttpResponse, JsonResponse
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
import os
import time
import logging
from uuid import uuid4
from .tasks import generate_hls_stream

logger = logging.getLogger(__name__)


class HLSSource(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        url = request.GET.get("url")
        if not url:
            return Response({"error": "Missing url"}, status=400)

        # 🔥 NEW: SESSION PER PLAY -> always 0:00, no cross-device progress
        session_id = uuid4().hex

        hls_dir, master_playlist, process = generate_hls_stream(url, session=session_id)

        base = request.build_absolute_uri("/")

        return Response({
            "hls_playlist_stream": f"{base}api/stream/hls/{session_id}/master.m3u8"
        })


class HLSFileServe(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, folder, filename):
        hls_path = os.path.join(settings.MEDIA_ROOT, "hls", folder, filename)

        waited = 0
        while not os.path.exists(hls_path) and waited < 30:
            time.sleep(0.5)
            waited += 0.5

        if not os.path.exists(hls_path):
            return JsonResponse({"error": "HLS file not found"}, status=404)

        # TYPE
        if filename.endswith(".m3u8"):
            content_type = "application/vnd.apple.mpegurl"
        else:
            content_type = "video/mp2t"

        response = StreamingHttpResponse(open(hls_path, "rb"), content_type=content_type)

        # 🔥 HARD NO-CACHE
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"

        return response
