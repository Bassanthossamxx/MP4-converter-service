import os
import shutil
import subprocess
from django.conf import settings


def find_ffmpeg():
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    return ffmpeg or "ffmpeg"


def generate_hls_stream(source_url: str, session: str, start_time: float = 0.0):
    import time
    ffmpeg = find_ffmpeg()

    hls_dir = os.path.join(settings.MEDIA_ROOT, "hls", session)
    os.makedirs(hls_dir, exist_ok=True)

    master_playlist = os.path.join(hls_dir, "master.m3u8")

    # Fewer, lower renditions for faster startup and less bandwidth
    renditions = [
        ("240p", "426x240", "250k"),
        ("360p", "640x360", "500k"),
    ]

    cmd = [
        ffmpeg, "-y",
        "-ss", str(start_time),  # seek to requested start time (usually 0.0)
        "-i", source_url,

        # timing controls, force HLS timeline to start at 0
        "-vsync", "cfr",
        "-start_at_zero",
        "-avoid_negative_ts", "make_zero",
        "-muxpreload", "0",
        "-muxdelay", "0",

        # Encoding speed / latency
        "-threads", "2",
        "-preset", "superfast",
        "-tune", "zerolatency",
        "-sc_threshold", "0",
    ]

    variants = []

    for name, res, bitrate in renditions:
        playlist = f"{name}.m3u8"
        variants.append((playlist, res, bitrate))

        numeric_bitrate = bitrate.replace("k", "000")

        cmd.extend([
            "-map", "0:v", "-map", "0:a",
            "-c:v", "h264",
            "-profile:v", "baseline",
            "-level:v", "3.0",
            "-pix_fmt", "yuv420p",
            "-s:v", res,
            "-b:v", bitrate,
            "-maxrate", numeric_bitrate,
            "-bufsize", str(int(int(numeric_bitrate) * 1.5)),

            # keyframe every segment
            "-g", "30",
            "-keyint_min", "30",
            "-force_key_frames", "expr:gte(t,n_forced)",

            # Audio - slightly lower bitrate and sample rate
            "-c:a", "aac",
            "-b:a", "96k",
            "-ac", "2",
            "-ar", "44100",

            # HLS: very short segments, sliding window, independent segments
            "-f", "hls",
            "-hls_time", "1.5",
            "-hls_playlist_type", "event",
            "-hls_flags", "independent_segments+delete_segments+append_list",
            "-hls_list_size", "6",
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

    # wait for enough segments so player can start smoothly
    for _ in range(80):  # up to ~8s
        ready = True
        for playlist, _, _ in variants:
            path = os.path.join(hls_dir, playlist)
            if not os.path.exists(path):
                ready = False
                break
            with open(path, "r") as f:
                content = f.read()
                # need at least ~2 segments
                if content.count(".ts") < 2:
                    ready = False
                    break
        if ready:
            return hls_dir, master_playlist, process
        time.sleep(0.1)

    return hls_dir, master_playlist, process
