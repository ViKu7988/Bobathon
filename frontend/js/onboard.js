/**
 * onboard.js — SME onboarding flow
 * EcoComply Regulatory Radar | IBM Bobathon 2025
 */

/* ── Upload tabs ──────────────────────────────────────────────────────────── */
document.querySelectorAll(".upload-tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".upload-tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".upload-pane").forEach(p => p.classList.remove("active"));
    tab.classList.add("active");
    document.getElementById(`pane-${tab.dataset.tab}`).classList.add("active");
  });
});

/* ── Drag-and-drop ────────────────────────────────────────────────────────── */
const dropzone  = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");

dropzone.addEventListener("dragover",  e => { e.preventDefault(); dropzone.classList.add("dragover"); });
dropzone.addEventListener("dragleave", ()  => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop",      e  => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  const file = e.dataTransfer.files[0];
  if (file) handleLocalFile(file);
});
fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) handleLocalFile(fileInput.files[0]);
});

async function handleLocalFile(file) {
  const statusEl = document.getElementById("uploadStatus");
  statusEl.className = "upload-status";
  statusEl.textContent = `Uploading ${file.name}…`;

  const fd = new FormData();
  fd.append("file", file);

  try {
    const res = await apiPostForm("/upload/portfolio", fd);
    window._uploadedFilePath = res.file_path;
    statusEl.className = "upload-status success";
    statusEl.textContent = `✅ Loaded ${res.partners_loaded} partners from ${file.name}`;
    toast(`Portfolio loaded: ${res.partners_loaded} partners`, "success");
  } catch (e) {
    statusEl.className = "upload-status error";
    statusEl.textContent = `❌ ${e.message}`;
  }
}

/* ── Cloud upload ─────────────────────────────────────────────────────────── */
async function uploadFromCloud(provider) {
  const url = provider === "drive"
    ? document.getElementById("driveUrl").value.trim()
    : document.getElementById("onedriveUrl").value.trim();

  if (!url) { toast("Please enter a URL", "error"); return; }

  const statusEl = document.getElementById("uploadStatus");
  statusEl.className = "upload-status";
  statusEl.textContent = "Fetching from cloud…";
  // show local tab status
  document.querySelector("[data-tab='local']").click();

  try {
    const res = await apiPost("/upload/drive", { url });
    window._uploadedFilePath = res.file_path;
    statusEl.className = "upload-status success";
    statusEl.textContent = `✅ Loaded ${res.partners_loaded} partners from ${provider === "drive" ? "Google Drive" : "OneDrive"}`;
    toast(`Portfolio loaded: ${res.partners_loaded} partners`, "success");
  } catch (e) {
    statusEl.className = "upload-status error";
    statusEl.textContent = `❌ ${e.message}`;
  }
}

/* ── Tag selector ─────────────────────────────────────────────────────────── */
document.querySelectorAll("#productSelector .tag-btn, #certSelector .tag-btn").forEach(btn => {
  btn.addEventListener("click", () => btn.classList.toggle("active"));
});

function getSelectedTags(selectorId) {
  return Array.from(document.querySelectorAll(`#${selectorId} .tag-btn.active`))
    .map(b => b.dataset.val);
}

/* ── Form submit ──────────────────────────────────────────────────────────── */
document.getElementById("onboardForm").addEventListener("submit", async e => {
  e.preventDefault();
  const btn      = document.getElementById("submitBtn");
  const text     = document.getElementById("submitText");
  const spinner  = document.getElementById("submitSpinner");

  // Validate required fields
  const companyName   = document.getElementById("companyName").value.trim();
  const contactName   = document.getElementById("contactName").value.trim();
  const sector        = document.getElementById("sector").value;
  const phone         = document.getElementById("phone").value.trim();
  const productCats   = getSelectedTags("productSelector");

  if (!companyName || !contactName || !sector) {
    toast("Please fill in company name, contact name, and sector.", "error");
    return;
  }
  if (!phone) {
    toast("Please enter a phone number for alerts.", "error");
    return;
  }
  if (productCats.length === 0) {
    toast("Please select at least one product category.", "error");
    return;
  }

  // Loading state
  text.classList.add("hidden");
  spinner.classList.remove("hidden");
  btn.disabled = true;

  const channels = Array.from(document.querySelectorAll("[name='channels']:checked")).map(c => c.value);

  const payload = {
    company_name:        companyName,
    contact_name:        contactName,
    email:               document.getElementById("email").value.trim(),
    phone:               phone,
    whatsapp:            phone,
    country:             document.getElementById("country").value,
    sector:              sector,
    product_categories:  productCats,
    certifications:      getSelectedTags("certSelector"),
    eu_market:           true,
    alert_channels:      channels,
  };

  try {
    const res = await apiPost("/partners/onboard", payload);
    showResults(res);
  } catch (err) {
    toast(`Error: ${err.message}`, "error");
  } finally {
    text.classList.remove("hidden");
    spinner.classList.add("hidden");
    btn.disabled = false;
  }
});

