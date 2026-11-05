/* Pace Coach – Frontend (Vanilla JS, keine Abhängigkeiten) */
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let S = null;
let view = "heute";
let weekSel = null;
let actFilter = "plan";
let U = { on_watch: {}, notes: {}, moves: {} };  // Eingaben aus der App (siehe coach/userdata.py)
let modalRefresh = null;
const API_USER = "/api/userdata";
try { view = localStorage.getItem("view") || "heute"; } catch (_) {}

const ZONE_NAMES = ["Regeneration", "Grundlage", "Tempo", "Schwelle", "VO2max"];
const zc = (z) => `var(--z${z || 1})`;
const KIND = {
  vo2: "VO2max", short: "VO2max kurz", threshold: "Schwelle", tempo: "Tempo", progression: "Progression", hills: "Berg",
  easy: "Locker", long: "Lang", test: "Test", bike_z2: "Rad", strength: "Kraft", rest: "Ruhe", extra: "Zusatz", pre: "Vor Plan",
};
const SPORT_ICO = { run: "🏃", bike: "🚴", strength: "🏋️", rest: "😴", other: "•" };
const STATUS_TXT = { done: "Erledigt", missed: "Verpasst", today: "Heute", planned: "Geplant", rest: "Ruhe" };
const ICON = { ok: "✓", warn: "!", bad: "✕", info: "i" };

// ---------- Format ----------
const dFmt = new Intl.DateTimeFormat("de-AT", { weekday: "short", day: "numeric", month: "short" });
const dFmtLong = new Intl.DateTimeFormat("de-AT", { weekday: "long", day: "numeric", month: "long" });
const dFmtShort = new Intl.DateTimeFormat("de-AT", { day: "numeric", month: "numeric" });
const toDate = (s) => new Date(s + (s.length === 10 ? "T12:00:00" : ""));
const fmtDate = (s) => dFmt.format(toDate(s));
const fmtDateLong = (s) => dFmtLong.format(toDate(s));
const fmtDM = (s) => dFmtShort.format(toDate(s));
const fmtPace = (sec) => (sec ? `${Math.floor(sec / 60)}:${String(Math.round(sec % 60)).padStart(2, "0")}` : "–");
const fmtMin = (m) => { if (!m) return "–"; m = Math.round(m); return m >= 60 ? `${Math.floor(m / 60)}:${String(m % 60).padStart(2, "0")} h` : `${m} min`; };
const fmtStepMin = (m) => (m < 1 ? `${Math.round(m * 60)} s` : `${+m.toFixed(1)} min`);
const addDays = (s, n) => { const d = toDate(s); d.setDate(d.getDate() + n); return d.toISOString().slice(0, 10); };

// ---------- Daten ----------
async function loadUser() {
  try {
    const r = await fetch(API_USER);
    if (r.ok) U = await r.json();
  } catch (_) {}
}

const uval = (kind, key) => { const e = (U[kind] || {})[key]; return e ? e.value : undefined; };

async function uset(kind, key, value) {
  U[kind] = U[kind] || {};
  U[kind][key] = { value, at: new Date().toISOString() };
  refresh();
  try {
    const r = await fetch(API_USER, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind, key, value }) });
    if (!r.ok) throw new Error(r.status);
    U = await r.json();
  } catch (_) {
    toast("Speichern fehlgeschlagen. Bist du offline?");
  }
}

function refresh() {
  render();
  if (!$("#modal").hidden && modalRefresh) modalRefresh();
}

async function load() {
  try {
    const [r] = await Promise.all([fetch("/api/state"), loadUser()]);
    S = await r.json();
  } catch (e) {
    $("#view").innerHTML = `<div class="card">Server nicht erreichbar. Läuft <code>app.py</code>?</div>`;
    return;
  }
  render();
  updateSyncLabel();
  loadWeather();
  const last = S.sync && S.sync.last_sync ? new Date(S.sync.last_sync) : null;
  if (!last || Date.now() - last.getTime() > 30 * 60 * 1000) doSync(true);
}

async function doSync(auto = false) {
  const btn = $("#syncBtn");
  if (btn.classList.contains("busy")) return;
  btn.classList.add("busy");
  $("#syncLabel").textContent = "Synchronisiere …";
  try {
    const r = await fetch("/api/sync", { method: "POST" });
    if (r.status === 409) { toast("Sync läuft bereits."); return; }
    const j = await r.json();
    S = j.state;
    render();
    const n = (j.sync.new_fit || []).length;
    if (!j.sync.ok) toast("Sync mit Fehlern: " + (j.sync.errors || []).join("; ").slice(0, 160));
    else if (!auto || n) toast(n ? `${n} neue Aktivität${n > 1 ? "en" : ""} geladen.` : "Alles aktuell.");
  } catch (e) {
    toast("Sync fehlgeschlagen.");
  } finally {
    btn.classList.remove("busy");
    updateSyncLabel();
  }
}

function updateSyncLabel() {
  const t = S && S.sync && S.sync.last_sync;
  $("#syncLabel").textContent = t ? `Sync ${new Date(t).toLocaleTimeString("de-AT", { hour: "2-digit", minute: "2-digit" })}` : "Sync";
}

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (el.hidden = true), 3500);
}

const sessions = () => S.plan.sessions;
const actById = (id) => S.activities.find((a) => a.id === id);
const sessionById = (id) => sessions().find((s) => s.id === id);
const weekOf = (date) => { const s = sessions().find((x) => x.date === date); return s ? s.week : null; };
const currentWeek = () => {
  const w = weekOf(S.today);
  if (w !== null) return w;
  const first = sessions()[0];
  return first && S.today < first.date ? 0 : S.plan.weeks[S.plan.weeks.length - 1].week;
};
const phaseOf = (id) => S.plan.phases.find((p) => p.id === id) || { name: "", color: "#666" };

// ---------- Zustand vorbereiten ----------
const localISO = (d = new Date()) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
const WD = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];

/** Verschiebungen anwenden und Status nach dem Datum des Geräts berechnen (wichtig für die Online-Version). */
function prepare() {
  if (!S) return;
  S.today = localISO();
  S.plan.sessions.forEach((s) => {
    if (!s.orig_date) s.orig_date = s.moved_from || s.date;
    const mv = uval("moves", s.id);
    s.date = mv || s.orig_date;
    s.moved_from = s.date !== s.orig_date ? s.orig_date : null;
    s.weekday = WD[toDate(s.date).getDay()];
    s.status = s.sport === "rest" ? "rest" : (s.activity_ids || []).length ? "done"
      : s.date < S.today ? "missed" : s.date === S.today ? "today" : "planned";
  });
  S.plan.sessions.sort((a, b) => a.date.localeCompare(b.date) || (a.sport === "rest") - (b.sport === "rest"));
}

// ----- Verschieben mit Regelprüfung -----
const HARD_KINDS = ["vo2", "short", "threshold", "tempo", "progression", "hills", "test"];
const isHard = (s) => s.sport === "run" && (s.key || HARD_KINDS.includes(s.kind));

function moveOptions(s) {
  const w = S.plan.weeks.find((x) => x.week === s.week);
  const days = s.week === 0 ? sessions().filter((x) => x.week === 0).length : 7;
  const others = sessions().filter((x) => x.id !== s.id && x.sport !== "rest");
  const on = (day) => others.filter((x) => x.date === day);
  return Array.from({ length: days }, (_, i) => {
    const d = addDays(w.start, i);
    const reasons = [];
    let level = "ok";
    if (d === s.date) level = "current";
    else if (d < S.today) { level = "block"; reasons.push("liegt in der Vergangenheit"); }
    else {
      if (isHard(s)) {
        const near = [addDays(d, -1), d, addDays(d, 1)].flatMap(on).filter(isHard);
        if (near.length) { level = "block"; reasons.push(`zu nah an „${near[0].title}“ (${near[0].weekday}): nie zwei harte Tage hintereinander`); }
        if (on(addDays(d, -1)).some((x) => x.sport === "strength")) reasons.push("Kraft am Vortag, die Beine sind evtl. müde");
        if (on(addDays(d, 1)).some((x) => x.kind === "long")) reasons.push("Tag vor dem langen Lauf");
      }
      if (s.kind === "long") {
        const near = [addDays(d, -1), addDays(d, 1)].flatMap(on).filter(isHard);
        if (near.length) reasons.push(`direkt neben „${near[0].title}“`);
      }
      const same = on(d);
      if (same.length) reasons.push(`Doppeltag mit „${same[0].title}“`);
      if (level === "ok" && reasons.length) level = "warn";
    }
    return { d, level, reasons };
  });
}

function moveSection(s) {
  if (s.sport === "rest" || !["planned", "today"].includes(s.status)) return "";
  const opts = moveOptions(s);
  const ico = { ok: "✓", warn: "!", block: "✕", current: "●" };
  return `<details class="more"><summary>↔ Verschieben${s.moved_from ? ` <span class="chip adj" style="margin-left:6px">verschoben von ${fmtDate(s.moved_from)}</span>` : ""}</summary>
    <div class="move-list">${opts.map((o) => `<button class="move-opt ${o.level}" ${o.level === "block" || o.level === "current" ? "disabled" : ""} data-move="${s.id}|${o.d}">
      <span class="ico ${o.level === "ok" ? "ok" : o.level === "warn" ? "warn" : o.level === "block" ? "bad" : "info"}">${ico[o.level]}</span>
      <b>${fmtDate(o.d)}</b><span class="t2">${o.level === "current" ? "aktueller Tag" : o.reasons.length ? esc(o.reasons.join(" · ")) : "passt"}</span></button>`).join("")}</div>
    ${s.moved_from ? `<button class="chip" style="margin-top:8px" data-move="${s.id}|reset">Zurück auf ${fmtDate(s.moved_from)}</button>` : ""}
  </details>`;
}

function tomorrowButton(s) {
  if (s.status !== "today" || s.sport === "rest") return "";
  const o = moveOptions(s).find((x) => x.d === addDays(s.date, 1));
  if (!o || o.level === "block") return "";
  return `<button class="chip" data-move="${s.id}|${o.d}" title="${esc(o.reasons.join(" · "))}">Auf morgen ${o.level === "warn" ? "(!)" : ""}</button>`;
}

