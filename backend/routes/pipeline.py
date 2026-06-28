"""
Pipeline Route — the core end-to-end flow:
  POST /api/pipeline/run        → full scan: monitor → understand → match → alert
  POST /api/pipeline/trigger    → trigger a single regulation against all partners
  GET  /api/pipeline/status     → current pipeline state
  GET  /api/pipeline/live-status → live monitoring state + feed change detection
EcoComply | IBM Bobathon 2025
"""

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from flask import Blueprint, jsonify, request, current_app
from services.monitor       import load_preloaded_regulations, load_sme_portfolio, fetch_eurlex_updates, fetch_echa_updates
from services.matcher       import match_all_partners, get_affected_partners
from services.bob_ai        import generate_alert_message, summarise_partner_risk, explain_match
from services.alert_service import dispatch_alert, get_alert_log

logger        = logging.getLogger(__name__)
pipeline_bp   = Blueprint("pipeline", __name__)
_pipeline_log = []   # in-memory run history

# ── Live-monitoring state ──────────────────────────────────────────────────────
# Stores the last-seen hash of each monitored feed/source so we can detect
# changes between polls and surface them in the dashboard.
_live_monitor_state: dict = {
    "started_at":       None,
    "last_checked":     None,
    "check_count":      0,
    "sources":          [],       # [{name, url, last_hash, last_content, changed_at, status}]
    "change_log":       [],       # [{source, title, detected_at, summary}]
}

