/**
 * dashboard.js — full compliance dashboard with partner selector,
 * fix suggestions, portfolio risk, ack tracking, multi-language alerts
 * EcoComply Regulatory Radar | IBM Bobathon 2025
 */

let _allPartners = [];
let _selectedPartner = null;
let _riskMap = {};

// ── Boot ───────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  await Promise.all([loadPartners(), loadRegulations(), loadAlertLog(), loadPortfolioRisk(), loadFindings()]);
  // Live monitor loads after primary content (it polls external feeds — may be slower)
  loadLiveMonitor();
  // Auto-refresh live monitor every 90 seconds
  setInterval(loadLiveMonitor, 90_000);
});

// ── Load partners + build quick-selector ──────────────────────────────────────
async function loadPartners() {
  try {
    const data = await apiGet("/partners/");
    _allPartners = data.partners || [];

    // Load risk levels in parallel
    await Promise.all(_allPartners.map(async p => {
      try {
        const r = await apiGet(`/partners/${p.id}/risk`);
        _riskMap[p.id] = r.risk?.risk_level || "low";
      } catch { _riskMap[p.id] = "low"; }
    }));

    // Update KPIs
    const levels = Object.values(_riskMap);
    document.getElementById("kpiPartners").textContent  = _allPartners.length;
    document.getElementById("kpiCritical").textContent  = levels.filter(l => l === "critical").length;
    document.getElementById("kpiHigh").textContent      = levels.filter(l => l === "high").length;
    document.getElementById("kpiCompliant").textContent = levels.filter(l => l === "low").length;

    // Sort by risk
    const order = { critical:0, high:1, medium:2, low:3 };
    _allPartners.sort((a,b) => (order[_riskMap[a.id]]||3) - (order[_riskMap[b.id]]||3));

    buildPartnerSelector();

    // Auto-select Company X demo = SME001 (AlphaVolt GmbH) for live demo
    if (_allPartners.length) selectPartner(_allPartners[0].id);

  } catch(e) {
    document.getElementById("partnerQuickBtns").innerHTML =
      `<p class="loading-msg" style="color:var(--red)">Failed: ${e.message}</p>`;
  }
}

function buildPartnerSelector() {
  const wrap = document.getElementById("partnerQuickBtns");
  wrap.innerHTML = _allPartners.map(p => `
    <button class="pq-btn ${riskClass(_riskMap[p.id])}" id="pqb-${p.id}"
            onclick="selectPartner('${p.id}')">
      <span class="pq-name">${p.company_name}</span>
      <span class="pq-sector">${p.sector} · ${p.country}</span>
      <span class="pq-risk">● ${(_riskMap[p.id]||'low').toUpperCase()}</span>
    </button>
  `).join("") + `
    <button class="pq-btn" style="border-style:dashed;color:var(--accent);"
            onclick="window.location='onboard.html'">
      <span class="pq-name">+ Add your company</span>
      <span class="pq-sector">Live onboarding</span>
    </button>`;
}

