# Garmin Coach

Dein persönlicher Laufcoach für die Garmin-Uhr, mit [Claude](https://claude.com/claude-code) als Trainer.
Die App holt deine Trainings- und Gesundheitsdaten über Garmins **offizielle Personal API**, führt dich durch einen
**12-Wochen-Plan zur VO2max-Steigerung** und wertet jede Einheit automatisch aus. Claude schreibt dir zu jedem Lauf
ein Feedback und passt den Plan an, wenn du müde bist, etwas verpasst hast oder es zwickt.
Alles läuft auf deinem eigenen Rechner, am Handy auf Wunsch als App.

> Inoffizielles Hobbyprojekt, nicht mit Garmin verbunden. Die Garmin Personal API ist nur für die private Nutzung gedacht.

## Was die App kann

- **Heute:** Tagesform aus HRV, Ruhepuls, Schlaf und Body Battery, dazu das heutige Workout mit Puls- und Pace-Zielen
  und einer Empfehlung, wenn du lieber tauschen solltest.
- **Trainingsplan:** 12 Wochen in 3 Phasen mit Entlastungswochen, zwei 5-km-Tests und abwechslungsreichen
  Intervallen (Pyramide, 30/15, Berg, Fahrtspiel …), plus Kraft und lockeres Radfahren.
- **Automatische Analyse:** Pace und Puls je Wiederholung, Zeit in den Zonen und eine Bewertung, ob der geplante
  Reiz gesetzt wurde.
- **Coach-Feedback von Claude** zu jeder Einheit, Wochen-Rückblick und Planänderungen nach festen Regeln.
- **Dein Feedback:** Gefühl, Beine, Schmerzen und Notiz nach jeder Einheit. Der Coach geht darauf ein.
- **Praktisches:** Spickzettel zum Eintippen der Workouts auf die Uhr, Einheiten verschieben mit Regelprüfung,
  Belastungsampel gegen zu schnelles Steigern, Wettkampf-Prognose (5 km bis Halbmarathon) und Wetter-Hinweise.
- **Fortschritt:** VO2max-Verlauf, Intensitätsverteilung, HRV, Ruhepuls und Schlaf.
- **Aufs Handy:** als PWA mit eigenem Icon, auf Wunsch passwortgeschützt online über Netlify.

---

## Installation und Einrichtung

### Voraussetzungen

- Python **3.12+**
- Eine Garmin-Uhr und ein Garmin-Connect-Konto
- Ein **persönlicher API-Schlüssel**: Garmin Connect (Web) → Einstellungen → Persönlicher API-Schlüssel
  ([direkt](https://connect.garmin.com/app/settings/personalApiToken)). Er wird nur einmal angezeigt, also gleich
  sichern.
- Für das Coach-Feedback: [Claude Code](https://claude.com/claude-code) oder die Claude-Desktop-App
- Nur für die Online-Version: [Node.js](https://nodejs.org) und ein kostenloses Netlify-Konto

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

### 4. Profil anlegen

Kopiere `athlete.example.json` nach `athlete.json` und trag deine Werte ein:

| Feld | Bedeutung |
|---|---|
| `name`, `age`, `weight_kg`, `height_cm` | Grunddaten |
| `hr_max`, `hr_rest` | maximale Herzfrequenz und Ruhepuls |
| `lthr` | Puls an der Laktatschwelle. Grobe Schätzung: Ø-Puls eines hart gelaufenen 10-km- oder 30-min-Laufs. **Daraus entstehen alle Pulszonen.** |
| `five_k` | aktuelle 5-km-Zeit (`"mm:ss"`). **Daraus entstehen alle Paces.** |
| `vo2max_start`, `vo2max_goal` | aktueller Garmin-VO2max und Ziel |
| `plan_start` | ein **Montag**, Beginn von Woche 1 |
| `plan_intro_days` | lockere Einstiegstage vor Woche 1 (0–3) |
| `bike_hr_offset` | wie viele Schläge der Puls beim Radfahren niedriger liegt |
| `location`, `training_hour` | Ort (Name, lat, lon) und übliche Trainingszeit für den Wetter-Hinweis |
| `coach_context` | Freitext für den Coach: Vorgeschichte, Verletzungen, Muster, Vorlieben |

Optional lassen sich Zonen (`"zones_run": [[0,139],[140,155],…]`) und Paces (`"paces": {"vo2": "4:55–5:05", …}`)
direkt vorgeben. `athlete.json` bleibt lokal und landet nicht im Repo.

### 5. Daten holen und Plan erzeugen

```bash
python garmin_sync.py
```

```bash
python -m coach.plan_builder
```

Der Plan wird nur einmal erzeugt und danach vom Coach angepasst.

### 6. App starten

- **Windows:** `Pace Coach starten.bat` doppelklicken
- **macOS / Linux:** `./start.sh` ausführen

Die App öffnet sich unter http://127.0.0.1:5057 und holt neue Daten automatisch, wenn der letzte Abruf länger als
30 Minuten her ist.

### 7. Claude als Coach einrichten

[`CLAUDE.md`](CLAUDE.md) beschreibt die Coach-Rolle und den **Coach-Check**: neue Daten holen, zu jeder Einheit ein
Feedback schreiben, den Plan bei Bedarf anpassen und montags eine Wochen-Nachricht schreiben.

- **Von Hand:** Claude Code im Projektordner öffnen und „Coach-Check“ schreiben.
- **Automatisch:** in der Claude-Desktop-App eine geplante Aufgabe anlegen, z. B. morgens und abends. Die Vorlage
  steht in [`docs/coach-check-prompt.md`](docs/coach-check-prompt.md).

### 8. Optional: online aufs Handy

Die App lässt sich passwortgeschützt auf Netlify veröffentlichen. Der PC rechnet weiter alles und lädt nach jedem
Coach-Check eine aktuelle Version hoch. Deine Eingaben am Handy kommen beim nächsten Check zurück auf den PC, der
Garmin-Schlüssel bleibt auf dem PC. Die Schritt-für-Schritt-Anleitung steht in [`docs/netlify.md`](docs/netlify.md).

Danach die Seite am Handy öffnen und im Browser „Zum Startbildschirm hinzufügen“ wählen. Die App startet dann im
Vollbild und zeigt den letzten Stand auch offline.

---

## Anpassen

- **Plan:** `coach/plan_builder.py`. Die Wochen stehen in `WEEKS`, die Bausteine darüber, z. B. `vo2(4, 4, 3)`,
  `pyramid([2, 3, 4, 3, 2])`, `distance_reps(5, 800, 2.5)`, `hill_reps(6, 3)`, `threshold(2, 12, 3)`,
  `long_run(90, finish=15)`, `bike(60)` oder `strength("A")`. Danach `python -m coach.plan_builder --force`
  ausführen. **Achtung:** Das überschreibt den Plan samt aller Coach-Anpassungen.
- **Wochenrhythmus:** in `build()` (`plan_days`). Standard: Mo Kraft · Mi VO2max · Do Rad · Fr Schwelle · So lang.
- **Analyse-Regeln:** `coach/analysis.py`
- **Oberfläche:** `web/` (reines HTML, CSS und JS, kein Build-Schritt)

## Grenzen

- Die Personal API kann **nur lesen**. Workouts kommen nicht automatisch auf die Uhr. Leg Intervalle als Workout in
  Garmin Connect an (der Spickzettel in der App hilft), dann erkennt die Analyse jede Wiederholung.
- Der VO2max je Lauf stammt aus einem nicht dokumentierten Feld der FIT-Datei. Er stimmt mit Garmins Anzeige überein,
  kann sich aber mit Firmware-Updates ändern.
- Zonen und Paces sind Schätzungen. Nach jedem 5-km-Test `five_k` aktualisieren.

## Aufbau

```
app.py                  Flask-Server (127.0.0.1:5057)
garmin_sync.py          Daten-Sync per Kommandozeile
coach/config.py         Profil, Zonen, Paces (aus athlete.json)
coach/sync.py           Garmin Personal API + FIT-Auswertung
coach/analysis.py       Plan-Abgleich, Auto-Analyse, Tagesform, Prognose
coach/plan_builder.py   12-Wochen-Plan
coach/userdata.py       Eingaben aus der App (Häkchen, Notizen, Verschiebungen)
coach/cli.py            Übersicht für den Coach (status / sync / week)
coach/netlify.py        Online-Version (setup / pull / export / deploy / preview)
web/                    Oberfläche (PWA)
netlify/                Login und Speicher für die Online-Version
CLAUDE.md               Anweisungen für Claude als Coach
```

Persönliches (`athlete.json`, `data/`, `feedback/`, `plan/`, `userdata/`) ist per `.gitignore` vom Repo
ausgeschlossen.

## Lizenz

[MIT](LICENSE): Du darfst den Code frei nutzen, verändern und weitergeben, solange der Lizenzhinweis erhalten bleibt.
