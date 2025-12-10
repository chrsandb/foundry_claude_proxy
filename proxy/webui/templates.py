"""Static HTML template for the admin dashboard (served at /admin)."""

ADMIN_INDEX_HTML = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Foundry Proxy Admin</title>
  <style>
    :root {
      --bg: #050b15;
      --panel: #0f1629;
      --panel-2: #111b31;
      --text: #e8eef7;
      --muted: #9cb3d3;
      --accent: #6dd5fa;
      --accent-2: #a8ff78;
      --danger: #ff6b6b;
      --warn: #f7c266;
      --success: #4ade80;
      --border: rgba(255, 255, 255, 0.06);
      --shadow: 0 14px 48px rgba(0, 0, 0, 0.4);
      --card-radius: 14px;
      --font: "Inter", "Manrope", "Segoe UI", system-ui, -apple-system, sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: var(--font);
      background: radial-gradient(circle at 10% 10%, rgba(109,213,250,0.05), transparent 35%),
                  radial-gradient(circle at 90% 20%, rgba(168,255,120,0.05), transparent 30%),
                  var(--bg);
      color: var(--text);
      min-height: 100vh;
    }
    a { color: var(--accent); text-decoration: none; }
    .page {
      max-width: 1200px;
      margin: 0 auto;
      padding: 28px 22px 48px;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      margin-bottom: 18px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .brand .mark {
      width: 38px;
      height: 38px;
      border-radius: 12px;
      background: linear-gradient(135deg, var(--accent), var(--accent-2));
      display: grid;
      place-items: center;
      color: #051025;
      font-weight: 700;
      box-shadow: var(--shadow);
    }
    .brand h1 {
      margin: 0;
      font-size: 20px;
      letter-spacing: 0.2px;
    }
    .tagline {
      color: var(--muted);
      font-size: 13px;
      margin: 0;
    }
    nav {
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
    }
    nav a {
      padding: 10px 12px;
      border: 1px solid var(--border);
      border-radius: 12px;
      color: var(--text);
      background: rgba(255, 255, 255, 0.02);
      transition: all 0.15s ease;
    }
    nav a:hover { border-color: rgba(255,255,255,0.15); transform: translateY(-1px); }
    .grid {
      display: grid;
      gap: 14px;
    }
    .cards {
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      margin: 12px 0 6px;
    }
    .card {
      background: linear-gradient(160deg, var(--panel), var(--panel-2));
      border: 1px solid var(--border);
      border-radius: var(--card-radius);
      padding: 16px;
      box-shadow: var(--shadow);
    }
    .card h3 {
      margin: 0 0 8px;
      font-size: 14px;
      letter-spacing: 0.2px;
      color: var(--muted);
    }
    .card .value {
      font-size: 24px;
      font-weight: 700;
    }
    .card .sub {
      margin-top: 6px;
      color: var(--muted);
      font-size: 12px;
    }
    section {
      background: rgba(255, 255, 255, 0.02);
      border: 1px solid var(--border);
      border-radius: var(--card-radius);
      padding: 18px;
      box-shadow: var(--shadow);
    }
    section h2 {
      margin: 0 0 4px;
      font-size: 17px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    section p.lead {
      margin: 0 0 12px;
      color: var(--muted);
      font-size: 13px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
    }
    th, td {
      padding: 10px;
      border-bottom: 1px solid var(--border);
      text-align: left;
      font-size: 13px;
    }
    th { color: var(--muted); font-weight: 600; }
    tr:hover td { background: rgba(255,255,255,0.02); }
    .bar {
      height: 6px;
      border-radius: 999px;
      background: rgba(255,255,255,0.08);
      overflow: hidden;
    }
    .bar span {
      display: block;
      height: 100%;
      background: linear-gradient(135deg, var(--accent), var(--accent-2));
    }
    .muted { color: var(--muted); }
    .pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(255,255,255,0.06);
      font-size: 12px;
      color: var(--text);
      border: 1px solid var(--border);
    }
    .pill.warn { color: var(--warn); border-color: rgba(247,194,102,0.3); }
    .pill.danger { color: var(--danger); border-color: rgba(255,107,107,0.3); }
    .pill.success { color: var(--success); border-color: rgba(74,222,128,0.3); }
    form {
      display: grid;
      gap: 10px;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      align-items: center;
      margin-top: 12px;
    }
    label {
      display: flex;
      flex-direction: column;
      gap: 6px;
      font-size: 13px;
      color: var(--muted);
    }
    input, select {
      background: rgba(255,255,255,0.04);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 10px 12px;
      color: var(--text);
      font-size: 14px;
    }
    button {
      background: linear-gradient(135deg, var(--accent), var(--accent-2));
      border: none;
      color: #051025;
      font-weight: 700;
      padding: 12px 14px;
      border-radius: 12px;
      cursor: pointer;
      box-shadow: var(--shadow);
      transition: transform 0.1s ease, box-shadow 0.15s ease;
    }
    button:hover { transform: translateY(-1px); box-shadow: 0 10px 30px rgba(109,213,250,0.2); }
    button.ghost {
      background: rgba(255,255,255,0.04);
      color: var(--text);
      border: 1px solid var(--border);
      box-shadow: none;
    }
    button.ghost:hover { border-color: rgba(255,255,255,0.2); }
    .actions { display: flex; gap: 6px; flex-wrap: wrap; }
    .status-dot {
      width: 10px; height: 10px; border-radius: 50%;
      background: var(--success);
      box-shadow: 0 0 0 6px rgba(74,222,128,0.1);
    }
    .status-dot.off { background: var(--danger); box-shadow: 0 0 0 6px rgba(255,107,107,0.08); }
    .toast {
      position: fixed;
      bottom: 18px;
      right: 18px;
      padding: 14px 16px;
      border-radius: 12px;
      background: rgba(15,22,41,0.95);
      border: 1px solid var(--border);
      color: var(--text);
      box-shadow: var(--shadow);
      min-width: 220px;
      display: none;
      z-index: 100;
    }
    .toast.show { display: block; }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 8px;
      border-radius: 8px;
      background: rgba(255,255,255,0.06);
      font-size: 12px;
      color: var(--muted);
    }
    @media (max-width: 720px) {
      nav { width: 100%; }
      header { flex-direction: column; align-items: flex-start; }
      form { grid-template-columns: 1fr; }
      table { font-size: 12px; }
    }
  </style>
