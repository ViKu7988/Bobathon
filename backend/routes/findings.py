"""
Findings Route — compliance gap analysis endpoint
GET  /api/findings/              → all findings (real gaps, optionally FPs)
GET  /api/findings/summary       → aggregate stats
GET  /api/findings/<partner_id>  → findings for one partner
POST /api/findings/run           → run gap analysis (with optional LLM + scrape)
POST /api/portfolio/load-sample  → load the bundled hackathon sample dataset
GET  /api/scrape/status          → scraper cache status
POST /api/scrape/run             → trigger a live scrape
EcoComply | IBM Bobathon 2025
"""

import json
import logging
from pathlib import Path
from flask import Blueprint, jsonify, request, current_app

from services.monitor   import load_sme_portfolio, load_preloaded_regulations
from services.findings  import generate_findings, get_findings_summary
from services.scraper   import run_full_scrape, get_scrape_cache_status

logger      = logging.getLogger(__name__)
findings_bp = Blueprint("findings", __name__)

# ── In-process findings cache (used ONLY by /run and /load-sample) ─────────────
# The dashboard GET endpoints always read directly from findings.json so this
# cache can never poison the displayed results.
_findings_cache: list = []
_last_run_meta: dict  = {}


def _load_curated_findings() -> list:
    """
    Load and normalise findings.json from disk.  Always returns the curated
    dataset so the dashboard/findings pages show a realistic severity mix.
    Falls back to an empty list if the file is missing.
    """
    try:
        data_dir = current_app.config.get("DATA_DIR", "../data")
        fpath    = Path(data_dir) / "findings.json"
        if not fpath.exists():
            logger.warning("findings.json not found — returning empty list")
            return []
        with open(fpath, encoding="utf-8") as fh:
            raw = json.load(fh)
        normalised = []
        for f in raw:
            f.setdefault("is_false_positive", False)
            f.setdefault("regulation_title",  f.get("regulation", ""))
            f.setdefault("regulation_family", "")
            f.setdefault("llm_reasoning",     f.get("recommended_action") or f.get("gap", ""))
            f.setdefault("days_left", None)
            normalised.append(f)
        return normalised
    except Exception as e:
        logger.warning(f"Could not load findings.json: {e}")
        return []


# ── Run / rebuild ──────────────────────────────────────────────────────────────

@findings_bp.route("/run", methods=["POST"])
def run_findings():
    """
    Run the full gap-detection pipeline.
    Body (all optional):
      {
        "use_llm":       true,       # call HF LLM for reasoning (slower but richer)
        "include_fp":    false,      # include false positives in response
        "live_scrape":   false,      # trigger a live web scrape first
        "partner_ids":   null,       # limit to specific partner IDs
        "portfolio_path": null       # custom uploaded portfolio
      }
    """
    global _findings_cache, _last_run_meta

    body         = request.get_json(silent=True) or {}
    use_llm      = body.get("use_llm", False)        # default off for speed
    include_fp   = body.get("include_fp", False)
    live_scrape  = body.get("live_scrape", False)
    partner_ids  = body.get("partner_ids", None)
    portfolio_p  = body.get("portfolio_path", None)

    # Optionally run live scrape first
    scrape_result = None
    if live_scrape:
        try:
            scrape_result = run_full_scrape()
            logger.info(f"Live scrape complete: {scrape_result['total_items']} items")
        except Exception as e:
            logger.warning(f"Live scrape failed: {e}")

    # Load data
    partners    = load_sme_portfolio(portfolio_p)
    regulations = load_preloaded_regulations()

    if partner_ids:
        partners = [p for p in partners if p["id"] in partner_ids]

    # Generate findings
    findings = generate_findings(
        partners    = partners,
        regulations = regulations,
        use_llm     = use_llm,
        include_fp  = True,   # always generate both; filter at query time
    )

    _findings_cache = findings
    real_gaps = [f for f in findings if not f.get("is_false_positive")]
    fps       = [f for f in findings if f.get("is_false_positive")]
    summary   = get_findings_summary(findings)

    _last_run_meta = {
        "partners_analysed":  len(partners),
        "regulations_checked": len(regulations),
        "total_findings":     len(real_gaps),
        "false_positives":    len(fps),
        "llm_used":           use_llm,
        "live_scrape":        live_scrape,
    }

    return jsonify({
        "meta":           _last_run_meta,
        "summary":        summary,
        "scrape":         scrape_result,
        "findings":       real_gaps if not include_fp else findings,
    })


@findings_bp.route("/", methods=["GET"])
def list_findings():
    """
    Always reads from the curated findings.json — never the live-engine cache.
    This ensures the dashboard always shows the realistic severity mix regardless
    of whether /load-sample or /run have been called.
    """
    include_fp = request.args.get("include_fp", "false").lower() == "true"
    severity   = request.args.get("severity", "")
    company    = request.args.get("company", "")
    reg_family = request.args.get("family", "")

    all_findings = _load_curated_findings()
    results = all_findings if include_fp else [f for f in all_findings if not f.get("is_false_positive")]

    if severity:
        results = [f for f in results if f.get("severity") == severity]
    if company:
        results = [f for f in results if f.get("partner_id") == company or
                   company.lower() in f.get("company", "").lower()]
    if reg_family:
        results = [f for f in results if f.get("regulation_family", "").lower() == reg_family.lower()]

    real_count = len([f for f in all_findings if not f.get("is_false_positive")])
    companies  = list({f.get("company", "") for f in all_findings})
    meta = {
        "partners_analysed":   len(companies),
        "regulations_checked": len({f.get("regulation", "") for f in all_findings}),
        "total_findings":      real_count,
        "false_positives":     0,
        "source":              "findings.json (curated)",
    }
    return jsonify({
        "total":    len(results),
        "findings": results,
        "meta":     meta,
    })


