// Speicher für deine Eingaben in der Online-Version (Häkchen, eigenes Feedback, Verschiebungen).
// Gleiches Format wie coach/userdata.py: {kind: {key: {value, at}}}, zusammengeführt nach „neuester gewinnt“.
import { getStore } from "@netlify/blobs";

const KINDS = ["on_watch", "notes", "moves"];
const ts = (e) => Date.parse((e && e.at) || "") || 0;

function merge(a, b) {
  const out = {};
  for (const k of KINDS) {
    out[k] = {};
    for (const src of [(a && a[k]) || {}, (b && b[k]) || {}]) {
      for (const [key, e] of Object.entries(src)) {
        if (!(key in out[k]) || ts(e) > ts(out[k][key])) out[k][key] = e;
      }
    }
  }
  return out;
}

const json = (data, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json", "cache-control": "no-store" } });

export default async (req) => {
  const store = getStore("coach");
  const current = (await store.get("userdata", { type: "json" })) || {};
  if (req.method === "GET") return json(merge(current, {}));

  const body = await req.json().catch(() => null);
  if (!body) return json({ error: "ungültige Anfrage" }, 400);

  let next;
  if (req.method === "POST") {
    // einzelner Eintrag aus der App
    if (!KINDS.includes(body.kind) || body.key === undefined || body.key === null) return json({ error: "ungültige Anfrage" }, 400);
    next = merge(current, { [body.kind]: { [String(body.key)]: { value: body.value ?? null, at: new Date().toISOString() } } });
  } else if (req.method === "PUT") {
    // kompletter Stand vom PC
    next = merge(current, body);
  } else {
    return json({ error: "Methode nicht erlaubt" }, 405);
  }
  await store.setJSON("userdata", next);
  return json(next);
};

export const config = { path: "/api/userdata" };
