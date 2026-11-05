// Passwortschutz für die ganze Seite (läuft vor jeder Anfrage).
// Netlify-Umgebungsvariablen: COACH_PASSWORD (Login), COACH_SYNC_KEY (Zugriff des PCs auf /api/userdata).

const COOKIE = "coach_auth";

async function sha256(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function safeEqual(a, b) {
  if (!a || !b || a.length !== b.length) return false;
  let r = 0;
  for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}

function cookie(req, name) {
  const m = (req.headers.get("cookie") || "").match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return m ? m[1] : "";
}

const loginPage = (msg = "") => `<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Pace Coach – Login</title>
<meta name="theme-color" content="#0d0f13"><link rel="manifest" href="/manifest.webmanifest">
<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png">
<style>
  body{margin:0;min-height:100vh;display:grid;place-items:center;background:#0d0f13;color:#eef0f3;font-family:Inter,"Segoe UI",system-ui,sans-serif}
  form{width:min(340px,calc(100% - 32px));background:#16181d;border:1px solid #2a2e37;border-radius:16px;padding:28px;display:grid;gap:14px}
  img{width:56px;height:56px;border-radius:14px}
  h1{font-size:20px;margin:0}
  input{background:#1e2128;border:1px solid #2a2e37;border-radius:10px;padding:12px;color:#eef0f3;font-size:16px}
  button{background:#c8f560;color:#0d0f13;border:0;border-radius:10px;padding:12px;font-weight:700;font-size:16px;cursor:pointer}
  p{margin:0;color:#f07171;font-size:14px}
</style></head><body>
<form method="post" action="/login"><img src="/icons/icon-192.png" alt=""><h1>Pace Coach</h1>
<input type="password" name="password" placeholder="Passwort" autocomplete="current-password" autofocus required>
<button type="submit">Anmelden</button>${msg ? `<p>${msg}</p>` : ""}</form></body></html>`;

const html = (body, status = 401) =>
  new Response(body, { status, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" } });

export default async (req, context) => {
  const password = Netlify.env.get("COACH_PASSWORD");
  if (!password) return html("<p>COACH_PASSWORD ist auf Netlify nicht gesetzt.</p>", 500);
  const url = new URL(req.url);
  const token = await sha256(`pace-coach:${password}`);

  // Der PC (Coach-Check) gleicht deine Eingaben mit einem eigenen Schlüssel ab
  const syncKey = Netlify.env.get("COACH_SYNC_KEY");
  if (url.pathname === "/api/userdata" && syncKey && safeEqual(req.headers.get("x-coach-key") || "", syncKey)) {
    return context.next();
  }

  if (url.pathname === "/login" && req.method === "POST") {
    const form = await req.formData();
    const given = await sha256(`pace-coach:${form.get("password") || ""}`);
    if (safeEqual(given, token)) {
      return new Response(null, {
        status: 303,
        headers: { Location: "/", "Set-Cookie": `${COOKIE}=${token}; Path=/; Max-Age=31536000; HttpOnly; Secure; SameSite=Lax` },
      });
    }
    return html(loginPage("Falsches Passwort."));
  }
  if (url.pathname === "/logout") {
    return new Response(null, { status: 303, headers: { Location: "/", "Set-Cookie": `${COOKIE}=; Path=/; Max-Age=0` } });
  }

  if (safeEqual(cookie(req, COOKIE), token)) return context.next();

  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/data/")) {
    return new Response(JSON.stringify({ error: "login" }), { status: 401, headers: { "content-type": "application/json" } });
  }
  return html(loginPage());
};

export const config = { path: "/*", excludedPath: ["/manifest.webmanifest", "/icons/*"] };
