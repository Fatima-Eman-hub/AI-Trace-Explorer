
const API_BASE = "http://localhost:8000/api/v1";
const WS_BASE = "ws://localhost:8000";

function getApiKey() { return localStorage.getItem("ate_api_key") || ""; }
function setApiKey(key) { localStorage.setItem("ate_api_key", key || ""); }

function apiHeaders(extra = {}) {
  const headers = { "Content-Type": "application/json", ...extra };
  const key = getApiKey();
  if (key) headers["X-API-Key"] = key;
  return headers;
}

async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`, { headers: apiHeaders() });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

async function apiPost(path, data) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: apiHeaders(),
    body: JSON.stringify(data),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `Request failed (${res.status})`);
  return body;
}

async function apiDelete(path) {
  const res = await fetch(`${API_BASE}${path}`, { method: "DELETE", headers: apiHeaders() });
  if (!res.ok) throw new Error(`Request failed (${res.status})`);
  return res.json();
}

async function checkHealth() {
  try {
    const res = await fetch("http://localhost:8000/health");
    return res.ok;
  } catch {
    return false;
  }
}

function fmtMs(ms) {
  if (ms === null || ms === undefined) return "—";
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${ms}ms`;
}
function fmtUsd(v) {
  if (v === null || v === undefined) return "—";
  if (v === 0) return "$0.00";
  return v < 0.01 ? `$${v.toFixed(6)}` : `$${v.toFixed(4)}`;
}
function fmtPct(v) {
  if (v === null || v === undefined) return "—";
  return `${Math.round(v * 100)}%`;
}
function fmtRelTime(iso) {
  if (!iso) return "—";
  const diff = (Date.now() - new Date(iso + "Z").getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}
function truncate(s, n) {
  if (!s) return "";
  return s.length > n ? s.slice(0, n) + "…" : s;
}
function escapeHtml(s) {
  if (s === null || s === undefined) return "";
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function showToast(message, isError = false) {
  let el = document.getElementById("toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "toast";
    document.body.appendChild(el);
  }
  el.textContent = message;
  el.className = isError ? "show error" : "show";
  clearTimeout(window.__toastTimer);
  window.__toastTimer = setTimeout(() => el.classList.remove("show"), 3200);
}

const NAV_ITEMS = [
  { href: "index.html", key: "dashboard", label: "Dashboard",
    icon: `<path d="M3 13h8V3H3v10Zm0 8h8v-6H3v6Zm10 0h8V11h-8v10Zm0-18v6h8V3h-8Z" fill="currentColor"/>` },
  { href: "traces.html", key: "traces", label: "Traces",
    icon: `<path d="M4 6h16M4 12h16M4 18h10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>` },
  { href: "new-request.html", key: "new", label: "New Request",
    icon: `<path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>` },
  { href: "analytics.html", key: "analytics", label: "Analytics",
    icon: `<path d="M4 20V10M11 20V4M18 20v-7" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>` },
  { href: "models.html", key: "models", label: "Models",
    icon: `<circle cx="12" cy="6" r="3" stroke="currentColor" stroke-width="2"/><circle cx="6" cy="17" r="3" stroke="currentColor" stroke-width="2"/><circle cx="18" cy="17" r="3" stroke="currentColor" stroke-width="2"/>` },
];

function renderShell(activeKey, pageTitle, eyebrow) {
  const rail = document.createElement("div");
  rail.className = "rail";
  rail.innerHTML = `
    <a href="index.html" class="rail-logo">AI</a>
    <div class="rail-nav">
      ${NAV_ITEMS.map(item => `
        <a href="${item.href}" class="rail-link ${item.key === activeKey ? "active" : ""}">
          <svg viewBox="0 0 24 24" fill="none">${item.icon}</svg>
          <span class="tooltip">${item.label}</span>
        </a>
      `).join("")}
    </div>
    <div class="rail-status" title="Backend status"></div>
  `;

  const topbar = document.createElement("div");
  topbar.className = "topbar";
  topbar.innerHTML = `
    <div class="topbar-title">
      <span class="eyebrow">${eyebrow || "LLMOPS OBSERVABILITY"}</span>
      <h1>${pageTitle}</h1>
    </div>
    <div class="search-box">
      <svg viewBox="0 0 24 24" fill="none"><circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="2"/><path d="m20 20-3-3" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
      <input type="text" placeholder="Search traces, prompts, or spans…" id="global-search" />
    </div>
    <div class="topbar-right">
      <button class="btn btn-ghost" id="api-key-btn" title="Set API key (optional)" style="padding:7px 10px;">🔑</button>
      <span class="status-pill" id="backend-status"><span class="dot"></span> Checking…</span>
    </div>
  `;

  const main = document.createElement("div");
  main.className = "main";
  main.appendChild(topbar);
  const content = document.createElement("div");
  content.className = "content";
  content.id = "page-content";
  main.appendChild(content);

  const shell = document.getElementById("app-shell");
  shell.appendChild(rail);
  shell.appendChild(main);

  // Global search: Enter key -> jump to traces.html?search=...
  const searchInput = document.getElementById("global-search");
  searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && searchInput.value.trim()) {
      window.location.href = `traces.html?search=${encodeURIComponent(searchInput.value.trim())}`;
    }
  });

  // API key popover (simple prompt-based, keeps this lightweight)
  document.getElementById("api-key-btn").addEventListener("click", () => {
    const current = getApiKey();
    const next = window.prompt(
      "API key (leave blank if your backend has no API_KEY set in .env):",
      current
    );
    if (next !== null) {
      setApiKey(next.trim());
      showToast(next.trim() ? "API key saved" : "API key cleared");
    }
  });

  checkHealth().then((ok) => {
    const pill = document.getElementById("backend-status");
    const dot = document.querySelector(".rail-status");
    if (ok) {
      pill.innerHTML = `<span class="dot"></span> All gateways online`;
      pill.classList.remove("offline");
    } else {
      pill.innerHTML = `<span class="dot"></span> Backend offline`;
      pill.classList.add("offline");
      dot.style.background = "var(--error)";
    }
  });

  return content;
}

