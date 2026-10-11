import re
from typing import Any, Dict, List, Optional


def normalize_text(text: str) -> str:
    text = str(text or "").lower().replace("°", " degree ")
    return re.sub(r"\s+", " ", text).strip()


def _number(pattern: str, text: str) -> Optional[float]:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except (TypeError, ValueError):
        return None


def detect_property(text: str) -> Optional[str]:
    t = normalize_text(text)
    # Check maintenance intervals before generic properties.
    if re.search(r"\b(inspect(?:ed|ion)?|service|maintenance|replace(?:ment)?)\b", t) and re.search(
        r"\b(every|each|per)\b|\b\d+(?:\.\d+)?\s*(?:operating\s*)?hours?\b", t
    ):
        return "inspection_interval"
    for prop, pattern in (
        ("temperature", r"\btemperature\b|\btemp\b|\bthermal\b"),
        ("vibration", r"\bvibration\b"),
        ("pressure", r"\bpressure\b"),
        ("voltage", r"\bvoltage\b"),
        ("current", r"\bcurrent\b"),
        ("power", r"\bpower\b"),
        ("speed", r"\bspeed\b|\brpm\b"),
        ("frequency", r"\bfrequency\b"),
        ("capacity", r"\bcapacity\b"),
    ):
        if re.search(pattern, t):
            return prop
    return None


def _extract_value_with_unit(text: str, prop: str) -> Optional[float]:
    t = normalize_text(text)
    patterns = {
        "temperature": r"(-?\d+(?:\.\d+)?)\s*(?:degree\s*)?(?:celsius|c|fahrenheit|f)\b",
        "vibration": r"(\d[\d,]*(?:\.\d+)?)\s*mm\s*/\s*s\b",
        "pressure": r"(\d[\d,]*(?:\.\d+)?)\s*(?:kpa|pa|bar)\b",
        "voltage": r"(\d[\d,]*(?:\.\d+)?)\s*(?:kv|mv|v)\b",
        "current": r"(\d[\d,]*(?:\.\d+)?)\s*(?:ma|a)\b",
        "power": r"(\d[\d,]*(?:\.\d+)?)\s*(?:kw|w)\b",
        "speed": r"(\d[\d,]*(?:\.\d+)?)\s*rpm\b",
        "frequency": r"(\d[\d,]*(?:\.\d+)?)\s*(?:khz|mhz|hz)\b",
        "capacity": r"\bcapacity\D{0,25}(\d[\d,]*(?:\.\d+)?)",
    }
    return _number(patterns.get(prop, r"(?!)"), t)


def _extract_interval(text: str) -> Optional[float]:
    t = normalize_text(text)
    # Prefer values explicitly attached to hours; avoid unrelated section numbers.
    return _number(
        r"\b(?:every|each|per|after|at)\s+(\d[\d,]*(?:\.\d+)?)\s*(?:operating\s*)?hours?\b",
        t,
    ) or _number(r"\b(\d[\d,]*(?:\.\d+)?)\s*(?:operating\s*)?hours?\b", t)


