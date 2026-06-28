/**
 * findings.js — Compliance Findings Dashboard
 * Features: findings table, false-positive filtering, side panel with
 * product cards, LLM reasoning, source links, alert dispatch
 * EcoComply Regulatory Radar | IBM Bobathon 2025
 */

// ── State ──────────────────────────────────────────────────────────────────────
let _allFindings   = [];   // full unfiltered list (real + fp)
let _filteredFindings = [];
let _allPartners   = [];
let _selectedRow   = null;
let _selectedFinding = null;

// ── Boot ───────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  // Load partners in background for side panel
  try {
    const d = await apiGet("/partners/");
    _allPartners = d.partners || [];
  } catch {}

  // Populate regulation dropdown from API
  try {
    const d = await apiGet("/regulations/");
    const sel = document.getElementById("filterReg");
    const families = [...new Set((d.regulations || []).map(r => r.regulation_family).filter(Boolean))].sort();
    families.forEach(f => {
      const o = document.createElement("option");
      o.value = f; o.textContent = f;
      sel.appendChild(o);
    });
  } catch {}

  // Auto-load findings on page open (no LLM, fast)
  await loadFindings(false);
});

// ── Data loading ───────────────────────────────────────────────────────────────
async function loadFindings(useLLM = false) {
  showLoadingRows();
  showBanner(useLLM ? "🤖 Running HuggingFace LLM reasoning… (30-60s)" : "⚙️ Analysing portfolio…");

  try {
    const res = await apiPost("/findings/run", {
      use_llm:    useLLM,
      include_fp: true,
    });
    processFindings(res.findings || [], res.meta || {});
    hideBanner();
    if (useLLM) toast("LLM reasoning complete!", "success");
  } catch (e) {
    hideBanner();
    toast("Error: " + e.message, "error");
    clearLoadingRows();
  }
}

async function loadSampleDataset() {
  showLoadingRows();
  showBanner("📂 Loading EcoComply sample dataset…");
  document.getElementById("btnLoadSample").disabled = true;

  try {
    const res = await apiPost("/findings/load-sample", {});
    const all = await apiGet("/findings/?include_fp=true");
    processFindings(all.findings || [], all.meta || {});
    toast(res.message || "Sample dataset loaded!", "success");
  } catch (e) {
    toast("Error: " + e.message, "error");
    clearLoadingRows();
  } finally {
    hideBanner();
    document.getElementById("btnLoadSample").disabled = false;
  }
}

async function runWithLLM() {
  const btn = document.getElementById("btnRunLLM");
  btn.disabled = true;
  btn.textContent = "🤖 Thinking…";
  await loadFindings(true);
  btn.disabled = false;
  btn.textContent = "🤖 Run + LLM Reasoning";
}

async function runScrape() {
  const btn = document.getElementById("btnScrape");
  btn.disabled = true;
  btn.textContent = "🌐 Scraping…";
  showBanner("🌐 Scraping EUR-Lex, ECHA, Safety Gate…");
  try {
    const res = await apiPost("/findings/scrape/run", {});
    const msg = `Scraped ${res.total_items} items from ${Object.keys(res.by_source||{}).length} sources`;
    toast(msg, "success");
  } catch (e) {
    toast("Scrape error: " + e.message, "error");
  } finally {
    hideBanner();
    btn.disabled = false;
    btn.textContent = "🌐 Live Scrape";
  }
}

async function runAlertDispatch() {
  const real = _allFindings.filter(f => !f.is_false_positive);
  if (!real.length) { toast("No findings to dispatch", "error"); return; }
  toast(`Dispatching alerts for ${real.length} findings…`, "info");
  // Delegate to pipeline
  try {
    const res = await apiPost("/pipeline/run", { send_alerts: true, channels: ["email"] });
    toast(`Pipeline complete: ${res.summary?.total_alerts_sent || 0} alerts sent`, "success");
  } catch (e) {
    toast("Dispatch error: " + e.message, "error");
  }
}

