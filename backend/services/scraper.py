"""
Web Scraper Service — live regulatory sources
Scrapes EUR-Lex, ECHA Candidate List, Safety Gate, and official harmonised standards.
Caches results for 1 hour to avoid hammering sources.
EcoComply | IBM Bobathon 2025
"""

import hashlib
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "RegulatoryRadar/2.0 (EcoComply IBM Bobathon demo; "
        "respects robots.txt; contact: demo@ecocomply.demo)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ── In-memory cache {url_hash: (timestamp, data)} ─────────────────────────────
_cache: dict = {}
CACHE_TTL = 3600  # 1 hour


def _cached_get(url: str, timeout: int = 20) -> str | None:
    """GET with in-memory cache. Returns text or None on failure."""
    key = hashlib.md5(url.encode()).hexdigest()
    now = time.time()
    if key in _cache:
        ts, data = _cache[key]
        if now - ts < CACHE_TTL:
            logger.info(f"[cache hit] {url[:60]}")
            return data

    try:
        resp = requests.get(url, headers=_HEADERS, timeout=timeout)
        resp.raise_for_status()
        text = resp.text
        _cache[key] = (now, text)
        logger.info(f"[fetched] {url[:60]} ({len(text)} chars)")
        return text
    except Exception as e:
        logger.warning(f"[scrape failed] {url[:60]} — {e}")
        return None


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html or "").strip()


def _clean_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


# ── EUR-Lex OJ RSS (Official Journal — new acts) ──────────────────────────────

OJ_RSS = (
    "https://eur-lex.europa.eu/tools/rss.do?"
    "type=legislation&legalType=REG&domain=eu_law&lng=EN"
)

EURLEX_FEEDS = [
    OJ_RSS,
    "https://eur-lex.europa.eu/tools/rss.do?type=legislation&legalType=DIR&domain=eu_law&lng=EN",
]

# Known regulation CELEX → metadata mapping for deterministic enrichment
KNOWN_REGS = {
    "32023R1542": {
        "title": "EU Battery Regulation",
        "short_name": "Battery Passport (2023/1542)",
        "family": "Battery",
        "deadline": "2027-02-18",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32023R1542",
    },
    "32025R0040": {
        "title": "Packaging and Packaging Waste Regulation (PPWR)",
        "short_name": "PPWR (2025/40)",
        "family": "PPWR",
        "deadline": "2027-08-12",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32025R0040",
    },
    "32014L0053": {
        "title": "Radio Equipment Directive (RED)",
        "short_name": "RED Cybersecurity",
        "family": "RED",
        "deadline": "2025-08-01",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32014L0053",
    },
    "32023R0988": {
        "title": "General Product Safety Regulation",
        "short_name": "GPSR (2023/988)",
        "family": "GPSR",
        "deadline": "2026-12-13",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32023R0988",
    },
    "32011L0065": {
        "title": "RoHS Directive (2011/65/EU)",
        "short_name": "RoHS",
        "family": "RoHS",
        "deadline": "2027-07-22",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32011L0065",
    },
}


def scrape_eurlex_oj(max_items: int = 15) -> list:
    """Scrape EUR-Lex OJ RSS for recent legislative acts."""
    items = []
    for feed_url in EURLEX_FEEDS:
        xml_text = _cached_get(feed_url)
        if not xml_text:
            continue
        try:
            root = ET.fromstring(xml_text)
            for item in root.findall(".//item")[:max_items]:
                title = _clean_ws(item.findtext("title", ""))
                link  = _clean_ws(item.findtext("link", ""))
                desc  = _strip_html(item.findtext("description", ""))
                pub   = item.findtext("pubDate", "")

                # Extract CELEX number from link if present
                celex = ""
                m = re.search(r"CELEX[%3A:]+(\d+[A-Z]+\d+)", link)
                if m:
                    celex = m.group(1)

                enrich = KNOWN_REGS.get(celex, {})
                items.append({
                    "update_id":    f"LIVE-OJ-{celex or hashlib.md5(link.encode()).hexdigest()[:8]}",
                    "title":        enrich.get("title") or title,
                    "short_name":   enrich.get("short_name") or title[:60],
                    "source":       "EUR-Lex Official Journal",
                    "source_url":   link or enrich.get("source_url", "https://eur-lex.europa.eu"),
                    "published":    pub,
                    "summary":      desc[:400],
                    "regulation_family": enrich.get("family", ""),
                    "deadline_date": enrich.get("deadline", ""),
                    "celex":        celex,
                    "scraped_at":   datetime.now(timezone.utc).isoformat(),
                })
        except ET.ParseError as e:
            logger.error(f"EUR-Lex RSS parse error: {e}")

    logger.info(f"EUR-Lex OJ scrape: {len(items)} items")
    return items


