"""
HuggingFace Inference API — LLM reasoning service
Uses HuggingFace's free Inference API with open-source models.
Primary:  mistralai/Mistral-7B-Instruct-v0.3
Fallback: microsoft/Phi-3-mini-4k-instruct (smaller, faster)
EcoComply | IBM Bobathon 2025
"""

import json
import logging
import os
import re
import time

import requests
from flask import current_app

logger = logging.getLogger(__name__)

# ── Token cache ────────────────────────────────────────────────────────────────
_hf_token: str | None = None

HF_MODELS = [
    "mistralai/Mistral-7B-Instruct-v0.3",
    "microsoft/Phi-3-mini-4k-instruct",
    "HuggingFaceH4/zephyr-7b-beta",
]

HF_API_URL = "https://api-inference.huggingface.co/models/{model}"


def _get_token() -> str:
    global _hf_token
    if _hf_token:
        return _hf_token
    try:
        _hf_token = current_app.config.get("HF_API_TOKEN", "") or os.getenv("HF_API_TOKEN", "")
    except RuntimeError:
        _hf_token = os.getenv("HF_API_TOKEN", "")
    return _hf_token or ""


def _call_hf(prompt: str, max_tokens: int = 400, model_idx: int = 0) -> str:
    """Call HuggingFace Inference API with automatic model fallback."""
    token = _get_token()
    if not token:
        logger.warning("HF_API_TOKEN not set — using rule-based fallback")
        return ""

    model = HF_MODELS[model_idx % len(HF_MODELS)]
    url   = HF_API_URL.format(model=model)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Instruction format works for both Mistral and Phi-3
    payload = {
        "inputs": f"<s>[INST] {prompt} [/INST]",
        "parameters": {
            "max_new_tokens":    max_tokens,
            "temperature":       0.3,
            "top_p":             0.9,
            "repetition_penalty": 1.1,
            "return_full_text":  False,
        },
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)

        # Model loading — wait and retry once
        if resp.status_code == 503:
            logger.info(f"HF model {model} loading, waiting 20s…")
            time.sleep(20)
            resp = requests.post(url, headers=headers, json=payload, timeout=30)

        if resp.status_code == 429:
            logger.warning("HF rate-limited — trying next model")
            if model_idx + 1 < len(HF_MODELS):
                return _call_hf(prompt, max_tokens, model_idx + 1)
            return ""

        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, list) and data:
            return data[0].get("generated_text", "").strip()
        if isinstance(data, dict):
            return data.get("generated_text", "").strip()
        return ""

    except requests.exceptions.Timeout:
        logger.warning(f"HF timeout on {model} — trying next")
        if model_idx + 1 < len(HF_MODELS):
            return _call_hf(prompt, max_tokens, model_idx + 1)
        return ""
    except Exception as e:
        logger.error(f"HF API error ({model}): {e}")
        if model_idx + 1 < len(HF_MODELS):
            return _call_hf(prompt, max_tokens, model_idx + 1)
        return ""


# ── Public reasoning functions ─────────────────────────────────────────────────

def reason_gap(product: dict, regulation: dict, gap_desc: str, source_url: str) -> str:
    """
    Generate a detailed, source-cited gap explanation using the LLM.
    Returns a 2-3 sentence explanation with the specific requirement cited.
    """
    prompt = f"""You are an EU product compliance expert. Explain the compliance gap below in 2-3 clear sentences.
Cite the specific regulation article and source. Be direct — no fluff.

Product: {product.get('name','')} (category: {product.get('category','')}, use: {product.get('intended_use','')})
Regulation: {regulation.get('title','')} ({regulation.get('regulation_number','')})
Gap identified: {gap_desc}
Deadline: {regulation.get('deadline_date','TBD')}
Source: {source_url}

Write the explanation now (2-3 sentences, cite article/source):"""

    result = _call_hf(prompt, max_tokens=180)
    if result and len(result) > 40:
        # Clean any leftover instruction tags
        result = re.sub(r"\[/?INST\]", "", result).strip()
        return result

    # Rule-based fallback
    return (
        f"{product.get('name','')} falls within the scope of {regulation.get('title','')} "
        f"({regulation.get('regulation_number','')}). "
        f"The gap: {gap_desc}. "
        f"Action required before {regulation.get('deadline_date','TBD')}. "
        f"Source: {source_url}"
    )


