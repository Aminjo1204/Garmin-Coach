# Online-Version auf Netlify

Dein PC macht weiter die Arbeit: Garmin-Sync, Analyse und Coach-Feedback. Am Ende jedes Coach-Checks lädt er eine
fertige, statische Version der App zu Netlify hoch. Von dort kannst du sie am Handy öffnen.

- **Passwortschutz** für die ganze Seite (Edge Function `netlify/edge-functions/auth.js`)
- **Deine Eingaben am Handy** (Häkchen, eigenes Feedback, Verschieben) landen in Netlify Blobs
  (`netlify/functions/userdata.mjs`). Der PC holt sie bei jedem Coach-Check und führt sie mit seinen eigenen zusammen.
- Der **Garmin-API-Schlüssel bleibt auf dem PC**. Netlify bekommt nur die fertigen Daten.
- Alles läuft im kostenlosen Netlify-Tarif.

## Einrichtung (einmalig)

Voraussetzungen: Node.js und ein kostenloser Netlify-Account. Alle Befehle im Projektordner ausführen.

**1. Bei Netlify anmelden.** Das öffnet den Browser:

```bash
npx -y netlify-cli@27.14.1 login
```

**2. Seite anlegen.** Der Name wird Teil der Adresse, z. B. `mein-coach` ergibt `https://mein-coach.netlify.app`:

```bash
npx -y netlify-cli@27.14.1 sites:create --name mein-coach
```

Falls der Ordner danach nicht verknüpft ist, zusätzlich `npx -y netlify-cli@27.14.1 link` ausführen.

**3. Passwort festlegen.** Das gibst du später am Handy ein:

```bash
npx -y netlify-cli@27.14.1 env:set COACH_PASSWORD "dein-sicheres-passwort"
```

**4. Sync-Schlüssel einrichten.** Damit der PC deine Handy-Eingaben abholen darf:

```bash
python -m coach.netlify setup
```

Wird die Adresse nicht automatisch gefunden: `python -m coach.netlify setup --url https://mein-coach.netlify.app`

**5. Netlifys eigenen Seitenschutz auf Vorschauen beschränken.** Bei neuen Projekten ist oft „Private“ für alles
voreingestellt. Dann sperrt Netlifys Team-Login auch den Abgleich vom PC aus. In app.netlify.com → Projekt →
Project configuration → Access & security → Visitor access die Option „Applies to“ auf **„Previews only“** stellen.
Die Produktivseite schützt danach das Passwort aus Schritt 3.

**6. Erster Upload:**

```bash
python -m coach.netlify deploy
```

Unter Windows jeweils `.venv\Scripts\python.exe` statt `python` verwenden.

**7. Am Handy:** die Adresse öffnen, einloggen und im Browser-Menü „Zum Startbildschirm hinzufügen“ wählen.

## Danach

- Jeder Coach-Check (siehe `CLAUDE.md`) lädt die Online-Version automatisch neu hoch.
- Vorher lokal ansehen: `python -m coach.netlify preview` (ohne Login und Online-Speicher)
- Abmelden: `https://<deine-seite>/logout`. Passwort ändern: Schritt 3 wiederholen, dann `deploy`.
- `netlify.local.json` (Adresse und Sync-Schlüssel) und `dist/` bleiben lokal und sind nicht im Repo.
