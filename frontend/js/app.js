// AI-Powered Industrial Academy — front-end client
const API = "/api";

const state = {
  token: localStorage.getItem("academy_token") || null,
  user: null,
  projects: [],
  currentProject: null,
  chatHistory: [],
  chatLevel: 1,
  currentFault: null,
  faults: [],
};

// ---------- helpers ----------
function $(sel) { return document.querySelector(sel); }
function $all(sel) { return Array.from(document.querySelectorAll(sel)); }
function el(tag, cls, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  return e;
}
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function api(path, { method = "GET", body, form, auth = true } = {}) {
  const headers = {};
  if (auth && state.token) headers["Authorization"] = "Bearer " + state.token;
  let payload;
  if (form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    payload = new URLSearchParams(form).toString();
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const res = await fetch(API + path, { method, headers, body: payload });
  if (res.status === 401) { logout(); throw new Error("Session expired. Sign in again."); }
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) throw new Error((data && (data.detail || data.message)) || "Request failed");
  return data;
}

// ---------- simple markdown renderer ----------
function renderMarkdown(md) {
  const lines = String(md || "").split("\n");
  let html = "", inTable = false, inList = false;
  const flushList = () => { if (inList) { html += "</ul>"; inList = false; } };
  const flushTable = () => { if (inTable) { html += "</tbody></table>"; inTable = false; } };
  for (let raw of lines) {
    const line = raw.trimEnd();
    if (/^\|(.+)\|$/.test(line)) {
      const cells = line.slice(1, -1).split("|").map((c) => c.trim());
      if (/^[-: ]+$/.test(cells.join(""))) continue;
      if (!inTable) { html += "<table><thead><tr>" + cells.map((c) => `<th>${esc(c)}</th>`).join("") + "</tr></thead><tbody>"; inTable = true; }
      else html += "<tr>" + cells.map((c) => `<td>${esc(c)}</td>`).join("") + "</tr>";
      continue;
    }
    flushTable();
    if (/^#{1,6}\s+/.test(line)) {
      flushList();
      const level = line.match(/^#+/)[0].length;
      html += `<h${Math.min(level + 1, 6)}>${esc(line.replace(/^#+\s+/, ""))}</h${Math.min(level + 1, 6)}>`;
    } else if (/^[-*]\s+/.test(line)) {
      if (!inList) { html += "<ul>"; inList = true; }
      html += `<li>${esc(line.replace(/^[-*]\s+/, ""))}</li>`;
    } else if (line.trim() === "") {
      flushList();
    } else {
      flushList();
      html += `<p>${esc(line)}</p>`;
    }
  }
  flushList(); flushTable();
  return html;
}

// ---------- device fingerprint ----------
function deviceFingerprint() {
  let fp = localStorage.getItem("academy_device_fp");
  if (!fp) {
    const seed = navigator.userAgent + "|" + screen.width + "x" + screen.height + "|" + Date.now();
    fp = "fp_" + btoa(seed).replace(/[^a-z0-9]/gi, "").slice(0, 40);
    localStorage.setItem("academy_device_fp", fp);
  }
  return fp;
}

// ---------- auth ----------
async function login(email, password) {
  const data = await api("/auth/token", { method: "POST", form: { username: email, password }, auth: false });
  state.token = data.access_token;
  localStorage.setItem("academy_token", state.token);
  await boot();
}
async function register(payload) {
  await api("/auth/register", { method: "POST", body: payload, auth: false });
  await login(payload.email, payload.password);
}
function logout() {
  state.token = null; state.user = null;
  localStorage.removeItem("academy_token");
  $("#app").classList.add("hidden");
  $("#auth-screen").classList.remove("hidden");
}

// ---------- boot ----------
async function boot() {
  if (!state.token) { $("#auth-screen").classList.remove("hidden"); return; }
  try {
    state.user = await api("/auth/me");
  } catch { logout(); return; }
  $("#auth-screen").classList.add("hidden");
  $("#app").classList.remove("hidden");
  $("#user-chip").innerHTML = `<div>${esc(state.user.full_name)}</div><div class="email">${esc(state.user.email)}</div>`;
  await loadProjects();
  await authorizeThisDevice();
  showTab("projects");
}

async function authorizeThisDevice() {
  const fp = deviceFingerprint();
  $("#device-self").innerHTML = `<div class="title">Fingerprint</div><div class="sub">${esc(fp)}</div>`;
  try {
    await api("/devices/authorize", {
      method: "POST",
      body: { device_fingerprint: fp, device_label: "Browser client", platform: navigator.platform || "web" },
    });
  } catch (e) { console.warn("device authorize:", e.message); }
}

// ---------- tabs ----------
function showTab(tab) {
  $all(".view").forEach((v) => v.classList.add("hidden"));
  $("#view-" + tab).classList.remove("hidden");
  $all(".nav-item").forEach((n) => n.classList.toggle("active", n.dataset.tab === tab));
  const loaders = { dashboard: loadDashboard, credentials: loadCredentials, devices: loadDevices, faultlab: openFaultLab, mentor: initMentorContext };
  if (loaders[tab]) loaders[tab]();
}

// ---------- projects ----------
async function loadProjects() {
  state.projects = await api("/projects");
  const list = $("#projects-list");
  list.innerHTML = "";
  if (!state.projects.length) { list.innerHTML = "<p class='muted'>No projects published yet.</p>"; return; }
  for (const p of state.projects) {
    const card = el("div", "project-card");
    card.innerHTML = `<div class="title">${esc(p.title)}</div><div class="desc">${esc(p.description)}</div>
      <div class="chips"><span class="chip industry">${esc(p.industry)}</span><span class="chip">${esc(p.difficulty)}</span><span class="chip">${p.hours} h</span></div>`;
    card.onclick = () => openProject(p.id);
    list.appendChild(card);
  }
}
async function openProject(id) {
  const project = await api("/projects/" + id);
  state.currentProject = project;
  $("#projects-list").classList.add("hidden");
  $("#project-detail").classList.remove("hidden");
  $("#pd-title").textContent = project.title;
  $("#pd-meta").textContent = `${project.industry} · ${project.difficulty} · ${project.hours} h · 17-section lifecycle`;

  let progress = null;
  try { progress = await api(`/projects/${id}/progress`); } catch { /* not signed in edge */ }
  const doneKeys = new Set((progress?.sections || []).filter((s) => s.status === "completed").map((s) => s.section_key));
  $("#pd-progress").innerHTML = progress
    ? `<div class="progress-strip"><div style="width:${progress.percent}%"></div></div><div class="muted">${progress.completed_sections} / ${progress.total_sections} sections completed (${progress.percent.toFixed(0)}%)</div>`
    : "";

  const nav = $("#pd-sections");
  nav.innerHTML = "";
  project.sections.forEach((s, i) => {
    const b = el("button", doneKeys.has(s.key) ? "done" : "");
    b.textContent = `${i + 1}. ${s.title}`;
    b.onclick = () => {
      $all("#pd-sections button").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      showSection(s);
    };
    nav.appendChild(b);
  });
  if (project.sections.length) { nav.children[0].click(); }
}
function showSection(section) {
  $("#pd-section-title").textContent = section.title;
  $("#pd-section-body").innerHTML = renderMarkdown(section.content);
}
$("#project-back").onclick = () => {
  $("#project-detail").classList.add("hidden");
  $("#projects-list").classList.remove("hidden");
};

// ---------- dashboard ----------
async function loadDashboard() {
  let rows = [];
  try { rows = await api("/progress"); } catch { /* ignore */ }
  const grid = $("#dash-grid");
  grid.innerHTML = "";
  const byProject = {};
  rows.forEach((r) => { (byProject[r.project_id] = byProject[r.project_id] || []).push(r); });

  if (!state.projects.length) { grid.innerHTML = "<p class='muted'>No projects yet.</p>"; return; }
  for (const p of state.projects) {
    const proj = byProject[p.id] || [];
    const done = proj.filter((r) => r.status === "completed").length;
    const total = 17;
    const pct = Math.round((done / total) * 100);
    const div = el("div", "progress-ring");
    div.innerHTML = `<div class="ring" style="--p:${pct}%"><div>${pct}%</div></div><div class="ring-label">${esc(p.title)}</div>`;
    grid.appendChild(div);
  }
  const list = $("#dash-project-list");
  list.innerHTML = "";
  rows.slice().sort((a, b) => (b.updated_at || "").localeCompare(a.updated_at || "")).slice(0, 8).forEach((r) => {
    const p = state.projects.find((x) => x.id === r.project_id);
    list.appendChild(el("div", "panel-item",
      `<div class="title">${esc(p ? p.title : "Project " + r.project_id)} — ${esc(r.section_key.replace(/_/g, " "))}</div>
       <div class="sub">${esc(r.status)} · score ${r.score} · updated ${esc((r.updated_at || "").slice(0, 16).replace("T", " "))}</div>`));
  });
  if (!rows.length) list.innerHTML = "<p class='muted'>No progress recorded yet. Open a project to begin.</p>";
}

// ---------- mentor ----------
function initMentorContext() {
  const sel = $("#chat-context");
  sel.innerHTML = `<option value="">General / project brief</option>`;
  if (state.currentProject) {
    state.currentProject.sections.forEach((s) => {
      const o = document.createElement("option");
      o.value = s.key; o.textContent = s.title;
      sel.appendChild(o);
    });
  }
  renderLevelPicker();
}
function renderLevelPicker() {
  const picker = $("#level-picker");
  picker.innerHTML = "";
  for (let i = 1; i <= 5; i++) {
    const b = el("button", i === state.chatLevel ? "active" : "");
    b.textContent = i;
    b.onclick = () => { state.chatLevel = i; renderLevelPicker(); };
    picker.appendChild(b);
  }
}
function addMsg(role, text, mode, level) {
  const m = el("div", `msg ${role} ${mode || ""}`);
  const tag = role === "mentor" ? `MENTOR · ${String(mode || "socratic").toUpperCase()}` + (level ? ` · L${level}` : "") : "YOU";
  m.innerHTML = `<span class="tag">${esc(tag)}</span>${esc(text)}`;
  $("#chat-window").appendChild(m);
  $("#chat-window").scrollTop = $("#chat-window").scrollHeight;
}
async function sendChat() {
  const input = $("#chat-input");
  const message = input.value.trim();
  if (!message) return;
  input.value = "";
  addMsg("user", message, "", null);
  try {
    const res = await api("/mentor/chat", {
      method: "POST",
      body: {
        message,
        project_id: state.currentProject ? state.currentProject.id : null,
        section_key: $("#chat-context").value || null,
        history: [{ role: "user", level: state.chatLevel }],
      },
    });
    addMsg("mentor", res.reply, res.mode, res.level);
  } catch (e) { addMsg("mentor", "Error: " + e.message, "guided", 1); }
}
async function requestSolution() {
  const message = $("#chat-input").value.trim() || "Show me the full solution with reasoning for this section.";
  addMsg("user", "[solution request] " + message, "", null);
  try {
    const res = await api("/mentor/solution", {
      method: "POST",
      body: {
        message,
        project_id: state.currentProject ? state.currentProject.id : null,
        section_key: $("#chat-context").value || null,
        history: [{ role: "user", level: state.chatLevel }],
      },
    });
    addMsg("mentor", res.reply, res.mode, res.level);
  } catch (e) { addMsg("mentor", "Error: " + e.message, "guided", 1); }
}

// ---------- fault lab ----------
async function openFaultLab() {
  const pid = state.currentProject ? state.currentProject.id : (state.projects[0] && state.projects[0].id);
  if (!pid) { $("#fault-select").innerHTML = "<p class='muted'>Open a project first.</p>"; return; }
  state.faults = await api(`/projects/${pid}/faults`);
  $("#fault-run").classList.add("hidden");
  const list = $("#fault-select");
  list.classList.remove("hidden");
  list.innerHTML = "";
  state.faults.forEach((f) => {
    const item = el("div", "panel-item");
    item.innerHTML = `<div class="title">${esc(f.title)}</div><div class="sub">${esc(f.symptom)}</div>
      <div class="chips"><span class="chip">difficulty ${f.difficulty}</span></div>`;
    item.style.cursor = "pointer";
    item.onclick = () => openFault(f);
    list.appendChild(item);
  });
}
async function openFault(f) {
  state.currentFault = f;
  $("#fault-select").classList.add("hidden");
  $("#fault-run").classList.remove("hidden");
  $("#fault-title").textContent = f.title;
  const detail = await api(`/projects/${state.currentProject.id}/faults/${f.id}`);
  $("#fault-symptom").textContent = detail.symptom;
  $("#fault-result").innerHTML = "";
  $("#fault-diagnosis").value = "";
  const checks = $("#fault-checks");
  checks.innerHTML = "";
  (detail.available_checks || []).forEach((c) => {
    const row = el("div", "check-row");
    row.innerHTML = `<input type="checkbox" id="chk-${esc(c)}" /><label for="chk-${esc(c)}">${esc(c.replace(/_/g, " "))}</label>`;
    checks.appendChild(row);
  });
}
async function submitDiagnosis() {
  const performed = $all("#fault-checks input").filter((c) => c.checked).map((c) => c.id.replace("chk-", ""));
  const diagnosis = $("#fault-diagnosis").value.trim();
  try {
    const res = await api("/fault/diagnose", {
      method: "POST",
      body: { fault_id: state.currentFault.id, checks: performed.map((c) => ({ check_id: c, performed: true })), diagnosis },
    });
    const box = $("#fault-result");
    box.className = "fault-result " + (res.correct ? "pass" : "fail");
    box.innerHTML = `<div><strong>${res.correct ? "Diagnosis correct" : "Not quite"}</strong> — score ${(res.score * 100).toFixed(0)}%</div>
      <div class="sub">Checks: ${res.checks_correct}/${res.checks_total} correct · expected: ${esc(res.correct_diagnosis)}</div>
      <ul>${res.feedback.map((f) => `<li>${esc(f)}</li>`).join("")}</ul>
      ${res.recommended_step ? `<div class="muted">${esc(res.recommended_step)}</div>` : ""}`;
  } catch (e) {
    $("#fault-result").className = "fault-result fail";
    $("#fault-result").textContent = "Error: " + e.message;
  }
}
$("#fault-back").onclick = () => { $("#fault-run").classList.add("hidden"); $("#fault-select").classList.remove("hidden"); };
$("#fault-help").onclick = () => { showTab("mentor"); };

// ---------- credentials ----------
async function loadCredentials() {
  const certs = await api("/credentials/certificates");
  const port = await api("/credentials/portfolio");
  const cl = $("#certificates-list"); cl.innerHTML = "";
  if (!certs.length) cl.innerHTML = "<p class='muted'>No certificates yet — complete all 17 sections of a project.</p>";
  certs.forEach((c) => cl.appendChild(el("div", "panel-item",
    `<div class="title">${esc(c.certificate_ref)}</div><div class="sub">Project ${c.project_id} · issued ${esc(c.issued_at.slice(0, 10))} · verify token ${esc(c.verification_token.slice(0, 12))}…</div>`)));
  const pl = $("#portfolio-list"); pl.innerHTML = "";
  if (!port.length) pl.innerHTML = "<p class='muted'>No portfolio entries yet.</p>";
  port.forEach((p) => pl.appendChild(el("div", "panel-item",
    `<div class="title">${esc(p.title)}</div><div class="sub">${esc(p.summary)}</div>`)));
}

// ---------- devices ----------
async function loadDevices() {
  const devices = await api("/devices");
  const list = $("#devices-list"); list.innerHTML = "";
  if (!devices.length) list.innerHTML = "<p class='muted'>No devices authorized.</p>";
  devices.forEach((d) => {
    const item = el("div", "panel-item");
    item.innerHTML = `<div class="title">${esc(d.device_label)} ${d.is_authorized ? "" : "(revoked)"}</div>
      <div class="sub">${esc(d.device_fingerprint.slice(0, 22))}… · last seen ${d.last_seen ? esc(d.last_seen.slice(0, 16).replace("T", " ")) : "never"}</div>`;
    if (d.is_authorized) {
      const btn = el("button", "btn btn-ghost"); btn.textContent = "Revoke"; btn.style.marginTop = "8px";
      btn.onclick = async () => { await api("/devices/revoke", { method: "POST", body: { device_id: d.id } }); loadDevices(); };
      item.appendChild(btn);
    }
    list.appendChild(item);
  });
}
async function syncNow() {
  const fp = deviceFingerprint();
  const out = $("#sync-out");
  out.textContent = "Syncing…";
  try {
    const res = await api("/sync", { method: "POST", body: { device_fingerprint: fp, changes: [] } });
    out.textContent = `Sync complete. Applied ${res.applied.length}, conflicts ${res.conflicts.length}, server rows ${res.server_state.length}.`;
  } catch (e) { out.textContent = "Sync failed: " + e.message; }
}

// ---------- wire events ----------
$("#login-form").onsubmit = async (e) => {
  e.preventDefault(); $("#auth-error").textContent = "";
  try { await login($("#login-email").value, $("#login-password").value); }
  catch (err) { $("#auth-error").textContent = err.message; }
};
$("#register-form").onsubmit = async (e) => {
  e.preventDefault(); $("#auth-error").textContent = "";
  try {
    await register({ email: $("#reg-email").value, full_name: $("#reg-name").value, password: $("#reg-password").value, institution: $("#reg-institution").value || null });
  } catch (err) { $("#auth-error").textContent = err.message; }
};
$all("#auth-tabs .tab-mini").forEach((t) => t.onclick = () => {
  $all("#auth-tabs .tab-mini").forEach((x) => x.classList.remove("active"));
  t.classList.add("active");
  $("#login-form").classList.toggle("hidden", t.dataset.target !== "login");
  $("#register-form").classList.toggle("hidden", t.dataset.target !== "register");
});
$("#logout-btn").onclick = logout;
$all(".nav-item").forEach((n) => n.onclick = () => showTab(n.dataset.tab));
$("#chat-send").onclick = sendChat;
$("#chat-solution").onclick = requestSolution;
$("#chat-input").onkeydown = (e) => { if (e.key === "Enter") sendChat(); };
$("#fault-submit").onclick = submitDiagnosis;
$("#sync-now").onclick = syncNow;

// ---------- go ----------
boot();