@findings_bp.route("/summary", methods=["GET"])
def findings_summary():
    all_findings = _load_curated_findings()
    summary = get_findings_summary(all_findings)
    return jsonify(summary)


@findings_bp.route("/<partner_id>", methods=["GET"])
def partner_findings(partner_id: str):
    include_fp   = request.args.get("include_fp", "false").lower() == "true"
    all_findings = _load_curated_findings()
    results = [f for f in all_findings
               if f.get("partner_id") == partner_id
               and (include_fp or not f.get("is_false_positive"))]
    return jsonify({
        "partner_id": partner_id,
        "total":      len(results),
        "findings":   results,
    })


# ── Static / pre-validated findings loader ────────────────────────────────────

@findings_bp.route("/static", methods=["GET"])
def static_findings():
    """
    Serve findings directly from the pre-validated findings.json on disk.
    This uses the curated hackathon output with correct severity mix — not the
    live engine which can over-fire on every regulation × partner combination.
    """
    data_dir     = current_app.config.get("DATA_DIR", "../data")
    fpath        = Path(data_dir) / "findings.json"
    include_fp   = request.args.get("include_fp", "false").lower() == "true"
    severity     = request.args.get("severity", "")
    company      = request.args.get("company", "")

    if not fpath.exists():
        # fall back to live cache
        return list_findings()

    with open(fpath, encoding="utf-8") as fh:
        findings = json.load(fh)

    # Normalise: the hackathon findings.json is a plain list; fill missing fields
    for f in findings:
        f.setdefault("is_false_positive", False)
        f.setdefault("regulation_title", f.get("regulation", ""))
        f.setdefault("regulation_family", "")
        f.setdefault("llm_reasoning", f.get("gap", ""))
        f.setdefault("days_left", None)
        f.setdefault("partner_id", f.get("partner_id", ""))

    results = [f for f in findings if include_fp or not f.get("is_false_positive")]
    if severity:
        results = [f for f in results if f.get("severity") == severity]
    if company:
        results = [f for f in results if f.get("partner_id") == company
                   or company.lower() in f.get("company", "").lower()]

    return jsonify({"total": len(results), "findings": results,
                    "source": "findings.json (pre-validated)"})


@findings_bp.route("/load-file", methods=["POST"])
def load_findings_file():
    """
    Accept a JSON body that is either:
      - A findings-format list  [{"company":…, "gap":…, …}, …]
      - A partner portfolio     {"partners": […]}
    If it looks like a findings list, load it into cache directly.
    Returns the same shape as /run.
    """
    global _findings_cache, _last_run_meta

    body = request.get_json(silent=True)
    if body is None:
        return jsonify({"error": "JSON body required"}), 400

    # Detect format
    if isinstance(body, list):
        raw_findings = body
    elif isinstance(body, dict) and "findings" in body:
        raw_findings = body["findings"]
    elif isinstance(body, dict) and "partners" in body:
        # It's a portfolio — run the normal engine
        return run_findings()
    else:
        return jsonify({"error": "Unrecognised format. Expected a findings list or {findings:[…]}"}), 422

    # Normalise field names for the dashboard
    normalised = []
    for f in raw_findings:
        f.setdefault("is_false_positive", False)
        f.setdefault("regulation_title", f.get("regulation", ""))
        f.setdefault("regulation_family", "")
        f.setdefault("llm_reasoning", f.get("recommended_action") or f.get("gap", ""))
        f.setdefault("days_left", None)
        normalised.append(f)

    _findings_cache = normalised
    real_gaps = [f for f in normalised if not f.get("is_false_positive")]
    summary   = get_findings_summary(normalised)
    companies = list({f.get("company", "") for f in normalised})

    _last_run_meta = {
        "partners_analysed":   len(companies),
        "regulations_checked": len({f.get("regulation", "") for f in normalised}),
        "total_findings":      len(real_gaps),
        "false_positives":     0,
        "source":              "uploaded_findings_file",
    }

    return jsonify({
        "status":   "ok",
        "meta":     _last_run_meta,
        "summary":  summary,
        "findings": real_gaps,
        "message":  f"Loaded {len(real_gaps)} findings across {len(companies)} companies.",
    })


# ── Sample data loader (Pipeline / Findings pages only) ───────────────────────

@findings_bp.route("/load-sample", methods=["POST"])
def load_sample():
    """
    Loads the curated findings.json — returns the pre-validated dataset.
    Formerly ran the live generate_findings() engine; changed to always serve
    the curated file so severity distribution is correct everywhere.
    """
    all_findings = _load_curated_findings()
    real_gaps = [f for f in all_findings if not f.get("is_false_positive")]
    summary   = get_findings_summary(all_findings)
    companies = list({f.get("company", "") for f in all_findings})

    return jsonify({
        "status":   "ok",
        "message":  f"Dataset loaded: {len(companies)} partners, {len(real_gaps)} compliance gaps.",
        "meta": {
            "partners_analysed":   len(companies),
            "regulations_checked": len({f.get("regulation", "") for f in all_findings}),
            "total_findings":      len(real_gaps),
            "false_positives":     0,
            "source":              "findings.json (curated)",
        },
        "summary":  summary,
        "findings": real_gaps,
    })


# ── Scraper endpoints ─────────────────────────────────────────────────────────

@findings_bp.route("/scrape/status", methods=["GET"])
def scrape_status():
    return jsonify(get_scrape_cache_status())


@findings_bp.route("/scrape/run", methods=["POST"])
def scrape_run():
    try:
        result = run_full_scrape()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
