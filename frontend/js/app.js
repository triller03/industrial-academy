// AI-Powered Industrial Academy — front-end client
const API = "/api";

const state = {
  token: localStorage.getItem("academy_token") || null,
  refreshToken: localStorage.getItem("academy_refresh") || null,
  user: null,
  projects: [],
  currentProject: null,
  currentSection: null,
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

function storeTokens(data) {
  if (data.access_token) {
    state.token = data.access_token;
    localStorage.setItem("academy_token", data.access_token);
  }
  if (data.refresh_token) {
    state.refreshToken = data.refresh_token;
    localStorage.setItem("academy_refresh", data.refresh_token);
  }
}

async function refreshAccessToken() {
  if (!state.refreshToken) return false;
  try {
    const res = await fetch(API + "/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: state.refreshToken }),
    });
    if (!res.ok) return false;
    storeTokens(await res.json());
    return true;
  } catch { return false; }
}

async function api(path, { method = "GET", body, form, auth = true, retry = true } = {}) {
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
  let res;
  try {
    res = await fetch(API + path, { method, headers, body: payload });
  } catch (err) {
    throw new Error("You are offline. Your work is saved on this device and will sync automatically.");
  }
  if (res.status === 401 && auth) {
    if (retry && await refreshAccessToken()) {
      return api(path, { method, body, form, auth, retry: false });
    }
    logout();
    throw new Error("Session expired. Sign in again.");
  }
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
  storeTokens(data);
  await boot();
}
async function register(payload) {
  await api("/auth/register", { method: "POST", body: payload, auth: false });
  await login(payload.email, payload.password);
}
function logout() {
  state.token = null; state.refreshToken = null; state.user = null;
  localStorage.removeItem("academy_token");
  localStorage.removeItem("academy_refresh");
  $("#app").classList.add("hidden");
  $("#auth-screen").classList.remove("hidden");
}

// ---------- boot ----------
async function boot() {
  if (!state.token) { $("#auth-screen").classList.remove("hidden"); return; }
  try {
    state.user = await api("/auth/me");
    localStorage.setItem("academy_user", JSON.stringify(state.user));
  } catch (err) {
    const cached = localStorage.getItem("academy_user");
    if (cached && !Offline.isOnline()) {
      state.user = JSON.parse(cached);
    } else { logout(); return; }
  }
  $("#auth-screen").classList.add("hidden");
  $("#app").classList.remove("hidden");
  $("#user-chip").innerHTML = `<div>${esc(state.user.full_name)}</div><div class="email">${esc(state.user.email)}</div>`;

  await loadProjects();
  await authorizeThisDevice();
  updateNetStatus();
  showTab("projects");
  if (Offline.isOnline()) flushQueue();
}