// ---------- Render ----------
function render() {
  prepare();
  $$("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  const el = $("#view");
  ({ heute: renderToday, woche: renderWeek, plan: renderPlan, aktivitaeten: renderActivities, fortschritt: renderProgress }[view] || renderToday)(el);
  bindCommon(el);
}

function bindCommon(root) {
  $$("[data-act]", root).forEach((n) => n.addEventListener("click", (e) => { e.stopPropagation(); openActivity(+n.dataset.act); }));
  $$("[data-session]", root).forEach((n) => n.addEventListener("click", () => openSession(n.dataset.session)));
  $$("[data-watch]", root).forEach((n) => n.addEventListener("click", (e) => {
    e.stopPropagation();
    const id = n.dataset.watch;
    uset("on_watch", id, uval("on_watch", id) ? null : true);
  }));
  bindNoteForms(root);
  $$("[data-move]", root).forEach((n) => n.addEventListener("click", (e) => {
    e.stopPropagation();
    const [id, d] = n.dataset.move.split("|");
    const s = sessionById(id);
    uset("moves", id, d === "reset" ? null : d);
    toast(d === "reset" ? "Zurück auf den ursprünglichen Tag." : `„${s.title}“ liegt jetzt am ${fmtDate(d)}.`);
  }));
  $$("[data-copy]", root).forEach((n) => n.addEventListener("click", async (e) => {
    e.preventDefault(); e.stopPropagation();
    try { await navigator.clipboard.writeText(n.dataset.copy); toast("Name kopiert."); } catch (_) { toast(n.dataset.copy); }
  }));
}

// ----- Heute -----
function renderToday(el) {
  const today = S.today;
  const todays = sessions().filter((s) => s.date === today);
  const main = todays.find((s) => s.sport !== "rest") || todays[0];
  const next = sessions().filter((s) => s.date > today && s.sport !== "rest").slice(0, 3);
  const latest = S.activities.find((a) => a.feedback) || S.activities[0];
  const notes = (S.notes || []).slice(0, 2);
  const planStart = sessions()[0] && sessions()[0].date;
  const wk = currentWeek();
  const week = S.plan.weeks.find((w) => w.week === wk);

  el.innerHTML = `
    <div class="page-head">
      <h2>Hallo ${esc(S.athlete.name)} 👋</h2>
      <p>${fmtDateLong(today)} · ${week ? `Woche ${wk} · ${esc(phaseOf(week.phase).name)} · ${esc(week.focus)}` : ""}${planStart && today < planStart ? ` · Plan startet ${fmtDate(planStart)}` : ""}</p>
    </div>
    <div class="grid grid-hero">
      <div class="stack">
        ${main ? sessionCard(main, { hero: true }) : `<div class="card"><h3>Heute nichts geplant</h3><p class="t2" style="margin-top:6px">Der Plan startet am ${fmtDate(planStart)}</p></div>`}
        ${feelPrompt()}
        ${watchReminder()}
        ${notes.map((n) => `<div class="card note-card"><div class="label">Coach · ${fmtDate(n.date)}</div><h3 style="margin-top:6px">${esc(n.title)}</h3><p class="t2" style="margin-top:6px;white-space:pre-line">${esc(n.text)}</p></div>`).join("")}
        ${latest ? `<div><div class="section-head"><h3>Letzte Einheit</h3><button class="chip" data-view-link="aktivitaeten">Alle ansehen →</button></div>${activityFeedbackCard(latest)}</div>` : ""}
      </div>
      <div class="stack">
        ${readinessCard(S.readiness.today)}
        ${weatherCard()}
        ${loadCard(S.load && S.load.today)}
        <div class="card">
          <div class="label">Als Nächstes</div>
          <div class="stack" style="gap:10px;margin-top:10px">
            ${next.map((s) => `<div class="row between clickable" data-session="${s.id}" style="cursor:pointer">
                <div><div class="day-title">${esc(s.title)}</div><div class="day-sub">${fmtDate(s.date)} · ${fmtMin(s.duration_min)}</div></div>
                ${s.key ? `<span class="chip key">Schlüssel</span>` : `<span class="chip">${KIND[s.kind] || ""}</span>`}
              </div>`).join("") || `<p class="empty">Keine weiteren Einheiten.</p>`}
          </div>
        </div>
        ${week ? weekStrip(wk) : ""}
      </div>
    </div>`;
  $$("[data-view-link]", el).forEach((b) => b.addEventListener("click", () => setView(b.dataset.viewLink)));
}

function watchReminder() {
  const until = addDays(S.today, 4);
  const todo = sessions().filter((s) => s.date >= S.today && s.date <= until && needsWatch(s) && !uval("on_watch", s.id));
  if (!todo.length) return "";
  return `<div class="card" style="border-color:rgba(250,178,25,.35)">
    <div class="label" style="color:var(--warning)">⌚ Noch auf die Uhr bringen</div>
    <div class="stack" style="gap:8px;margin-top:10px">${todo.map((s) => `<div class="row between clickable" data-session="${s.id}" style="cursor:pointer">
      <div><div class="day-title">${esc(s.title)}</div><div class="day-sub">${fmtDate(s.date)} · Name: ${esc(workoutName(s))}</div></div><span class="chip">Spickzettel →</span></div>`).join("")}</div>
  </div>`;
}

function weekStrip(wk) {
  const all = sessions().filter((s) => s.week === wk);
  const ss = all.filter((s) => s.sport !== "rest" || !all.some((x) => x.date === s.date && x.sport !== "rest"));
  const w = S.plan.weeks.find((x) => x.week === wk);
  const pct = w.sessions_due ? Math.round((100 * w.sessions_done) / w.sessions_due) : 0;
  return `<div class="card">
    <div class="row between"><div class="label">Woche ${wk}</div><span class="t2 num" style="font-size:13px">${w.done_run_km} / ${w.run_km} km</span></div>
    <div class="row" style="gap:6px;margin-top:12px">
      ${ss.map((s) => `<div title="${esc(fmtDate(s.date) + ": " + s.title)}" data-session="${s.id}" style="flex:1;cursor:pointer;text-align:center">
        <div style="font-size:11px;color:var(--muted)">${s.weekday}</div>
        <div style="height:6px;border-radius:3px;margin-top:4px;background:${s.status === "done" ? "var(--good)" : s.status === "missed" ? "var(--critical)" : s.status === "today" ? "var(--accent)" : s.sport === "rest" ? "var(--surface-2)" : "var(--border)"}"></div>
        <div style="font-size:15px;margin-top:4px">${SPORT_ICO[s.sport]}</div></div>`).join("")}
    </div>
    <div class="row between" style="margin-top:10px;font-size:13px"><span class="t2">${w.sessions_done} von ${w.sessions_due} fälligen Einheiten</span><span class="t2">${pct} %</span></div>
  </div>`;
}

function readinessCard(r) {
  if (!r) return "";
  const col = { green: "var(--good)", yellow: "var(--warning)", red: "var(--critical)" }[r.level];
  const lbl = { green: "Bereit", yellow: "Mittel", red: "Erholen" }[r.level];
  const C = 2 * Math.PI * 40;
  return `<div class="card">
    <div class="label">Tagesform</div>
    <div class="ready" style="margin-top:10px">
      <div class="ring"><svg width="92" height="92" viewBox="0 0 92 92"><circle cx="46" cy="46" r="40" fill="none" stroke="var(--surface-2)" stroke-width="8"/>
        <circle cx="46" cy="46" r="40" fill="none" stroke="${col}" stroke-width="8" stroke-linecap="round" stroke-dasharray="${(C * r.score) / 100} ${C}"/></svg>
        <div class="val num">${r.score}<small>${lbl}</small></div></div>
      <ul class="factors">${r.factors.map(([lvl, t]) => `<li><span class="ico ${lvl}">${ICON[lvl]}</span>${esc(t)}</li>`).join("") || `<li>Keine Daten für heute.</li>`}</ul>
    </div>
    <div class="advice ${r.level}">${esc(r.advice)}</div>
  </div>`;
}

const LOAD_COL = { low: "var(--z1)", ok: "var(--good)", high: "var(--warning)", danger: "var(--critical)" };
const LOAD_ICO = { low: "↓", ok: "✓", high: "!", danger: "✕" };

function loadCard(t) {
  if (!t) return "";
  if (t.acwr === null || !t.level) {
    return `<div class="card"><div class="label">Belastungsampel</div><p class="t2" style="margin-top:8px;font-size:13.5px">Braucht mindestens 4 Wochen Trainingsdaten.</p></div>`;
  }
  const pos = Math.min(100, (t.acwr / 2) * 100);
  return `<div class="card">
    <div class="row between"><div class="label">Belastungsampel</div><span class="status" style="color:${LOAD_COL[t.level.key]}">${LOAD_ICO[t.level.key]} ${esc(t.level.name)}</span></div>
    <div class="row" style="align-items:baseline;gap:8px;margin-top:8px"><span class="num" style="font-size:28px;font-weight:700">${t.acwr.toFixed(2).replace(".", ",")}</span><span class="t2" style="font-size:13px">× dein 4-Wochen-Schnitt</span></div>
    <div class="gauge" aria-hidden="true">
      <span style="flex:0.8;background:var(--z1)"></span><span style="flex:0.5;background:var(--good)"></span><span style="flex:0.2;background:var(--warning)"></span><span style="flex:0.5;background:var(--critical)"></span>
      <i style="left:${pos}%"></i>
    </div>
    <div class="gauge-scale"><span style="left:0;transform:none">0</span><span style="left:40%">0,8</span><span style="left:65%">1,3</span><span style="left:75%">1,5</span><span style="left:100%;transform:translateX(-100%)">2+</span></div>
    <p class="t2" style="font-size:13.5px;margin-top:8px">${esc(t.level.text)}</p>
    <p class="muted" style="font-size:12px;margin-top:6px">Last 7 Tage: ${t.acute} · Ø pro Woche (4 Wo.): ${t.chronic}</p>
  </div>`;
}

// ----- Wetter (Open-Meteo, ohne Anmeldung) -----
let W = null;
const WX_ICO = (c) => (c === 0 ? "☀️" : c <= 2 ? "🌤️" : c === 3 ? "☁️" : c <= 48 ? "🌫️" : c <= 57 ? "🌦️" : c <= 67 ? "🌧️" : c <= 77 ? "🌨️" : c <= 82 ? "🌧️" : c <= 86 ? "🌨️" : "⛈️");

async function loadWeather() {
  const loc = S && S.athlete && S.athlete.location;
  if (!loc) return;
  const key = `wx:${loc.lat},${loc.lon}`;
  try {
    const c = JSON.parse(localStorage.getItem(key) || "null");
    if (c && Date.now() - c.t < 30 * 60 * 1000) { W = c.d; return; }
  } catch (_) {}
  try {
    const url = `https://api.open-meteo.com/v1/forecast?latitude=${loc.lat}&longitude=${loc.lon}` +
      "&hourly=temperature_2m,apparent_temperature,precipitation,snowfall,weather_code,wind_gusts_10m" +
      "&past_hours=12&forecast_days=3&timezone=auto";
    const r = await fetch(url);
    if (!r.ok) return;
    W = (await r.json()).hourly;
    try { localStorage.setItem(key, JSON.stringify({ t: Date.now(), d: W })); } catch (_) {}
    if (view === "heute") render();
  } catch (_) {}
}

/** Bewertet das Wetter zur Trainingszeit. Glätte: ≤ 1 °C und Niederschlag/Schnee in den 12 h davor oder gefrierender Regen. */
function weatherFor(day, hour, s) {
  if (!W) return null;
  const i = W.time.indexOf(`${day}T${String(hour).padStart(2, "0")}:00`);
  if (i < 0) return null;
  const at = (k) => W[k][i];
  const prev = (k) => W[k].slice(Math.max(0, i - 12), i + 1);
  const sum = (a) => a.reduce((x, y) => x + (y || 0), 0);
  const temp = at("temperature_2m"), feel = at("apparent_temperature"), code = at("weather_code");
  const gust = at("wind_gusts_10m"), rain = at("precipitation");
  const wet12 = sum(prev("precipitation")), snow12 = sum(prev("snowfall"));
  const hints = [];
  const indoorRun = s && s.sport === "run" ? (isHard(s) ? "Intervalle aufs Laufband verlegen (1 % Steigung, gleiche Pace)" : "Laufband oder stattdessen locker aufs Rad (Rolle)") : "";
  if ([56, 57, 66, 67].includes(code) || (temp <= 1 && (wet12 > 0.2 || snow12 > 0))) {
    hints.push(["bad", `Glättegefahr (${temp.toFixed(0)} °C nach Niederschlag)`, s && s.sport !== "strength" ? (s.sport === "bike" ? "Rad drinnen auf der Rolle" : indoorRun) : ""]);
  }
  if (code >= 95) hints.push(["bad", "Gewitter", "drinnen trainieren oder Einheit verschieben"]);
  if (feel <= -10) hints.push(["bad", `Sehr kalt (gefühlt ${feel.toFixed(0)} °C)`, s && isHard(s) ? "harte Einheit besser drinnen" : "Schichten, Mütze, Handschuhe, Mund und Nase bedecken"]);
  else if (feel <= 0) hints.push(["warn", `Kalt (gefühlt ${feel.toFixed(0)} °C)`, "lange Hose, Handschuhe, 5 min länger einlaufen. Bei Intervallen zählt der Puls, die Pace darf 5–10 s langsamer sein"]);
  if (s && s.sport === "bike" && temp <= 3 && !hints.some((h) => h[0] === "bad")) hints.push(["warn", "Kalt für draußen auf dem Rad", "Rolle oder Ergometer ist die angenehmere Wahl"]);
  if (rain >= 2) hints.push(["warn", `Starker Regen (${rain.toFixed(1)} mm/h)`, "Regenjacke, oder Laufband"]);
  if (gust >= 50) hints.push(["warn", `Sturmböen bis ${Math.round(gust)} km/h`, "windgeschützte Strecke, Intervalle nach Puls statt Pace"]);
  if (temp >= 25) hints.push(["warn", `Warm (${temp.toFixed(0)} °C)`, "früh oder spät laufen, viel trinken, Puls steigt schneller"]);
  return { day, hour, temp, feel, code, gust, rain, hints };
}

function weatherCard() {
  if (!W || !S.athlete.location) return "";
  const hour = S.athlete.training_hour ?? 18;
  const nowH = new Date().getHours();
  // nächste geplante Einheit in den nächsten 2 Tagen (heute nur, wenn die Trainingszeit noch nicht vorbei ist)
  const s = sessions().find((x) => x.sport !== "rest" && x.sport !== "strength" && x.status !== "done" &&
    (x.date > S.today || (x.date === S.today && nowH <= hour)) && x.date <= addDays(S.today, 2));
  const day = s ? s.date : (nowH <= hour ? S.today : addDays(S.today, 1));
  const w = weatherFor(day, hour, s);
  if (!w) return "";
  const ok = !w.hints.length;
  return `<div class="card">
    <div class="row between"><div class="label">Wetter · ${day === S.today ? "heute" : fmtDate(day)} ${hour} Uhr${s ? " · " + esc(KIND[s.kind] || s.title) : ""}</div><span class="muted" style="font-size:12px">${esc(S.athlete.location.name || "")}</span></div>
    <div class="row" style="gap:12px;margin-top:8px"><span style="font-size:30px">${WX_ICO(w.code)}</span>
      <div><div class="num" style="font-size:22px;font-weight:700">${w.temp.toFixed(0)} °C <span class="t2" style="font-size:13px;font-weight:500">gefühlt ${w.feel.toFixed(0)} °C</span></div>
      <div class="t2" style="font-size:12.5px">Niederschlag ${w.rain.toFixed(1)} mm · Böen ${Math.round(w.gust)} km/h</div></div></div>
    ${ok ? `<p class="t2" style="font-size:13.5px;margin-top:10px"><span class="ico ok">✓</span> Gute Bedingungen für draußen.</p>`
      : `<ul class="factors" style="margin-top:10px">${w.hints.map(([lvl, t, tip]) => `<li><span class="ico ${lvl}">${ICON[lvl]}</span><span><b style="color:var(--text)">${esc(t)}</b>${tip ? ": " + esc(tip) : ""}</span></li>`).join("")}</ul>`}
  </div>`;
}

// ----- Einheit -----
function flatSteps(steps) {
  const out = [];
  (steps || []).forEach((s) => {
    if (s.type === "repeat") for (let i = 0; i < s.times; i++) out.push(...flatSteps(s.steps));
    else out.push(s);
  });
  return out;
}

function profileSvg(steps) {
  const fl = flatSteps(steps);
  const total = fl.reduce((a, s) => a + s.min, 0);
  if (!total) return "";
  const W = 1000, H = 86, gap = fl.length > 40 ? 1 : 2;
  let x = 0;
  const rects = fl.map((s) => {
    const w = Math.max(1, (s.min / total) * W - gap);
    const h = 14 + ((s.zone || 1) / 5) * (H - 14);
    const r = `<rect x="${x.toFixed(1)}" y="${H - h}" width="${w.toFixed(1)}" height="${h}" rx="${w > 6 ? 3 : 1}" fill="${zc(s.zone)}"><title>${esc(s.label)} · ${fmtStepMin(s.min)}${s.hr ? ` · ${s.hr[0] ? s.hr[0] + "–" : "<"}${s.hr[1]} bpm` : ""}${s.pace ? " · " + s.pace : ""}</title></rect>`;
    x += (s.min / total) * W;
    return r;
  });
  return `<div class="profile"><svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Workout-Profil">${rects.join("")}</svg></div>`;
}

function stepLine(s) {
  const hr = s.hr ? (s.hr[0] ? `${s.hr[0]}–${s.hr[1]} bpm` : `< ${s.hr[1]} bpm`) : "";
  const tgt = [hr, s.pace ? (/\d:\d\d/.test(s.pace) ? s.pace + " /km" : s.pace) : "", s.note || ""].filter(Boolean).join(" · ");
  return `<div class="step-line"><span class="zdot" style="background:${zc(s.zone)}" title="Z${s.zone}"></span><b>${fmtStepMin(s.min)}</b> ${esc(s.label)} <span class="tgt">Z${s.zone || 1}${tgt ? " · " + esc(tgt) : ""}</span></div>`;
}

function stepsList(steps) {
  return `<ul class="steps">${steps.map((s) => s.type === "repeat"
    ? `<li><div class="rep-head">${s.times} ×${s.label ? " " + esc(s.label) : ""}</div><div class="sub">${s.steps.map(stepLine).join("")}</div></li>`
    : `<li>${stepLine(s)}</li>`).join("")}</ul>`;
}

function sessionCard(s, opt = {}) {
  const phase = phaseOf(S.plan.weeks.find((w) => w.week === s.week)?.phase);
  const acts = (s.activity_ids || []).map(actById).filter(Boolean);
  const dist = s.distance_km ? ` · <b>~${s.distance_km} km</b>` : "";
  const body = s.sport === "rest"
    ? `<p class="purpose">${esc(s.purpose)}</p>${tipsList(s.tips)}`
    : `
      ${profileSvg(s.steps)}
      ${s.steps && s.steps.length ? stepsList(s.steps) : ""}
      ${s.exercises ? exerciseTable(s.exercises) : ""}
      <p class="purpose"><b style="color:var(--text)">Warum?</b> ${esc(s.purpose)}</p>
      ${tipsList(s.tips)}
      ${needsWatch(s) ? garminSheet(s, opt.openSheet) : ""}`;
  return `<div class="card">
    <div class="row between wrap">
      <div class="row wrap" style="gap:8px">
        <span class="label">${opt.hero ? (s.date === S.today ? "Heute" : fmtDateLong(s.date)) : fmtDateLong(s.date)} · W${s.week}</span>
        ${s.key ? `<span class="chip key">★ Schlüsseleinheit</span>` : ""}
        <span class="chip"><span class="phase-dot" style="background:${phase.color}"></span>${esc(KIND[s.kind] || s.kind)}</span>
        ${s.adjusted ? `<span class="chip adj" title="${esc(s.adjusted.reason || "")}">angepasst</span>` : ""}
        ${s.moved_from ? `<span class="chip adj">verschoben von ${esc(WD[toDate(s.moved_from).getDay()])}</span>` : ""}
      </div>
      <div class="row" style="gap:8px">${opt.hero ? tomorrowButton(s) : ""}<span class="status ${s.status}">${STATUS_TXT[s.status] || ""}</span></div>
    </div>
    <div class="workout-title">${SPORT_ICO[s.sport]} ${esc(s.title)}</div>
    ${s.sport !== "rest" ? `<div class="meta"><span><b>${fmtMin(s.duration_min)}</b>${dist}</span>${s.steps && s.steps[0] && s.steps[0].hr ? `<span>Ziel: <b>${esc(mainTarget(s))}</b></span>` : ""}</div>` : ""}
    ${s.adjusted ? `<div class="advice yellow" style="margin-top:12px"><b>Angepasst:</b> ${esc(s.adjusted.reason || "")}</div>` : ""}
    ${acts.length ? `<div style="margin-top:14px" class="stack">${acts.map((a) => activityMini(a)).join("")}</div>` : ""}
    ${acts.length && !opt.expand ? `<details class="more"><summary>Geplante Einheit anzeigen</summary>${body}</details>` : body}
    ${opt.expand || opt.hero ? moveSection(s) : ""}
  </div>`;
}

// ----- Spickzettel für den Garmin-Workout-Editor -----
const STEP_TYPE = { warmup: "Aufwärmen", cooldown: "Abkühlen", recovery: "Erholung" };
const needsWatch = (s) => s.sport === "run" && (s.steps || []).length > 1;
const workoutName = (s) => `W${String(s.week).padStart(2, "0")} ${s.weekday} ${shortTitle(s)}`.slice(0, 40);
const fmtClock = (min) => { const sec = Math.round(min * 60); return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`; };

function sheetStep(st, sport, label) {
  const type = STEP_TYPE[st.type] || (sport === "bike" ? "Radfahren" : "Laufen");
  const dur = st.dist_m ? `Distanz <b>${(st.dist_m / 1000).toLocaleString("de-AT", { minimumFractionDigits: 2 })} km</b>` : `Zeit <b>${fmtClock(st.min)}</b>`;
  const target = st.hr && st.hr[0] && st.type !== "recovery"
    ? `Herzfrequenz → Benutzerdefiniert <b>${st.hr[0]}–${st.hr[1]} bpm</b>` : "Kein Ziel";
  const notes = [st.pace && /\d:\d\d/.test(st.pace) ? `Pace ${st.pace} /km` : st.pace, st.note].filter(Boolean).join(" · ");
  return `<li><span class="sh-n">${label}</span><div><b>${type}</b> · ${dur}<div class="sh-t">Ziel: ${target}</div>${notes ? `<div class="sh-note">Notiz: ${esc(notes)}</div>` : ""}</div></li>`;
}

function garminSheet(s, open) {
  const items = s.steps.map((st, i) => {
    const n = i + 1;
    if (st.type === "repeat") {
      const sub = st.steps.map((x, j) => sheetStep(x, s.sport, `${n}.${j + 1}`)).join("");
      return `<li class="sh-rep"><span class="sh-n">${n}</span><div><b>Wiederholen</b> · <b>${st.times} Mal</b>${st.label ? ` (${esc(st.label)})` : ""}<ol class="sheet">${sub}</ol></div></li>`;
    }
    return sheetStep(st, s.sport, String(n));
  }).join("");
  const name = workoutName(s);
  return `<details class="more sheet-box" ${open ? "open" : ""}>
    <summary>⌚ Garmin-Eingabe (Spickzettel)${uval("on_watch", s.id) ? ` <span class="watch-ok">✓ auf der Uhr</span>` : ""}</summary>
    <p class="t2" style="font-size:13px;margin-top:8px">Garmin Connect App → <b>Training &amp; Planung → Workouts → Workout erstellen → Laufen</b>. Schritte in dieser Reihenfolge anlegen, speichern, dann <b>An Gerät senden</b>.</p>
    <div class="row wrap" style="margin-top:10px;gap:8px"><span class="t2" style="font-size:13px">Name:</span><code class="wname">${esc(name)}</code><button class="chip" data-copy="${esc(name)}">Kopieren</button></div>
    <ol class="sheet">${items}</ol>
    ${watchToggle(s)}
  </details>`;
}

function watchToggle(s) {
  const on = !!uval("on_watch", s.id);
  return `<button class="watch-btn ${on ? "on" : ""}" data-watch="${s.id}">${on ? "✓ Ist auf der Uhr" : "Auf der Uhr? Abhaken ✓"}</button>`;
}

function mainTarget(s) {
  const work = flatSteps(s.steps).filter((x) => x.type === "work");
  const t = ["easy", "long", "bike_z2"].includes(s.kind) ? s.steps[0] : work[0] || s.steps[0];
  if (!t) return "";
  const hr = t.hr ? (t.hr[0] ? `${t.hr[0]}–${t.hr[1]} bpm` : `< ${t.hr[1]} bpm`) : "";
  return [hr, t.pace && /\d:\d\d/.test(t.pace) ? t.pace + " /km" : ""].filter(Boolean).join(" · ");
}

const tipsList = (tips) => (tips && tips.length ? `<ul class="tips">${tips.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>` : "");
const exerciseTable = (ex) => `<table class="ex-table">${ex.map((e) => `<tr><td>${esc(e.name)}${e.note ? `<div class="note">${esc(e.note)}</div>` : ""}</td><td>${esc(e.dose)}</td></tr>`).join("")}</table>`;

function activityMini(a) {
  const m = a.analysis.metrics;
  const isRated = a.analysis.score !== null;
  return `<div class="card tight clickable" data-act="${a.id}" style="background:var(--surface-2)">
    <div class="row between"><div class="row"><span>${SPORT_ICO[m.sport]}</span><b>${esc(a.name)}</b></div>
    <span class="rating ${isRated ? a.analysis.rating : "muted"}">${esc(a.analysis.rating)}</span></div>
    <div class="act-sub" style="margin-top:4px">${actStats(a)}</div>
    ${a.feedback ? `<p style="margin-top:8px;font-size:14px"><b>Coach:</b> ${esc(a.feedback.headline)}</p>` : `<p class="t2" style="margin-top:6px;font-size:13px">Tippen für Analyse →</p>`}
  </div>`;
}

function actStats(a) {
  const m = a.analysis.metrics;
  return [fmtMin(m.dur_min), m.dist_km ? `${m.dist_km} km` : "", m.pace_s ? `${fmtPace(m.pace_s)} /km` : "", m.speed_kmh ? `${m.speed_kmh} km/h` : "",
    m.avg_hr ? `Ø ${Math.round(m.avg_hr)} bpm` : ""].filter(Boolean).map((x) => `<span class="num">${x}</span>`).join("");
}

function activityFeedbackCard(a) {
  const an = a.analysis;
  return `<div class="card clickable" data-act="${a.id}">
    <div class="row between wrap"><div><div class="label">${fmtDate(a.date)}${a.session_title ? " · geplant: " + esc(a.session_title) : ""}</div>
      <h3 style="margin-top:4px">${SPORT_ICO[an.metrics.sport]} ${esc(a.name)}</h3></div>
      <span class="rating ${an.score !== null ? an.rating : "muted"}">${esc(an.rating)}${an.score !== null ? " · " + an.score : ""}</span></div>
    <div class="act-sub" style="margin-top:6px">${actStats(a)}</div>
    ${an.metrics.zone_pct ? zoneBar(an.metrics.zone_pct) : ""}
    ${noteOf(a) ? `<div class="mynote" style="margin-top:12px"><div class="label">Dein Feedback</div>${noteSummary(noteOf(a))}</div>` : ""}
    ${a.feedback ? feedbackBlock(a.feedback) : `<ul class="points">${an.points.slice(0, 4).map(pointLi).join("")}</ul><p class="muted" style="font-size:12.5px;margin-top:10px">Coach-Feedback folgt nach dem nächsten Check.</p>`}
  </div>`;
}

const pointLi = (p) => `<li><span class="ico ${p.level}">${ICON[p.level]}</span>${esc(p.text)}</li>`;

function feedbackBlock(f) {
  return `<div class="feedback" style="margin-top:14px">
    <div class="label" style="color:var(--accent)">Coach-Feedback${f.written ? " · " + fmtDate(f.written.slice(0, 10)) : ""}</div>
    <h4 style="margin-top:4px">${esc(f.headline)}</h4>
    ${(f.text || "").split(/\n\n+/).map((p) => `<p>${esc(p)}</p>`).join("")}
    ${f.next ? `<p class="next"><b>Nächstes Mal:</b> ${esc(f.next)}</p>` : ""}
  </div>`;
}

function zoneBar(pct, showLegend = false) {
  const segs = pct.map((p, i) => (p > 0 ? `<span style="flex:${p};background:${zc(i + 1)}" title="Z${i + 1} ${ZONE_NAMES[i]}: ${p} %">${p >= 8 ? `Z${i + 1} ${p}%` : ""}</span>` : "")).join("");
  return `<div class="zbar">${segs}</div>${showLegend ? zoneLegend() : ""}`;
}

function zoneLegend(sport = "run") {
  const zones = S.plan.zones[sport];
  const rng = (z) => (!z.lo ? `< ${z.hi + 1}` : z.hi >= 250 ? `${z.lo}+` : `${z.lo}–${z.hi}`);
  return `<div class="zlegend">${zones.map((z) => `<span><i class="zdot" style="background:${zc(z.z)}"></i>Z${z.z} ${z.name} ${rng(z)}</span>`).join("")}</div>`;
}

// ----- Woche -----
function renderWeek(el) {
  if (weekSel === null) weekSel = currentWeek();
  const weeks = S.plan.weeks;
  const w = weeks.find((x) => x.week === weekSel) || weeks[0];
  const all = sessions().filter((s) => s.week === w.week);
  // Ruhetag ausblenden, wenn an dem Tag (durch Verschieben) etwas anderes liegt
  const ss = all.filter((s) => s.sport !== "rest" || !all.some((x) => x.date === s.date && x.sport !== "rest"));
  const phase = phaseOf(w.phase);
  const end = addDays(w.start, w.week === 0 ? all.length - 1 : 6);
  el.innerHTML = `
    <div class="page-head row between wrap">
      <div><h2>Woche ${w.week}${w.deload ? " · Entlastung" : ""}</h2>
        <p>${fmtDate(w.start)} – ${fmtDate(end)} · <span class="phase-dot" style="background:${phase.color}"></span> ${esc(phase.name)} · ${esc(w.focus)}</p></div>
      <div class="week-nav">
        <button class="icon-btn" id="wPrev" ${w.week <= weeks[0].week ? "disabled" : ""} aria-label="Vorige Woche">‹</button>
        <button class="chip" id="wNow">Aktuell</button>
        <button class="icon-btn" id="wNext" ${w.week >= weeks[weeks.length - 1].week ? "disabled" : ""} aria-label="Nächste Woche">›</button>
      </div>
    </div>
    <div class="kpis" style="margin-bottom:16px">
      <div class="card tight kpi"><div class="label">Laufen</div><div class="v num">${w.done_run_km} <small>/ ${w.run_km} km</small></div></div>
      <div class="card tight kpi"><div class="label">Trainingszeit</div><div class="v num">${fmtMin(w.done_min)} <small>/ ${fmtMin(w.total_min)}</small></div></div>
      <div class="card tight kpi"><div class="label">Erledigt</div><div class="v num">${w.sessions_done} <small>/ ${w.sessions_due} fällig</small></div></div>
    </div>
    <div class="stack" style="gap:10px">
      ${ss.map((s) => `<div class="card tight day clickable ${s.date === S.today ? "is-today" : ""} ${s.sport === "rest" ? "rest" : ""}" data-session="${s.id}">
        <div class="dow">${s.weekday}<small>${fmtDM(s.date)}</small></div>
        <div><div class="day-title">${SPORT_ICO[s.sport]} ${esc(s.title)} ${s.key ? `<span class="chip key" style="margin-left:4px">★</span>` : ""}${s.adjusted ? `<span class="chip adj" style="margin-left:4px">angepasst</span>` : ""}${s.moved_from ? `<span class="chip adj" style="margin-left:4px">verschoben</span>` : ""}${needsWatch(s) && s.status !== "done" && s.status !== "missed" ? (uval("on_watch", s.id) ? `<span class="chip watch-chip on" style="margin-left:4px" title="Auf der Uhr">⌚ ✓</span>` : `<span class="chip watch-chip" style="margin-left:4px" title="Noch nicht auf der Uhr">⌚ fehlt</span>`) : ""}</div>
          <div class="day-sub">${s.sport === "rest" ? esc(s.tips[0] || "") : `${fmtMin(s.duration_min)}${s.distance_km ? ` · ~${s.distance_km} km` : ""} · ${esc(mainTarget(s) || KIND[s.kind])}`}</div>
          ${(s.activity_ids || []).map((id) => { const a = actById(id); return a ? `<div class="day-sub" style="margin-top:4px;color:var(--text)" data-act="${a.id}">↳ ${esc(a.name)} · ${actStats(a).replace(/<[^>]+>/g, " ")} <span class="rating ${a.analysis.rating}" style="margin-left:6px">${a.analysis.rating}</span></div>` : ""; }).join("")}
        </div>
        <span class="status ${s.status}">${STATUS_TXT[s.status]}</span>
      </div>`).join("")}
    </div>`;
  $("#wPrev", el).onclick = () => { weekSel--; render(); };
  $("#wNext", el).onclick = () => { weekSel++; render(); };
  $("#wNow", el).onclick = () => { weekSel = currentWeek(); render(); };
}

// ----- Plan -----
function renderPlan(el) {
  const weeks = S.plan.weeks;
  const cur = currentWeek();
  const phases = S.plan.phases;
  el.innerHTML = `
    <div class="page-head"><h2>Dein 12-Wochen-Plan</h2><p>Ziel: ${esc(S.goal)} · Start ${fmtDate(S.plan.start)} · 3 Läufe, 1 Rad, 1 Kraft pro Woche</p></div>
    <div class="card">
      <div class="label">Phasen</div>
      <div class="phase-bar">${weeks.map((w) => `<span style="flex:1;background:${phaseOf(w.phase).color};opacity:${w.week < cur ? 0.45 : 1}" title="W${w.week}"></span>`).join("")}</div>
      <div class="grid grid-2" style="margin-top:12px">${phases.filter((p) => p.id !== "intro").map((p) => `<div><div class="row"><span class="phase-dot" style="background:${p.color}"></span><b>${esc(p.name)}</b><span class="muted" style="font-size:13px">W${p.weeks[0]}–${p.weeks[p.weeks.length - 1]}</span></div><p class="t2" style="font-size:13.5px;margin-top:4px">${esc(p.goal)}</p></div>`).join("")}
        <div><div class="row"><b>Wochenrhythmus</b></div><p class="t2" style="font-size:13.5px;margin-top:4px">Mo Kraft · Di Ruhe · <b style="color:var(--text)">Mi VO2max</b> · Do Rad · <b style="color:var(--text)">Fr Schwelle</b> · Sa Ruhe · <b style="color:var(--text)">So Langer Lauf</b>. Tage tauschen ist okay: zwischen zwei harten Einheiten mindestens 48 h.</p></div>
      </div>
    </div>
    <div class="card" style="margin-top:16px">
      <div class="row between wrap"><h3>Laufumfang pro Woche</h3></div>
      <div id="volChart" class="chart" style="margin-top:8px"></div>
    </div>
    <div class="card" style="margin-top:16px">
      <h3>Deine Zonen</h3>
      <p class="t2" style="font-size:13.5px;margin-top:4px">Persönlich aus deinen Daten abgeleitet (HFmax ≈ ${S.athlete.hr_max}, Schwelle ≈ ${S.athlete.lthr} bpm). Tipp: Diese Werte auch auf der Uhr als Laufzonen eintragen. Rad-Zonen liegen etwa 10 bpm tiefer.</p>
      ${zoneLegend("run")}
    </div>
    <div class="stack" style="gap:10px;margin-top:16px">
      ${weeks.map((w) => {
        const ss = sessions().filter((s) => s.week === w.week && s.sport !== "rest");
        return `<div class="card tight plan-week clickable ${w.week === cur ? "current" : ""}" data-week="${w.week}">
          <div class="wk">W${w.week}<small>${fmtDM(w.start)}</small></div>
          <div><div class="row wrap" style="gap:8px"><span class="phase-dot" style="background:${phaseOf(w.phase).color}"></span><b>${esc(w.focus)}</b>${w.deload ? `<span class="chip">Entlastung</span>` : ""}</div>
            <div class="mini-sessions">${ss.map((s) => `<span class="chip ${s.key ? "key" : ""}" title="${esc(s.title)}">${SPORT_ICO[s.sport]} ${esc(shortTitle(s))}</span>`).join("")}</div></div>
          <div class="t2 num" style="text-align:right;font-size:13px">${w.run_km} km<br><span class="muted">${fmtMin(w.total_min)}</span></div>
        </div>`;
      }).join("")}
    </div>`;
  $$("[data-week]", el).forEach((n) => n.addEventListener("click", () => { weekSel = +n.dataset.week; setView("woche"); }));
  barChart($("#volChart", el), weeks.map((w) => ({ label: `W${w.week}`, a: w.run_km, b: w.week <= cur ? w.done_run_km : null })),
    { aName: "Geplant", bName: "Gelaufen", unit: "km" });
}

function shortTitle(s) {
  if (s.sport === "strength") return "Kraft";
  if (s.sport === "bike") return `${s.duration_min}′`;
  return s.title
    .replace(/^Langer Lauf/, "Lang")
    .replace(/^(\d+\/\d+)-Intervalle:\s*/, "$1 · ")
    .replace(/^Cruise-Intervalle:\s*/, "Cruise ")
    .replace(/^(Bergintervalle|Bergsprints|Fahrtspiel):\s*/, (m, n) => (n === "Bergintervalle" ? "Berg " : n + " "))
    .replace(/^(VO2max|Schwelle|Tempodauerlauf):\s*/, "")
    .slice(0, 28);
}

// ----- Aktivitäten -----
function renderActivities(el) {
  const start = sessions()[0].date;
  const list = S.activities.filter((a) => actFilter === "all" || a.date >= start);
  el.innerHTML = `
    <div class="page-head row between wrap"><div><h2>Aktivitäten</h2><p>Jede Einheit wird automatisch gegen den Plan geprüft. Dazu kommt Coach-Feedback.</p></div>
      <div class="filter"><button data-f="plan" class="${actFilter === "plan" ? "active" : ""}">Seit Planstart</button><button data-f="all" class="${actFilter === "all" ? "active" : ""}">Alle (120 Tage)</button></div></div>
    <div class="stack" style="gap:10px">
      ${list.map((a) => `<div class="card tight act clickable" data-act="${a.id}">
        <div class="sport-ico">${SPORT_ICO[a.analysis.metrics.sport]}</div>
        <div><div class="act-name">${esc(a.name)}</div>
          <div class="act-sub"><span>${fmtDate(a.date)}</span>${actStats(a)}</div>
          ${a.session_title || a.feedback || noteOf(a) ? `<div class="act-sub" style="margin-top:2px">${a.session_title ? `<span>Plan: ${esc(a.session_title)}</span>` : ""}${noteOf(a) ? `<span>${noteOf(a).feel ? FEELS[noteOf(a).feel - 1] : "💬"} dein Feedback</span>` : ""}${a.feedback ? `<span style="color:var(--accent)">● Coach-Feedback</span>` : ""}</div>` : ""}</div>
        <span class="rating ${a.analysis.score !== null ? a.analysis.rating : "muted"}">${esc(a.analysis.rating)}</span>
      </div>`).join("") || `<div class="card empty">Seit Planstart noch keine Aktivitäten. Sobald du trainierst und die Uhr synchronisiert, erscheint die Einheit hier.</div>`}
    </div>`;
  $$("[data-f]", el).forEach((b) => b.addEventListener("click", () => { actFilter = b.dataset.f; render(); }));
}

// ----- Eigenes Feedback -----
const FEELS = ["😫", "😕", "😐", "🙂", "😄"];
const FEEL_TXT = ["Sehr schlecht", "Zäh", "Okay", "Gut", "Super"];
const LEGS = [["frisch", "Frisch"], ["normal", "Normal"], ["schwer", "Schwer"]];
const PAIN = [[0, "Keine"], [1, "Leicht"], [2, "Deutlich"]];

function noteOf(a) {
  const v = uval("notes", String(a.id));
  return v !== undefined ? v : a.athlete_note;
}

function noteSummary(n) {
  const parts = [];
  if (n.feel) parts.push(`<span class="chip">${FEELS[n.feel - 1]} ${FEEL_TXT[n.feel - 1]}</span>`);
  if (n.legs) parts.push(`<span class="chip">Beine: ${esc(n.legs)}</span>`);
  if (n.pain) parts.push(`<span class="chip" style="color:${n.pain > 1 ? "#f07171" : "var(--warning)"}">Schmerz: ${PAIN[n.pain][1].toLowerCase()}${n.pain_where ? " · " + esc(n.pain_where) : ""}</span>`);
  return `<div class="row wrap" style="gap:6px;margin-top:8px">${parts.join("")}</div>${n.text ? `<p class="t2" style="margin-top:8px;font-size:14px;white-space:pre-line">„${esc(n.text)}“</p>` : ""}`;
}

function noteForm(a, edit) {
  const n = noteOf(a);
  if (n && !edit) {
    return `<div class="mynote"><div class="row between"><div class="label">Dein Feedback</div><button class="chip" data-note-edit="${a.id}">Bearbeiten</button></div>${noteSummary(n)}</div>`;
  }
  const d = n || {};
  const seg = (field, opts) => `<div class="seg" data-field="${field}">${opts.map(([v, l]) => `<button type="button" data-v="${v}" class="${d[field] === v ? "on" : ""}">${l}</button>`).join("")}</div>`;
  return `<form class="noteform" data-note-form="${a.id}">
    <div class="label">Wie war's?</div>
    ${seg("feel", FEELS.map((f, i) => [i + 1, f]))}
    <div class="label">Beine</div>${seg("legs", LEGS)}
    <div class="label">Schmerzen</div>${seg("pain", PAIN)}
    <input name="pain_where" placeholder="Wo? z. B. linke Wade, Knie außen" value="${esc(d.pain_where || "")}" ${d.pain ? "" : "hidden"}>
    <textarea name="text" rows="3" placeholder="Notiz für den Coach (optional): Wetter, Stress, wie sich die Intervalle angefühlt haben …">${esc(d.text || "")}</textarea>
    <div class="row" style="gap:8px"><button type="submit" class="btn-primary">Speichern</button>${n ? `<button type="button" class="chip" data-note-cancel="${a.id}">Abbrechen</button>` : ""}</div>
    <p class="muted" style="font-size:12px">Ich sehe dein Feedback beim nächsten Coach-Check und gehe darauf ein.</p>
  </form>`;
}

function bindNoteForms(root) {
  $$("[data-note-form]", root).forEach((form) => {
    $$(".seg", form).forEach((seg) => $$("button", seg).forEach((b) => b.addEventListener("click", () => {
      const wasOn = b.classList.contains("on");
      $$("button", seg).forEach((x) => x.classList.remove("on"));
      if (!wasOn) b.classList.add("on");
      if (seg.dataset.field === "pain") form.pain_where.hidden = !(b.classList.contains("on") && +b.dataset.v > 0);
    })));
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const pick = (f) => { const b = $(`.seg[data-field="${f}"] button.on`, form); return b ? b.dataset.v : null; };
      const note = {
        feel: pick("feel") ? +pick("feel") : null,
        legs: pick("legs"),
        pain: pick("pain") !== null ? +pick("pain") : 0,
        pain_where: form.pain_where.hidden ? "" : form.pain_where.value.trim(),
        text: form.text.value.trim(),
      };
      if (!note.feel && !note.legs && !note.pain && !note.text) { toast("Bitte mindestens eine Angabe machen."); return; }
      const id = form.dataset.noteForm;
      uset("notes", id, note);
      toast("Danke! Ich schau's mir beim nächsten Check an.");
    });
  });
  $$("[data-note-edit]", root).forEach((b) => b.addEventListener("click", () => openActivity(+b.dataset.noteEdit, { editNote: true })));
  $$("[data-note-cancel]", root).forEach((b) => b.addEventListener("click", () => openActivity(+b.dataset.noteCancel)));
  $$("[data-quickfeel]", root).forEach((b) => b.addEventListener("click", (e) => {
    e.stopPropagation();
    const [id, v] = b.dataset.quickfeel.split(":");
    uset("notes", id, { ...(uval("notes", id) || {}), feel: +v });
    openActivity(+id, { editNote: true });
  }));
}

