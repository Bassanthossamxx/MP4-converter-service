# MP4 Converter Service

A Django REST API service that converts video files to MP4 format using FFmpeg.

## Prerequisites

### 1. Python 3.8+
Make sure you have Python installed on your system.

### 2. FFmpeg (Required)
This service requires FFmpeg to be installed and accessible in your system PATH.

#### Windows Installation:
1. Download FFmpeg from [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html) or use a build from [https://github.com/BtbN/FFmpeg-Builds/releases](https://github.com/BtbN/FFmpeg-Builds/releases)
2. Extract the downloaded archive to a location (e.g., `C:\ffmpeg`)
3. Add FFmpeg to your PATH:
   - Open System Properties → Advanced → Environment Variables
   - Edit the `Path` variable under System variables
   - Add the path to FFmpeg's `bin` folder (e.g., `C:\ffmpeg\bin`)
4. Verify installation by opening a new terminal and running:
   ```
   ffmpeg -version
   ```

#### Linux Installation:
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install ffmpeg

# CentOS/RHEL
sudo yum install ffmpeg
```

#### macOS Installation:
```bash
brew install ffmpeg
```

## Setup

1. Clone the repository
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run migrations:
   ```bash
   python manage.py migrate
   ```

4. Start the development server:
   ```bash
   python manage.py runserver
   ```

## Project Structure

High-level layout of the Django project:

```text
MP4-converter-service/
├── manage.py                 # Django management script
├── db.sqlite3                # Default SQLite database (generated)
├── requirements.txt          # Python dependencies
├── README.md                 # Project documentation
├── config/                   # Django project configuration
│   ├── __init__.py
│   ├── asgi.py               # ASGI entrypoint
│   ├── settings.py           # Django settings (installed apps, DB, media, etc.)
│   ├── urls.py               # Root URL router (includes `converter` under /api/)
│   └── wsgi.py               # WSGI entrypoint
├── converter/                # Application that exposes the streaming API
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py             # (currently not used for streaming)
│   ├── tasks.py              # FFmpeg helpers: stream_to_mp4, generate_hls_stream
│   ├── urls.py               # /api/ endpoints for MP4 & HLS
│   ├── utils.py              # Extra helpers (if any)
│   ├── views.py              # APIView classes: StreamIOS, HLSSource, HLSFileServe
│   └── migrations/           # Django migration files
└── media/                    # Media root (see settings.MEDIA_ROOT)
    ├── mp4/                  # (optional) MP4 files (if you decide to save)
    └── hls/                  # HLS folders and segments generated at runtime
```

## API Endpoints

All endpoints are prefixed with `/api/` (see `config/urls.py`).

### 1. Stream as MP4 (live)
- **Method:** `GET`
- **URL:** `/api/stream/mp4`
- **Query params:**
   - `url` (string, required) – source video URL (e.g. `.mp4`, `.m3u8`, etc.)

Example:

`GET http://localhost:8000/api/stream/mp4?url=https://example.com/video.m3u8`

- **Response:**
   - `200` – `video/mp4` streaming response (live bytes)
   - `400` – JSON: `{ "error": "Missing url" }`

Use this when you just want a direct MP4 stream from a single URL.

### 2. Get HLS Playlist + MP4 Fallback
- **Method:** `GET`
- **URL:** `/api/stream/hls`
- **Query params:**
   - `url` (string, required) – source video URL

Example:

`GET http://localhost:8000/api/stream/hls?url=https://example.com/video.m3u8`

- **Successful response (200, JSON):**
```json
{
   "mp4_fallback_stream": "http://localhost:8000/api/stream?url=...",
   "hls_playlist_stream": "http://localhost:8000/api/stream/hls/<folder>/index.m3u8"
}
```

- **Error response (400, JSON):**
```json
{ "error": "Missing url" }
```

Use `hls_playlist_stream` as an HLS playlist URL in your player, and `mp4_fallback_stream` as a backup plain MP4 stream if HLS is not supported.

> Note: `mp4_fallback_stream` uses the same backend stream function as `/api/stream/mp4` but is returned as a convenience URL.

### 3. Serve HLS Segments & Playlist
- **Method:** `GET`
- **URL:** `/api/stream/hls/<folder>/<filename>`
- **Path params:**
   - `folder` – HLS folder name returned inside `hls_playlist_stream`
   - `filename` – HLS file name (`index.m3u8` or `.ts` segment)

Example playlist URL (returned by endpoint 2):

`http://localhost:8000/api/stream/hls/3a1b2c3d/index.m3u8`

- **Response:**
   - For `.m3u8` – content type `application/vnd.apple.mpegurl`
   - For `.ts` – content type `video/mp2t`
   - `404` – if the segment or playlist file does not exist

## Streaming Quality & Performance

The service is tuned for **series/movies** with **fast start** and **reasonable quality**, not maximum bitrate:

- Video is re-encoded to **H.264 at ~720p** with a target bitrate of about **2.5 Mbps**.
- Audio is encoded as **AAC ~128 kbps**.
- FFmpeg uses the **`veryfast` preset** so the server spends less time encoding and can start streaming quickly.

These settings apply to both:
- The MP4 stream returned by `/api/stream/mp4`.
- The HLS stream generated by `/api/stream/hls`.

You can adjust these values in `converter/tasks.py` if you need higher or lower quality (e.g. change `scale=-2:720`, `-b:v 2500k`, or `-b:a 128k`).

## Flutter Integration Guide

This section shows how a Flutter app can consume the API.

### 1. Using `video_player` with MP4 stream

Add dependency:

```yaml
dependencies:
   video_player: ^2.8.0
```

Create a controller pointing to the MP4 endpoint:

```dart
final sourceUrl = Uri.encodeComponent('https://example.com/video.m3u8');
final controller = VideoPlayerController.networkUrl(
   Uri.parse('http://localhost:8000/api/stream/mp4?url=$sourceUrl'),
);
```

Then initialize and build normally with `VideoPlayer` widget.

### 2. Using an HLS player (recommended)

For better streaming (seek, adaptive bitrate), use HLS with a player like `better_player` or `video_player_hls` (or any player that supports `.m3u8`).

Example with `better_player`:

```yaml
dependencies:
   better_player: ^0.0.83
```

First, call the HLS endpoint to get URLs:

```dart
Future<Map<String, dynamic>> fetchHlsInfo(String sourceUrl) async {
   final encoded = Uri.encodeComponent(sourceUrl);
   final uri = Uri.parse('http://localhost:8000/api/stream/hls?url=$encoded');

   final resp = await http.get(uri);
   if (resp.statusCode != 200) {
      throw Exception('Failed to get HLS source');
   }
   return jsonDecode(resp.body) as Map<String, dynamic>;
}
```

Then use `hls_playlist_stream` in the player:

```dart
final info = await fetchHlsInfo('https://example.com/video.m3u8');
final hlsUrl = info['hls_playlist_stream'] as String;

final betterPlayerController = BetterPlayerController(
   const BetterPlayerConfiguration(),
   betterPlayerDataSource: BetterPlayerDataSource(
      BetterPlayerDataSourceType.network,
      hlsUrl,
   ),
);
```

Optionally, keep `mp4_fallback_stream` as a backup for devices that do not support HLS:

```dart
final fallbackMp4Url = info['mp4_fallback_stream'] as String?;
```

### 3. Notes for Flutter developers
- Always `Uri.encodeComponent` the original `url` before sending it as a query parameter.
- On real devices/emulators, replace `localhost` with your machine IP (e.g., `http://192.168.1.10:8000`).
- For production, put this service behind HTTPS and use your public domain instead of `localhost`.

## Troubleshooting

### "FFmpeg is not installed or not found in PATH"
This means FFmpeg is not properly installed. Follow the FFmpeg installation instructions above and make sure to restart your terminal/IDE after adding it to PATH.

### Conversion timeout
The current implementation is **streaming-based**, not offline file conversion, so there is **no fixed 10‑minute timeout** inside `converter/tasks.py`.
Playback will continue for the full length of the episode/movie as long as:
- The source video URL remains available.
- The Django server and FFmpeg process are running.
- The client keeps the HTTP connection open.


