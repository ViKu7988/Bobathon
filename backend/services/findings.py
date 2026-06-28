"""
Findings Engine — Gap Detection with False-Positive Filtering
Deterministically assesses each product against each regulation,
applies scoping rules to eliminate false positives, then calls
HF LLM for a detailed cited explanation of each real gap.

Output shape matches sample_expected_output.json from the challenge.
EcoComply | IBM Bobathon 2025
"""

import datetime
import logging
from typing import Literal

logger = logging.getLogger(__name__)

# ── Severity mapping ───────────────────────────────────────────────────────────
SEV_ORDER = {"high": 0, "medium": 1, "low": 2}

# ── False-positive filter rules ───────────────────────────────────────────────
# Each rule is a function(product, regulation) → (is_fp: bool, reason: str)
# If ANY rule returns True, the match is marked as false_positive.

def _fp_market_mismatch(product: dict, reg: dict) -> tuple[bool, str]:
    """Regulation applies only to specific markets the product doesn't sell in."""
    reg_markets = reg.get("scope_markets", ["EU"])
    if "EU" in reg_markets:
        return False, ""  # EU = all member states, no FP
    prod_markets = product.get("markets", ["EU"])
    overlap = set(reg_markets) & set(prod_markets)
    if not overlap:
        return True, f"Regulation applies to {reg_markets} only; product sold in {prod_markets}"
    return False, ""


def _fp_substance_not_present(product: dict, reg: dict) -> tuple[bool, str]:
    """Substance-specific regulation but product doesn't contain the substance."""
    reg_substances = reg.get("scope_substances", [])
    if not reg_substances:
        return False, ""  # No substance restriction — not a substance FP
    prod_substances = product.get("substances", [])
    # If ALL required substances are absent → FP
    present = [s for s in reg_substances if s in prod_substances]
    if not present:
        return True, (
            f"Substance-specific regulation (targets {', '.join(reg_substances)}) "
            f"but product contains none of these substances"
        )
    return False, ""


def _fp_category_mismatch(product: dict, reg: dict) -> tuple[bool, str]:
    """Regulation targets specific categories product doesn't belong to."""
    reg_cats = reg.get("affected_product_categories", [])
    if not reg_cats or len(reg_cats) > 10:
        return False, ""  # "all" categories or very broad
    prod_cat = product.get("category", "")
    if prod_cat not in reg_cats:
        return True, f"Regulation scoped to {reg_cats[:4]}; product is '{prod_cat}'"
    return False, ""


def _fp_battery_type_mismatch(product: dict, reg: dict) -> tuple[bool, str]:
    """Battery regulation only applies to specific battery types."""
    reg_fam = reg.get("regulation_family", "")
    if reg_fam != "Battery":
        return False, ""
    reg_title_lower = reg.get("title", "").lower()
    prod_battery_type = product.get("battery_type", "none")

    # Passport / carbon footprint / due diligence: only industrial (>2 kWh) or LMT
    if any(kw in reg_title_lower for kw in ["passport", "carbon footprint", "due diligence", "recycled content"]):
        if product.get("battery_capacity_wh", 0) < 2000 and prod_battery_type not in ("lmt", "industrial"):
            return True, (
                f"Battery passport/carbon-footprint applies to industrial (>2 kWh) and LMT batteries; "
                f"product has {product.get('battery_capacity_wh',0)} Wh ({prod_battery_type})"
            )
    # Removability: applies to portable/button_cell consumer products
    if "removab" in reg_title_lower:
        if prod_battery_type == "none" or not product.get("has_battery"):
            return True, "Battery removability rule — product has no battery"
        if product.get("intended_use") == "industrial":
            return True, "Battery removability rule applies to consumer products, not industrial"
    return False, ""