// ── Select & inspect a partner ─────────────────────────────────────────────────
async function selectPartner(pid) {
  // Highlight selected button
  document.querySelectorAll(".pq-btn").forEach(b => b.classList.remove("active"));
  const btn = document.getElementById(`pqb-${pid}`);
  if (btn) btn.classList.add("active");

  _selectedPartner = pid;
  const card    = document.getElementById("partnerDetail");
  const content = document.getElementById("partnerDetailContent");
  card.classList.remove("hidden");
  content.innerHTML = `<p class="loading-msg">Loading ${pid}…</p>`;
  card.scrollIntoView({ behavior:"smooth", block:"nearest" });

  try {
    const [pData, riskData, matchData] = await Promise.all([
      apiGet(`/partners/${pid}`),
      apiGet(`/partners/${pid}/risk`),
      apiGet(`/partners/${pid}/matches`),
    ]);

    const p       = pData;
    const risk    = riskData.risk || {};
    const level   = risk.risk_level || "low";
    const matches = matchData.matches || [];

    content.innerHTML = `
      <div class="pd-header">
        <div>
          <div class="pd-title">${p.company_name}</div>
          <div class="pd-sub">${p.sector} · ${p.country} · ${p.employees||'?'} employees</div>
        </div>
        <span class="risk-badge ${level}" style="flex-shrink:0;">${level.toUpperCase()} RISK — Score ${risk.risk_score||0}/100</span>
      </div>

      <div class="pd-meta">
        <div><strong>Contact:</strong> ${p.contact_name}</div>
        <div><strong>Email:</strong> ${p.email||'—'}</div>
        <div><strong>Phone:</strong> ${p.phone||'—'}</div>
        <div><strong>Certifications:</strong> ${(p.certifications||[]).join(', ')||'—'}</div>
      </div>

      <div style="background:var(--surface);border-radius:8px;padding:12px 14px;font-size:13px;margin-bottom:16px;">
        ${risk.summary || 'No risk summary available.'}
      </div>

      <!-- Tabs -->
      <div class="pd-tabs">
        <button class="pd-tab active" onclick="switchTab('matches','${pid}')">📋 Regulations (${matches.length})</button>
        <button class="pd-tab" onclick="switchTab('fix','${pid}')">🔧 Fix Suggestions</button>
        <button class="pd-tab" onclick="switchTab('alert','${pid}')">📲 Send Alert</button>
      </div>

      <!-- Tab: Regulations matches -->
      <div class="pd-pane active" id="tab-matches">
        ${matches.length ? matches.map(m => `
          <div class="reg-list-item" style="margin-bottom:10px;">
            <div class="reg-urgency-dot urgency-${m.regulation?.urgency||'low'}"></div>
            <div style="flex:1;">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <strong style="font-size:14px;">${m.regulation?.short_name||''}</strong>
                <span class="chip chip-blue">Score: ${m.score}</span>
              </div>
              <div style="font-size:12px;color:var(--muted);">${(m.match_reasons||[]).join(' · ')}</div>
              <div style="font-size:12px;font-weight:600;color:var(--orange);margin-top:3px;">📅 ${m.regulation?.deadline_date||'TBD'}</div>
            </div>
          </div>`) .join('') : '<p class="loading-msg">No regulations matched this profile.</p>'}
      </div>

      <!-- Tab: Fix suggestions (loaded on click) -->
      <div class="pd-pane" id="tab-fix">
        <div id="fixContent-${pid}"><p class="loading-msg">Click "Fix Suggestions" tab to load…</p></div>
      </div>

      <!-- Tab: Send alert -->
      <div class="pd-pane" id="tab-alert">
        <div class="alert-send-form">
          <h3>Send a live compliance alert</h3>
          <div class="field-row" style="margin-bottom:12px;">
            <div class="field-group">
              <label class="field-label">Regulation</label>
              <select id="alertRegSelect-${pid}" class="field-input">
                ${matches.map(m => `<option value="${m.regulation?.id}">${m.regulation?.short_name} (score ${m.score})</option>`).join('')}
              </select>
            </div>
            <div class="field-group">
              <label class="field-label">Channel</label>
              <div class="checkbox-row" style="margin-top:6px;">
                <label class="checkbox-label"><input type="checkbox" name="aChannel-${pid}" value="whatsapp"/> 💬 WhatsApp</label>
                <label class="checkbox-label"><input type="checkbox" name="aChannel-${pid}" value="sms"/> 📱 SMS</label>
                <label class="checkbox-label"><input type="checkbox" name="aChannel-${pid}" value="email" checked/> ✉️ Email</label>
              </div>
            </div>
            <div class="field-group">
              <label class="field-label">Language</label>
              <select id="alertLang-${pid}" class="field-input">
                <option value="en">🇬🇧 English</option>
                <option value="de">🇩🇪 Deutsch</option>
                <option value="fr">🇫🇷 Français</option>
                <option value="es">🇪🇸 Español</option>
                <option value="it">🇮🇹 Italiano</option>
                <option value="pl">🇵🇱 Polski</option>
              </select>
            </div>
            <div class="field-group" style="align-self:flex-end;">
              <button class="btn btn-primary" onclick="sendPartnerAlert('${pid}')">⚡ Send Alert</button>
            </div>
          </div>
          <div id="alertResult-${pid}"></div>
        </div>
      </div>
    `;

    // Pre-load fix suggestions
    loadFixSuggestions(pid, matches);

  } catch(e) {
    content.innerHTML = `<p style="color:var(--red)">Error: ${e.message}</p>`;
  }
}