/* ── Show results ─────────────────────────────────────────────────────────── */
function showResults(res) {
  document.getElementById("onboardForm").classList.add("hidden");
  document.getElementById("uploadSection").classList.add("hidden");
  const panel = document.getElementById("resultsPanel");
  panel.classList.remove("hidden");
  panel.scrollIntoView({ behavior: "smooth" });

  document.getElementById("resultsIntro").textContent = res.message || "";

  // Risk badge
  const risk = res.risk_assessment || {};
  const level = risk.risk_level || "medium";
  const badge = document.getElementById("riskBadge");
  badge.className = `risk-badge ${level}`;
  badge.textContent = `${level.toUpperCase()} RISK`;
  document.getElementById("riskScoreLabel").textContent =
    `Risk score: ${risk.risk_score || 0}/100 · ${risk.total_regulations || 0} regulation(s) matched`;
  document.getElementById("riskSummary").textContent = risk.summary || "";

  // Matches
  const matchesList = document.getElementById("matchesList");
  matchesList.innerHTML = "";
  if (res.alerts_triggered && res.alerts_triggered.length > 0) {
    res.alerts_triggered.forEach(m => {
      const div = document.createElement("div");
      div.className = "match-item";
      div.innerHTML = `
        <div class="match-header">
          <span class="match-name">${m.regulation || ""}</span>
          <span class="match-score">Score: ${m.score || 0}</span>
        </div>
        <div class="match-reasons">
          ${(m.match_reasons || []).map(r => `<div class="match-reason">• ${r}</div>`).join("")}
        </div>
        <div class="match-preview" style="margin-top:8px;font-size:12px;color:var(--muted);font-style:italic;">
          "${(m.message_preview || "").slice(0, 140)}…"
        </div>
      `;
      matchesList.appendChild(div);
    });
  } else {
    matchesList.innerHTML = "<p style='color:var(--muted);font-size:13px;'>No regulation matches found for this profile.</p>";
  }

  // Alerts
  const alertsList = document.getElementById("alertsList");
  alertsList.innerHTML = "";
  if (res.alerts_triggered && res.alerts_triggered.length > 0) {
    res.alerts_triggered.forEach(m => {
      (m.alert_results || []).forEach(a => {
        const div = document.createElement("div");
        div.className = "alert-item";
        div.innerHTML = `
          <div class="alert-icon">${channelIcon(a.channel)}</div>
          <div class="alert-detail">
            <div><strong>${a.channel?.toUpperCase()}</strong> alert for ${m.regulation}
              <span class="alert-status ${a.status === 'failed' ? 'failed' : ''}">
                ${a.status === 'sent' ? '✅ Delivered' : a.status === 'demo_sent' ? '🔵 Demo Sent' : '❌ Failed'}
              </span>
            </div>
            <div class="alert-preview">${a.to || ""}</div>
          </div>
        `;
        alertsList.appendChild(div);
      });
    });
  } else {
    alertsList.innerHTML = "<p style='color:var(--muted);font-size:13px;'>No alerts triggered.</p>";
  }
}

function resetForm() {
  document.getElementById("onboardForm").classList.remove("hidden");
  document.getElementById("uploadSection").classList.remove("hidden");
  document.getElementById("resultsPanel").classList.add("hidden");
  window.scrollTo(0, 0);
}
