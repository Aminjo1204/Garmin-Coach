"""Online-Version auf Netlify (siehe docs/netlify.md).

  python -m coach.netlify setup [--url https://…]   Sync-Schlüssel erzeugen und auf Netlify setzen (einmalig)
  python -m coach.netlify pull                      Eingaben vom Handy holen und mit den lokalen zusammenführen
  python -m coach.netlify export                    statische Version nach dist/ schreiben
  python -m coach.netlify deploy                    pull + export + hochladen (für den Coach-Check)
  python -m coach.netlify preview                   dist/ lokal ansehen wie online (Port 5058, ohne Login)
"""

from __future__ import annotations

import json
import secrets
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime

from . import userdata
from .analysis import build_state
from .config import FIT_DIR, ROOT

CONF_FILE = ROOT / "netlify.local.json"   # {"site_url": "...", "sync_key": "..."} – nicht im Repo
DIST = ROOT / "dist"
NETLIFY_CLI = "netlify-cli@27.14.1"


def conf() -> dict | None:
    try:
        return json.loads(CONF_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _cli(*args: str, capture: bool = False) -> subprocess.CompletedProcess:
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        raise SystemExit("npx nicht gefunden – bitte Node.js installieren.")
    return subprocess.run([npx, "-y", NETLIFY_CLI, *args], cwd=ROOT, check=True, text=True,
                          capture_output=capture, encoding="utf-8")


def _request(method: str, data: dict | None = None) -> dict:
    c = conf()
    req = urllib.request.Request(
        c["site_url"].rstrip("/") + "/api/userdata", method=method,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"x-coach-key": c["sync_key"], "content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def pull() -> bool:
    """Eingaben vom Handy holen, zusammenführen, beide Seiten aktualisieren."""
    if not conf():
        return False
    remote = _request("GET")
    merged = userdata.merge(userdata.load(), remote)
    userdata.save(merged)
    _request("PUT", merged)
    return True


def export() -> None:
    shutil.rmtree(DIST, ignore_errors=True)
    shutil.copytree(ROOT / "web", DIST)
    state = build_state()
    state["static"] = True
    state["exported"] = datetime.now().isoformat(timespec="seconds")
    data = DIST / "data"
    (data / "activity").mkdir(parents=True)
    (data / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    for a in state["activities"]:
        src = FIT_DIR / f"{a['id']}.json"
        if src.exists():
            shutil.copyfile(src, data / "activity" / f"{a['id']}.json")


def deploy() -> None:
    if not conf():
        raise SystemExit("Noch nicht eingerichtet: siehe docs/netlify.md (python -m coach.netlify setup).")
    try:
        pull()
    except Exception as exc:  # Online-Abgleich soll das Hochladen nicht verhindern
        print(f"Hinweis: Eingaben vom Handy konnten nicht geholt werden ({exc}).")
    export()
    if not (ROOT / "node_modules" / "@netlify" / "blobs").exists():
        subprocess.run([shutil.which("npm") or "npm.cmd", "install", "--no-audit", "--no-fund"], cwd=ROOT, check=True)
    _cli("deploy", "--prod", "--dir", "dist", "--message", f"Coach-Check {datetime.now():%d.%m. %H:%M}")
    print("Online-Version aktualisiert:", conf()["site_url"])


def setup(url: str | None) -> None:
    if not url:
        status = json.loads(_cli("status", "--json", capture=True).stdout or "{}")
        site = status.get("siteData") or {}
        url = site.get("site-url") or site.get("url")
    if not url:
        raise SystemExit("Seiten-URL nicht gefunden. Bitte mit --url https://deine-seite.netlify.app angeben.")
    old = conf() or {}
    key = old.get("sync_key") or secrets.token_urlsafe(32)
    _cli("env:set", "COACH_SYNC_KEY", key, capture=True)
    CONF_FILE.write_text(json.dumps({"site_url": url.rstrip("/"), "sync_key": key}, indent=1), encoding="utf-8")
    print(f"Eingerichtet für {url}. Sync-Schlüssel ist auf Netlify gesetzt und in {CONF_FILE.name} gespeichert.")


def preview(port: int = 5058) -> None:
    """dist/ ausliefern und die Umleitungen aus netlify.toml nachbilden. Login und Online-Speicher fehlen hier."""
    from flask import Flask, abort, send_from_directory

    if not (DIST / "data" / "state.json").exists():
        export()
    app = Flask(__name__, static_folder=None)
    app.get("/api/state", endpoint="state")(lambda: send_from_directory(DIST / "data", "state.json"))
    app.get("/api/activity/<aid>", endpoint="activity")(
        lambda aid: send_from_directory(DIST / "data" / "activity", f"{aid}.json"))
    app.route("/api/userdata", methods=["GET", "POST"], endpoint="userdata")(lambda: abort(404))
    app.get("/", endpoint="root")(lambda: send_from_directory(DIST, "index.html"))
    app.get("/<path:p>", endpoint="files")(lambda p: send_from_directory(DIST, p))
    app.run(host="127.0.0.1", port=port)


def main(argv: list[str]) -> None:
    cmd = argv[1] if len(argv) > 1 else "deploy"
    if cmd == "setup":
        setup(argv[argv.index("--url") + 1] if "--url" in argv else None)
    elif cmd == "pull":
        print("Abgeglichen." if pull() else "Keine Online-Version eingerichtet.")
    elif cmd == "export":
        export()
        print(f"Statische Version in {DIST}")
    elif cmd == "deploy":
        deploy()
    elif cmd == "preview":
        import os
        preview(int(os.environ.get("PORT", 5058)))
    else:
        print(__doc__)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv)