function switchTab(name, pid) {
  document.querySelectorAll(".pd-tab").forEach((t,i) => {
    const names = ["matches","fix","alert"];
    t.classList.toggle("active", names[i] === name);
  });
  document.querySelectorAll(".pd-pane").forEach((p,i) => {
    const names = ["matches","fix","alert"];
    p.classList.toggle("active", names[i] === name);
  });
}

async function loadFixSuggestions(pid, matches) {
  const el = document.getElementById(`fixContent-${pid}`);
  if (!el || !matches.length) return;

  const fixes = [];
  for (const m of matches.slice(0, 4)) {
    try {
      const f = await apiGet(`/alerts/fix/${pid}/${m.regulation?.id}`);
      fixes.push(f);
    } catch {}
  }

  if (!fixes.length) { el.innerHTML = '<p class="loading-msg">No fix data available.</p>'; return; }

  fixes.sort((a,b) => b.priority_score - a.priority_score);

  el.innerHTML = fixes.map(f => `
    <div style="border:1px solid var(--border);border-radius:8px;padding:14px;margin-bottom:12px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
        <strong style="font-size:14px;">${f.regulation}</strong>
        ${urgencyChip(f.urgency)}
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;font-size:12px;margin-bottom:10px;">
        <div style="background:var(--surface);padding:8px;border-radius:6px;text-align:center;">
          <div style="font-weight:700;font-size:16px;color:var(--accent);">${f.priority_score}</div>
          <div style="color:var(--muted);">Priority</div>
        </div>
        <div style="background:var(--surface);padding:8px;border-radius:6px;text-align:center;">
          <div style="font-weight:700;font-size:16px;color:var(--red);">€${f.estimated_fine_eur.toLocaleString()}</div>
          <div style="color:var(--muted);">Est. Exposure</div>
        </div>
        <div style="background:var(--surface);padding:8px;border-radius:6px;text-align:center;">
          <div style="font-weight:700;font-size:16px;color:${f.days_to_deadline < 180 ? 'var(--orange)':'var(--muted)'};">${f.days_to_deadline ?? '?'}</div>
          <div style="color:var(--muted);">Days left</div>
        </div>
      </div>
      <div class="priority-bar"><div class="priority-fill pf-${f.urgency}" style="width:${f.priority_score}%"></div></div>
      <div style="margin-top:10px;font-size:13px;background:#f0f4ff;border-left:3px solid var(--accent);padding:8px 12px;border-radius:0 6px 6px 0;">
        💡 <strong>Immediate action:</strong> ${f.immediate_action}
      </div>
      <div class="fix-step-list">
        ${(f.fix_steps||[]).map(s => `
          <div class="fix-step">
            <div class="fix-step-n">${s.step}</div>
            <div class="fix-step-body">
              <div class="fix-step-action">${s.action}</div>
              <div class="fix-step-meta">Owner: ${s.owner} · Effort: ${s.effort}</div>
            </div>
          </div>`).join('')}
      </div>
    </div>`).join('');
}

