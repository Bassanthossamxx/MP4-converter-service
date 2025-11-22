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
    Streams the remote MKV/MP4 to FFmpeg via stdin using Range requests.
    - Uses fixed-size chunks
    - Retries on network errors
    - Runs until whole file streamed or server stops responding
    """

    CHUNK_SIZE = 1024 * 1024 * 2  # 2MB per request
    offset = 0
    max_retries = 8

    base_headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
        "Referer": "https://google.com/",
    }

    # Try to get content length (for logging / debug)
    total_size = None
    try:
        head = requests.head(source_url, headers=base_headers, timeout=10)
        if head.status_code in (200, 206):
            total_size = int(head.headers.get("Content-Length", "0") or "0")
            print(f"📦 Remote size: {total_size} bytes")
    except Exception as e:
        print("⚠ HEAD failed:", e)

    print("⏳ Start streaming to FFmpeg:", source_url)

    while True:
        headers = base_headers.copy()
        headers["Range"] = f"bytes={offset}-{offset + CHUNK_SIZE - 1}"

        retries = 0

        while True:
            try:
                r = requests.get(
                    source_url,
                    headers=headers,
                    timeout=15,
                )

                if r.status_code not in (200, 206):
                    print("❌ Chunk request failed, status:", r.status_code)
                    return

                data = r.content
                if not data:
                    print("✔ No more data (EOF reached from server).")
                    try:
                        ffmpeg_process.stdin.close()
                    except Exception:
                        pass
                    return

                # Write chunk into ffmpeg stdin
                try:
                    ffmpeg_process.stdin.write(data)
                    ffmpeg_process.stdin.flush()
                except BrokenPipeError:
                    print("⚠ FFmpeg stdin closed (broken pipe).")
                    return

                offset += len(data)

                if total_size:
                    percent = offset * 100 / total_size
                    print(f"⬇ streamed {offset//1024//1024} MB ({percent:.1f}%)")
                    if offset >= total_size:
                        print("✔ Finished streaming whole file.")
                        try:
                            ffmpeg_process.stdin.close()
                        except Exception:
                            pass
                        return
                else:
                    print(f"⬇ streamed {offset//1024//1024} MB")

                # success → break retry loop
                break

            except Exception as e:
                retries += 1
                print(f"⚠ Network error on chunk (retry {retries}/{max_retries}):", e)
                if retries >= max_retries:
                    print("❌ Too many retries, aborting stream.")
                    try:
                        ffmpeg_process.stdin.close()
                    except Exception:
                        pass
                    return
                time.sleep(2)


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
