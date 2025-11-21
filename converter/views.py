from .models import Mp4Cache, ConversionStatus
from .utils import generate_job_id
from .tasks import convert_to_mp4
import threading
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

def run_in_background(job_id):
    convert_to_mp4(job_id)

@api_view(["POST"])
def convert_view(request):
    # For POST requests, use DRF's request.data to get JSON/body params
    url = request.data.get("url")

    if not url:
        return Response({"error": "Missing url"}, status=status.HTTP_400_BAD_REQUEST)

    # Check cache
    job = Mp4Cache.objects.filter(original_url=url).first()

    # If cached and ready → return MP4 immediately
    if job and job.status == ConversionStatus.READY:
        return Response({
            "status": "ready",
            "mp4_url": request.build_absolute_uri("/media/" + job.mp4_path),
        }, status=status.HTTP_200_OK)

    # If exists but processing/failed → return status
    if job:
        response_data = {
            "status": job.status,
            "job_id": job.job_id,
            "mp4_url": None,
        }
        if job.status == ConversionStatus.FAILED and job.error_message:
            response_data["error"] = job.error_message
        return Response(response_data, status=status.HTTP_200_OK)

    # Create a new job
    job_id = generate_job_id()
    Mp4Cache.objects.create(
        original_url=url,
        job_id=job_id,
        status=ConversionStatus.PENDING,
    )

    # Start conversion in BACKGROUND without blocking API
    threading.Thread(
        target=run_in_background,
        args=(job_id,),
        daemon=True,
    ).start()

    return Response({
        "status": "processing",
        "job_id": job_id,
        "mp4_url": None,
    }, status=status.HTTP_201_CREATED)

@api_view(["GET"])
def status_view(request, job_id):
    job = Mp4Cache.objects.filter(job_id=job_id).first()

    if not job:
        return Response({"error": "Job not found"}, status=status.HTTP_404_NOT_FOUND)

    if job.status == ConversionStatus.READY:
        return Response({
            "status": "ready",
            "mp4_url": request.build_absolute_uri("/media/" + job.mp4_path),
        }, status=status.HTTP_200_OK)

    response_data = {
        "status": job.status,
        "mp4_url": None,
    }
    if job.status == ConversionStatus.FAILED and job.error_message:
        response_data["error"] = job.error_message

    return Response(response_data, status=status.HTTP_200_OK)
