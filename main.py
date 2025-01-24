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

# ===== Enhanced Configuration =====
ssl_context = ssl.create_default_context(cafile=certifi.where())
ssl._create_default_https_context = lambda: ssl_context
os.environ['SSL_CERT_FILE'] = certifi.where()

DOWNLOADS_DIR = Path.home() / "Downloads"
COOKIES_FILE = Path("cookies.txt")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('app.log'), logging.StreamHandler()]
)

def human_like_delay():
    """Randomized human interaction simulation"""
    delays = [
        (0.5, 2),    # Short wait
        (2, 4),      # Medium wait
        (4, 6)       # Long wait (occasionally)
    ]
    min_s, max_s = random.choices(delays, weights=[60, 30, 10])[0]
    time.sleep(random.uniform(min_s, max_s))

@app.route("/")
def serve_frontend():
    return send_from_directory(app.static_folder, "FrontPage.html")

@app.route("/download", methods=["POST"])
def handle_download():
    try:
        human_like_delay()
        data = request.get_json()
        
        if not all([data.get("videoUrl"), data.get("downloadType")]):
            return jsonify({"error": "Missing required fields"}), 400

        video_url = data["videoUrl"]
        download_type = data["downloadType"]

        # ===== Enhanced YouTube Configuration =====
        ydl_opts = {
            "outtmpl": str(DOWNLOADS_DIR / "%(title)s.%(ext)s"),
            "nocheckcertificate": False,
            "ignoreerrors": False,
            "http_headers": {
                "User-Agent": random.choice([
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"
                ]),
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Referer": "https://www.youtube.com/",
                "Origin": "https://www.youtube.com",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site"
            },
            "ratelimit": random.randint(800000, 1200000),
            "retries": 3,
            "sleep_interval": random.randint(5, 20),
            "verbose": False
        }

        # ===== Cookie Handling =====
        if COOKIES_FILE.exists():
            ydl_opts.update({
                "cookiefile": str(COOKIES_FILE),
                "cookiesfrombrowser": ("chrome",) if os.name == 'nt' else ("chrome", "/home/user/.config/google-chrome")
            })
            logging.info("Using browser cookies for authentication")

        # ===== Format Handling =====
        format_selector = {
            "mp3": "bestaudio/best",
            "webm": "bestvideo[ext=webm]+bestaudio[ext=webm]/best[ext=webm]/best"
        }
        if download_type not in format_selector:
            return jsonify({"error": "Invalid download type"}), 400

        ydl_opts["format"] = format_selector[download_type]
        
        if download_type == "mp3":
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]

        # ===== Download Execution =====
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            human_like_delay()
            info = ydl.extract_info(video_url, download=True)
            
            if not info or 'title' not in info:
                raise yt_dlp.utils.DownloadError("Invalid video response")

            downloaded_file = Path(ydl.prepare_filename(info)).resolve()
            logging.info(f"Download successful: {downloaded_file}")

        return jsonify({
            "success": True,
            "path": str(downloaded_file),
            "filename": downloaded_file.name
        })

    except yt_dlp.utils.DownloadError as e:
        logging.error(f"Download failed: {str(e)}")
        return jsonify({"error": "YouTube requires verification. Please ensure valid cookies are provided."}), 400
        
    except Exception as e:
        logging.exception("Server error:")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)