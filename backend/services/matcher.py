"""
Regulation ↔ Partner Matcher Service
Scores and ranks which regulations affect which SME partners.
Uses a combination of:
  - Direct product category intersection
  - Certification / compliance stream overlap
  - Sector-level heuristics
EcoComply | IBM Bobathon 2025
"""

import logging
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)


# ── Sector-level fallback mappings ─────────────────────────────────────────────
# Maps broad sectors to regulation categories they're likely exposed to
SECTOR_REGULATION_MAP = {
    "Electronics":          ["product_compliance", "chemical_compliance"],
    "Consumer Electronics": ["product_compliance", "chemical_compliance"],
    "Lighting":             ["product_compliance", "chemical_compliance"],
    "Power Electronics":    ["product_compliance"],
    "Energy Storage":       ["product_compliance"],
    "E-Mobility":           ["product_compliance"],
    "Smart Home":           ["product_compliance"],
    "Wearables":            ["product_compliance", "chemical_compliance"],
    "Medical Devices":      ["product_compliance"],
    "Toy / Electronics":    ["product_compliance", "chemical_compliance"],
    "Cables & Connectors":  ["product_compliance", "chemical_compliance"],
    "Displays":             ["product_compliance"],
    "Industrial IoT":       ["product_compliance", "chemical_compliance"],
    "Renewable Energy":     ["product_compliance"],
    "Networking":           ["product_compliance"],
    "Home Appliances":      ["product_compliance"],
    "3D Printing":          ["product_compliance"],
    "Drones / UAV":         ["product_compliance"],
    "Packaging":            ["product_compliance"],
    "Chemical / Materials": ["chemical_compliance"],
    "Automotive":           ["product_compliance", "import_compliance"],
    "Steel / Manufacturing":["import_compliance"],
}

# Certification → compliance stream mapping
CERT_STREAM_MAP = {
    "CE":       ["CE"],
    "RoHS":     ["RoHS"],
    "REACH":    ["REACH", "SCIP"],
    "WEEE":     ["WEEE"],
    "RED":      ["RED", "CE"],
    "MDR":      ["MDR"],
    "ISO14001": ["ISO14001", "EPR"],
    "CBAM":     ["CBAM"],
}


def match_regulations_to_partner(partner: dict, regulations: list) -> list:
    """
    Given a partner profile and a list of regulations, return a list of
    match results sorted by relevance score (highest first).

    Each match result contains:
      - regulation: the regulation dict
      - score: 0–100 relevance score
      - match_reasons: list of strings explaining the match
      - matched_categories: product categories that triggered the match
      - matched_streams: compliance streams that triggered the match
    """
    results = []
    partner_cats       = set(partner.get("product_categories", []))
    partner_substances = set(partner.get("substances", []))
    partner_certs      = set(partner.get("certifications", []))
    partner_sector     = partner.get("sector", "")

    # Build partner compliance streams from certs
    partner_streams = set()
    for cert in partner_certs:
        partner_streams.update(CERT_STREAM_MAP.get(cert, [cert]))

    # Also expand streams from product-level compliance_streams (richer data)
    for product in partner.get("products", []):
        for stream in product.get("compliance_streams", []):
            partner_streams.add(stream)
            partner_streams.update(CERT_STREAM_MAP.get(stream, []))

    for reg in regulations:
        score, reasons, matched_cats, matched_streams = _score_match(
            partner_cats, partner_substances, partner_streams, partner_certs, partner_sector, reg
        )
        if score > 0:
            results.append({
                "regulation":        reg,
                "score":             score,
                "match_reasons":     reasons,
                "matched_categories": list(matched_cats),
                "matched_streams":   list(matched_streams),
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def _score_match(
    partner_cats: set,
    partner_substances: set,
    partner_streams: set,
    partner_certs: set,
    partner_sector: str,
    reg: dict,
) -> Tuple[int, List[str], set, set]:
    """Compute match score and reasons for one regulation against one partner."""
    score = 0
    reasons = []
    matched_cats    = set()
    matched_streams = set()

    reg_cats       = set(reg.get("affected_product_categories", []))
    reg_streams    = set(reg.get("affected_compliance_streams", []))
    reg_substances = set(reg.get("scope_substances", []))

    # 1. Direct product category match (highest weight)
    cat_overlap = partner_cats & reg_cats
    if cat_overlap:
        cat_score = min(60, len(cat_overlap) * 20)
        score += cat_score
        matched_cats = cat_overlap
        reasons.append(
            f"Product category match: {', '.join(c.replace('_', ' ') for c in cat_overlap)}"
        )

    # 2. Substance match — chemical regulations (high precision signal)
    if reg_substances:
        substance_overlap = partner_substances & reg_substances
        if substance_overlap:
            score += min(40, len(substance_overlap) * 20)
            reasons.append(
                f"Substance match: {', '.join(substance_overlap)} present in products"
            )

    # 3. Compliance stream / certification match (medium weight)
    stream_overlap = partner_streams & reg_streams
    if stream_overlap:
        stream_score = min(30, len(stream_overlap) * 10)
        score += stream_score
        matched_streams = stream_overlap
        reasons.append(
            f"Compliance stream match: {', '.join(stream_overlap)}"
        )

    # 4. Sector-level heuristic (low weight — broadens coverage)
    if score == 0:
        sector_reg_cats = SECTOR_REGULATION_MAP.get(partner_sector, [])
        if reg.get("category") in sector_reg_cats:
            score += 10
            reasons.append(
                f"Sector exposure: '{partner_sector}' is typically subject to {reg.get('category', 'this regulation type')}"
            )

    # 5. Urgency boost
    if score > 0:
        urgency_boost = {"critical": 10, "high": 5, "medium": 2, "low": 0}
        score += urgency_boost.get(reg.get("urgency", "low"), 0)

    return score, reasons, matched_cats, matched_streams


def match_all_partners(partners: list, regulations: list) -> dict:
    """
    Run matching for all partners against all regulations.
    Returns {partner_id: [match_results]} dict.
    """
    result = {}
    for partner in partners:
        pid     = partner["id"]
        matches = match_regulations_to_partner(partner, regulations)
        result[pid] = matches
        logger.info(
            f"Partner {pid} ({partner['company_name']}): "
            f"{len(matches)} regulation(s) matched"
        )
    return result


def get_affected_partners(regulation: dict, partners: list, min_score: int = 10) -> list:
    """
    Given a single regulation, return all partners it affects (score >= min_score).
    Sorted by score descending.
    """
    affected = []
    for partner in partners:
        matches = match_regulations_to_partner(partner, [regulation])
        if matches and matches[0]["score"] >= min_score:
            affected.append({
                "partner":       partner,
                "score":         matches[0]["score"],
                "match_reasons": matches[0]["match_reasons"],
                "matched_categories": matches[0]["matched_categories"],
            })
    affected.sort(key=lambda x: x["score"], reverse=True)
    return affected