</head>
<body>
  <div class="page">
    <header>
      <div class="brand">
        <div class="mark">FP</div>
        <div>
          <h1>Foundry Proxy Admin</h1>
          <p class="tagline">Observe traffic, manage users, and tune admin config.</p>
        </div>
      </div>
      <nav>
        <a href="#dashboard">Dashboard</a>
        <a href="#users">Users</a>
        <a href="#metrics">Metrics</a>
        <a href="#config">Config</a>
        <a href="#logs">Logs</a>
      </nav>
    </header>

    <section id="dashboard">
      <h2>Dashboard</h2>
      <p class="lead">Live snapshot of request volume, errors, and system state. Auto-refreshing every 10 seconds.</p>
      <div class="cards" id="card-grid">
        <div class="card">
          <h3>Uptime</h3>
          <div class="value" id="uptime">--</div>
          <div class="sub" id="start-time">Start: --</div>
        </div>
        <div class="card">
          <h3>Requests</h3>
          <div class="value" id="requests">--</div>
          <div class="sub" id="requests-rate">-- / min</div>
        </div>
        <div class="card">
          <h3>Errors</h3>
          <div class="value" id="errors">--</div>
          <div class="sub" id="error-rate">--</div>
        </div>
        <div class="card">
          <h3>Users</h3>
          <div class="value" id="users-count">--</div>
          <div class="sub" id="users-disabled">-- disabled</div>
        </div>
        <div class="card">
          <h3>Latency</h3>
          <div class="value" id="latency-p95">--</div>
          <div class="sub" id="latency-avg">--</div>
        </div>
      </div>
    </section>

    <div class="grid" style="margin-top: 16px;">
      <section id="users">
        <h2>Users</h2>
        <p class="lead">API key-only auth with friendly labels. Create, disable/enable, reset tokens.</p>
        <form id="user-form">
          <label>User ID
            <input name="user" placeholder="e.g. jane.doe" required />
          </label>
          <label>Email (optional)
            <input name="email" type="email" placeholder="jane@example.com" />
          </label>
          <label>Display Name (optional)
            <input name="display_name" placeholder="Jane Doe" />
          </label>
          <label>Custom Token (optional)
            <input name="token" placeholder="Leave blank to auto-generate" />
          </label>
          <label>State
            <select name="disabled">
              <option value="false">Enabled</option>
              <option value="true">Disabled</option>
            </select>
          </label>
          <div style="display:flex; align-items:center; gap:10px;">
            <button type="submit">Create / Add User</button>
            <span class="muted" id="user-form-result"></span>
          </div>
        </form>
        <div style="display:flex; justify-content: space-between; align-items:center; gap:10px; margin:12px 0;">
          <input id="user-search" placeholder="Search users by id, name, or email" style="flex:1; max-width:360px;" />
          <div class="actions">
            <select id="page-size" style="min-width:110px;">
              <option value="10">10 / page</option>
              <option value="20">20 / page</option>
              <option value="50">50 / page</option>
            </select>
            <button type="button" class="ghost" id="pager-prev">Prev</button>
            <span id="user-pager" class="muted">Page 1 / 1</span>
            <button type="button" class="ghost" id="pager-next">Next</button>
          </div>
        </div>
        <div style="margin-top: 12px; overflow-x: auto;">
          <table id="users-table">
            <thead>
              <tr>
                <th>User</th>
                <th>Name</th>
                <th>Email</th>
                <th>Created</th>
                <th>Last Used</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody></tbody>
          </table>
        </div>
        <div id="user-detail" class="card" style="margin-top:12px;"></div>
      </section>

      <section id="metrics">
        <div style="display:flex; justify-content:space-between; align-items:center; gap:10px;">
          <div>
            <h2>Metrics</h2>
            <p class="lead">Route-level volume, errors, and token counts. Updates every 10 seconds.</p>
          </div>
          <button class="ghost" id="reset-metrics">Reset metrics</button>
        </div>
        <div class="cards">
          <div class="card">
            <h3>Requests / min (poll-based)</h3>
            <canvas id="req-chart" height="80"></canvas>
          </div>
          <div class="card">
            <h3>Errors / min (poll-based)</h3>
            <canvas id="err-chart" height="80"></canvas>
          </div>
          <div class="card">
            <h3>Latency p95 (ms)</h3>
            <canvas id="lat-chart" height="80"></canvas>
          </div>
        </div>
        <div style="overflow-x:auto;">
          <table id="metrics-table">
            <thead>
              <tr>
                <th>Route</th>
                <th>Requests</th>
                <th>Errors</th>
                <th>Usage (tokens)</th>
                <th>Latency (p95 / avg ms)</th>
                <th>Last Seen</th>
              </tr>
            </thead>
            <tbody></tbody>
          </table>
        </div>
      </section>

      <section id="config">
        <h2>Config &amp; Health</h2>
        <p class="lead">Admin auth mode, flags, and config store snapshot.</p>
        <div class="cards">
          <div class="card">
            <h3>Admin Auth</h3>
            <div class="value" id="auth-mode">--</div>
            <div class="sub" id="auth-flags">--</div>
          </div>
          <div class="card">
            <h3>Metrics Start</h3>
            <div class="value" id="metrics-start">--</div>
            <div class="sub" id="metrics-uptime">--</div>
          </div>
          <div class="card">
            <h3>Admin Config Store</h3>
            <div class="value" id="config-store-state">--</div>
            <div class="sub" id="config-store-path">--</div>
          </div>
        </div>
        <pre id="config-dump" style="background: rgba(0,0,0,0.25); border:1px solid var(--border); padding:14px; border-radius:12px; color: var(--muted); font-size: 12px; overflow-x:auto;"></pre>
      </section>

      <section id="logs">
        <h2>Logs &amp; Events</h2>
        <p class="lead">Recent notable events. Polling every 30 seconds.</p>
        <div class="actions" style="margin-bottom:8px;">
          <button class="ghost" id="download-logs">Download events (NDJSON)</button>
        </div>
        <div id="logs-container" class="grid" style="gap:8px;"></div>
      </section>
    </div>
  </div>

      <div class="toast" id="toast"></div>
      <div class="toast" id="copy-toast"></div>

  <script>
    const state = {
      summary: null,
      metrics: null,
      users: {},
      lastToken: null,
      metricsHistory: [],
      userFilter: "",
      userPage: 0,
      pageSize: 10,
      selectedUser: null,
    };

    const api = {
      async json(url, opts = {}) {
        const res = await fetch(url, {
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          ...opts,
        });
        if (!res.ok) {
          const detail = await res.text();
          throw new Error(detail || ("Request failed: " + res.status));
        }
        const text = await res.text();
        return text ? JSON.parse(text) : {};
      },
      summary() { return this.json("/admin/api/summary"); },
      metrics() { return this.json("/admin/api/metrics"); },
      users() { return this.json("/admin/users"); },
      userDetail(user) { return this.json(`/admin/users/${encodeURIComponent(user)}`); },
      createUser(body) { return this.json("/admin/users", { method: "POST", body: JSON.stringify(body) }); },
      updateUser(user, body) { return this.json(`/admin/users/${encodeURIComponent(user)}`, { method: "PATCH", body: JSON.stringify(body) }); },
      disableUser(user) { return this.json(`/admin/users/${encodeURIComponent(user)}/disable`, { method: "POST" }); },
      enableUser(user) { return this.json(`/admin/users/${encodeURIComponent(user)}/enable`, { method: "POST" }); },
      resetUser(user) { return this.json(`/admin/users/${encodeURIComponent(user)}/reset`, { method: "POST" }); },
      deleteUser(user) { return this.json(`/admin/users/${encodeURIComponent(user)}`, { method: "DELETE" }); },
      resetMetrics() { return this.json("/admin/metrics/reset", { method: "POST" }); },
      logs() { return this.json("/admin/logs"); },
      downloadLogs() { return fetch("/admin/logs/download", { credentials: "include" }); },
      config() { return this.json("/admin/api/config"); },
    };

    function fmtDate(ts) {
      if (!ts) return "—";
      const d = new Date(ts * 1000);
      return d.toLocaleString();
    }
    function fmtDuration(seconds) {
      if (!seconds && seconds !== 0) return "—";
      const mins = Math.floor(seconds / 60);
      const hrs = Math.floor(mins / 60);
      const days = Math.floor(hrs / 24);
      if (days > 0) return `${days}d ${hrs % 24}h`;
      if (hrs > 0) return `${hrs}h ${mins % 60}m`;
      if (mins > 0) return `${mins}m ${Math.floor(seconds % 60)}s`;
      return `${Math.floor(seconds)}s`;
    }
    function showToast(msg) {
      const el = document.getElementById("toast");
      el.textContent = msg;
      el.classList.add("show");
      setTimeout(() => el.classList.remove("show"), 3200);
    }
    async function copyText(text) {
      try {
        await navigator.clipboard.writeText(text);
        const el = document.getElementById("copy-toast");
        el.textContent = "Copied";
        el.classList.add("show");
        setTimeout(() => el.classList.remove("show"), 2000);
      } catch (e) {
        showToast("Copy failed");
      }
    }

    async function loadSummary() {
      try {
        const data = await api.summary();
        state.summary = data;
        renderSummary();
        renderConfig();
      } catch (e) {
        console.error(e);
        showToast("Failed to load summary: " + e.message);
      }
    }

    async function loadMetrics() {
      try {
        const data = await api.metrics();
        state.metrics = data;
        renderMetrics();
      } catch (e) {
        console.error(e);
        showToast("Failed to load metrics: " + e.message);
      }
    }

    async function loadUsers() {
      try {
        const data = await api.users();
        if (data && data.users) {
          state.users = data.users;
          renderUsers();
        } else if (data.status === "disabled") {
          document.querySelector("#users-table tbody").innerHTML = `<tr><td colspan="7">${data.message || "User management disabled."}</td></tr>`;
        }
      } catch (e) {
        console.error(e);
        document.querySelector("#users-table tbody").innerHTML = `<tr><td colspan="7">User management unavailable (${e.message}).</td></tr>`;
      }
    }

    async function loadLogs() {
      try {
        const data = await api.logs();
        renderLogs(data.events || [], data.message, data.persisted ? data.path : null);
      } catch (e) {
        console.error(e);
        renderLogs([], "Logs unavailable: " + e.message);
      }
    }

    function renderSummary() {
      const s = state.summary;
      if (!s) return;
      const metrics = s.metrics || {};
      const uptime = metrics.uptime_seconds || 0;
      const totalRequests = metrics.total_requests || 0;
      const totalErrors = metrics.total_errors || 0;
      const latency = metrics.latency || {};
      const start = metrics.start_time ? fmtDate(metrics.start_time) : "—";
      const rate = uptime ? Math.round((totalRequests / uptime) * 60) : 0;
      document.getElementById("uptime").textContent = fmtDuration(uptime);
      document.getElementById("start-time").textContent = "Start: " + start;
      document.getElementById("requests").textContent = totalRequests.toLocaleString();
      document.getElementById("requests-rate").textContent = `${rate} / min`;
      document.getElementById("errors").textContent = totalErrors.toLocaleString();
      document.getElementById("error-rate").textContent = totalRequests ? `${Math.round((totalErrors / totalRequests) * 100)}%` : "0%";
      document.getElementById("users-count").textContent = (s.user_count || 0).toString();
      document.getElementById("users-disabled").textContent = `${s.disabled_users || 0} disabled`;
      document.getElementById("latency-p95").textContent = `${Math.round(latency.p95_ms || 0)} ms p95`;
      document.getElementById("latency-avg").textContent = `Avg ${Math.round(latency.avg_ms || 0)} ms`;
    }

    function renderMetrics() {
      const table = document.querySelector("#metrics-table tbody");
      const metrics = state.metrics || {};
      const routes = metrics.routes || {};
      const rows = Object.entries(routes);
      if (rows.length === 0) {
        table.innerHTML = "<tr><td colspan='5'>No traffic yet.</td></tr>";
        return;
      }
      const maxCount = Math.max(...rows.map(([_, v]) => v.count || 0), 1);
      table.innerHTML = rows
        .sort((a, b) => (b[1].count || 0) - (a[1].count || 0))
        .map(([route, data]) => {
          const usage = data.usage || {};
          const bar = Math.max(4, Math.round(((data.count || 0) / maxCount) * 100));
          const lat = data.latency_ms || {};
          const p95 = lat.p95 ? Math.round(lat.p95) : 0;
          const avg = lat.avg ? Math.round(lat.avg) : 0;
          return `
            <tr>
              <td><code>${route}</code></td>
              <td>${data.count || 0}<div class="bar"><span style="width:${bar}%"></span></div></td>
              <td>${data.error_count || 0}</td>
              <td><span class="badge">prompt ${usage.prompt_tokens || 0}</span> <span class="badge">completion ${usage.completion_tokens || 0}</span> <span class="badge">total ${usage.total_tokens || 0}</span></td>
              <td>${p95} / ${avg}</td>
              <td class="muted">${data.last_seen ? fmtDate(data.last_seen) : "—"}</td>
            </tr>
          `;
        }).join("");

      // Record history point for charts.
      const totalReq = metrics.total_requests || 0;
      const totalErr = metrics.total_errors || 0;
      const p95 = (metrics.latency && metrics.latency.p95_ms) || 0;
      const now = Date.now() / 1000;
      state.metricsHistory.push({ ts: now, totalReq, totalErr, p95 });
      if (state.metricsHistory.length > 60) state.metricsHistory.shift();
      renderMetricCharts();
    }

    function renderMetricCharts() {
      const hist = state.metricsHistory;
      if (!hist.length) return;
      const reqCanvas = document.getElementById("req-chart");
      const errCanvas = document.getElementById("err-chart");
      const latCanvas = document.getElementById("lat-chart");
      drawLineChart(reqCanvas, hist, p => p.totalReq, "#6dd5fa");
      drawLineChart(errCanvas, hist, p => p.totalErr, "#ff6b6b");
      drawLineChart(latCanvas, hist, p => p.p95, "#f7c266");
    }

    function drawLineChart(canvas, points, accessor, stroke) {
      if (!canvas || !canvas.getContext) return;
      const ctx = canvas.getContext("2d");
      const w = canvas.width = canvas.clientWidth;
      const h = canvas.height = canvas.clientHeight;
      ctx.clearRect(0, 0, w, h);
      if (points.length < 2) return;
      const xs = points.map(p => p.ts);
      const ys = points.map(accessor);
      const minX = Math.min(...xs);
      const maxX = Math.max(...xs);
      const minY = Math.min(...ys);
      const maxY = Math.max(...ys);
      const scaleX = (x) => (w * (x - minX)) / Math.max(1, maxX - minX);
      const scaleY = (y) => h - (h * (y - minY)) / Math.max(1, maxY - minY);
      ctx.beginPath();
      ctx.strokeStyle = stroke;
      ctx.lineWidth = 2;
      points.forEach((p, i) => {
        const x = scaleX(p.ts);
        const y = scaleY(accessor(p));
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
      // Baseline grid
      ctx.strokeStyle = "rgba(255,255,255,0.08)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, h - 1);
      ctx.lineTo(w, h - 1);
      ctx.stroke();
    }

    function renderUsers() {
      const tbody = document.querySelector("#users-table tbody");
      const query = (state.userFilter || "").toLowerCase();
      const entries = Object.entries(state.users || {}).filter(([user, data]) => {
        return (
          user.toLowerCase().includes(query) ||
          (data.email || "").toLowerCase().includes(query) ||
          (data.display_name || "").toLowerCase().includes(query)
        );
      });
      if (entries.length === 0) {
        tbody.innerHTML = "<tr><td colspan='7'>No users configured.</td></tr>";
        return;
      }
      const pageCount = Math.max(1, Math.ceil(entries.length / state.pageSize));
      state.userPage = Math.min(state.userPage, pageCount - 1);
      const start = state.userPage * state.pageSize;
      const pageEntries = entries
        .sort((a, b) => (b[1].created_at || 0) - (a[1].created_at || 0))
        .slice(start, start + state.pageSize);
      tbody.innerHTML = pageEntries
        .map(([user, data]) => {
          const disabled = data.disabled ? "<span class='pill danger'>Disabled</span>" : "<span class='pill success'>Enabled</span>";
          return `
            <tr onclick="showUserDetail('${user}')" style="cursor:pointer;">
              <td><strong>${user}</strong></td>
              <td>${data.display_name || "—"}</td>
              <td>${data.email || "—"}</td>
              <td class="muted">${fmtDate(data.created_at)}</td>
              <td class="muted">${fmtDate(data.last_used)}</td>
              <td>${disabled}</td>
              <td>
                <div class="actions">
                  <button class="ghost" onclick="event.stopPropagation(); toggleUser('${user}', ${!data.disabled})">${data.disabled ? "Enable" : "Disable"}</button>
                  <button class="ghost" onclick="event.stopPropagation(); resetToken('${user}')">Reset token</button>
                  <button class="ghost" onclick="event.stopPropagation(); deleteUser('${user}')">Delete</button>
                </div>
              </td>
            </tr>
          `;
        }).join("");
      const pager = document.getElementById("user-pager");
      pager.textContent = `Page ${state.userPage + 1} / ${pageCount}`;
    }

    function renderConfig() {
      const summary = state.summary || {};
      const adminConfig = (summary.admin_config) || {};
      const configStore = summary.config_store || {};
      const metricsStart = state.metrics ? state.metrics.start_time : adminConfig.start_time;
      document.getElementById("auth-mode").textContent = (adminConfig.auth_mode || "unknown").toUpperCase();
      const flags = [
        adminConfig.allow_user_mgmt ? "user mgmt" : null,
        adminConfig.allow_config_edit ? "config edit" : null,
        adminConfig.allow_reset ? "metrics reset" : null,
      ].filter(Boolean).join(" · ") || "No admin features enabled.";
      document.getElementById("auth-flags").textContent = flags;
      document.getElementById("metrics-start").textContent = metricsStart ? fmtDate(metricsStart) : "—";
      if (state.metrics && state.metrics.uptime_seconds !== undefined) {
        document.getElementById("metrics-uptime").textContent = `Uptime ${fmtDuration(state.metrics.uptime_seconds)}`;
      } else {
        document.getElementById("metrics-uptime").textContent = "—";
      }
      const hasConfig = configStore && Object.keys(configStore).length > 0;
      document.getElementById("config-store-state").textContent = hasConfig ? "Loaded" : "Not configured";
      document.getElementById("config-store-path").textContent = configStore.path || "—";
      document.getElementById("config-dump").textContent = hasConfig ? JSON.stringify(configStore, null, 2) : "No admin config store attached.";
    }

    function renderLogs(events, message, path) {
      const container = document.getElementById("logs-container");
      if ((!events || events.length === 0) && !message) {
        container.innerHTML = "<div class='muted'>No events yet.</div>";
        return;
      }
      const parts = [];
      if (message) {
        const extra = path ? `<div class="muted" style="margin-top:6px;">Path: ${path}</div>` : "";
        parts.push(`<div class="card"><div class="value">Info</div><div class="sub">${message}</div>${extra}</div>`);
      }
      (events || []).slice(0, 12).forEach(evt => {
        parts.push(`
          <div class="card">
            <h3>${evt.title || "Event"}</h3>
            <div class="sub">${evt.detail || ""}</div>
            <div class="muted" style="margin-top:6px;">${fmtDate(evt.ts)}</div>
          </div>
        `);
      });
      container.innerHTML = parts.join("");
    }

    async function showUserDetail(user) {
      try {
        const res = await api.userDetail(user);
        state.selectedUser = res;
        const box = document.getElementById("user-detail");
        const data = res.data || {};
        box.innerHTML = `
          <h3>User Detail: ${res.user}</h3>
          <p class="muted">Email: ${data.email || "—"} | Name: ${data.display_name || "—"}</p>
          <p class="muted">Created: ${fmtDate(data.created_at)} | Last used: ${fmtDate(data.last_used)}</p>
          <p class="muted">Status: ${data.disabled ? "Disabled" : "Enabled"}</p>
          <div class="actions">
            <button class="ghost" onclick="toggleUser('${res.user}', ${data.disabled})">${data.disabled ? "Enable" : "Disable"}</button>
            <button class="ghost" onclick="resetToken('${res.user}')">Reset token</button>
          </div>
        `;
      } catch (e) {
        showToast("Detail failed: " + e.message);
      }
    }

    async function toggleUser(user, enable) {
      try {
        if (enable) {
          await api.enableUser(user);
        } else {
          await api.disableUser(user);
        }
        showToast(`User ${user} ${enable ? "enabled" : "disabled"}`);
        await loadUsers();
      } catch (e) {
        console.error(e);
        showToast(`Failed to update user: ${e.message}`);
      }
    }

    async function resetToken(user) {
      try {
        const res = await api.resetUser(user);
        if (res && res.token) {
          state.lastToken = res.token;
          showToast(`New token for ${user}: ${res.token}`);
          copyText(res.token);
          if (state.selectedUser && state.selectedUser.user === user) {
            document.getElementById("user-detail").insertAdjacentHTML("beforeend", `<p class="muted">Latest token: ${res.token}</p>`);
          }
        }
        await loadUsers();
      } catch (e) {
        console.error(e);
        showToast(`Failed to reset token: ${e.message}`);
      }
    }

    async function deleteUser(user) {
      if (!confirm(`Delete user ${user}?`)) return;
      try {
        await api.deleteUser(user);
        showToast(`Deleted ${user}`);
        await loadUsers();
      } catch (e) {
        console.error(e);
        showToast(`Failed to delete user: ${e.message}`);
      }
    }

    document.getElementById("user-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const form = new FormData(e.target);
      const payload = {
        user: form.get("user"),
        email: form.get("email") || undefined,
        display_name: form.get("display_name") || undefined,
        token: form.get("token") || undefined,
        disabled: form.get("disabled") === "true",
      };
      try {
        const res = await api.createUser(payload);
        if (res && res.token) {
          state.lastToken = res.token;
          const msg = `Token created: ${res.token}`;
          document.getElementById("user-form-result").textContent = msg;
          const copyBtn = document.createElement("button");
          copyBtn.textContent = "Copy token";
          copyBtn.className = "ghost";
          copyBtn.style.marginLeft = "8px";
          copyBtn.onclick = () => copyText(res.token);
          const resultSpan = document.getElementById("user-form-result");
          resultSpan.innerHTML = msg + " ";
          resultSpan.appendChild(copyBtn);
        }
        showToast(`User ${payload.user} created`);
        e.target.reset();
        await loadUsers();
        await loadSummary();
      } catch (err) {
        console.error(err);
        showToast("Create failed: " + err.message);
      }
    });

    document.getElementById("reset-metrics").addEventListener("click", async () => {
      try {
        await api.resetMetrics();
        showToast("Metrics reset");
        await loadMetrics();
        await loadSummary();
      } catch (e) {
        showToast("Reset failed: " + e.message);
      }
    });

    document.getElementById("user-search").addEventListener("input", (e) => {
      state.userFilter = e.target.value;
      state.userPage = 0;
      renderUsers();
    });
    document.getElementById("page-size").addEventListener("change", (e) => {
      state.pageSize = parseInt(e.target.value, 10) || 10;
      state.userPage = 0;
      renderUsers();
    });

    document.getElementById("pager-prev").addEventListener("click", () => {
      if (state.userPage > 0) { state.userPage -= 1; renderUsers(); }
    });
    document.getElementById("pager-next").addEventListener("click", () => {
      const total = Object.entries(state.users || {}).length;
      const pageCount = Math.max(1, Math.ceil(total / state.pageSize));
      if (state.userPage < pageCount - 1) { state.userPage += 1; renderUsers(); }
    });

    document.getElementById("download-logs").addEventListener("click", async () => {
      try {
        const res = await api.downloadLogs();
        if (!res.ok) throw new Error("Download failed");
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "admin-events.ndjson";
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        showToast("Logs downloaded");
      } catch (e) {
        showToast("Download failed: " + e.message);
      }
    });

    // Initial load + polling
    loadSummary();
    loadMetrics();
    loadUsers();
    loadLogs();
    setInterval(loadSummary, 10000);
    setInterval(loadMetrics, 10000);
    setInterval(loadLogs, 30000);
  </script>
</body>
</html>
"""