_MONITORED_SOURCES = [
    {
        "name":    "EUR-Lex (EU Regulations)",
        "url":     "https://eur-lex.europa.eu/tools/rss.do?type=legislation&legalType=REG&lng=EN",
        "type":    "rss",
        "fallback_items": [
            {"title": "Regulation (EU) 2023/1542 — Battery Regulation", "link": "https://eur-lex.europa.eu/eli/reg/2023/1542/oj", "published": "2023-07-28", "summary": "EU Battery Passport mandatory from 18 Feb 2027.", "source": "EUR-Lex (snapshot)"},
            {"title": "Regulation (EU) 2024/1781 — Ecodesign for Sustainable Products", "link": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ:L_202401781", "published": "2024-06-28", "summary": "ESPR framework replaces Energy-related Products Directive.", "source": "EUR-Lex (snapshot)"},
        ],
    },
    {
        "name":    "ECHA SVHC Candidate List",
        "url":     "https://echa.europa.eu/rss/substances-of-very-high-concern-svhc-intentions.xml",
        "type":    "rss",
        "fallback_items": [
            {"title": "ECHA SVHC Candidate List Update 2025", "link": "https://echa.europa.eu/candidate-list-table", "published": "2025-01-15", "summary": "ECHA added 3 new substances to SVHC Candidate List — affects REACH compliance obligations.", "source": "ECHA (snapshot)"},
        ],
    },
]


@pipeline_bp.route("/run", methods=["POST"])
def run_pipeline():
    """
    Full automated pipeline run.
    Body (optional JSON):
      {
        "channels":      ["whatsapp","sms","email"],   # which channels to alert on
        "min_score":     10,                            # minimum match score
        "live_fetch":    false,                         # true = try live EUR-Lex fetch
        "send_alerts":   true,                          # false = dry run (no real sends)
        "portfolio_path": null                          # custom uploaded portfolio path
      }
    """
    body         = request.get_json(silent=True) or {}
    channels     = body.get("channels", ["whatsapp"])
    min_score    = body.get("min_score", 10)
    live_fetch   = body.get("live_fetch", False)
    send_alerts  = body.get("send_alerts", True)
    portfolio_path = body.get("portfolio_path", None)

    result = {"steps": {}, "summary": {}}

    # ── Step 1: Monitor ──────────────────────────────────────────────────────
    logger.info("Pipeline: Step 1 — Monitor")
    if live_fetch:
        live_items = fetch_eurlex_updates(max_items=5) + fetch_echa_updates(max_items=3)
        result["steps"]["monitor"] = {
            "source": "live",
            "items_fetched": len(live_items),
            "items": live_items[:5],
        }
    else:
        result["steps"]["monitor"] = {
            "source": "pre-loaded snapshot",
            "items_fetched": 5,
            "note": "Using pre-loaded EUR-Lex JSON snapshots for reliable demo"
        }

    # ── Step 2: Understand (load pre-parsed regulations) ─────────────────────
    logger.info("Pipeline: Step 2 — Understand")
    regulations = load_preloaded_regulations()
    result["steps"]["understand"] = {
        "regulations_parsed": len(regulations),
        "regulation_ids": [r["id"] for r in regulations],
        "ai_engine": "IBM Watsonx Granite (via Bob)",
    }

    # ── Step 3: Match ─────────────────────────────────────────────────────────
    logger.info("Pipeline: Step 3 — Match")
    partners = load_sme_portfolio(portfolio_path)
    all_matches = match_all_partners(partners, regulations)

    match_summary = []
    for partner in partners:
        pid      = partner["id"]
        matches  = all_matches.get(pid, [])
        regs     = [m["regulation"] for m in matches if m["score"] >= min_score]
        risk     = summarise_partner_risk(partner, regs)
        match_summary.append({
            "partner_id":     pid,
            "company_name":   partner["company_name"],
            "regulations_matched": len(matches),
            "risk_level":     risk["risk_level"],
            "risk_score":     risk.get("risk_score", 0),
            "top_regulation": matches[0]["regulation"]["short_name"] if matches else None,
        })

    result["steps"]["match"] = {
        "partners_scanned":  len(partners),
        "partners_affected": sum(1 for m in match_summary if m["regulations_matched"] > 0),
        "match_summary":     match_summary,
    }

    # ── Step 4: Alert ─────────────────────────────────────────────────────────
    logger.info("Pipeline: Step 4 — Alert")
    alerts_sent   = []
    alerts_failed = []

    for partner in partners:
        pid     = partner["id"]
        matches = [m for m in all_matches.get(pid, []) if m["score"] >= min_score]
        for match in matches[:2]:   # max 2 alerts per partner per run
            reg     = match["regulation"]
            message = generate_alert_message(reg, partner, channel=channels[0] if channels else "whatsapp")
            if send_alerts:
                send_results = dispatch_alert(partner, reg, message, channels=channels)
                for res in send_results:
                    entry = {
                        "partner_id":    pid,
                        "company_name":  partner["company_name"],
                        "regulation_id": reg["id"],
                        "regulation":    reg["short_name"],
                        "channel":       res["channel"],
                        "status":        res["status"],
                    }
                    if res["status"] in ("sent", "demo_sent"):
                        alerts_sent.append(entry)
                    else:
                        alerts_failed.append(entry)
            else:
                alerts_sent.append({
                    "partner_id":    pid,
                    "company_name":  partner["company_name"],
                    "regulation_id": reg["id"],
                    "regulation":    reg["short_name"],
                    "channel":       "dry_run",
                    "status":        "dry_run",
                    "message_preview": message[:120],
                })

    result["steps"]["alert"] = {
        "alerts_sent":   len(alerts_sent),
        "alerts_failed": len(alerts_failed),
        "details":       alerts_sent + alerts_failed,
    }

    # ── Summary ───────────────────────────────────────────────────────────────
    result["summary"] = {
        "regulations_monitored": len(regulations),
        "partners_in_portfolio": len(partners),
        "partners_alerted":      len({a["partner_id"] for a in alerts_sent}),
        "total_alerts_sent":     len(alerts_sent),
        "pipeline_status":       "success",
    }
    _pipeline_log.append(result["summary"])
    return jsonify(result)


@pipeline_bp.route("/trigger", methods=["POST"])
def trigger_regulation():
    """
    Trigger a single regulation by ID against the loaded partner portfolio.
    Body: { "regulation_id": "REG001", "channels": ["whatsapp"], "partner_ids": null }
    """
    body        = request.get_json(silent=True) or {}
    reg_id      = body.get("regulation_id")
    channels    = body.get("channels", ["whatsapp"])
    partner_ids = body.get("partner_ids", None)  # null = all partners

    if not reg_id:
        return jsonify({"error": "regulation_id is required"}), 400

    regulations = load_preloaded_regulations()
    reg         = next((r for r in regulations if r["id"] == reg_id), None)
    if not reg:
        return jsonify({"error": f"Regulation '{reg_id}' not found"}), 404

    partners = load_sme_portfolio()
    if partner_ids:
        partners = [p for p in partners if p["id"] in partner_ids]

    affected = get_affected_partners(reg, partners)
    results  = []

    for item in affected:
        partner = item["partner"]
        message = generate_alert_message(reg, partner, channel=channels[0])
        sends   = dispatch_alert(partner, reg, message, channels=channels)
        results.append({
            "partner_id":    partner["id"],
            "company_name":  partner["company_name"],
            "match_score":   item["score"],
            "match_reasons": item["match_reasons"],
            "ai_explanation": explain_match(reg, partner),
            "message_preview": message[:150],
            "alert_results": sends,
        })

    return jsonify({
        "regulation": {
            "id":         reg["id"],
            "short_name": reg["short_name"],
            "title":      reg["title"],
            "urgency":    reg["urgency"],
            "deadline":   reg.get("deadline_date"),
        },
        "affected_partners": len(results),
        "results": results,
    })


@pipeline_bp.route("/status", methods=["GET"])
def pipeline_status():
    """Return pipeline run history and audit log."""
    return jsonify({
        "pipeline_runs":  _pipeline_log[-10:],
        "alert_log":      get_alert_log()[:20],
        "total_runs":     len(_pipeline_log),
        "total_alerts":   len(get_alert_log()),
    })


# ── Live monitoring status endpoint ───────────────────────────────────────────

@pipeline_bp.route("/live-status", methods=["GET"])
def live_monitoring_status():
    """
    Returns current live-monitoring state: whether the system is active,
    when feeds were last polled, and any detected regulation changes.
    Also triggers a fresh poll of EUR-Lex and ECHA feeds so the frontend
    always gets up-to-date change-detection results.
    """
    now = datetime.now(timezone.utc).isoformat()

    if _live_monitor_state["started_at"] is None:
        _live_monitor_state["started_at"] = now

    _live_monitor_state["last_checked"] = now
    _live_monitor_state["check_count"] += 1

    # ── Poll each monitored source and detect changes ──────────────────────────
    source_statuses = []
    for src in _MONITORED_SOURCES:
        import requests as req_lib
        entry = {
            "name":       src["name"],
            "url":        src["url"],
            "status":     "ok",
            "changed":    False,
            "last_items": [],
            "checked_at": now,
        }
        try:
            resp = req_lib.get(src["url"], timeout=10,
                               headers={"User-Agent": "RegulatoryRadar/1.0 (EcoComply demo)"})
            resp.raise_for_status()
            content = resp.text

            # Hash the feed to detect any change
            new_hash = hashlib.md5(content.encode()).hexdigest()

            # Find previous state for this source
            prev = next((s for s in _live_monitor_state["sources"]
                         if s["name"] == src["name"]), None)

            if prev is None:
                # First poll — record baseline
                _live_monitor_state["sources"].append({
                    "name":         src["name"],
                    "last_hash":    new_hash,
                    "changed_at":   now,
                })
                entry["status"] = "baseline_recorded"
            elif prev["last_hash"] != new_hash:
                # Content changed since last poll!
                entry["changed"] = True
                prev["last_hash"] = new_hash
                prev["changed_at"] = now

                # Extract top items from new feed
                try:
                    from services.monitor import _parse_rss
                    items = _parse_rss(content, source=src["name"], max_items=3)
                    entry["last_items"] = items
                    for item in items:
                        _live_monitor_state["change_log"].insert(0, {
                            "source":      src["name"],
                            "title":       item.get("title", ""),
                            "summary":     item.get("summary", ""),
                            "link":        item.get("link", ""),
                            "detected_at": now,
                        })
                except Exception:
                    pass

                # Keep change log to last 50 entries
                _live_monitor_state["change_log"] = _live_monitor_state["change_log"][:50]
            else:
                entry["status"] = "no_change"
                # Still show last items for context
                try:
                    from services.monitor import _parse_rss
                    items = _parse_rss(content, source=src["name"], max_items=3)
                    entry["last_items"] = items
                except Exception:
                    pass

        except Exception as e:
            entry["status"] = "snapshot"
            entry["last_items"] = src.get("fallback_items", [])
            logger.warning(f"Live monitor: using snapshot for {src['name']} ({e})")

        source_statuses.append(entry)

    return jsonify({
        "live":          True,
        "status":        "monitoring",
        "started_at":    _live_monitor_state["started_at"],
        "last_checked":  now,
        "check_count":   _live_monitor_state["check_count"],
        "sources":       source_statuses,
        "change_log":    _live_monitor_state["change_log"][:10],
        "total_changes": len(_live_monitor_state["change_log"]),
        "message":       (
            f"System is LIVE — monitoring {len(_MONITORED_SOURCES)} regulatory sources. "
            f"Checked {_live_monitor_state['check_count']} time(s). "
            f"{len(_live_monitor_state['change_log'])} change(s) detected."
        ),
    })