// ── Send a live alert from the detail panel ────────────────────────────────────
async function sendPartnerAlert(pid) {
  const regId    = document.getElementById(`alertRegSelect-${pid}`)?.value;
  const langEl   = document.getElementById(`alertLang-${pid}`);
  const language = langEl?.value || "en";
  const channels = Array.from(document.querySelectorAll(`[name="aChannel-${pid}"]:checked`))
                        .map(c => c.value);
  const resultEl = document.getElementById(`alertResult-${pid}`);

  if (!regId)           { toast("Please select a regulation", "error"); return; }
  if (!channels.length) { toast("Select at least one channel", "error"); return; }

  resultEl.innerHTML = `<p class="loading-msg">Sending…</p>`;
  try {
    const res = await apiPost("/alerts/send", {
      partner_id: pid, regulation_id: regId, channels, language
    });
    const results = res.send_results || [];
    const ok      = results.filter(r => ["sent","demo_sent"].includes(r.status));
    const failed  = results.filter(r => r.status === "failed");

    resultEl.innerHTML = `
      <div style="margin-top:12px;">
        ${ok.map(r => `
          <div class="alert-item" style="background:#f0fdf4;border-color:var(--green);margin-bottom:6px;">
            <div class="alert-icon">${channelIcon(r.channel)}</div>
            <div>
              <div style="font-size:13px;font-weight:600;color:var(--green);">
                ${r.status === 'sent' ? '✅ Delivered' : '🔵 Demo Sent'} via ${r.channel.toUpperCase()}
              </div>
              <div style="font-size:12px;color:var(--muted);">${r.to||''}</div>
            </div>
          </div>`).join('')}
        ${failed.map(r => `
          <div class="alert-item" style="background:#fef2f2;border-color:var(--red);margin-bottom:6px;">
            <div class="alert-icon">❌</div>
            <div>
              <div style="font-size:13px;font-weight:600;color:var(--red);">Failed — ${r.channel}</div>
              <div style="font-size:12px;color:var(--muted);">${r.error||''}</div>
            </div>
          </div>`).join('')}
        <div style="font-size:12px;font-style:italic;color:var(--muted);margin-top:8px;padding:8px;background:var(--surface);border-radius:6px;">
          "${(res.message||'').slice(0,200)}…"
        </div>
      </div>`;

    if (ok.length) {
      toast(`Alert sent! ${ok.map(r=>r.channel).join(', ')}`, "success");
      setTimeout(() => refreshAlertLog(), 800);
    } else if (failed.length) {
      toast(failed[0].error?.slice(0,80) || "Send failed", "error");
    }
  } catch(e) {
    resultEl.innerHTML = `<p style="color:var(--red)">Error: ${e.message}</p>`;
    toast(e.message, "error");
  }
}

// ── Portfolio risk financial dashboard ────────────────────────────────────────
async function loadPortfolioRisk() {
  const el = document.getElementById("riskDashboard");
  try {
    const data = await apiGet("/partners/portfolio-risk");
    document.getElementById("kpiExposure").textContent =
      `€${Math.round(data.total_exposure_eur/1000)}k`;

    const rows = (data.report || []).map(r => {
      const topFix = r.fixes?.[0];
      return `
        <tr class="risk-row-${r.risk_level}" onclick="selectPartner('${r.partner_id}')" style="cursor:pointer;">
          <td><strong>${r.company_name}</strong><br><span style="font-size:11px;color:var(--muted);">${r.sector} · ${r.country}</span></td>
          <td>${urgencyChip(r.risk_level)}</td>
          <td><div style="font-size:13px;">${r.regulations_matched}</div></td>
          <td class="exposure">€${r.total_exposure_eur.toLocaleString()}</td>
          <td>
            <div class="priority-bar" style="width:100px;">
              <div class="priority-fill pf-${r.risk_level}" style="width:${r.max_priority_score}%"></div>
            </div>
            <div style="font-size:11px;color:var(--muted);margin-top:2px;">${r.max_priority_score}/100</div>
          </td>
          <td style="font-size:12px;color:var(--muted);">${topFix?.immediate_action?.slice(0,60)||'—'}…</td>
        </tr>`;
    }).join('');

    el.innerHTML = `
      <div style="display:flex;gap:16px;margin-bottom:14px;font-size:13px;flex-wrap:wrap;">
        <div style="background:#fee2e2;color:var(--red);padding:8px 14px;border-radius:8px;font-weight:600;">
          🔴 ${(data.report||[]).filter(r=>r.risk_level==='critical').length} Critical
        </div>
        <div style="background:#fef3c7;color:var(--orange);padding:8px 14px;border-radius:8px;font-weight:600;">
          🟠 ${(data.report||[]).filter(r=>r.risk_level==='high').length} High
        </div>
        <div style="background:#e8f0fe;color:var(--accent);padding:8px 14px;border-radius:8px;font-weight:600;">
          💶 Total exposure: <strong>€${data.total_exposure_eur.toLocaleString()}</strong>
        </div>
      </div>
      <div class="risk-table-wrap">
        <table class="risk-table">
          <thead><tr>
            <th>Partner</th><th>Risk</th><th>Regs</th>
            <th>Est. Exposure</th><th>Priority</th><th>Top Action</th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      <p style="font-size:11px;color:var(--muted);margin-top:8px;">
        Click any row to inspect the partner's full risk profile. Exposure is estimated based on revenue and urgency. Not legal advice.
      </p>`;
  } catch(e) {
    el.innerHTML = `<p style="color:var(--red)">Failed to load risk data: ${e.message}</p>`;
  }
}

