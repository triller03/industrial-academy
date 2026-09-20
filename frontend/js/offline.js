// ASAPA — offline engine
// IndexedDB bundle store + queued local changes + offline mentor + sync flush.
(function (global) {
  "use strict";

  const DB_NAME = "academy-offline";
  const DB_VERSION = 1;
  const QUEUE_KEY = "academy_queue";
  const LOCAL_PROGRESS_KEY = "academy_local_progress";

  // ---------------- IndexedDB: offline bundles ----------------
  function openDb() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains("bundles")) {
          db.createObjectStore("bundles", { keyPath: "project_id" });
        }
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  async function idb(mode, fn) {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction("bundles", mode);
      const store = tx.objectStore("bundles");
      let result;
      try { result = fn(store); } catch (e) { reject(e); return; }
      tx.oncomplete = () => resolve(result && result.__req ? result.__req.result : result);
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error);
    });
  }

  async function putBundle(entry) {
    await idb("readwrite", (store) => store.put(entry));
    return entry;
  }
  async function getBundle(projectId) {
    return idb("readonly", (store) => ({ __req: store.get(Number(projectId)) }));
  }
  async function listBundles() {
    return (await idb("readonly", (store) => ({ __req: store.getAll() }))) || [];
  }
  async function deleteBundle(projectId) {
    return idb("readwrite", (store) => store.delete(Number(projectId)));
  }
  async function getAnyBundle() {
    const all = await listBundles();
    return all.length ? all[0] : null;
  }

  // ---------------- Queue (localStorage) ----------------
  function queue() {
    try { return JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]"); } catch { return []; }
  }
  function saveQueue(q) {
    localStorage.setItem(QUEUE_KEY, JSON.stringify(q));
    updateStatus();
  }
  function changeKey(change) {
    const p = change.payload || {};
    if (change.entity === "progress") return `progress:${p.project_id}:${p.section_key}`;
    if (change.entity === "fault_attempt") return `fault_attempt:${p.fault_id}`;
    return `${change.entity}:${Math.random()}`;
  }
  function enqueue(change) {
    const q = queue();
    const key = changeKey(change);
    const idx = q.findIndex((c) => c._key === key);
    if (idx >= 0) {
      const prev = q[idx];
      const better =
        change.payload.status === "completed" ||
        (change.payload.score || 0) > (prev.payload.score || 0);
      q[idx] = better ? { ...change, _key: key } : prev;
    } else {
      q.push({ ...change, _key: key });
    }
    saveQueue(q);
    return q.length;
  }
  function dequeueKey(key) {
    saveQueue(queue().filter((c) => c._key !== key));
  }
  function clearQueue() {
    saveQueue([]);
  }

  // ---------------- Local (un-synced) progress overlay ----------------
  function localProgressMap() {
    try { return JSON.parse(localStorage.getItem(LOCAL_PROGRESS_KEY) || "{}"); } catch { return {}; }
  }
  function saveLocalProgressMap(m) {
    localStorage.setItem(LOCAL_PROGRESS_KEY, JSON.stringify(m));
  }
  function recordLocalProgress(projectId, sectionKey, patch) {
    const m = localProgressMap();
    const k = `${projectId}:${sectionKey}`;
    m[k] = { ...(m[k] || {}), ...patch, updated_at: new Date().toISOString() };
    saveLocalProgressMap(m);
  }
  function getLocalProgress(projectId) {
    const m = localProgressMap();
    const out = {};
    Object.keys(m).forEach((k) => {
      const [pid, key] = k.split(":");
      if (Number(pid) === Number(projectId)) out[key] = m[k];
    });
    return out;
  }
  function clearLocalProgress(projectId, sectionKey) {
    const m = localProgressMap();
    delete m[`${projectId}:${sectionKey}`];
    saveLocalProgressMap(m);
  }

  // ---------------- Queue change builders ----------------
  function progressChange(projectId, sectionKey, status, score, seconds) {
    return {
      entity: "progress",
      local_key: `${projectId}:${sectionKey}`,
      status,
      score,
      time_spent_seconds: seconds || 0,
      updated_at: new Date().toISOString(),
      payload: {
        project_id: projectId,
        section_key: sectionKey,
        status,
        score: score || 0,
        time_spent_seconds: seconds || 0,
        updated_at: new Date().toISOString(),
      },
    };
  }
  function faultAttemptChange(faultId, checks, diagnosis, sectionKey) {
    return {
      entity: "fault_attempt",
      local_key: `fault:${faultId}`,
      status: "completed",
      payload: {
        fault_id: faultId,
        checks,
        diagnosis,
        section_key: sectionKey || "fault_injection",
        updated_at: new Date().toISOString(),
      },
    };
  }

  // ---------------- Sync ----------------
  async function flush(token, deviceFingerprint) {
    const q = queue();
    if (!q.length) return { applied: [], conflicts: [], server_state: [] };
    const changes = q.map(({ _key, ...rest }) => rest);
    const res = await fetch("/api/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
      body: JSON.stringify({ device_fingerprint: deviceFingerprint, changes }),
    });
    if (res.status === 401) throw new Error("unauthorized");
    if (!res.ok) throw new Error("Sync failed (" + res.status + ")");
    const data = await res.json();

    // Remove the entries the server accepted and clear their local overlays.
    q.forEach((c) => {
      const p = c.payload || {};
      if (c.entity === "progress") clearLocalProgress(p.project_id, p.section_key);
      dequeueKey(c._key);
    });
    return data;
  }

  // ---------------- Offline mentor ----------------
  function hashString(s) {
    let h = 0;
    for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
    return Math.abs(h);
  }

  async function offlineMentor(message, sectionKey, level, projectId) {
    const entry = projectId ? await getBundle(projectId) : await getAnyBundle();
    const pack = entry && entry.bundle && entry.bundle.mentor_pack;
    if (!pack) {
      return {
        reply: "You are offline and no offline pack is available on this device. Open the Devices tab and download a project bundle before working offline.",
        mode: "guided", level: 1, safety_triggered: false, offline: true,
      };
    }
    const msg = String(message || "").toLowerCase();
    const has = (list) => (list || []).find((k) => msg.includes(k));

    const safetyKw = has(pack.safety_keywords);
    if (safetyKw) {
      const category = safetyKw.includes("arc") ? "arc flash" : "default";
      const steps = (pack.safety_steps && (pack.safety_steps[category] || pack.safety_steps.default)) || [];
      return {
        reply: pack.safety_preface + "\n\n" + steps.join("\n"),
        mode: "safety", level: 0, safety_triggered: true, offline: true,
      };
    }

    const asks = has(pack.frustration_keywords) || has(pack.ask_answer_keywords);
    if (asks || level >= 3) {
      const steps = pack.guided_steps || [];
      const parts = [steps.slice(0, level >= 4 ? steps.length : 3).join("\n\n")];
      if (level >= 4) parts.unshift(pack.full_solution_intro);
      parts.push("(Offline guidance — reconnect to the server for full reasoning and grading.)");
      return { reply: parts.join("\n\n"), mode: "guided", level, safety_triggered: false, offline: true };
    }

    const questions = pack.socratic_questions || [];
    const q = questions[hashString(sectionKey || "general") % questions.length];
    return { reply: q, mode: "socratic", level: 1, safety_triggered: false, offline: true };
  }

  // ---------------- Status ----------------
  function status() {
    return { online: navigator.onLine, pending: queue().length };
  }
  function updateStatus() {
    global.dispatchEvent(new CustomEvent("offline-status", { detail: status() }));
  }

  global.Offline = {
    isOnline: () => navigator.onLine,
    status, updateStatus,
    putBundle, getBundle, listBundles, deleteBundle, getAnyBundle,
    queue, enqueue, dequeueKey, clearQueue,
    recordLocalProgress, getLocalProgress, clearLocalProgress,
    progressChange, faultAttemptChange,
    flush, offlineMentor,
  };
})(window);
