"""
Partners Route
GET  /api/partners/          → list all partners
GET  /api/partners/<id>      → get one partner
GET  /api/partners/<id>/risk → AI risk summary + fix priorities
GET  /api/partners/<id>/matches → matching regulations
POST /api/partners/onboard   → live onboarding (match + alert instantly)
EcoComply | IBM Bobathon 2025
"""

import json
import logging
import uuid
from pathlib import Path
from flask import Blueprint, jsonify, request, current_app
from services.monitor       import load_sme_portfolio, load_preloaded_regulations
from services.matcher       import match_regulations_to_partner
from services.bob_ai        import summarise_partner_risk
from services.alert_service import (dispatch_alert, build_fix_suggestion,
                                    build_whatsapp_message)

logger      = logging.getLogger(__name__)
partners_bp = Blueprint("partners", __name__)

# In-memory registry for live-onboarded partners (demo session)
_live_partners: list = []


def _risk_from_findings(partner_id: str, partner: dict) -> dict:
    """
    Compute risk level and score for a partner using the curated findings.json.
    This gives a realistic severity distribution instead of the matcher-count
    formula that makes every partner score 100/critical.
    """
    try:
        data_dir = current_app.config.get("DATA_DIR", "../data")
        fpath    = Path(data_dir) / "findings.json"
        if not fpath.exists():
            raise FileNotFoundError("findings.json missing")
        with open(fpath, encoding="utf-8") as fh:
            all_f = json.load(fh)
        partner_findings = [f for f in all_f if f.get("partner_id") == partner_id
                            and not f.get("is_false_positive", False)]
    except Exception:
        partner_findings = []

    if not partner_findings:
        # Partner has no findings in curated file → low risk
        return {
            "risk_level":       "low",
            "risk_score":       10,
            "summary":          f"{partner.get('company_name','This partner')} has no active compliance gaps in the current dataset.",
            "critical_count":   0,
            "high_count":       0,
            "total_regulations": 0,
        }

    import datetime
    today = datetime.date.today()

    high_count   = sum(1 for f in partner_findings if f.get("severity") == "high")
    medium_count = sum(1 for f in partner_findings if f.get("severity") == "medium")
    low_count    = sum(1 for f in partner_findings if f.get("severity") == "low")

    # ── Deadline analysis on high-severity findings ────────────────────────────
    overdue_high = 0    # deadline already passed → immediate legal exposure
    near_high    = 0    # deadline within 6 months → urgent
    future_high  = 0    # deadline > 6 months away

    for f in partner_findings:
        if f.get("severity") != "high":
            continue
        dl = f.get("deadline", "")
        if not dl:
            future_high += 1
            continue
        try:
            days = (datetime.date.fromisoformat(dl) - today).days
            if days < 0:
                overdue_high += 1
            elif days <= 180:
                near_high += 1
            else:
                future_high += 1
        except ValueError:
            future_high += 1

    # ── Score: deadline urgency drives the number up ───────────────────────────
    # overdue high = 35 pts (already non-compliant)
    # near-term high (≤6 mo) = 20 pts
    # future high = 10 pts
    # medium = 5 pts, low = 2 pts
    score = min(99,
        overdue_high * 35 +
        near_high    * 20 +
        future_high  * 10 +
        medium_count *  5 +
        low_count    *  2
    )

    # ── Tier classification  (deadline-driven, 4-band) ─────────────────────────
    #
    # CRITICAL  ≥2 overdue high gaps  → already in legal breach across 2+ regulations
    # HIGH      1 overdue AND (near_high≥1 OR high_count≥3)
    #           i.e. overdue AND more deadlines closing in, or overwhelmingly many gaps
    # MEDIUM    1 overdue high gap (one breach but otherwise manageable),
    #           OR ≥2 future-high findings (significant upcoming workload),
    #           OR any near-deadline high finding
    # LOW       only medium/low findings or single future-high — monitoring only
    if overdue_high >= 2:
        level = "critical"
    elif overdue_high >= 1 and (near_high >= 1 or high_count >= 3):
        level = "high"
    elif overdue_high >= 1 or high_count >= 2 or near_high >= 1:
        level = "medium"
    else:
        level = "low"

    regs = list({f.get("regulation", "") for f in partner_findings})[:3]
    overdue_regs = [
        f.get("regulation", "")
        for f in partner_findings
        if f.get("severity") == "high" and f.get("deadline")
        and (today - datetime.date.fromisoformat(f["deadline"])).days > 0
        if True
    ]
    if overdue_high:
        urgency_note = f" ⚠ {overdue_high} deadline(s) already passed — company is currently non-compliant."
    elif near_high:
        urgency_note = f" ⏰ {near_high} deadline(s) within 6 months."
    else:
        urgency_note = ""

    summary = (
        f"{partner.get('company_name','This partner')} has {len(partner_findings)} compliance gap(s): "
        f"{high_count} high, {medium_count} medium, {low_count} low severity.{urgency_note} "
        f"Key regulations: {', '.join(list({f.get('regulation','') for f in partner_findings})[:2])}."
    )
    return {
        "risk_level":        level,
        "risk_score":        score,
        "summary":           summary,
        "high_count":        high_count,
        "medium_count":      medium_count,
        "low_count":         low_count,
        "overdue_high":      overdue_high,
        "near_high":         near_high,
        "total_regulations": len({f.get("regulation", "") for f in partner_findings}),
    }


