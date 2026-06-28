"""
AI Service — HuggingFace (primary) + IBM Watsonx (optional fallback)
Uses HuggingFace Mistral-7B as the primary reasoning engine.
If HF_API_TOKEN is not set, falls back to Watsonx if credentials present,
otherwise uses deterministic mock/rule-based responses.
EcoComply | IBM Bobathon 2025
"""

import json
import logging
import requests
from flask import current_app

logger = logging.getLogger(__name__)

# ── Watsonx token cache (kept for optional fallback) ──────────────────────────
_token_cache = {"token": None, "expires_at": 0}


def _get_iam_token(api_key: str) -> str:
    import time
    if _token_cache["token"] and time.time() < _token_cache["expires_at"] - 60:
        return _token_cache["token"]
    resp = requests.post(
        "https://iam.cloud.ibm.com/identity/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": api_key},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    import time as t
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = t.time() + data.get("expires_in", 3600)
    return _token_cache["token"]


def _generate(prompt: str, max_tokens: int = 512) -> str:
    """
    LLM dispatch: HuggingFace first, Watsonx if HF token missing, mock last.
    """
    # ── 1. Try HuggingFace (open-source, primary) ──────────────────────────
    try:
        from services.hf_llm import _call_hf
        hf_token = current_app.config.get("HF_API_TOKEN", "")
        if hf_token:
            result = _call_hf(prompt, max_tokens=max_tokens)
            if result and len(result) > 20:
                return result
    except Exception as e:
        logger.debug(f"HF LLM skipped: {e}")

    # ── 2. Try Watsonx (if credentials present) ────────────────────────────
    api_key    = current_app.config.get("WATSONX_API_KEY", "")
    project_id = current_app.config.get("WATSONX_PROJECT_ID", "")
    if api_key and project_id:
        try:
            base_url = current_app.config["WATSONX_URL"]
            model_id = current_app.config["WATSONX_MODEL_ID"]
            token    = _get_iam_token(api_key)
            url      = f"{base_url}/ml/v1/text/generation?version=2023-05-29"
            payload  = {
                "model_id": model_id, "project_id": project_id, "input": prompt,
                "parameters": {"decoding_method": "greedy", "max_new_tokens": max_tokens,
                               "temperature": 0.2, "repetition_penalty": 1.1},
            }
            headers = {"Authorization": f"Bearer {token}",
                       "Content-Type": "application/json", "Accept": "application/json"}
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            results = resp.json().get("results", [{}])
            return results[0].get("generated_text", "").strip()
        except Exception as e:
            logger.warning(f"Watsonx call failed: {e}")

    # ── 3. Mock fallback ───────────────────────────────────────────────────
    logger.info("No LLM credentials configured — using rule-based mock response")
    return _mock_ai_response(prompt)


# Keep old name as alias for compatibility
def _watsonx_generate(prompt: str, max_tokens: int = 512) -> str:
    return _generate(prompt, max_tokens)


# ── Public API ─────────────────────────────────────────────────────────────────

def parse_regulation_text(raw_text: str) -> dict:
    """
    Feed raw regulation HTML/text to Bob and extract structured fields.
    Returns a dict with: title, regulation_number, effective_date, deadline_date,
    affected_categories, what_changed, required_actions, urgency.
    """
    prompt = f"""You are a EU regulatory compliance expert. Read the following regulation text and extract key compliance information as JSON.

REGULATION TEXT:
{raw_text[:3000]}

Extract and return ONLY a valid JSON object with these fields:
{{
  "title": "full regulation title",
  "regulation_number": "e.g. Regulation (EU) 2023/1542",
  "effective_date": "YYYY-MM-DD or null",
  "deadline_date": "YYYY-MM-DD or null",
  "urgency": "critical|high|medium|low",
  "what_changed": "one paragraph summary of the key change",
  "affected_product_categories": ["list", "of", "product types"],
  "required_actions": ["list of specific actions companies must take"],
  "fines": "penalty description or null"
}}

JSON output only, no extra text:"""

    raw = _watsonx_generate(prompt, max_tokens=600)
    try:
        # Extract JSON from response
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(raw[start:end])
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse AI regulation output: {e}")
    return {}


