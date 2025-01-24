from flask import Flask, request, jsonify, send_from_directory
import yt_dlp
import os
import logging
import certifi
import ssl
import random
import time
from pathlib import Path

app = Flask(__name__, static_folder="./FrontEnd", static_url_path="")

# SSL Configuration
ssl_context = ssl.create_default_context(cafile=certifi.where())
ssl._create_default_https_context = lambda: ssl_context
os.environ['SSL_CERT_FILE'] = certifi.where()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('app.log'), logging.StreamHandler()]
)

COOKIES_PATH = Path("cookies.txt")

def human_like_delay(min_sec=1, max_sec=3):
    time.sleep(random.uniform(min_sec, max_sec))

def validate_cookies():
    if COOKIES_PATH.exists():
        logging.info("Valid cookies file found")
        return True
    logging.warning("No cookies.txt file found - bot detection likely")
    return False

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "FrontPage.html")

@app.route("/download", methods=["POST"])
def download_video():
    try:
        human_like_delay(0.5, 1.5)
        data = request.get_json()
        
        # Extract parameters
        video_url = data.get("videoUrl")
        download_type = data.get("downloadType")
        download_path = data.get("downloadPath", "downloads")

        if not all([video_url, download_type]):
            return jsonify({"message": "Missing required fields"}), 400

        os.makedirs(download_path, exist_ok=True)

        # Configure download options with cookies
        ydl_opts = {
            "outtmpl": os.path.join(download_path, "%(title)s.%(ext)s"),
            "nocheckcertificate": False,
            "ignoreerrors": False,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.youtube.com/"
            },
            "cookiefile": str(COOKIES_PATH) if validate_cookies() else None,
            "ratelimit": 1_500_000,
            "retries": 5,
            "sleep_interval": random.randint(5, 15),
            "throttled_duration": 45,
            "verbose": False
        }

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
            return jsonify({"message": "Invalid download type"}), 400

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            human_like_delay(1, 2)
            info = ydl.extract_info(video_url, download=True)
            
            # Enhanced validation
            if not info or 'title' not in info:
                logging.error(f"Invalid video info: {info}")
                raise yt_dlp.utils.DownloadError("Invalid video response")

            logging.info(f"Downloaded: {info['title']}")

        return jsonify({
            "success": True,
            "message": "Download completed",
            "title": info['title'][:50] + "..." if len(info['title']) > 50 else info['title']
        })

    except yt_dlp.utils.DownloadError as e:
        logging.error(f"Download failed: {str(e)}")
        return jsonify({"message": f"YouTube error: {str(e)}"}), 400
        
    except Exception as e:
        logging.exception("Critical error:")
        return jsonify({"message": "Internal server error"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False)