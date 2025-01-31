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
COOKIES_PATH = "cookies.txt"  # Provide your YouTube cookies here

# --------------------------
# Utility Functions
# --------------------------
def human_like_delay():
    time.sleep(random.uniform(5, 10))

def sanitize_filename(filename: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", filename)[:200]

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
        
        if not data or not data.get("videoUrl"):
            return jsonify({"error": "Missing required fields"}), 400
        
        video_url = data["videoUrl"]
        logging.info(f"New download request: {video_url}")
        
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
        }
        
        return handle_best_download(video_url, base_ydl_opts)

    except yt_dlp.utils.DownloadError as e:
        logging.error(f"Download error: {str(e)}")
        return jsonify({"error": "Download failed. Video may be restricted or unavailable."}), 400
    except Exception as e:
        logging.exception("Critical server error")
        return jsonify({"error": "Internal server error"}), 500

def handle_best_download(url, base_opts):
    ydl_opts = {
        **base_opts,
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        original_path = Path(ydl.prepare_filename(info))
        temp_path = TEMP_DIR / f"{sanitize_filename(info.get('title', 'video'))}.mp4"
        shutil.move(original_path, temp_path)
        response = send_file(temp_path, as_attachment=True, mimetype="video/mp4")
        response.call_on_close(lambda: temp_path.unlink(missing_ok=True))
        return response

# --------------------------
# Execution
# --------------------------
if __name__ == "__main__":
    TEMP_DIR.mkdir(exist_ok=True, parents=True)
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False, threaded=True)
