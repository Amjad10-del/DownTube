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
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0"
]

# --------------------------
# Utility Functions
# --------------------------
def human_like_delay():
    """Simulate human-like delay."""
    time.sleep(random.uniform(5, 15))

def sanitize_filename(filename: str) -> str:
    """Sanitize filenames to avoid invalid characters."""
    return re.sub(r'[\\/*?:"<>|]', "", filename)[:200]

def get_random_headers():
    """Generate realistic browser headers."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.youtube.com/",
        "DNT": str(random.randint(0, 1)),
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache"
    }

# --------------------------
# Core Download Handlers
# --------------------------
@app.route("/", methods=["GET"])
def serve_frontend():
    """Serve the frontend HTML file."""
    return app.send_static_file("FrontPage.html")

@app.route("/upload-cookies", methods=["POST"])
def upload_cookies():
    """Allow users to upload a cookies.txt file."""
    if "cookies" not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files["cookies"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400
    if file and file.filename.endswith(".txt"):
        try:
            cookie_path = TEMP_DIR / "cookies.txt"
            file.save(cookie_path)
            return jsonify({"message": "Cookies uploaded successfully"}), 200
        except Exception as e:
            logging.error(f"Failed to save cookies: {str(e)}")
            return jsonify({"error": "Failed to save cookies"}), 500
    return jsonify({"error": "Invalid file type"}), 400

@app.route("/download", methods=["POST"])
def handle_download():
    """Handle video/audio download requests."""
    try:
        human_like_delay()
        data = request.get_json()
        if not data or not all([data.get("videoUrl"), data.get("downloadType")]):
            return jsonify({"error": "Missing required fields"}), 400

        video_url = data["videoUrl"]
        download_type = data["downloadType"]
        logging.info(f"New download request: {video_url} [{download_type}]")

        # Load cookies if available
        cookie_path = TEMP_DIR / "cookies.txt"
        cookiefile = str(cookie_path) if cookie_path.exists() else None

        base_ydl_opts = {
            "noplaylist": True,
            "logger": logging,
            "outtmpl": str(TEMP_DIR / "%(title)s.%(ext)s"),
            "http_headers": get_random_headers(),
            "cookiefile": cookiefile,
            "ssl_ca_certificates": certifi.where(),
            "merge_output_format": "mp4",
            "ignoreerrors": False,
            "retries": 3,
            "fragment_retries": 3,
            "skip_unavailable_fragments": False
        }

        if download_type == "video":
            return handle_video_download(video_url, base_ydl_opts)
        elif download_type == "mp3":
            return handle_audio_download(video_url, base_ydl_opts)
        else:
            return jsonify({"error": "Invalid download type"}), 400

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "bot" in error_msg.lower() or "sign in" in error_msg.lower():
            logging.error("Bot detection triggered. Update cookies and headers.")
            return jsonify({"error": "Bot detected. Upload valid cookies and try again."}), 403
        return jsonify({"error": "Download failed. Video may be restricted or format unavailable."}), 400
    except Exception as e:
        logging.exception("Critical server error")
        return jsonify({"error": "Internal server error"}), 500

def handle_video_download(url, base_opts):
    """Handle video downloads."""
    ydl_opts = {
        **base_opts,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",  # Fallback to best available format
        "postprocessors": [{
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4"
        }]
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        original_path = Path(ydl.prepare_filename(info))
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

def handle_audio_download(url, base_opts):
    """Handle audio downloads."""
    temp_path = TEMP_DIR / "temp_audio.mp3"
    ydl_opts = {
        **base_opts,
        "format": "bestaudio/best",  # Best available audio format
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "outtmpl": str(temp_path.with_suffix('')),
        "keepvideo": False
    }
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

# --------------------------
# Execution & Cleanup
# --------------------------
@atexit.register
def cleanup():
    """Cleanup temporary files on exit."""
    for file in TEMP_DIR.glob("*"):
        try:
            file.unlink(missing_ok=True)
        except Exception as e:
            logging.warning(f"Cleanup failed for {file}: {str(e)}")

if __name__ == "__main__":
    TEMP_DIR.mkdir(exist_ok=True, parents=True)
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False, threaded=True)