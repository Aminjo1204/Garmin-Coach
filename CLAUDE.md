# Garmin Coach – Claude ist der Laufcoach

Claude betreut einen Läufer mit einem Trainingsplan (6–16 Wochen). Das Ziel wählt der Athlet im Fragebogen der App:
VO2max steigern, 5 km, 10 km oder Halbmarathon. Alles Persönliche steht in `athlete.json` (Name, Pulswerte,
5-km-Zeit, Planstart, `training` mit Ziel, Wettkampftag, Zielzeit, Lauftagen, und `coach_context` mit Vorgeschichte
und Mustern). `coach.cli status` gibt diese Werte mit aus. Lies `training` und `coach_context` bei jedem Check.
Der Wochenrhythmus steht in `plan/plan.json` unter `rhythm` (ältere Pläne ohne `rhythm`: Mo Kraft · Di Ruhe ·
Mi VO2max · Do Rad · Fr Schwelle/locker · Sa Ruhe · So langer Lauf).
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
- `coach/plan_builder.py`: erzeugt `plan/plan.json` aus `athlete.json` (Vorlage je Ziel in `template()`, Rhythmus in
  `PATTERNS`, Umfang nach `level`). **Nur einmalig**: `--force` überschreibt alle Anpassungen, nur auf ausdrücklichen
  Wunsch verwenden.
- `coach/setup.py`: Fragebogen-Backend (`/api/setup`): Vorschläge aus Garmin-Daten, Antworten prüfen, `athlete.json`
  schreiben, alten Plan als `plan/plan-<Zeit>.json` sichern, Plan erzeugen, `moves`/`on_watch` zurücksetzen
- `coach/userdata.py`: Eingaben aus der App (`on_watch`, `notes`, `moves`) in `userdata/userdata.json`
- `coach/store.py`: `write_json` / `read_text`: JSON sicher schreiben (temporäre Datei, dann umbenennen) und lesen
- `coach/cli.py`: `status` / `sync` / `week [N]` für den Coach-Check
- `app.py` + `web/`: lokale Web-App (Flask) auf http://127.0.0.1:5057, PWA (Manifest, Service Worker, Icons).
  `app.py --home DIR --port N` legt alle persönlichen Daten in DIR ab (Konfiguration `pace-coach-test` → `testhome/`).
- `feedback/<activityId>.json`: Coach-Feedback (von Claude geschrieben), `feedback/notes.json`: Coach-Nachrichten
- Nicht im Repo: `athlete.json`, `data/`, `feedback/`, `plan/`, `userdata/`, `testhome/`, `CLAUDE.local.md`

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
     - Renntempo (10 km / Halbmarathon): Pace im Zielbereich, gleichmäßig. HM-Tempo darf am Übergang Z3/Z4 liegen.
     - Locker, lang, Rad: mindestens 80 % in Z1–2 (ohne den geplanten zügigen Schlussabschnitt).
     - Wettkampf (`kind: race` bzw. 5-km-Wettkampf): Zeit, Pacing (erste vs. zweite Hälfte), Vergleich mit `goal_time`.
       Danach 2–3 Tage nur locker.
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
       `pb.pyramid([2, 3, 4, 3, 2])`, `pb.race_pace(3, 2000, 2, "ten_k")`.
   - Wettkampftermin (`training.race_date`) nie verschieben. Die Woche davor bleibt Taper: keine Zusatzbelastung.
   - Vom Athleten in der App verschobene Einheiten (`moved_from` gesetzt) respektieren. Sie liegen als Overlay in
     `userdata/userdata.json` (`moves`), `plan/plan.json` bleibt unverändert. Wenn du selbst verschiebst: `date` und
     `weekday` in `plan/plan.json` ändern, die `id` bleibt gleich.
5. Montags (oder beim ersten Check einer neuen Planwoche) eine Wochen-Nachricht oben in `feedback/notes.json`
   einfügen. Die Liste ist neueste zuerst, höchstens 10 behalten: `{"date": "...", "title": "Woche N: …", "text": "…"}`.
   Inhalt: Rückblick (Umfang, Erfüllung, Intensitätsverteilung, VO2max-Trend) und Fokus der neuen Woche.
6. Kurze Zusammenfassung ausgeben: welche Feedbacks geschrieben und welche Anpassungen gemacht wurden.

## Sicherheit
Bei Schmerzen, Krankheit oder auffälligen Werten (Ruhepuls 8 oder mehr über dem Schnitt, Fieber, Brustschmerz):
Training pausieren lassen und bei anhaltenden Beschwerden eine ärztliche Abklärung empfehlen.
Kein medizinischer Rat über die Trainingsanpassung hinaus.

## Journal

Neueste Einträge oben. Format: `### JJJJ-MM-TT – Thema`, danach Stichpunkte (was, warum, Stolperfallen).

