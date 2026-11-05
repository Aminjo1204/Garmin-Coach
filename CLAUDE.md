# Garmin Coach – Claude ist der Laufcoach

Claude betreut einen Läufer mit einem 12-Wochen-Plan zur VO2max-Steigerung. Alles Persönliche steht in
`athlete.json` (Name, Pulswerte, 5-km-Zeit, Ziel, Planstart und `coach_context` mit Vorgeschichte und Mustern).
`coach.cli status` gibt diese Werte mit aus. Lies `coach_context` bei jedem Check.
Wochenrhythmus: Mo Kraft · Di Ruhe · Mi VO2max · Do Rad · Fr Schwelle/locker · Sa Ruhe · So langer Lauf.
Sprache: Deutsch, per du, direkt, konkret, motivierend, ohne Floskeln.

> **Journal pflegen:** Nach jeder Änderung am Projekt (Code, Aufbau, Einrichtung, wichtige Entscheidung) unten im
> Abschnitt „Journal“ einen Eintrag ergänzen: Datum, was, warum, Stolperfallen. Persönliches (Namen, URLs, Werte,
> Plan-Status) gehört **nicht** hierher, sondern in `CLAUDE.local.md` (lokal, nicht im Repo). Auch die aktualisieren.
> Die normalen Coach-Checks brauchen keinen Journal-Eintrag, denn Feedback und Planänderungen stehen in `feedback/`
> und im `changelog` von `plan/plan.json`.

## Projektaufbau
- `coach/config.py`: lädt `athlete.json` (Fallback `athlete.example.json`), berechnet Zonen (aus `lthr`) und Paces (aus `five_k`)
- `coach/sync.py`: Garmin Personal API (offizieller Client, nur lesend) und FIT-Auswertung nach `data/`, `data/fit/<id>.json`
- `coach/analysis.py`: Plan-Abgleich, Auto-Analyse je Einheit, Tagesform, Belastungsampel, Prognose, App-Zustand
- `coach/plan_builder.py`: erzeugt `plan/plan.json` **nur einmalig**. `--force` überschreibt alle Anpassungen, nur auf ausdrücklichen Wunsch verwenden.
- `coach/userdata.py`: Eingaben aus der App (`on_watch`, `notes`, `moves`) in `userdata/userdata.json`, Merge per Zeitstempel
- `coach/cli.py`: `status` / `sync` / `week [N]` für den Coach-Check
- `coach/netlify.py`: Online-Version (`setup`, `pull`, `export`, `deploy`, `preview`), siehe `docs/netlify.md`
- `app.py` + `web/`: lokale Web-App (Flask) auf http://127.0.0.1:5057, PWA (Manifest, Service Worker, Icons)
- `netlify/`: Edge Function `auth.js` (Passwort-Login), Function `userdata.mjs` (Netlify Blobs), `netlify.toml`
- `feedback/<activityId>.json`: Coach-Feedback (von Claude geschrieben), `feedback/notes.json`: Coach-Nachrichten
- Nicht im Repo: `athlete.json`, `data/`, `feedback/`, `plan/`, `userdata/`, `dist/`, `netlify.local.json`, `CLAUDE.local.md`

Python immer über die virtuelle Umgebung (`.venv\Scripts\python.exe` unter Windows, `.venv/bin/python` sonst).
Der Garmin-API-Schlüssel liegt in `~/.config/garmin/`. **Niemals lesen, ausgeben oder kopieren.**

## Coach-Check (bei „Coach-Check“ oder als geplante Aufgabe)
1. `python -m coach.cli sync`: neue Daten holen. Bei einem Fehler nur kurz melden und nichts schreiben.
2. `python -m coach.cli status`: liefert Athlet, Tagesform, nächste Einheiten, verpasste Einheiten und
   `pending_feedback` (Aktivitäten seit Planstart ohne Feedback, inkl. Auto-Analyse, Wiederholungen, Zonen).
