from flask import Flask, request, jsonify, send_from_directory
import yt_dlp
import os
import logging
import certifi
import ssl

app = Flask(__name__, static_folder="./FrontEnd", static_url_path="")

# Configure SSL context before anything else
ssl_context = ssl.create_default_context(cafile=certifi.where())
ssl._create_default_https_context = lambda: ssl_context
os.environ['SSL_CERT_FILE'] = certifi.where()

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
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
        download_path = data.get("downloadPath", "downloads")

        if not all([video_url, download_type]):
            return jsonify({"message": "Missing required fields"}), 400

        os.makedirs(download_path, exist_ok=True)

        ydl_opts = {
            "outtmpl": os.path.join(download_path, "%(title)s.%(ext)s"),
            "ignoreerrors": False,
            "verbose": False,
            "nocheckcertificate": False,  # Enable certificate check
            "socket_timeout": 30,
            "source_address": "0.0.0.0",
            "certifi_ca_bundle": certifi.where(),  # Explicit CA bundle
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
            }
        }

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
            info = ydl.extract_info(video_url, download=True)
            if not info:
                raise yt_dlp.utils.DownloadError("No video information found")

        return jsonify({"message": "Download completed successfully!"})

    except yt_dlp.utils.DownloadError as e:
        logging.error(f"Download error: {str(e)}")
        return jsonify({"message": f"Download failed: {str(e)}"}), 400
    except Exception as e:
        logging.exception("Critical error occurred:")
        return jsonify({"message": "Internal server error"}), 500

if __name__ == "__main__":
    app.run(debug=False)