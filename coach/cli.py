"""Kompakte Übersicht für den Coach (Claude).

  python -m coach.cli status        Tagesform, nächste Einheiten, Aktivitäten ohne Feedback (JSON)
  python -m coach.cli sync          Garmin-Sync ausführen
  python -m coach.cli week [N]      Planwoche N inkl. Status (Standard: aktuelle Woche)
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta

from .analysis import build_state


def _aware(ts: str | None):
    if not ts:
        return None
    d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return d if d.tzinfo else d.astimezone()  # Feedback-Zeit ohne Zone = lokale Zeit


def _note_after_feedback(a: dict) -> bool:
    """Hat der Athlet nach dem Coach-Feedback noch etwas eingetragen?"""
    if not (a["feedback"] and a["athlete_note"]):
        return False
    n, f = _aware(a["athlete_note_at"]), _aware(a["feedback"].get("written"))
    return bool(n and f and n > f)


def _act_brief(a: dict) -> dict:
    an = a["analysis"]
    m = an["metrics"]
    return {
        "athlete_note": a["athlete_note"],
        "note_after_feedback": _note_after_feedback(a),
        "id": a["id"], "date": a["date"], "name": a["name"], "type": a["type"],
        "planned": a["session_title"], "kind": an["kind"], "auto_score": an["score"], "auto_rating": an["rating"],
        "dur_min": m["dur_min"], "dist_km": m["dist_km"], "pace": m.get("pace_s"), "avg_hr": m["avg_hr"],
        "max_hr": m["max_hr"], "zone_pct": m["zone_pct"], "vo2_min": m["vo2_min"], "rpe": m["rpe"],
        "vo2max": m["vo2max"], "reps": m.get("reps"), "auto_points": [f"[{p['level']}] {p['text']}" for p in an["points"]],
    }


def status() -> dict:
    s = build_state()
    today = s["today"]
    sessions = s["plan"]["sessions"]
    start = sessions[0]["date"] if sessions else today
    pending = [a for a in s["activities"] if a["date"] >= start and (not a["feedback"] or _note_after_feedback(a))]
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    pain = [{"date": a["date"], "name": a["name"], "pain": a["athlete_note"].get("pain"),
             "where": a["athlete_note"].get("pain_where"), "text": a["athlete_note"].get("text")}
            for a in s["activities"] if a["date"] >= week_ago and a["athlete_note"] and (a["athlete_note"].get("pain") or 0) > 0]
    upcoming = [x for x in sessions if x["date"] >= today][:5]
    cur_week = next((x["week"] for x in sessions if x["date"] == today), None)
    return {
        "today": today,
        "athlete": s["athlete"],
        "goal": s["goal"],
        "sync": {k: s["sync"].get(k) for k in ("last_sync", "ok", "errors")},
        "readiness": s["readiness"]["today"],
        "readiness_last7": s["readiness"]["series"][-7:],
        "vo2max_last": s["vo2"][-5:],
        "current_week": next((w for w in s["plan"]["weeks"] if w["week"] == cur_week), None),
        "upcoming": [{k: x[k] for k in ("id", "date", "weekday", "title", "kind", "key", "duration_min", "status", "adjusted")}
                     for x in upcoming],
        "missed": [{k: x[k] for k in ("id", "date", "title")} for x in sessions if x["status"] == "missed"][-5:],
        "pending_feedback": [_act_brief(a) for a in pending],
        "pain_reports_7d": pain,
        "recent_with_feedback": [{"id": a["id"], "date": a["date"], "name": a["name"],
                                  "headline": a["feedback"].get("headline")}
                                 for a in s["activities"] if a["feedback"]][:5],
    }


def main(argv: list[str]) -> None:
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "sync":
        from .sync import sync
        info = sync()
        print(json.dumps(info, ensure_ascii=False))
    elif cmd == "week":
        s = build_state()
        today = date.today().isoformat()
        n = int(argv[2]) if len(argv) > 2 else next((x["week"] for x in s["plan"]["sessions"] if x["date"] >= today), 0)
        out = [{k: x[k] for k in ("id", "date", "weekday", "title", "status", "activity_ids", "adjusted")}
               for x in s["plan"]["sessions"] if x["week"] == n]
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print(json.dumps(status(), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv)