@partners_bp.route("/", methods=["GET"])
def list_partners():
    partners = load_sme_portfolio() + _live_partners
    return jsonify({"count": len(partners), "partners": partners})


@partners_bp.route("/<partner_id>", methods=["GET"])
def get_partner(partner_id: str):
    all_p = load_sme_portfolio() + _live_partners
    p     = next((x for x in all_p if x["id"] == partner_id), None)
    if not p:
        return jsonify({"error": f"Partner '{partner_id}' not found"}), 404
    return jsonify(p)


@partners_bp.route("/<partner_id>/risk", methods=["GET"])
def partner_risk(partner_id: str):
    all_p = load_sme_portfolio() + _live_partners
    p     = next((x for x in all_p if x["id"] == partner_id), None)
    if not p:
        return jsonify({"error": f"Partner '{partner_id}' not found"}), 404

    # ── Derive risk from the curated findings.json (correct severity mix) ─────
    risk = _risk_from_findings(partner_id, p)

    regs    = load_preloaded_regulations()
    matches = match_regulations_to_partner(p, regs)
    return jsonify({
        "partner_id":   partner_id,
        "company_name": p["company_name"],
        "risk":         risk,
        "top_matches":  matches[:3],
    })


@partners_bp.route("/<partner_id>/matches", methods=["GET"])
def partner_matches(partner_id: str):
    all_p = load_sme_portfolio() + _live_partners
    p     = next((x for x in all_p if x["id"] == partner_id), None)
    if not p:
        return jsonify({"error": f"Partner '{partner_id}' not found"}), 404
    regs    = load_preloaded_regulations()
    matches = match_regulations_to_partner(p, regs)
    return jsonify({
        "partner_id":          partner_id,
        "company_name":        p["company_name"],
        "total_matches":       len(matches),
        "matches":             matches,
    })


