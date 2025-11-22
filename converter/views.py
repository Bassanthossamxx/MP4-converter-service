import os
import time
from uuid import uuid4
from django.conf import settings
from django.http import StreamingHttpResponse, JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from .tasks import generate_hls_stream


class HLSSource(APIView):
    """
    GET /api/stream/hls?url=<remote_mkv_or_mp4>
    Returns:
    {
      "hls_playlist_stream": "http://host/api/stream/hls/<session>/index.m3u8"
    }
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        url = request.GET.get("url")
        if not url:
            return Response({"error": "Missing url"}, status=400)

        session = uuid4().hex

        hls_dir, playlist_path, process = generate_hls_stream(url, session)

        base = request.build_absolute_uri("/").rstrip("/")

        return Response({
            "hls_playlist_stream": f"{base}/api/stream/hls/{session}/index.m3u8"
        })


class HLSFileServe(APIView):
    """
    Serve HLS playlist (.m3u8) and segments (.ts)
    URL: /api/stream/hls/<session>/<filename>
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request, folder, filename):
        hls_path = os.path.join(settings.MEDIA_ROOT, "hls", folder, filename)

        waited = 0.0

        # Playlist usually appears after the first few chunks are processed
        max_wait = 30.0 if filename.endswith(".m3u8") else 60.0

        while not os.path.exists(hls_path) and waited < max_wait:
            time.sleep(0.5)
            waited += 0.5

        if not os.path.exists(hls_path):
            return JsonResponse({"error": "HLS file not ready"}, status=404)

        if filename.endswith(".m3u8"):
            content_type = "application/vnd.apple.mpegurl"
        else:
            content_type = "video/mp2t"

        f = open(hls_path, "rb")
        response = StreamingHttpResponse(f, content_type=content_type)

        response["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"

        return response
