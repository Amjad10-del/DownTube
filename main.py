import os
import certifi
import logging
import random
import time
import tempfile
import shutil
import mimetypes
import re
import requests
import atexit
from pathlib import Path
from flask import Flask, request, jsonify, Response, send_file
import yt_dlp
import browser_cookie3

# --------------------------
# Initial Configuration
# --------------------------
app = Flask(__name__, static_folder="./FrontEnd", static_url_path="/")

# SSL Configuration
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Constants
TEMP_DIR = Path(tempfile.gettempdir()) / "ytdl_downloads"
TEMP_DIR.mkdir(exist_ok=True)


# --------------------------
# Utility Functions
# --------------------------
def human_like_delay():
    time.sleep(random.uniform(5, 15))

def sanitize_filename(filename: str) -> str:
    cleaned = re.sub(r'[\\/*?:"<>|]', "", filename)
    return cleaned[:200]  # Safer filename length

# --------------------------
# Cleanup System
# --------------------------
def cleanup_temp_files():
    """Remove all temporary files in the download directory"""
    try:
        for file_path in TEMP_DIR.glob('*'):
            try:
                if file_path.is_file():
                    file_path.unlink(missing_ok=True)
            except Exception as e:
                logging.error(f"Failed to delete {file_path}: {str(e)}")
        logging.info("Cleanup completed successfully")
    except Exception as e:
        logging.error(f"Cleanup error: {str(e)}")

atexit.register(cleanup_temp_files)

# --------------------------
# Core Download Handlers
# --------------------------
@app.route("/")
def serve_frontend():
    return app.send_static_file("FrontPage.html")

@app.route("/download", methods=["POST"])
def handle_download():
    try:
        human_like_delay()
        data = request.get_json()

        if not data or not all([data.get("videoUrl"), data.get("downloadType")]):
            return jsonify({"error": "Missing required fields"}), 400

        video_url = data["videoUrl"]
        download_type = data["downloadType"]
        logging.info(f"New download request: {video_url} [{download_type}]")

        # Common configuration
        base_ydl_opts = {
            "noplaylist": True,
            "logger": logging,
            "outtmpl": str(TEMP_DIR / "%(title)s.%(ext)s"),
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            },
            "ssl_ca_certificates": certifi.where(),
        }

        if download_type == "webm":
            return handle_video_download(video_url, base_ydl_opts)
        elif download_type == "mp3":
            return handle_audio_download(video_url, base_ydl_opts)
        else:
            return jsonify({"error": "Invalid download type"}), 400

    except yt_dlp.utils.DownloadError as e:
        logging.error(f"Download error: {str(e)}")
        return jsonify({"error": "Download failed. Video may be restricted or unavailable."}), 400
    except Exception as e:
        logging.exception("Critical server error")
        return jsonify({"error": "Internal server error"}), 500

def handle_video_download(url, base_opts):
    """Handle video downloads with proper audio/video merging"""
    ydl_opts = {
        **base_opts,
        "format": "bestvideo[ext=webm][height<=1080]+bestaudio[ext=webm]/best[ext=webm]",
        "merge_output_format": "webm",
        "postprocessors": [{
            "key": "FFmpegVideoConvertor",
            "preferedformat": "webm"
        }]
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        original_path = Path(ydl.prepare_filename(info))

        # Create temp copy to avoid file locking
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm", dir=TEMP_DIR) as temp_file:
            temp_path = Path(temp_file.name)
            shutil.copyfile(original_path, temp_path)

        # Cleanup original file
        original_path.unlink(missing_ok=True)

        # Create response with cleanup
        response = send_file(
            temp_path,
            as_attachment=True,
            mimetype="video/webm",
            download_name=f"{sanitize_filename(info.get('title', 'video'))}.webm"
        )
        response.call_on_close(lambda: temp_path.unlink(missing_ok=True))
        return response

def handle_audio_download(url, base_opts):
    """Handle audio downloads with proper MP3 conversion"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3", dir=TEMP_DIR) as temp_file:
        temp_path = Path(temp_file.name)

    ydl_opts = {
        **base_opts,
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "ffmpeg_location": shutil.which("ffmpeg"),
        "outtmpl": str(temp_path.with_suffix('')),
        "keepvideo": False
    }

    if not ydl_opts["ffmpeg_location"]:
        raise RuntimeError("FFmpeg not found - required for audio conversion")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        # Verify successful conversion
        if not temp_path.exists() or temp_path.stat().st_size < 1024:
            raise ValueError("MP3 conversion failed - file too small")

        # Create response with cleanup
        response = send_file(
            temp_path,
            as_attachment=True,
            mimetype="audio/mpeg",
            download_name=f"{sanitize_filename(info.get('title', 'audio'))}.mp3"
        )
        response.call_on_close(lambda: temp_path.unlink(missing_ok=True))
        return response

    except Exception as e:
        temp_path.unlink(missing_ok=True)
        raise

# --------------------------
# Execution
# --------------------------
if __name__ == "__main__":
    # Verify temp directory exists
    TEMP_DIR.mkdir(exist_ok=True, parents=True)
    
    # Start the application
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('PORT', 5000)),
        debug=False,
        threaded=True
    )