def _fp_intended_use_mismatch(product: dict, reg: dict) -> tuple[bool, str]:
    """Consumer-safety rules don't cover medical/industrial-only equipment."""
    reg_fam = reg.get("regulation_family", "")
    intended = product.get("intended_use", "consumer")

    # GPSR and ToySafety don't apply to industrial or medical equipment
    if reg_fam in ("GPSR", "ToySafety") and intended in ("industrial", "medical"):
        return True, f"{reg_fam} applies to consumer/toy products; this is {intended} equipment"

    # ToySafety only applies to toys
    if reg_fam == "ToySafety" and intended != "toy":
        return True, f"Toy Safety applies to toys; this product has intended_use='{intended}'"

    # MDR applies only to medical purpose products
    if reg_fam == "MDR" and intended != "medical":
        return True, "MDR (medical devices regulation) applies only to medical-purpose products"

    return False, ""


def _fp_no_radio(product: dict, reg: dict) -> tuple[bool, str]:
    """RED cybersecurity requires internet-connected radio equipment."""
    reg_title = reg.get("title", "").lower()
    reg_fam   = reg.get("regulation_family", "")
    if reg_fam == "RED" and "cybersecurity" in reg_title:
        if not product.get("has_radio"):
            return True, "RED cybersecurity applies to radio/connected equipment; product has no radio"
    if reg_fam == "RED" and "common charger" in reg_title:
        connector = product.get("connector", "none")
        if connector in ("none", "barrel", "usb_c"):
            if connector == "usb_c":
                return True, "Already uses USB-C — common charger rule already satisfied"
            if connector == "none":
                return True, "Product has no wired charging port — common charger rule doesn't apply"
    return False, ""


def _fp_market_only(product: dict, reg: dict) -> tuple[bool, str]:
    """Some regulations are only for specific country markets (DE, FR)."""
    conditions = reg.get("scope_conditions", "").lower()
    prod_markets = product.get("markets", ["EU"])

    if "germany" in conditions or "(de)" in conditions or "de only" in conditions:
        if "DE" not in prod_markets and "EU" not in prod_markets:
            return True, "German-market-only regulation; product doesn't sell in Germany"
    if "france" in conditions or "(fr)" in conditions or "fr only" in conditions:
        if "FR" not in prod_markets and "EU" not in prod_markets:
            return True, "France-market-only regulation; product doesn't sell in France"
    return False, ""


def _fp_no_product(product: dict, reg: dict) -> tuple[bool, str]:
    """Catch-all: scope conditions explicitly exclude this product type."""
    conditions = reg.get("scope_conditions", "").lower()
    prod_cat   = product.get("category", "").lower()
    exclude_phrases = [
        "not in this portfolio", "not in portfolio", "not finished",
        "raw commodity", "food-contact", "smartphone", "tablet",
        "f-gas", "refrigeration", "hvac"
    ]
    for phrase in exclude_phrases:
        if phrase in conditions:
            return True, f"Regulation explicitly out of scope: '{conditions[:80]}'"
    return False, ""


FP_RULES = [
    _fp_market_mismatch,
    _fp_substance_not_present,
    _fp_category_mismatch,
    _fp_battery_type_mismatch,
    _fp_intended_use_mismatch,
    _fp_no_radio,
    _fp_market_only,
    _fp_no_product,
]


def check_false_positive(product: dict, regulation: dict) -> tuple[bool, str]:
    """
    Run all FP rules. Returns (is_false_positive, reason).
    If any rule fires, the finding is a false positive.
    """
    for rule in FP_RULES:
        try:
            is_fp, reason = rule(product, regulation)
            if is_fp:
                return True, reason
        except Exception as e:
            logger.debug(f"FP rule {rule.__name__} error: {e}")
    return False, ""


# ── Gap description builder ───────────────────────────────────────────────────

