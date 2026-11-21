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
</style></head><body>
<header><b>MemoryMate · test page</b><span id="who"></span><button class="light" id="out" style="display:none">Log out</button></header>
<main>
  <form id="login"><div>Log in to start (same accounts as /docs). Elder accounts get the chat, family accounts get the dashboard.</div>
    <input id="email" placeholder="Email" value="vivek@example.com" autocomplete="username">
    <input id="pw" type="password" placeholder="Password" autocomplete="current-password">
    <button>Log in</button><div id="lerr" class="m err" style="display:none"></div></form>
  <div id="family" style="display:none">
    <div class="row" style="margin-bottom:12px"><label for="elder">Relative:</label><select id="elder" style="font:inherit;padding:8px;border-radius:10px"></select>
      <button class="light" id="refresh">Refresh</button></div>
    <div id="dash"></div>
    <div class="card"><h3>Suggest a reminder</h3>
      <p class="muted">It only starts ringing after your relative accepts it.</p>
      <form id="sugf" class="row">
        <input id="st" placeholder="What, e.g. Call Priya" required>
        <select id="sk" style="font:inherit;padding:10px;border-radius:12px"><option value="CALL">Call</option><option value="MEDICINE">Medicine</option><option value="APPOINTMENT">Appointment</option><option value="TASK">Task</option><option value="BIRTHDAY">Birthday</option></select>
        <input id="sd" type="date" required><input id="sti" type="time" value="18:00" required>
        <button>Suggest</button></form>
      <div id="sugmsg" class="muted"></div></div>
  </div>
  <div id="app" style="display:none">
    <div id="alerts"></div>
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
  $("#app").style.display = loggedIn && role === "ELDER" ? "block" : "none";
  $("#family").style.display = loggedIn && role === "FAMILY" ? "block" : "none";
  $("#out").style.display = loggedIn ? "inline-block" : "none";
}
function logout() { token = ""; role = ""; sessionStorage.removeItem("mm_token"); show(false); }

$("#login").addEventListener("submit", async e => {
  e.preventDefault(); $("#lerr").style.display = "none";
  const form = new URLSearchParams({username: $("#email").value, password: $("#pw").value});
  const r = await fetch("/auth/login", {method: "POST", body: form});
  if (!r.ok) { $("#lerr").textContent = "Wrong email or password."; $("#lerr").style.display = "block"; return; }
  token = (await r.json()).access_token; sessionStorage.setItem("mm_token", token); start();
});
$("#out").addEventListener("click", logout);

async function start() {
  try {
    const me = await api("/auth/me");
    role = me.role;
    $("#who").textContent = me.name + " (" + me.role.toLowerCase() + ")";
    show(true);
    if (role === "FAMILY") { loadElders(); return; }
    $("#log").innerHTML = ""; add("Hello " + me.name + ". Tell me something, or ask me anything you've told me.");
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
    const notes = [];
    (r.pending_memories || []).forEach(m => notes.push("Waiting for your yes: remember “" + m.normalized_fact + "”" + (m.replaces_id ? " (replaces an older memory)" : "")));
    (r.forget_candidates || []).forEach(m => notes.push("Waiting for your yes: forget “" + m.normalized_fact + "”"));
    if (r.reminder_suggestion) { const s = r.reminder_suggestion; notes.push("Waiting for your yes: reminder “" + s.title + "” on " + (s.date || "?") + " at " + (s.time || "?")); }
    (r.suggested_people || []).forEach(p => notes.push("Will also add " + p.name + (p.relationship ? " (" + p.relationship + ")" : "") + " to your people"));
    if (notes.length) add(notes.join("\n"), "info");
    $("#quick").style.display = r.waiting_for_yes_or_no ? "flex" : "none";
  } catch (e) { thinking.remove(); add("Error: " + e.message, "err"); }
  checkAlerts();
}
$("#say").addEventListener("submit", e => { e.preventDefault(); const t = $("#msg").value; $("#msg").value = ""; send(t); });
$("#yes").addEventListener("click", () => send("yes"));
$("#no").addEventListener("click", () => send("no"));

