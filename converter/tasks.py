import os
import shutil
import subprocess
from django.conf import settings


def find_ffmpeg():
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    return ffmpeg or "ffmpeg"


def generate_hls_stream(source_url: str, session: str):
    ffmpeg = find_ffmpeg()

    hls_dir = os.path.join(settings.MEDIA_ROOT, "hls", session)
    os.makedirs(hls_dir, exist_ok=True)

    playlist_path = os.path.join(hls_dir, "index.m3u8")

    cmd = [
        ffmpeg, "-y",
        "-i", source_url,            # ALWAYS start from 0:00

        "-c:v", "h264",
        "-preset", "veryfast",
        "-profile:v", "baseline",
        "-level", "3.1",
        "-pix_fmt", "yuv420p",
        "-vf", "scale=-2:720",
        "-b:v", "2000k",

        "-c:a", "aac",
        "-b:a", "128k",
        "-ac", "2",
        "-ar", "48000",

        "-f", "hls",
        "-hls_time", "3",
        "-hls_list_size", "5",
        "-start_number", "0",
        "-hls_flags", "independent_segments",
        "-hls_segment_type", "mpegts",

        playlist_path
    ]

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return hls_dir, playlist_path, process
