"""
Regulations Route
GET  /api/regulations/         → list all regulations
GET  /api/regulations/<id>     → get one regulation
POST /api/regulations/parse    → parse raw text with IBM Bob
EcoComply | IBM Bobathon 2025
"""

from flask import Blueprint, jsonify, request
from services.monitor import load_preloaded_regulations
from services.bob_ai  import parse_regulation_text

regulations_bp = Blueprint("regulations", __name__)


@regulations_bp.route("/", methods=["GET"])
def list_regulations():
    regs = load_preloaded_regulations()
    return jsonify({"count": len(regs), "regulations": regs})


@regulations_bp.route("/<reg_id>", methods=["GET"])
def get_regulation(reg_id: str):
    regs = load_preloaded_regulations()
    reg  = next((r for r in regs if r["id"] == reg_id), None)
    if not reg:
        return jsonify({"error": f"Regulation '{reg_id}' not found"}), 404
    return jsonify(reg)


@regulations_bp.route("/parse", methods=["POST"])
def parse_regulation():
    """Feed raw regulation text to IBM Bob and get structured output."""
    body     = request.get_json(silent=True) or {}
    raw_text = body.get("text", "")
    if not raw_text:
        return jsonify({"error": "text field is required"}), 400
    parsed = parse_regulation_text(raw_text)
    return jsonify({"parsed": parsed, "ai_engine": "IBM Watsonx Granite"})