def _describe_gap(product: dict, regulation: dict) -> str:
    """Build a concise human-readable gap description from product + regulation attributes."""
    fam   = regulation.get("regulation_family", "")
    title = regulation.get("title", "")
    title_lower = title.lower()
    cat   = product.get("category", "")
    intended = product.get("intended_use", "consumer")

    # Battery-specific gaps
    if fam == "Battery":
        btype = product.get("battery_type", "none")
        bwh   = product.get("battery_capacity_wh", 0)
        if "passport" in title_lower:
            return (
                f"{'LMT' if btype=='lmt' else 'Industrial'} battery ({bwh} Wh) placed on EU market "
                "without a digital battery passport / QR data carrier."
            )
        if "removab" in title_lower:
            return (
                f"Battery embedded in device may not be independently removable by end-user "
                f"({product.get('name','')} — {btype} battery)."
            )
        if "carbon footprint" in title_lower:
            return f"Industrial/EV battery missing mandatory carbon footprint declaration and performance class."
        if "labelling" in title_lower or "label" in title_lower:
            return f"Battery/product missing required capacity, CE, QR code labelling."
        if "recycled content" in title_lower:
            return f"Industrial battery: no documented minimum recycled cobalt/lithium/nickel content."
        if "due diligence" in title_lower:
            return f"No supply-chain due diligence policy for battery raw materials (cobalt, lithium, nickel)."

    # RoHS substance gaps
    if fam == "RoHS":
        substances = product.get("substances", [])
        if substances:
            return (
                f"Product contains restricted substance(s) {', '.join(substances)} — "
                "must confirm homogeneous-material content is within RoHS thresholds or apply for exemption."
            )
        return "Product may contain RoHS-restricted heavy metals or phthalates — confirmation required."

    # REACH SVHC
    if fam == "REACH":
        substances = product.get("substances", [])
        if substances:
            return (
                f"Product contains SVHC substance(s) {', '.join(substances)} above 0.1% w/w — "
                "SCIP notification to ECHA required; customer communication duty triggered."
            )
        return "Product may contain REACH SVHC substances — screening and SCIP notification required."

    # RED
    if fam == "RED":
        connector = product.get("connector", "")
        if "common charger" in title_lower and connector in ("micro_usb", "proprietary"):
            return (
                f"Product uses '{connector}' charging port — "
                "USB-C is now mandatory for portable electronics on EU market."
            )
        if "cybersecurity" in title_lower:
            return (
                "Internet-connected radio device must comply with RED Art. 3(3)(d)(e)(f) "
                "(EN 18031) — cybersecurity conformity assessment not documented."
            )
        return f"Radio equipment compliance gap under RED: {title[:80]}"

    # GPSR
    if fam == "GPSR":
        btype = product.get("battery_type", "")
        if btype == "button_cell" and "button" in title_lower:
            return (
                "Product contains button/coin cell battery — compartment must be child-resistant "
                "and carry mandatory safety warnings."
            )
        if "online" in title_lower:
            return "Online product listing missing required GPSR safety information and recall documentation."
        if "software" in title_lower or "recall" in title_lower:
            return "Connected product missing documented software-update and recall pathway."
        return f"General product safety gap: {title[:80]}"

    # PPWR
    if fam == "PPWR":
        pkgs = product.get("packaging", [])
        if "plastic_film" in pkgs:
            return (
                "Product uses plastic-film packaging — "
                "PPWR requires minimum recycled content and recyclability compliance from 2027."
            )
        return "Packaging must meet PPWR recyclability, recycled-content, and labelling requirements."

    # WEEE
    if fam == "WEEE":
        return (
            f"EEE placed on EU market — WEEE crossed-out wheelie-bin marking and "
            "national producer registration must be current."
        )

    # ToySafety
    if fam == "ToySafety":
        substances = product.get("substances", [])
        if substances:
            return f"Toy contains restricted chemical(s) {', '.join(substances)} — re-test against tighter limits."
        return "Electronic toy must comply with revised chemical limits and safety requirements."

    # MDR
    if fam == "MDR":
        return (
            "Body-worn device with medical intended purpose — "
            "must be classified under MDR with full clinical evidence."
        )

    # ESPR / DPP
    if fam == "ESPR":
        return (
            f"{cat} must carry a Digital Product Passport (DPP) with material, "
            "repair, and carbon data per ESPR pilot."
        )

    # Machinery
    if fam == "Machinery":
        return f"{cat} must meet New Machinery Regulation safety and software risk assessment requirements."

    # Default
    return f"Compliance gap identified under {regulation.get('regulation_number', title[:60])}."


# ── Days-to-deadline helper ───────────────────────────────────────────────────

def _days_left(deadline_str: str | None) -> int | None:
    if not deadline_str:
        return None
    try:
        dl = datetime.datetime.strptime(deadline_str, "%Y-%m-%d").date()
        return (dl - datetime.date.today()).days
    except ValueError:
        return None