// ── Regulations list ───────────────────────────────────────────────────────────
async function loadRegulations() {
  const list = document.getElementById("regList");
  try {
    const data = await apiGet("/regulations/");
    const regs = data.regulations || [];
    document.getElementById("regCount").textContent = regs.length;
    list.innerHTML = regs.map(r => `
      <div class="reg-list-item">
        <div class="reg-urgency-dot urgency-${r.urgency||'low'}"></div>
        <div>
          <div class="reg-list-title">${r.short_name||r.title}</div>
          <div class="reg-list-meta">${r.regulation_number||''}</div>
          <div class="reg-list-deadline">📅 ${r.deadline_date||'TBD'}</div>
        </div>
        ${urgencyChip(r.urgency)}
      </div>`).join('');
  } catch(e) {
    list.innerHTML = `<p class="loading-msg" style="color:var(--red)">${e.message}</p>`;
  }
}

// ── Alert log with ack ────────────────────────────────────────────────────────
async function refreshAlertLog() { await loadAlertLog(); }

async function loadAlertLog() {
  const list = document.getElementById("alertLogList");
  try {
    const data   = await apiGet("/alerts/log");
    const alerts = data.alerts || [];
    if (!alerts.length) {
      list.innerHTML = "<p class='loading-msg'>No alerts yet.</p>";
      return;
    }
    list.innerHTML = alerts.slice(0, 20).map(a => `
      <div class="alert-log-item status-${a.status}">
        <div class="log-header">
          <span class="log-title">${channelIcon(a.channel)} ${a.partner_id} → ${a.regulation_id}</span>
          <span class="log-time">${timeAgo(a.timestamp)}</span>
        </div>
        <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:3px 0;">
          <span class="log-channel">${a.channel}</span>
          ${statusChip(a.status)}
          ${a.language && a.language !== 'en' ? `<span class="chip chip-gray">${a.language.toUpperCase()}</span>` : ''}
          ${a.acknowledged
            ? `<span class="acked-badge">✓ Acknowledged</span>`
            : `<button class="ack-btn" onclick="ackAlert('${a.alert_id}', this)">Mark read</button>`}
        </div>
        ${a.message_preview ? `<div class="log-preview">"${a.message_preview}"</div>` : ''}
      </div>`).join('');
  } catch(e) {
    list.innerHTML = `<p class="loading-msg" style="color:var(--red)">${e.message}</p>`;
  }
}

async function ackAlert(alertId, btn) {
  try {
    await apiPost(`/alerts/${alertId}/acknowledge`, {});
    btn.replaceWith(Object.assign(document.createElement("span"), {
      className: "acked-badge", textContent: "✓ Acknowledged"
    }));
  } catch(e) {
    toast("Could not acknowledge: " + e.message, "error");
  }
}

// ── Compliance Findings (inline dashboard section) ────────────────────────────
let _allFindings = [];

// Called on boot and by Refresh button
async function loadFindings() {
  const wrap = document.getElementById("findingsTableWrap");
  if (!wrap) return;
  wrap.innerHTML = `<div class="loading-msg">Running compliance engine…</div>`;
  try {
    const data = await apiGet("/findings/?include_fp=true");
    _allFindings = data.findings || [];

    // Populate regulation filter dropdown (API field: regulation_title)
    const regSel = document.getElementById("fRegFilter");
    if (regSel) {
      const regs = [...new Set(_allFindings.map(f => f.regulation_title || f.regulation_id).filter(Boolean))].sort();
      const existing = Array.from(regSel.options).map(o => o.value);
      regs.forEach(r => {
        if (!existing.includes(r)) {
          const opt = document.createElement("option");
          opt.value = r; opt.textContent = r.length > 50 ? r.slice(0,48)+"…" : r;
          regSel.appendChild(opt);
        }
      });
    }

    // Populate company filter dropdown (API field: company)
    const coSel = document.getElementById("fCoFilter");
    if (coSel) {
      const cos = [...new Set(_allFindings.map(f => f.company).filter(Boolean))].sort();
      const existing = Array.from(coSel.options).map(o => o.value);
      cos.forEach(c => {
        if (!existing.includes(c)) {
          const opt = document.createElement("option");
          opt.value = c; opt.textContent = c;
          coSel.appendChild(opt);
        }
      });
    }

    renderFindingsTable();
  } catch(e) {
    wrap.innerHTML = `<p style="color:var(--red);font-size:13px;">⚠ Could not load findings: ${e.message}</p>`;
  }
}

