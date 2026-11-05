# Garmin Coach

Persönlicher Lauf-Coach als lokale Web-App, ähnlich wie Trainings-Apps à la Runna, aber auf deinem eigenen Rechner und mit
[Claude](https://claude.com/claude-code) als Coach. Die App holt deine Daten über Garmins **offizielle Personal API**,
gleicht jede Einheit mit einem 12-Wochen-Plan zur **VO2max-Steigerung** ab und zeigt Tagesform, Feedback und Fortschritt.

> Inoffizielles Hobbyprojekt, nicht mit Garmin verbunden. Die Garmin Personal API ist nur für die private Nutzung gedacht.

## Was die App kann

- **Heute:**
  - Tagesform aus HRV, Ruhepuls, Schlaf und Body Battery, mit Empfehlung, z. B. die Intervalle zu tauschen, wenn du müde bist
  - das heutige Workout mit Profil-Grafik, Puls- und Pace-Zielen und dem Grund für die Einheit
- **Woche / Plan:**
  - 12 Wochen in 3 Phasen (Basis, VO2max-Aufbau, Spitze & Test), mit Entlastungswochen und zwei 5-km-Tests
  - abwechslungsreiche Intervalle: klassisch, Pyramide, 800/1000/1200 m, 30/15, 30/30, Berg, Leiter, Fahrtspiel, Cruise-Intervalle
  - Kraftprogramm in drei Phasen und lockere Radeinheiten
- **Automatische Analyse jeder Einheit** (aus der FIT-Datei):
  - Pace und Puls je Wiederholung, Zeit in Zonen, Zeit im VO2max-Bereich
  - ob der geplante Reiz erreicht wurde, mit Bewertung
- **Coach-Feedback:** Claude schreibt zu jeder Einheit ein persönliches Feedback und passt den Plan an (siehe unten).
- **Fortschritt:** VO2max-Verlauf pro Lauf, Intensitätsverteilung, HRV mit Normalbereich, Ruhepuls und Schlaf.

Alle Daten bleiben lokal. Persönliches (`athlete.json`, `data/`, `feedback/`, `plan/`) ist per `.gitignore` vom Repo ausgeschlossen.

## Voraussetzungen

- Python **3.12+**
- Garmin-Uhr und Garmin-Connect-Konto
- Ein persönlicher API-Schlüssel: Garmin Connect (Web) → Einstellungen → **Persönlicher API-Schlüssel**
  ([direkt](https://connect.garmin.com/app/settings/personalApiToken)). Der Schlüssel wird nur einmal angezeigt.
- Optional für das Coach-Feedback: [Claude Code](https://claude.com/claude-code) bzw. die Claude-Desktop-App

## Einrichtung

```bash
git clone https://github.com/Aminjo1204/Garmin-Coach.git
cd Garmin-Coach
python -m venv .venv
```

Abhängigkeiten installieren:

```bash
# Windows
.venv\Scripts\python.exe -m pip install -r requirements.txt
# macOS / Linux
.venv/bin/python -m pip install -r requirements.txt
```

**1. API-Schlüssel ablegen.** Leg eine Textdatei an, die nur den Schlüssel enthält:

| System | Pfad |
|---|---|
| Windows | `%USERPROFILE%\.config\garmin\connect-personal-api-key` |
| macOS / Linux | `~/.config/garmin/connect-personal-api-key` |

Alternativ geht die Umgebungsvariable `GARMIN_PERSONAL_API_KEY`. Den Schlüssel nie ins Repo legen.

**2. Profil anlegen.** Kopiere `athlete.example.json` nach `athlete.json` und trag deine Werte ein:

| Feld | Bedeutung |
|---|---|
| `hr_max`, `hr_rest` | maximale Herzfrequenz und Ruhepuls |
| `lthr` | Herzfrequenz an der Laktatschwelle. Grobe Schätzung: Ø-Puls eines hart gelaufenen 10-km- oder 30-min-Laufs. **Daraus werden alle Pulszonen berechnet.** |
| `five_k` | aktuelle 5-km-Zeit (`"mm:ss"`). **Daraus werden alle Paces berechnet.** |
| `vo2max_start`, `vo2max_goal` | aktueller Garmin-VO2max und Ziel |
| `plan_start` | ein **Montag**, Beginn von Woche 1 |
| `plan_intro_days` | lockere Einstiegstage vor Woche 1 (0–3) |
| `coach_context` | Freitext für den Coach: Vorgeschichte, Verletzungen, Muster, Vorlieben |

Optional lassen sich Zonen (`"zones_run": [[0,139],[140,155],…]`) und Paces (`"paces": {"vo2": "4:55–5:05", …}`) direkt vorgeben.

**3. Daten holen und Plan erzeugen:**

```bash
python garmin_sync.py
python -m coach.plan_builder
```

Unter Windows jeweils mit `.venv\Scripts\python.exe` statt `python`, unter macOS/Linux mit `.venv/bin/python`.

**4. App starten:** Unter Windows `Pace Coach starten.bat` doppelklicken, unter macOS/Linux `./start.sh` ausführen.
Danach öffnet sich http://127.0.0.1:5057. Die App synchronisiert beim Öffnen automatisch, wenn der letzte Abruf über
30 Minuten her ist.

## Claude als Coach

[`CLAUDE.md`](CLAUDE.md) beschreibt die Coach-Rolle und den **Coach-Check**:
1. neue Daten holen
2. zu jeder neuen Einheit ein Feedback schreiben (`feedback/<id>.json`)
3. den Plan bei schlechter Tagesform oder verpassten Einheiten anpassen
4. eine Wochen-Nachricht schreiben

- **Manuell:** Claude Code im Projektordner öffnen und „Coach-Check“ schreiben.
- **Automatisch:** eine geplante Aufgabe in der Claude-Desktop-App anlegen. Die Vorlage steht in
  [`docs/coach-check-prompt.md`](docs/coach-check-prompt.md).

## Anpassen

- **Plan:** `coach/plan_builder.py`. Die Wochen stehen in `WEEKS` (Fokus, Mo, Mi, Do, Fr, So). Die Bausteine darüber
  sind z. B. `vo2(4, 4, 3)`, `pyramid([2, 3, 4, 3, 2])`, `distance_reps(5, 800, 2.5)`, `short_intervals(3)`,
  `hill_reps(6, 3)`, `threshold(2, 12, 3)`, `cruise(5)`, `long_run(90, finish=15)`, `bike(60)` und `strength("A")`.
  Nach Änderungen `python -m coach.plan_builder --force` ausführen. Das überschreibt den Plan inklusive aller
  Coach-Anpassungen.
- **Wochenrhythmus:** in `build()` (`plan_days`), Standard Mo Kraft · Mi VO2max · Do Rad · Fr Schwelle · So lang.
- **Analyse-Regeln:** `coach/analysis.py` (`analyze`, `readiness_today`)
- **Oberfläche:** `web/` (reines HTML, CSS und JS, kein Build-Schritt)

## Grenzen

- Die Personal API kann **nur lesen**. Workouts landen nicht automatisch auf der Uhr. Leg Intervalle als Workout in der
  Garmin-Connect-App an (Anleitung bei jeder Einheit), dann erkennt die Analyse jede Wiederholung.
- Der VO2max je Lauf stammt aus einem nicht dokumentierten Feld der FIT-Datei. Er stimmt mit Garmins Anzeige überein,
  kann sich aber mit Firmware-Updates ändern.
- Zonen und Paces sind Schätzungen. Nach jedem 5-km-Test `five_k` aktualisieren.

## Lizenz

[MIT](LICENSE): Du darfst den Code frei nutzen, verändern und weitergeben, solange der Lizenzhinweis erhalten bleibt.

## Aufbau

```
app.py                  Flask-Server (127.0.0.1:5057)
garmin_sync.py          Daten-Sync per Kommandozeile
coach/config.py         Profil, Zonen, Paces (aus athlete.json)
coach/sync.py           Garmin Personal API + FIT-Auswertung
coach/analysis.py       Plan-Abgleich, Auto-Analyse, Tagesform
coach/plan_builder.py   12-Wochen-Plan
coach/cli.py            Übersicht für den Coach (status / sync / week)
web/                    Oberfläche
CLAUDE.md               Anweisungen für Claude als Coach
```