function feelPrompt() {
  const since = addDays(S.today, -2);
  const a = S.activities.find((x) => x.date >= since && !noteOf(x));
  if (!a) return "";
  return `<div class="card" style="border-color:rgba(200,245,96,.35)">
    <div class="label" style="color:var(--accent)">Wie war's?</div>
    <div class="day-title" style="margin-top:6px">${SPORT_ICO[a.analysis.metrics.sport]} ${esc(a.name)} · ${fmtDate(a.date)}</div>
    <div class="seg" style="margin-top:10px">${FEELS.map((f, i) => `<button data-quickfeel="${a.id}:${i + 1}" title="${FEEL_TXT[i]}">${f}</button>`).join("")}</div>
  </div>`;
}

async function openActivity(id, opts = {}) {
  const a = actById(id);
  if (!a) return;
  modalRefresh = () => openActivity(id);
  const an = a.analysis, m = an.metrics;
  const s = a.session_id ? sessionById(a.session_id) : null;
  openModal(`
    <div class="label">${fmtDateLong(a.date)} · ${a.start.slice(11, 16)} Uhr${s ? " · geplant: " + esc(s.title) : ""}</div>
    <div class="row between wrap" style="margin-top:6px"><h2>${SPORT_ICO[m.sport]} ${esc(a.name)}</h2>
      <span class="rating ${an.score !== null ? an.rating : "muted"}">${esc(an.rating)}${an.score !== null ? " · " + an.score + "/100" : ""}</span></div>
    <div class="stat-grid">
      ${stat("Dauer", fmtMin(m.dur_min))}${m.dist_km ? stat("Distanz", m.dist_km + " km") : ""}${m.pace_s ? stat("Pace", fmtPace(m.pace_s) + " /km") : ""}
      ${m.speed_kmh ? stat("Tempo", m.speed_kmh + " km/h") : ""}${m.avg_hr ? stat("Ø Puls", Math.round(m.avg_hr)) : ""}${m.max_hr ? stat("Max Puls", Math.round(m.max_hr)) : ""}
      ${m.vo2_min !== null && m.sport !== "strength" ? stat("Zeit in Z5", m.vo2_min + " min") : ""}${m.rpe ? stat("RPE", m.rpe + "/10") : ""}${m.vo2max ? stat("VO2max", m.vo2max) : ""}
      ${m.te_aer ? stat("Training Effect", `${(+m.te_aer).toFixed(1)} / ${(+m.te_ana || 0).toFixed(1)}`) : ""}${m.test_5k ? stat("5 km", m.test_5k) : ""}
    </div>
    <div style="margin-top:16px">${noteForm(a, opts.editNote)}</div>
    ${a.feedback ? feedbackBlock(a.feedback) : ""}
    <h3 style="margin-top:20px">Auto-Analyse</h3>
    <ul class="points">${an.points.map(pointLi).join("") || "<li>Keine Auffälligkeiten.</li>"}</ul>
    ${m.zone_pct ? `<h3 style="margin-top:20px">Zeit in Zonen</h3>${zoneBar(m.zone_pct)}${zoneLegend(m.sport === "bike" ? "bike" : "run")}` : ""}
    <div id="hrChartWrap"></div>
    ${m.reps ? `<h3 style="margin-top:20px">Wiederholungen</h3><table class="laps"><tr><th>#</th><th>Dauer</th><th>Pace</th><th>Ø HF</th><th>Max HF</th></tr>
      ${m.reps.map((r) => `<tr><td>${r.n}</td><td>${fmtStepMin(r.sec / 60)}</td><td>${r.pace || "–"}</td><td>${r.avg_hr ?? "–"}</td><td>${r.max_hr ?? "–"}</td></tr>`).join("")}</table>` : ""}
    <div id="lapsWrap"></div>
  `);
  try {
    const r = await fetch(`/api/activity/${id}`);
    if (!r.ok) return;
    const d = await r.json();
    if (d.series && d.series.length > 5) {
      $("#hrChartWrap").innerHTML = `<h3 style="margin-top:20px">Herzfrequenz</h3><div class="chart" id="hrChart"></div>`;
      const zones = S.plan.zones[m.sport === "bike" ? "bike" : "run"];
      lineChart($("#hrChart"), {
        series: [{ name: "Puls", color: "var(--text)", points: d.series.map(([t, hr]) => [t, hr]) }],
        xType: "num", xFmt: (t) => (t < 60 ? "0 min" : fmtMin(t / 60)), yFmt: (v) => `${Math.round(v)} bpm`, height: 200, gapAt: 60,
        zoneBands: zones, yMin: 90, tipExtra: (i) => { const sp = d.series[i][2]; return sp && m.sport === "run" ? ` · ${fmtPace(1000 / sp)} /km` : sp ? ` · ${(sp * 3.6).toFixed(1)} km/h` : ""; },
      });
    }
    if (d.laps && d.laps.length > 1 && !m.reps) {
      $("#lapsWrap").innerHTML = `<h3 style="margin-top:20px">Runden</h3><table class="laps"><tr><th>#</th><th>Typ</th><th>Dauer</th><th>Distanz</th><th>Pace</th><th>Ø HF</th></tr>
        ${d.laps.map((l) => `<tr><td>${l.i}</td><td>${{ warmup: "Warm-up", active: "Aktiv", rest: "Pause", recovery: "Pause", cooldown: "Cool-down", interval: "Intervall" }[l.intensity] || l.intensity}</td><td>${fmtStepMin(l.sec / 60)}</td><td>${(l.dist / 1000).toFixed(2)} km</td><td>${l.pace_s ? fmtPace(l.pace_s) : "–"}</td><td>${l.avg_hr ?? "–"}</td></tr>`).join("")}</table>`;
    }
  } catch (_) {}
}

