# main.py
from flask import Flask, request, jsonify, send_from_directory
import yt_dlp
import os
import logging
import certifi
import ssl
import random
import time
from pathlib import Path

app = Flask(__name__, static_folder="./FrontEnd", static_url_path="/")

# ========== Configuration Section ==========
# SSL Setup
ssl_context = ssl.create_default_context(cafile=certifi.where())
ssl._create_default_https_context = lambda: ssl_context
os.environ['SSL_CERT_FILE'] = certifi.where()

# Default downloads directory (system's Downloads folder)
DOWNLOADS_DIR = Path.home() / "Downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True, parents=True)

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('app.log'), logging.StreamHandler()]
)

# ========== Helper Functions ==========
def human_like_delay(min_sec=1, max_sec=3):
    """Simulate human interaction delays"""
    time.sleep(random.uniform(min_sec, max_sec))

# ========== Routes ==========
@app.route("/")
def serve_frontend():
    return send_from_directory(app.static_folder, "FrontPage.html")

@app.route("/download", methods=["POST"])
def handle_download():
    try:
        human_like_delay(0.5, 1.5)
        data = request.get_json()
        
        # Validate input
        if not all([data.get("videoUrl"), data.get("downloadType")]):
            return jsonify({"error": "Missing required fields"}), 400

        video_url = data["videoUrl"]
        download_type = data["downloadType"]

        # YouTube DL Configuration
        ydl_opts = {
            "outtmpl": str(DOWNLOADS_DIR / "%(title)s.%(ext)s"),
            "nocheckcertificate": False,
            "ignoreerrors": False,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.youtube.com/"
            },
            "ratelimit": 1_500_000,
            "retries": 3,
            "sleep_interval": random.randint(5, 15),
            "verbose": False
        }

        # Add cookies if available
        cookies_file = Path("cookies.txt")
        if cookies_file.exists():
            ydl_opts["cookiefile"] = str(cookies_file)
            logging.info("Using cookies for authentication")
        else:
            logging.warning("No cookies.txt found - some videos might require login")

        # Format configuration
        if download_type == "mp3":
            ydl_opts.update({
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }]
            })
        elif download_type == "webm":
            ydl_opts["format"] = "bestvideo[ext=webm]+bestaudio[ext=webm]/best[ext=webm]/best"
        else:
            return jsonify({"error": "Invalid download type"}), 400

        # Execute download
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            human_like_delay(1, 2)
            info = ydl.extract_info(video_url, download=True)
            
            if not info or 'title' not in info:
                raise yt_dlp.utils.DownloadError("Invalid video response")

            downloaded_file = Path(ydl.prepare_filename(info)).resolve()
            logging.info(f"Successfully downloaded to: {downloaded_file}")

        return jsonify({
            "success": True,
            "path": str(downloaded_file),
            "filename": downloaded_file.name
        })

    except yt_dlp.utils.DownloadError as e:
        logging.error(f"Download failed: {str(e)}")
        return jsonify({"error": str(e)}), 400
        
    except Exception as e:
        logging.exception("Server error:")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)