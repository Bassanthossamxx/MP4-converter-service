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
        "-threads", "4",

        "-i", source_url,

        # Ultra fast video
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "fastdecode",
        "-profile:v", "baseline",
        "-level", "3.0",
        "-pix_fmt", "yuv420p",
        "-vf", "scale=426:240",
        "-b:v", "600k",
        "-maxrate", "600k",
        "-bufsize", "1200k",

        # keyframe every 2 seconds
        "-g", "48",
        "-keyint_min", "48",

        # audio low
        "-c:a", "aac",
        "-b:a", "64k",
        "-ac", "2",
        "-ar", "44100",

        # always start from 0.00
        "-fflags", "+genpts",
        "-reset_timestamps", "1",
        "-avoid_negative_ts", "make_zero",

        # HLS
        "-f", "hls",
        "-hls_time", "2",
        "-hls_list_size", "999999",       # <== keep full video!
        "-start_number", "0",
        "-hls_flags", "independent_segments",
        "-hls_segment_type", "mpegts",

        playlist_path,
    ]

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # --- Preload ~30 seconds without blocking ffmpeg output ---
    import time
    needed_segments = 30 // 2  # 2s segment → need 15 segments

    for _ in range(300):  # wait ~30s max, but usually ready in 3–6s
        if os.path.exists(playlist_path):
            data = open(playlist_path).read()
            if data.count(".ts") >= needed_segments:
                break
        time.sleep(0.1)

    return hls_dir, playlist_path, process