### 2026-11-10 – Sync behält die Historie, Dateien werden sicher geschrieben
- Der Sync hat `activities`, `daily_summaries`, `sleep_summaries` und `hrv` bisher komplett überschrieben (120 bzw.
  60 Tage). Ältere Werte gingen verloren. Jetzt (`_with_history` in `coach/sync.py`): Das abgerufene Zeitfenster wird
  ersetzt, alles davor bleibt. So verschwinden in Garmin gelöschte Aktivitäten weiterhin, die Dateien wachsen aber
  mit der Zeit. `body_battery` wird weiter überschrieben (groß, von der App nicht genutzt).
- Leere Antwort von Garmin bei vorhandenen Daten: nichts schreiben, Fehler in `sync_info.json`.
- Neues `coach/store.py`: Schreiben über temporäre Datei + `os.replace`, damit App und Coach-Check nie eine halbe
  Datei lesen. Genutzt von Sync und `userdata`. `setup.py` und `plan_builder.py` schreiben noch direkt.
- `userdata.json`: Vor jedem Speichern Kopie als `userdata.json.bak`. Ist die Datei beschädigt, wird die Sicherung
  geladen und die kaputte Datei als `userdata.json.defekt` abgelegt. Vorher galt sie als leer und der nächste Klick
  hätte alle Notizen und Verschiebungen überschrieben.
- **Stolperfalle Windows:** `os.replace` scheitert mit `PermissionError`, solange ein anderer Prozess die Zieldatei
  liest, und Leser bekommen denselben Fehler während des Ersetzens. Deshalb wiederholen beide Seiten kurz
  (`write_text` bis 5 s, `read_text` bis 2 s). JSON-Dateien in `data/` und `userdata/` immer über `store` lesen.
- Die Diagramme zeigen weiterhin nur 42 Tage (Tagesform) bzw. 56 Tage (Belastung). Die längere Historie ist nur
  gespeichert, noch nicht sichtbar.

### 2026-11-05 – Fragebogen und Pläne je Ziel, Netlify entfernt
- Netlify komplett entfernt (Functions, `coach/netlify.py`, Doku, npm-Dateien, Static-Modus im Frontend). Grund: Der
  neue Netlify-Gratistarif hat 300 Credits/Monat, ein Produktions-Deploy kostet 15. Bei 2 Coach-Checks täglich wäre die
  Seite nach ~10 Tagen pausiert. Die App läuft jetzt nur lokal.
- Fragebogen in der App (6 Schritte: Ziel, Über dich, Stand, Puls, Trainingswoche, Abschluss). Erscheint, wenn kein Plan
  existiert, sonst über „Neuen Plan erstellen“ auf der Planseite. Schreibt `athlete.json` inkl. `training`, erzeugt den
  Plan per Subprozess (`plan_builder --force`) und lädt danach die Module neu (`_reload()` in `app.py`), weil
  `config.py` alles beim Import liest.
- Plan-Builder: Vorlagen für vo2max/5k/10k/half (je 12 Wochen), Rhythmus aus 3–5 Lauftagen + Kraft/Rad optional +
  langer Lauf Sa/So, Umfang nach `level` (Faktor 0,7–1,15 auf Dauer, Niveau 0 eine Wiederholung weniger).
  Mit Wettkampftermin: 6–16 Wochen. Kürzer → Wochen aus dem Aufbau fallen weg (`DROP_ORDER`), länger → vorne
  Grundlagenwochen. Rennen auf das echte Datum, Tag davor nur kurz locker.
- Mit den Standardwerten (`TRAINING_DEFAULTS`) entsteht exakt der alte VO2max-Plan (geprüft per JSON-Vergleich, nur
  zwei Tipp-Texte allgemeiner formuliert). Bestehende Pläne ohne `rhythm` zeigt das Frontend mit dem alten Text.
- Renn-Paces 10 km / HM nach Riegel (Exponent 1,06) aus `five_k`. Maximalpuls ohne Angabe: max(208 − 0,7 × Alter,
  höchster gemessener Lauf-Puls), Schwellenpuls 89 % davon.
- **Stolperfallen:** Testen nur mit `pace-coach-test` (Port 5059, `testhome/`), sonst überschreibt der Fragebogen den
  echten Plan. Der Service Worker liefert nach Änderungen alte Dateien aus: `VERSION` in `web/sw.js` hochzählen bzw.
  im Test die Registrierung löschen. JSON-Dateien nicht mit PowerShell `Set-Content -Encoding utf8` schreiben (BOM →
  Python liest sie als leer).

### 2026-11-05 – README neu gegliedert
- Oben eine kurze Erklärung mit kompakter Funktionsliste, danach die Einrichtung in nummerierten Schritten (1–8:
  Download, Python, API-Schlüssel, Profil, Sync + Plan, Start, Claude-Coach, optional Netlify). Anpassen, Grenzen,
  Aufbau und Lizenz stehen am Ende.
- Warum: Wer das Repo öffnet, soll in wenigen Zeilen sehen, was die App kann, und dann ohne Suchen loslegen können.
- Neue Felder oder Setup-Schritte künftig auch im README nachtragen (Profil-Tabelle, Aufbau-Liste).

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
