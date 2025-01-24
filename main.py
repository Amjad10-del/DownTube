from flask import Flask, request, jsonify, send_from_directory
import yt_dlp
import os
import logging
import certifi
import ssl

app = Flask(__name__,static_folder="./FrontEnd", static_url_path="")


logging.basicConfig(level=logging.DEBUG)
# Force SSL certificate verification
ssl._create_default_https_context = ssl.create_default_context(cafile=certifi.where())
os.environ['SSL_CERT_FILE'] = certifi.where()

@app.route("/")
def index():
    return send_from_directory(app.static_folder,"FrontPage.html")

@app.route("/download", methods=["POST"])
def download_video():
    try:
        data = request.json
        video_url = data.get("videoUrl")
        download_type = data.get("downloadType")
        download_path = data.get("downloadPath")

        if not video_url or not download_type or not download_path:
            logging.debug(f"Invalid input: {data}")
            return jsonify({"message": "Invalid input. Please provide all required fields."}), 400

        # Create the directory if it doesn't exist (important!)
        os.makedirs(download_path, exist_ok=True)


        ydl_opts = {
            "outtmpl": os.path.join(download_path, "%(title)s.%(ext)s"),
            "nocheckcertificate": True,
            "ignoreerrors": True,
        }

        if download_type == "mp3":
            ydl_opts["format"] = "bestaudio/best"
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
        elif download_type != "webm":
            return jsonify({"message": "Invalid download type specified."}), 400

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logging.debug(f"Downloading video from URL: {video_url} to: {download_path}")
            ydl.download([video_url])

        return jsonify({"message": "Download completed successfully!"})

    except yt_dlp.utils.DownloadError as e:
        return jsonify({"message": f"Download error: {e}"}), 400
    except Exception as e:
        logging.exception("An error occurred during download:") # Log full traceback
        return jsonify({"message": f"An error occurred: {type(e).__name__}: {e}"}), 500

if __name__ == "__main__":
    app.run(debug=True)