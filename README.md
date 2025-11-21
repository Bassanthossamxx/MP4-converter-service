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

## API Endpoints

### Convert Video to MP4
**POST** `/api/convert/`

Request body:
```json
{
  "url": "https://example.com/video.mkv"
}
```

Response:
```json
{
  "status": "processing",
  "job_id": "abc-123-def",
  "mp4_url": null
}
```

### Check Conversion Status
**GET** `/api/status/{job_id}/`

Response (when ready):
```json
{
  "status": "ready",
  "mp4_url": "http://localhost:8000/media/mp4/abc-123-def.mp4"
}
```

Response (when failed):
```json
{
  "status": "failed",
  "mp4_url": null,
  "error": "Error message describing what went wrong"
}
```

## Troubleshooting

### "FFmpeg is not installed or not found in PATH"
This means FFmpeg is not properly installed. Follow the FFmpeg installation instructions above and make sure to restart your terminal/IDE after adding it to PATH.

### Conversion timeout
By default, conversions timeout after 10 minutes. For very large files, you may need to adjust the timeout in `converter/tasks.py`.

