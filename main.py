import os
import certifi
import logging
from flask import Flask, request, jsonify, send_file
import yt_dlp
import ssl
import random
import time
import tempfile
from pathlib import Path
from urllib.parse import quote
import mimetypes

app = Flask(__name__)

# SSL Configuration
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

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

        # Temporary directory for downloads
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "%(title)s.%(ext)s")
            ydl_opts = {
                "outtmpl": output_path,
                "nocheckcertificate": False,
                "cookiefile": str(COOKIES_FILE) if COOKIES_FILE.exists() else None,
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://www.youtube.com/",
                },
                "retries": 5,
                "socket_timeout": 30,
                "force_ipv4": True,
                "ssl_ca_certificates": certifi.where(),
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
                ydl_opts.update({
                    "format": "bestvideo[ext=webm]+bestaudio[ext=webm]/best[ext=webm]/best",
                    "merge_output_format": "webm",
                    "postprocessors": [{
                        "key": "FFmpegVideoConvertor",
                        "preferedformat": "webm"
                    }],
                })
            else:
                return jsonify({"error": "Invalid download type"}), 400

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                if not info:
                    raise yt_dlp.utils.DownloadError("No video information found.")
                
                downloaded_file_path = Path(ydl.prepare_filename(info))
                if not downloaded_file_path.exists():
                    logging.error(f"Downloaded file not found: {downloaded_file_path}")
                    return jsonify({"error": "Processed file not found"}), 500

                # Send the file back to the client
                return send_file(
                    downloaded_file_path,
                    as_attachment=True,
                    mimetype=mimetypes.guess_type(str(downloaded_file_path))[0] or "application/octet-stream",
                    download_name=downloaded_file_path.name,
                )
    except yt_dlp.utils.DownloadError as e:
        logging.error(f"Download error: {e}")
        return jsonify({"error": "Download failed. The video may require authentication or be restricted."}), 400

    except Exception as e:
        logging.exception("Unexpected server error")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)