const stat = (k, v) => `<div class="stat"><div class="v num">${esc(v)}</div><div class="k">${esc(k)}</div></div>`;

function openSession(id, openSheet = false) {
  const s = sessionById(id);
  if (!s) return;
  openModal(sessionCard(s, { expand: true, openSheet }).replace('class="card"', 'class=""'));
  modalRefresh = () => openSession(id, true);
}

function openModal(html) {
  $("#modalBody").innerHTML = html;
  $("#modal").hidden = false;
  document.body.style.overflow = "hidden";
  bindCommon($("#modalBody"));
}
function closeModal() {
  modalRefresh = null;
  $("#modal").hidden = true;
  document.body.style.overflow = "";
  hideTip();
}

// ----- Fortschritt -----
function renderProgress(el) {
  const vo2 = S.vo2;
  const lastVo2 = vo2.length ? vo2[vo2.length - 1].value : null;
  const ser = S.readiness.series;
  const z = S.zone_4w;
  const zt = z.reduce((a, b) => a + b, 0) || 1;
  const zp = z.map((v) => Math.round((100 * v) / zt));
  const easy = zp[0] + zp[1];
  el.innerHTML = `
    <div class="page-head"><h2>Fortschritt</h2><p>Ziel: VO2max ${S.athlete.vo2max_start} → ${S.athlete.vo2max_goal}</p></div>
    <div class="kpis">
      <div class="card tight kpi"><div class="label">VO2max aktuell</div><div class="v num">${lastVo2 ?? "–"} <small>Ziel ${S.athlete.vo2max_goal}</small></div></div>
      <div class="card tight kpi"><div class="label">Locker-Anteil (4 Wo.)</div><div class="v num">${easy} % <small>Ziel ≥ 75 %</small></div></div>
      <div class="card tight kpi"><div class="label">HRV 7-Tage-Ø</div><div class="v num">${lastVal(ser, "hrv_week") ?? "–"} <small>ms</small></div></div>
      <div class="card tight kpi"><div class="label">Ruhepuls</div><div class="v num">${lastVal(ser, "rhr") ?? "–"} <small>bpm</small></div></div>
    </div>
    <div class="card" style="margin-top:16px"><h3>VO2max (Garmin-Schätzung je Lauf)</h3><div id="vo2Chart" class="chart" style="margin-top:8px"></div>
      <p class="muted" style="font-size:12.5px;margin-top:6px">Garmin zeigt den Wert gerundet an (z. B. 46,6 → 47). Er reagiert langsam: Ein Plus von 2–3 Punkten in 12 Wochen ist ein starkes Ergebnis.</p></div>
    ${predictionCard(S.prediction)}
    <div class="card" style="margin-top:16px"><h3>Belastungsampel (akut ÷ chronisch)</h3>
      <p class="t2" style="font-size:13.5px;margin-top:4px">Trainingslast der letzten 7 Tage geteilt durch deinen 4-Wochen-Schnitt. Am besten bleibst du zwischen 0,8 und 1,3. Über 1,5 steigt das Verletzungsrisiko deutlich.</p>
      <div id="acwrChart" class="chart" style="margin-top:8px"></div></div>
    <div class="card" style="margin-top:16px"><h3>Intensitätsverteilung Laufen (letzte 4 Wochen)</h3>
      <p class="t2" style="font-size:13.5px;margin-top:4px">${Math.round(zt)} min gesamt. Für VO2max-Fortschritt: etwa 75–80 % locker (Z1–2), der Rest gezielt hart (Z4–5). Wenig Z3.</p>
      ${zoneBar(zp)}${zoneLegend("run")}</div>
    <div class="grid grid-2" style="margin-top:16px">
      <div class="card"><h3>HRV (nachts)</h3><div id="hrvChart" class="chart" style="margin-top:8px"></div></div>
      <div class="card"><h3>Ruhepuls</h3><div id="rhrChart" class="chart" style="margin-top:8px"></div></div>
    </div>
    <div class="card" style="margin-top:16px"><h3>Schlaf</h3><div id="sleepChart" class="chart" style="margin-top:8px"></div></div>`;
  if (vo2.length) {
    lineChart($("#vo2Chart", el), {
      series: [{ name: "VO2max", color: "var(--accent)", points: vo2.map((v) => [v.date, v.value]) }],
      refLines: [{ y: S.athlete.vo2max_goal, label: `Ziel ${S.athlete.vo2max_goal}` }],
      yMin: Math.floor(Math.min(...vo2.map((v) => v.value)) - 1), yMax: S.athlete.vo2max_goal + 0.5, yFmt: (v) => v.toFixed(1), height: 220, dots: true,
    });
  } else $("#vo2Chart", el).innerHTML = `<p class="empty">Noch keine Werte.</p>`;
  const pt = (S.prediction && S.prediction.trend) || [];
  if (pt.length > 1) {
    lineChart($("#predChart", el), {
      series: [{ name: "5-km-Prognose", color: "var(--accent)", points: pt.map((x) => [x.date, x.t5k]) }],
      yFmt: (v) => fmtPace(v), tickFmt: (v) => fmtPace(v), height: 170, dots: true,
    });
  }
  const ls = ((S.load && S.load.series) || []).filter((x) => x.acwr !== null);
  if (ls.length > 1) {
    lineChart($("#acwrChart", el), {
      series: [{ name: "Belastung", color: "var(--accent)", points: ls.map((x) => [x.date, x.acwr]) }],
      band: ls.map((x) => [x.date, 0.8, 1.3]), bandName: "Optimal 0,8–1,3",
      refLines: [{ y: 1.5, label: "1,5 Risiko" }], yMin: 0, yMax: Math.max(2, ...ls.map((x) => x.acwr)) + 0.1,
      yFmt: (v) => v.toFixed(2).replace(".", ","), height: 200,
      tipExtra: (i) => ` · 7 Tage: ${ls[i].acute} · Ø/Woche: ${ls[i].chronic}`,
    });
  } else $("#acwrChart", el).innerHTML = `<p class="empty">Braucht mindestens 4 Wochen Trainingsdaten.</p>`;
  lineChart($("#hrvChart", el), {
    series: [{ name: "HRV", color: "var(--z1)", points: ser.filter((x) => x.hrv).map((x) => [x.date, x.hrv]) }],
    band: ser.filter((x) => x.hrv_low).map((x) => [x.date, x.hrv_low, x.hrv_high]), bandName: "Normalbereich",
    yFmt: (v) => `${Math.round(v)} ms`, height: 190,
  });
  lineChart($("#rhrChart", el), {
    series: [{ name: "Ruhepuls", color: "var(--z4)", points: ser.filter((x) => x.rhr).map((x) => [x.date, x.rhr]) }],
    yFmt: (v) => `${Math.round(v)} bpm`, height: 190,
  });
  lineChart($("#sleepChart", el), {
    series: [{ name: "Schlaf-Score", color: "var(--z2)", points: ser.filter((x) => x.sleep_score).map((x) => [x.date, x.sleep_score]) }],
    yMin: 30, yMax: 100, yFmt: (v) => `${Math.round(v)}`, height: 170,
    tipExtra: (i, pts) => { const d = ser.find((x) => x.date === pts[i][0]); return d && d.sleep_h ? ` · ${d.sleep_h} h` : ""; },
  });
}
function predictionCard(p) {
  if (!p) return "";
  const de = (x) => String(x).replace(".", ",");
  return `<div class="card" style="margin-top:16px">
    <h3>Wettkampf-Prognose</h3>
    <p class="t2" style="font-size:13.5px;margin-top:4px">Basis: ${esc(p.source)} (${p.ref_time}) bei VO2max ${de(p.ref_vo2)}. Steigt dein VO2max, wird die Prognose schneller.</p>
    <table class="laps pred"><tr><th>Strecke</th><th>Heute <span class="muted">(VO2max ${de(p.cur_vo2)})</span></th><th>Bei Ziel <span class="muted">(${de(p.goal_vo2)})</span></th><th>Gewinn</th></tr>
      ${p.races.map((r) => `<tr><td><b>${esc(r.name)}</b></td><td class="num">${r.now_fmt}</td><td class="num" style="color:var(--accent);font-weight:700">${r.goal_fmt}</td><td class="num t2">−${r.gain_fmt}</td></tr>`).join("")}
    </table>
    <div class="label" style="margin-top:16px">5-km-Prognose im Verlauf <span style="text-transform:none;letter-spacing:0">(niedriger = schneller)</span></div>
    <div id="predChart" class="chart" style="margin-top:6px"></div>
    <p class="muted" style="font-size:12px;margin-top:6px">Berechnet nach Jack Daniels (VDOT) bei optimalen Bedingungen. Für 10 km und Halbmarathon braucht es zusätzlich passendes Ausdauertraining über die Distanz. Nach jedem 5-km-Test wird die Basis automatisch aktualisiert.</p>
  </div>`;
}