def generate_alert_message(regulation: dict, partner: dict, channel: str = "whatsapp") -> str:
    """
    Generate a personalised, actionable alert message for a specific partner.
    channel: 'whatsapp' | 'sms' | 'email'
    """
    # Format affected products
    matched_products = [
        p for p in partner.get("product_categories", [])
        if p in regulation.get("affected_product_categories", [])
    ]
    products_str = ", ".join(matched_products).replace("_", " ") if matched_products else "your products"

    if channel == "sms":
        max_len = 160
        prompt = f"""Write a brief SMS compliance alert (max 160 chars) for {partner['company_name']}.
Regulation: {regulation['short_name']}. Deadline: {regulation.get('deadline_date', 'TBD')}.
Products affected: {products_str}. Be direct and urgent. No fluff."""
    elif channel == "email":
        prompt = f"""Write a professional compliance alert email for {partner['contact_name']} at {partner['company_name']}.

Regulation: {regulation['title']} ({regulation['short_name']})
Regulation number: {regulation.get('regulation_number', '')}
What changed: {regulation.get('what_changed', '')}
Deadline: {regulation.get('deadline_date', 'TBD')}
Products affected: {products_str}
Required actions: {'; '.join(regulation.get('required_actions', [])[:3])}
Fines: {regulation.get('fines', 'penalties apply')}

Write a clear, professional email with:
- Subject line on first line starting with 'Subject:'
- Greeting
- What changed and why it matters to them specifically
- Their specific affected products
- 3 clear action items with the deadline
- Contact offer for more help
- Sign off as EcoComply Regulatory Radar

Keep it under 300 words. Be direct and helpful."""
    else:  # whatsapp — default
        prompt = f"""Write a WhatsApp compliance alert message for {partner['contact_name']} at {partner['company_name']}.

Regulation: {regulation['short_name']} — {regulation['title']}
What changed: {regulation.get('what_changed', '')}
Deadline: {regulation.get('deadline_date', 'TBD')}
Your affected products: {products_str}
Actions needed: {'; '.join(regulation.get('required_actions', [])[:3])}
Fine risk: {regulation.get('fines', 'penalties apply')}

Format as a WhatsApp message with:
- Opening with their first name
- ⚠️ emoji for urgency
- Clear bullet points
- The deadline prominently shown
- Specific next step they can take today
- Keep under 200 words
- Sign as EcoComply Regulatory Radar 🛡️"""

    raw = _watsonx_generate(prompt, max_tokens=400)
    if raw:
        return raw

    # Fallback template if AI unavailable
    return _fallback_alert(regulation, partner, channel)


def explain_match(regulation: dict, partner: dict) -> str:
    """Generate a brief explanation of WHY this regulation matches this partner."""
    matched = [p for p in partner.get("product_categories", [])
               if p in regulation.get("affected_product_categories", [])]
    if not matched:
        return "Indirect regulatory impact based on supply chain exposure."

    prompt = f"""In 2 sentences, explain why {partner['company_name']} (sector: {partner['sector']}, products: {', '.join(partner['product_categories'])}) is affected by {regulation['short_name']}.
Their matching product categories are: {', '.join(matched)}.
Be specific and professional."""
    result = _watsonx_generate(prompt, max_tokens=100)
    return result or f"{partner['company_name']} manufactures {', '.join(matched).replace('_', ' ')}, which are directly in scope of {regulation['short_name']}."


def summarise_partner_risk(partner: dict, matched_regulations: list) -> dict:
    """Generate an overall compliance risk summary for a partner."""
    critical = [r for r in matched_regulations if r.get("urgency") == "critical"]
    high     = [r for r in matched_regulations if r.get("urgency") == "high"]

    if not matched_regulations:
        return {"risk_level": "low", "summary": "No active regulatory changes match your current product portfolio.", "score": 10}

    score = min(100, len(critical) * 30 + len(high) * 15 + len(matched_regulations) * 5)
    if score >= 60:
        risk_level = "critical"
    elif score >= 35:
        risk_level = "high"
    elif score >= 15:
        risk_level = "medium"
    else:
        risk_level = "low"

    regs_str = "; ".join([r["short_name"] for r in matched_regulations])
    prompt = f"""In 3 sentences, summarise the compliance risk for {partner['company_name']} (sector: {partner['sector']}).
They are affected by these EU regulations: {regs_str}.
Critical issues: {len(critical)}. High issues: {len(high)}.
Give a risk-aware, actionable summary for a compliance officer. Be direct."""
    summary = _watsonx_generate(prompt, max_tokens=150)

    return {
        "risk_level": risk_level,
        "risk_score": score,
        "summary": summary or f"{partner['company_name']} faces {len(matched_regulations)} active regulatory obligations including {len(critical)} critical deadlines.",
        "critical_count": len(critical),
        "high_count": len(high),
        "total_regulations": len(matched_regulations),
    }


