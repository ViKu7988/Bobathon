"""
Alerts Route
GET  /api/alerts/log                    → full audit log
POST /api/alerts/send                   → manually send an alert
POST /api/alerts/test                   → send a test alert (verify Twilio)
POST /api/alerts/<alert_id>/acknowledge → mark alert as acknowledged
GET  /api/alerts/fix/<partner_id>/<reg_id> → get fix suggestions
EcoComply | IBM Bobathon 2025
"""

from flask import Blueprint, jsonify, request
from services.monitor       import load_sme_portfolio, load_preloaded_regulations
from services.alert_service import (dispatch_alert, get_alert_log,
                                    send_whatsapp, send_sms, send_email,
                                    acknowledge_alert, build_fix_suggestion,
                                    build_whatsapp_message)
from services.matcher       import match_regulations_to_partner

alerts_bp = Blueprint("alerts", __name__)


@alerts_bp.route("/log", methods=["GET"])
def alert_log():
    log = get_alert_log()
    return jsonify({"count": len(log), "alerts": log})


@alerts_bp.route("/<alert_id>/acknowledge", methods=["POST"])
def ack_alert(alert_id: str):
    ok = acknowledge_alert(alert_id)
    return jsonify({"acknowledged": ok, "alert_id": alert_id})


@alerts_bp.route("/fix/<partner_id>/<reg_id>", methods=["GET"])
def get_fix(partner_id: str, reg_id: str):
    partners    = load_sme_portfolio()
    regulations = load_preloaded_regulations()
    partner     = next((p for p in partners if p["id"] == partner_id), None)
    reg         = next((r for r in regulations if r["id"] == reg_id), None)
    if not partner:
        return jsonify({"error": f"Partner '{partner_id}' not found"}), 404
    if not reg:
        return jsonify({"error": f"Regulation '{reg_id}' not found"}), 404
    return jsonify(build_fix_suggestion(reg, partner))


@alerts_bp.route("/send", methods=["POST"])
def send_alert():
    """
    Body: { "partner_id", "regulation_id", "channels", "language" }
    """
    body          = request.get_json(silent=True) or {}
    partner_id    = body.get("partner_id")
    regulation_id = body.get("regulation_id")
    channels      = body.get("channels", ["whatsapp"])
    language      = body.get("language", "en")

    if not partner_id or not regulation_id:
        return jsonify({"error": "partner_id and regulation_id are required"}), 400

    partners = load_sme_portfolio()
    partner  = next((p for p in partners if p["id"] == partner_id), None)
    if not partner:
        return jsonify({"error": f"Partner '{partner_id}' not found"}), 404

    regulations = load_preloaded_regulations()
    reg = next((r for r in regulations if r["id"] == regulation_id), None)
    if not reg:
        return jsonify({"error": f"Regulation '{regulation_id}' not found"}), 404

    matches      = match_regulations_to_partner(partner, [reg])
    matched_cats = matches[0]["matched_categories"] if matches else []
    fix          = build_fix_suggestion(reg, partner)
    message      = build_whatsapp_message(reg, partner, matched_cats, language,
                                          fix["immediate_action"])
    results      = dispatch_alert(partner, reg, message, channels=channels, language=language)

    return jsonify({
        "partner":      {"id": partner["id"], "name": partner["company_name"]},
        "regulation":   {"id": reg["id"], "name": reg["short_name"]},
        "language":     language,
        "message":      message,
        "fix":          fix,
        "send_results": results,
    })


@alerts_bp.route("/test", methods=["POST"])
def test_alert():
    """
    Body: { "channel": "whatsapp"|"sms"|"email", "to": "+49...", "message": "..." }
    """
    body    = request.get_json(silent=True) or {}
    channel = body.get("channel", "sms")
    to      = body.get("to", "")
    message = body.get("message",
        "✅ EcoComply Regulatory Radar — test alert received! "
        "Your compliance monitoring is live. 🛡️")

    if not to:
        return jsonify({"error": "'to' field (phone or email) is required"}), 400

    if channel == "whatsapp":
        result = send_whatsapp(to, message)
    elif channel == "sms":
        result = send_sms(to, message)
    elif channel == "email":
        result = send_email(to, f"Subject: ✅ EcoComply Test Alert\n\n{message}")
    else:
        return jsonify({"error": f"Unknown channel: {channel}"}), 400

    return jsonify({"channel": channel, "to": to, "result": result})