def reason_false_positive(product: dict, regulation: dict, reason: str) -> str:
    """Explain why a regulation does NOT apply to this product (false positive)."""
    prompt = f"""You are an EU compliance expert. Explain in 1 sentence why this regulation does NOT apply to this product.

Product: {product.get('name','')} ({product.get('category','')}, use: {product.get('intended_use','')})
Regulation: {regulation.get('title','')}
Reason it does not apply: {reason}

One clear sentence:"""

    result = _call_hf(prompt, max_tokens=80)
    if result and len(result) > 20:
        result = re.sub(r"\[/?INST\]", "", result).strip()
        return result
    return reason


def generate_alert_message_hf(regulation: dict, partner: dict, gap: str, channel: str = "whatsapp") -> str:
    """Generate a personalised compliance alert message using HF LLM."""
    name     = (partner.get("contact_name") or partner.get("company_name", "")).split()[0]
    reg      = regulation.get("short_name", regulation.get("title", "EU Regulation"))
    deadline = regulation.get("deadline_date", "TBD")
    action   = (regulation.get("required_actions") or ["Review compliance requirements"])[0]

    if channel == "sms":
        prompt = f"""Write a compliance SMS alert (max 160 chars) to {name} at {partner.get('company_name','')}.
Regulation: {reg}. Gap: {gap[:80]}. Deadline: {deadline}. One action. No fluff."""
        result = _call_hf(prompt, max_tokens=60)
        if result and len(result) > 20:
            return re.sub(r"\[/?INST\]", "", result).strip()[:160]
        return f"EcoComply: {reg} affects {partner.get('company_name','')}. Deadline: {deadline}. Action: {action[:60]}"

    elif channel == "email":
        prompt = f"""Write a short compliance alert email to {name} ({partner.get('company_name','')}).
Regulation: {reg} | Gap: {gap} | Deadline: {deadline} | Action: {action}
Format: Subject line first, then 3-sentence body. Professional, direct."""
        result = _call_hf(prompt, max_tokens=250)
        if result and len(result) > 40:
            return re.sub(r"\[/?INST\]", "", result).strip()
    else:
        prompt = f"""Write a WhatsApp compliance alert for {name} at {partner.get('company_name','')}.
Regulation: {reg}
Gap: {gap}
Deadline: {deadline}
Action needed: {action}
Format: friendly, use emoji sparingly, bullet points, max 150 words, sign as EcoComply Regulatory Radar."""
        result = _call_hf(prompt, max_tokens=220)
        if result and len(result) > 40:
            return re.sub(r"\[/?INST\]", "", result).strip()

    return ""  # caller falls back to template


def summarise_risk_hf(partner: dict, findings: list) -> str:
    """Generate a risk summary paragraph for a partner using HF LLM."""
    if not findings:
        return "No active compliance gaps identified for this partner's current product portfolio."

    high_count   = sum(1 for f in findings if f.get("severity") == "high")
    medium_count = sum(1 for f in findings if f.get("severity") == "medium")
    regs = list({f.get("regulation_title","") for f in findings})[:3]

    prompt = f"""Write a 2-sentence compliance risk summary for {partner.get('company_name','')} (sector: {partner.get('sector','')}).
They have {len(findings)} compliance gaps: {high_count} high severity, {medium_count} medium.
Key regulations involved: {', '.join(regs)}.
Be direct and actionable. No fluff."""

    result = _call_hf(prompt, max_tokens=120)
    if result and len(result) > 40:
        return re.sub(r"\[/?INST\]", "", result).strip()

    return (
        f"{partner.get('company_name','')} has {len(findings)} active compliance gaps "
        f"({high_count} high severity) requiring immediate attention. "
        f"Key areas: {', '.join(regs[:2])}."
    )