function renderFindingsTable() {
  const wrap    = document.getElementById("findingsTableWrap");
  const showFP  = document.getElementById("showFPDash")?.checked || false;
  const sevF    = document.getElementById("fSevFilter")?.value   || "";
  const regF    = document.getElementById("fRegFilter")?.value   || "";
  const coF     = document.getElementById("fCoFilter")?.value    || "";

  let rows = _allFindings.filter(f => {
    if (!showFP && f.is_false_positive) return false;
    if (sevF && f.severity !== sevF)    return false;
    if (regF && (f.regulation_title || f.regulation_id) !== regF) return false;
    if (coF  && f.company !== coF) return false;
    return true;
  });

  // Sort by deadline (earliest first; nulls last)
  rows.sort((a, b) => {
    if (!a.deadline && !b.deadline) return 0;
    if (!a.deadline) return 1;
    if (!b.deadline) return -1;
    return new Date(a.deadline) - new Date(b.deadline);
  });

  const count = rows.length;
  const badge = document.getElementById("findingsCount");
  if (badge) badge.textContent = `${count} finding${count !== 1 ? "s" : ""}`;

  if (!rows.length) {
    wrap.innerHTML = `<p class="loading-msg">No findings match the current filters.</p>`;
    return;
  }

  const sevColor = { high:"var(--red)", medium:"var(--orange)", low:"var(--accent)" };
  const sevBg    = { high:"#fee2e2",    medium:"#fef3c7",       low:"#e0f2fe" };

  const tableRows = rows.map((f, i) => {
    // Normalise field names (API uses: company, gap, regulation_title, false_positive_reason)
    const company  = f.company      || f.company_name  || f.partner_id || "—";
    const gapText  = f.gap          || f.gap_description || "—";
    const regTitle = f.regulation_title || f.regulation_short_name || f.regulation_id || "—";
    const fpReason = f.false_positive_reason || f.fp_reason || "";

    const fpTag = f.is_false_positive
      ? `<span class="chip chip-gray" style="font-size:10px;">FP</span> ` : "";
    const sev   = f.severity || "low";
    const srcLink = f.source_url
      ? `<a href="${f.source_url}" target="_blank" rel="noopener"
             style="color:var(--accent);font-size:12px;text-decoration:none;"
             title="${f.source_url}">🔗 Source</a>`
      : `<span style="color:var(--muted);font-size:12px;">—</span>`;

    const reasonId = `fp-reason-${i}`;
    const fpReasonRow = f.is_false_positive && fpReason
      ? `<tr id="${reasonId}" style="display:none;">
           <td colspan="7" style="padding:8px 12px;background:#f8f9fa;font-size:12px;color:var(--muted);font-style:italic;">
             ⚡ False positive reason: ${fpReason}
           </td>
         </tr>`
      : "";

    const llmId = `llm-${i}`;
    const llmBtn = `<button onclick="toggleLLM('${llmId}')"
                            style="background:none;border:none;cursor:pointer;font-size:11px;color:var(--accent);padding:0;">
                      🤖 Reasoning
                    </button>`;
    const llmRow = f.llm_reasoning
      ? `<tr id="${llmId}" style="display:none;">
           <td colspan="7" style="padding:10px 14px;background:#f0f4ff;border-left:3px solid var(--accent);font-size:12px;line-height:1.6;">
             <strong>AI Reasoning:</strong> ${f.llm_reasoning}
             ${f.source_url ? `<br><a href="${f.source_url}" target="_blank" rel="noopener" style="color:var(--accent);">📎 ${f.source_url}</a>` : ""}
           </td>
         </tr>`
      : "";

    return `
      <tr style="border-bottom:1px solid var(--border);${f.is_false_positive ? 'opacity:0.65;' : ''}">
        <td style="padding:10px 8px;">
          ${fpTag}<strong style="font-size:13px;">${company}</strong>
          <div style="font-size:11px;color:var(--muted);">${f.product || ""}</div>
        </td>
        <td style="padding:10px 8px;">
          <span style="display:inline-block;padding:3px 8px;border-radius:4px;
                       font-size:11px;font-weight:700;text-transform:uppercase;
                       background:${sevBg[sev]};color:${sevColor[sev]};">${sev}</span>
        </td>
        <td style="padding:10px 8px;font-size:12px;max-width:200px;">
          <strong>${regTitle.length > 50 ? regTitle.slice(0,48)+"…" : regTitle}</strong>
          <div style="font-size:10px;color:var(--muted);">${f.regulation_family || ""}</div>
        </td>
        <td style="padding:10px 8px;font-size:12px;max-width:240px;color:var(--text);">
          ${gapText}
        </td>
        <td style="padding:10px 8px;font-size:12px;color:var(--orange);white-space:nowrap;">
          📅 ${f.deadline || "TBD"}
          ${f.days_left !== undefined && f.days_left !== null
            ? `<div style="font-size:10px;color:${f.days_left < 0 ? 'var(--red)' : 'var(--muted)'};">${f.days_left < 0 ? '⚠ OVERDUE' : f.days_left + 'd left'}</div>`
            : ""}
        </td>
        <td style="padding:10px 8px;">${srcLink}</td>
        <td style="padding:10px 8px;">${llmBtn}</td>
      </tr>
      ${llmRow}
      ${fpReasonRow}`;
  }).join("");

  wrap.innerHTML = `
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <thead>
        <tr style="background:var(--surface);font-size:12px;text-align:left;">
          <th style="padding:8px;">Partner</th>
          <th style="padding:8px;">Severity</th>
          <th style="padding:8px;">Regulation</th>
          <th style="padding:8px;">Gap</th>
          <th style="padding:8px;">Deadline</th>
          <th style="padding:8px;">Source</th>
          <th style="padding:8px;">AI</th>
        </tr>
      </thead>
      <tbody>${tableRows}</tbody>
    </table>
    <p style="font-size:11px;color:var(--muted);margin-top:8px;">
      ${showFP ? "Showing real gaps + false positives (greyed)." : "False positives hidden — toggle to show."}
      Click 🤖 Reasoning for AI-generated compliance analysis with source citations.
    </p>`;
}

