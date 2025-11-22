# views.py
from django.http import StreamingHttpResponse, Http404, JsonResponse
from django.conf import settings
from rest_framework.views import APIView

from rest_framework.response import Response
import os
import logging
from .tasks import generate_hls_stream
from .tasks import stream_to_mp4

logger = logging.getLogger(__name__)


class StreamIOS(APIView):
    authentication_classes = []   # NO AUTH
    permission_classes = []       # NO AUTH

    def get(self, request):
        url = request.GET.get("url")
        if not url:
            return Response({"error": "Missing url"}, status=400)

        # Start ffmpeg streaming process
        process = stream_to_mp4(url)

        # Generator to stream bytes
        def generate():
            while True:
                chunk = process.stdout.read(4096)
                if not chunk:
                    break
                yield chunk

        # Return live MP4 stream
        response = StreamingHttpResponse(
            generate(),
            content_type="video/mp4"
        )

        response["Cache-Control"] = "no-cache"
        response["Accept-Ranges"] = "bytes"

        return response


class HLSSource(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        url = request.GET.get("url")
        if not url:
            return Response({"error": "Missing url"}, status=400)

        try:
            hls_dir, playlist_path, process = generate_hls_stream(url)
        except RuntimeError as e:
            logger.error(f"HLS generation failed: {e}")
            return Response({
                "error": "HLS generation failed",
                "detail": str(e),
                "mp4_fallback_stream": request.build_absolute_uri("/") + "api/stream/mp4?url=" + url
            }, status=500)
        except Exception as e:
            logger.error(f"Unexpected error in HLS generation: {e}")
            return Response({
                "error": "Internal server error",
                "detail": str(e)
            }, status=500)

        base = request.build_absolute_uri("/")

        return Response({
            "mp4_fallback_stream": base + "api/stream/mp4?url=" + url,
            "hls_playlist_stream": base + f"api/stream/hls/{os.path.basename(hls_dir)}/index.m3u8"
        })

class HLSFileServe(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, folder, filename):
        import time
        
        hls_path = os.path.join(
            settings.MEDIA_ROOT, "hls", folder, filename
        )

        # Wait up to 30 seconds for the file to appear (handles slow transcoding)
        max_wait = 30
        waited = 0
        while not os.path.exists(hls_path) and waited < max_wait:
            time.sleep(0.5)
            waited += 0.5

        if not os.path.exists(hls_path):
            logger.error(f"HLS file not found: {hls_path}")
            return JsonResponse(
                {
                    "detail": "HLS segment not found",
                    "folder": folder,
                    "filename": filename,
                    "expected_path": hls_path,
                    "media_root": str(settings.MEDIA_ROOT),
                    "hls_dir_exists": os.path.exists(os.path.join(settings.MEDIA_ROOT, "hls", folder)),
                },
                status=404,
            )

        # Correct MIME type for .m3u8 and .ts
        if filename.endswith(".m3u8"):
            content_type = "application/vnd.apple.mpegurl"
        else:
            content_type = "video/mp2t"

        return StreamingHttpResponse(
            open(hls_path, "rb"),
            content_type=content_type
        )
