# Garmin Coach

Dein persönlicher Laufcoach für die Garmin-Uhr, mit [Claude](https://claude.com/claude-code) als Trainer.
Beim ersten Start fragt dich die App nach deinem Ziel, also **VO2max steigern, 5 km, 10 km oder Halbmarathon**, und
nach deinem aktuellen Stand. Daraus erstellt sie einen **persönlichen Trainingsplan** (6–16 Wochen, auf Wunsch bis
zum Wettkampftag). Deine Trainings- und Gesundheitsdaten kommen über Garmins **offizielle Personal API**, jede Einheit
wird automatisch ausgewertet. Claude schreibt dir zu jedem Lauf ein Feedback und passt den Plan an, wenn du müde bist,
etwas verpasst hast oder es zwickt. Alles läuft auf deinem eigenen Rechner.

> Inoffizielles Hobbyprojekt, nicht mit Garmin verbunden. Die Garmin Personal API ist nur für die private Nutzung gedacht.

## Was die App kann

- **Plan nach deinen Antworten:** Ziel, Wettkampftermin, Zielzeit, 5-km-Zeit, Wochenumfang, Puls, 3–5 Lauftage,
  langer Lauf am Samstag oder Sonntag, Kraft und Rad optional. Puls- und Pace-Zonen werden daraus berechnet. Werte,
  die du nicht kennst, schätzt die App aus deinen Garmin-Daten.
- **Heute:** Tagesform aus HRV, Ruhepuls, Schlaf und Body Battery, dazu das heutige Workout mit Puls- und Pace-Zielen
  und einer Empfehlung, wenn du lieber tauschen solltest.
- **Trainingsplan:** Basis, Aufbau und Spitze mit Entlastungswochen, abwechslungsreiche Intervalle (Pyramide, 30/15,
  Berg, Fahrtspiel …), Renntempo-Einheiten und Taper vor dem Wettkampf.
- **Automatische Analyse:** Pace und Puls je Wiederholung, Zeit in den Zonen und eine Bewertung, ob der geplante
  Reiz gesetzt wurde.
- **Coach-Feedback von Claude** zu jeder Einheit, Wochen-Rückblick und Planänderungen nach festen Regeln.
- **Dein Feedback:** Gefühl, Beine, Schmerzen und Notiz nach jeder Einheit. Der Coach geht darauf ein.
- **Praktisches:** Workouts als Datei für die Uhr (oder Spickzettel zum Eintippen), Einheiten verschieben mit Regelprüfung,
  Belastungsampel gegen zu schnelles Steigern, Wettkampf-Prognose (5 km bis Halbmarathon) und Wetter-Hinweise.
- **Fortschritt:** VO2max-Verlauf, Intensitätsverteilung, HRV, Ruhepuls und Schlaf.

---

## Installation und Einrichtung

### Voraussetzungen

- Python **3.12+**
- Eine Garmin-Uhr und ein Garmin-Connect-Konto
- Ein **persönlicher API-Schlüssel**: Garmin Connect (Web) → Einstellungen → Persönlicher API-Schlüssel
  ([direkt](https://connect.garmin.com/app/settings/personalApiToken)). Er wird nur einmal angezeigt, also gleich
  sichern.
- Für das Coach-Feedback: [Claude Code](https://claude.com/claude-code) oder die Claude-Desktop-App

> **Hinweis zu den Befehlen:** `python` steht unten immer für das Python der virtuellen Umgebung, also
> `.venv\Scripts\python.exe` unter Windows und `.venv/bin/python` unter macOS/Linux.

### 1. Projekt herunterladen

```bash
git clone https://github.com/Aminjo1204/Garmin-Coach.git
cd Garmin-Coach
```

### 2. Python-Umgebung einrichten

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

macOS / Linux:

```bash
.venv/bin/python -m pip install -r requirements.txt
```

### 3. API-Schlüssel ablegen

Leg eine Textdatei an, die nur den Schlüssel enthält:

| System | Pfad |
|---|---|
| Windows | `%USERPROFILE%\.config\garmin\connect-personal-api-key` |
| macOS / Linux | `~/.config/garmin/connect-personal-api-key` |

Alternativ geht die Umgebungsvariable `GARMIN_PERSONAL_API_KEY`. Den Schlüssel nie ins Repo legen.

### 4. App starten

- **Windows:** `Pace Coach starten.bat` doppelklicken
- **macOS / Linux:** `./start.sh` ausführen

Die App öffnet sich unter http://127.0.0.1:5057 und holt beim Start deine Garmin-Daten (danach automatisch, wenn der
letzte Abruf länger als 30 Minuten her ist).

### 5. Fragebogen ausfüllen

Beim ersten Start erscheint der Fragebogen: Ziel, ein paar Angaben zu dir, deine 5-km-Zeit, Puls und deine
Trainingswoche. Vieles ist aus deinen Garmin-Daten schon vorausgefüllt. Danach steht dein Plan.

Später kannst du jederzeit auf der Seite **Plan → Neuen Plan erstellen** ein neues Ziel wählen. Der alte Plan wird
vorher als `plan/plan-<Datum>.json` gesichert.

Deine Antworten landen in `athlete.json`. Die Datei bleibt lokal und kommt nicht ins Repo. Ein Beispiel mit allen
Feldern steht in [`athlete.example.json`](athlete.example.json). Optional lassen sich dort auch Zonen
(`"zones_run": [[0,139],[140,155],…]`) und Paces (`"paces": {"vo2": "4:55–5:05", …}`) direkt vorgeben.

### 6. Claude als Coach einrichten

[`CLAUDE.md`](CLAUDE.md) beschreibt die Coach-Rolle und den **Coach-Check**: neue Daten holen, zu jeder Einheit ein
Feedback schreiben, den Plan bei Bedarf anpassen und montags eine Wochen-Nachricht schreiben.

- **Von Hand:** Claude Code im Projektordner öffnen und „Coach-Check“ schreiben.
- **Automatisch:** in der Claude-Desktop-App eine geplante Aufgabe anlegen, z. B. morgens und abends. Die Vorlage
  steht in [`docs/coach-check-prompt.md`](docs/coach-check-prompt.md).

### Ausprobieren ohne eigene Daten zu ändern

```bash
python app.py --home testhome --port 5059
```

Profil, Plan und Eingaben landen dann in `testhome/` statt im Projektordner.

---

## Anpassen

- **Pläne:** `coach/plan_builder.py`. Die 12-Wochen-Vorlagen je Ziel stehen in `template()`, der Wochenrhythmus in
  `PATTERNS`. Die Bausteine darüber sind z. B. `vo2(4, 4, 3)`, `pyramid([2, 3, 4, 3, 2])`,
  `distance_reps(5, 800, 2.5)`, `threshold(2, 12, 3)`, `race_pace(3, 2000, 2)`, `long_run(90, finish=15)`,
  `bike(60)` oder `strength("A")`.
- **Fragebogen:** Prüfung und Schätzungen in `coach/setup.py`, Oberfläche in `web/app.js` (`renderSetup`).
- **Analyse-Regeln:** `coach/analysis.py`
- **Tests:** `python -m unittest` im Projektordner. Sie laufen in einem leeren Wegwerf-Ordner, nie auf deinen Daten.
- **Oberfläche:** `web/` (reines HTML, CSS und JS, kein Build-Schritt)

## Grenzen

- Die Personal API kann **nur lesen**. Workouts kommen nicht automatisch auf die Uhr. Zwei Wege: im Detailfenster
  der Einheit die **Workout-Datei (.fit)** laden und per USB in den Ordner `GARMIN/NewFiles` der Uhr kopieren, oder das
  Workout mit dem Spickzettel in Garmin Connect eintippen. Mit Workout erkennt die Analyse jede Wiederholung.
- Der VO2max je Lauf stammt aus einem nicht dokumentierten Feld der FIT-Datei. Er stimmt mit Garmins Anzeige überein,
  kann sich aber mit Firmware-Updates ändern.
- Zonen und Paces sind Schätzungen. Nach jedem 5-km-Test `five_k` aktualisieren.
- Die Pläne sind allgemeine Vorlagen und ersetzen keine ärztliche Abklärung bei Beschwerden.

## Aufbau

```
app.py                  Flask-Server (127.0.0.1:5057), Optionen --home und --port
garmin_sync.py          Daten-Sync per Kommandozeile
coach/config.py         Profil, Zonen, Paces, Trainings-Einstellungen (aus athlete.json)
coach/setup.py          Fragebogen: Vorschläge, Prüfung, Plan erzeugen
coach/plan_builder.py   Plan-Vorlagen je Ziel und Bausteine
coach/sync.py           Garmin Personal API + FIT-Auswertung
coach/analysis.py       Plan-Abgleich, Auto-Analyse, Tagesform, Prognose
coach/userdata.py       Eingaben aus der App (Häkchen, Notizen, Verschiebungen)
coach/store.py          JSON-Dateien sicher schreiben und lesen
coach/workout_fit.py    Geplante Einheit als Garmin-Workout (FIT-Datei)
coach/cli.py            Übersicht für den Coach (status / sync / week)
web/                    Oberfläche (PWA)
tests/                  Tests (unittest)
CLAUDE.md               Anweisungen für Claude als Coach
```

Persönliches (`athlete.json`, `data/`, `feedback/`, `plan/`, `userdata/`) ist per `.gitignore` vom Repo
ausgeschlossen.

## Lizenz

[MIT](LICENSE): Du darfst den Code frei nutzen, verändern und weitergeben, solange der Lizenzhinweis erhalten bleibt.
