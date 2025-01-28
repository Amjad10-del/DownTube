import os
import certifi
import logging
import tempfile
import shutil
from flask import Flask, request, jsonify, send_file
import yt_dlp
from pathlib import Path

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# Set SSL certificates
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

app = Flask(__name__, static_folder="./FrontEnd", static_url_path="/")

@app.route("/")
def serve_frontend():
    return app.send_static_file("FrontPage.html")

def get_ydl_options(download_type):
    """Return appropriate options based on download type"""
    base_options = {
        'nocheckcertificate': False,
        'retries': 10,
        'fragment_retries': 10,
        'ignoreerrors': False,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.youtube.com/',
        },
        'extractor_args': {
            'youtube': {'player_client': ['web', 'android']}
        },
    }

    if download_type == "mp3":
        base_options.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        })
    else:  # webm
        base_options.update({
            'format': 'bestvideo[ext=webm]+bestaudio[ext=webm]/best[ext=webm]'
        })

    return base_options

@app.route("/download", methods=["POST"])
def handle_download():
    try:
        data = request.get_json()
        if not data or not all([data.get("videoUrl"), data.get("downloadType")]):
            return jsonify({"error": "Missing required fields"}), 400

        video_url = data["videoUrl"]
        download_type = data["downloadType"]
        temp_dir = tempfile.mkdtemp()

        try:
            ydl_opts = get_ydl_options(download_type)
            ydl_opts['outtmpl'] = os.path.join(temp_dir, '%(title)s.%(ext)s')

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                filename = ydl.prepare_filename(info)

                # Handle post-processing for MP3
                if download_type == "mp3":
                    filename = os.path.splitext(filename)[0] + '.mp3'

                if not os.path.exists(filename):
                    raise FileNotFoundError("Downloaded file not found")

                # Send file to client
                return send_file(
                    filename,
                    as_attachment=True,
                    download_name=os.path.basename(filename),
                    mimetype='audio/mpeg' if download_type == 'mp3' else 'video/webm'
                )

        except yt_dlp.utils.DownloadError as e:
            logging.error(f"Download failed: {str(e)}")
            return jsonify({"error": "Download failed. The video may be unavailable or restricted."}), 400

        finally:
            # Clean up temporary files
            shutil.rmtree(temp_dir, ignore_errors=True)

    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=False
    )