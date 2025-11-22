
## Flutter HLS Streaming Integration

This document explains how a Flutter app can stream videos using your backend HLS service.

---

## 1. Backend Endpoint (for Flutter)

To start streaming a video, call:

```text
GET {BASE_URL}/api/stream/hls?url={SOURCE_VIDEO_URL}
```

**Example:**

```text
GET http://YOUR_SERVER/api/stream/hls?url=https://example.com/video.mkv
```

**Backend response (example):**

```json
{
  "master_playlist_url": "http://YOUR_SERVER/api/stream/hls/13292f3b5d8445be85c91965eb4d740f/master.m3u8"
}
```

---

## 2. What video URLs are accepted

The `url` parameter (`SOURCE_VIDEO_URL`) can be:

- A direct link to an **MKV** file (e.g. `https://.../video.mkv`) – this is the main use case.
- A direct link to an **MP4** file (e.g. `https://.../video.mp4`).
- In all cases, the link must be:
  - Publicly reachable over HTTP/HTTPS (no local/LAN-only URLs).
  - Not DRM‑protected.
  - Not behind login or JavaScript-only players (must be a direct file URL).

### Recommended / best-working formats

The backend uses FFmpeg, so it can usually handle several containers/codecs, but these are **recommended and most stable**:

- Containers: **MKV**, **MP4**.
- Video codec: **H.264/AVC** (strongly recommended).
- Audio codec: **AAC** (recommended).

Other containers/codecs (M4V, MOV, HEVC, etc.) may work, but MKV/MP4 with H.264 + AAC is the safest and best‑tested option.

---

## 3. Flutter dependencies

Add this to `pubspec.yaml`:

```yaml
dependencies:
  flutter:
    sdk: flutter
  chewie: ^1.7.0
  video_player: ^2.8.0
  http: ^1.1.0
```

---

## 4. Service layer (call backend and get HLS URL)

```dart
// lib/services/stream_service.dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class StreamService {
  // TODO: replace with your real backend URL
  static const String baseUrl = 'http://YOUR_SERVER';

  /// Call /api/stream/hls?url={source_video_url}
  /// Returns the master .m3u8 URL
  static Future<String> getHlsUrl(String sourceVideoUrl) async {
    final uri = Uri.parse('$baseUrl/api/stream/hls')
        .replace(queryParameters: {'url': sourceVideoUrl});

    final res = await http.get(uri);

    if (res.statusCode != 200) {
      throw Exception('Failed to start streaming: ${res.statusCode}');
    }

    final data = jsonDecode(res.body) as Map<String, dynamic>;
    return data['master_playlist_url'] as String;
  }
}
```

---

## 5. Flutter video player with Chewie

Starts from 0:00, default quality is lowest (240p), user can switch quality.

```dart
// lib/screens/video_player_screen.dart
import 'package:flutter/material.dart';
import 'package:chewie/chewie.dart';
import 'package:video_player/video_player.dart';
import '../services/stream_service.dart';

class VideoPlayerScreen extends StatefulWidget {
  final String sourceVideoUrl; // original MP4 URL

  const VideoPlayerScreen({super.key, required this.sourceVideoUrl});

  @override
  State<VideoPlayerScreen> createState() => _VideoPlayerScreenState();
}

class _VideoPlayerScreenState extends State<VideoPlayerScreen> {
  VideoPlayerController? _videoController;
  ChewieController? _chewieController;
  bool _loading = true;

  // Manual quality URLs built from master playlist
  String? _baseStreamUrl; // e.g. http://server/api/stream/hls/{session_id}
  String _currentQuality = '240p';

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    try {
      // 1) Ask backend for HLS master URL
      final masterUrl = await StreamService.getHlsUrl(widget.sourceVideoUrl);

      // master example: http://server/api/stream/hls/{session_id}/master.m3u8
      _baseStreamUrl = masterUrl.replaceAll('/master.m3u8', '');

      // 2) Load lowest quality first (240p)
      await _loadQuality('240p');
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e')),
      );
    }
  }

  Future<void> _loadQuality(String quality) async {
    if (_baseStreamUrl == null) return;

    final url = '$_baseStreamUrl/$quality.m3u8';

    // remember current time if changing quality
    final currentPos = _videoController?.value.position ?? Duration.zero;

    await _chewieController?.dispose();
    await _videoController?.dispose();

    final controller = VideoPlayerController.networkUrl(Uri.parse(url));
    await controller.initialize();

    // force start from 0:00 on first load, or keep position on switch
    if (currentPos == Duration.zero) {
      await controller.seekTo(Duration.zero);
    } else {
      await controller.seekTo(currentPos);
    }

    final chewie = ChewieController(
      videoPlayerController: controller,
      autoPlay: true,
      looping: false,
    );

    setState(() {
      _videoController = controller;
      _chewieController = chewie;
      _currentQuality = quality;
      _loading = false;
    });
  }

  @override
  void dispose() {
    _chewieController?.dispose();
    _videoController?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('HLS Stream'),
        actions: [
          PopupMenuButton<String>(
            initialValue: _currentQuality,
            onSelected: (q) async {
              setState(() => _loading = true);
              await _loadQuality(q);
            },
            itemBuilder: (context) => const [
              PopupMenuItem(value: '240p', child: Text('240p (Fast)')),
              PopupMenuItem(value: '360p', child: Text('360p')),
              PopupMenuItem(value: '480p', child: Text('480p')),
              PopupMenuItem(value: '720p', child: Text('720p (Best)')),
            ],
          ),
        ],
      ),
      body: Center(
        child: _loading
            ? const CircularProgressIndicator()
            : (_chewieController == null
                ? const Text('Failed to load video')
                : Chewie(controller: _chewieController!)),
      ),
    );
  }
}
```

---

## 6. How to use in Flutter

```dart
// Example: open player for a given MP4 URL
Navigator.push(
  context,
  MaterialPageRoute(
    builder: (_) => const VideoPlayerScreen(
      sourceVideoUrl: 'https://example.com/video.mkv', // your MKV link
    ),
  ),
);
```

---

## Summary for Flutter developer

- Call `GET /api/stream/hls?url={mkv_url}` to get `master_playlist_url`.
- Flutter always starts from time 0:00 and default quality 240p (lowest).
- User can manually change quality between 240p / 360p / 480p / 720p.
- Only direct, public MP4 links (H.264 + AAC) are guaranteed to work.