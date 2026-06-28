"""
Configuration — Regulatory Radar
EcoComply | IBM Bobathon 2025
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ── Flask ──────────────────────────────────────────────────────────────────
    SECRET_KEY        = os.getenv("SECRET_KEY", "regulatory-radar-bobathon-2025")
    DEBUG             = os.getenv("DEBUG", "true").lower() == "true"

    # ── IBM Watsonx / Bob ──────────────────────────────────────────────────────
    WATSONX_API_KEY   = os.getenv("WATSONX_API_KEY", "")
    WATSONX_PROJECT_ID= os.getenv("WATSONX_PROJECT_ID", "")
    WATSONX_URL       = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
    WATSONX_MODEL_ID  = os.getenv("WATSONX_MODEL_ID", "ibm/granite-13b-instruct-v2")

    # ── HuggingFace Inference API ──────────────────────────────────────────────
    HF_API_TOKEN      = os.getenv("HF_API_TOKEN", "")

    # ── Twilio ─────────────────────────────────────────────────────────────────
    TWILIO_ACCOUNT_SID   = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN    = os.getenv("TWILIO_AUTH_TOKEN", "")
    # Accept both TWILIO_FROM_PHONE and TWILIO_PHONE_NUMBER (common alternative)
    TWILIO_FROM_PHONE    = os.getenv("TWILIO_FROM_PHONE") or os.getenv("TWILIO_PHONE_NUMBER", "")
    TWILIO_FROM_WHATSAPP = os.getenv("TWILIO_FROM_WHATSAPP", "whatsapp:+14155238886")  # Twilio sandbox
    # Accept both TWILIO_SENDGRID_KEY and SENDGRID_API_KEY
    TWILIO_SENDGRID_KEY  = os.getenv("TWILIO_SENDGRID_KEY") or os.getenv("SENDGRID_API_KEY", "")
    # Accept both TWILIO_FROM_EMAIL and FROM_EMAIL
    TWILIO_FROM_EMAIL    = os.getenv("TWILIO_FROM_EMAIL") or os.getenv("FROM_EMAIL", "radar@ecocomply.demo")

    # ── Data paths ─────────────────────────────────────────────────────────────
    DATA_DIR          = os.path.join(os.path.dirname(__file__), "..", "data")
    UPLOAD_DIR        = os.path.join(os.path.dirname(__file__), "..", "uploads")
    REGULATIONS_FILE  = os.path.join(DATA_DIR, "regulations.json")
    SME_PORTFOLIO_FILE= os.path.join(DATA_DIR, "sme_portfolio.json")

    # ── Alert settings ─────────────────────────────────────────────────────────
    ALERT_CHANNELS    = ["whatsapp", "sms", "email"]
    DEMO_MODE         = os.getenv("DEMO_MODE", "false").lower() == "true"  # false = real sends when creds present

    # ── CORS ───────────────────────────────────────────────────────────────────
    CORS_ORIGINS      = os.getenv("CORS_ORIGINS", "*")
