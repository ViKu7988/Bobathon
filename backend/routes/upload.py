"""
Upload Route — handles partner portfolio uploads
POST /api/upload/portfolio      → upload a JSON portfolio file
POST /api/upload/portfolio-csv  → upload a CSV portfolio file (partners.csv format)
POST /api/upload/drive          → receive a Google Drive / OneDrive share URL and fetch it
EcoComply | IBM Bobathon 2025
"""

import csv
import io
import json
import os
import uuid
import logging
import requests
from pathlib    import Path
from flask      import Blueprint, jsonify, request, current_app
from werkzeug.utils import secure_filename

from services.monitor import load_uploaded_portfolio

logger    = logging.getLogger(__name__)
upload_bp = Blueprint("upload", __name__)

ALLOWED_EXTENSIONS = {".json", ".csv"}
MAX_FILE_SIZE_MB   = 5


def _allowed(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


@upload_bp.route("/portfolio", methods=["POST"])
def upload_portfolio():
    """
    Upload a partner portfolio JSON file OR a findings-format JSON list.
    Accepts:
      - {"partners": [...]}          — standard portfolio
      - [{"id":…, "company_name":…}] — partner list
      - [{"company":…, "gap":…, …}]  — findings list (treated as findings upload)
    Returns the file path and a preview of the loaded records.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file field in request"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400
    if not _allowed(file.filename):
        return jsonify({"error": "Only .json or .csv files are supported"}), 400

    raw = file.read()
    if len(raw) > MAX_FILE_SIZE_MB * 1024 * 1024:
        return jsonify({"error": f"File exceeds {MAX_FILE_SIZE_MB} MB limit"}), 413

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Invalid JSON: {e}"}), 400

    upload_dir = Path(current_app.config.get("UPLOAD_DIR", "../uploads"))
    upload_dir.mkdir(parents=True, exist_ok=True)
    fname    = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
    filepath = str(upload_dir / fname)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # ── Detect format and respond accordingly ─────────────────────────────────
    # 1. Standard portfolio (has "partners" key or list of partner-like dicts)
    partners = load_uploaded_portfolio(filepath)
    if partners:
        return jsonify({
            "status":          "ok",
            "file_path":       filepath,
            "partners_loaded": len(partners),
            "preview":         partners[:3],
            "partners_preview": partners[:5],
            "message":         f"Successfully loaded {len(partners)} partner(s).",
        })

    # 2. Findings-format list — [{"company":…, "gap":…, "severity":…}]
    raw_list = data if isinstance(data, list) else data.get("findings", [])
    if raw_list and isinstance(raw_list, list) and raw_list[0].get("gap") is not None:
        companies = list({f.get("company", f.get("partner_id", "")) for f in raw_list if f.get("company") or f.get("partner_id")})
        # Build synthetic partner previews for the selector
        previews = [{"id": c, "company_name": c} for c in companies[:5]]
        return jsonify({
            "status":           "ok",
            "file_path":        filepath,
            "file_type":        "findings",
            "partners_loaded":  len(companies),
            "partners_preview": previews,
            "preview":          previews[:3],
            "message":          f"Findings file loaded: {len(raw_list)} findings across {len(companies)} companies.",
        })

    # 3. Empty or unrecognised structure — still save and let the user proceed
    return jsonify({
        "status":          "ok",
        "file_path":       filepath,
        "partners_loaded": 0,
        "preview":         [],
        "partners_preview": [],
        "message":         "File saved. No partner or findings records were auto-detected — you can still run analysis.",
    })


@upload_bp.route("/portfolio-csv", methods=["POST"])
def upload_portfolio_csv():
    """
    Upload a partners.csv file (format from hackathon dataset).
    Converts it to JSON partner objects and saves for the pipeline.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file field in request"}), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    raw = file.read()
    if len(raw) > MAX_FILE_SIZE_MB * 1024 * 1024:
        return jsonify({"error": f"File exceeds {MAX_FILE_SIZE_MB} MB limit"}), 413

    try:
        text    = raw.decode("utf-8-sig")  # handle BOM
        reader  = csv.DictReader(io.StringIO(text))
        rows    = list(reader)
    except Exception as e:
        return jsonify({"error": f"Could not parse CSV: {e}"}), 400

    if not rows:
        return jsonify({"error": "CSV is empty"}), 422

    # Group rows by partner_id to build partner objects
    partners_map = {}
    for row in rows:
        pid = row.get("partner_id") or row.get("id", "")
        if pid not in partners_map:
            partners_map[pid] = {
                "id":               pid,
                "company_name":     row.get("company", row.get("company_name", pid)),
                "contact_name":     row.get("contact_name", "Compliance Desk"),
                "email":            row.get("contact_email", row.get("email", "")),
                "phone":            row.get("contact_phone", row.get("phone", "")),
                "whatsapp":         row.get("contact_phone", row.get("phone", "")),
                "country":          row.get("hq_country", row.get("country", "EU")),
                "sector":           row.get("sector", "Electronics"),
                "product_categories": [],
                "substances":       [],
                "certifications":   [],
                "eu_market":        True,
                "preferred_channel": row.get("preferred_channel", "email"),
                "sells_in":         [s.strip() for s in row.get("sells_in", "EU").split("|")] if row.get("sells_in") else ["EU"],
                "products":         [],
            }
        p = partners_map[pid]
        # Add product
        cat = row.get("category", "")
        if cat and cat not in p["product_categories"]:
            p["product_categories"].append(cat)
        subs = [s.strip() for s in row.get("substances", "").split("|") if s.strip()]
        for s in subs:
            if s not in p["substances"]:
                p["substances"].append(s)
        certs = [c.strip() for c in row.get("compliance_streams", "").split("|") if c.strip()]
        for c in certs:
            if c not in p["certifications"]:
                p["certifications"].append(c)
        if row.get("product_id"):
            p["products"].append({
                "product_id":        row.get("product_id", ""),
                "name":              row.get("product_name", row.get("name", "")),
                "category":          cat,
                "substances":        subs,
                "has_battery":       row.get("has_battery", "False").lower() == "true",
                "battery_type":      row.get("battery_type", "none"),
                "battery_capacity_wh": float(row.get("battery_capacity_wh", 0) or 0),
                "has_radio":         row.get("has_radio", "False").lower() == "true",
                "connector":         row.get("connector", "none"),
                "packaging":         [x.strip() for x in row.get("packaging", "").split("|") if x.strip()],
                "intended_use":      row.get("intended_use", "consumer"),
                "markets":           [m.strip() for m in row.get("markets", "EU").split("|") if m.strip()],
                "compliance_streams": certs,
            })

    partners = list(partners_map.values())
    if not partners:
        return jsonify({"error": "No valid partners found in CSV"}), 422

    # Save as JSON
    upload_dir = Path(current_app.config.get("UPLOAD_DIR", "../uploads"))
    upload_dir.mkdir(parents=True, exist_ok=True)
    fname    = f"{uuid.uuid4().hex}_{secure_filename(file.filename.replace('.csv','.json'))}"
    filepath = str(upload_dir / fname)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({"portfolio_version": "csv-upload", "partners": partners}, f, indent=2)

    return jsonify({
        "status":          "ok",
        "file_path":       filepath,
        "partners_loaded": len(partners),
        "partners_preview": partners[:5],
        "preview":         partners[:3],
        "message":         f"CSV converted and loaded: {len(partners)} partner(s) · {len(rows)} product rows.",
    })


@upload_bp.route("/drive", methods=["POST"])
def upload_from_drive():
    """
    Fetch a JSON portfolio from a Google Drive or OneDrive public share link.
    Body: { "url": "https://drive.google.com/..." }
    """
    body = request.get_json(silent=True) or {}
    url  = body.get("url", "").strip()

    if not url:
        return jsonify({"error": "url is required"}), 400

    # Convert Google Drive view link to direct download link
    if "drive.google.com" in url and "/file/d/" in url:
        file_id = url.split("/file/d/")[1].split("/")[0]
        url     = f"https://drive.google.com/uc?export=download&id={file_id}"

    # Convert OneDrive share link
    if "1drv.ms" in url or "onedrive.live.com" in url:
        url = url.replace("?e=", "?download=1&e=") if "?" in url else url + "?download=1"

    try:
        resp = requests.get(url, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        raw  = resp.content

        if len(raw) > MAX_FILE_SIZE_MB * 1024 * 1024:
            return jsonify({"error": f"File exceeds {MAX_FILE_SIZE_MB} MB limit"}), 413

        data = json.loads(raw)
    except requests.RequestException as e:
        return jsonify({"error": f"Failed to fetch file: {e}"}), 502
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Invalid JSON at URL: {e}"}), 400

    # Save locally
    upload_dir = Path(current_app.config.get("UPLOAD_DIR", "../uploads"))
    upload_dir.mkdir(parents=True, exist_ok=True)
    fname    = f"{uuid.uuid4().hex}_cloud_portfolio.json"
    filepath = str(upload_dir / fname)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    partners = load_uploaded_portfolio(filepath)
    if not partners:
        return jsonify({"error": "No valid partner records found at URL"}), 422

    return jsonify({
        "status":          "ok",
        "source_url":      url,
        "file_path":       filepath,
        "partners_loaded": len(partners),
        "preview":         partners[:3],
        "message":         f"Successfully loaded {len(partners)} partner(s) from cloud URL.",
    })