# ── Main findings function ─────────────────────────────────────────────────────

def generate_findings(partners: list, regulations: list,
                      use_llm: bool = True, include_fp: bool = False) -> list:
    """
    Core gap-detection engine.

    For each partner × regulation (deduplicated):
      - Evaluates all products under that partner for the regulation
      - Keeps the one product with the worst gap (highest severity)
      - Applies false-positive filter rules per product
      - If real gap: builds structured finding
      - If LLM available: enriches with cited reasoning

    Deduplication is the correct compliance approach: one regulatory obligation
    per partner per regulation, represented by the most critical product.

    Returns a list of finding dicts (shape matches sample_expected_output.json).
    include_fp=True also returns false positives (one per partner×reg, same dedup).
    """
    from services.hf_llm import reason_gap, reason_false_positive

    SEV_NUM = {"high": 0, "medium": 1, "low": 2}

    # ── Pass 1: gather all (partner × regulation × product) candidates ─────────
    # Structure: {(partner_id, reg_id): {"real": best_real_gap, "fp": first_fp}}
    candidates: dict[tuple, dict] = {}

    for partner in partners:
        partner_id   = partner["id"]
        company_name = partner["company_name"]
        products     = partner.get("products", [])
        if not products:
            continue

        for reg in regulations:
            if not reg.get("affected_product_categories"):
                continue

            key = (partner_id, reg["id"])
            best_real: dict | None  = None
            first_fp:  dict | None  = None

            for product in products:
                product_id = product.get("product_id", "")
                prod_name  = product.get("name", product_id)

                is_fp, fp_reason = check_false_positive(product, reg)

                if is_fp:
                    # Record first FP encountered for this partner×reg
                    if first_fp is None:
                        first_fp = {
                            "product":    product,
                            "product_id": product_id,
                            "prod_name":  prod_name,
                            "fp_reason":  fp_reason,
                        }
                    continue

                # Real gap — compute severity
                deadline = reg.get("deadline_date", "")
                days     = _days_left(deadline)
                severity = reg.get("urgency", "medium")
                if days is not None and days < 0 and severity == "medium":
                    severity = "high"

                gap_desc = _describe_gap(product, reg)

                candidate = {
                    "product":    product,
                    "product_id": product_id,
                    "prod_name":  prod_name,
                    "gap_desc":   gap_desc,
                    "severity":   severity,
                    "days":       days,
                    "deadline":   deadline,
                }

                # Keep worst severity; break ties by soonest deadline
                if best_real is None:
                    best_real = candidate
                else:
                    curr_sev  = SEV_NUM.get(best_real["severity"], 2)
                    new_sev   = SEV_NUM.get(severity, 2)
                    if new_sev < curr_sev:
                        best_real = candidate
                    elif new_sev == curr_sev:
                        curr_days = best_real["days"] if best_real["days"] is not None else 9999
                        new_days  = days           if days           is not None else 9999
                        if new_days < curr_days:
                            best_real = candidate

            candidates[key] = {"partner": partner, "reg": reg,
                                "real": best_real, "fp": first_fp}

    # ── Pass 2: build findings from deduplicated candidates ────────────────────
    findings = []

    for (partner_id, reg_id), cand in candidates.items():
        partner      = cand["partner"]
        reg          = cand["reg"]
        company_name = partner["company_name"]
        best_real    = cand["real"]
        first_fp     = cand["fp"]

        action     = (reg.get("required_actions") or ["Review compliance requirements"])[0]
        source_url = reg.get("source_url", "#")

        if best_real is not None:
            # ── Emit real gap ──────────────────────────────────────────────────
            product    = best_real["product"]
            product_id = best_real["product_id"]
            prod_name  = best_real["prod_name"]
            gap_desc   = best_real["gap_desc"]
            severity   = best_real["severity"]
            days       = best_real["days"]
            deadline   = best_real["deadline"]

            llm_reasoning = ""
            if use_llm:
                try:
                    llm_reasoning = reason_gap(product, reg, gap_desc, source_url)
                except Exception as e:
                    logger.warning(f"LLM reasoning failed for {product_id}/{reg_id}: {e}")

            findings.append({
                "company":            company_name,
                "partner_id":         partner_id,
                "product_id":         product_id,
                "product":            prod_name,
                "regulation":         f"{reg.get('title','')} ({reg.get('regulation_number','')})",
                "regulation_id":      reg_id,
                "regulation_family":  reg.get("regulation_family", ""),
                "regulation_title":   reg.get("title", ""),
                "regulation_number":  reg.get("regulation_number", ""),
                "requirement":        action,
                "source_url":         source_url,
                "gap":                gap_desc,
                "deadline":           deadline,
                "days_left":          days,
                "severity":           severity,
                "recommended_action": action,
                "llm_reasoning":      llm_reasoning or gap_desc,
                "is_false_positive":  False,
                # Dashboard extras
                "product_category":      product.get("category", ""),
                "product_intended_use":  product.get("intended_use", ""),
                "product_substances":    product.get("substances", []),
                "product_has_radio":     product.get("has_radio", False),
                "product_battery_type":  product.get("battery_type", "none"),
                "product_connector":     product.get("connector", ""),
                "preferred_channel":     partner.get("preferred_channel", "email"),
                "contact_email":         partner.get("email", ""),
                "contact_phone":         partner.get("phone", ""),
            })

        elif include_fp and first_fp is not None:
            # ── Emit FP (only if ALL products for this partner×reg are FP) ────
            product    = first_fp["product"]
            product_id = first_fp["product_id"]
            prod_name  = first_fp["prod_name"]
            fp_reason  = first_fp["fp_reason"]

            fp_explanation = ""
            if use_llm:
                try:
                    fp_explanation = reason_false_positive(product, reg, fp_reason)
                except Exception:
                    fp_explanation = fp_reason

            findings.append({
                "company":               company_name,
                "partner_id":            partner_id,
                "product_id":            product_id,
                "product":               prod_name,
                "regulation":            reg.get("title", ""),
                "regulation_id":         reg_id,
                "regulation_family":     reg.get("regulation_family", ""),
                "regulation_title":      reg.get("title", ""),
                "requirement":           action,
                "source_url":            source_url,
                "gap":                   None,
                "deadline":              reg.get("deadline_date", ""),
                "days_left":             _days_left(reg.get("deadline_date")),
                "severity":              reg.get("urgency", "low"),
                "recommended_action":    None,
                "is_false_positive":     True,
                "false_positive_reason": fp_explanation or fp_reason,
                "llm_reasoning":         fp_explanation,
            })

    # ── Sort: severity first, then soonest deadline ────────────────────────────
    def sort_key(f):
        sev   = SEV_ORDER.get(f.get("severity", "low"), 2)
        days  = f.get("days_left")
        d_key = days if days is not None else 9999
        return (sev, d_key)

    findings.sort(key=sort_key)
    real_count = sum(1 for f in findings if not f.get("is_false_positive"))
    fp_count   = sum(1 for f in findings if     f.get("is_false_positive"))
    logger.info(
        f"Findings engine (deduplicated): {real_count} real gaps, "
        f"{fp_count} false positives across {len(partners)} partners"
    )
    return findings


def get_findings_summary(findings: list) -> dict:
    """Compute aggregate stats for the findings set."""
    real    = [f for f in findings if not f.get("is_false_positive")]
    fps     = [f for f in findings if f.get("is_false_positive")]
    high    = [f for f in real if f.get("severity") == "high"]
    medium  = [f for f in real if f.get("severity") == "medium"]
    low     = [f for f in real if f.get("severity") == "low"]

    companies = {}
    for f in real:
        pid = f["partner_id"]
        if pid not in companies:
            companies[pid] = {"company": f["company"], "gap_count": 0, "severities": []}
        companies[pid]["gap_count"] += 1
        companies[pid]["severities"].append(f.get("severity", "low"))

    return {
        "total_findings":       len(real),
        "false_positives":      len(fps),
        "high":                 len(high),
        "medium":               len(medium),
        "low":                  len(low),
        "companies_affected":   len(companies),
        "by_company":           sorted(companies.values(), key=lambda x: x["gap_count"], reverse=True)[:10],
    }
