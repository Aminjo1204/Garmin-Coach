"""Erzeugt den 12-Wochen-VO2max-Plan als plan/plan.json aus athlete.json.

Aufruf:  python -m coach.plan_builder [--force]
Ohne --force wird ein bestehender Plan nicht überschreiben (der Coach passt ihn laufend an).

Anpassen: Die Wochen stehen in WEEKS weiter unten, die Bausteine (vo2, pyramid, threshold, …) darüber.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, timedelta

from .config import (ATHLETE, BIKE_ZONES, EASY_CAP_RUN, HR_TARGETS as HR, PACES, PLAN_FILE, PLAN_INTRO_DAYS,
                     PLAN_START, RUN_ZONES, THR_HI, VO2_HR)

# ---------- Bausteine ----------


def step(kind, label, minutes, zone, hr=None, pace=None, note=None):
    return {"type": kind, "label": label, "min": round(minutes, 2), "zone": zone, "hr": hr, "pace": pace, "note": note}


def rep(times, *steps, label=None):
    return {"type": "repeat", "times": times, "label": label, "steps": list(steps)}


def warmup(minutes=15, strides=3):
    note = f"inkl. {strides} Steigerungen à 20 s am Ende" if strides else None
    return step("warmup", "Einlaufen", minutes, 2, HR["wu"], PACES["easy"], note)


def cooldown(minutes=10):
    return step("cooldown", "Auslaufen", minutes, 1, HR["wu"], "locker")


def jog(minutes, label="Trabpause"):
    return step("recovery", label, minutes, 1, HR["jog"], "locker traben")


def pace_sec(p: str | None) -> float:
    """'6:50–7:30' → Mittelwert in s/km. Unbekannt → 7:00."""
    if not p:
        return 420
    vals = [int(m) * 60 + int(s) for m, s in re.findall(r"(\d+):(\d\d)", p)]
    return sum(vals) / len(vals) if vals else 420


def flat_steps(steps):
    for s in steps:
        if s["type"] == "repeat":
            for _ in range(s["times"]):
                yield from flat_steps(s["steps"])
        else:
            yield s


def totals(steps):
    mins = sum(s["min"] for s in flat_steps(steps))
    km = sum(s["min"] * 60 / pace_sec(s.get("pace")) for s in flat_steps(steps))
    return round(mins), round(km, 1)


def fmt_min(m):
    return f"{m:g}"


# ---------- Einheiten ----------

PURPOSE = {
    "vo2": "Schlüsseleinheit für deinen VO2max: Intervalle von 3–6 min bei 90–95 % HFmax halten Herz und Sauerstoffaufnahme "
    "lange nahe am Maximum. Genau dieser Reiz hebt den VO2max am stärksten an. Die Form wechselt, der Reiz bleibt.",
    "short": "Kurze Intervalle mit kurzen Pausen: Du sammelst viele Minuten nahe VO2max, weil der Puls in den Pausen "
    "oben bleibt. Studien zeigen hier besonders starke VO2max-Zuwächse.",
    "threshold": "Schwellentraining verschiebt deine Laktatschwelle nach oben: Du kannst dann einen größeren Anteil deines "
    "VO2max dauerhaft nutzen. Kontrolliert hart, nicht am Limit.",
    "tempo": "Längerer Block an der Schwelle: lehrt den Körper, Laktat effizient abzubauen und Tempo lange zu halten.",
    "progression": "Startet locker und wird stufenweise schneller. Trainiert Tempogefühl und Ermüdungsresistenz.",
    "hills": "Bergintervalle: hohe Herzfrequenz bei weniger Stoßbelastung, dazu mehr Kraft und bessere Laufökonomie.",
    "easy": "Lockerer Lauf für Erholung und Grundlage. Wirklich locker bleiben: Hier entsteht die Basis, die harte Einheiten erst möglich macht.",
    "long": "Langer Lauf in der Grundlage: mehr Mitochondrien, mehr Kapillaren, größeres Schlagvolumen des Herzens. "
    "Das ist das Fundament für einen höheren VO2max. Tempo ist hier egal, Puls zählt.",
    "test": "5-km-Test: misst deinen Fortschritt objektiv und liefert Garmin einen frischen VO2max-Wert. "
    "Danach werden Paces und Zonen angepasst.",
    "bike_z2": "Lockere Radeinheit: zusätzliches Ausdauertraining ohne Stoßbelastung. Gut für die Erholung und für mehr Volumen.",
    "strength": "Krafttraining für Läufer: stärkere Beine und Sehnen bedeuten bessere Laufökonomie und weniger Verletzungen. "
    "Schwer, aber nie bis zum Muskelversagen.",
    "rest": "Ruhetag. Anpassung passiert in der Erholung, nicht im Training.",
}

VO2_TIPS = [
    "Die ersten 1–2 Wiederholungen bewusst kontrolliert laufen. Die letzte soll genauso schnell sein wie die erste.",
    f"Der Puls steigt mit Verzögerung: Ab der 2. Hälfte jeder Wiederholung solltest du über {VO2_HR} bpm sein.",
    "Pausen locker traben, nicht stehen bleiben.",
]


def run_session(kind, title, steps, tips=None, key=False):
    mins, km = totals(steps)
    return {"sport": "run", "kind": kind, "title": title, "key": key, "duration_min": mins, "distance_km": km,
            "purpose": PURPOSE[kind if kind in PURPOSE else "easy"], "steps": steps, "tips": tips or []}


def work(label, minutes, pace=None, zone=5, hr=None, note=None):
    return step("work", label, minutes, zone, hr or HR["vo2"], pace or PACES["vo2"], note)


def vo2(reps, minutes, rest, pace=None, extra_tip=None):
    """Klassisch: N × M min."""
    tips = ([extra_tip] if extra_tip else []) + VO2_TIPS
    w = work(f"{fmt_min(minutes)} min schnell", minutes, pace)
    return run_session("vo2", f"VO2max: {reps} × {fmt_min(minutes)} min",
                       [warmup(15), rep(reps, w, jog(rest)), cooldown(10)], tips, key=True)


def pyramid(mins: list, rest_ratio=0.75, pace=None, name="Pyramide"):
    """Belastungen mit wechselnder Länge, Pause = rest_ratio × Belastung (mind. 1:30)."""
    steps = [warmup(15)]
    for i, m in enumerate(mins):
        steps.append(work(f"{fmt_min(m)} min schnell", m, pace))
        if i < len(mins) - 1:
            steps.append(jog(max(1.5, round(m * rest_ratio * 2) / 2)))
    steps.append(cooldown(10))
    tips = [f"{name}: Kürzere Abschnitte etwas schneller als die langen, aber alles im VO2max-Bereich.",
            "Auf der Uhr Schritt für Schritt anlegen (keine Wiederholung möglich)."] + VO2_TIPS[1:]
    return run_session("vo2", f"{name} {'-'.join(fmt_min(m) for m in mins)} min", steps, tips, key=True)


def distance_reps(reps, meters, rest, pace=None):
    """N × X m – Distanz statt Zeit (Bahn oder flache Strecke)."""
    pace = pace or PACES["vo2"]
    minutes = meters / 1000 * pace_sec(pace) / 60
    w = work(f"{meters} m schnell", minutes, pace, note=f"Distanz-Schritt ({meters} m)")
    return run_session("vo2", f"VO2max: {reps} × {meters} m", [warmup(15), rep(reps, w, jog(rest)), cooldown(10)],
                       ["Ideal auf der Bahn oder einer flachen, vermessenen Strecke.",
                        f"Ziel-Pace {pace} /km ≈ {minutes:.1f} min pro Wiederholung."] + VO2_TIPS[1:], key=True)


def hill_reps(reps, minutes, pace_note="hart, ~5-km-Gefühl"):
    w = step("work", f"{fmt_min(minutes)} min bergauf", minutes, 5, HR["vo2"], pace_note, "Steigung 4–7 %")
    r = step("recovery", "Bergab traben", minutes, 1, HR["jog"], "locker")
    return run_session("hills", f"Bergintervalle: {reps} × {fmt_min(minutes)} min",
                       [warmup(15, 2), rep(reps, w, r), cooldown(10)],
                       ["Nach Puls und Gefühl laufen, nicht nach Pace: Bergauf ist die Pace langsamer.",
                        "Aufrecht, aktive Arme, kurze schnelle Schritte.",
                        "Kein Hügel? Laufband mit 5–6 % Steigung."], key=True)


def short_intervals(sets, reps=13, on=30, off=15, pace=None):
    pace = pace or PACES["short"]
    block = rep(reps, step("work", f"{on} s schnell", on / 60, 5, HR["short"], pace),
                step("recovery", f"{off} s locker", off / 60, 2, None, "sehr locker traben"), label="Satz")
    steps = [warmup(15)]
    for i in range(sets):
        steps.append(block)
        if i < sets - 1:
            steps.append(jog(3, "Satzpause"))
    steps.append(cooldown(10))
    tips = [f"{on} s schnell, aber nicht sprinten, etwa 3-km-Renntempo.",
            f"Die {off}-s-Pausen sind kurz. Genau das hält den Puls oben, der Reiz kommt über die Summe.",
            f"Auf der Uhr als Workout mit Wiederholungen anlegen ({on} s / {off} s, {reps}×)."]
    title = f"{on}/{off}-Intervalle: " + (f"{sets} × {reps}" if sets > 1 else f"{reps} Wdh.")
    return run_session("short", title, steps, tips, key=True)


def fartlek(reps, on=1, off=1):
    w = step("work", f"{fmt_min(on)} min zügig", on, 4, None, PACES["vo2"], "nach Gefühl, ~5-km-Tempo")
    r = step("recovery", f"{fmt_min(off)} min locker", off, 2, HR["jog"], "locker")
    return run_session("vo2", f"Fahrtspiel: {reps} × {fmt_min(on)} min", [warmup(15, 0), rep(reps, w, r), cooldown(10)],
                       ["Entlastungswoche: zügig, aber nicht am Limit. Spaß an der Geschwindigkeit."], key=False)


def threshold(blocks, minutes, rest, pace=None):
    pace = pace or PACES["threshold"]
    w = step("work", f"{fmt_min(minutes)} min Schwelle", minutes, 4, HR["thr"], pace)
    steps = [warmup(15, 2), rep(blocks, w, jog(rest)) if blocks > 1 else w, cooldown(10)]
    tips = ["Schwelle heißt »angenehm hart«: Du könntest noch 2–3 Wörter sprechen.",
            f"Puls über {THR_HI} bedeutet zu schnell. Dann wird es eine VO2max-Einheit, und die steht schon am Mittwoch an.",
            "Gleichmäßig laufen, kein Endspurt."]
    title = f"Schwelle: {blocks} × {fmt_min(minutes)} min" if blocks > 1 else f"Tempodauerlauf: {fmt_min(minutes)} min Schwelle"
    return run_session("threshold" if blocks > 1 else "tempo", title, steps, tips, key=True)


def cruise(reps, meters=1000, rest=1):
    minutes = meters / 1000 * pace_sec(PACES["threshold"]) / 60
    w = step("work", f"{meters} m Schwelle", minutes, 4, HR["thr"], PACES["threshold"], f"Distanz-Schritt ({meters} m)")
    return run_session("threshold", f"Cruise-Intervalle: {reps} × {meters} m",
                       [warmup(15, 2), rep(reps, w, jog(rest)), cooldown(10)],
                       ["Kurze Pausen, Schwellentempo: Am Ende soll es sich wie ein langer Tempolauf anfühlen.",
                        f"Puls in den Abschnitten {HR['thr'][0]}–{HR['thr'][1]} bpm."], key=True)


def progression(total):
    third = total // 3
    steps = [step("steady", "Locker", third, 2, HR["easy"], PACES["easy"]),
             step("steady", "Zügig", third, 3, HR["tempo"], PACES["tempo"]),
             step("work", "Schwellentempo", total - 2 * third, 4, HR["thr"], PACES["threshold"]),
             cooldown(5)]
    return run_session("progression", f"Progressionslauf {total} min", steps,
                       ["Jedes Drittel etwas schneller. Das letzte Drittel ist an der Schwelle, nicht darüber."], key=True)


def hill_sprints(reps, sec=60):
    w = step("work", f"{sec} s bergauf", sec / 60, 5, HR["vo2"], "kräftig, ~5-km-Gefühl", "Steigung 5–8 %")
    r = step("recovery", "Bergab gehen/traben", 1.5, 1, HR["jog"], "locker")
    return run_session("hills", f"Bergsprints: {reps} × {sec} s", [warmup(15, 2), rep(reps, w, r), cooldown(10)],
                       ["Aufrecht laufen, aktive Arme, kurze schnelle Schritte.",
                        "Kein passender Hügel? Laufband mit 6 % oder Brückenrampe."], key=True)


def easy(minutes, strides=0):
    steps = [step("steady", "Locker", minutes, 2, HR["easy"], PACES["easy"])]
    if strides:
        steps.append(rep(strides, step("work", "Steigerung 20 s", 1 / 3, 4, None, PACES["strides"]),
                         step("recovery", "Gehen/Traben", 2 / 3, 1, None, "locker"), label="Steigerungen"))
    title = f"Locker {minutes} min" + (f" + {strides} Steigerungen" if strides else "")
    return run_session("easy", title, steps,
                       [f"Puls unter {EASY_CAP_RUN}. Wenn nötig langsamer laufen oder kurz gehen, das ist völlig okay.",
                        "Steigerungen: über 20 s von locker auf schnell beschleunigen, locker und technisch sauber."])


def long_run(minutes, finish=None):
    if finish:
        steps = [step("steady", "Grundlage", minutes - finish, 2, HR["easy"], PACES["long"]),
                 step("work", "Endbeschleunigung", finish, 3, HR["tempo"], PACES["tempo"])]
        title = f"Langer Lauf {minutes} min (letzte {finish} min zügig)"
    else:
        steps = [step("steady", "Grundlage", minutes, 2, HR["easy"], PACES["long"])]
        title = f"Langer Lauf {minutes} min"
    return run_session("long", title, steps,
                       [f"Puls {HR['easy'][0]}–{HR['easy'][1]} zählt, nicht die Pace. Bergauf langsamer werden.",
                        "Ab 75 min etwas trinken, bei 90+ min ein Gel oder Riegel mitnehmen."])


def test5k():
    steps = [warmup(15, 3), step("work", "5 km Test", pace_sec(PACES["five_k"]) * 5 / 60, 5, None,
                                 "so schnell wie gleichmäßig möglich", f"Referenz: {PACES['five_k']} /km"),
             cooldown(10)]
    return run_session("test", "5-km-Test", steps,
                       ["Flache Strecke, ausgeruht, nicht nüchtern.",
                        "Ersten Kilometer kontrolliert, dann steigern. Letzter Kilometer alles raus.",
                        "Uhr: als normalen Lauf starten, beim Teststart und am Ende eine Runde drücken."], key=True)


def bike(minutes, note=None):
    steps = [step("steady", "Rad Grundlage", minutes, 2, HR["bike_z2"], "Trittfrequenz 85–95")]
    tips = [f"Puls {HR['bike_z2'][0]}–{HR['bike_z2'][1]}, locker treten. Du solltest dich problemlos unterhalten können.",
            f"Indoor (Rolle/Ergometer): {max(30, round(minutes * 0.7 / 5) * 5)} min reichen, da durchgehend getreten wird."]
    if note:
        tips.insert(0, note)
    return {"sport": "bike", "kind": "bike_z2", "title": f"Rad locker {minutes} min", "key": False,
            "duration_min": minutes, "distance_km": None, "purpose": PURPOSE["bike_z2"], "steps": steps, "tips": tips}


STRENGTH = {
    "A": ("Kraft A – Grundkraft & Stabilität", [
        ("Goblet Squat", "3 × 10", "RIR 3: drei Wiederholungen im Tank lassen"),
        ("Rumänisches Kreuzheben (Kurzhantel)", "3 × 10", "Rücken gerade, Dehnung in der Oberschenkelrückseite"),
        ("Bulgarian Split Squat", "3 × 8 / Seite", "Knie stabil über dem Fuß"),
        ("Hip Thrust", "3 × 10", "oben 1 s halten"),
        ("Wadenheben einbeinig (Stufe)", "3 × 15 / Seite", "3 s langsam absenken"),
        ("Copenhagen Plank (kurz)", "2 × 20 s / Seite", "Adduktoren, Leistenschutz"),
        ("Pallof Press", "2 × 10 / Seite", "Rumpfstabilität"),
        ("Plank", "3 × 40 s", ""),
    ]),
    "B": ("Kraft B – Maximalkraft", [
        ("Kniebeuge (Langhantel)", "4 × 5", "schwer, RIR 2, explosiv hoch"),
        ("Rumänisches Kreuzheben (Langhantel)", "4 × 6", "RIR 2"),
        ("Step-ups mit Kurzhanteln", "3 × 6 / Seite", "Kasten auf Kniehöhe"),
        ("Wadenheben stehend (schwer)", "4 × 8", ""),
        ("Pogo Jumps", "3 × 20", "kurzer Bodenkontakt, steife Sprunggelenke"),
        ("Box Jumps", "3 × 5", "leise landen, runtersteigen"),
        ("Seitstütz", "3 × 30 s / Seite", ""),
        ("Dead Bug", "3 × 10", ""),
    ]),
    "C": ("Kraft C – Kraft & Reaktivkraft", [
        ("Kniebeuge (Langhantel)", "3 × 4", "schwer, maximal explosiv hoch"),
        ("Trap-Bar-Kreuzheben", "3 × 4", "RIR 2"),
        ("Bounding (Sprunglauf)", "4 × 20 m", "weite, federnde Sprünge"),
        ("Einbeinige Hops", "3 × 8 / Seite", "auf der Stelle, reaktiv"),
        ("Wadenheben einbeinig (Zusatzgewicht)", "3 × 8 / Seite", ""),
        ("Nordic Hamstring Curl", "3 × 5", "langsam absenken"),
        ("Pallof Press", "2 × 10 / Seite", ""),
        ("Plank mit Schulter-Tippen", "3 × 30 s", ""),
    ]),
}


def strength(phase, light=False, no_jumps=False):
    title, ex = STRENGTH[phase]
    exercises = []
    for name, dose, note in ex:
        if no_jumps and any(k in name for k in ("Jump", "Bounding", "Hops")):
            continue
        if light:
            dose = re.sub(r"^\d+", "2", dose)
            note = (note + "; " if note else "") + "ca. 70 % Gewicht"
        exercises.append({"name": name, "dose": dose, "note": note})
    return {"sport": "strength", "kind": "strength", "title": title + (" (leicht)" if light else ""), "key": False,
            "duration_min": 40 if light else 55, "distance_km": None, "purpose": PURPOSE["strength"],
            "steps": [], "exercises": exercises,
            "tips": ["10 min Aufwärmen: Rudern/Rad + Mobility (Hüfte, Sprunggelenk).",
                     "Nie bis zum Muskelversagen: Am Mittwoch stehen Intervalle an.",
                     "Wenn es leicht wird: nächste Woche +2,5–5 kg."]}


def rest(note=None):
    return {"sport": "rest", "kind": "rest", "title": "Ruhetag", "key": False, "duration_min": 0, "distance_km": None,
            "purpose": PURPOSE["rest"], "steps": [], "tips": [note] if note else
            ["Optional: 10–15 min Mobility (Hüftbeuger, Waden, Oberschenkelrückseite)."]}


# ---------- Wochenstruktur ----------
# Mo Kraft · Di Ruhe · Mi VO2max · Do Rad · Fr Schwelle/locker · Sa Ruhe · So Langer Lauf

PHASES = [
    {"id": "base", "name": "Basis & Einführung", "weeks": [1, 2, 3, 4], "color": "#4cc38a",
     "goal": "Erholung stabilisieren, lockere Läufe wirklich locker, VO2max-Intervalle in verschiedenen Formen einführen."},
    {"id": "build", "name": "VO2max-Aufbau", "weeks": [5, 6, 7, 8], "color": "#f5a524",
     "goal": "Mehr Zeit nahe VO2max (längere Intervalle, 30/15, Berg), Maximalkraft, Grundlage auf 90 min."},
    {"id": "peak", "name": "Spitze & Test", "weeks": [9, 10, 11, 12], "color": "#f2555a",
     "goal": "Höchste Intervallqualität, Reaktivkraft, dann Taper und 5-km-Abschlusstest."},
]

WEEKS = {
    # Woche: (Fokus, Mo, Mi = VO2max, Do, Fr = Qualität 2, So)
    1: ("Reset & Einstieg", strength("A"),
        vo2(5, 3, 2.5, extra_tip="Einstiegswoche: eher am langsamen Ende der Pace-Vorgabe."),
        bike(60), easy(40, 6), long_run(60)),
    2: ("Intervalle verlängern", strength("A"), pyramid([2, 3, 4, 3, 2]), bike(70), threshold(3, 8, 2), long_run(70)),
    3: ("Volumen hoch", strength("A"), distance_reps(5, 800, 2.5), bike(75), threshold(2, 12, 3), long_run(80)),
    4: ("Entlastung + 5-km-Test", strength("A", light=True), short_intervals(1, reps=12, on=30, off=30),
        bike(45), easy(35, 4), test5k()),
    5: ("Längere Intervalle", strength("B"), vo2(4, 5, 3), bike(75), threshold(1, 20, 0), long_run(80)),
    6: ("30/15 einführen", strength("B"), short_intervals(3), bike(90), cruise(5), long_run(90)),
    7: ("Bergauf zur VO2max", strength("B"), hill_reps(6, 3), bike(75), progression(45), long_run(90, finish=15)),
    8: ("Entlastung", strength("B", light=True), fartlek(8), bike(60), easy(35, 4), long_run(70)),
    9: ("Spitzenblock startet", strength("C"), short_intervals(3, pace=PACES["short_fast"]), bike(90),
        threshold(2, 15, 3), long_run(95)),
    10: ("Höchste Belastung", strength("C"), pyramid([6, 5, 4, 3, 2], rest_ratio=0.6, name="Leiter"), bike(90),
         hill_sprints(10), long_run(100)),
    11: ("Schärfen", strength("C"), distance_reps(4, 1200, 3, pace=PACES["vo2_fast"]), bike(75),
         threshold(1, 25, 0), long_run(90, finish=20)),
    12: ("Taper + Abschlusstest", strength("C", light=True, no_jumps=True), vo2(6, 2, 2), bike(45), easy(30, 4),
         test5k()),
}

HOLIDAYS = {(12, 24), (12, 25), (12, 26), (12, 31), (1, 1)}


def intro_days():
    """Lockere Einstiegstage vor Woche 1 (z. B. Fr–So)."""
    if PLAN_INTRO_DAYS <= 0:
        return []
    d0 = PLAN_START - timedelta(days=PLAN_INTRO_DAYS)
    pattern = [rest("Erholt in den Plan starten."), bike(50, "Optional. Nur wenn du dich frisch fühlst."), easy(40)]
    pattern = pattern[-PLAN_INTRO_DAYS:] if PLAN_INTRO_DAYS <= 3 else [rest()] * (PLAN_INTRO_DAYS - 3) + pattern
    return [(d0 + timedelta(days=i), s) for i, s in enumerate(pattern)]


def build():
    sessions = []

    def add(d: date, w: int, s: dict):
        s = dict(s)
        s.update({"id": f"{d.isoformat()}-{s['sport']}", "date": d.isoformat(), "week": w,
                  "weekday": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"][d.weekday()], "adjusted": None})
        sessions.append(s)

    weeks = []
    intro = intro_days()
    if intro:
        for d, s in intro:
            add(d, 0, s)
        weeks.append({"week": 0, "start": intro[0][0].isoformat(), "phase": "intro",
                      "focus": "Erholung zuerst", "deload": False})
    for w, (focus, mo, mi, do, fr, so) in WEEKS.items():
        start = PLAN_START + timedelta(weeks=w - 1)
        phase = next(p["id"] for p in PHASES if w in p["weeks"])
        days = [start + timedelta(days=i) for i in range(7)]
        if any((d.month, d.day) in HOLIDAYS for d in days):
            focus += " (Feiertage: Tage flexibel schieben)"
        weeks.append({"week": w, "start": start.isoformat(), "phase": phase, "focus": focus,
                      "deload": w in (4, 8, 12)})
        plan_days = {0: mo, 1: rest(), 2: mi, 3: do, 4: fr,
                     5: rest("Ruhetag vor dem langen Lauf. Spaziergang oder Mobility ist okay."), 6: so}
        for offset, s in plan_days.items():
            add(days[offset], w, s)

    for wk in weeks:
        ss = [s for s in sessions if s["week"] == wk["week"]]
        wk["run_km"] = round(sum(s["distance_km"] or 0 for s in ss if s["sport"] == "run"), 1)
        wk["run_min"] = sum(s["duration_min"] for s in ss if s["sport"] == "run")
        wk["total_min"] = sum(s["duration_min"] for s in ss)

    phases = ([{"id": "intro", "name": "Einstieg", "weeks": [0], "color": "#7c8aa5",
                "goal": "Ein paar ruhige Tage, damit du erholt in den Plan startest."}] if intro else []) + PHASES
    return {
        "version": 1,
        "created": date.today().isoformat(),
        "goal": f"VO2max {ATHLETE['vo2max_start']} → {ATHLETE['vo2max_goal']}",
        "start": PLAN_START.isoformat(),
        "athlete": ATHLETE,
        "zones": {"run": RUN_ZONES, "bike": BIKE_ZONES},
        "paces": PACES,
        "phases": phases,
        "weeks": weeks,
        "sessions": sessions,
        "changelog": [{"date": date.today().isoformat(), "text": "Plan erstellt."}],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="bestehenden Plan überschreiben (löscht alle Anpassungen!)")
    args = ap.parse_args()
    if PLAN_FILE.exists() and not args.force:
        print(f"{PLAN_FILE} existiert schon. Mit --force überschreiben (löscht alle Anpassungen).")
        return
    PLAN_FILE.parent.mkdir(parents=True, exist_ok=True)
    plan = build()
    PLAN_FILE.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    for w in plan["weeks"]:
        print(f"W{w['week']:>2} {w['start']} {w['phase']:<6} {w['run_km']:5.1f} km Lauf, {w['total_min']:4d} min  {w['focus']}")


if __name__ == "__main__":
    main()
