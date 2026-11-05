"""Coach-Web-App. Start:  .venv\\Scripts\\python.exe app.py  → http://127.0.0.1:5057"""

from __future__ import annotations

import os
import threading

from flask import Flask, jsonify, send_from_directory

from coach.analysis import activity_detail, build_state
from coach.config import ROOT
from coach.sync import sync

app = Flask(__name__, static_folder=str(ROOT / "web"), static_url_path="")
_sync_lock = threading.Lock()


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/state")
def state():
    return jsonify(build_state())


@app.post("/api/sync")
def do_sync():
    if not _sync_lock.acquire(blocking=False):
        return jsonify({"busy": True}), 409
    try:
        info = sync(log=lambda *_: None)
    finally:
        _sync_lock.release()
    return jsonify({"sync": info, "state": build_state()})


@app.get("/api/activity/<int:aid>")
def detail(aid: int):
    d = activity_detail(aid)
    return (jsonify(d), 200) if d else (jsonify({"error": "keine FIT-Daten"}), 404)


@app.after_request
def no_cache(resp):
    resp.headers["Cache-Control"] = "no-store"
    return resp


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5057)), debug=False)
