import subprocess
import shutil
import os
import uuid
from django.conf import settings

def find_ffmpeg():
    path = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if path:
        return path

    env_path = os.environ.get("FFMPEG_PATH")
    if env_path and os.path.exists(env_path):
        return env_path

    common_paths = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\ffmpeg\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    ]

    for path in common_paths:
        if os.path.exists(path):
            return path

    return "ffmpeg"


def stream_to_mp4(source_url: str):
    """
    STREAMING MODE (NOT CONVERSION)
    - Always fast (<1 min)
    - No full file processing
    - iOS compatible
    - Returns a live MP4 byte stream (pipe)
    """

    ffmpeg = find_ffmpeg()

    # Verify ffmpeg exists before attempting to run
    if ffmpeg == "ffmpeg":
        # Check if it's actually in PATH
        if not shutil.which("ffmpeg") and not shutil.which("ffmpeg.exe"):
            raise FileNotFoundError(
                "ffmpeg not found. Please install ffmpeg and add it to your PATH, "
                "or set FFMPEG_PATH environment variable pointing to ffmpeg.exe"
            )
    elif not os.path.exists(ffmpeg):
        raise FileNotFoundError(
            f"ffmpeg not found at: {ffmpeg}. "
            "Please install ffmpeg and add it to your PATH, "
            "or set FFMPEG_PATH environment variable pointing to ffmpeg.exe"
        )

    cmd = [
        ffmpeg,
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "5",
        "-i", source_url,

        # NO re-encode video
        "-c:v", "copy",

        # Convert audio for iOS
        "-c:a", "aac",

        # Make it a streaming MP4
        "-movflags", "+frag_keyframe+empty_moov",

        # Output to STDOUT
        "-f", "mp4",
        "pipe:1"
    ]

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"Failed to execute ffmpeg: {e}. "
            "Please install ffmpeg from https://ffmpeg.org/download.html"
        )

    return process


def generate_hls_stream(source_url: str):
    """
    Live HLS streaming with real duration, seeking, and stability.
    Supports large files instantly.
    """
    ffmpeg = find_ffmpeg()

    hls_dir = os.path.join(settings.MEDIA_ROOT, "hls", uuid.uuid4().hex)
    os.makedirs(hls_dir, exist_ok=True)

    playlist_path = os.path.join(hls_dir, "index.m3u8")

    cmd = [
        ffmpeg,
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "5",
        "-i", source_url,

        # Safe re-encode fallback — ensures H.264 ALWAYS
        "-c:v", "h264",
        "-preset", "veryfast",

        # Audio always iOS compatible
        "-c:a", "aac",
        "-b:a", "128k",

        # HLS configs
        "-f", "hls",
        "-hls_time", "4",
        "-hls_list_size", "0",           # keep all segments => real duration
        "-hls_flags", "independent_segments",  # allow seeking anywhere

        playlist_path
    ]

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    return hls_dir, playlist_path, process