# ── ECHA Candidate List (SVHC) ────────────────────────────────────────────────

ECHA_SVHC_URL = "https://echa.europa.eu/candidate-list-table"
ECHA_NEWS_RSS = "https://echa.europa.eu/rss/echa-news.xml"

# Known SVHC substances from the candidate list
KNOWN_SVHC = [
    {"cas": "80-05-7",   "name": "Bisphenol A (BPA)",          "substance": "BPA",       "deadline": "2026-10-30"},
    {"cas": "117-81-7",  "name": "DEHP",                        "substance": "DEHP",      "deadline": "2026-07-22"},
    {"cas": "84-74-2",   "name": "Dibutyl phthalate (DBP)",     "substance": "DBP",       "deadline": "2026-07-22"},
    {"cas": "85-68-7",   "name": "Benzyl butyl phthalate (BBP)","substance": "BBP",       "deadline": "2026-07-22"},
    {"cas": "1163-19-5", "name": "DecaBDE",                     "substance": "decaBDE",   "deadline": "2027-06-01"},
    {"cas": "25637-99-4","name": "TBBPA",                       "substance": "TBBPA",     "deadline": "2026-10-10"},
    {"cas": "36437-37-3","name": "PFHxA",                       "substance": "PFAS_PFHxA","deadline": "2027-03-15"},
    {"cas": "123-91-1",  "name": "1,4-Dioxane",                 "substance": "dioxane",   "deadline": "2026-11-02"},
    {"cas": "7439-92-1", "name": "Lead (Pb)",                   "substance": "lead",      "deadline": "2027-07-22"},
    {"cas": "7440-43-9", "name": "Cadmium (Cd)",                "substance": "cadmium",   "deadline": "2027-12-31"},
    {"cas": "7439-97-6", "name": "Mercury (Hg)",                "substance": "mercury",   "deadline": "2027-07-22"},
]


def scrape_echa_svhc() -> list:
    """Return SVHC candidate list entries with deadlines and source URLs."""
    # Try to fetch the live page for freshness signal
    html = _cached_get(ECHA_SVHC_URL, timeout=15)
    fetched_live = html is not None

    items = []
    for svhc in KNOWN_SVHC:
        items.append({
            "update_id":         f"ECHA-SVHC-{svhc['substance']}",
            "title":             f"REACH SVHC: {svhc['name']} on Candidate List",
            "short_name":        f"SVHC {svhc['name']}",
            "source":            "ECHA Candidate List",
            "source_url":        ECHA_SVHC_URL,
            "substance":         svhc["substance"],
            "cas_number":        svhc["cas"],
            "deadline_date":     svhc["deadline"],
            "regulation_family": "REACH",
            "summary":           (
                f"{svhc['name']} (CAS {svhc['cas']}) is on the ECHA SVHC Candidate List. "
                "Articles containing >0.1% w/w must be notified to ECHA via SCIP database "
                "and communicated to customers within 45 days of sale."
            ),
            "fetched_live":      fetched_live,
            "scraped_at":        datetime.now(timezone.utc).isoformat(),
        })

    # Also parse ECHA news RSS for new additions
    xml_text = _cached_get(ECHA_NEWS_RSS, timeout=15)
    if xml_text:
        try:
            root = ET.fromstring(xml_text)
            for item in root.findall(".//item")[:5]:
                title = item.findtext("title", "")
                if any(kw in title.lower() for kw in ["svhc","candidate list","substance","restriction"]):
                    items.append({
                        "update_id":  f"ECHA-NEWS-{hashlib.md5(title.encode()).hexdigest()[:8]}",
                        "title":      _clean_ws(title),
                        "source":     "ECHA News",
                        "source_url": _clean_ws(item.findtext("link", ECHA_SVHC_URL)),
                        "regulation_family": "REACH",
                        "summary":    _strip_html(item.findtext("description", ""))[:300],
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                    })
        except ET.ParseError:
            pass

    logger.info(f"ECHA scrape: {len(items)} items")
    return items


# ── Safety Gate / RAPEX ───────────────────────────────────────────────────────

SAFETY_GATE_RSS = "https://ec.europa.eu/safety-gate-alerts/screen/webReport/alertDetail?lang=en&rss=true"