// ── Process & render ───────────────────────────────────────────────────────────
function processFindings(findings, meta) {
  _allFindings = findings;

  // Populate company dropdown
  const compSel = document.getElementById("filterCompany");
  compSel.innerHTML = '<option value="">All</option>';
  const seen = new Set();
  findings.forEach(f => {
    if (!f.is_false_positive && !seen.has(f.partner_id)) {
      seen.add(f.partner_id);
      const o = document.createElement("option");
      o.value = f.partner_id;
      o.textContent = f.company;
      compSel.appendChild(o);
    }
  });

  // Show dispatch button once we have data
  if (findings.filter(f => !f.is_false_positive).length > 0) {
    document.getElementById("btnDispatch").style.display = "inline-flex";
  }

  applyFilters();
}

function applyFilters() {
  const sev      = document.getElementById("filterSev").value;
  const reg      = document.getElementById("filterReg").value;
  const company  = document.getElementById("filterCompany").value;
  const showFP   = document.getElementById("showFP").checked;

  _filteredFindings = _allFindings.filter(f => {
    if (!showFP && f.is_false_positive) return false;
    if (sev     && f.severity !== sev)  return false;
    if (reg     && f.regulation_family !== reg) return false;
    if (company && f.partner_id !== company)    return false;
    return true;
  });

  updateKPIs();
  renderTable(_filteredFindings);
  document.getElementById("filterCount").textContent =
    `${_filteredFindings.filter(f => !f.is_false_positive).length} findings`;
}

function updateKPIs() {
  const real   = _allFindings.filter(f => !f.is_false_positive);
  const fps    = _allFindings.filter(f =>  f.is_false_positive);
  document.getElementById("fKpiTotal").textContent = real.length;
  document.getElementById("fKpiHigh").textContent  = real.filter(f => f.severity === "high").length;
  document.getElementById("fKpiMed").textContent   = real.filter(f => f.severity === "medium").length;
  document.getElementById("fKpiLow").textContent   = real.filter(f => f.severity === "low").length;
  document.getElementById("fKpiFP").textContent    = fps.length;
}

// ── Table rendering ────────────────────────────────────────────────────────────
function renderTable(findings) {
  const tbody = document.getElementById("fTableBody");

  if (!findings.length) {
    tbody.innerHTML = `<tr><td colspan="7" class="f-empty-row">
      <div class="f-empty-state">
        <div style="font-size:28px;margin-bottom:8px;">✅</div>
        <strong>No findings match current filters</strong>
        <p>Try adjusting the severity or company filter, or toggle "Show False Positives".</p>
      </div>
    </td></tr>`;
    return;
  }

  tbody.innerHTML = findings.map((f, idx) => {
    const isFP      = f.is_false_positive;
    const rowClass  = [
      isFP ? "is-fp" : `sev-${f.severity}`,
      _selectedFinding && _selectedFinding._idx === idx ? "selected" : ""
    ].filter(Boolean).join(" ");

    const deadlineHtml = formatDeadline(f.deadline, f.days_left);
    const regChip = `<span class="f-reg-chip${isFP ? " fp" : ""}">${escHtml(f.regulation_title || f.regulation || "")}</span>`;
    const sevBadge = isFP
      ? `<span class="f-sev-badge fp">FALSE +</span>`
      : `<span class="f-sev-badge ${f.severity}">${(f.severity||"").toUpperCase()}</span>`;

    const gapText = isFP
      ? `<span class="f-gap-fp">✓ Not applicable — ${escHtml((f.false_positive_reason||"").slice(0,100))}</span>`
      : `<span class="f-gap-text">${escHtml((f.gap||"").slice(0,120))}${(f.gap||"").length>120?"…":""}</span>`;

    const actionText = isFP ? "—"
      : `<span class="f-action-text">${escHtml((f.recommended_action||"").slice(0,80))}${(f.recommended_action||"").length>80?"…":""}</span>`;

    const sourceHtml = f.source_url && f.source_url !== "#"
      ? `<a class="f-source-link" href="${escHtml(f.source_url)}" target="_blank" rel="noopener"
            onclick="event.stopPropagation()">${sourceLabel(f.source_url)}</a>`
      : `<span style="color:var(--muted);font-size:12px;">—</span>`;

    return `<tr class="${rowClass}" data-idx="${idx}" onclick="selectFinding(${idx})">
      <td>
        <div class="f-company-name" onclick="event.stopPropagation();selectCompany('${escHtml(f.partner_id)}')">${escHtml(f.company)}</div>
        <div class="f-product-sub">${escHtml(f.product_id)} · ${escHtml(f.product)}</div>
      </td>
      <td>${regChip}</td>
      <td>${gapText}</td>
      <td>${sevBadge}</td>
      <td>${deadlineHtml}</td>
      <td>${actionText}</td>
      <td>${sourceHtml}</td>
    </tr>`;
  }).join("");
}