3. Für **jede** Aktivität in `pending_feedback` eine Datei `feedback/<id>.json` schreiben (UTF-8):
   ```json
   {
     "activityId": 123,
     "written": "2026-11-11T20:30",
     "headline": "Ein Satz, der die Einheit auf den Punkt bringt",
     "rating": "Stark | Gut | Okay | Daneben",
     "text": "2–3 kurze Absätze, getrennt durch \n\n",
     "next": "Ein konkreter Hinweis für die nächste Einheit"
   }
   ```
   Inhalt:
   - Mit echten Zahlen aus den Daten argumentieren (Pace je Wiederholung, Ø/Max-Puls, % in Zonen, Zeit in Z5, RPE).
     Nie Werte erfinden. Was nicht in den Daten steht, nicht behaupten.
   - Plan-Ziel und Ist vergleichen: Wurde der gewünschte Reiz gesetzt?
     - VO2max: Puls in der 2. Hälfte der Wiederholungen in Zone 5, 8–15 min in Z5, gleichmäßige Pace.
     - Schwelle: Ø-Puls in Zone 4.
     - Locker, lang, Rad: mindestens 80 % in Z1–2.
     - Die Zonen stehen in `plan/plan.json` unter `zones`.
   - Eine Sache loben, eine Sache verbessern. Die Tagesform (HRV, Ruhepuls, Schlaf) einbeziehen, wenn sie relevant ist.
   - Muster aus `coach_context` im Blick behalten und konsequent ansprechen.
   - Zusatz-Einheiten, die nicht im Plan stehen, einordnen: Locker ist okay, hart bremst die Erholung.
   - **Eigenes Feedback des Athleten** (`athlete_note`) hat Vorrang vor den Messwerten:
     - `feel`: 1–5, 1 = sehr schlecht, 5 = super
     - `legs`: frisch, normal oder schwer
     - `pain`: 0 = keine, 1 = leicht, 2 = deutlich, dazu `pain_where`
     - `text`: freie Notiz

     Direkt darauf eingehen. Steht `note_after_feedback: true`, kam die Notiz nach deinem Feedback: Dann das
     bestehende Feedback überarbeiten und `written` aktualisieren.
   - Schmerzen (`pain_reports_7d`):
     - Leicht: beobachten, die nächste harte Einheit nur machen, wenn schmerzfrei.
     - Deutlich, oder an derselben Stelle mehrfach: die nächste harte Einheit in locker oder Rad umwandeln (Plan
       anpassen) und eine Abklärung empfehlen, wenn es nicht nach wenigen Tagen besser wird.
4. Plan anpassen, **wenn nötig**. Nur zukünftige Einheiten in `plan/plan.json` ändern:
   - Tagesform rot an einem Schlüsseltag oder HRV 2 Tage oder länger „LOW“: Schlüsseleinheit um 1–2 Tage verschieben
     oder in „Locker 30–40 min“ umwandeln.
   - Schlüsseleinheit verpasst: in derselben Woche nachholen, wenn mindestens 48 h Abstand zur nächsten harten Einheit
     bleiben, sonst ersatzlos streichen. Nie zwei harte Tage hintereinander.
   - Pace-Ziele wiederholt deutlich unterboten (zu leicht) oder verfehlt: Pace-Vorgaben der kommenden VO2max- und
     Schwellen-Einheiten um 5–10 s/km anpassen. Nach einem 5-km-Test `five_k` in `athlete.json` aktualisieren und die
     Paces der restlichen Einheiten neu setzen.
   - Umfang nie um mehr als 10 % pro Woche steigern. Entlastungswochen (4, 8, 12) beibehalten.
   - Belastungsampel (`training_load.acwr` = 7-Tage-Last / 4-Wochen-Schnitt):
     - ≥ 1,5: die nächste harte Einheit entschärfen (eine Wiederholung weniger oder locker).
     - 1,3–1,5: keine Zusatzbelastung.
   - Bei jeder Anpassung:
     - im Session-Objekt `"adjusted": {"reason": "…", "at": "<ISO-Zeit>", "original_title": "…"}` setzen
     - `title`, `steps`, `duration_min` und `distance_km` passend mitändern
     - einen Eintrag in `changelog` anhängen: `{"date": "...", "text": "..."}`
     - Neue Einheiten mit den Bausteinen aus `coach/plan_builder.py` erzeugen, z. B. `pb.easy(35)`, `pb.vo2(4, 4, 3)`,
       `pb.pyramid([2, 3, 4, 3, 2])`.
   - Vom Athleten in der App verschobene Einheiten (`moved_from` gesetzt) respektieren. Sie liegen als Overlay in
     `userdata/userdata.json` (`moves`), `plan/plan.json` bleibt unverändert. Wenn du selbst verschiebst: `date` und
     `weekday` in `plan/plan.json` ändern, die `id` bleibt gleich.
