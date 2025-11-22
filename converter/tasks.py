import os
import shutil
import subprocess
from django.conf import settings


def find_ffmpeg():
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    return ffmpeg or "ffmpeg"


def generate_hls_stream(source_url: str, session: str):
    import time
    ffmpeg = find_ffmpeg()

    hls_dir = os.path.join(settings.MEDIA_ROOT, "hls", session)
    os.makedirs(hls_dir, exist_ok=True)

    master_playlist = os.path.join(hls_dir, "master.m3u8")

    renditions = [
        ("240p", "426x240", "400k"),
        ("360p", "640x360", "800k"),
        ("480p", "854x480", "1200k"),
        ("720p", "1280x720", "2500k"),
    ]

    cmd = [
        ffmpeg, "-y",
        "-i", source_url,

        # FORCE exact zero timestamp
        "-ss", "0",
        "-vsync", "cfr",
        "-copyts",
        "-start_at_zero",
        "-avoid_negative_ts", "make_zero",
        "-muxpreload", "0",
        "-muxdelay", "0",

        "-threads", "2",
        "-preset", "veryfast",
        "-tune", "zerolatency",
        "-sc_threshold", "0",
    ]

    variants = []

    for name, res, bitrate in renditions:
        playlist = f"{name}.m3u8"
        variants.append((playlist, res, bitrate))

        cmd.extend([
            "-map", "0:v", "-map", "0:a",
            "-c:v", "h264",
            "-profile:v", "baseline",
            "-level:v", "3.0",
            "-pix_fmt", "yuv420p",
            "-s:v", res,
            "-b:v", bitrate,

            # keyframe EXACT at t=0
            "-g", "30",
            "-keyint_min", "30",
            "-force_key_frames", "expr:gte(t,n_forced)",

            # Audio
            "-c:a", "aac",
            "-b:a", "128k",
            "-ac", "2",
            "-ar", "48000",

            # HLS
            "-f", "hls",
            "-hls_time", "1",
            "-hls_list_size", "10000",
            "-hls_flags", "independent_segments+omit_endlist",
            "-start_number", "0",
            os.path.join(hls_dir, playlist)
        ])

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    with open(master_playlist, "w") as m3u:
        m3u.write("#EXTM3U\n")
        for playlist, res, bitrate in variants:
            bw = bitrate.replace("k", "000")
            m3u.write(f"#EXT-X-STREAM-INF:BANDWIDTH={bw},RESOLUTION={res}\n")
            m3u.write(f"{playlist}\n")

    # wait for segments
    for _ in range(50):
        for playlist, _, _ in variants:
            path = os.path.join(hls_dir, playlist)
            if os.path.exists(path):
                with open(path, "r") as f:
                    if ".ts" in f.read():
                        return hls_dir, master_playlist, process
        time.sleep(0.1)

    return hls_dir, master_playlist, process
