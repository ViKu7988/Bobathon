/**
 * pipeline.js — pipeline runner controls
 * EcoComply Regulatory Radar | IBM Bobathon 2025
 */

function getChannels() {
  return Array.from(document.querySelectorAll("#ch_whatsapp, #ch_sms, #ch_email"))
    .filter(c => c.checked).map(c => c.value);
}

function getLiveFetch() {
  return document.querySelector("[name='fetchMode']:checked")?.value === "live";
}

function getSendAlerts() {
  return document.querySelector("[name='sendMode']:checked")?.value === "real";
}

function setStep(n, state) {
  const step   = document.getElementById(`pstep${n}`);
  const status = document.getElementById(`pstep${n}-status`);
  step.className = `pipeline-step ${state}`;
  const icons = { idle: "⬜", running: "🔄", done: "✅", error: "❌" };
  status.textContent = icons[state] || "⬜";
}

function setStepDetail(n, html) {
  const el = document.getElementById(`pstep${n}-detail`);
  el.innerHTML = html;
  el.classList.remove("hidden");
}

async function runFullPipeline() {
  [1,2,3,4].forEach(n => setStep(n, "idle"));
  [1,2,3,4].forEach(n => {
    const el = document.getElementById(`pstep${n}-detail`);
    el.innerHTML = "";
    el.classList.add("hidden");
  });
  document.getElementById("pipelineResults").classList.add("hidden");

  const channels   = getChannels();
  const live_fetch = getLiveFetch();
  const send_alerts= getSendAlerts();

  // Step 1
  setStep(1, "running");
  await delay(400);

  let result;
  try {
    setStepDetail(1, live_fetch ? "🔴 Fetching live EUR-Lex RSS…" : "📂 Loading pre-built snapshots…");
    result = await apiPost("/pipeline/run", { channels, live_fetch, send_alerts, min_score: 10 });
    setStep(1, "done");
    const s1 = result.steps?.monitor || {};
    setStepDetail(1, `Source: <strong>${s1.source}</strong> · ${s1.items_fetched || 5} updates fetched`);
  } catch (e) {
    setStep(1, "error");
    setStepDetail(1, `❌ ${e.message}`);
    toast("Pipeline failed: " + e.message, "error");
    return;
  }

  await delay(300);

  // Step 2
  setStep(2, "done");
  const s2 = result.steps?.understand || {};
  setStepDetail(2,
    `IBM Bob parsed <strong>${s2.regulations_parsed || 0}</strong> regulations · Engine: ${s2.ai_engine || "Watsonx"}`
  );

  await delay(300);

  // Step 3
  setStep(3, "done");
  const s3 = result.steps?.match || {};
  setStepDetail(3,
    `${s3.partners_scanned || 0} partners scanned · <strong>${s3.partners_affected || 0} affected</strong>`
  );

  await delay(300);

  // Step 4
  setStep(4, "done");
  const s4 = result.steps?.alert || {};
  setStepDetail(4,
    `<strong>${s4.alerts_sent || 0}</strong> alerts sent · ${s4.alerts_failed || 0} failed`
  );

  showPipelineResults(result);
}

