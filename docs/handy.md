# Die App am Handy nutzen (Tailscale)

Die App läuft auf deinem PC und ist nur dort erreichbar (`127.0.0.1`). Mit Tailscale gibst du sie für deine eigenen
Geräte frei: verschlüsselt, mit einer festen Adresse, nicht aus dem Internet erreichbar. Tailscale ist für private
Nutzung kostenlos.

Der PC muss an sein und die App muss laufen. Ist der PC aus, zeigt die Handy-App den zuletzt geladenen Stand,
Eingaben und Sync gehen dann nicht.

## Einmalig einrichten

### 1. Tailscale am PC
- Von https://tailscale.com/download installieren und anmelden (z. B. mit Google, Microsoft oder Apple).

### 2. Tailscale am iPhone
- App „Tailscale“ aus dem App Store laden und mit **demselben Konto** anmelden.
- Die VPN-Abfrage von iOS erlauben und den Schalter in der App einschalten.

### 3. HTTPS im Tailscale-Konto einschalten
- https://login.tailscale.com/admin/dns öffnen.
- **MagicDNS** aktivieren (falls nicht schon an).
- Unter **HTTPS Certificates** auf **Enable HTTPS** klicken.

Hinweis: Damit wird der Gerätename deines PCs in einem öffentlichen Zertifikatsverzeichnis sichtbar (nur der Name,
keine Inhalte). Enthält er etwas Privates, den PC vorher in Tailscale umbenennen.

### 4. App freigeben
- `Pace Coach Handy.bat` doppelklicken. Das Fenster zeigt am Ende die Adresse, etwa
  `https://dein-pc.tailxxxx.ts.net`.
- Die Freigabe bleibt bestehen, auch nach einem Neustart. Beenden: `tailscale serve reset`.

### 5. App dauerhaft laufen lassen
- `Pace Coach Hintergrund.bat` startet die App ohne Fenster.
- Für den Autostart: `Win + R`, `shell:startup` eingeben, und in den Ordner eine **Verknüpfung** zu
  `Pace Coach Hintergrund.bat` legen.
- Beenden: Task-Manager, Prozess `pythonw.exe`.

### 6. Am iPhone öffnen
- Die Adresse aus Schritt 4 in **Safari** öffnen.
- Teilen-Symbol → **Zum Home-Bildschirm**. Eine alte Coach-App vom Homescreen vorher löschen.

## Wenn es nicht geht
- **Seite lädt nicht:** Ist Tailscale am iPhone eingeschaltet? Läuft die App am PC (http://127.0.0.1:5057)?
- **Zertifikatsfehler:** Schritt 3 prüfen, dann `Pace Coach Handy.bat` noch einmal ausführen. Das erste Zertifikat
  kann eine Minute dauern.
- **Alte Ansicht am Handy:** App schließen und neu öffnen.
- **PC im Ruhezustand:** Dann ist die App nicht erreichbar. In den Windows-Energieoptionen den Ruhezustand am Netz
  ausschalten, wenn du abends vom Handy zugreifen willst.
