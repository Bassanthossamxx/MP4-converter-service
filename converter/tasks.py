import os
import subprocess
import threading
import shutil
import requests
import time
from django.conf import settings


def find_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    return ffmpeg or "ffmpeg"


def stream_downloader_to_ffmpeg(source_url: str, ffmpeg_process: subprocess.Popen):
    """
    FORCE continuous streaming:
    - Never stop on failed chunk
    - Always retry
    - Always move to next chunk once something is received
    """

    CHUNK_SIZE = 1024 * 1024 * 2  # 2MB
    offset = 0

    base_headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
        "Referer": "https://google.com/",
    }

    print("⏳ Start FORCE streaming:", source_url)

    while True:  
        # If FFmpeg died → stop
        if ffmpeg_process.poll() is not None:
            print("❌ FFmpeg ended, stopping downloader.")
            return

        headers = base_headers.copy()
        headers["Range"] = f"bytes={offset}-{offset + CHUNK_SIZE - 1}"

        try:
            r = requests.get(
                source_url,
                headers=headers,
                timeout=10,
            )

            # ❌ If status != 200/206 → skip and retry immediately
            if r.status_code not in (200, 206):
                print(f"❌ Bad chunk status {r.status_code}, retrying...")
                continue

            if not r.content:
                print("⚠ Empty chunk, retrying...")
                time.sleep(0.5)
                continue

            # Write into FFmpeg
            try:
                ffmpeg_process.stdin.write(r.content)
                ffmpeg_process.stdin.flush()
            except Exception as e:
                print("❌ FFmpeg closed stdin:", e)
                return

            offset += len(r.content)
            print(f"⬇ streamed {offset//1024//1024} MB")

        except Exception as e:
            # ❗ NEVER STOP → Always retry
            print("⚠ Network error, retrying:", e)
            time.sleep(1)
            continue


def generate_hls_stream(source_url: str, session: str):
    """
    Start FFmpeg that converts streamed data (stdin) to HLS on the fly.
    - Works with unstable network as long as chunks keep arriving.
    - Real-time HLS generation; player starts quickly.
    """
    ffmpeg = find_ffmpeg()

    hls_dir = os.path.join(settings.MEDIA_ROOT, "hls", session)
    os.makedirs(hls_dir, exist_ok=True)

    playlist_path = os.path.join(hls_dir, "index.m3u8")

    cmd = [
        ffmpeg, "-y",

        # Read from stdin (pipe)
        "-i", "pipe:0",

        # Video
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-profile:v", "baseline",
        "-level:v", "3.0",
        "-pix_fmt", "yuv420p",
        "-vf", "scale=426:240",
        "-b:v", "600k",
        "-maxrate", "600k",
        "-bufsize", "1200k",

        "-g", "48",
        "-keyint_min", "48",

        # Audio
        "-c:a", "aac",
        "-b:a", "64k",
        "-ac", "2",
        "-ar", "44100",

        "-fflags", "+genpts",

        # HLS (progressive VOD-like)
        "-f", "hls",
        "-hls_time", "4",
        "-hls_list_size", "0",                  # keep all segments
        "-start_number", "0",
        "-hls_flags", "independent_segments+append_list",
        playlist_path,
    ]

    print("🔥 Starting FFmpeg for session:", session)

    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=10**8
    )

    # log ffmpeg output for debug
    def log_ffmpeg(proc):
        for line in iter(proc.stderr.readline, b""):
            if not line:
                break
            print("FFMPEG:", line.decode(errors="ignore").strip())

    threading.Thread(target=log_ffmpeg, args=(process,), daemon=True).start()

    # start streaming thread
    threading.Thread(
        target=stream_downloader_to_ffmpeg,
        args=(source_url, process),
        daemon=True
    ).start()

    return hls_dir, playlist_path, process
