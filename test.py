from flask import Flask, request, jsonify, send_file

app = Flask(__name__, static_folder="./FrontEnd", static_url_path="/")

@app.route("/", methods=["GET"])
def serve_frontend():
    """Serve the frontend HTML file."""
    return app.send_static_file("FrontPage.html")