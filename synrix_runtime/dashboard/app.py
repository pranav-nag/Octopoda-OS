"""
Synrix Agent Runtime — Dashboard Application
Flask application with SSE streaming for the real-time dashboard.
"""

import os
from pathlib import Path
from flask import Flask, send_from_directory
from flask_cors import CORS


def create_app():
    """Create and configure the Flask dashboard application."""
    static_dir = Path(__file__).parent / "static"
    app = Flask(__name__, static_folder=str(static_dir))
    CORS(app, origins=["http://localhost:7842", "http://127.0.0.1:7842"])

    from synrix_runtime.dashboard.api_routes import api
    app.register_blueprint(api)

    @app.route("/")
    def index():
        return send_from_directory(str(static_dir), "index.html")

    @app.route("/css/<path:filename>")
    def css(filename):
        return send_from_directory(str(static_dir / "css"), filename)

    @app.route("/js/<path:filename>")
    def js(filename):
        return send_from_directory(str(static_dir / "js"), filename)

    @app.route("/img/<path:filename>")
    def img(filename):
        return send_from_directory(str(static_dir / "img"), filename)

    return app


def run_dashboard(port=7842, debug=False):
    """Start the dashboard server."""
    app = create_app()
    print(f"[DASHBOARD] Starting on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)


if __name__ == "__main__":
    run_dashboard()
