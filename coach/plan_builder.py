"""Erzeugt den Trainingsplan als plan/plan.json aus athlete.json (Profil + Antworten aus dem Fragebogen).

Aufruf:  python -m coach.plan_builder [--force]
Ohne --force wird ein bestehender Plan nicht überschrieben (der Coach passt ihn laufend an).

Ziele (athlete.json → training.goal): vo2max, 5k, 10k, half. Jedes Ziel hat eine 12-Wochen-Vorlage in TEMPLATES.
Kürzere Pläne (bis zum Wettkampf) lassen vorne Wochen weg, längere bekommen vorne Grundlagenwochen dazu.
Die Bausteine (vo2, pyramid, threshold, …) stehen weiter oben.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, timedelta

from .config import (ATHLETE, BIKE_ZONES, EASY_CAP_RUN, GOALS, HR_TARGETS as HR, PACES, PLAN_FILE, PLAN_INTRO_DAYS,
                     PLAN_START, RUN_ZONES, THR_HI, TRAINING, VO2_HR)

# ---------- Umfang nach Niveau ----------
LEVEL = int(TRAINING.get("level", 2))
_F = {0: 0.7, 1: 0.85, 2: 1.0, 3: 1.15}.get(LEVEL, 1.0)


def m(minutes: float) -> int:
    """Dauer an den aktuellen Umfang anpassen (Niveau 2 = unverändert)."""
    return minutes if _F == 1 else max(20, int(round(minutes * _F / 5) * 5))


def R(n: int, lo: int = 3) -> int:
    """Wiederholungen: bei wenig Umfang (Niveau 0) eine weniger."""
    return max(lo, n - 1) if LEVEL == 0 else n


# ---------- Bausteine ----------


def step(kind, label, minutes, zone, hr=None, pace=None, note=None, dist_m=None):
    s = {"type": kind, "label": label, "min": round(minutes, 2), "zone": zone, "hr": hr, "pace": pace, "note": note}
    if dist_m:
        s["dist_m"] = dist_m  # Distanz-Schritt (auf der Uhr: Dauer = Distanz)
    return s


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
    "race_pace": "Renntempo-Training: Du lernst, dein Wettkampftempo zu spüren und ökonomisch zu halten. "
    "Genau dieses Tempo soll sich am Renntag vertraut anfühlen.",
    "race": "Dein Wettkampf. Alles der letzten Wochen zielt auf diesen Tag: gleichmäßig starten, Tempo halten, hinten raus zulegen.",
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


def run_session(kind, title, steps, tips=None, key=False, purpose=None):
    mins, km = totals(steps)
    return {"sport": "run", "kind": kind, "title": title, "key": key, "duration_min": mins, "distance_km": km,
            "purpose": purpose or PURPOSE[kind if kind in PURPOSE else "easy"], "steps": steps, "tips": tips or []}


def work(label, minutes, pace=None, zone=5, hr=None, note=None, dist_m=None):
    return step("work", label, minutes, zone, hr or HR["vo2"], pace or PACES["vo2"], note, dist_m)


def vo2(reps, minutes, rest, pace=None, extra_tip=None):
    """Klassisch: N × M min."""
    tips = ([extra_tip] if extra_tip else []) + VO2_TIPS
    w = work(f"{fmt_min(minutes)} min schnell", minutes, pace)
    return run_session("vo2", f"VO2max: {reps} × {fmt_min(minutes)} min",
                       [warmup(15), rep(reps, w, jog(rest)), cooldown(10)], tips, key=True)


def pyramid(mins: list, rest_ratio=0.75, pace=None, name="Pyramide"):
    """Belastungen mit wechselnder Länge, Pause = rest_ratio × Belastung (mind. 1:30)."""
    steps = [warmup(15)]
    for i, m_ in enumerate(mins):
        steps.append(work(f"{fmt_min(m_)} min schnell", m_, pace))
        if i < len(mins) - 1:
            steps.append(jog(max(1.5, round(m_ * rest_ratio * 2) / 2)))
    steps.append(cooldown(10))
    tips = [f"{name}: Kürzere Abschnitte etwas schneller als die langen, aber alles im VO2max-Bereich.",
            "Auf der Uhr Schritt für Schritt anlegen (keine Wiederholung möglich)."] + VO2_TIPS[1:]
    return run_session("vo2", f"{name} {'-'.join(fmt_min(x) for x in mins)} min", steps, tips, key=True)


def distance_reps(reps, meters, rest, pace=None):
    """N × X m – Distanz statt Zeit (Bahn oder flache Strecke)."""
    pace = pace or PACES["vo2"]
    minutes = meters / 1000 * pace_sec(pace) / 60
    w = work(f"{meters} m schnell", minutes, pace, dist_m=meters)
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


def fartlek(reps, on=1, off=1, tip="Entlastungswoche: zügig, aber nicht am Limit. Spaß an der Geschwindigkeit."):
    w = step("work", f"{fmt_min(on)} min zügig", on, 4, None, PACES["vo2"], "nach Gefühl, ~5-km-Tempo")
    r = step("recovery", f"{fmt_min(off)} min locker", off, 2, HR["jog"], "locker")
    return run_session("vo2", f"Fahrtspiel: {reps} × {fmt_min(on)} min", [warmup(15, 0), rep(reps, w, r), cooldown(10)],
                       [tip], key=False)


def threshold(blocks, minutes, rest, pace=None):
    pace = pace or PACES["threshold"]
    w = step("work", f"{fmt_min(minutes)} min Schwelle", minutes, 4, HR["thr"], pace)
    steps = [warmup(15, 2), rep(blocks, w, jog(rest)) if blocks > 1 else w, cooldown(10)]
    tips = ["Schwelle heißt »angenehm hart«: Du könntest noch 2–3 Wörter sprechen.",
            f"Puls über {THR_HI} bedeutet zu schnell. Dann wird es eine VO2max-Einheit, und dafür gibt es einen eigenen Tag.",
            "Gleichmäßig laufen, kein Endspurt."]
    title = f"Schwelle: {blocks} × {fmt_min(minutes)} min" if blocks > 1 else f"Tempodauerlauf: {fmt_min(minutes)} min Schwelle"
    return run_session("threshold" if blocks > 1 else "tempo", title, steps, tips, key=True)


def cruise(reps, meters=1000, rest=1):
    minutes = meters / 1000 * pace_sec(PACES["threshold"]) / 60
    w = step("work", f"{meters} m Schwelle", minutes, 4, HR["thr"], PACES["threshold"], dist_m=meters)
    return run_session("threshold", f"Cruise-Intervalle: {reps} × {meters} m",
                       [warmup(15, 2), rep(reps, w, jog(rest)), cooldown(10)],
                       ["Kurze Pausen, Schwellentempo: Am Ende soll es sich wie ein langer Tempolauf anfühlen.",
                        f"Puls in den Abschnitten {HR['thr'][0]}–{HR['thr'][1]} bpm."], key=True)


def race_pace(reps, meters, rest, which="ten_k"):
    """N × X m im geplanten Renntempo (10 km oder Halbmarathon)."""
    pace = PACES[which]
    minutes = meters / 1000 * pace_sec(pace) / 60
    name = "10-km-Tempo" if which == "ten_k" else "HM-Tempo"
    hr = HR["thr"] if which == "ten_k" else [HR["tempo"][0], HR["thr"][0] + 2]
    w = step("work", f"{meters / 1000:g} km {name}", minutes, 4 if which == "ten_k" else 3, hr, pace, dist_m=meters)
    steps = [warmup(15, 2), rep(reps, w, jog(rest)) if reps > 1 else w, cooldown(10)]
    title = f"Renntempo: {reps} × {meters / 1000:g} km" if reps > 1 else f"Renntempo: {meters / 1000:g} km"
    return run_session("threshold" if which == "ten_k" else "tempo", title, steps,
                       [f"Ziel-Pace {pace} /km. Genau so, nicht schneller: Es geht um Gefühl und Gleichmäßigkeit.",
                        "Trink- und Gel-Strategie für den Wettkampf hier ausprobieren." if which == "half" else
                        "Locker in den Schultern bleiben, Atmung gleichmäßig."],
                       key=True, purpose=PURPOSE["race_pace"])


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


def long_run(minutes, finish=None, finish_pace=None):
    if finish and finish_pace == "half":
        steps = [step("steady", "Grundlage", minutes - finish, 2, HR["easy"], PACES["long"]),
                 step("work", "Halbmarathon-Tempo", finish, 3, [HR["tempo"][0], HR["thr"][0] + 2], PACES["half"])]
        title = f"Langer Lauf {minutes} min (letzte {finish} min HM-Tempo)"
    elif finish:
        steps = [step("steady", "Grundlage", minutes - finish, 2, HR["easy"], PACES["long"]),
                 step("work", "Endbeschleunigung", finish, 3, HR["tempo"], PACES["tempo"])]
        title = f"Langer Lauf {minutes} min (letzte {finish} min zügig)"
    else:
        steps = [step("steady", "Grundlage", minutes, 2, HR["easy"], PACES["long"])]
        title = f"Langer Lauf {minutes} min"
    return run_session("long", title, steps,
                       [f"Puls {HR['easy'][0]}–{HR['easy'][1]} zählt, nicht die Pace. Bergauf langsamer werden.",
                        "Ab 75 min etwas trinken, bei 90+ min ein Gel oder Riegel mitnehmen."])


def test5k(race=False):
    steps = [warmup(15, 3), step("work", "5 km Wettkampf" if race else "5 km Test", pace_sec(PACES["five_k"]) * 5 / 60, 5,
                                 None, "so schnell wie gleichmäßig möglich", f"Referenz: {PACES['five_k']} /km", 5000),
             cooldown(10)]
    if race:
        return run_session("test", "5-km-Wettkampf", steps,
                           ["Ersten Kilometer kontrolliert, dann steigern. Letzter Kilometer alles raus.",
                            "Gut einlaufen, die Steigerungen erst kurz vor dem Start.",
                            "Uhr: als normalen Lauf starten, beim Start und im Ziel eine Runde drücken."],
                           key=True, purpose=PURPOSE["race"])
    return run_session("test", "5-km-Test", steps,
                       ["Flache Strecke, ausgeruht, nicht nüchtern.",
                        "Ersten Kilometer kontrolliert, dann steigern. Letzter Kilometer alles raus.",
                        "Uhr: als normalen Lauf starten, beim Teststart und am Ende eine Runde drücken."], key=True)


def race(km):
    pace = PACES["ten_k"] if km < 15 else PACES["half"]
    name = "10-km-Wettkampf" if km < 15 else "Halbmarathon"
    steps = [warmup(15, 3) if km < 15 else warmup(10, 2),
             step("work", name, pace_sec(pace) * km / 60, 4, None, pace, "gleichmäßig, ab der Hälfte darf es härter werden",
                  int(km * 1000)),
             cooldown(10)]
    tips = [f"Geplante Pace {pace} /km. Die ersten 2 km bewusst nicht schneller.",
            "Am Vortag nur kurz locker laufen, viel trinken, gewohnt essen. Nichts Neues am Renntag."]
    if km >= 15:
        tips.append("Ab km 5 alle 30–40 min ein Gel, an jeder Verpflegung ein paar Schlucke.")
    return run_session("race", name, steps, tips, key=True)


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
                     "Nie bis zum Muskelversagen: In den nächsten Tagen stehen Intervalle an.",
                     "Wenn es leicht wird: nächste Woche +2,5–5 kg."]}


def rest(note=None):
    return {"sport": "rest", "kind": "rest", "title": "Ruhetag", "key": False, "duration_min": 0, "distance_km": None,
            "purpose": PURPOSE["rest"], "steps": [], "tips": [note] if note else
            ["Optional: 10–15 min Mobility (Hüftbeuger, Waden, Oberschenkelrückseite)."]}


# ---------- Vorlagen je Ziel (12 Wochen) ----------
# Woche: (Fokus, Q1 = Intervalle, Q2 = Schwelle/Tempo, L = langer Lauf, Rad-Minuten, Entlastung)


def template(goal: str) -> list[tuple]:
    if goal == "5k":
        return [
            ("Einstieg", vo2(R(5), 3, 2.5, extra_tip="Einstiegswoche: eher am langsamen Ende der Pace-Vorgabe."),
             easy(m(40), 6), long_run(m(60)), 60, False),
            ("Intervalle verlängern", pyramid([2, 3, 4, 3, 2]), threshold(R(3), 8, 2), long_run(m(70)), 70, False),
            ("Volumen hoch", distance_reps(R(5), 800, 2.5), threshold(2, 12, 3), long_run(m(75)), 75, False),
            ("Entlastung + 5-km-Test", short_intervals(1, reps=12, on=30, off=30), easy(m(35), 4), test5k(), 45, True),
            ("Längere Intervalle", distance_reps(R(5), 1000, 3), cruise(R(5)), long_run(m(80)), 75, False),
            ("30/15 einführen", short_intervals(R(3, 1)), threshold(2, 12, 3), long_run(m(80)), 90, False),
            ("Bergauf", hill_reps(R(6), 3), progression(45), long_run(m(85)), 75, False),
            ("Entlastung", fartlek(8), easy(m(35), 4), long_run(m(65)), 60, True),
            ("Renntempo", distance_reps(R(6), 1000, 2.5), threshold(2, 15, 3), long_run(m(85)), 90, False),
            ("Höchste Belastung", short_intervals(R(3, 1), pace=PACES["short_fast"]), cruise(R(6)), long_run(m(90)), 90, False),
            ("Schärfen", distance_reps(R(4), 1200, 3, pace=PACES["vo2_fast"]), threshold(1, 20, 0), long_run(m(75)), 75, False),
            ("Taper + 5-km-Wettkampf", vo2(5, 2, 2), easy(m(25), 4), test5k(race=True), 45, True),
        ]
    if goal == "10k":
        return [
            ("Einstieg", vo2(R(5), 3, 2.5, extra_tip="Einstiegswoche: eher am langsamen Ende der Pace-Vorgabe."),
             easy(m(40), 6), long_run(m(65)), 60, False),
            ("Intervalle verlängern", pyramid([2, 3, 4, 3, 2]), threshold(R(3), 8, 2), long_run(m(70)), 70, False),
            ("Volumen hoch", distance_reps(R(5), 1000, 2.5), threshold(2, 12, 3), long_run(m(80)), 75, False),
            ("Entlastung + 5-km-Test", fartlek(8), easy(m(35), 4), test5k(), 45, True),
            ("Längere Intervalle", vo2(R(4), 5, 3), cruise(R(6)), long_run(m(85)), 75, False),
            ("Bergauf", hill_reps(R(6), 3), threshold(R(3), 10, 2), long_run(m(90)), 90, False),
            ("Schwelle verlängern", distance_reps(R(5), 1200, 3), threshold(1, 25, 0), long_run(m(95), finish=15), 75, False),
            ("Entlastung", short_intervals(1, reps=12, on=30, off=30), easy(m(35), 4), long_run(m(70)), 60, True),
            ("Spitzenblock", vo2(R(5), 4, 2.5), cruise(R(8)), long_run(m(95)), 90, False),
            ("Renntempo", short_intervals(R(3, 1)), race_pace(R(3), 2000, 2), long_run(m(100)), 90, False),
            ("Schärfen", distance_reps(R(4), 1200, 3, pace=PACES["vo2_fast"]), race_pace(2, 3000, 3),
             long_run(m(85), finish=20), 75, False),
            ("Taper + 10-km-Wettkampf", vo2(5, 2, 2), easy(m(25), 4), race(10), 45, True),
        ]
    if goal == "half":
        return [
            ("Einstieg", vo2(R(5), 3, 2.5, extra_tip="Einstiegswoche: eher am langsamen Ende der Pace-Vorgabe."),
             easy(m(40), 6), long_run(m(70)), 60, False),
            ("Grundlage", pyramid([2, 3, 4, 3, 2]), threshold(R(3), 8, 2), long_run(m(80)), 70, False),
            ("Volumen hoch", hill_reps(R(6), 3), threshold(2, 12, 3), long_run(m(90)), 75, False),
            ("Entlastung + 5-km-Test", fartlek(8), easy(m(35), 4), test5k(), 45, True),
            ("Schwelle", distance_reps(R(5), 1000, 2.5), threshold(2, 15, 3), long_run(m(95)), 75, False),
            ("Tempo halten", cruise(R(8)), progression(50), long_run(m(100), finish=20, finish_pace="half"), 90, False),
            ("Längere Blöcke", vo2(R(4), 5, 3), threshold(1, 30, 0), long_run(m(110)), 75, False),
            ("Entlastung", short_intervals(1, reps=12, on=30, off=30), easy(m(35), 4), long_run(m(80)), 60, True),
            ("HM-Tempo", cruise(R(8)), race_pace(R(3), 3000, 3, "half"), long_run(m(115), finish=20, finish_pace="half"),
             90, False),
            ("Höchster Umfang", distance_reps(R(5), 1200, 3), progression(55), long_run(m(120)), 90, False),
            ("Schärfen", threshold(2, 15, 3), race_pace(2, 5000, 3, "half"), long_run(m(100), finish=25, finish_pace="half"),
             75, False),
            ("Taper + Halbmarathon", threshold(2, 8, 3), easy(m(30), 4), race(21.1), 45, True),
        ]
    # vo2max (ursprünglicher Plan)
    return [
        ("Reset & Einstieg", vo2(R(5), 3, 2.5, extra_tip="Einstiegswoche: eher am langsamen Ende der Pace-Vorgabe."),
         easy(m(40), 6), long_run(m(60)), 60, False),
        ("Intervalle verlängern", pyramid([2, 3, 4, 3, 2]), threshold(R(3), 8, 2), long_run(m(70)), 70, False),
        ("Volumen hoch", distance_reps(R(5), 800, 2.5), threshold(2, 12, 3), long_run(m(80)), 75, False),
        ("Entlastung + 5-km-Test", short_intervals(1, reps=12, on=30, off=30), easy(m(35), 4), test5k(), 45, True),
        ("Längere Intervalle", vo2(R(4), 5, 3), threshold(1, 20, 0), long_run(m(80)), 75, False),
        ("30/15 einführen", short_intervals(R(3, 1)), cruise(R(5)), long_run(m(90)), 90, False),
        ("Bergauf zur VO2max", hill_reps(R(6), 3), progression(45), long_run(m(90), finish=15), 75, False),
        ("Entlastung", fartlek(8), easy(m(35), 4), long_run(m(70)), 60, True),
        ("Spitzenblock startet", short_intervals(R(3, 1), pace=PACES["short_fast"]), threshold(2, 15, 3),
         long_run(m(95)), 90, False),
        ("Höchste Belastung", pyramid([6, 5, 4, 3, 2], rest_ratio=0.6, name="Leiter"), hill_sprints(R(10)),
         long_run(m(100)), 90, False),
        ("Schärfen", distance_reps(R(4), 1200, 3, pace=PACES["vo2_fast"]), threshold(1, 25, 0),
         long_run(m(90), finish=20), 75, False),
        ("Taper + Abschlusstest", vo2(6, 2, 2), easy(m(30), 4), test5k(), 45, True),
    ]


MIN_WEEKS, MAX_WEEKS = 6, 16
DROP_ORDER = [5, 6, 3, 7, 4, 9]  # Vorlagenwochen, die bei kürzeren Plänen nacheinander wegfallen


def base_week(i: int) -> tuple:
    """Zusätzliche Grundlagenwoche vor der Vorlage (wenn der Wettkampf mehr als 12 Wochen entfernt ist)."""
    return ("Grundlage", fartlek(6, tip="Grundlagenwoche: zügig nach Gefühl, nicht am Limit."), easy(m(40), 6),
            long_run(m(50 + 5 * i)), 60, False)


PHASE_INFO = {
    "vo2max": [("Basis & Einführung", "Erholung stabilisieren, lockere Läufe wirklich locker, VO2max-Intervalle in verschiedenen Formen einführen."),
               ("VO2max-Aufbau", "Mehr Zeit nahe VO2max (längere Intervalle, 30/15, Berg), Maximalkraft, Grundlage auf 90 min."),
               ("Spitze & Test", "Höchste Intervallqualität, Reaktivkraft, dann Taper und 5-km-Abschlusstest.")],
    "5k": [("Basis", "Grundlage und Schwelle aufbauen, Intervalle in verschiedenen Formen kennenlernen."),
           ("Aufbau", "Längere Intervalle und 30/15 für mehr Tempo, Schwelle für Tempohärte."),
           ("Spitze & Wettkampf", "Renntempo schärfen, dann Taper und 5-km-Wettkampf.")],
    "10k": [("Basis", "Grundlage aufbauen, Intervalle und Schwelle einführen."),
            ("Aufbau", "Längere Schwellenblöcke und VO2max-Intervalle, langer Lauf bis 95 min."),
            ("Spitze & Wettkampf", "10-km-Renntempo trainieren, dann Taper und Wettkampf.")],
    "half": [("Basis", "Grundlage und Umfang aufbauen, Intervalle und Schwelle einführen."),
             ("Aufbau", "Lange Schwellenblöcke, erste Abschnitte im Halbmarathon-Tempo, langer Lauf bis 110 min."),
             ("Spitze & Wettkampf", "Halbmarathon-Tempo über längere Strecken, langer Lauf bis 2 h, dann Taper und Rennen.")],
}
PHASE_COLORS = {"base": "#4cc38a", "build": "#f5a524", "peak": "#f2555a"}

# Wochenrhythmus bei langem Lauf am Sonntag (Mo … So). S Kraft, R Ruhe, E locker, B Rad, Q1/Q2 Qualität, L lang
PATTERNS = {
    3: ["S", "R", "Q1", "B", "Q2", "R", "L"],
    4: ["S", "E", "Q1", "B", "Q2", "R", "L"],
    5: ["S", "E", "Q1", "E2", "Q2", "R", "L"],
}
SLOT_NAMES = {"S": "Kraft", "R": "Ruhe", "E": "Locker", "E2": "Locker", "B": "Rad", "L": "Langer Lauf"}
WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def week_pattern() -> list[str]:
    p = list(PATTERNS.get(int(TRAINING.get("run_days", 3)), PATTERNS[3]))
    p = [("R" if (s == "S" and not TRAINING.get("strength", True)) or (s == "B" and not TRAINING.get("bike", True))
          else s) for s in p]
    if TRAINING.get("long_day") == "Sa":
        p = p[1:] + p[:1]
    return p


def slot_names(goal: str) -> dict:
    q1 = "VO2max" if goal == "vo2max" else "Intervalle"
    q2 = "Schwelle" if goal in ("vo2max", "5k") else "Schwelle/Renntempo"
    return SLOT_NAMES | {"Q1": q1, "Q2": q2}


HOLIDAYS = {(12, 24), (12, 25), (12, 26), (12, 31), (1, 1)}


def intro_days():
    """Lockere Einstiegstage vor Woche 1 (z. B. Fr–So)."""
    if PLAN_INTRO_DAYS <= 0:
        return []
    d0 = PLAN_START - timedelta(days=PLAN_INTRO_DAYS)
    ride = bike(50, "Optional. Nur wenn du dich frisch fühlst.") if TRAINING.get("bike", True) else rest()
    pattern = [rest("Erholt in den Plan starten."), ride, easy(m(40))]
    pattern = pattern[-PLAN_INTRO_DAYS:] if PLAN_INTRO_DAYS <= 3 else [rest()] * (PLAN_INTRO_DAYS - 3) + pattern
    return [(d0 + timedelta(days=i), s) for i, s in enumerate(pattern)]


def goal_text(goal: str) -> str:
    if goal == "vo2max":
        return f"VO2max {ATHLETE['vo2max_start']} → {ATHLETE['vo2max_goal']}"
    name = {"5k": "5 km", "10k": "10 km", "half": "Halbmarathon"}[goal]
    t = TRAINING.get("goal_time")
    rd = TRAINING.get("race_date")
    return name + (f" in {t}" if t else " schneller" if goal == "5k" else "") + \
        (f" am {date.fromisoformat(rd):%d.%m.%Y}" if rd else "")


def build():
    goal = TRAINING.get("goal", "vo2max")
    if goal not in GOALS:
        goal = "vo2max"
    n = int(TRAINING.get("weeks") or 12)
    tpl = template(goal)
    phase_of = ["base"] * 4 + ["build"] * 4 + ["peak"] * 4
    if n < 12:
        # Kürzer bis zum Wettkampf: Wochen aus dem Aufbau streichen, sanften Einstieg und Taper behalten
        drop = set(DROP_ORDER[:12 - n])
        keep = [i for i in range(12) if i + 1 not in drop]
        tpl, phase_of = [tpl[i] for i in keep], [phase_of[i] for i in keep]
    elif n > 12:
        extra = n - 12
        tpl = [base_week(i) for i in range(extra)] + tpl
        phase_of = ["base"] * extra + phase_of

    pattern = week_pattern()
    names = slot_names(goal)
    race_date = date.fromisoformat(TRAINING["race_date"]) if TRAINING.get("race_date") and goal != "vo2max" else None
    sessions = []

    def add(d: date, w: int, s: dict):
        s = dict(s)
        s.update({"id": f"{d.isoformat()}-{s['sport']}", "date": d.isoformat(), "week": w,
                  "weekday": WEEKDAYS[d.weekday()], "adjusted": None})
        sessions.append(s)

    weeks = []
    intro = intro_days()
    if intro:
        for d, s in intro:
            add(d, 0, s)
        weeks.append({"week": 0, "start": intro[0][0].isoformat(), "phase": "intro",
                      "focus": "Erholung zuerst", "deload": False})
    for i, (focus, q1, q2, long_, bike_min, deload) in enumerate(tpl):
        w = i + 1
        last = w == len(tpl)
        start = PLAN_START + timedelta(weeks=w - 1)
        days = [start + timedelta(days=k) for k in range(7)]
        if any((d.month, d.day) in HOLIDAYS for d in days):
            focus += " (Feiertage: Tage flexibel schieben)"
        weeks.append({"week": w, "start": start.isoformat(), "phase": phase_of[i], "focus": focus, "deload": deload})
        sphase = {"base": "A", "build": "B", "peak": "C"}[phase_of[i]]
        e_min = m(30) if deload else m(45 if goal == "half" else 40)
        slot = {"S": strength(sphase, light=deload, no_jumps=last), "Q1": q1, "Q2": q2, "L": long_,
                "B": bike(m(bike_min)), "E": easy(e_min), "E2": easy(m(35) if not deload else m(30), 0 if deload else 4)}
        plan_days = {}
        for k, code in enumerate(pattern):
            if code == "R":
                nxt = pattern[(k + 1) % 7]
                plan_days[k] = rest("Ruhetag vor dem langen Lauf. Spaziergang oder Mobility ist okay." if nxt == "L" else None)
            else:
                plan_days[k] = slot[code]
        if last and race_date and days[0] <= race_date <= days[6]:
            # Wettkampf auf den echten Termin legen, Tag davor nur kurz locker
            rk = race_date.weekday()
            lk = pattern.index("L")
            plan_days[lk], plan_days[rk] = rest("Erholung nach dem Wettkampf." if lk > rk else None), long_
            if rk > 0 and plan_days[rk - 1]["sport"] != "rest":
                plan_days[rk - 1] = easy(20, 3) if plan_days[rk - 1]["sport"] == "run" else rest("Tag vor dem Wettkampf.")
            if rk > 1 and plan_days[rk - 2].get("key"):
                plan_days[rk - 2] = easy(m(30), 4)
        for k, s in plan_days.items():
            add(days[k], w, s)

    for wk in weeks:
        ss = [s for s in sessions if s["week"] == wk["week"]]
        wk["run_km"] = round(sum(s["distance_km"] or 0 for s in ss if s["sport"] == "run"), 1)
        wk["run_min"] = sum(s["duration_min"] for s in ss if s["sport"] == "run")
        wk["total_min"] = sum(s["duration_min"] for s in ss)

    phases = [{"id": pid, "name": name, "weeks": [i + 1 for i, p in enumerate(phase_of) if p == pid],
               "color": PHASE_COLORS[pid], "goal": text}
              for pid, (name, text) in zip(("base", "build", "peak"), PHASE_INFO[goal])]
    phases = [p for p in phases if p["weeks"]]
    if intro:
        phases.insert(0, {"id": "intro", "name": "Einstieg", "weeks": [0], "color": "#7c8aa5",
                          "goal": "Ein paar ruhige Tage, damit du erholt in den Plan startest."})
    rhythm = [{"day": WEEKDAYS[k], "name": names[c], "key": c in ("Q1", "Q2", "L")} for k, c in enumerate(pattern)]
    return {
        "version": 2,
        "created": date.today().isoformat(),
        "goal": goal_text(goal),
        "goal_id": goal,
        "start": PLAN_START.isoformat(),
        "athlete": ATHLETE,
        "training": TRAINING,
        "rhythm": rhythm,
        "zones": {"run": RUN_ZONES, "bike": BIKE_ZONES},
        "paces": PACES,
        "phases": phases,
        "weeks": weeks,
        "sessions": sessions,
        "changelog": [{"date": date.today().isoformat(), "text": "Plan erstellt."}],
    }


def write(plan: dict) -> None:
    PLAN_FILE.parent.mkdir(parents=True, exist_ok=True)
    PLAN_FILE.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="bestehenden Plan überschreiben (löscht alle Anpassungen!)")
    args = ap.parse_args()
    if PLAN_FILE.exists() and not args.force:
        print(f"{PLAN_FILE} existiert schon. Mit --force überschreiben (löscht alle Anpassungen).")
        return
    plan = build()
    write(plan)
    for w in plan["weeks"]:
        print(f"W{w['week']:>2} {w['start']} {w['phase']:<6} {w['run_km']:5.1f} km Lauf, {w['total_min']:4d} min  {w['focus']}")


if __name__ == "__main__":
    main()
