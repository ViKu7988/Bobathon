"""
Regulation Monitor Service
Fetches live regulation updates from EUR-Lex / ECHA RSS feeds,
or falls back to pre-loaded JSON/HTML snapshots.
EcoComply | IBM Bobathon 2025
"""

import json
import logging
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib  import Path

import requests
from flask import current_app

logger = logging.getLogger(__name__)

# ── EUR-Lex CELLAR SPARQL / RSS endpoints ─────────────────────────────────────
EURLEX_RSS_URL = (
    "https://eur-lex.europa.eu/tools/rss.do?"
    "type=legislation"
    "&legalType=REG"
    "&domain=eu_law"
    "&lng=EN"
)

# ECHA SVHC news feed
ECHA_NEWS_RSS = "https://echa.europa.eu/rss/echa-news.xml"

_HEADERS = {
    "User-Agent": (
        "RegulatoryRadar/1.0 (EcoComply Bobathon demo; "
        "contact: demo@ecocomply.demo)"
    )
}


# ── Live fetch ─────────────────────────────────────────────────────────────────

def fetch_eurlex_updates(max_items: int = 10) -> list:
    """
    Pull the latest items from EUR-Lex RSS feed.
    Returns a list of {title, link, published, summary} dicts.
    """
    try:
        resp = requests.get(EURLEX_RSS_URL, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        return _parse_rss(resp.text, source="EUR-Lex", max_items=max_items)
    except Exception as e:
        logger.warning(f"EUR-Lex live fetch failed ({e}) — using snapshot fallback")
        return _load_html_snapshot()


def fetch_echa_updates(max_items: int = 5) -> list:
    """Pull the latest SVHC/chemical updates from ECHA news RSS."""
    try:
        resp = requests.get(ECHA_NEWS_RSS, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        return _parse_rss(resp.text, source="ECHA", max_items=max_items)
    except Exception as e:
        logger.warning(f"ECHA live fetch failed ({e}) — returning empty list")
        return []


def _parse_rss(xml_text: str, source: str, max_items: int = 10) -> list:
    """Parse an RSS 2.0 or Atom feed and return normalised item list."""
    items = []
    try:
        root = ET.fromstring(xml_text)
        ns   = {}
        # RSS 2.0
        for item in root.findall(".//item")[:max_items]:
            items.append({
                "title":     _text(item, "title"),
                "link":      _text(item, "link"),
                "published": _text(item, "pubDate"),
                "summary":   _clean(_text(item, "description")),
                "source":    source,
                "raw_text":  _clean(_text(item, "description")),
            })
        # Atom
        if not items:
            atom_ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("atom:entry", atom_ns)[:max_items]:
                items.append({
                    "title":     _text(entry, "atom:title", atom_ns),
                    "link":      entry.find("atom:link", atom_ns).get("href", "") if entry.find("atom:link", atom_ns) is not None else "",
                    "published": _text(entry, "atom:published", atom_ns),
                    "summary":   _clean(_text(entry, "atom:summary", atom_ns)),
                    "source":    source,
                    "raw_text":  _clean(_text(entry, "atom:summary", atom_ns)),
                })
    except ET.ParseError as e:
        logger.error(f"RSS parse error for {source}: {e}")
    return items


def _text(element, tag: str, ns: dict = None) -> str:
    child = element.find(tag, ns or {})
    return (child.text or "").strip() if child is not None else ""


def _clean(html: str) -> str:
    """Strip HTML tags from a string."""
    return re.sub(r"<[^>]+>", " ", html or "").strip()


# ── Snapshot / pre-loaded fallback ────────────────────────────────────────────

def _load_html_snapshot() -> list:
    """Load the pre-saved EUR-Lex HTML snapshot and return normalised items."""
    data_dir      = current_app.config.get("DATA_DIR", "../data")
    snapshot_path = Path(data_dir) / "eurlex_sample.html"

    if not snapshot_path.exists():
        logger.warning("EUR-Lex HTML snapshot not found")
        return []

    with open(snapshot_path, encoding="utf-8") as f:
        raw = f.read()

    return [{
        "title":     "Regulation (EU) 2023/1542 — Battery Regulation + ECHA SVHC Update Jan 2025",
        "link":      "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32023R1542",
        "published": "2023-07-28",
        "summary":   "EU Battery Passport mandatory from 18 Feb 2027. ECHA adds 3 new SVHCs to Candidate List.",
        "source":    "EUR-Lex Snapshot",
        "raw_text":  _clean(raw),
    }]


def load_preloaded_regulations() -> list:
    """Load regulations from the pre-parsed JSON file."""
    data_dir = current_app.config.get("DATA_DIR", "../data")
    reg_path = Path(data_dir) / "regulations.json"

    if not reg_path.exists():
        logger.error(f"Regulations file not found: {reg_path}")
        return []

    with open(reg_path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("regulations", [])


def load_sme_portfolio(filepath: str = None) -> list:
    """Load SME partner portfolio from JSON (default or uploaded path)."""
    if not filepath:
        data_dir  = current_app.config.get("DATA_DIR", "../data")
        filepath  = str(Path(data_dir) / "sme_portfolio.json")

    if not os.path.exists(filepath):
        logger.error(f"SME portfolio file not found: {filepath}")
        return []

    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    # Support both direct list and wrapped {"partners": [...]}
    if isinstance(data, list):
        return data
    return data.get("partners", [])


def load_uploaded_portfolio(filepath: str) -> list:
    """Load and validate an uploaded partner portfolio JSON file."""
    try:
        partners = load_sme_portfolio(filepath)
        # Minimal validation — only id and company_name are truly required
        required = {"id", "company_name"}
        valid    = []
        for p in partners:
            if required.issubset(set(p.keys())):
                # Ensure products list exists (may be empty from CSV upload)
                if "products" not in p:
                    p["products"] = []
                valid.append(p)
            else:
                logger.warning(f"Skipping invalid partner record (missing fields): {p.get('id','?')}")
        return valid
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Failed to load uploaded portfolio: {e}")
        return []


def get_regulation_snapshot() -> dict:
    """Return a summary of the current monitoring state."""
    return {
        "timestamp":     datetime.now(timezone.utc).isoformat(),
        "sources":       ["EUR-Lex (RSS)", "ECHA (RSS)", "Pre-loaded JSON snapshots"],
        "last_checked":  datetime.now(timezone.utc).isoformat(),
        "status":        "active",
    }
