# 🛡️ Regulatory Radar
### by EcoComply — IBM Bobathon 2025 | GDGoC TUM Heilbronn

> An AI-powered EU compliance monitoring agent that watches regulations, matches rule changes to affected SME partners, and fires real-time alerts via WhatsApp, SMS, or email — before a deadline is missed.

---

## 🎯 What It Does

**Five automated steps, zero manual monitoring:**

| Step | What happens |
|------|-------------|
| **1. Monitor** | Pulls EUR-Lex / ECHA RSS feeds (or falls back to pre-parsed JSON/HTML snapshots) |
| **2. Understand** | IBM Bob (Watsonx Granite) reads each update and extracts: what changed, which regulation, deadline, affected categories |
| **3. Match** | Scored multi-factor matching engine maps each regulation to specific SME partners by product category, compliance streams, and sector |
| **4. Alert** | Sends actionable notifications via Twilio (WhatsApp, SMS, email): *"Rule X applies to your product Y. Deadline Z. Here's what to do."* |
| **5. Track** | Live compliance dashboard, audit log, per-partner risk scores, acknowledgement tracking |

---

## 🚀 Quick Start

### 1. Backend setup

```bash
cd Project/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure credentials
cp .env.example .env
# Edit .env — add your Watsonx and Twilio credentials

# Run the API server
python app.py
```
API will start on `http://localhost:5000`

### 2. Frontend setup

No build step required. Open the frontend directly:

```bash
# Option A: Python simple server
cd Project/frontend
python -m http.server 3000
# Open http://localhost:3000

# Option B: VS Code Live Server extension
# Right-click index.html → Open with Live Server

# Option C: Open index.html directly in browser
```

---

## 🛠️ Stack

| Layer | Technology |
|-------|-----------|
| **Backend API** | Python 3.10+, Flask 3.0, Flask-CORS |
| **AI Engine** | IBM Watsonx (Granite 13B Instruct v2) via Bob |
| **Alert Delivery** | Twilio (WhatsApp Sandbox, SMS, SendGrid Email) |
| **Frontend** | Vanilla HTML5/CSS3/JS — no framework, no build step |
| **Data** | JSON (EUR-Lex snapshots, synthetic SME portfolio) |
| **Live Sources** | EUR-Lex RSS, ECHA News RSS |

---

## 🔑 Credentials Setup

Edit `Project/backend/.env`:

```env
# IBM Watsonx (get from cloud.ibm.com)
WATSONX_API_KEY=your_key_here
WATSONX_PROJECT_ID=your_project_id_here
WATSONX_URL=https://us-south.ml.cloud.ibm.com
WATSONX_MODEL_ID=ibm/granite-13b-instruct-v2

# Twilio (get from console.twilio.com — promo: TUM-TWILIO-50)
TWILIO_ACCOUNT_SID=ACxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_FROM_PHONE=+1xxxxxxxxxx
TWILIO_FROM_WHATSAPP=whatsapp:+14155238886   # Twilio Sandbox number
TWILIO_SENDGRID_KEY=SG.xxxxxxxx              # optional — for email
TWILIO_FROM_EMAIL=radar@ecocomply.demo

# App settings
DEMO_MODE=false    # set true to log alerts instead of sending when no Twilio creds
```

> **Twilio WhatsApp Sandbox:** Join the sandbox by sending `join <sandbox-keyword>` to `+1 415 523 8886` on WhatsApp first.

---

## 📡 API Reference

### Pipeline
| Method | Endpoint | Description |
|--------|---------|-------------|
| `POST` | `/api/pipeline/run` | Full automated pipeline run |
| `POST` | `/api/pipeline/trigger` | Trigger one regulation against all partners |
| `GET`  | `/api/pipeline/status` | Pipeline run history + audit log |

### Partners
| Method | Endpoint | Description |
|--------|---------|-------------|
| `GET`  | `/api/partners/` | List all SME partners |
| `GET`  | `/api/partners/<id>/risk` | AI risk summary for a partner |
| `GET`  | `/api/partners/<id>/matches` | Matching regulations for a partner |
| `POST` | `/api/partners/onboard` | Live onboarding — instantly match + alert |

### Regulations
| Method | Endpoint | Description |
|--------|---------|-------------|
| `GET`  | `/api/regulations/` | List all pre-loaded regulations |
| `GET`  | `/api/regulations/<id>` | Get one regulation |
| `POST` | `/api/regulations/parse` | Parse raw text with IBM Bob |

### Alerts
| Method | Endpoint | Description |
|--------|---------|-------------|
| `GET`  | `/api/alerts/log` | Full audit log |
| `POST` | `/api/alerts/send` | Send an alert manually |
| `POST` | `/api/alerts/test` | Send a test alert to verify Twilio |

### Upload
| Method | Endpoint | Description |
|--------|---------|-------------|
| `POST` | `/api/upload/portfolio` | Upload a JSON partner portfolio |
| `POST` | `/api/upload/drive` | Load portfolio from Google Drive / OneDrive URL |

---

## 🎬 Demo Script (3 minutes)

**Opening (30s):**
> "EcoComply manually monitors EU legislation for their SME clients. That costs time and misses deadlines. We automated the whole thing."

