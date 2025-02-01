#!/usr/bin/env python3
import os
import logging
import random
import time
import tempfile
import shutil
import re
import atexit
from pathlib import Path
from flask import Flask, request, jsonify, send_file, Response
import yt_dlp
import certifi
from werkzeug.utils import secure_filename
import requests
from http.cookiejar import MozillaCookieJar

# --------------------------
# Configuration and Logging
# --------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

app = Flask(__name__, static_folder="./FrontEnd", static_url_path="/")

# Configure SSL certificates
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

# Global Constants
TEMP_DIR = Path(tempfile.gettempdir()) / "ytdl_downloads"
TEMP_DIR.mkdir(exist_ok=True, parents=True)
COOKIES_PATH = TEMP_DIR / "cookies.txt"
ALLOWED_COOKIE_EXT = {".txt"}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0"
]

# --------------------------
# Utility Functions
# --------------------------
def human_like_delay():
    """Simulate a human-like delay."""
    delay = random.uniform(5, 15)
    logging.info(f"Sleeping for {delay:.2f} seconds to mimic human interaction.")
    time.sleep(delay)

def sanitize_filename(filename: str) -> str:
    """Sanitize filenames using secure_filename and limiting length."""
    safe_name = secure_filename(filename)
    return safe_name[:200]

def get_random_headers() -> dict:
    """Return a set of realistic randomized HTTP headers."""
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

def cleanup_file(file_path: Path):
    """Attempt to remove a file, logging any exceptions."""
    try:
        if file_path.exists():
            file_path.unlink()
            logging.info(f"Cleaned up file: {file_path}")
    except Exception as e:
        logging.warning(f"Cleanup failed for {file_path}: {str(e)}")

# --------------------------
# Flask Endpoints
# --------------------------
@app.route("/", methods=["GET"])
def serve_frontend():
    """Serve the main frontend HTML file."""
    return app.send_static_file("FrontPage.html")

@app.route("/upload-cookies", methods=["POST"])
def upload_cookies():
    """Allow users to upload a cookies.txt file."""
    if "cookies" not in request.files:
        return jsonify({"error": "No file part in the request."}), 400

    file = request.files["cookies"]
    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_COOKIE_EXT:
        return jsonify({"error": "Invalid file type. Only .txt files are allowed."}), 400

    try:
        file.save(COOKIES_PATH)
        logging.info("Cookies uploaded successfully.")
        return jsonify({"message": "Cookies uploaded successfully."}), 200
    except Exception as e:
        logging.exception("Failed to save cookies file.")
        return jsonify({"error": "Failed to save cookies file."}), 500

@app.route("/download", methods=["POST"])
def handle_download():
    """
    Main download endpoint.
    Expects JSON with 'videoUrl' and 'downloadType' (supported: video, mp3, webm).
    """
    try:
        human_like_delay()
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON payload provided."}), 400

        video_url = data.get("videoUrl")
        download_type = data.get("downloadType", "").strip().lower()

        if not video_url or not download_type:
            return jsonify({"error": "Missing required parameters."}), 400

        logging.info(f"Received download request: URL={video_url} Type={download_type}")

        # Load cookies if available
        cookiefile = str(COOKIES_PATH) if COOKIES_PATH.exists() else None

        base_ydl_opts = {
            "noplaylist": True,
            "logger": logging,
            "outtmpl": str(TEMP_DIR / "%(title)s.%(ext)s"),
            "http_headers": get_random_headers(),
            "cookiefile": cookiefile,
            "ssl_ca_certificates": certifi.where(),
            "ignoreerrors": False,
            "retries": 3,
            "fragment_retries": 3,
            "skip_unavailable_fragments": False,
            "verbose": True  # Add verbose logging
        }

        if download_type == "webm":
            # Approach 1: Direct streaming for WebM
            ydl_opts = {
                **base_ydl_opts,
                "format": "bestvideo[ext=webm]+bestaudio[ext=webm]/best[ext=webm]/best",
                "download": False  # Don't download, just get metadata
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                if not info:
                    raise yt_dlp.utils.DownloadError("No video information found")

                formats = info.get('formats', [])
                stream_url = None

                for fmt in formats:
                    if fmt.get('ext') == 'webm' and fmt.get('url'):
                        stream_url = fmt['url']
                        break

                if not stream_url:
                    raise yt_dlp.utils.DownloadError("No direct stream URL found")

                # Prepare streaming headers
                headers = {"User-Agent": base_ydl_opts["http_headers"]["User-Agent"]}
                if COOKIES_PATH.exists():
                    cj = MozillaCookieJar()
                    cj.load(str(COOKIES_PATH), ignore_discard=True, ignore_expires=True)
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
        error_message = str(e)
        if "Sign in to confirm you’re not a bot" in error_message:
            logging.error(f"Download error: {e}")
            return jsonify({"error": "Download failed. Please sign in to confirm you’re not a bot and upload the cookies file again. You can also try using a VPN or updating yt-dlp."}), 400
        else:
            logging.error(f"Download error: {e}")
            return jsonify({"error": "Download failed. The video may require authentication or be restricted."}), 400
    except requests.RequestException as e:
        logging.error(f"Streaming error: {e}")
        return jsonify({"error": "Streaming failed. Check network connection."}), 500
    except Exception as e:
        logging.exception("Unexpected server error")
        return jsonify({"error": "Internal server error"}), 500

# --------------------------
# Cleanup on Exit
# --------------------------
@atexit.register
def cleanup_temp_dir():
    """Clean up all temporary files on exit."""
    try:
        for file in TEMP_DIR.glob("*"):
            file.unlink(missing_ok=True)
        logging.info("Temporary directory cleaned up on exit.")
    except Exception as e:
        logging.warning(f"Error during temporary directory cleanup: {str(e)}")

# --------------------------
# Main Execution
# --------------------------
if __name__ == "__main__":
    TEMP_DIR.mkdir(exist_ok=True, parents=True)
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