const STAGE_LABELS = {
  prompt_builder: "Prompt Builder",
  tokenizer: "Tokenizer",
  llm_gateway: "LLM Gateway",
  llm_call: "LLM Call",
  response_parser: "Response Parser",
  evaluator: "Evaluator",
  cost_calculator: "Cost Calculator",
};
function stageLabel(name) { return STAGE_LABELS[name] || name; }

function renderDonut(container, data) {
  const total = data.reduce((s, d) => s + d.value, 0) || 1;
  const r = 42, cx = 50, cy = 50, circumference = 2 * Math.PI * r;
  let offset = 0;
  const segments = data.map((d) => {
    const frac = d.value / total;
    const dash = frac * circumference;
    const seg = `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${d.color}"
      stroke-width="12" stroke-dasharray="${dash} ${circumference - dash}"
      stroke-dashoffset="${-offset}" transform="rotate(-90 ${cx} ${cy})" stroke-linecap="butt"/>`;
    offset += dash;
    return seg;
  }).join("");
  container.innerHTML = `
    <svg viewBox="0 0 100 100" style="width:120px;height:120px;display:block;margin:0 auto;">
      <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="var(--line)" stroke-width="12"/>
      ${segments}
      <text x="50" y="47" text-anchor="middle" font-family="IBM Plex Mono" font-size="15" font-weight="600" fill="var(--ink-800)">${Math.round((data[0]?.value / total) * 100) || 0}%</text>
      <text x="50" y="60" text-anchor="middle" font-family="IBM Plex Mono" font-size="6" fill="var(--ink-400)">TOP MODEL</text>
    </svg>
    <div style="margin-top:12px;display:flex;flex-direction:column;gap:8px;">
      ${data.map(d => `
        <div style="display:flex;align-items:center;justify-content:space-between;font-size:12px;">
          <span style="display:flex;align-items:center;gap:7px;"><span style="width:8px;height:8px;border-radius:50%;background:${d.color};display:inline-block;"></span>${escapeHtml(d.label)}</span>
          <span class="mono" style="color:var(--ink-400);">${Math.round((d.value/total)*100)}%</span>
        </div>
      `).join("")}
    </div>
  `;
}

function renderBarChart(container, data, valueFmt) {
  const max = Math.max(...data.map(d => d.value), 0.001);
  container.innerHTML = `
    <div style="display:flex;align-items:flex-end;gap:6px;height:130px;padding:0 4px;">
      ${data.map(d => {
        const h = Math.max((d.value / max) * 100, 3);
        return `
          <div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:8px;height:100%;justify-content:flex-end;" title="${valueFmt(d.value)}">
            <div style="width:100%;max-width:26px;height:${h}%;background:var(--trace);border-radius:3px 3px 0 0;opacity:${d.value === max ? 1 : 0.55};transition:opacity .15s;"></div>
            <span class="mono" style="font-size:10px;color:var(--ink-400);">${escapeHtml(d.label)}</span>
          </div>`;
      }).join("")}
    </div>
  `;
}

function renderSparkline(container, values) {
  if (!values.length) { container.innerHTML = `<div class="empty-state" style="padding:20px;"><p>No data yet</p></div>`; return; }
  const w = 240, h = 60, pad = 6;
  const max = Math.max(...values, 1), min = Math.min(...values, 0);
  const range = max - min || 1;
  const step = (w - pad * 2) / Math.max(values.length - 1, 1);
  const pts = values.map((v, i) => {
    const x = pad + i * step;
    const y = h - pad - ((v - min) / range) * (h - pad * 2);
    return `${x},${y}`;
  });
  container.innerHTML = `
    <svg viewBox="0 0 ${w} ${h}" style="width:100%;height:60px;display:block;">
      <polyline points="${pts.join(" ")}" fill="none" stroke="var(--trace)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      ${pts.map(p => `<circle cx="${p.split(",")[0]}" cy="${p.split(",")[1]}" r="2.5" fill="var(--trace)"/>`).join("")}
    </svg>
  `;
}