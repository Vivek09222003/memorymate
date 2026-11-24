"""A simple chat page for testing in plain English: http://localhost:8000/test

Not the real app (that will be React). It just logs in and talks to /chat, so you can test
without Swagger, JSON or ids. Answer MemoryMate's questions with "yes" or "no".
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["Testing"])

PAGE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MemoryMate test page</title>
<style>
  body{margin:0;font:18px/1.5 system-ui,sans-serif;background:#f4f5fb;color:#1d2552}
  header{background:#ffd45c;padding:12px 20px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
  header b{font-size:24px;flex:1}
  main{max-width:860px;margin:0 auto;padding:16px}
  #log{background:#fff;border-radius:16px;padding:16px;height:58vh;overflow-y:auto;display:flex;flex-direction:column;gap:10px}
  .m{max-width:80%;padding:10px 14px;border-radius:14px;background:#eef0fa;white-space:pre-wrap}
  .me{align-self:flex-end;background:#2c3a9e;color:#fff}
  .info{font-size:14px;color:#555d8c;background:none;padding:0 4px}
  .err{background:#fde2e2;color:#8a1020}
  form{display:flex;gap:8px;margin-top:12px}
  input{font:inherit;padding:12px;border:2px solid #d3d6ee;border-radius:12px;flex:1;min-width:0}
  button{font:inherit;padding:10px 18px;border-radius:12px;border:0;background:#2c3a9e;color:#fff;cursor:pointer}
  button.light{background:#e3e6f6;color:#1d2552}
  #quick{display:none;gap:8px;margin-top:8px}
  #alerts{margin-top:12px}
  .alert{background:#1d2552;color:#fff;border-radius:14px;padding:12px 16px;margin-bottom:8px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
  .alert span{flex:1}
  #login{background:#fff;border-radius:16px;padding:20px;display:grid;gap:10px;max-width:420px}
  .card{background:#fff;border-radius:16px;padding:14px 18px;margin-bottom:12px}
  .card h3{margin:0 0 6px;font-size:19px}
  .card ul{margin:4px 0;padding-left:22px}
  .muted{color:#555d8c;font-size:15px}
  .row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
  .row input,.row select{flex:1 1 140px}
  .sug{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:6px 0}
  .sug span{flex:1}
  button.sos{background:#c8102e;color:#fff;font-weight:700;letter-spacing:.02em}
  button.sos.armed{background:#7a0018;outline:3px solid #ffb3c0}
  .emer{background:#fff0f2;border:3px solid #c8102e;border-radius:16px;padding:14px 18px;margin-bottom:12px}
  .emer h3{margin:0 0 6px;color:#a00d26;font-size:21px}
  .emer .row{margin-top:8px}
  a.call{display:inline-block;background:#c8102e;color:#fff;text-decoration:none;border-radius:12px;padding:9px 16px;font-weight:600}
  a.call.light{background:#ffe1e6;color:#7a0018}
  .missed{background:#fff6e5;border:3px solid #d9861a;border-radius:16px;padding:12px 18px;margin-bottom:12px}
  .missed h3{margin:0 0 6px;color:#8a4b00;font-size:19px}
  #overview .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px}
  .ov{background:#f7f8fd;border:2px solid #e3e6f6;border-left-width:8px;border-left-color:#2e9e5b;border-radius:14px;padding:10px 14px;font-size:16px;display:flex;flex-direction:column;gap:3px}
  .ov.attention{border-left-color:#d9861a;background:#fffaf0}
  .ov.emergency{border-left-color:#c8102e;background:#fff0f2}
  .ov b.name{font-size:18px}
  .ov .tag{font-weight:600;font-size:14px}
  .ov .row{margin-top:6px}
  .ov button,.ov a.call{padding:6px 12px;font-size:15px}
</style></head><body>
<header><b>MemoryMate · test page</b><button class="sos" id="sos" style="display:none" aria-label="Help: alert my family">Help (SOS)</button><button class="light" id="notif" style="display:none">Turn on desktop alerts</button><select id="lang" style="display:none;font:inherit;padding:8px;border-radius:10px" aria-label="Language"><option value="en">English</option><option value="hi">हिन्दी</option><option value="hinglish">Hinglish</option></select><span id="who"></span><button class="light" id="out" style="display:none">Log out</button></header>
<main>
  <form id="login"><div>Log in to start (same accounts as /docs). Elder accounts get the chat, family accounts get the dashboard.</div>
    <input id="email" placeholder="Email" value="vivek@example.com" autocomplete="username">
    <input id="pw" type="password" placeholder="Password" autocomplete="current-password">
    <button>Log in</button><div id="lerr" class="m err" style="display:none"></div></form>
  <form id="esignup" style="background:#fff;border-radius:16px;padding:20px;display:grid;gap:10px;max-width:420px;margin-top:14px">
    <div><b>New to MemoryMate?</b> Create your own account.</div>
    <input id="ename" placeholder="Your name" required>
    <input id="eemail" placeholder="Email" required autocomplete="username">
    <input id="epw" type="password" placeholder="Choose a password (6+ characters)" required autocomplete="new-password">
    <input id="ephone" type="tel" placeholder="Your phone number (optional, so family can call you)" autocomplete="tel">
    <select id="elang" style="font:inherit;padding:12px;border:2px solid #d3d6ee;border-radius:12px"><option value="en">English</option><option value="hi">हिन्दी</option><option value="hinglish">Hinglish</option></select>
    <button>Create my account</button><div id="eerr" class="m err" style="display:none"></div></form>
  <form id="signup" style="background:#fff;border-radius:16px;padding:20px;display:grid;gap:10px;max-width:420px;margin-top:14px">
    <div><b>New family member or doctor?</b> Sign up with the code you were given.</div>
    <input id="sname" placeholder="Your name" required>
    <input id="semail" placeholder="Email" required autocomplete="username">
    <input id="spw" type="password" placeholder="Choose a password (6+ characters)" required autocomplete="new-password">
    <input id="scode" placeholder="Code, e.g. K7M2Q9RD" required style="text-transform:uppercase">
    <button>Sign up and connect</button><div id="serr" class="m err" style="display:none"></div></form>
  <div id="family" style="display:none">
    <div id="femer"></div>
    <div id="fmissed"></div>
    <div id="overview"></div>
    <div class="row" style="margin-bottom:12px"><label for="elder" id="elderlabel">Relative:</label><select id="elder" style="font:inherit;padding:8px;border-radius:10px"></select>
      <button class="light" id="refresh">Refresh</button></div>
    <div id="dash"></div>
    <div class="card"><h3 id="codetitle">Got a code from a patient or relative?</h3>
      <form id="joinf" class="row"><input id="jcode" placeholder="e.g. K7M2Q9RD" style="text-transform:uppercase" required><button>Connect</button></form>
      <div id="jmsg" class="muted"></div></div>
    <div class="card" id="doc" style="display:none"><h3>Add a health note</h3>
      <p class="muted">Advice or a doctor's instruction. It's added to their memory only if they accept it.</p>
      <form id="notef" class="row"><input id="ntext" placeholder="e.g. Walk 20 minutes every morning; keep sugar low" required style="flex:1 1 300px"><button>Send note</button></form>
      <div id="nmsg" class="muted"></div></div>
    <div class="card"><h3 id="sugtitle">Suggest a medicine or reminder</h3>
      <p class="muted">It only starts ringing after your relative accepts it.</p>
      <form id="sugf" class="row">
        <input id="st" placeholder="What, e.g. Call Priya" required>
        <select id="sk" style="font:inherit;padding:10px;border-radius:12px"><option value="CALL">Call</option><option value="MEDICINE">Medicine</option><option value="APPOINTMENT">Appointment</option><option value="TASK">Task</option><option value="BIRTHDAY">Birthday</option></select>
        <input id="sd" type="date" required><input id="sti" type="time" value="18:00" required>
        <select id="srep" style="font:inherit;padding:10px;border-radius:12px"><option value="NONE">Once</option><option value="DAILY">Every day</option><option value="WEEKLY">Every week</option><option value="YEARLY">Every year</option></select>
        <input id="snotes" placeholder="Notes, e.g. 5 mg after dinner">
        <button>Suggest</button></form>
      <div id="sugmsg" class="muted"></div></div>
  </div>
  <div id="app" style="display:none">
    <div id="emer"></div>
    <div id="phonebox"></div>
    <div id="alerts"></div>
    <div id="docnotes"></div>
    <div id="suggestions"></div>
    <div id="log"></div>
    <div id="quick"><button id="yes">Yes</button><button class="light" id="no">No</button></div>
    <form id="say"><input id="msg" placeholder="Type a message, e.g. My grandson Rahul works at Infosys" autocomplete="off"><button>Send</button></form>
    <p class="info">Tips: answer MemoryMate's questions with "yes" or "no". Try: "What do I have tomorrow?", "Did I take my medicine?", "Forget that I like tea".</p>
  </div>
</main>
<script>
{
let token = sessionStorage.getItem("mm_token") || "";
const $ = s => document.querySelector(s);
const esc = t => String(t ?? "").replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));

function add(text, cls) {
  const d = document.createElement("div"); d.className = "m " + (cls || ""); d.textContent = text;
  $("#log").appendChild(d); $("#log").scrollTop = $("#log").scrollHeight;
}
async function api(path, opts = {}) {
  const r = await fetch(path, {...opts, headers: {...(opts.headers || {}), Authorization: "Bearer " + token}});
  if (r.status === 401) { logout(); throw new Error("Please log in again."); }
  const body = r.status === 204 ? null : await r.json();
  if (!r.ok) throw new Error(body && body.detail ? (typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail)) : r.statusText);
  return body;
}
let role = "";
function show(loggedIn) {
  $("#login").style.display = loggedIn ? "none" : "grid";
  $("#signup").style.display = loggedIn ? "none" : "grid";
  $("#esignup").style.display = loggedIn ? "none" : "grid";
  $("#app").style.display = loggedIn && role === "ELDER" ? "block" : "none";
  $("#family").style.display = loggedIn && (role === "FAMILY" || role === "DOCTOR") ? "block" : "none";
  $("#doc").style.display = loggedIn && (role === "FAMILY" || role === "DOCTOR") ? "block" : "none";
  $("#out").style.display = loggedIn ? "inline-block" : "none";
  $("#sos").style.display = loggedIn && role === "ELDER" ? "inline-block" : "none";
}
$("#lang").addEventListener("change", async () => {
  try { await api("/auth/me", {method: "PATCH", headers: {"Content-Type": "application/json"},
                               body: JSON.stringify({preferred_language: $("#lang").value})}); } catch (e) {}
});
function logout() { $("#lang").style.display = "none"; token = ""; role = ""; sessionStorage.removeItem("mm_token"); show(false); }

$("#login").addEventListener("submit", async e => {
  e.preventDefault(); $("#lerr").style.display = "none";
  const form = new URLSearchParams({username: $("#email").value, password: $("#pw").value});
  const r = await fetch("/auth/login", {method: "POST", body: form});
  if (!r.ok) { $("#lerr").textContent = "Wrong email or password."; $("#lerr").style.display = "block"; return; }
  token = (await r.json()).access_token; sessionStorage.setItem("mm_token", token);
  askNotify(); start();
});
$("#esignup").addEventListener("submit", async e => {
  e.preventDefault(); $("#eerr").style.display = "none";
  const body = {name: $("#ename").value, email: $("#eemail").value, password: $("#epw").value,
                role: "ELDER", preferred_language: $("#elang").value, phone: $("#ephone").value.trim() || null};
  const r = await fetch("/auth/register", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
  if (!r.ok) { const b = await r.json().catch(() => ({})); $("#eerr").textContent = typeof b.detail === "string" ? b.detail : "Please check the details (a real email, and a password of 6+ characters)."; $("#eerr").style.display = "block"; return; }
  const form = new URLSearchParams({username: body.email, password: body.password});
  const t = await fetch("/auth/login", {method: "POST", body: form});
  token = (await t.json()).access_token; sessionStorage.setItem("mm_token", token);
  askNotify(); start();
});
$("#signup").addEventListener("submit", async e => {
  e.preventDefault(); $("#serr").style.display = "none";
  const body = {name: $("#sname").value, email: $("#semail").value, password: $("#spw").value,
                role: "FAMILY", invite_code: $("#scode").value.trim().toUpperCase()};
  const r = await fetch("/auth/register", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
  if (!r.ok) { const b = await r.json().catch(() => ({})); $("#serr").textContent = typeof b.detail === "string" ? b.detail : "Please check the details (password needs 6+ characters)."; $("#serr").style.display = "block"; return; }
  const form = new URLSearchParams({username: body.email, password: body.password});
  const t = await fetch("/auth/login", {method: "POST", body: form});
  token = (await t.json()).access_token; sessionStorage.setItem("mm_token", token); start();
});
$("#out").addEventListener("click", logout);

async function start() {
  try {
    const me = await api("/auth/me");
    role = me.role;
    $("#lang").value = me.preferred_language; $("#lang").style.display = "inline-block";
    $("#who").textContent = me.name + " (" + me.role.toLowerCase() + ")";
    show(true);
    updateNotifButton();
    if (role === "FAMILY" || role === "DOCTOR") {
      loadElders(); checkFamilyAlerts(); return;
    }
    $("#log").innerHTML = ""; add("Hello " + me.name + ". Tell me something, or ask me anything you've told me.");
    phoneBox(me.phone);
    checkAlerts();
  } catch (e) { logout(); }
}

async function send(text) {
  text = text.trim(); if (!text) return;
  add(text, "me"); $("#quick").style.display = "none";
  const thinking = document.createElement("div"); thinking.className = "m info"; thinking.textContent = "Thinking…";
  $("#log").appendChild(thinking);
  try {
    const r = await api("/chat", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({message: text})});
    thinking.remove(); add(r.reply);
    if (r.emergency) renderEmer(r.emergency);
    if (r.suggest_help && !r.emergency) suggestHelp();
    const notes = [];
    const SHARE = {SHARED_FAMILY: " — shared with family", CARE: " — family who help with your health can see it", EMERGENCY: " — shown in emergencies"};
    (r.pending_memories || []).forEach(m => notes.push("Waiting for your yes: remember “" + m.normalized_fact + "”" + (m.replaces_id ? " (replaces an older memory)" : "") + (SHARE[m.visibility] || " — private")));
    (r.visibility_changes || []).forEach(v => notes.push("Waiting for your yes: change who sees memory #" + v.memory_id + " to " + ({PRIVATE: "private", SHARED_FAMILY: "family", CARE: "health helpers", EMERGENCY: "emergency"}[v.visibility] || v.visibility)));
    (r.forget_candidates || []).forEach(m => notes.push("Waiting for your yes: forget “" + m.normalized_fact + "”"));
    (r.reminder_suggestions || []).forEach(s => notes.push("Waiting for your yes: reminder “" + s.title + "” " +
      (s.repeat === "DAILY" ? "every day" : "on " + (s.date || "?")) + " at " + (s.time || "?") + (s.notes ? " (" + s.notes + ")" : "")));
    if ((r.reminders_to_cancel || []).length) notes.push("Waiting for your yes: remove reminder(s) " + r.reminders_to_cancel.map(x => "\u201c" + x.title + "\u201d").join(", "));
    (r.access_changes || []).forEach(a => {
      const parts = [["medicines","medicines"],["appointments","appointments"],["emergency","emergency contacts"],["shared_memories","shared memories"]]
        .filter(([k]) => a[k] === true).map(([, w]) => w);
      notes.push("Waiting for your yes: " + (a.action === "REVOKE" ? "remove all access for " + a.name
        : (a.action === "GRANT" ? "let " : "change what ") + a.name + (a.action === "GRANT" ? " see " : " sees: ") + (parts.length ? parts.join(", ") : "the usual (medicines, appointments, emergency contacts)")));
    });
    (r.suggested_people || []).forEach(p => notes.push((p.id ? "Will update " : "Will save ") + p.name + (p.relationship ? " as your " + p.relationship : "") +
      (p.person_type && !p.id ? " (" + p.person_type.toLowerCase() + ")" : "") +
      (p.phone ? ", phone " + p.phone : "") + (p.is_emergency_contact ? ", emergency contact" : "")));
    if (notes.length) add(notes.join("\n"), "info");
    $("#quick").style.display = r.waiting_for_yes_or_no ? "flex" : "none";
  } catch (e) { thinking.remove(); add(e.message, "err"); }
  checkAlerts();
}
$("#say").addEventListener("submit", e => { e.preventDefault(); const t = $("#msg").value; $("#msg").value = ""; send(t); });
$("#yes").addEventListener("click", () => send("yes"));
$("#no").addEventListener("click", () => send("no"));

// ---------- desktop pop-ups (no sound) ----------
const notified = new Set();
const canNotify = () => "Notification" in window;
function updateNotifButton() {
  $("#notif").style.display = canNotify() && Notification.permission === "default" && role ? "inline-block" : "none";
}
function askNotify() {
  if (canNotify() && Notification.permission === "default") Notification.requestPermission().then(updateNotifButton);
}
$("#notif").addEventListener("click", askNotify);
function popup(a) {
  if (!canNotify() || Notification.permission !== "granted" || notified.has(a.id)) return;
  notified.add(a.id);
  const n = new Notification("MemoryMate reminder: " + a.title, {
    body: a.when + (a.notes ? " \u00b7 " + a.notes : ""), tag: "mm-" + a.id, requireInteraction: true, silent: true});
  n.onclick = () => { window.focus(); n.close(); };
}

async function checkAlerts() {
  if (token && (role === "FAMILY" || role === "DOCTOR")) return checkFamilyAlerts();
  if (!token || role !== "ELDER") return;
  try { renderEmer(await api("/emergency/active")); } catch (e) {}
  try {
    const notes = await api("/memories/from-others").catch(() => []);
    $("#docnotes").innerHTML = notes.length ? `<div class="card"><h3>Notes from your doctor and family</h3>` + notes.map(n =>
      `<div class="sug"><span>${esc(n.text)} · <i>from ${esc(n.from_name)}</i></span>
       <button data-napprove="${n.id}">Accept</button><button class="light" data-nreject="${n.id}">Decline</button></div>`).join("") + `</div>` : "";
    const sug = await api("/reminders/suggestions");
    $("#suggestions").innerHTML = sug.length ? `<div class="card"><h3>Suggestions from family and doctors</h3>` + sug.map(r =>
      `<div class="sug"><span><b>${esc(r.title)}</b> · ${esc(r.due_local || r.next_alert_local || new Date(r.due_at).toLocaleString())}${r.suggested_by ? ` · <i>from ${esc(r.suggested_by)}</i>` : ""}</span>
       <button data-accept="${r.id}">Accept</button><button class="light" data-decline="${r.id}">Decline</button></div>`).join("") + `</div>` : "";
  } catch (e) {}
  try {
    const due = await api("/reminders/due");
    due.forEach(popup);
    $("#alerts").innerHTML = due.map(a => `<div class="alert"><span>⏰ <b>${esc(a.title)}</b> · ${esc(a.when)}${a.notes ? " · " + esc(a.notes) : ""}</span>
      <button class="light" data-done="${a.id}">Done</button><button class="light" data-snooze="${a.id}">In 10 min</button></div>`).join("");
  } catch (e) { /* not logged in or server restarting */ }
}
$("#docnotes").addEventListener("click", async e => {
  const a = e.target.dataset.napprove, d = e.target.dataset.nreject;
  try {
    if (a) { await api(`/memories/${a}/approve`, {method: "POST"}); add("Added to your memories.", "info"); }
    if (d) { await api(`/memories/${d}/reject`, {method: "POST"}); add("Declined.", "info"); }
  } catch (err) { add(err.message, "err"); }
  checkAlerts();
});
$("#suggestions").addEventListener("click", async e => {
  const a = e.target.dataset.accept, d = e.target.dataset.decline;
  try {
    if (a) { await api(`/reminders/${a}/accept`, {method: "POST"}); add("Accepted. That reminder will ring on time.", "info"); }
    if (d) { await api(`/reminders/${d}/decline`, {method: "POST"}); add("Declined.", "info"); }
  } catch (err) { add("Error: " + err.message, "err"); }
  checkAlerts();
});
$("#alerts").addEventListener("click", async e => {
  const done = e.target.dataset.done, snooze = e.target.dataset.snooze;
  if (done) await api(`/reminders/alerts/${done}/done`, {method: "POST"}).catch(() => {});
  if (snooze) await api(`/reminders/alerts/${snooze}/snooze?minutes=10`, {method: "POST"}).catch(() => {});
  checkAlerts();
});
// ---------- emergency (Help button) ----------
const telOf = p => "tel:" + String(p || "").replace(/[^0-9+]/g, "");
const callLinks = contacts => contacts.filter(p => p.phone).map(p =>
  `<a class="call" href="${telOf(p.phone)}">Call ${esc(p.name)}${p.relation_to_user ? " (" + esc(p.relation_to_user) + ")" : ""} · ${esc(p.phone)}</a>`).join(" ");
let sosTimer = null;
$("#sos").addEventListener("click", async () => {
  const b = $("#sos");
  if (!b.classList.contains("armed")) {          // first tap: ask to tap again, so it isn't pressed by mistake
    b.classList.add("armed"); b.textContent = "Tap again to alert family";
    sosTimer = setTimeout(() => { b.classList.remove("armed"); b.textContent = "Help (SOS)"; }, 5000);
    return;
  }
  clearTimeout(sosTimer); b.classList.remove("armed"); b.textContent = "Help (SOS)";
  try { renderEmer(await api("/emergency/sos", {method: "POST"})); add("Your family has been alerted.", "info"); }
  catch (e) { add("Couldn't send the alert: " + e.message + ". Please call someone directly.", "err"); }
});
function renderEmer(a) {
  if (!a || a.status !== "ACTIVE") { $("#emer").innerHTML = ""; return; }
  const c = callLinks(a.contacts);
  $("#emer").innerHTML = `<div class="emer" role="alert"><h3>Help is on the way</h3>
    <div>${a.notified.length ? "Alert sent to " + esc(a.notified.join(", ")) + " at " + esc(a.raised_at) + ". Stay where you are if you can."
      : "No family member or doctor is connected yet, so nobody got the alert. Please call someone now."}</div>
    <div class="row">${c || `<span class="muted">No emergency contacts saved yet. Tell me, e.g. "Rajesh is my emergency contact, 98765 43210".</span>`}
      <a class="call light" href="tel:108">Call 108 (Ambulance)</a></div>
    ${a.information.length ? `<div class="muted" style="margin-top:8px">Shown to helpers: ${esc(a.information.join(" · "))}</div>` : ""}
    <div class="row"><button class="light" data-safe="${a.id}">I'm safe now</button></div></div>`;
}
$("#emer").addEventListener("click", async e => {
  const id = e.target.dataset.safe; if (!id) return;
  try { await api(`/emergency/${id}/resolve`, {method: "POST"}); $("#emer").innerHTML = ""; add("Glad you're safe. I've told your family.", "info"); }
  catch (err) { add(err.message, "err"); }
});
function suggestHelp() {
  const d = document.createElement("div"); d.className = "m info";
  d.innerHTML = `Not feeling well? <button class="sos" data-sosnow="1">Alert my family now</button>`;
  $("#log").appendChild(d); $("#log").scrollTop = $("#log").scrollHeight;
}
$("#log").addEventListener("click", async e => {
  if (!e.target.dataset.sosnow) return;
  e.target.disabled = true;
  try { renderEmer(await api("/emergency/sos", {method: "POST"})); add("Your family has been alerted.", "info"); }
  catch (err) { e.target.disabled = false; add("Couldn't send the alert: " + err.message, "err"); }
});
// Elder: ask for their own phone number once, so family can call them in an emergency.
function phoneBox(phone) {
  $("#phonebox").innerHTML = phone ? "" : `<div class="card"><h3>Your phone number</h3>
    <p class="muted">Add it so your family and doctor can call you straight away in an emergency.</p>
    <form id="phonef" class="row"><label for="myphone" class="muted">Phone</label>
      <input id="myphone" type="tel" placeholder="e.g. 98765 43210" required autocomplete="tel"><button>Save</button></form></div>`;
}
$("#phonebox").addEventListener("submit", async e => {
  e.preventDefault();
  try {
    await api("/auth/me", {method: "PATCH", headers: {"Content-Type": "application/json"},
                           body: JSON.stringify({phone: $("#myphone").value.trim()})});
    phoneBox("saved"); add("Saved your phone number. Your family can now call you from their alert.", "info");
  } catch (err) { add("Couldn't save it: " + err.message + " (use digits, spaces or +).", "err"); }
});
// Family / doctor: a red banner for every open alert, plus a desktop pop-up (with sound) the first time.
const alerted = new Set();
async function checkFamilyAlerts() {
  if (!token || !(role === "FAMILY" || role === "DOCTOR")) return;
  checkMissed();
  let list = [];
  try { list = await api("/emergency/alerts"); } catch (e) { return; }
  $("#femer").innerHTML = list.map(a => `<div class="emer" role="alert"><h3>Emergency: ${esc(a.elder_name)} needs help</h3>
    <div>${a.source === "button" ? "Pressed the Help button" : "Said: \u201c" + esc(a.message || "") + "\u201d"} at ${esc(a.raised_at)}.</div>
    <div class="row">${a.elder_phone ? `<a class="call" href="${telOf(a.elder_phone)}">Call ${esc(a.elder_name)} · ${esc(a.elder_phone)}</a> ` : ""}<a class="call light" href="tel:108">Call 108 (Ambulance)</a></div>
    ${callLinks(a.contacts) ? `<div class="muted" style="margin-top:8px">Other emergency contacts:</div><div class="row" style="margin-top:4px">${callLinks(a.contacts)}</div>` : ""}
    ${a.information.length ? `<div class="muted" style="margin-top:8px">${esc(a.information.join(" · "))}</div>` : ""}
    <div class="row"><button class="light" data-handled="${a.id}">Mark as handled</button></div></div>`).join("");
  list.forEach(a => {
    if (alerted.has(a.id) || !canNotify() || Notification.permission !== "granted") return;
    alerted.add(a.id);
    const n = new Notification("EMERGENCY: " + a.elder_name + " needs help", {
      body: (a.source === "button" ? "Pressed the Help button" : a.message || "") + " \u00b7 " + a.raised_at,
      tag: "mm-sos-" + a.id, requireInteraction: true});
    n.onclick = () => { window.focus(); n.close(); };
  });
}
// Missed medicines: an orange banner and one pop-up per missed dose. "OK" hides it on this computer.
const store = {get: k => { try { return JSON.parse(localStorage.getItem(k) || "[]"); } catch (e) { return []; } },
               set: (k, v) => { try { localStorage.setItem(k, JSON.stringify(v.slice(-200))); } catch (e) {} }};
async function checkMissed() {
  let list = [];
  try { list = await api("/family/missed-medicines"); } catch (e) { return; }
  const hidden = store.get("mm_missed_ok"), popped = store.get("mm_missed_popped");
  const items = list.filter(m => !hidden.includes(m.id));
  $("#fmissed").innerHTML = items.length ? `<div class="missed" role="status"><h3>Missed medicine${items.length > 1 ? "s" : ""}</h3>` +
    items.map(m => `<div class="sug"><span><b>${esc(m.elder_name)}</b> didn't confirm <b>${esc(m.title)}</b> (due ${esc(m.when)})${m.notes ? " · " + esc(m.notes) : ""}</span>
      <button class="light" data-missok="${m.id}">OK, I'll check</button></div>`).join("") + `</div>` : "";
  items.forEach(m => {
    if (popped.includes(m.id) || !canNotify() || Notification.permission !== "granted") return;
    popped.push(m.id); store.set("mm_missed_popped", popped);
    const n = new Notification("Missed medicine: " + m.elder_name, {body: m.title + " \u00b7 due " + m.when, tag: "mm-miss-" + m.id, silent: true});
    n.onclick = () => { window.focus(); n.close(); };
  });
}
$("#fmissed").addEventListener("click", e => {
  const id = Number(e.target.dataset.missok); if (!id) return;
  const hidden = store.get("mm_missed_ok"); hidden.push(id); store.set("mm_missed_ok", hidden); checkMissed();
});
$("#femer").addEventListener("click", async e => {
  const id = e.target.dataset.handled; if (!id) return;
  try { await api(`/emergency/${id}/resolve`, {method: "POST"}); } catch (err) {}
  checkFamilyAlerts();
});

// ---------- family view ----------
// The link stores YOUR relation to them ("daughter"); show THEIR role for you, gender-neutral.
const ROLE = [
  [/\b(daughter-in-law|son-in-law)\b/, "Your parent-in-law"],
  [/\b(daughter|son|child|kid)\b/, "Your parent"],
  [/\b(granddaughter|grandson|grandchild)\b/, "Your grandparent"],
  [/\b(wife|husband|spouse|partner)\b/, "Your spouse"],
  [/\b(sister|brother|sibling)\b/, "Your sibling"],
  [/\b(niece|nephew)\b/, "Your aunt or uncle"],
  [/\b(doctor|physician|nurse)\b/, "Your patient"],
  [/\b(caregiver|carer|attendant)\b/, "In your care"],
  [/\b(friend)\b/, "Your friend"],
  [/\b(neighbou?r)\b/, "Your neighbour"],
];
const roleFor = rel => { const r = (rel || "").toLowerCase(); for (const [re, label] of ROLE) if (re.test(r)) return label; return "Family"; };
let elderLinks = [];

async function loadElders() {
  const links = await api("/family/my-elders").catch(() => []);
  elderLinks = links;
  // Linked as a doctor (to anyone)? Then the people you see are your patients.
  const asDoctor = role === "DOCTOR" || links.some(l => /doctor|nurse|physician/i.test(l.relation || ""));
  if (links.length) {
    $("#elderlabel").textContent = asDoctor ? "Patient:" : "Relative:";
    $("#codetitle").textContent = asDoctor ? "Got a code from a patient?" : "Got a code from a relative?";
  }
  $("#elder").innerHTML = links.map(l => `<option value="${l.elder_id}">${esc(l.elder_name)} · ${roleFor(l.relation)}</option>`).join("");
  if (!links.length) { $("#dash").innerHTML = `<div class="card">You're not connected to anyone yet. Ask your relative to tell MemoryMate "let [your name] see my information", then enter the code they give you below.</div>`; return; }
  const t = new Date(); // local date, not UTC
  loadOverview();
  $("#sd").value = `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, "0")}-${String(t.getDate()).padStart(2, "0")}`;
  loadDash();
}
// Overview: everyone you look after on one screen, most urgent first. "Open" shows their full dashboard below.
async function loadOverview() {
  let rows = [];
  try { rows = await api("/family/overview"); } catch (e) { return; }
  if (!rows.length) { $("#overview").innerHTML = ""; return; }
  const asDoctor = role === "DOCTOR" || rows.some(r => /doctor|nurse|physician/i.test(r.relation || ""));
  const tag = {emergency: "\u{1F6A8} Needs help now", attention: "\u26A0\uFE0F Missed medicine", ok: "\u2705 All good"};
  $("#overview").innerHTML = `<div class="card"><h3>${asDoctor ? "My patients" : "My family"} at a glance</h3>
    <p class="muted">Most urgent first. Updates every minute.</p><div class="grid">` + rows.map(r => `
    <div class="ov ${r.status}"><b class="name">${esc(r.elder_name)}</b>
      <span class="muted">${roleFor(r.relation)}</span>
      <span class="tag">${tag[r.status]}${r.emergency_since ? " · since " + esc(r.emergency_since.split(", ").pop()) : ""}</span>
      ${r.medicines_total === null ? "" : `<span>Medicines today: ${r.medicines_taken}/${r.medicines_total} taken${r.medicines_missed ? `, <b style="color:#c8102e">${r.medicines_missed} missed</b>` : ""}</span>`}
      ${r.next_appointment ? `<span>Next: ${esc(r.next_appointment)}, ${esc(r.next_appointment_when)}</span>` : ""}
      ${r.my_suggestions_waiting ? `<span class="muted">${r.my_suggestions_waiting} of your suggestion${r.my_suggestions_waiting > 1 ? "s" : ""} waiting for an answer</span>` : ""}
      <div class="row"><button class="light" data-open="${r.elder_id}">Open</button>${r.elder_phone ? `<a class="call${r.status === "emergency" ? "" : " light"}" href="${telOf(r.elder_phone)}">Call</a>` : ""}</div>
    </div>`).join("") + `</div></div>`;
}
$("#overview").addEventListener("click", e => {
  const id = e.target.dataset.open; if (!id) return;
  $("#elder").value = id; loadDash(); $("#dash").scrollIntoView({behavior: "smooth"});
});
const list = (items, f) => items.length ? "<ul>" + items.map(f).join("") + "</ul>" : `<p class="muted">Nothing here.</p>`;
const word = s => ({DONE: "✅ taken / done", MISSED: "❌ missed", DUE: "⏰ ringing now", SCHEDULED: "later today", SKIPPED: "cancelled"}[s] || s);
async function loadDash() {
  const id = $("#elder").value; if (!id) return;
  try {
    const d = await api(`/family/elders/${id}/dashboard`);
    let h = `<div class="card"><h3>${esc(d.elder_name)} · ${roleFor(d.relation)}</h3><p class="muted">As of ${esc(d.as_of)} (updates every minute). Only what ${esc(d.elder_name)} chose to share is shown. Each view is logged for them.</p>${d.elder_phone ? `<a class="call light" href="${telOf(d.elder_phone)}">Call ${esc(d.elder_name)} · ${esc(d.elder_phone)}</a>` : ""}</div>`;
    if (d.medicines_today) h += `<div class="card"><h3>Medicines today${d.missed_medicines_today ? ` · <span style="color:#c8102e">${d.missed_medicines_today} missed</span>` : ""}</h3>` +
      list(d.medicines_today, m => `<li>${esc(m.title)} at ${esc(m.when.split(", ").pop())}: ${word(m.status)}</li>`) + `</div>`;
    if (d.upcoming_appointments) h += `<div class="card"><h3>Upcoming appointments and tasks</h3>` +
      list(d.upcoming_appointments, a => `<li><b>${esc(a.when)}</b>: ${esc(a.title)}</li>`) + `</div>`;
    if (d.health_notes && d.health_notes.length) h += `<div class="card"><h3>Health notes</h3>` +
      list(d.health_notes, m => `<li>${esc(m.fact)}</li>`) + `</div>`;
    if (d.shared_memories) h += `<div class="card"><h3>Shared memories</h3>` +
      list(d.shared_memories, m => `<li>${esc(m.fact)} <span class="muted">(${esc(m.told_on)})</span></li>`) + `</div>`;
    if (d.emergency) h += `<div class="card"><h3>Emergency</h3>` +
      list(d.emergency.contacts, p => `<li>${esc(p.name)} (${esc(p.relation_to_user || "")}): ${esc(p.phone || "no number saved")}</li>`) +
      (d.emergency.information.length ? list(d.emergency.information, t => `<li>${esc(t)}</li>`) : "") + `</div>`;
    if (d.hidden_sections.length) h += `<div class="card muted">Not shared with you: ${esc(d.hidden_sections.join(", "))}.</div>`;
    $("#dash").innerHTML = h;
  } catch (e) { $("#dash").innerHTML = `<div class="card m err">Error: ${esc(e.message)}</div>`; }
}
$("#joinf").addEventListener("submit", async e => {
  e.preventDefault();
  try {
    const l = await api("/family/join", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({code: $("#jcode").value.trim().toUpperCase()})});
    $("#jmsg").textContent = "Connected to " + l.elder_name + "."; $("#jcode").value = ""; loadElders();
  } catch (err) { $("#jmsg").textContent = err.message; }
});
$("#notef").addEventListener("submit", async e => {
  e.preventDefault();
  try {
    await api(`/family/elders/${$("#elder").value}/notes`, {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({text: $("#ntext").value})});
    $("#nmsg").textContent = "Sent. It's added once your patient accepts it."; $("#ntext").value = "";
  } catch (err) { $("#nmsg").textContent = "Couldn't send it: " + err.message; }
});
$("#elder").addEventListener("change", loadDash);
$("#refresh").addEventListener("click", () => { loadDash(); loadOverview(); });
$("#sugf").addEventListener("submit", async e => {
  e.preventDefault();
  try {
    await api(`/family/elders/${$("#elder").value}/reminders`, {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({title: $("#st").value, kind: $("#sk").value, date: $("#sd").value, time: $("#sti").value,
                            repeat: $("#srep").value, notes: $("#snotes").value || null})});
    $("#sugmsg").textContent = "Suggested. It will ring once they accept it."; $("#st").value = "";
  } catch (err) { $("#sugmsg").textContent = "Couldn't suggest it: " + err.message; }
});

// Check for ringing reminders every 20 s from a worker: Chrome slows or pauses normal timers in background
// tabs, but much less so in workers. Also check the moment the tab or window comes back into view.
try {
  const ticker = new Worker(URL.createObjectURL(new Blob(["setInterval(() => postMessage(1), 20000);"],
                                                         {type: "text/javascript"})));
  ticker.onmessage = () => checkAlerts();
} catch (e) { setInterval(checkAlerts, 20000); }
document.addEventListener("visibilitychange", () => { if (!document.hidden) checkAlerts(); });
window.addEventListener("focus", checkAlerts);
// Family / doctor dashboard: refresh every minute so "taken" and "missed" show up by themselves.
setInterval(() => { if (token && (role === "FAMILY" || role === "DOCTOR") && $("#elder").value) { loadDash(); loadOverview(); } }, 60000);
if (token) start(); else show(false);
}
</script></body></html>"""


@router.get("/test", response_class=HTMLResponse, include_in_schema=False)
def test_page():
    return PAGE
