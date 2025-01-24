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

# Configure base download directory (absolute path)
DOWNLOADS_DIR = Path.home() / "DownTube/Downloads"  # Creates in user's home folder
DOWNLOADS_DIR.mkdir(exist_ok=True)  # Ensure directory exists

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

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "FrontPage.html")

@app.route("/download", methods=["POST"])
def download_video():
    try:
        data = request.get_json()
        video_url = data.get("videoUrl")
        download_type = data.get("downloadType")
        
        # Use fixed download directory
        download_path = DOWNLOADS_DIR
        
        # Validate inputs
        if not all([video_url, download_type]):
            return jsonify({"message": "Missing required fields"}), 400

        ydl_opts = {
            # Absolute path for output template
            "outtmpl": str(download_path / "%(title)s.%(ext)s"),
            "nocheckcertificate": False,
            "ignoreerrors": False,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.youtube.com/"
            },
            "ratelimit": 1_500_000,
            "retries": 3,
            "verbose": True
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
            # Add human-like delay
            time.sleep(random.uniform(1, 2))
            
            info = ydl.extract_info(video_url, download=True)
            
            if not info:
                raise yt_dlp.utils.DownloadError("No video information found")
            
            # Get actual saved file path
            downloaded_file = ydl.prepare_filename(info)
            downloaded_file = Path(downloaded_file).resolve()  # Get absolute path
            
            logging.info(f"File saved to: {downloaded_file}")

        return jsonify({
            "success": True,
            "message": "Download completed!",
            "path": str(downloaded_file),
            "file": os.path.basename(downloaded_file)
        })

    except yt_dlp.utils.DownloadError as e:
        logging.error(f"Download failed: {str(e)}")
        return jsonify({"message": f"Download error: {str(e)}"}), 400
        
    except Exception as e:
        logging.exception("Critical error:")
        return jsonify({"message": "Internal server error"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)