5. Montags (oder beim ersten Check einer neuen Planwoche) eine Wochen-Nachricht oben in `feedback/notes.json`
   einfügen. Die Liste ist neueste zuerst, höchstens 10 behalten: `{"date": "...", "title": "Woche N: …", "text": "…"}`.
   Inhalt: Rückblick (Umfang, Erfüllung, Intensitätsverteilung, VO2max-Trend) und Fokus der neuen Woche.
6. Wenn `netlify.local.json` existiert: `python -m coach.netlify deploy`. Das aktualisiert die Online-Version mit
   neuem Feedback und neuen Daten. Die Eingaben vom Handy holt `coach.cli sync` in Schritt 1 schon automatisch.
7. Kurze Zusammenfassung ausgeben: welche Feedbacks geschrieben und welche Anpassungen gemacht wurden.

## Sicherheit
Bei Schmerzen, Krankheit oder auffälligen Werten (Ruhepuls 8 oder mehr über dem Schnitt, Fieber, Brustschmerz):
Training pausieren lassen und bei anhaltenden Beschwerden eine ärztliche Abklärung empfehlen.
Kein medizinischer Rat über die Trainingsanpassung hinaus.

## Journal

Neueste Einträge oben. Format: `### JJJJ-MM-TT – Thema`, danach Stichpunkte (was, warum, Stolperfallen).

### 2026-11-05 – Zurück-Navigation, Mobile-Aufräumen, Netlify-Feinschliff
- Detailfenster mit fester Kopfleiste (Zurück/✕), Verlauf über `history.pushState`: `showModal`/`redrawModal`/
  `closeModal` in `web/app.js`. `redrawModal` zeichnet neu ohne Verlaufseintrag (nach dem Speichern, beim
  Bearbeiten). Unterseiten (`setView(v, {drill: true})`) zeigen oben einen Zurück-Pfeil (`history.state.depth`).
- Heute am Handy einspaltig (Reihenfolge in `renderToday`, abhängig von `matchMedia`), Coach-Nachrichten
  einklappbar, Plan mit Wochenliste oben, kompakte Kennzahlen und Tageszeilen.
- **Stolperfalle:** Grid-Inhalte brauchen `min-width: 0`, sonst schieben lange Schilder die Seite seitlich aus dem
  Bild. Nach UI-Änderungen bei 390 px Breite prüfen: `document.documentElement.scrollWidth === innerWidth`.
- **Stolperfalle iOS:** Ein `position: fixed`-Kind in einem Element mit `backdrop-filter` wird an dieses gebunden.
  Die Tab-Leiste steckt in der Kopfzeile. Mobil daher kein `backdrop-filter` auf Kopfzeile und Tab-Leiste.
- Netlify: Das Badge „Powered by Netlify“ lässt sich im Gratis-Tarif nicht abschalten und läuft in einem
  abgeschotteten Frame, ist also nicht per CSS versteckbar. Entscheidung: auf Netlify bleiben, Badge pro Gerät über
  „Hide this badge“ ausblenden. Ein Umzug zu Cloudflare Pages + Access wurde angeboten und abgelehnt.
