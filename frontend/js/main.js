/**
 * main.js — shared utilities
 * EcoComply Regulatory Radar | IBM Bobathon 2025
 */

// ── API base: always use the ngrok HTTPS backend — works from any device/network
// ngrok gives the backend a valid HTTPS URL, eliminating mixed-content errors.
const API_BASE = "https://secluded-defacing-quiet.ngrok-free.dev/api";

// ── HTTP helpers ───────────────────────────────────────────────────────────────
// ngrok-skip-browser-warning bypasses the ngrok interstitial page for API calls
const _HEADERS = {
  "ngrok-skip-browser-warning": "true",
  "Content-Type": "application/json",
};

async function apiGet(path) {
  const r = await fetch(API_BASE + path, { headers: { "ngrok-skip-browser-warning": "true" } });
  if (!r.ok) throw new Error(`API ${path} → ${r.status}`);
  return r.json();
}

async function apiPost(path, body) {
  const r = await fetch(API_BASE + path, {
    method:  "POST",
    headers: _HEADERS,
    body:    JSON.stringify(body),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.error || `API ${path} → ${r.status}`);
  }
  return r.json();
}

async function apiPostForm(path, formData) {
  // Don't set Content-Type for FormData — browser sets it with boundary
  const r = await fetch(API_BASE + path, {
    method: "POST",
    body: formData,
    headers: { "ngrok-skip-browser-warning": "true" },
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.error || `API ${path} → ${r.status}`);
  }
  return r.json();
}

// ── Chip / badge helpers ───────────────────────────────────────────────────────
function urgencyChip(urgency) {
  const map = { critical:"chip chip-red", high:"chip chip-orange",
                medium:"chip chip-gray",  low:"chip chip-green" };
  return `<span class="${map[urgency]||'chip chip-gray'}">${(urgency||'').toUpperCase()}</span>`;
}

function statusChip(status) {
  const map = { sent:"chip chip-green", demo_sent:"chip chip-blue",
                dry_run:"chip chip-gray", failed:"chip chip-red" };
  return `<span class="${map[status]||'chip chip-gray'}">${(status||'').replace(/_/g,' ').toUpperCase()}</span>`;
}

function channelIcon(ch) {
  return { whatsapp:"💬", sms:"📱", email:"✉️" }[ch] || "📢";
}

function riskClass(level) {
  return { critical:"risk-critical", high:"risk-high",
           medium:"risk-medium",     low:"risk-low" }[level] || "risk-low";
}

function timeAgo(isoStr) {
  if (!isoStr) return "";
  const diff = Math.floor((Date.now() - new Date(isoStr)) / 1000);
  if (diff < 60)   return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400)return `${Math.floor(diff/3600)}h ago`;
  return new Date(isoStr).toLocaleDateString();
}

// ── Toast notifications ────────────────────────────────────────────────────────
function toast(msg, type = "info") {
  const el = document.createElement("div");
  el.textContent = msg;
  el.style.cssText = `
    position:fixed;bottom:20px;right:20px;z-index:9999;
    padding:12px 20px;border-radius:8px;font-size:14px;max-width:340px;
    background:${type==="error"?"#fee2e2":type==="success"?"#dcfce7":"#e0f2fe"};
    color:${type==="error"?"#dc2626":type==="success"?"#16a34a":"#0369a1"};
    border:1px solid ${type==="error"?"#fca5a5":type==="success"?"#86efac":"#7dd3fc"};
    box-shadow:0 4px 16px rgba(0,0,0,.1);
  `;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

// ── Language flag picker value ─────────────────────────────────────────────────
function getSelectedLanguage() {
  const el = document.getElementById("langSelect");
  return el ? el.value : "en";
}