**Step 1 — Show the pipeline (45s):**
→ Go to **Pipeline** tab → Click **Run Full Pipeline**
→ Watch the 4 steps run live: Monitor → Understand → Match → Alert
→ Show the results table: which partners are affected, risk levels

**Step 2 — Trigger one regulation (30s):**
→ Select **REG001 · EU Battery Passport** from dropdown → Click **Trigger**
→ Show: AlphaVolt GmbH and SolarFlex BV matched (they make batteries)
→ Show the AI-generated WhatsApp message preview

**Step 3 — Live onboarding on phone (45s):** ← THE MOMENT
→ Open `http://localhost:3000/onboard.html` on your phone
→ Fill in: "EV Startup GmbH", select "lithium_batteries + ev_components", enter your phone number
→ Hit "Activate My Radar"
→ **Phone buzzes — real WhatsApp message arrives**
→ Show the message to the camera

**Step 4 — Dashboard (30s):**
→ Go to **Dashboard** → show the risk heatmap
→ Click a partner card → show detailed risk assessment

---

## 📊 Regulations Monitored

| ID | Regulation | Deadline | Urgency |
|----|-----------|---------|---------|
| REG001 | EU Battery Passport (2023/1542) | 18 Feb 2027 | 🔴 Critical |
| REG002 | PPWR (2025/40) | 12 Aug 2026 | 🟠 High |
| REG003 | RED Cybersecurity (2022/30) | 1 Aug 2025 | 🔴 Critical |
| REG004 | CBAM (2023/956) | 1 Jan 2026 | 🟠 High |
| REG005 | REACH SVHC Update (Jan 2025) | 14 Jul 2025 | 🟠 High |

---

## 🏗️ Project Structure

```
Project/
├── backend/
│   ├── app.py                  ← Flask app entry point
│   ├── config.py               ← All configuration + env vars
│   ├── requirements.txt
│   ├── .env.example
│   ├── routes/
│   │   ├── regulations.py      ← /api/regulations/
│   │   ├── partners.py         ← /api/partners/
│   │   ├── alerts.py           ← /api/alerts/
│   │   ├── pipeline.py         ← /api/pipeline/
│   │   └── upload.py           ← /api/upload/
│   └── services/
│       ├── monitor.py          ← EUR-Lex / ECHA fetcher + snapshot loader
│       ├── matcher.py          ← Regulation ↔ partner matching engine
│       ├── bob_ai.py           ← IBM Watsonx / Bob AI integration
│       └── alert_service.py    ← Twilio WhatsApp / SMS / email sender
├── frontend/
│   ├── index.html              ← Landing page
│   ├── onboard.html            ← Live onboarding + upload
│   ├── dashboard.html          ← Compliance risk dashboard
│   ├── pipeline.html           ← Pipeline runner + test alerts
│   ├── css/main.css            ← Full responsive stylesheet
│   └── js/
│       ├── main.js             ← Shared API utils + helpers
│       ├── onboard.js          ← Onboarding form logic
│       ├── dashboard.js        ← Dashboard data loading
│       └── pipeline.js         ← Pipeline controls
└── data/
    ├── sme_portfolio.json      ← 10 synthetic SME partner profiles
    ├── regulations.json        ← 5 pre-parsed EU regulations
    └── eurlex_sample.html      ← EUR-Lex HTML snapshot fallback
```

---

## 🏆 How We Used IBM Bob

1. **Built with Bob** — the entire codebase was developed using IBM Bob as the AI coding agent
2. **AI regulation parser** — `bob_ai.py` calls Watsonx Granite to parse raw EUR-Lex text into structured JSON
3. **Alert message generation** — Bob generates personalised, actionable WhatsApp/SMS/email messages for each partner
4. **Match explanation** — Bob writes a 2-sentence explanation of why a regulation matches a specific partner
5. **Risk summarisation** — Bob generates a plain-English compliance risk summary for each SME's portfolio

---

## 📋 Judging Criteria Coverage

| Criterion | How we address it |
|-----------|------------------|
| **Works end to end (30%)** | Monitor → Match → Alert all fire live. WhatsApp message arrives on real phone during demo. |
| **Smart matching (25%)** | Scored multi-factor matcher: product category overlap (60 pts) + compliance stream match (30 pts) + sector heuristics (10 pts) + urgency boost. |
| **Use of IBM Bob (15%)** | Bob powers regulation parsing, alert generation, match explanations, and risk summaries via Watsonx Granite. |
| **Alert delivery (10%)** | Real Twilio WhatsApp/SMS fires live on stage. Email via SendGrid. All three channels supported simultaneously. |
| **Real-world fit (10%)** | Self-serve onboarding, portfolio upload (local/Drive/OneDrive), audit log, risk scores — EcoComply could deploy this tomorrow. |
| **Demo & communication (10%)** | Live phone demo on stage. Clean UI. 3-min script above. |

---

*Built at IBM Bobathon 2025 — GDGoC TUM Heilbronn · EcoComply challenge, Team Members: Vivek, Sourabh, Ahmet, Yus, Haru*
*Promo code: TUM-TWILIO-50*