const lastVal = (ser, k) => { for (let i = ser.length - 1; i >= 0; i--) if (ser[i][k]) return ser[i][k]; return null; };

// ---------- Diagramme (SVG) ----------
const tip = $("#tooltip");
function showTip(html, x, y) {
  tip.innerHTML = html;
  tip.hidden = false;
  const r = tip.getBoundingClientRect();
  let left = x + 14, top = y - r.height - 10;
  if (left + r.width > window.innerWidth - 8) left = x - r.width - 14;
  if (top < 8) top = y + 14;
  tip.style.left = left + "px";
  tip.style.top = top + "px";
}
function hideTip() { tip.hidden = true; }

function lineChart(el, o) {
  const W = Math.max(280, el.clientWidth || 600), H = o.height || 200;
  const pad = { l: 44, r: 12, t: 12, b: 26 };
  const pts = o.series[0].points;
  if (!pts.length) { el.innerHTML = `<p class="empty">Keine Daten.</p>`; return; }
  const xv = (x) => (o.xType === "num" ? x : toDate(x).getTime());
  const xs = pts.map((p) => xv(p[0]));
  let ys = pts.map((p) => p[1]);
  if (o.band) o.band.forEach((b) => ys.push(b[1], b[2]));
  if (o.refLines) o.refLines.forEach((r) => ys.push(r.y));
  const x0 = Math.min(...xs), x1 = Math.max(...xs) || x0 + 1;
  let y0 = o.yMin ?? Math.min(...ys), y1 = o.yMax ?? Math.max(...ys);
  if (o.yMin === undefined) y0 -= (y1 - y0) * 0.1 || 1;
  if (o.yMax === undefined) y1 += (y1 - y0) * 0.1 || 1;
  const sx = (x) => pad.l + ((xv(x) - x0) / (x1 - x0 || 1)) * (W - pad.l - pad.r);
  const sy = (y) => pad.t + (1 - (y - y0) / (y1 - y0 || 1)) * (H - pad.t - pad.b);
  const ticks = niceTicks(y0, y1, 4);
  let g = ticks.map((t) => `<line class="grid-line" x1="${pad.l}" x2="${W - pad.r}" y1="${sy(t)}" y2="${sy(t)}"/><text class="axis-text" x="${pad.l - 8}" y="${sy(t) + 4}" text-anchor="end">${o.tickFmt ? o.tickFmt(t) : Number.isInteger(t) ? t : t.toFixed(1)}</text>`).join("");
  // Zonenbänder (HF-Chart)
  if (o.zoneBands) {
    g = o.zoneBands.map((z) => {
      const lo = Math.max(z.lo, y0), hi = Math.min(z.hi, y1);
      if (hi <= lo) return "";
      return `<rect x="${pad.l}" width="${W - pad.l - pad.r}" y="${sy(hi)}" height="${sy(lo) - sy(hi)}" fill="${zc(z.z)}" opacity=".13"/><text class="axis-text" x="${W - pad.r - 4}" y="${sy(hi) + 12}" text-anchor="end">Z${z.z}</text>`;
    }).join("") + g;
  }
  if (o.band && o.band.length > 1) {
    const top = o.band.map((b) => `${sx(b[0])},${sy(b[2])}`).join(" ");
    const bot = o.band.slice().reverse().map((b) => `${sx(b[0])},${sy(b[1])}`).join(" ");
    g += `<polygon points="${top} ${bot}" fill="var(--z2)" opacity=".14"/>`;
  }
  (o.refLines || []).forEach((r) => {
    g += `<line x1="${pad.l}" x2="${W - pad.r}" y1="${sy(r.y)}" y2="${sy(r.y)}" stroke="var(--text-2)" stroke-dasharray="4 4" stroke-width="1"/><text class="ref-text" x="${W - pad.r}" y="${sy(r.y) - 5}" text-anchor="end">${esc(r.label)}</text>`;
  });
  // x-Achse
  const nX = Math.min(6, pts.length);
  for (let i = 0; i < nX; i++) {
    const p = pts[Math.round((i * (pts.length - 1)) / Math.max(1, nX - 1))];
    g += `<text class="axis-text" x="${sx(p[0])}" y="${H - 6}" text-anchor="middle">${o.xType === "num" ? o.xFmt(p[0]) : fmtDM(p[0])}</text>`;
  }
  o.series.forEach((s) => {
    // Lücken (z. B. Uhr pausiert) nicht verbinden
    const d = s.points.map((p, i) => {
      const gap = i && o.gapAt && p[0] - s.points[i - 1][0] > o.gapAt;
      return `${i && !gap ? "L" : "M"}${sx(p[0]).toFixed(1)},${sy(p[1]).toFixed(1)}`;
    }).join("");
    g += `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`;
    if (o.dots) g += s.points.map((p) => `<circle cx="${sx(p[0])}" cy="${sy(p[1])}" r="4" fill="${s.color}" stroke="var(--surface)" stroke-width="2"/>`).join("");
  });
  g += `<line id="xh" y1="${pad.t}" y2="${H - pad.b}" stroke="var(--text-2)" stroke-width="1" opacity="0"/><circle id="xd" r="5" fill="${o.series[0].color}" stroke="var(--surface)" stroke-width="2" opacity="0"/>`;
  g += `<rect x="${pad.l}" y="0" width="${W - pad.l - pad.r}" height="${H}" fill="transparent" id="hit"/>`;
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" height="${H}">${g}</svg>${o.band ? `<div class="legend"><span><i style="background:${o.series[0].color}"></i>${o.series[0].name}</span><span><i class="box" style="background:var(--z2);opacity:.35"></i>${o.bandName}</span></div>` : ""}`;
  const svg = el.querySelector("svg"), xh = svg.querySelector("#xh"), xd = svg.querySelector("#xd");
  svg.querySelector("#hit").addEventListener("mousemove", (e) => {
    const r = svg.getBoundingClientRect();
    const mx = ((e.clientX - r.left) / r.width) * W;
    let best = 0, bd = Infinity;
    pts.forEach((p, i) => { const d = Math.abs(sx(p[0]) - mx); if (d < bd) { bd = d; best = i; } });
    const p = pts[best];
    xh.setAttribute("x1", sx(p[0])); xh.setAttribute("x2", sx(p[0])); xh.setAttribute("opacity", ".5");
    xd.setAttribute("cx", sx(p[0])); xd.setAttribute("cy", sy(p[1])); xd.setAttribute("opacity", "1");
    const label = o.xType === "num" ? o.xFmt(p[0]) : fmtDate(p[0]);
    const bandTxt = o.band ? (() => { const b = o.band.find((b) => b[0] === p[0]); return b ? `<br><span class="muted">${o.bandName}: ${b[1]}–${b[2]}</span>` : ""; })() : "";
    showTip(`<b>${label}</b><br>${o.series[0].name}: ${o.yFmt(p[1])}${o.tipExtra ? o.tipExtra(best, pts) : ""}${bandTxt}`, e.clientX, e.clientY);
  });
  svg.querySelector("#hit").addEventListener("mouseleave", () => { xh.setAttribute("opacity", "0"); xd.setAttribute("opacity", "0"); hideTip(); });
}