function showPipelineResults(result) {
  const card   = document.getElementById("pipelineResults");
  const body   = document.getElementById("pipelineResultsBody");
  const badges = document.getElementById("pipelineBadges");
  card.classList.remove("hidden");
  card.scrollIntoView({ behavior: "smooth" });

  const s = result.summary || {};
  badges.innerHTML = `
    <span class="summary-badge green">✅ ${s.total_alerts_sent || 0} Alerts Sent</span>
    <span class="summary-badge blue">👥 ${s.partners_alerted || 0} Partners Alerted</span>
    <span class="summary-badge">📋 ${s.regulations_monitored || 0} Regulations</span>
  `;

  const matchSummary = result.steps?.match?.match_summary || [];
  const alerts       = result.steps?.alert?.details || [];

  body.innerHTML = `
    <h3 style="font-size:14px;font-weight:600;margin-bottom:12px;">Partner Risk Summary</h3>
    <table class="result-table">
      <thead><tr><th>Partner</th><th>Regulations</th><th>Risk</th><th>Top Regulation</th></tr></thead>
      <tbody>
        ${matchSummary.map(m => `
          <tr>
            <td><strong>${m.company_name}</strong></td>
            <td>${m.regulations_matched}</td>
            <td>${urgencyChip(m.risk_level)}</td>
            <td>${m.top_regulation || "—"}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>

    <h3 style="font-size:14px;font-weight:600;margin:20px 0 12px;">Alert Delivery</h3>
    <table class="result-table">
      <thead><tr><th>Partner</th><th>Regulation</th><th>Channel</th><th>Status</th></tr></thead>
      <tbody>
        ${alerts.map(a => `
          <tr>
            <td>${a.company_name}</td>
            <td>${a.regulation}</td>
            <td>${channelIcon(a.channel)} ${a.channel}</td>
            <td>${statusChip(a.status)}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

/* ── Trigger one regulation ───────────────────────────────────────────────── */
async function triggerRegulation() {
  const reg_id   = document.getElementById("triggerRegId").value;
  const channels = getChannels();

  if (!reg_id) { toast("Please select a regulation to trigger.", "error"); return; }

  const card = document.getElementById("triggerResults");
  const body = document.getElementById("triggerResultsBody");
  card.classList.remove("hidden");
  body.innerHTML = "<p class='loading-msg'>Triggering regulation…</p>";
  card.scrollIntoView({ behavior: "smooth" });

  try {
    const res = await apiPost("/pipeline/trigger", { regulation_id: reg_id, channels });
    const reg = res.regulation || {};

    body.innerHTML = `
      <div style="background:var(--surface);border-radius:8px;padding:14px;margin-bottom:16px;">
        <div style="font-size:16px;font-weight:700;">${reg.short_name || ""}</div>
        <div style="font-size:13px;color:var(--muted);">${reg.title || ""}</div>
        <div style="margin-top:6px;font-size:13px;">
          ${urgencyChip(reg.urgency)} &nbsp;📅 Deadline: <strong>${reg.deadline || "TBD"}</strong>
        </div>
      </div>
      <p style="font-size:14px;margin-bottom:12px;">
        <strong>${res.affected_partners || 0}</strong> partner(s) affected:
      </p>
      ${(res.results || []).map(r => `
        <div style="border:1px solid var(--border);border-radius:8px;padding:14px;margin-bottom:10px;">
          <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
            <strong>${r.company_name}</strong>
            <span class="chip chip-blue">Score: ${r.match_score}</span>
          </div>
          <div style="font-size:12px;color:var(--muted);margin-bottom:6px;">${(r.match_reasons||[]).join(" · ")}</div>
          ${r.ai_explanation ? `<div style="font-size:12px;background:var(--surface);padding:8px;border-radius:6px;margin-bottom:8px;">${r.ai_explanation}</div>` : ""}
          <div style="font-size:12px;font-style:italic;color:var(--muted);margin-bottom:8px;">"${(r.message_preview||"").slice(0,160)}…"</div>
          ${(r.alert_results||[]).map(a => `
            <span>${channelIcon(a.channel)} ${statusChip(a.status)}</span>
          `).join(" ")}
        </div>
      `).join("")}
    `;
    toast(`Triggered: ${res.affected_partners} partner(s) alerted`, "success");
  } catch (e) {
    body.innerHTML = `<p style='color:var(--red)'>Error: ${e.message}</p>`;
    toast(e.message, "error");
  }
}

/* ── Test alert ───────────────────────────────────────────────────────────── */
async function sendTestAlert() {
  const channel = document.getElementById("testChannel").value;
  const to      = document.getElementById("testTo").value.trim();
  const result  = document.getElementById("testAlertResult");

  if (!to) { toast("Please enter a phone or email address.", "error"); return; }

  result.className = "test-alert-result";
  result.textContent = "Sending…";
  result.classList.remove("hidden");

  try {
    const res = await apiPost("/alerts/test", { channel, to });
    const status = res.result?.status || "unknown";
    const ok     = ["sent","demo_sent"].includes(status);
    result.className = `test-alert-result ${ok ? "success" : "error"}`;
    result.textContent = ok
      ? `✅ Test alert sent via ${channel} to ${to} (status: ${status})`
      : `❌ Failed: ${res.result?.error || "unknown error"}`;
    toast(ok ? "Test alert sent!" : "Test alert failed", ok ? "success" : "error");
  } catch (e) {
    result.className = "test-alert-result error";
    result.textContent = `❌ ${e.message}`;
    toast(e.message, "error");
  }
}

function delay(ms) { return new Promise(r => setTimeout(r, ms)); }
