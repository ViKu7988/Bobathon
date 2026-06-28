"""
Alert Delivery Service
Sends real notifications via Twilio (WhatsApp, SMS) and email (SendGrid).
EcoComply | IBM Bobathon 2025
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from datetime             import datetime, timezone
from flask                import current_app

logger = logging.getLogger(__name__)

# ── Audit log + acknowledgement registry ──────────────────────────────────────
_alert_log: list = []
_ack_registry: dict = {}   # alert_id → {acked: bool, acked_at: str}


def get_alert_log() -> list:
    log = list(reversed(_alert_log))
    # Attach ack status to each entry
    for entry in log:
        aid = entry.get("alert_id", "")
        entry["acknowledged"] = _ack_registry.get(aid, {}).get("acked", False)
        entry["acked_at"]     = _ack_registry.get(aid, {}).get("acked_at", None)
    return log


def acknowledge_alert(alert_id: str) -> bool:
    if alert_id not in _ack_registry:
        _ack_registry[alert_id] = {}
    _ack_registry[alert_id]["acked"]    = True
    _ack_registry[alert_id]["acked_at"] = datetime.now(timezone.utc).isoformat()
    # also mark in log
    for entry in _alert_log:
        if entry.get("alert_id") == alert_id:
            entry["acknowledged"] = True
    return True


def _log_alert(partner_id: str, regulation_id: str, channel: str, status: str,
               message: str, response: str = "", language: str = "en") -> str:
    import uuid
    alert_id = str(uuid.uuid4())[:12]
    _alert_log.append({
        "alert_id":        alert_id,
        "timestamp":       datetime.now(timezone.utc).isoformat(),
        "partner_id":      partner_id,
        "regulation_id":   regulation_id,
        "channel":         channel,
        "status":          status,
        "language":        language,
        "message_preview": message[:120],
        "provider_response": response,
        "acknowledged":    False,
        "acked_at":        None,
    })
    _ack_registry[alert_id] = {"acked": False, "acked_at": None}
    return alert_id


# ── Language templates ─────────────────────────────────────────────────────────
LANG_LABELS = {
    "en": {"greeting": "Hi", "alert_word": "Compliance Alert", "deadline": "Deadline",
           "products": "Your affected products", "actions": "Actions needed",
           "fine": "Fine risk", "next": "Next step", "sign": "EcoComply Regulatory Radar 🛡️"},
    "de": {"greeting": "Hallo", "alert_word": "Compliance-Warnung", "deadline": "Frist",
           "products": "Betroffene Produkte", "actions": "Erforderliche Maßnahmen",
           "fine": "Bußgeldrisiko", "next": "Nächster Schritt", "sign": "EcoComply Regulatory Radar 🛡️"},
    "fr": {"greeting": "Bonjour", "alert_word": "Alerte conformité", "deadline": "Échéance",
           "products": "Produits concernés", "actions": "Actions requises",
           "fine": "Risque d'amende", "next": "Prochaine étape", "sign": "EcoComply Regulatory Radar 🛡️"},
    "es": {"greeting": "Hola", "alert_word": "Alerta de cumplimiento", "deadline": "Fecha límite",
           "products": "Productos afectados", "actions": "Acciones requeridas",
           "fine": "Riesgo de multa", "next": "Próximo paso", "sign": "EcoComply Regulatory Radar 🛡️"},
    "it": {"greeting": "Ciao", "alert_word": "Avviso di conformità", "deadline": "Scadenza",
           "products": "Prodotti interessati", "actions": "Azioni richieste",
           "fine": "Rischio di sanzione", "next": "Prossimo passo", "sign": "EcoComply Regulatory Radar 🛡️"},
    "pl": {"greeting": "Cześć", "alert_word": "Alert dotyczący zgodności", "deadline": "Termin",
           "products": "Produkty objęte przepisami", "actions": "Wymagane działania",
           "fine": "Ryzyko kary", "next": "Następny krok", "sign": "EcoComply Regulatory Radar 🛡️"},
}

def build_whatsapp_message(regulation: dict, partner: dict,
                           matched_cats: list, language: str = "en",
                           fix_suggestion: str = "") -> str:
    """Build a multilingual, actionable WhatsApp/SMS message."""
    L      = LANG_LABELS.get(language, LANG_LABELS["en"])
    name   = (partner.get("contact_name") or "").split()[0] or partner.get("company_name", "")
    reg    = regulation.get("short_name", "New EU Regulation")
    dl     = regulation.get("deadline_date", "TBD")
    cats   = ", ".join(c.replace("_", " ") for c in matched_cats[:3]) if matched_cats else "your products"
    fine   = regulation.get("fines", "penalties apply")
    actions= regulation.get("required_actions", ["Review compliance requirements"])[:2]
    fix    = fix_suggestion or actions[0] if actions else "Review compliance documentation"

    lines = [
        f"{L['greeting']} {name}! ⚠️ *{L['alert_word']} — EcoComply* 🛡️",
        "",
        f"📋 *{reg}*",
        f"📅 *{L['deadline']}:* {dl}",
        f"🏭 *{L['products']}:* {cats}",
        "",
        f"✅ *{L['actions']}:*",
    ]
    for i, a in enumerate(actions, 1):
        lines.append(f"{i}. {a}")

    lines += [
        "",
        f"💶 *{L['fine']}:* {fine}",
        f"💡 *{L['next']}:* {fix}",
        "",
        f"— {L['sign']}",
    ]
    return "\n".join(lines)


# ── WhatsApp via Twilio ────────────────────────────────────────────────────────

def send_whatsapp(to_number: str, message: str,
                  partner_id: str = "", regulation_id: str = "",
                  language: str = "en") -> dict:
    sid   = current_app.config["TWILIO_ACCOUNT_SID"]
    token = current_app.config["TWILIO_AUTH_TOKEN"]
    from_ = current_app.config["TWILIO_FROM_WHATSAPP"]

    if not to_number.startswith("+"):
        to_number = "+" + to_number
    to_wa = f"whatsapp:{to_number}"

    if not (sid and token):
        logger.info(f"[DEMO] WhatsApp to {to_wa}")
        aid = _log_alert(partner_id, regulation_id, "whatsapp", "demo_sent", message, language=language)
        return {"status": "demo_sent", "to": to_wa, "channel": "whatsapp", "alert_id": aid}

    try:
        from twilio.rest import Client
        client = Client(sid, token)
        msg = client.messages.create(body=message, from_=from_, to=to_wa)
        logger.info(f"WhatsApp sent to {to_wa} — SID: {msg.sid}")
        aid = _log_alert(partner_id, regulation_id, "whatsapp", "sent", message, msg.sid, language)
        return {"status": "sent", "sid": msg.sid, "to": to_wa, "channel": "whatsapp", "alert_id": aid}
    except Exception as e:
        err = str(e)
        logger.error(f"WhatsApp send failed: {err}")
        # Twilio trial: only verified numbers — surface a helpful message
        if "unverified" in err.lower() or "21608" in err or "not a valid" in err.lower():
            err = (f"Twilio trial account: recipient {to_number} must be verified at "
                   f"console.twilio.com/phone-numbers/verified before receiving messages.")
        aid = _log_alert(partner_id, regulation_id, "whatsapp", "failed", message, err, language)
        return {"status": "failed", "error": err, "channel": "whatsapp", "alert_id": aid}


# ── SMS via Twilio ─────────────────────────────────────────────────────────────

def send_sms(to_number: str, message: str,
             partner_id: str = "", regulation_id: str = "",
             language: str = "en") -> dict:
    sid   = current_app.config["TWILIO_ACCOUNT_SID"]
    token = current_app.config["TWILIO_AUTH_TOKEN"]
    from_ = current_app.config["TWILIO_FROM_PHONE"]

    if not to_number.startswith("+"):
        to_number = "+" + to_number

    if not (sid and token):
        logger.info(f"[DEMO] SMS to {to_number}")
        aid = _log_alert(partner_id, regulation_id, "sms", "demo_sent", message, language=language)
        return {"status": "demo_sent", "to": to_number, "channel": "sms", "alert_id": aid}

    try:
        from twilio.rest import Client
        client = Client(sid, token)
        # SMS body: strip markdown formatting (no asterisks in SMS)
        sms_body = message.replace("*", "").replace("_", "")[:1600]
        msg = client.messages.create(body=sms_body, from_=from_, to=to_number)
        logger.info(f"SMS sent to {to_number} — SID: {msg.sid}")
        aid = _log_alert(partner_id, regulation_id, "sms", "sent", message, msg.sid, language)
        return {"status": "sent", "sid": msg.sid, "to": to_number, "channel": "sms", "alert_id": aid}
    except Exception as e:
        err = str(e)
        logger.error(f"SMS send failed: {err}")
        if "unverified" in err.lower() or "21608" in err or "not a valid" in err.lower():
            err = (f"Twilio trial account: recipient {to_number} must be verified at "
                   f"console.twilio.com/phone-numbers/verified before receiving messages.")
        aid = _log_alert(partner_id, regulation_id, "sms", "failed", message, err, language)
        return {"status": "failed", "error": err, "channel": "sms", "alert_id": aid}


# ── Email via SendGrid ─────────────────────────────────────────────────────────

def send_email(to_email: str, message_with_subject: str,
               partner_id: str = "", regulation_id: str = "",
               language: str = "en", html_body: str = "") -> dict:
    from_email = current_app.config["TWILIO_FROM_EMAIL"]
    sg_key     = current_app.config["TWILIO_SENDGRID_KEY"]

    lines   = message_with_subject.strip().split("\n")
    subject = "⚠️ EcoComply Regulatory Radar Alert"
    body    = message_with_subject
    if lines and lines[0].lower().startswith("subject:"):
        subject = lines[0][8:].strip()
        body    = "\n".join(lines[1:]).strip()

    if not sg_key:
        logger.info(f"[DEMO] Email to {to_email}: {subject}")
        aid = _log_alert(partner_id, regulation_id, "email", "demo_sent", body, language=language)
        return {"status": "demo_sent", "to": to_email, "channel": "email", "alert_id": aid}

    try:
        from sendgrid             import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, Content
        mail = Mail(from_email=from_email, to_emails=to_email, subject=subject)
        mail.add_content(Content("text/plain", body))
        if html_body:
            mail.add_content(Content("text/html", html_body))
        sg  = SendGridAPIClient(sg_key)
        res = sg.send(mail)
        logger.info(f"Email sent to {to_email} — status {res.status_code}")
        aid = _log_alert(partner_id, regulation_id, "email", "sent", body,
                         str(res.status_code), language)
        return {"status": "sent", "to": to_email, "channel": "email", "alert_id": aid}
    except Exception as e:
        err = str(e)
        logger.error(f"SendGrid send failed: {err}")
        aid = _log_alert(partner_id, regulation_id, "email", "failed", body, err, language)
        return {"status": "failed", "error": err, "channel": "email", "alert_id": aid}


# ── Fix suggestions ────────────────────────────────────────────────────────────

def build_fix_suggestion(regulation: dict, partner: dict) -> dict:
    """
    Return a structured fix suggestion for this regulation + partner.
    Includes priority score, estimated fine exposure, and ordered action steps.
    """
    urgency_score = {"critical": 100, "high": 70, "medium": 40, "low": 10}
    employees     = partner.get("employees", 30)
    revenue       = partner.get("annual_revenue_eur", 2_000_000)
    urgency       = regulation.get("urgency", "medium")

    # Estimate fine exposure as % of revenue (heuristic, compliance-realistic)
    fine_pct = {"critical": 0.05, "high": 0.025, "medium": 0.01, "low": 0.002}
    estimated_fine = min(100_000, revenue * fine_pct.get(urgency, 0.01))
    priority_score = urgency_score.get(urgency, 40)

    # Days to deadline
    import datetime as dt
    deadline_str = regulation.get("deadline_date")
    days_left    = None
    if deadline_str:
        try:
            deadline_dt = dt.datetime.strptime(deadline_str, "%Y-%m-%d").date()
            days_left   = (deadline_dt - dt.date.today()).days
            if days_left < 0:
                priority_score += 30   # already overdue
            elif days_left < 90:
                priority_score += 20   # less than 3 months
            elif days_left < 180:
                priority_score += 10
        except ValueError:
            pass

    actions = regulation.get("required_actions", [])
    steps   = []
    for i, action in enumerate(actions, 1):
        steps.append({
            "step":    i,
            "action":  action,
            "effort":  "Low" if i > 2 else "Medium",
            "owner":   "Compliance Manager" if i == 1 else "Product Team",
        })

    return {
        "regulation_id":    regulation["id"],
        "regulation":       regulation["short_name"],
        "urgency":          urgency,
        "priority_score":   min(100, priority_score),
        "days_to_deadline": days_left,
        "estimated_fine_eur": round(estimated_fine),
        "immediate_action": actions[0] if actions else "Review compliance documentation",
        "fix_steps":        steps,
        "resources": [
            {"label": "Official text", "url": regulation.get("source_url", "#")},
            {"label": "EcoComply guide", "url": "https://ecocomply.eu/guides"},
        ],
    }


# ── Unified dispatcher ─────────────────────────────────────────────────────────

def dispatch_alert(partner: dict, regulation: dict, message: str,
                   channels: list = None, language: str = "en") -> list:
    if channels is None:
        channels = current_app.config.get("ALERT_CHANNELS", ["whatsapp"])

    pid     = partner.get("id", "")
    rid     = regulation.get("id", "")
    results = []

    # Build HTML email body
    html_body = _build_html_email(regulation, partner, message, language)

    for channel in channels:
        if channel == "whatsapp":
            phone = partner.get("whatsapp") or partner.get("phone", "")
            if phone:
                results.append(send_whatsapp(phone, message, pid, rid, language))
        elif channel == "sms":
            phone = partner.get("phone", "")
            if phone:
                results.append(send_sms(phone, message, pid, rid, language))
        elif channel == "email":
            email = partner.get("email", "")
            if email:
                subj   = f"⚠️ {regulation.get('short_name','Compliance Alert')} — Action Required by {regulation.get('deadline_date','TBD')}"
                msg_ws = f"Subject: {subj}\n\n{message}"
                results.append(send_email(email, msg_ws, pid, rid, language, html_body))
        else:
            logger.warning(f"Unknown alert channel: {channel}")

    return results


def _build_html_email(regulation: dict, partner: dict,
                      plain_message: str, language: str = "en") -> str:
    """Generate a crisp HTML email body for compliance alerts."""
    fix   = build_fix_suggestion(regulation, partner)
    name  = partner.get("contact_name", partner.get("company_name", ""))
    reg   = regulation.get("short_name", "New Regulation")
    title = regulation.get("title", "")
    dl    = regulation.get("deadline_date", "TBD")
    fine  = regulation.get("fines", "")
    urgency_color = {"critical": "#dc2626", "high": "#d97706", "medium": "#ca8a04", "low": "#16a34a"}
    uc    = urgency_color.get(regulation.get("urgency", "medium"), "#d97706")

    steps_html = "".join(f"""
      <tr>
        <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;font-weight:600;color:#1a56db;">{s['step']}</td>
        <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;">{s['action']}</td>
        <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;color:#57606a;">{s['owner']}</td>
      </tr>""" for s in fix["fix_steps"])

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:-apple-system,Segoe UI,sans-serif;max-width:620px;margin:0 auto;background:#fff;color:#1f2328;">
  <div style="background:{uc};padding:20px 28px;border-radius:8px 8px 0 0;">
    <div style="color:#fff;font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;">
      ⚠️ EcoComply Regulatory Radar — Compliance Alert
    </div>
    <h1 style="color:#fff;margin:8px 0 4px;font-size:20px;">{reg}</h1>
    <div style="color:rgba(255,255,255,.85);font-size:13px;">{title}</div>
  </div>
  <div style="padding:24px 28px;border:1px solid #e5e7eb;border-top:0;">
    <p style="margin:0 0 16px;">Dear <strong>{name}</strong>,</p>
    <p style="margin:0 0 16px;">A regulatory change directly affects your product portfolio and requires action.</p>

    <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">
      <tr><td style="padding:8px 12px;background:#f7f8fa;font-weight:600;border:1px solid #e5e7eb;width:140px;">Regulation</td>
          <td style="padding:8px 12px;border:1px solid #e5e7eb;">{regulation.get('regulation_number','')}</td></tr>
      <tr><td style="padding:8px 12px;background:#f7f8fa;font-weight:600;border:1px solid #e5e7eb;">⏰ Deadline</td>
          <td style="padding:8px 12px;border:1px solid #e5e7eb;font-weight:700;color:{uc};">{dl}</td></tr>
      <tr><td style="padding:8px 12px;background:#f7f8fa;font-weight:600;border:1px solid #e5e7eb;">Fine risk</td>
          <td style="padding:8px 12px;border:1px solid #e5e7eb;">{fine}</td></tr>
      <tr><td style="padding:8px 12px;background:#f7f8fa;font-weight:600;border:1px solid #e5e7eb;">Est. exposure</td>
          <td style="padding:8px 12px;border:1px solid #e5e7eb;font-weight:700;">
            ~€{fix['estimated_fine_eur']:,} for {partner.get('company_name','')}
          </td></tr>
      <tr><td style="padding:8px 12px;background:#f7f8fa;font-weight:600;border:1px solid #e5e7eb;">Days left</td>
          <td style="padding:8px 12px;border:1px solid #e5e7eb;">
            {'<span style="color:#dc2626;font-weight:700;">' + str(fix['days_to_deadline']) + ' days</span>' if fix['days_to_deadline'] and fix['days_to_deadline'] < 90 else str(fix['days_to_deadline']) + ' days' if fix['days_to_deadline'] else 'Check deadline'}
          </td></tr>
    </table>

    <h3 style="margin:0 0 12px;font-size:14px;">📋 Your Action Plan</h3>
    <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:20px;">
      <tr style="background:#f7f8fa;">
        <th style="padding:8px 12px;text-align:left;border:1px solid #e5e7eb;">#</th>
        <th style="padding:8px 12px;text-align:left;border:1px solid #e5e7eb;">Action</th>
        <th style="padding:8px 12px;text-align:left;border:1px solid #e5e7eb;">Owner</th>
      </tr>
      {steps_html}
    </table>

    <div style="background:#f0f4ff;border-left:4px solid #1a56db;padding:14px 16px;border-radius:0 8px 8px 0;margin-bottom:20px;font-size:13px;">
      <strong>💡 Immediate next step:</strong> {fix['immediate_action']}
    </div>

    <p style="font-size:13px;color:#57606a;">
      Questions? Reply to this email or contact your EcoComply account manager.
      We can guide you through the full compliance process.
    </p>
  </div>
  <div style="padding:14px 28px;background:#f7f8fa;border:1px solid #e5e7eb;border-top:0;
              border-radius:0 0 8px 8px;font-size:11px;color:#57606a;text-align:center;">
    🛡️ <strong>EcoComply Regulatory Radar</strong> · IBM Bobathon 2025 ·
    Powered by IBM Watsonx &amp; Twilio
  </div>
</body></html>"""