async function checkAlerts() {
  if (!token || role !== "ELDER") return;
  try {
    const sug = await api("/reminders/suggestions");
    $("#suggestions").innerHTML = sug.length ? `<div class="card"><h3>Suggestions from family</h3>` + sug.map(r =>
      `<div class="sug"><span><b>${esc(r.title)}</b> · ${esc(r.next_alert_local || new Date(r.due_at).toLocaleString())}</span>
       <button data-accept="${r.id}">Accept</button><button class="light" data-decline="${r.id}">Decline</button></div>`).join("") + `</div>` : "";
  } catch (e) {}
  try {
    const due = await api("/reminders/due");
    $("#alerts").innerHTML = due.map(a => `<div class="alert"><span>⏰ <b>${esc(a.title)}</b> · ${esc(a.when)}${a.notes ? " · " + esc(a.notes) : ""}</span>
      <button class="light" data-done="${a.id}">Done</button><button class="light" data-snooze="${a.id}">In 10 min</button></div>`).join("");
  } catch (e) { /* not logged in or server restarting */ }
}
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
// ---------- family view ----------
async function loadElders() {
  const links = await api("/family/my-elders").catch(() => []);
  $("#elder").innerHTML = links.map(l => `<option value="${l.elder_id}">${esc(l.elder_name)} (your ${esc(l.relation)})</option>`).join("");
  if (!links.length) { $("#dash").innerHTML = `<div class="card">No one has linked you yet. Ask your relative to add you (POST /family/links with your email).</div>`; return; }
  const t = new Date(); // local date, not UTC
  $("#sd").value = `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, "0")}-${String(t.getDate()).padStart(2, "0")}`;
  loadDash();
}
const list = (items, f) => items.length ? "<ul>" + items.map(f).join("") + "</ul>" : `<p class="muted">Nothing here.</p>`;
const word = s => ({DONE: "✅ taken / done", MISSED: "❌ missed", DUE: "⏰ ringing now", SCHEDULED: "later today", SKIPPED: "cancelled"}[s] || s);
async function loadDash() {
  const id = $("#elder").value; if (!id) return;
  try {
    const d = await api(`/family/elders/${id}/dashboard`);
    let h = `<div class="card"><h3>${esc(d.elder_name)}</h3><p class="muted">As of ${esc(d.as_of)}. Only what ${esc(d.elder_name)} chose to share is shown. Each view is logged for them.</p></div>`;
    if (d.medicines_today) h += `<div class="card"><h3>Medicines today${d.missed_medicines_today ? ` · <span style="color:#c8102e">${d.missed_medicines_today} missed</span>` : ""}</h3>` +
      list(d.medicines_today, m => `<li>${esc(m.title)} at ${esc(m.when.split(", ").pop())}: ${word(m.status)}</li>`) + `</div>`;
    if (d.upcoming_appointments) h += `<div class="card"><h3>Upcoming appointments</h3>` +
      list(d.upcoming_appointments, a => `<li><b>${esc(a.when)}</b>: ${esc(a.title)}</li>`) + `</div>`;
    if (d.shared_memories) h += `<div class="card"><h3>Shared memories</h3>` +
      list(d.shared_memories, m => `<li>${esc(m.fact)} <span class="muted">(${esc(m.told_on)})</span></li>`) + `</div>`;
    if (d.emergency) h += `<div class="card"><h3>Emergency</h3>` +
      list(d.emergency.contacts, p => `<li>${esc(p.name)} (${esc(p.relation_to_user || "")}): ${esc(p.phone || "no number saved")}</li>`) +
      (d.emergency.information.length ? list(d.emergency.information, t => `<li>${esc(t)}</li>`) : "") + `</div>`;
    if (d.hidden_sections.length) h += `<div class="card muted">Not shared with you: ${esc(d.hidden_sections.join(", "))}.</div>`;
    $("#dash").innerHTML = h;
  } catch (e) { $("#dash").innerHTML = `<div class="card m err">Error: ${esc(e.message)}</div>`; }
}
$("#elder").addEventListener("change", loadDash);
$("#refresh").addEventListener("click", loadDash);
$("#sugf").addEventListener("submit", async e => {
  e.preventDefault();
  try {
    await api(`/family/elders/${$("#elder").value}/reminders`, {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({title: $("#st").value, kind: $("#sk").value, date: $("#sd").value, time: $("#sti").value})});
    $("#sugmsg").textContent = "Suggested. It will ring once they accept it."; $("#st").value = "";
  } catch (err) { $("#sugmsg").textContent = "Couldn't suggest it: " + err.message; }
});

setInterval(checkAlerts, 30000);
if (token) start(); else show(false);
}
</script></body></html>"""


@router.get("/test", response_class=HTMLResponse, include_in_schema=False)
def test_page():
    return PAGE
