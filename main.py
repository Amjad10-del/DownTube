from flask import Flask, request, jsonify, Response
import yt_dlp
import os
import logging
import certifi
import ssl
import random
import time
import tempfile
import shutil
import mimetypes
import re
from pathlib import Path
from urllib.parse import quote

app = Flask(__name__, static_folder="./FrontEnd", static_url_path="/")

# Configure logging with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

ssl_context = ssl.create_default_context(cafile=certifi.where())
ssl._create_default_https_context = lambda: ssl_context
os.environ['SSL_CERT_FILE'] = certifi.where()

COOKIES_FILE = Path("cookies.txt")

def human_like_delay():
    time.sleep(random.uniform(3, 10))

@app.route("/")
def serve_frontend():
    return app.send_static_file("FrontPage.html")

@app.route("/download", methods=["POST"])
def handle_download():
    try:
        human_like_delay()
        data = request.get_json()

        if not data or not all([data.get("videoUrl"), data.get("downloadType")]):
            return jsonify({"error": "Missing required fields: videoUrl or downloadType"}), 400

        video_url = data["videoUrl"]
        download_type = data["downloadType"]
        logging.info(f"Processing download for URL: {video_url}, Type: {download_type}")


        ydl_opts = {
            "outtmpl": os.path.join("~/download", "%(title)s.%(ext)s"),
            "nocheckcertificate": True,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.youtube.com/",
            },
            "retries": 3,
        }

        if download_type == "mp3":
            ydl_opts.update({
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
                "keepvideo": False,
            })
        elif download_type == "webm":
            ydl_opts["format"] = "bestvideo+bestaudio/best"
        else:
            return jsonify({"error": "Invalid download type"}), 400

        if COOKIES_FILE.exists():
            ydl_opts["cookiefile"] = str(COOKIES_FILE)
            logging.info("Using cookies.txt for authentication")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            if not info:
                raise yt_dlp.utils.DownloadError("No video information found.")

            if 'requested_downloads' not in info or not info['requested_downloads']:
                raise yt_dlp.utils.DownloadError("Downloaded file information missing.")

            final_file = Path(info['requested_downloads'][0]['filepath']).resolve()

            if download_type == "mp3" and final_file.suffix != ".mp3":
                final_file = final_file.with_suffix(".mp3")

            if not final_file.exists():
                logging.error(f"File not found: {final_file}")
                return jsonify({"error": "Processed file not found"}), 500

        mime_type, _ = mimetypes.guess_type(str(final_file))

        with open(final_file, "rb") as file:
            response = Response(file.read(), mimetype=mime_type)
            
            # Set safe filename with URL encoding
            response.headers["Content-Disposition"] = (
                f"attachment; "
            )
            
            response.headers["Content-Length"] = os.path.getsize(final_file)
            logging.info(f"Prepared file for download")
            return response

    except yt_dlp.utils.DownloadError as e:
        logging.error(f"Download error: {e}")
        return jsonify({"error": "Download failed. The video may require authentication or be restricted."}), 400

    except Exception as e:
        logging.exception("Unexpected server error")
        return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)