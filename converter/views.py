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

        session_id = uuid4().hex

        hls_dir, index_playlist, process = generate_hls_stream(
            url,
            session=session_id
        )

        base = request.build_absolute_uri("/").rstrip("/")

        return Response({
            "hls_playlist_stream": f"{base}/api/stream/hls/{session_id}/index.m3u8"
        })

class HLSFileServe(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, folder, filename):
        hls_path = os.path.join(settings.MEDIA_ROOT, "hls", folder, filename)

        # Wait until file exists + ready
        waited = 0
        while not os.path.exists(hls_path) and waited < 10:
            time.sleep(0.2)
            waited += 0.2

        if not os.path.exists(hls_path):
            return JsonResponse({"error": "HLS file not found"}, status=404)

        if filename.endswith(".m3u8"):
            content_type = "application/vnd.apple.mpegurl"
        else:
            content_type = "video/mp2t"

        response = StreamingHttpResponse(open(hls_path, "rb"), content_type=content_type)

        # iOS important headers
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        response["X-Accel-Buffering"] = "no"

        return response
