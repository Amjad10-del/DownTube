import os
import certifi
import logging
from flask import Flask, request, jsonify, Response, send_file
import yt_dlp
import ssl
import random
import time
from pathlib import Path
import mimetypes

app = Flask(__name__, static_folder="./FrontEnd", static_url_path="/")

# Configure SSL certificates
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

COOKIES_FILE = Path("cookies.txt")


# Function to simulate human-like delay
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

        # yt-dlp configuration
        ydl_opts = {
            "outtmpl": os.path.join(tempfile.gettempdir(), "%(title)s.%(ext)s"),
            "nocheckcertificate": False,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.youtube.com/",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            },
            "retries": 5,
            "socket_timeout": 30,
            "force_ipv4": True,
            "ssl_ca_certificates": certifi.where(),
        }

        # Add format-specific options
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
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'webm'
                }]
            })
        else:
            return jsonify({"error": "Invalid download type"}), 400

        # Use cookies if available
        if COOKIES_FILE.exists():
            ydl_opts["cookiefile"] = str(COOKIES_FILE)
            logging.info("Using cookies.txt for authentication")

        # Download the video using yt-dlp
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            if not info or 'requested_downloads' not in info or not info['requested_downloads']:
                raise yt_dlp.utils.DownloadError("Download failed or file information missing.")

            # Get the downloaded file path
            final_file = Path(info['requested_downloads'][0]['filepath']).resolve()

        # Validate and serve the file
        if final_file.exists():
            logging.info(f"File successfully downloaded: {final_file}")
            return send_file(
                final_file,
                as_attachment=True,
                mimetype=mimetypes.guess_type(str(final_file))[0] or "application/octet-stream",
                download_name=final_file.name,
            )
        else:
            logging.error(f"File not found after download: {final_file}")
            return jsonify({"error": "File not found after processing"}), 500

    except yt_dlp.utils.DownloadError as e:
        logging.error(f"Download error: {e}")
        return jsonify({"error": "Download failed. The video may require authentication or be restricted."}), 400

    except Exception as e:
        logging.exception("Unexpected server error")
        return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)
