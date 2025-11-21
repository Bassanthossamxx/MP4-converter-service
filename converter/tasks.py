import subprocess
import os
import logging
import shutil
from django.conf import settings
from .models import Mp4Cache, ConversionStatus

logger = logging.getLogger(__name__)

def find_ffmpeg():
    """Find FFmpeg executable, checking common Windows installation paths."""
    # First, try to find it in PATH
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path

    # Common Windows installation paths
    common_paths = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\ffmpeg\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    ]

    # Also check for installations with version numbers
    if os.path.exists(r"C:\ffmpeg"):
        for root, dirs, files in os.walk(r"C:\ffmpeg"):
            if "ffmpeg.exe" in files:
                return os.path.join(root, "ffmpeg.exe")

    # Check common paths
    for path in common_paths:
        if os.path.exists(path):
            return path

    # If not found, return "ffmpeg" and let it fail with proper error
    return "ffmpeg"

def convert_to_mp4(job_id):
    job = Mp4Cache.objects.get(job_id=job_id)
    source_url = job.original_url

    output_dir = os.path.join(settings.MEDIA_ROOT, "mp4")
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, f"{job_id}.mp4")

    # Find FFmpeg executable
    ffmpeg_exe = find_ffmpeg()
    logger.info(f"Using FFmpeg at: {ffmpeg_exe}")

    # More robust FFmpeg command with proper error handling
    cmd = [
        ffmpeg_exe,
        "-y",  # Overwrite output file if exists
        "-i", source_url,
        "-c:v", "libx264",  # Re-encode video to ensure compatibility
        "-preset", "fast",  # Faster encoding
        "-crf", "23",  # Quality (lower = better, 23 is default)
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        "-max_muxing_queue_size", "1024",  # Prevent muxing queue overflow
        output_path
    ]

    try:
        logger.info(f"Starting conversion for job {job_id}: {source_url}")

        # Run FFmpeg with timeout and capture output
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )

        # Check if output file exists and has size > 0
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            job.status = ConversionStatus.READY
            job.mp4_path = f"mp4/{job_id}.mp4"
            logger.info(f"Successfully converted job {job_id}")
        else:
            job.status = ConversionStatus.FAILED
            job.error_message = "Output file not created or empty"
            logger.error(f"Conversion failed for job {job_id}: Output file issue")

    except subprocess.TimeoutExpired as e:
        job.status = ConversionStatus.FAILED
        job.error_message = "Conversion timeout (>10 minutes)"
        logger.error(f"Timeout for job {job_id}: {str(e)}")

    except subprocess.CalledProcessError as e:
        job.status = ConversionStatus.FAILED
        error_output = e.stderr if e.stderr else str(e)
        job.error_message = f"FFmpeg error: {error_output[:500]}"  # Limit error message length
        logger.error(f"FFmpeg error for job {job_id}: {error_output}")

    except FileNotFoundError as e:
        job.status = ConversionStatus.FAILED
        job.error_message = "FFmpeg is not installed or not found in PATH. Please install FFmpeg: https://ffmpeg.org/download.html"
        logger.error(f"FFmpeg not found for job {job_id}: {str(e)}")

    except Exception as e:
        job.status = ConversionStatus.FAILED
        job.error_message = f"Unexpected error: {str(e)[:500]}"
        logger.error(f"Unexpected error for job {job_id}: {str(e)}", exc_info=True)

    finally:
        job.save()
        logger.info(f"Job {job_id} final status: {job.status}")