function formatDeadline(deadline, daysLeft) {
  if (!deadline) return `<span class="f-deadline ok">TBD</span>`;
  let cls = "ok";
  if (daysLeft !== null && daysLeft !== undefined) {
    if (daysLeft < 0)   cls = "overdue";
    else if (daysLeft < 180) cls = "soon";
  }
  return `<span class="f-deadline ${cls}">${escHtml(deadline)}</span>`;
}

function sourceLabel(url) {
  if (!url) return "—";
  if (url.includes("eur-lex"))       return "eur-lex.europa.eu";
  if (url.includes("echa.europa"))   return "echa.europa.eu";
  if (url.includes("safety-gate"))   return "safety-gate";
  if (url.includes("single-market")) return "ec.europa.eu";
  try { return new URL(url).hostname.replace("www.",""); } catch { return "source"; }
}

// ── Side panel ─────────────────────────────────────────────────────────────────
function selectFinding(idx) {
  _selectedFinding = { ..._filteredFindings[idx], _idx: idx };

  // Highlight selected row
  document.querySelectorAll("#fTableBody tr").forEach((r, i) => {
    r.classList.toggle("selected", i === idx);
  });

  openSidePanel(_selectedFinding);
}

function selectCompany(partnerId) {
  document.getElementById("filterCompany").value = partnerId;
  applyFilters();
}

