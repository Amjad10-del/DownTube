import os
import certifi
import logging
from http.cookiejar import MozillaCookieJar

print(f"[DEBUG] Certifi CA bundle path: {certifi.where()}")
print(f"[DEBUG] Files at certifi path: {os.listdir(os.path.dirname(certifi.where()))}")

# MUST BE AT VERY TOP - BEFORE ANY IMPORTS
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

from flask import Flask, request, jsonify, Response, send_file
import yt_dlp
import ssl
import random
import time
import tempfile
import shutil
import mimetypes
import re
import requests
from pathlib import Path
from urllib.parse import quote

app = Flask(__name__, static_folder="./FrontEnd", static_url_path="/")

# Critical SSL Configuration (MUST BE AT TOP)
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

# Log the paths to ensure they are set correctly
logging.info(f"SSL_CERT_FILE: {os.environ['SSL_CERT_FILE']}")
logging.info(f"REQUESTS_CA_BUNDLE: {os.environ['REQUESTS_CA_BUNDLE']}")

# Configure logging with UTF-8 encoding
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
    time.sleep(random.uniform(15, 30))

def sanitize_filename(filename: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", filename)

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

        # Common YDL options
        base_ydl_opts = {
            "nocheckcertificate": False,
            "retries": 5,
            "socket_timeout": 30,
            "skip": ["authcheck"],  # Bypass bot checks
            "force_ipv4": True,
            "compat_opts": ["no-certifi"],
            "ssl_ca_certificates": certifi.where(),
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.youtube.com/",
            }
        }

        if download_type == "webm":
            # Approach 1: Direct streaming for WebM
            ydl_opts = {
                **base_ydl_opts,
                "format": "bestvideo[ext=webm]+bestaudio[ext=webm]/best[ext=webm]/best",
                # "download": False  # Don't download, just get metadata
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                if not info:
                    raise yt_dlp.utils.DownloadError("No video information found")
                stream_url = info['formats'][-1]['url'] 
                if not stream_url:
                    raise yt_dlp.utils.DownloadError("NOT direct stream URL found" + stream_url.get('url'))

                print("Stream URL:", stream_url)

                # Prepare streaming headers
                headers = {"User-Agent": base_ydl_opts["http_headers"]["User-Agent"]}
                if COOKIES_FILE.exists():
                    cj = MozillaCookieJar()
                    cj.load(str(COOKIES_FILE), ignore_discard=True, ignore_expires=True)
                    headers.update({"Cookie": "; ".join([f"{c.name}={c.value}" for c in cj])})

                # Forward range headers for resumable downloads
                if 'Range' in request.headers:
                    headers['Range'] = request.headers['Range']

                # Stream directly from YouTube
                response = requests.get(stream_url, headers=headers, stream=True)
                response.raise_for_status()

                # Build streaming response
                def generate():
                    for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB chunks
                        if chunk:
                            yield chunk

                filename = sanitize_filename(info.get('title', 'video')) + ".webm"
                
                return Response(
                    generate(),
                    headers={
                        "Content-Type": "video/webm",
                        "Content-Disposition": f'attachment; filename="{filename}"',
                        "Content-Length": response.headers.get("Content-Length", ""),
                        "Accept-Ranges": "bytes"
                    },
                    status=response.status_code
                )

        elif download_type == "mp3":
            # Approach 2: Download + Process for MP3
            ydl_opts = {
                **base_ydl_opts,
                "outtmpl": os.path.join(tempfile.gettempdir(), "%(title)s.%(ext)s"),
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
                "keepvideo": False
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                if not info.get('requested_downloads'):
                    raise yt_dlp.utils.DownloadError("No download information found")

                final_path = Path(ydl.prepare_filename(info)).with_suffix('.mp3')
                if not final_path.exists():
                    raise FileNotFoundError("Processed MP3 file not found")

                return send_file(
                    final_path,
                    as_attachment=True,
                    mimetype="audio/mpeg",
                    download_name=sanitize_filename(info.get('title', 'audio')) + ".mp3"
                )

        else:
            return jsonify({"error": "Invalid download type"}), 400

    except yt_dlp.utils.DownloadError as e:
        logging.error(f"Download error: {e}")
        return jsonify({"error": "Download failed. The video may require authentication or be restricted."}), 400
    except requests.RequestException as e:
        logging.error(f"Streaming error: {e}")
        return jsonify({"error": "Streaming failed. Check network connection."}), 500
    except Exception as e:
        logging.exception("Unexpected server error")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)