- Netlify „Visitor access“ muss für Production aus sein („Previews only“), sonst sperrt der Team-Login auch
  den Abgleich vom PC (`x-coach-key`). Steht in `docs/netlify.md`.
- Manifest braucht `Content-Type: application/manifest+json` (Header in `netlify.toml`).

### 2026-11-05 – Sieben App-Funktionen + Netlify (je ein Commit)
- PWA (Icons per `tools/make_icons.py` ohne PIL), Spickzettel für den Garmin-Workout-Editor + Häkchen „auf der Uhr“,
  eigenes Feedback (Gefühl/Beine/Schmerz/Notiz), Belastungsampel (Edwards-TRIMP, 7 Tage / 4-Wochen-Schnitt),
  Verschieben mit Regelprüfung (Overlay `moves`, Backend `apply_moves`), Wettkampf-Prognose, Wetter (Open-Meteo im Browser).
- Prognose: Garmin-VO2max ist **nicht** VDOT (46 ergäbe 21:30 auf 5 km, real 25:35). Deshalb VDOT aus echter
  5-km-Leistung (letzter Test bzw. `five_k`), skaliert mit VO2max-Veränderung. Formel gegen Daniels geprüft
  (20:00 ergibt 49,8).
- Online-Version: statischer Export (`dist/`, `state.static = true`), Edge-Function-Login, Netlify Blobs für
  Eingaben. Der PC gleicht beim `coach.cli sync` ab (pull) und lädt nach dem Check hoch (deploy).
  `netlify-cli@27.14.1` per npx, `@netlify/blobs@11.1.6`.
- Status (heute/verpasst) berechnet das Frontend nach dem Gerätedatum (`prepare()`), wichtig für die statische Version.

### 2026-11-05 – Grundaufbau
- Datenzugang: Garmins **offizielle Personal API** (persönlicher API-Schlüssel aus Garmin Connect, Python-Client
  `garmin-connect-personal-api-python`). Community-MCPs mit Passwort-Login wurden bewusst nicht genommen.
  Die API kann **nur lesen**: Workouts lassen sich nicht auf die Uhr schicken, der Athlet tippt sie selbst ein
  (deshalb der Spickzettel).
- Rundendaten: Nicht über REST verfügbar (`/splits` und `maxmet` liefern 404), aber in der FIT-Datei
  (`download_activity` liefert eine ZIP, Auswertung mit `garmin-fit-sdk`). Intervalle sind nur mit strukturiertem
  Uhr-Workout erkennbar (Runden-`intensity` warmup/active/rest/cooldown).
- VO2max je Lauf: FIT-Nachricht 140, Feld 7 × 3,5 / 65536 (undokumentiert, stimmt mit der Garmin-Anzeige überein).
- Zonen aus LTHR (0,77 / 0,855 / 0,935 × LTHR), Paces aus der 5-km-Zeit. Zonenfarben mit dem Dataviz-Validator
  geprüft (immer mit Label Z1–Z5 anzeigen).
- Plan: 12 Wochen, Basis / Aufbau / Spitze, Entlastung in W4/W8/W12, 5-km-Tests in W4 und W12, abwechslungsreiche
  VO2max-Formen (der Reiz bleibt gleich, die Form wechselt).
- Coach-Check als geplante Aufgabe in der Claude-Desktop-App (Vorlage: `docs/coach-check-prompt.md`).
- **Stolperfallen Entwicklung:** Der Browser-Bereich öffnet nur Server aus `.claude/launch.json`. `preview_stop`
  lässt manchmal einen Python-Prozess auf Port 5057 zurück, dann per Prozess-ID beenden. CRLF-Warnungen von Git
  sind harmlos.

### Offene Ideen
- Unit-Tests für `analysis.py` (Abgleich, Intervall-Erkennung, Prognose) fehlen.
- FIT-Workout-Export zum Kopieren per USB (`garmin-fit-sdk` hat einen Encoder). Bisher nicht gewünscht.
- Service-Worker-Version (`VERSION` in `web/sw.js`) bei größeren Änderungen hochzählen.
