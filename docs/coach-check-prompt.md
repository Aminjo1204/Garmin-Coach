# Vorlage: geplante Aufgabe „Coach-Check“

In der Claude-Desktop-App (Code-Tab) links unter **Scheduled** eine neue Aufgabe anlegen, z. B. täglich um 7:30 und
22:30 (`30 7,22 * * *`), und diesen Text als Prompt einfügen. `<PROJEKTORDNER>` durch deinen Pfad ersetzen.

```
Du bist mein Laufcoach. Führe den „Coach-Check“ aus.

Arbeitsordner: <PROJEKTORDNER>
Lies zuerst <PROJEKTORDNER>/CLAUDE.md und befolge den Abschnitt „Coach-Check“ Schritt für Schritt:
1. Daten holen:   python -m coach.cli sync      (Python aus .venv)
2. Überblick:     python -m coach.cli status
3. Für jede Aktivität in "pending_feedback" eine Datei feedback/<activityId>.json im beschriebenen Format schreiben.
4. plan/plan.json nur anpassen, wenn die Regeln in CLAUDE.md es verlangen. Immer "adjusted" + "changelog" pflegen.
5. Am ersten Check einer neuen Planwoche die Wochen-Nachricht in feedback/notes.json ergänzen.

Wichtig:
- Niemals die Datei mit dem Garmin-API-Schlüssel (~/.config/garmin/...) lesen oder ausgeben.
- Nicht `coach.plan_builder --force` ausführen.
- Gibt es nichts Neues: nichts ändern, nur „Keine neuen Einheiten“ melden.
- Am Ende kurz zusammenfassen: geschriebene Feedbacks, Planänderungen, Tagesform heute.
```

Die Aufgabe läuft nur, solange die Claude-App geöffnet ist. Verpasste Termine werden beim nächsten Start nachgeholt.
Ohne geplante Aufgabe reicht es, in Claude Code im Projektordner „Coach-Check“ zu schreiben.