function toggleLLM(id) {
  const el = document.getElementById(id);
  if (el) el.style.display = el.style.display === "none" ? "table-row" : "none";
}

// ── Live Regulatory Monitoring ────────────────────────────────────────────────
async function loadLiveMonitor() {
  const el    = document.getElementById("liveMonitorContent");
  const badge = document.getElementById("liveChangeBadge");
  if (!el) return;

  try {
    const data = await apiGet("/pipeline/live-status");

    // Update badge
    const changed    = (data.sources || []).some(s => s.changed);
    const hasErr     = (data.sources || []).some(s => (s.status || "").startsWith("error"));
    const isSnapshot = (data.sources || []).every(s => s.status === "snapshot");
    if (changed) {
      badge.style.cssText = "background:#fef3c7;color:var(--orange);";
      badge.textContent = `${data.total_changes} change(s) detected`;
    } else if (isSnapshot) {
      badge.style.cssText = "background:#e0f2fe;color:var(--accent);";
      badge.textContent = "Live · using snapshot data";
    } else {
      badge.style.cssText = "background:#dcfce7;color:#16a34a;";
      badge.textContent = `Live · checked ${data.check_count}×`;
    }

    // ── Source status rows ─────────────────────────────────────────────────
    const srcRows = (data.sources || []).map(s => {
      const isErr      = (s.status || "").startsWith("error");
      const isSnapshot = s.status === "snapshot";
      const isChanged  = s.changed;
      const isFresh    = s.status === "baseline_recorded";
      const dot   = isErr ? "🔴" : isSnapshot ? "🔵" : isChanged ? "🟡" : "🟢";
      const label = isErr ? "Error" : isSnapshot ? "Snapshot (live feed restricted)" : isChanged ? "CHANGED" : isFresh ? "Baseline recorded" : "No change";
      const labelColor = isErr ? "var(--red)" : isSnapshot ? "var(--accent)" : isChanged ? "var(--orange)" : "#16a34a";

      const itemsHtml = (s.last_items || []).slice(0, 2).map(item => `
        <div style="margin-top:6px;padding:6px 10px;background:#f8f9fa;border-left:3px solid var(--border);border-radius:0 4px 4px 0;font-size:12px;">
          <div style="font-weight:600;color:var(--text);">${item.title || ""}</div>
          ${item.summary ? `<div style="color:var(--muted);margin-top:2px;font-size:11px;">${item.summary.slice(0,120)}…</div>` : ""}
          ${item.link ? `<a href="${item.link}" target="_blank" rel="noopener" style="color:var(--accent);font-size:11px;">↗ View on source</a>` : ""}
        </div>`).join("");

      return `
        <div style="display:flex;align-items:flex-start;gap:10px;padding:10px 0;border-bottom:1px solid var(--border);">
          <span style="font-size:18px;flex-shrink:0;margin-top:2px;">${dot}</span>
          <div style="flex:1;min-width:0;">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">
              <strong style="font-size:13px;">${s.name}</strong>
              <span style="font-size:11px;font-weight:700;color:${labelColor};">${label}</span>
            </div>
            <div style="font-size:11px;color:var(--muted);margin-top:2px;">
              Last polled: ${timeAgo(s.checked_at)}
              ${isErr ? ` · ${s.status}` : ""}
            </div>
            ${itemsHtml}
          </div>
        </div>`;
    }).join("");

    // ── Change log ────────────────────────────────────────────────────────
    const changeLog = (data.change_log || []);
    const changeHtml = changeLog.length
      ? `<div style="margin-top:14px;">
           <div style="font-size:12px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin-bottom:8px;">
             Recent Regulation Changes Detected
           </div>
           ${changeLog.map(c => `
             <div style="padding:8px 12px;background:#fefce8;border:1px solid #fde68a;border-radius:6px;margin-bottom:6px;font-size:12px;">
               <div style="font-weight:600;">${c.title || "Update detected"}</div>
               <div style="color:var(--muted);margin-top:2px;">${c.source} · ${timeAgo(c.detected_at)}</div>
               ${c.summary ? `<div style="margin-top:4px;color:var(--text);">${c.summary.slice(0,160)}</div>` : ""}
               ${c.link ? `<a href="${c.link}" target="_blank" rel="noopener" style="color:var(--accent);">↗ View update</a>` : ""}
             </div>`).join("")}
         </div>`
      : "";

    el.innerHTML = `
      <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:12px;font-size:13px;">
        <div style="background:#dcfce7;color:#15803d;padding:7px 14px;border-radius:8px;font-weight:600;">
          🟢 System LIVE
        </div>
        <div style="background:var(--surface);padding:7px 14px;border-radius:8px;color:var(--muted);">
          🕐 Last polled: <strong>${timeAgo(data.last_checked)}</strong>
        </div>
        <div style="background:var(--surface);padding:7px 14px;border-radius:8px;color:var(--muted);">
          📡 ${(data.sources || []).length} source(s) monitored
        </div>
        <div style="background:var(--surface);padding:7px 14px;border-radius:8px;color:var(--muted);">
          🔄 ${data.total_changes || 0} total change(s) since session start
        </div>
      </div>
      <div style="font-size:12px;color:var(--muted);font-style:italic;margin-bottom:12px;">
        ${data.message || ""}
      </div>
      ${srcRows}
      ${changeHtml}
      <p style="font-size:11px;color:var(--muted);margin-top:10px;">
        Polls EUR-Lex (EU legislation RSS) and ECHA (SVHC chemical news) every 90 seconds.
        Any change in feed content triggers a highlighted notification above.
        Auto-refresh is active — no manual action needed.
      </p>`;

  } catch (e) {
    if (badge) {
      badge.style.cssText = "background:#fee2e2;color:var(--red);";
      badge.textContent = "Offline";
    }
    el.innerHTML = `
      <div style="display:flex;gap:12px;align-items:center;padding:12px;background:#fef2f2;border-radius:8px;">
        <span style="font-size:20px;">🔴</span>
        <div>
          <div style="font-weight:600;color:var(--red);">Could not reach monitoring backend</div>
          <div style="font-size:12px;color:var(--muted);margin-top:3px;">${e.message}</div>
          <div style="font-size:12px;color:var(--muted);margin-top:2px;">The system will retry automatically every 90 seconds.</div>
        </div>
      </div>`;
  }
}