function openSidePanel(finding) {
  const panel   = document.getElementById("fSidePanel");
  const content = document.getElementById("fSidePanelContent");
  panel.classList.add("open");

  // Find partner data
  const partner = _allPartners.find(p => p.id === finding.partner_id) || {};
  const products = partner.products || [];

  // Build product cards
  const productCards = products.map(prod => {
    // Get all findings for this product
    const prodFindings = _allFindings.filter(f =>
      f.product_id === prod.product_id && !f.is_false_positive
    );

    const tagItems = [
      `cat: ${prod.category}`,
      `use: ${prod.intended_use}`,
      prod.has_battery ? `battery: ${prod.battery_type} ${prod.battery_capacity_wh}Wh` : null,
      prod.connector && prod.connector !== "none" ? `connector: ${prod.connector}` : null,
      prod.has_radio ? "radio: yes" : null,
      (prod.packaging||[]).length ? `pkg: ${prod.packaging.join(", ")}` : null,
    ].filter(Boolean);

    const findingRows = prodFindings.length === 0
      ? `<p class="sp-no-findings">✓ No active findings for this product.</p>`
      : prodFindings.map(f => `
          <div class="sp-finding-row sev-${f.severity}">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">
              <strong style="font-size:12px;">${escHtml(f.regulation_title||"")}</strong>
              <span class="f-sev-badge ${f.severity}" style="flex-shrink:0;">${f.severity.toUpperCase()}</span>
            </div>
            <div style="font-size:12px;color:var(--orange);font-weight:600;margin-top:2px;">
              📅 ${f.deadline||"TBD"}
            </div>
            <div style="font-size:12px;color:var(--muted);margin-top:2px;">${escHtml((f.gap||"").slice(0,120))}</div>
            ${f.llm_reasoning && f.llm_reasoning !== f.gap ? `
              <div class="sp-llm-block" style="margin-top:6px;">
                <div class="sp-llm-label">🤖 LLM Analysis</div>
                ${escHtml(f.llm_reasoning)}
              </div>` : ""}
            <a class="sp-source-btn" href="${escHtml(f.source_url||"#")}" target="_blank" rel="noopener">
              📄 Open compliance rule
            </a>
          </div>`).join("");

    const badgeCount = prodFindings.length > 0
      ? `<span style="background:var(--red);color:#fff;font-size:10px;font-weight:700;
             padding:2px 7px;border-radius:10px;">${prodFindings.length} ${prodFindings.length===1?"FINDING":"FINDINGS"}</span>`
      : `<span style="color:var(--green);font-size:11px;font-weight:600;">✓ No findings</span>`;

    return `
      <div class="sp-product-card">
        <div class="sp-product-header">
          <div>
            <div class="sp-product-name">${escHtml(prod.name)}</div>
            <div class="sp-product-id">${escHtml(prod.product_id)}</div>
          </div>
          ${badgeCount}
        </div>
        <div class="sp-product-tags">${tagItems.map(t=>`<span class="sp-tag">${escHtml(t)}</span>`).join("")}</div>
        <div class="sp-findings-on-product">${findingRows}</div>
      </div>`;
  }).join("") || `<p class="loading-msg">No product detail available.</p>`;

  // Build full panel
  const pref = partner.preferred_channel || finding.preferred_channel || "email";
  content.innerHTML = `
    <div class="sp-company">${escHtml(finding.company)}</div>
    <div class="sp-sub">${escHtml(finding.partner_id)} · HQ: ${escHtml(partner.country||"")} · Sells in: ${(partner.sells_in||["EU"]).join(", ")}</div>

    <div class="sp-contact">
      <div class="sp-contact-row">
        <span style="font-size:14px;">👤</span>
        <span class="sp-contact-label">Contact</span>
        <span class="sp-contact-val">${escHtml(partner.contact_name||finding.company)}</span>
      </div>
      <div class="sp-contact-row">
        <span style="font-size:14px;">✉️</span>
        <span class="sp-contact-label">Email</span>
        <span class="sp-contact-val" style="font-size:12px;">${escHtml(partner.email||finding.contact_email||"—")}</span>
      </div>
      <div class="sp-contact-row">
        <span style="font-size:14px;">📱</span>
        <span class="sp-contact-label">Phone</span>
        <span class="sp-contact-val">${escHtml(partner.phone||finding.contact_phone||"—")}</span>
      </div>
      <div class="sp-contact-row">
        <span style="font-size:14px;">📢</span>
        <span class="sp-contact-label">Preferred</span>
        <span class="sp-contact-val">${escHtml(pref)}</span>
      </div>
    </div>

    <div class="sp-products">
      ${productCards}
    </div>
  `;
}

function closeSidePanel() {
  document.getElementById("fSidePanel").classList.remove("open");
  _selectedFinding = null;
  document.querySelectorAll("#fTableBody tr.selected").forEach(r => r.classList.remove("selected"));
}

// ── Loading helpers ────────────────────────────────────────────────────────────
function showLoadingRows() {
  const tbody = document.getElementById("fTableBody");
  tbody.innerHTML = Array(8).fill(0).map(() => `
    <tr class="f-shimmer">
      <td style="height:14px;"></td><td></td><td></td><td></td><td></td><td></td><td></td>
    </tr>`).join("");
}

function clearLoadingRows() {
  const tbody = document.getElementById("fTableBody");
  tbody.innerHTML = `<tr><td colspan="7" class="f-empty-row">
    <div class="f-empty-state">
      <div style="font-size:28px;margin-bottom:8px;">⚠️</div>
      <strong>Failed to load findings</strong>
      <p>Check that the backend is running at <code>${API_BASE}</code></p>
    </div>
  </td></tr>`;
}

function showBanner(msg) {
  const b = document.getElementById("fLLMBanner");
  document.getElementById("fLLMBannerText").textContent = msg;
  b.classList.remove("hidden");
}
function hideBanner() {
  document.getElementById("fLLMBanner").classList.add("hidden");
}

// ── Utility ────────────────────────────────────────────────────────────────────
function escHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