async function loadProjects() {
  try {
    state.projects = await api("/projects");
    localStorage.setItem("academy_projects", JSON.stringify(state.projects));
  } catch (err) {
    const cached = localStorage.getItem("academy_projects");
    if (!cached) throw err;
    state.projects = JSON.parse(cached);
  }
  renderProjects();
}
function renderProjects() {
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

// ---------- offline status + sync ----------
function updateNetStatus() {
  const el0 = $("#net-status");
  if (!el0) return;
  const s = Offline.status();
  el0.className = "net-status " + (s.online ? "online" : "offline");
  el0.innerHTML = `<span class="dot"></span>${s.online ? "Online" : "Offline"}` +
    (s.pending ? ` · <span class="pending">${s.pending} pending</span>` : "");
}
async function flushQueue(silent) {
  const out = $("#sync-out");
  const qlen = Offline.queue().length;
  if (!qlen && silent) return;
  try {
    const res = await Offline.flush(state.token, deviceFingerprint());
    if (out) out.textContent = `Synced. Applied ${res.applied.length}, conflicts ${res.conflicts.length}.`;
    updateNetStatus();
    if (res.applied.length) { await loadDashboard(); }
    return res;
  } catch (err) {
    if (out && !silent) out.textContent = "Sync failed: " + err.message;
    updateNetStatus();
  }
}
window.addEventListener("online", () => { updateNetStatus(); flushQueue(true); });
window.addEventListener("offline", () => updateNetStatus());
window.addEventListener("offline-status", updateNetStatus);

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
async function openProject(id) {
  let project;
  try {
    project = await api("/projects/" + id);
  } catch (err) {
    const bundle = await Offline.getBundle(id);
    if (!bundle) throw err;
    project = { ...bundle.bundle.project, sections: bundle.bundle.sections };
  }
  state.currentProject = project;
  $("#projects-list").classList.add("hidden");
  $("#project-detail").classList.remove("hidden");
  $("#pd-title").textContent = project.title;
  $("#pd-meta").textContent = `${project.industry} · ${project.difficulty} · ${project.hours} h · 17-section lifecycle`;

  let progress = null;
  try { progress = await api(`/projects/${id}/progress`); } catch { /* offline: use local overlay */ }
  renderProjectProgress(project, progress);

  const nav = $("#pd-sections");
  nav.innerHTML = "";
  project.sections.forEach((s, i) => {
    const b = el("button", "");
    b.textContent = `${i + 1}. ${s.title}`;
    b.dataset.key = s.key;
    b.onclick = () => {
      $all("#pd-sections button").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      showSection(s);
    };
    nav.appendChild(b);
  });
  if (project.sections.length) { nav.children[0].click(); }
}

function renderProjectProgress(project, progress) {
  const local = Offline.getLocalProgress(project.id);
  const serverSections = (progress && progress.sections) || [];
  const serverByKey = {};
  serverSections.forEach((s) => { serverByKey[s.section_key] = s; });

  let completed = 0;
  project.sections.forEach((s) => {
    const server = serverByKey[s.key];
    const localRow = local[s.key];
    const status = (localRow && localRow.status) || (server && server.status) || "not_started";
    if (status === "completed") completed++;
    const btn = document.querySelector(`#pd-sections button[data-key="${s.key}"]`);
    if (btn) btn.classList.toggle("done", status === "completed");
  });

  const total = project.sections.length || 17;
  const pct = total ? (completed / total) * 100 : 0;
  const pending = Offline.queue().filter((c) => c.entity === "progress" && c.payload.project_id === project.id).length;
  $("#pd-progress").innerHTML =
    `<div class="progress-strip"><div style="width:${pct}%"></div></div>
     <div class="muted">${completed} / ${total} sections completed (${pct.toFixed(0)}%)` +
     (pending ? ` · <span class="pending">${pending} change(s) queued</span>` : "") + `</div>`;
}

async function markSectionComplete() {
  const project = state.currentProject;
  const section = state.currentSection;
  if (!project || !section) return;
  const note = $("#pd-complete-note");
  Offline.enqueue(Offline.progressChange(project.id, section.key, "completed", 100, 0));
  Offline.recordLocalProgress(project.id, section.key, { status: "completed", score: 100 });
  const serverProgress = await safeProjectProgress(project.id);
  renderProjectProgress(project, serverProgress);
  if (Offline.isOnline()) {
    note.textContent = "Saved. Syncing…";
    const res = await flushQueue(true);
    note.textContent = res && res.applied.length ? "Completed and synced." : "Saved locally; will sync shortly.";
  } else {
    note.textContent = "Saved on this device. It will sync when you are back online.";
  }
  updateNetStatus();
}

async function safeProjectProgress(projectId) {
  try { return await api(`/projects/${projectId}/progress`); }
  catch { return null; }
}

function showSection(section) {
  state.currentSection = section;
  $("#pd-section-title").textContent = section.title;
  $("#pd-section-body").innerHTML = renderMarkdown(section.content);
  $("#pd-complete-note").textContent = "";
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
  // Overlay locally-completed sections that have not synced yet.
  state.projects.forEach((p) => {
    const local = Offline.getLocalProgress(p.id);
    Object.keys(local).forEach((key) => {
      const existing = (byProject[p.id] || []).find((r) => r.section_key === key);
      if (existing) { if (local[key].status === "completed") existing.status = "completed"; }
      else byProject[p.id] = (byProject[p.id] || []).concat([{ project_id: p.id, section_key: key, status: local[key].status, score: local[key].score || 0, updated_at: local[key].updated_at }]);
    });
  });

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
  const allRows = Object.values(byProject).flat();
  const list = $("#dash-project-list");
  list.innerHTML = "";
  allRows.slice().sort((a, b) => (b.updated_at || "").localeCompare(a.updated_at || "")).slice(0, 8).forEach((r) => {
    const p = state.projects.find((x) => x.id === r.project_id);
    list.appendChild(el("div", "panel-item",
      `<div class="title">${esc(p ? p.title : "Project " + r.project_id)} — ${esc(String(r.section_key || "").replace(/_/g, " "))}</div>
       <div class="sub">${esc(r.status)} · score ${r.score} · updated ${esc(String(r.updated_at || "").slice(0, 16).replace("T", " "))}</div>`));
  });
  if (!allRows.length) list.innerHTML = "<p class='muted'>No progress recorded yet. Open a project to begin.</p>";
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
  const sectionKey = $("#chat-context").value || null;
  if (!Offline.isOnline()) {
    const res = await Offline.offlineMentor(message, sectionKey, state.chatLevel, state.currentProject && state.currentProject.id);
    addMsg("mentor", res.reply, res.mode, res.level);
    return;
  }
  try {
    const res = await api("/mentor/chat", {
      method: "POST",
      body: {
        message,
        project_id: state.currentProject ? state.currentProject.id : null,
        section_key: sectionKey,
        history: [{ role: "user", level: state.chatLevel }],
      },
    });
    addMsg("mentor", res.reply, res.mode, res.level);
  } catch (e) { addMsg("mentor", "Error: " + e.message, "guided", 1); }
}
async function requestSolution() {
  const message = $("#chat-input").value.trim() || "Show me the full solution with reasoning for this section.";
  addMsg("user", "[solution request] " + message, "", null);
  const sectionKey = $("#chat-context").value || null;
  if (!Offline.isOnline()) {
    const res = await Offline.offlineMentor(message, sectionKey, 5, state.currentProject && state.currentProject.id);
    addMsg("mentor", res.reply, res.mode, res.level);
    return;
  }
  try {
    const res = await api("/mentor/solution", {
      method: "POST",
      body: {
        message,
        project_id: state.currentProject ? state.currentProject.id : null,
        section_key: sectionKey,
        history: [{ role: "user", level: state.chatLevel }],
      },
    });
    addMsg("mentor", res.reply, res.mode, res.level);
  } catch (e) { addMsg("mentor", "Error: " + e.message, "guided", 1); }
}

// ---------- fault lab ----------
async function loadFaults(pid) {
  try { return await api(`/projects/${pid}/faults`); }
  catch (err) {
    const cached = await Offline.getBundle(pid);
    if (cached) return cached.bundle.faults.map((f) => ({ id: f.id, slug: f.slug, title: f.title, symptom: f.symptom, difficulty: f.difficulty }));
    throw err;
  }
}
async function openFaultLab() {
  const pid = state.currentProject ? state.currentProject.id : (state.projects[0] && state.projects[0].id);
  if (!pid) { $("#fault-select").innerHTML = "<p class='muted'>Open a project first.</p>"; return; }
  state.faults = await loadFaults(pid);
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
  let detail;
  try {
    detail = await api(`/projects/${state.currentProject.id}/faults/${f.id}`);
  } catch (err) {
    const cached = await Offline.getBundle(state.currentProject.id);
    detail = cached && cached.bundle.faults.find((x) => x.id === f.id);
    if (!detail) throw err;
  }
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
  const checks = performed.map((c) => ({ check_id: c, performed: true }));
  const diagnosis = $("#fault-diagnosis").value.trim();
  const box = $("#fault-result");

  if (!Offline.isOnline()) {
    Offline.enqueue(Offline.faultAttemptChange(state.currentFault.id, checks, diagnosis, "fault_injection"));
    Offline.recordLocalProgress(state.currentProject.id, "fault_injection", { status: "in_progress", score: 0 });
    box.className = "fault-result pending";
    box.innerHTML = `<div><strong>Queued for grading</strong></div>
      <div class="sub">You are offline. This attempt is saved on this device and will be graded the next time you sync.</div>`;
    updateNetStatus();
    return;
  }

  try {
    const res = await api("/fault/diagnose", {
      method: "POST",
      body: { fault_id: state.currentFault.id, checks, diagnosis },
    });
    box.className = "fault-result " + (res.correct ? "pass" : "fail");
    box.innerHTML = `<div><strong>${res.correct ? "Diagnosis correct" : "Not quite"}</strong> — score ${(res.score * 100).toFixed(0)}%</div>
      <div class="sub">Checks: ${res.checks_correct}/${res.checks_total} correct · expected: ${esc(res.correct_diagnosis)}</div>
      <ul>${res.feedback.map((f) => `<li>${esc(f)}</li>`).join("")}</ul>
      ${res.recommended_step ? `<div class="muted">${esc(res.recommended_step)}</div>` : ""}`;
  } catch (e) {
    box.className = "fault-result fail";
    box.textContent = "Error: " + e.message;
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
  let devices = [];
  try { devices = await api("/devices"); } catch (e) { /* offline */ }
  const list = $("#devices-list"); list.innerHTML = "";
  if (!devices.length) list.innerHTML = "<p class='muted'>No devices authorized (or you are offline).</p>";
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
  await renderBundles();
}

function fmtBytes(n) {
  if (!n) return "0 B";
  if (n < 1024) return n + " B";
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
  return (n / 1024 / 1024).toFixed(2) + " MB";
}

async function renderBundles() {
  const list = $("#bundle-list");
  if (!list) return;
  let manifest = [];
  try { manifest = await api("/offline/manifest"); } catch (e) { /* offline */ }
  const saved = await Offline.listBundles();
  const savedById = {};
  saved.forEach((s) => { savedById[s.project_id] = s; });

  list.innerHTML = "";
  if (!manifest.length && !saved.length) {
    list.innerHTML = "<p class='muted'>No bundles available yet.</p>";
    return;
  }
  const rows = manifest.length ? manifest : saved.map((s) => ({
    project_id: s.project_id, title: s.title || s.bundle.project.title, version: s.version,
    size_bytes: s.size_bytes, section_count: s.bundle.sections.length, fault_count: s.bundle.faults.length,
  }));

  rows.forEach((m) => {
    const local = savedById[m.project_id];
    const upToDate = local && local.version === m.version;
    const item = el("div", "panel-item");
    item.innerHTML = `<div class="title">${esc(m.title)}</div>
      <div class="sub">${m.section_count} sections · ${m.fault_count} faults · ${fmtBytes(m.size_bytes)} · v${esc(m.version)}</div>`;
    const status = el("div", "sub");
    status.innerHTML = local
      ? `<span class="${upToDate ? "ok" : "warn"}">${upToDate ? "Saved offline (up to date)" : "Saved offline (update available)"}</span>`
      : `<span class="warn">Not saved on this device</span>`;
    item.appendChild(status);
    const row = el("div", "row");
    const dl = el("button", "btn btn-ghost");
    dl.textContent = local ? (upToDate ? "Re-download" : "Update bundle") : "Download";
    dl.onclick = () => downloadBundle(m.project_id, dl);
    row.appendChild(dl);
    if (local) {
      const del = el("button", "btn btn-ghost");
      del.textContent = "Remove";
      del.onclick = async () => { await Offline.deleteBundle(m.project_id); renderBundles(); };
      row.appendChild(del);
    }
    item.appendChild(row);
    list.appendChild(item);
  });
}

async function downloadBundle(projectId, btn) {
  const out = $("#offline-out");
  const original = btn ? btn.textContent : "";
  if (btn) { btn.disabled = true; btn.textContent = "Downloading…"; }
  if (out) out.textContent = "";
  try {
    const local = await Offline.getBundle(projectId);
    const known = local ? local.version : "";
    const headers = { Authorization: "Bearer " + state.token };
    const url = `${API}/projects/${projectId}/offline-bundle?device_fingerprint=${encodeURIComponent(deviceFingerprint())}` +
      (known ? `&known_version=${encodeURIComponent(known)}` : "");
    const res = await fetch(url, { headers });
    if (res.status === 204) {
      if (out) out.textContent = "Already up to date.";
    } else if (res.ok) {
      const bundle = await res.json();
      await Offline.putBundle({
        project_id: projectId,
        version: res.headers.get("X-Bundle-Version") || bundle.version,
        checksum: res.headers.get("X-Bundle-Checksum") || bundle.checksum,
        size_bytes: JSON.stringify(bundle).length,
        title: bundle.project.title,
        saved_at: new Date().toISOString(),
        bundle,
      });
      if (out) out.textContent = `Saved "${bundle.project.title}" for offline use.`;
    } else {
      throw new Error("Download failed (" + res.status + ")");
    }
  } catch (e) {
    if (out) out.textContent = "Download failed: " + e.message;
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = original; }
    renderBundles();
    updateNetStatus();
  }
}

async function downloadAllBundles() {
  let manifest = [];
  try { manifest = await api("/offline/manifest"); } catch (e) {
    const out = $("#offline-out"); if (out) out.textContent = "Cannot reach the server to download bundles.";
    return;
  }
  for (const m of manifest) await downloadBundle(m.project_id, null);
}

async function syncNow() {
  const out = $("#sync-out");
  const qlen = Offline.queue().length;
  out.textContent = qlen ? `Syncing ${qlen} queued change(s)…` : "Checking for server updates…";
  const res = await flushQueue(false);
  if (!res) {
    out.textContent = Offline.isOnline() ? "Sync failed." : "Offline — changes are queued locally.";
    return;
  }
  out.textContent = `Sync complete. Applied ${res.applied.length}, conflicts ${res.conflicts.length}, server rows ${res.server_state.length}.`;
  renderBundles();
}

// ---------- service worker ----------
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((e) => console.warn("SW registration failed:", e.message));
  });
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
$("#pd-complete").onclick = markSectionComplete;
$("#download-bundles").onclick = downloadAllBundles;
document.addEventListener("offline-status", () => { if (!$("#view-devices").classList.contains("hidden")) renderBundles(); });

// ---------- go ----------
boot();