# ── Mock responses for demo without credentials ────────────────────────────────

def _mock_ai_response(prompt: str) -> str:
    """Return plausible mock AI responses for demo mode."""
    if "JSON" in prompt or "json" in prompt:
        return json.dumps({
            "title": "EU Battery Regulation (2023/1542)",
            "regulation_number": "Regulation (EU) 2023/1542",
            "effective_date": "2024-02-18",
            "deadline_date": "2027-02-18",
            "urgency": "critical",
            "what_changed": "Mandatory digital Battery Passport required for all industrial batteries >2kWh, EV and LMT batteries placed on the EU market from 18 February 2027.",
            "affected_product_categories": ["lithium_batteries", "ev_components", "energy_storage"],
            "required_actions": ["Register on EU Battery Passport registry", "Declare carbon footprint per kWh", "Implement supply chain due diligence"],
            "fines": "Up to €100,000 per market for non-compliance"
        })
    if "WhatsApp" in prompt or "whatsapp" in prompt:
        return (
            "Hi! ⚠️ *Compliance Alert from EcoComply Regulatory Radar* 🛡️\n\n"
            "A new EU regulation directly affects your products.\n\n"
            "📋 *Regulation:* EU Battery Passport (2023/1542)\n"
            "📅 *Deadline:* 18 February 2027 — NO grace period\n"
            "🏭 *Your affected products:* Lithium battery packs, EV charging modules\n\n"
            "✅ *Your next steps:*\n"
            "1. Register on the EU Battery Passport registry\n"
            "2. Calculate carbon footprint per kWh\n"
            "3. Set up supply chain due diligence for cobalt & lithium\n\n"
            "💶 Non-compliance risk: fines up to €100,000 per EU market\n\n"
            "Reply HELP for a full action plan. EcoComply is here to guide you."
        )
    if "email" in prompt.lower() or "Email" in prompt:
        return (
            "Subject: ⚠️ Compliance Alert: EU Battery Passport Regulation Affects Your Products\n\n"
            "Dear Markus,\n\n"
            "The EU Battery Regulation (2023/1542) introduces mandatory digital Battery Passports "
            "for all industrial batteries >2 kWh, EV batteries, and LMT batteries placed on the EU market.\n\n"
            "**Your affected products:** Lithium-ion battery packs, EV charging modules\n"
            "**Hard deadline:** 18 February 2027 (no grace period)\n\n"
            "**Required actions:**\n"
            "1. Register your battery products on the EU Battery Passport registry\n"
            "2. Calculate and declare carbon footprint per kWh for EV batteries by Feb 2025\n"
            "3. Implement supply chain due diligence for critical raw materials\n\n"
            "Non-compliance may result in fines up to €100,000 per EU market and market access being barred.\n\n"
            "We're here to help. Contact your EcoComply account manager to start the registration process.\n\n"
            "Best regards,\nEcoComply Regulatory Radar 🛡️"
        )
    return "This regulation directly impacts your product portfolio. Immediate compliance action is recommended."


def _fallback_alert(regulation: dict, partner: dict, channel: str) -> str:
    name    = partner.get("contact_name", "").split()[0]
    company = partner.get("company_name", "your company")
    reg     = regulation.get("short_name", "New EU Regulation")
    deadline= regulation.get("deadline_date", "TBD")
    actions = regulation.get("required_actions", ["Review compliance requirements"])[:2]

    if channel == "sms":
        return f"EcoComply Alert: {reg} affects {company}. Deadline: {deadline}. Log in to your Radar dashboard for actions."
    elif channel == "email":
        return (
            f"Subject: Compliance Alert — {reg} affects your products\n\n"
            f"Dear {name},\n\n"
            f"The {reg} regulation affects products at {company}.\n"
            f"Deadline: {deadline}\n\n"
            f"Actions required:\n" +
            "\n".join(f"• {a}" for a in actions) +
            f"\n\nLog in to your EcoComply Regulatory Radar dashboard for full details.\n\nEcoComply Team"
        )
    else:
        return (
            f"Hi {name}! ⚠️ *EcoComply Regulatory Radar Alert* 🛡️\n\n"
            f"📋 *{reg}* affects {company}\n"
            f"📅 *Deadline:* {deadline}\n\n"
            f"✅ *Actions needed:*\n" +
            "\n".join(f"• {a}" for a in actions) +
            "\n\nVisit your dashboard for the full compliance plan."
        )