@partners_bp.route("/onboard", methods=["POST"])
def onboard_partner():
    """
    Live demo onboarding: user fills a form → gets instant match + alert.
    Body:
    {
      "company_name":       "My Company GmbH",
      "contact_name":       "Jane Doe",
      "email":              "jane@myco.de",
      "phone":              "+49151xxxxxx",
      "whatsapp":           "+49151xxxxxx",
      "country":            "Germany",
      "sector":             "Electronics",
      "product_categories": ["lithium_batteries","consumer_electronics"],
      "certifications":     ["CE","RoHS"],
      "eu_market":          true,
      "alert_channels":     ["whatsapp","email"]
    }
    """
    body = request.get_json(silent=True) or {}
    required = ["company_name", "contact_name", "product_categories"]
    for f in required:
        if not body.get(f):
            return jsonify({"error": f"'{f}' is required"}), 400

    partner = {
        "id":                  f"LIVE-{str(uuid.uuid4())[:8].upper()}",
        "company_name":        body["company_name"],
        "contact_name":        body["contact_name"],
        "email":               body.get("email", ""),
        "phone":               body.get("phone", ""),
        "whatsapp":            body.get("whatsapp") or body.get("phone", ""),
        "country":             body.get("country", "EU"),
        "sector":              body.get("sector", "Other"),
        "product_categories":  body.get("product_categories", []),
        "certifications":      body.get("certifications", []),
        "eu_market":           body.get("eu_market", True),
        "description":         body.get("description", ""),
        "source":              "live_onboarding",
    }
    _live_partners.append(partner)

    # Instant matching
    regs    = load_preloaded_regulations()
    matches = match_regulations_to_partner(partner, regs)
    matched_regs = [m["regulation"] for m in matches]
    risk    = summarise_partner_risk(partner, matched_regs)

    channels = body.get("alert_channels", ["whatsapp"])
    language = body.get("language", "en")
    alerts   = []
    for match in matches[:3]:    # top 3 matches
        reg          = match["regulation"]
        matched_cats = match.get("matched_categories", [])
        fix          = build_fix_suggestion(reg, partner)
        message      = build_whatsapp_message(reg, partner, matched_cats, language,
                                              fix["immediate_action"])
        sends        = dispatch_alert(partner, reg, message,
                                      channels=channels, language=language)
        alerts.append({
            "regulation_id":   reg["id"],
            "regulation":      reg["short_name"],
            "score":           match["score"],
            "match_reasons":   match["match_reasons"],
            "message_preview": message[:200],
            "fix":             fix,
            "alert_results":   sends,
        })

    return jsonify({
        "partner":          partner,
        "risk_assessment":  risk,
        "regulations_matched": len(matches),
        "alerts_triggered": alerts,
        "message":          f"Welcome {partner['contact_name']}! Your Regulatory Radar is live. {len(matches)} regulation(s) affect your portfolio.",
    })


@partners_bp.route("/portfolio-risk", methods=["GET"])
def portfolio_risk():
    """
    Return a full portfolio risk report: every partner ranked by risk score,
    total estimated fine exposure, and per-regulation breakdown.
    Risk levels are derived from the curated findings.json so severity is correct.
    """
    from services.alert_service import build_fix_suggestion

    # Load curated findings once
    try:
        data_dir = current_app.config.get("DATA_DIR", "../data")
        fpath    = Path(data_dir) / "findings.json"
        with open(fpath, encoding="utf-8") as fh:
            curated = json.load(fh)
    except Exception:
        curated = []

    partners    = load_sme_portfolio() + _live_partners
    regulations = load_preloaded_regulations()
    report      = []
    total_exposure = 0

    for partner in partners:
        pid     = partner["id"]
        matches = match_regulations_to_partner(partner, regulations)

        # Use curated findings to derive risk level (not matcher count)
        risk = _risk_from_findings(pid, partner)

        # Build fixes only for top matched regs (cap at 5 to avoid overload)
        fixes = [build_fix_suggestion(m["regulation"], partner) for m in matches[:5]]
        exposure = sum(f["estimated_fine_eur"] for f in fixes)
        max_pri  = risk["risk_score"]   # use curated score
        total_exposure += exposure

        report.append({
            "partner_id":         pid,
            "company_name":       partner["company_name"],
            "sector":             partner.get("sector", ""),
            "country":            partner.get("country", ""),
            "regulations_matched": len(matches),
            "total_exposure_eur": round(exposure),
            "max_priority_score": max_pri,
            "risk_level":         risk["risk_level"],
            "fixes": sorted(fixes, key=lambda x: x["priority_score"], reverse=True)[:3],
        })

    report.sort(key=lambda x: x["max_priority_score"], reverse=True)

    return jsonify({
        "total_partners":       len(partners),
        "total_exposure_eur":   round(total_exposure),
        "partners_at_risk":     sum(1 for r in report if r["risk_level"] in ("high",)),
        "report":               report,
    })
