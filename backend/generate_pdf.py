#!/usr/bin/env python3
"""
Generate the sample PDF challenge brief / demo document for Regulatory Radar.
Uses only the standard library (no reportlab/weasyprint required).
Outputs: Project/data/regulatory_radar_demo.html
Then produces a printable PDF-ready HTML that can be saved as PDF via browser.
EcoComply | IBM Bobathon 2025
"""

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>Regulatory Radar — Demo Brief | EcoComply IBM Bobathon 2025</title>
  <style>
    @page { size: A4; margin: 28mm 22mm 24mm 22mm; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: "Segoe UI", Arial, sans-serif;
      font-size: 11pt;
      line-height: 1.55;
      color: #1f2328;
      background: #fff;
    }
    .cover {
      text-align: center;
      padding: 60px 40px 40px;
      border-bottom: 3px solid #1a56db;
      page-break-after: always;
    }
    .cover-logo { font-size: 54pt; margin-bottom: 12px; }
    .cover-tag {
      display: inline-block;
      background: #e8f0fe;
      color: #1a56db;
      padding: 4px 16px;
      border-radius: 20px;
      font-size: 9pt;
      font-weight: 700;
      letter-spacing: .06em;
      text-transform: uppercase;
      margin-bottom: 24px;
    }
    .cover h1 { font-size: 26pt; font-weight: 800; letter-spacing: -.02em; color: #1a56db; margin-bottom: 10px; }
    .cover h2 { font-size: 14pt; font-weight: 400; color: #57606a; margin-bottom: 30px; }
    .cover-meta { font-size: 10pt; color: #57606a; line-height: 1.8; }
    .cover-meta strong { color: #1f2328; }

    h1.section-h1 { font-size: 16pt; font-weight: 700; color: #1a56db; margin: 28px 0 10px; border-bottom: 2px solid #e5e7eb; padding-bottom: 6px; }
    h2.section-h2 { font-size: 13pt; font-weight: 600; color: #1f2328; margin: 20px 0 8px; }
    h3.section-h3 { font-size: 11pt; font-weight: 600; color: #1f2328; margin: 14px 0 6px; }
    p  { margin-bottom: 10px; }
    ul { margin: 8px 0 10px 18px; }
    li { margin-bottom: 4px; }

    .callout {
      background: #f0f4ff;
      border-left: 4px solid #1a56db;
      border-radius: 0 6px 6px 0;
      padding: 12px 16px;
      margin: 16px 0;
      font-size: 10.5pt;
    }
    .callout-red {
      background: #fef2f2;
      border-left-color: #dc2626;
    }
    .callout-orange {
      background: #fffbeb;
      border-left-color: #d97706;
    }
    .callout-green {
      background: #f0fdf4;
      border-left-color: #16a34a;
    }

    table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 10pt; }
    th { background: #f7f8fa; font-weight: 600; padding: 8px 10px; border: 1px solid #e5e7eb; text-align: left; }
    td { padding: 8px 10px; border: 1px solid #e5e7eb; vertical-align: top; }
    tr:nth-child(even) td { background: #fafafa; }

    .badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 20px;
      font-size: 9pt;
      font-weight: 700;
    }
    .badge-red    { background: #fee2e2; color: #dc2626; }
    .badge-orange { background: #fef3c7; color: #d97706; }
    .badge-blue   { background: #e0f2fe; color: #0369a1; }
    .badge-green  { background: #dcfce7; color: #16a34a; }

    .page-break { page-break-before: always; }
    .step-list { counter-reset: step; list-style: none; margin-left: 0; }
    .step-list li {
      counter-increment: step;
      padding: 12px 14px 12px 50px;
      margin-bottom: 10px;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      position: relative;
    }
    .step-list li::before {
      content: counter(step);
      position: absolute; left: 14px; top: 12px;
      width: 24px; height: 24px;
      background: #1a56db; color: #fff;
      border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      font-size: 12px; font-weight: 700;
      text-align: center; line-height: 24px;
    }
    .step-title { font-weight: 600; margin-bottom: 3px; }
    .step-desc  { font-size: 10pt; color: #57606a; }

    .footer-line {
      margin-top: 32px;
      padding-top: 12px;
      border-top: 1px solid #e5e7eb;
      font-size: 9pt;
      color: #57606a;
      text-align: center;
    }
  </style>
</head>
<body>

<!-- ══════════ COVER PAGE ══════════ -->
<div class="cover">
  <div class="cover-logo">🛡️</div>
  <div class="cover-tag">IBM Bobathon 2025 · GDGoC TUM Heilbronn</div>
  <h1>Regulatory Radar</h1>
  <h2>AI-Powered EU Compliance Monitoring for Electronics SMEs</h2>
  <p style="font-size:12pt;color:#57606a;max-width:440px;margin:0 auto 30px;">
    <em>"Watch every EU regulation that matters. Alert every partner who needs to act. Automatically."</em>
  </p>
  <div class="cover-meta">
    <strong>Partner Challenge:</strong> EcoComply (Bildungscampus 11, Heilbronn)<br>
    <strong>Built with:</strong> IBM Bob (Watsonx Granite) &amp; Twilio<br>
    <strong>Event:</strong> IBM Bobathon — GenAI Builders Day, 2025<br>
    <strong>Promo Code:</strong> TUM-TWILIO-50
  </div>
</div>

<!-- ══════════ PAGE 2: THE PROBLEM ══════════ -->
<h1 class="section-h1">The Problem We're Solving</h1>

<p>
  EcoComply helps electronics SMEs navigate the complex tangle of EU product compliance regulations —
  CE, RoHS, REACH, WEEE, RED, MDR, CBAM, EU Battery Passport, PPWR, and more. Their clients
  manufacture everything from lithium battery packs to medical devices and industrial coatings.
</p>

<div class="callout callout-red">
  <strong>The gap:</strong> EcoComply currently monitors regulatory updates <strong>manually</strong>.
  Someone reads EUR-Lex and ECHA portals, figures out which clients each change affects,
  and emails them one at a time. When a regulation has hundreds of pages and 50 clients,
  things get missed.
</div>

<h2 class="section-h2">What a missed deadline costs</h2>
<ul>
  <li><strong>Fines up to €100,000+ per EU market</strong> for non-compliance</li>
  <li><strong>Goods barred from the EU market</strong> — PPWR applies from 12 Aug 2026; EU Battery Passport is mandatory from 18 Feb 2027 with no grace period</li>
  <li><strong>Marketplace listings suspended</strong> and retailers delisting the manufacturer (lasting brand damage)</li>
  <li><strong>MDR deadlines:</strong> Class II devices must maintain continuous vigilance reporting or face withdrawal of CE certification</li>
</ul>

<div class="callout callout-orange">
  <strong>Key insight:</strong> When a rule changes, the affected partner needs to hear about it that day —
  not when a listing gets pulled.
</div>

<!-- ══════════ PAGE 3: OUR SOLUTION ══════════ -->
<h1 class="section-h1 page-break">Our Solution — Regulatory Radar</h1>

<p>
  Regulatory Radar is a fully automated, end-to-end compliance monitoring pipeline.
  It replaces the entire manual process with a five-step AI-driven workflow that runs continuously.
</p>

<ul class="step-list">
  <li>
    <div class="step-title">📡 Monitor</div>
    <div class="step-desc">
      Pulls updates from EUR-Lex RSS feeds and ECHA news. Falls back to pre-parsed JSON/HTML snapshots
      for reliable demos. New regulation? It's detected within the hour.
    </div>
  </li>
  <li>
    <div class="step-title">🤖 Understand (IBM Bob)</div>
    <div class="step-desc">
      IBM Watsonx Granite reads each regulatory update and extracts structured compliance data:
      what changed, which regulation number, the effective and deadline dates, and which
      product categories or compliance streams it touches.
    </div>
  </li>
  <li>
    <div class="step-title">🎯 Match</div>
    <div class="step-desc">
      A scored matching engine maps each regulatory change to specific SME partners using
      product category overlap (60 pts), compliance stream matching (30 pts), sector heuristics (10 pts),
      and urgency weighting. Low false positives by design.
    </div>
  </li>
  <li>
    <div class="step-title">📲 Alert (Twilio)</div>
    <div class="step-desc">
      Sends a real, actionable notification to the affected partner via WhatsApp, SMS, or email:
      "New rule X applies to your product Y. Deadline Z. Here's what to do."
      Powered by Twilio — the notification fires in seconds.
    </div>
  </li>
  <li>
    <div class="step-title">📊 Track &amp; Audit</div>
    <div class="step-desc">
      Live compliance dashboard with per-partner risk scores, regulation heatmap,
      alert audit log with timestamps, acknowledgement tracking,
      and a full compliance trail EcoComply can show auditors.
    </div>
  </li>
</ul>

<!-- ══════════ PAGE 4: REGULATIONS COVERED ══════════ -->
<h1 class="section-h1 page-break">Regulations We Monitor</h1>

<table>
  <thead>
    <tr>
      <th>ID</th><th>Regulation</th><th>Number</th><th>Deadline</th><th>Urgency</th><th>Sector Impact</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>REG001</td>
      <td><strong>EU Battery Passport</strong></td>
      <td>Reg. (EU) 2023/1542</td>
      <td>18 Feb 2027</td>
      <td><span class="badge badge-red">CRITICAL</span></td>
      <td>EV, Batteries, Energy Storage</td>
    </tr>
    <tr>
      <td>REG002</td>
      <td><strong>PPWR</strong> (Packaging Waste Reg.)</td>
      <td>Reg. (EU) 2025/40</td>
      <td>12 Aug 2026</td>
      <td><span class="badge badge-orange">HIGH</span></td>
      <td>Packaging, Consumer Goods</td>
    </tr>
    <tr>
      <td>REG003</td>
      <td><strong>RED Cybersecurity</strong></td>
      <td>Del. Reg. (EU) 2022/30</td>
      <td>1 Aug 2025</td>
      <td><span class="badge badge-red">CRITICAL</span></td>
      <td>IoT, Wireless, CE Devices</td>
    </tr>
    <tr>
      <td>REG004</td>
      <td><strong>CBAM</strong> (Carbon Border)</td>
      <td>Reg. (EU) 2023/956</td>
      <td>1 Jan 2026</td>
      <td><span class="badge badge-orange">HIGH</span></td>
      <td>Steel, Aluminium, Imports</td>
    </tr>
    <tr>
      <td>REG005</td>
      <td><strong>REACH SVHC Update</strong></td>
      <td>REACH (EC) 1907/2006</td>
      <td>14 Jul 2025</td>
      <td><span class="badge badge-orange">HIGH</span></td>
      <td>Chemicals, Coatings, PCBs</td>
    </tr>
  </tbody>
</table>

<!-- ══════════ PAGE 5: SME PORTFOLIO ══════════ -->
<h1 class="section-h1">Partner Portfolio (Synthetic Demo Data)</h1>

<table>
  <thead>
    <tr><th>ID</th><th>Company</th><th>Sector</th><th>Country</th><th>Key Products</th><th>Risk</th></tr>
  </thead>
  <tbody>
    <tr><td>SME001</td><td>AlphaVolt GmbH</td><td>Electronics</td><td>DE</td><td>Li-ion batteries, EV charging</td><td><span class="badge badge-red">CRITICAL</span></td></tr>
    <tr><td>SME002</td><td>GreenPack Solutions</td><td>Packaging</td><td>ES</td><td>Plastic &amp; composite packaging</td><td><span class="badge badge-orange">HIGH</span></td></tr>
    <tr><td>SME003</td><td>NordElec AS</td><td>Consumer Elec.</td><td>NO</td><td>IoT home automation, wireless</td><td><span class="badge badge-red">CRITICAL</span></td></tr>
    <tr><td>SME004</td><td>ChemCore Italia</td><td>Chemical</td><td>IT</td><td>Industrial coatings, SVHC substances</td><td><span class="badge badge-orange">HIGH</span></td></tr>
    <tr><td>SME005</td><td>MedTek Polska</td><td>Medical Devices</td><td>PL</td><td>Class II diagnostic devices</td><td><span class="badge badge-orange">HIGH</span></td></tr>
    <tr><td>SME006</td><td>SolarFlex BV</td><td>Renewable Energy</td><td>NL</td><td>Solar panels, LiFePO4 storage</td><td><span class="badge badge-red">CRITICAL</span></td></tr>
    <tr><td>SME007</td><td>TextilCircle GmbH</td><td>Textile/Fashion</td><td>DE</td><td>Recycled-fiber clothing</td><td><span class="badge badge-blue">MEDIUM</span></td></tr>
    <tr><td>SME008</td><td>AutoParts Iberia</td><td>Automotive</td><td>PT</td><td>EV drivetrain, battery modules</td><td><span class="badge badge-red">CRITICAL</span></td></tr>
    <tr><td>SME009</td><td>EcoBoard France</td><td>Electronics</td><td>FR</td><td>PCBs, consumer electronics</td><td><span class="badge badge-orange">HIGH</span></td></tr>
    <tr><td>SME010</td><td>CarbonBridge CZ</td><td>Steel/Mfg.</td><td>CZ</td><td>Carbon-intensive steel imports</td><td><span class="badge badge-orange">HIGH</span></td></tr>
  </tbody>
</table>

<!-- ══════════ PAGE 6: TECH STACK ══════════ -->
<h1 class="section-h1 page-break">Technical Architecture</h1>

<table>
  <thead><tr><th>Layer</th><th>Technology</th><th>Role</th></tr></thead>
  <tbody>
    <tr><td><strong>AI Engine</strong></td><td>IBM Watsonx Granite 13B (via Bob)</td><td>Parse regulations, generate alerts, explain matches, score risks</td></tr>
    <tr><td><strong>Backend API</strong></td><td>Python 3.10 + Flask 3.0</td><td>REST API for all pipeline operations</td></tr>
    <tr><td><strong>Alert Delivery</strong></td><td>Twilio WhatsApp + SMS + SendGrid Email</td><td>Real-time multi-channel notifications</td></tr>
    <tr><td><strong>Frontend</strong></td><td>Vanilla HTML/CSS/JS</td><td>Mobile-friendly UI — no build step, works on any device</td></tr>
    <tr><td><strong>Data Sources</strong></td><td>EUR-Lex RSS, ECHA RSS + JSON snapshots</td><td>Live + reliable fallback monitoring</td></tr>
    <tr><td><strong>Upload</strong></td><td>Local drag-drop + Google Drive + OneDrive</td><td>Flexible portfolio onboarding</td></tr>
  </tbody>
</table>

<h2 class="section-h2">How IBM Bob Powers the System</h2>
<ul>
  <li><strong>Built the product</strong> — Bob was the primary development agent throughout the hackathon</li>
  <li><strong>Regulation parser</strong> — Watsonx Granite extracts structured fields from raw EUR-Lex HTML</li>
  <li><strong>Alert message generator</strong> — Bob writes personalised WhatsApp/SMS/email messages per partner</li>
  <li><strong>Match explainer</strong> — 2-sentence AI explanation of why a regulation matches each partner</li>
  <li><strong>Risk summariser</strong> — Plain-English compliance risk assessment for each SME portfolio</li>
</ul>

<!-- ══════════ PAGE 7: JUDGING ══════════ -->
<h1 class="section-h1 page-break">Judging Criteria — Our Coverage</h1>

<table>
  <thead><tr><th>Criterion</th><th>Weight</th><th>How We Address It</th></tr></thead>
  <tbody>
    <tr>
      <td><strong>Works end to end</strong></td>
      <td>30%</td>
      <td>Monitor → Match → Alert all run live. Real WhatsApp message fires on stage to a real phone.</td>
    </tr>
    <tr>
      <td><strong>Smart matching</strong></td>
      <td>25%</td>
      <td>Scored multi-factor matching: product category (60 pts) + compliance streams (30 pts) + sector heuristic (10 pts). Only right partners get alerted.</td>
    </tr>
    <tr>
      <td><strong>Use of IBM Bob</strong></td>
      <td>15%</td>
      <td>Bob built the product and powers regulation parsing, alert generation, match explanations, and risk summaries via Watsonx.</td>
    </tr>
    <tr>
      <td><strong>Alert delivery</strong></td>
      <td>10%</td>
      <td>Real Twilio WhatsApp fires live on stage. SMS and email also supported. All three channels simultaneously.</td>
    </tr>
    <tr>
      <td><strong>Real-world fit</strong></td>
      <td>10%</td>
      <td>Self-serve onboarding, portfolio upload (local/cloud), audit log with timestamps, risk heatmap — EcoComply could deploy this tomorrow.</td>
    </tr>
    <tr>
      <td><strong>Demo &amp; communication</strong></td>
      <td>10%</td>
      <td>Live phone demo on stage. Clean, mobile-first UI. The "phone buzzes" moment during the presentation.</td>
    </tr>
  </tbody>
</table>

<!-- ══════════ FOOTER ══════════ -->
<div class="footer-line">
  🛡️ <strong>Regulatory Radar</strong> by EcoComply &nbsp;·&nbsp;
  IBM Bobathon 2025 &nbsp;·&nbsp; GDGoC TUM Heilbronn &nbsp;·&nbsp;
  Built with IBM Bob (Watsonx) &amp; Twilio (promo: TUM-TWILIO-50)
</div>

</body>
</html>"""

import os
output_path = os.path.join(os.path.dirname(__file__), "..", "data", "regulatory_radar_brief.html")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(HTML_CONTENT)

print(f"✅ Generated: {os.path.abspath(output_path)}")
print("   Open this file in a browser and use Ctrl+P → Save as PDF to generate the PDF.")
