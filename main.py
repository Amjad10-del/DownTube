import os
import certifi
import logging
import random
import time
import tempfile
import shutil
import re
import atexit
from pathlib import Path
from flask import Flask, request, jsonify, send_file
import yt_dlp

# --------------------------
# Initial Configuration
# --------------------------
app = Flask(__name__, static_folder="./FrontEnd", static_url_path="/")

# SSL Configuration
os.environ['SSL_CERT_FILE'] = certifi.where()

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
COOKIES_PATH = "cookies.txt"

# --------------------------
# Utility Functions
# --------------------------
def human_like_delay():
    time.sleep(random.uniform(2, 5))

def sanitize_filename(filename: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", filename)[:200]

def validate_ffmpeg():
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise RuntimeError("FFmpeg not found in PATH. Install FFmpeg and ensure it's available.")
    return ffmpeg_path

# --------------------------
# Cleanup System
# --------------------------
def cleanup_temp_files():
    for file_path in TEMP_DIR.glob('*'):
        try:
            if file_path.is_file():
                file_path.unlink(missing_ok=True)
        except Exception as e:
            logging.error(f"Failed to delete {file_path}: {str(e)}")
    logging.info("Cleanup completed successfully")

atexit.register(cleanup_temp_files)

# --------------------------
# Core Download Handlers
# --------------------------
@app.route("/", methods=["GET"])
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
        
        base_ydl_opts = {
            "noplaylist": True,
            "logger": logging,
            "outtmpl": str(TEMP_DIR / "%(title)s.%(ext)s"),
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            },
            "cookiefile": COOKIES_PATH if os.path.exists(COOKIES_PATH) else None,
            "cookies_from_browser": ("chrome",) if not os.path.exists(COOKIES_PATH) else None,
            "ssl_ca_certificates": certifi.where(),
            "format_sort": ["res:1080", "ext:mp4"],  # Prefer 1080p MP4
            "merge_output_format": "mp4",
        }
        
        if download_type == "video":
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
    """Handle video downloads with fallback formats"""
    ffmpeg_path = validate_ffmpeg()
    
    ydl_opts = {
        **base_opts,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4"
        }],
        "ffmpeg_location": ffmpeg_path
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            original_path = Path(ydl.prepare_filename(info))
            
            # Handle format variations
            if not original_path.exists():
                original_path = original_path.with_suffix('.mp4')
                
            temp_path = TEMP_DIR / f"{sanitize_filename(info.get('title', 'video'))}{original_path.suffix}"
            shutil.move(original_path, temp_path)
            
            response = send_file(
                temp_path,
                as_attachment=True,
                mimetype="video/mp4",
                download_name=f"{sanitize_filename(info.get('title', 'video'))}{temp_path.suffix}"
            )
            response.call_on_close(lambda: temp_path.unlink(missing_ok=True))
            return response
            
    except yt_dlp.utils.DownloadError as e:
        if "Requested format is not available" in str(e):
            # Fallback to best available format
            ydl_opts["format"] = "best"
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                original_path = Path(ydl.prepare_filename(info))
                # Rest of handling remains same
        else:
            raise

def handle_audio_download(url, base_opts):
    """Handle audio downloads with FFmpeg validation"""
    ffmpeg_path = validate_ffmpeg()
    temp_path = TEMP_DIR / "temp_audio.mp3"
    
    ydl_opts = {
        **base_opts,
        "format": "bestaudio/best",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "ffmpeg_location": ffmpeg_path,
        "outtmpl": str(temp_path.with_suffix('')),
        "keepvideo": False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not temp_path.exists() or temp_path.stat().st_size < 1024:
                raise ValueError("MP3 conversion failed")
                
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
    TEMP_DIR.mkdir(exist_ok=True, parents=True)
    try:
        validate_ffmpeg()
        app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False, threaded=True)
    except RuntimeError as e:
        logging.critical(str(e))
        exit(1)