def parse_claim_fact(claim: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    text = str(claim.get("text") or claim.get("claim_text") or "")
    if not text.strip():
        return None
    lower = normalize_text(text)
    prop = detect_property(text)
    if not prop:
        return None

    if prop == "inspection_interval":
        value = _extract_interval(text)
        if value is None:
            return None
        return {
            "property": prop,
            "role": "INTERVAL",
            "value": value,
            "document_id": claim.get("document_id"),
            "claim": claim,
        }

    value = _extract_value_with_unit(text, prop)
    if value is None:
        return None

    # Detect directional rules like "normal vibration below 4.5 mm/s RMS".
    direction_match = re.search(r"\b(above|below|exceed(?:s|ed)?)\b", lower)
    if direction_match and any(term in lower for term in ("normal", "threshold", "requires inspection", "require inspection")):
        direction = "above" if direction_match.group(1).startswith("exceed") else direction_match.group(1)
        return {
            "property": prop,
            "role": "THRESHOLD_RULE",
            "value": value,
            "direction": direction,
            "document_id": claim.get("document_id"),
            "claim": claim,
        }

    # Explicit maximum/minimum wording, plus generic "temperature limit: 95°C".
    if re.search(r"\b(max(?:imum)?|upper limit|maximum limit)\b", lower) or (
        re.search(r"\blimit\b", lower) and not re.search(r"\b(min(?:imum)?|lower limit)\b", lower)
    ):
        return {"property": prop, "role": "MAX_LIMIT", "value": value, "document_id": claim.get("document_id"), "claim": claim}
    if re.search(r"\b(min(?:imum)?|lower limit)\b", lower):
        return {"property": prop, "role": "MIN_LIMIT", "value": value, "document_id": claim.get("document_id"), "claim": claim}

    # An observed/measured reading is different from a stated limit.
    if re.search(r"\b(measured|measurement|reading|observed|recorded|actual)\b", lower) or "|" in text:
        return {"property": prop, "role": "OBSERVED", "value": value, "document_id": claim.get("document_id"), "claim": claim}

    # Treat a plain "normal vibration below X" as a directional threshold.
    if "normal" in lower and re.search(r"\b(below|under|less than)\b", lower):
        return {
            "property": prop,
            "role": "THRESHOLD_RULE",
            "value": value,
            "direction": "below",
            "document_id": claim.get("document_id"),
            "claim": claim,
        }
    return None


def detect_pair_issue(fact_a: Dict[str, Any], fact_b: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not fact_a or not fact_b or fact_a["property"] != fact_b["property"]:
        return None

    # Only compare across distinct known documents. If IDs are absent, use source/filename.
    a, b = fact_a.get("claim", {}), fact_b.get("claim", {})
    doc_a = fact_a.get("document_id") or a.get("source") or a.get("filename")
    doc_b = fact_b.get("document_id") or b.get("source") or b.get("filename")
    if doc_a and doc_b and doc_a == doc_b:
        return None

    ra, rb = fact_a["role"], fact_b["role"]
    va, vb = fact_a["value"], fact_b["value"]
    prop = fact_a["property"]

    # Different intervals may be recommendations/conditional guidance rather than direct contradictions.
    if ra == rb == "INTERVAL" and va != vb:
        text_a = normalize_text(a.get("text", a.get("claim_text", "")))
        text_b = normalize_text(b.get("text", b.get("claim_text", "")))

        recommendation_terms = ("recommend", "suggest", "advisory", "consider")
        conditional_terms = (
            "after heavy use", "under heavy use", "severe conditions",
            "harsh conditions", "if necessary", "as needed",
        )
        is_recommendation = any(term in text_a or term in text_b for term in recommendation_terms)
        is_conditional = any(term in text_a or term in text_b for term in conditional_terms)

        if is_recommendation or is_conditional:
            return {
                "is_conflict": False,
                "status": "DIFFERENCE_REQUIRING_REVIEW",
                "reason": (
                    f"Different maintenance intervals ({va:g} vs {vb:g} hours) "
                    "may reflect a recommendation or operating condition; human review is required."
                ),
                "property": [prop],
                "values_a": [str(va)],
                "values_b": [str(vb)],
            }

        return {
            "is_conflict": True,
            "status": "CONFLICT",
            "reason": f"Different documents specify different inspection/maintenance intervals ({va:g} vs {vb:g} hours).",
            "property": [prop],
            "values_a": [str(va)],
            "values_b": [str(vb)],
        }

    if ra == rb == "MAX_LIMIT" and va != vb:
        return {"is_conflict": True, "status": "CONFLICT", "reason": f"Different source documents specify different maximum limits for {prop} ({va:g} vs {vb:g}).", "property": [prop], "values_a": [str(va)], "values_b": [str(vb)]}
    if ra == rb == "MIN_LIMIT" and va != vb:
        return {"is_conflict": True, "status": "CONFLICT", "reason": f"Different source documents specify different minimum limits for {prop} ({va:g} vs {vb:g}).", "property": [prop], "values_a": [str(va)], "values_b": [str(vb)]}
    if ra == rb == "THRESHOLD_RULE" and (va != vb or fact_a.get("direction") != fact_b.get("direction")):
        return {"is_conflict": True, "status": "CONFLICT", "reason": f"Different source documents specify different {prop} thresholds.", "property": [prop], "values_a": [f"{fact_a.get('direction')} {va:g}"], "values_b": [f"{fact_b.get('direction')} {vb:g}"]}

    # Observed values that exceed explicit limits/thresholds are potential violations.
    observed, rule = (fact_a, fact_b) if ra == "OBSERVED" else ((fact_b, fact_a) if rb == "OBSERVED" else (None, None))
    if observed and rule:
        ov, rv = observed["value"], rule["value"]
        violation = (
            (rule["role"] == "MAX_LIMIT" and ov > rv)
            or (rule["role"] == "MIN_LIMIT" and ov < rv)
            or (rule["role"] == "THRESHOLD_RULE" and rule.get("direction") == "below" and ov > rv)
        )
        if violation:
            return {"is_conflict": True, "status": "POTENTIAL_VIOLATION", "reason": f"An observed {prop} value ({ov:g}) violates a documented limit/threshold ({rv:g}).", "property": [prop], "limit": rv, "observed_value": ov}
    return None


def detect_conflict(claim_a: Dict[str, Any], claim_b: Dict[str, Any]) -> Dict[str, Any]:
    fact_a, fact_b = parse_claim_fact(claim_a), parse_claim_fact(claim_b)
    if not fact_a or not fact_b:
        return {"is_conflict": False, "status": "NO_CONFLICT", "reason": "The claims do not contain comparable structured facts."}
    result = detect_pair_issue(fact_a, fact_b)
    return result or {"is_conflict": False, "status": "NO_CONFLICT", "reason": "No direct contradiction or limit violation was detected."}


def detect_conflicts(claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    conflicts: List[Dict[str, Any]] = []
    for i in range(len(claims)):
        for j in range(i + 1, len(claims)):
            claim_a, claim_b = claims[i], claims[j]
            if claim_a.get("id") is not None and claim_a.get("id") == claim_b.get("id"):
                continue
            result = detect_conflict(claim_a, claim_b)
            if not result.get("is_conflict"):
                continue
            conflicts.append({
                "id": f"{claim_a.get('id', i)}-{claim_b.get('id', j)}",
                "claim_a": claim_a,
                "claim_b": claim_b,
                "conflict": result,
                "reason": result.get("reason", "Conflicting information detected."),
            })
    return conflicts