function barChart(el, rows, o) {
  const W = Math.max(280, el.clientWidth || 600), H = 210, pad = { l: 36, r: 8, t: 10, b: 26 };
  const max = Math.max(...rows.map((r) => Math.max(r.a || 0, r.b || 0))) * 1.1 || 1;
  const ticks = niceTicks(0, max, 4);
  const sy = (v) => pad.t + (1 - v / ticks[ticks.length - 1]) * (H - pad.t - pad.b);
  const gw = (W - pad.l - pad.r) / rows.length;
  const bw = Math.min(16, (gw - 8) / 2);
  let g = ticks.map((t) => `<line class="grid-line" x1="${pad.l}" x2="${W - pad.r}" y1="${sy(t)}" y2="${sy(t)}"/><text class="axis-text" x="${pad.l - 6}" y="${sy(t) + 4}" text-anchor="end">${t}</text>`).join("");
  const bar = (x, v, fill, stroke) => {
    if (v === null || v === undefined) return "";
    const y = sy(v), h = sy(0) - y;
    if (h <= 0) return `<line x1="${x}" x2="${x + bw}" y1="${sy(0) - 1}" y2="${sy(0) - 1}" stroke="${stroke || fill}" stroke-width="2"/>`;
    const r = Math.min(4, bw / 2, h);
    return `<path d="M${x},${sy(0)} V${y + r} Q${x},${y} ${x + r},${y} H${x + bw - r} Q${x + bw},${y} ${x + bw},${y + r} V${sy(0)} Z" fill="${fill}" ${stroke ? `stroke="${stroke}" stroke-width="1"` : ""}/>`;
  };
  rows.forEach((r, i) => {
    const cx = pad.l + gw * i + gw / 2;
    g += bar(cx - bw - 1, r.a, "var(--surface-2)", "var(--muted)") + bar(cx + 1, r.b, "var(--accent)");
    g += `<text class="axis-text" x="${cx}" y="${H - 8}" text-anchor="middle">${r.label}</text>`;
    g += `<rect x="${pad.l + gw * i}" y="0" width="${gw}" height="${H}" fill="transparent" data-i="${i}" class="hitbar"/>`;
  });
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" height="${H}">${g}</svg><div class="legend"><span><i class="box" style="background:var(--surface-2);outline:1px solid var(--muted)"></i>${o.aName}</span><span><i class="box" style="background:var(--accent)"></i>${o.bName}</span></div>`;
  $$(".hitbar", el).forEach((h) => {
    h.addEventListener("mousemove", (e) => { const r = rows[+h.dataset.i]; showTip(`<b>${r.label}</b><br>${o.aName}: ${r.a} ${o.unit}${r.b !== null ? `<br>${o.bName}: ${r.b} ${o.unit}` : ""}`, e.clientX, e.clientY); });
    h.addEventListener("mouseleave", hideTip);
  });
}

function niceTicks(lo, hi, n) {
  const span = hi - lo || 1;
  const step0 = span / n;
  const mag = Math.pow(10, Math.floor(Math.log10(step0)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= step0) || step0;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(2));
  return out;
}

// ---------- Navigation ----------
function setView(v) {
  view = v;
  try { localStorage.setItem("view", v); } catch (_) {}
  closeModal();
  window.scrollTo(0, 0);
  render();
}

$$("#tabs button").forEach((b) => b.addEventListener("click", () => setView(b.dataset.view)));
$("#syncBtn").addEventListener("click", () => doSync(false));
$$("[data-close]").forEach((b) => b.addEventListener("click", closeModal));
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });
let rT;
window.addEventListener("resize", () => { clearTimeout(rT); rT = setTimeout(() => S && render(), 200); });
if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost" || location.hostname === "127.0.0.1")) {
  navigator.serviceWorker.register("sw.js").catch(() => {});
}
load();
