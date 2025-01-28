import os
import certifi
import logging

print(f"[DEBUG] Certifi CA bundle path: {certifi.where()}")
print(f"[DEBUG] Files at certifi path: {os.listdir(os.path.dirname(certifi.where()))}")

# MUST BE AT VERY TOP - BEFORE ANY IMPORTS
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

from flask import Flask, request, jsonify
# Response, send_file
import yt_dlp
# import ssl
import random
import time
# import tempfile
# import shutil
# import mimetypes
# import re
from pathlib import Path

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
            # "outtmpl": os.path.join(os.path.expanduser("~"), "download", "%(title)s.%(ext)s"),
            "nocheckcertificate": False,
            "cookiefile": "cookies.txt" if Path("cookies.txt").exists() else None,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.youtube.com/",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            },
            "retries": 5,
            "socket_timeout": 30,
            "force_ipv4": True,
            "compat_opts": ["no-certifi"],
            "ssl_ca_certificates": certifi.where(),
        }

        # Default path for download (before "Save As")
        default_path = os.path.join(os.path.expanduser("~"), "test_files", "%(title)s")

        if download_type == "mp3":
            ydl_opts.update({
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
                "outtmpl": default_path + ".mp3"
            })
        elif download_type == "webm":
            ydl_opts.update({
                "format": "bestvideo+bestaudio/best",
                # "postprocessors": [{
                #     'key': 'FFmpegVideoConvertor',
                #     'preferedformat': 'webm'
                # }],
                "outtmpl": default_path + ".webm"
            })
        else:
            return jsonify({"error": "Invalid download type"}), 400

        if COOKIES_FILE.exists():
            ydl_opts["cookiefile"] = str(COOKIES_FILE)
            logging.info("Using cookies.txt for authentication")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        return jsonify({"message": f"Download completed successfully. File saved to {os.path.expanduser('~')}/download"}), 200

    except Exception as e:
        logging.error(f"Error occurred: {e}")
        return jsonify({"error": str(e)}), 500        

        

        #     info = ydl.extract_info(video_url, download=True)
        #     if not info:
        #         raise yt_dlp.utils.DownloadError("No video information found.")

        #     if 'requested_downloads' not in info or not info['requested_downloads']:
        #         raise yt_dlp.utils.DownloadError("Downloaded file information missing.")

        #     final_file = Path(info['requested_downloads'][0]['filepath']).resolve()


        #     if final_file.exists():
        #         try:
        #             # Use Flask's `send_file` for sending files with correct MIME type
        #             return send_file(
        #                 final_file,
        #                 as_attachment=True,
        #                 mimetype=mimetypes.guess_type(str(final_file))[0] or "application/octet-stream",
        #                 download_name=final_file.name,
        #             )
        #         except Exception as e:
        #             logging.exception("Failed to send the file.")
        #             return jsonify({"error": "Failed to prepare the file for download."}), 500            

        #     # if download_type == "mp3" and final_file.suffix != ".mp3":
        #     #     final_file = final_file.with_suffix(".mp3")

        #     if not final_file.exists():
        #         logging.error(f"File not found: {final_file}")
        #         return jsonify({"error": "Processed file not found"}), 500

        # mime_type, _ = mimetypes.guess_type(str(final_file))

        

        # with open(final_file, "rb") as file:
        #     response = Response(file.read(), mimetype=mime_type)
            
        #     # Set safe filename with URL encoding
        #     response.headers["Content-Disposition"] = (
        #         f"attachment; filename*=UTF-8''{quote(final_file.name)}"
        #     )
            
        #     response.headers["Content-Length"] = os.path.getsize(final_file)
        #     logging.info(f"Prepared file for download")
        #     return response



    except yt_dlp.utils.DownloadError as e:
        logging.error(f"Download error: {e}")
        return jsonify({"error": "Download failed. The video may require authentication or be restricted."}), 400

    except Exception as e:
        logging.exception("Unexpected server error")
        return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)