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

        # Re-encode video for consistent, reasonable quality and lower bitrate
        "-c:v", "h264",
        "-preset", "veryfast",      # favor speed over compression
        "-vf", "scale=-2:720",      # limit height to 720p, keep aspect
        "-b:v", "2500k",            # target ~2.5 Mbps video bitrate

        # Convert audio for iOS and control bitrate
        "-c:a", "aac",
        "-b:a", "128k",

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
    import os, uuid, subprocess, time
    from django.conf import settings

    ffmpeg = find_ffmpeg()

    # Unique HLS folder
    hls_dir = os.path.join(settings.MEDIA_ROOT, "hls", uuid.uuid4().hex)
    os.makedirs(hls_dir, exist_ok=True)

    playlist_path = os.path.join(hls_dir, "index.m3u8")

    cmd = [
        ffmpeg,
        "-y",  # overwrite if exists

        # Force start from beginning
        "-ss", "0",

        # Reconnect options to avoid input drop
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "5",

        "-i", source_url,

        # VIDEO (iOS compatible)
        "-c:v", "h264",
        "-profile:v", "baseline",
        "-level", "3.0",
        "-pix_fmt", "yuv420p",
        "-preset", "veryfast",
        "-g", "24",              # GOP size = 24 frames (1 second at 24fps)
        "-keyint_min", "24",     # Minimum keyframe interval
        "-sc_threshold", "0",    # Disable scene change detection
        "-b:v", "2500k",

        # Force keyframe at start and every segment
        "-force_key_frames", "expr:gte(t,n_forced*4)",

        # AUDIO
        "-c:a", "aac",
        "-b:a", "128k",
        "-ac", "2",
        "-ar", "48000",

        # HLS OUTPUT (OPTIMIZED FOR CHEWIE)
        "-f", "hls",
        "-hls_time", "4",                      # 4 second segments
        "-hls_list_size", "0",                 # Keep all segments (allows full seeking)
        "-hls_flags", "independent_segments",  # Fix iOS/Android seeking
        "-hls_segment_type", "mpegts",
        "-start_number", "0",                  # Always start from 0
        "-hls_playlist_type", "event",         # Event playlist (grows as transcoding)

        playlist_path
    ]

    # Start ffmpeg
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # ---- FIX FOR "HLS segment not found" ----
    # Wait for the playlist and first segment to exist
    for _ in range(50):  # 50 × 0.1s = 5 seconds max
        if os.path.exists(playlist_path):
            # Check inside playlist for first segment name
            try:
                with open(playlist_path, "r") as f:
                    content = f.read()
                    if ".ts" in content:  # segment written
                        break
            except:
                pass
        time.sleep(0.1)

    return hls_dir, playlist_path, process