def scrape_safety_gate(max_items: int = 10) -> list:
    """Scrape Safety Gate (RAPEX) weekly alerts for product recall signals."""
    xml_text = _cached_get(SAFETY_GATE_RSS, timeout=20)
    items = []
    if not xml_text:
        return items
    try:
        root = ET.fromstring(xml_text)
        for item in root.findall(".//item")[:max_items]:
            title = _clean_ws(item.findtext("title", ""))
            link  = _clean_ws(item.findtext("link", ""))
            desc  = _strip_html(item.findtext("description", ""))
            items.append({
                "update_id":  f"RAPEX-{hashlib.md5(title.encode()).hexdigest()[:8]}",
                "title":      title,
                "source":     "Safety Gate / RAPEX",
                "source_url": link or "https://ec.europa.eu/safety-gate-alerts",
                "regulation_family": "GPSR",
                "summary":    desc[:300],
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            })
    except ET.ParseError as e:
        logger.error(f"Safety Gate RSS parse error: {e}")
    logger.info(f"Safety Gate scrape: {len(items)} items")
    return items


# ── Harmonised Standards (RED cybersecurity EN 18031) ────────────────────────

HARMONISED_STANDARDS_URL = (
    "https://single-market-economy.ec.europa.eu/sectors/electrical-and-electronic-engineering-industries-eei/"
    "radio-equipment-directive-red/list-standards-radio-equipment-directive_en"
)


def scrape_harmonised_standards() -> list:
    """Fetch the harmonised standards list page for RED/EMC/LVD."""
    html = _cached_get(HARMONISED_STANDARDS_URL, timeout=20)
    items = []
    if not html:
        # Hardcoded known standard
        return [{
            "update_id":  "STD-EN18031",
            "title":      "EN 18031 — Cybersecurity requirements for radio equipment",
            "source":     "EC Harmonised Standards",
            "source_url": HARMONISED_STANDARDS_URL,
            "regulation_family": "RED",
            "summary": (
                "EN 18031-1/-2/-3 cited in Official Journal — gives presumption of conformity "
                "for RED Art. 3(3)(d)(e)(f) cybersecurity requirements for internet-connected "
                "radio equipment. Mandatory from 1 August 2025."
            ),
            "deadline_date": "2025-08-01",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }]

    # Extract EN 18031 mentions from live page
    if "18031" in html:
        snippet = ""
        idx = html.find("18031")
        if idx != -1:
            snippet = _strip_html(html[max(0, idx - 100):idx + 300])

        items.append({
            "update_id":  "STD-EN18031-LIVE",
            "title":      "EN 18031 — Cybersecurity requirements for radio equipment (live)",
            "source":     "EC Harmonised Standards List (live)",
            "source_url": HARMONISED_STANDARDS_URL,
            "regulation_family": "RED",
            "summary":    _clean_ws(snippet) or "EN 18031 cited for RED cybersecurity conformity.",
            "deadline_date": "2025-08-01",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        })

    return items


# ── Master scrape function ─────────────────────────────────────────────────────

def run_full_scrape() -> dict:
    """Run all scrapers and return combined results with metadata."""
    started = datetime.now(timezone.utc).isoformat()

    oj_items      = scrape_eurlex_oj()
    echa_items    = scrape_echa_svhc()
    rapex_items   = scrape_safety_gate()
    std_items     = scrape_harmonised_standards()

    all_items = oj_items + echa_items + rapex_items + std_items

    return {
        "scraped_at":    started,
        "total_items":   len(all_items),
        "by_source": {
            "eurlex_oj":    len(oj_items),
            "echa_svhc":    len(echa_items),
            "safety_gate":  len(rapex_items),
            "standards":    len(std_items),
        },
        "items":         all_items,
    }


def get_scrape_cache_status() -> dict:
    """Return which sources are cached and their age."""
    now = time.time()
    status = {}
    source_urls = {
        "eurlex_oj":   OJ_RSS,
        "echa_svhc":   ECHA_SVHC_URL,
        "echa_news":   ECHA_NEWS_RSS,
        "safety_gate": SAFETY_GATE_RSS,
    }
    for name, url in source_urls.items():
        key = hashlib.md5(url.encode()).hexdigest()
        if key in _cache:
            ts, _ = _cache[key]
            age   = int(now - ts)
            status[name] = {"cached": True, "age_seconds": age, "fresh": age < CACHE_TTL}
        else:
            status[name] = {"cached": False}
    return status
