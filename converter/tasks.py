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

        # Very important for MKV = faster detect
        "-analyzeduration", "100000",
        "-probesize", "100000",

        "-i", source_url,

        # ULTRA FAST iOS Compatible
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-profile:v", "baseline",
        "-level:v", "3.0",
        "-pix_fmt", "yuv420p",

        # lowest quality = fastest
        "-vf", "scale=426:240",
        "-b:v", "500k",
        "-maxrate", "500k",
        "-bufsize", "1000k",

        # Keyframe every 1 second
        "-g", "24",
        "-keyint_min", "24",

        # Audio fast encode
        "-c:a", "aac",
        "-b:a", "64k",
        "-ac", "2",
        "-ar", "44100",

        # ALWAYS start from 0:00
        "-reset_timestamps", "1",
        "-avoid_negative_ts", "make_zero",
        "-fflags", "+genpts",

        # HLS
        "-f", "hls",
        "-hls_time", "1",              # fastest possible startup
        "-hls_list_size", "12",        # ~12 sec sliding window
        "-start_number", "0",
        "-hls_flags", "independent_segments",
        "-hls_segment_type", "mpegts",

        playlist_path,
    ]

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # minimal wait: only wait for first segment (~0.2–0.5s)
    import time
    for _ in range(20):  # 2 seconds max
        if os.path.exists(playlist_path):
            if ".ts" in open(playlist_path).read():
                break
        time.sleep(0.1)

    return hls_dir, playlist_path, process
