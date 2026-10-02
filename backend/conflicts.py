import re


# ============================================================
# TEXT HELPERS
# ============================================================

def normalize_text(text: str):
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def extract_numbers(text: str):
    return re.findall(r"\d+(?:\.\d+)?", text or "")


def detect_property(text: str):
    lower = normalize_text(text)

    if "temperature" in lower or re.search(r"\btemp\b", lower):
        return "temperature"

    if "vibration" in lower:
        return "vibration"

    if "pressure" in lower:
        return "pressure"

    if "voltage" in lower:
        return "voltage"

    if re.search(r"\bcurrent\b", lower):
        return "current"

    if "power" in lower:
        return "power"

    if "speed" in lower:
        return "speed"

    if "frequency" in lower:
        return "frequency"

    if "capacity" in lower:
        return "capacity"

    return None


# ============================================================
# CLAIM FACT EXTRACTION
# ============================================================

def parse_claim_fact(claim: dict):
    text = claim.get("text", "")
    lower = normalize_text(text)

    property_name = detect_property(text)

    if not property_name:
        return None

    numbers = [float(value) for value in extract_numbers(text)]

    # --------------------------------------------------------
    # Structured system-log observation
    # Example:
    # TEMP=84°C
    # VIBRATION=4.8 mm/s
    # --------------------------------------------------------

    if "|" in text and (
        "TEMP=" in text.upper()
        or "VIBRATION=" in text.upper()
        or "PRESSURE=" in text.upper()
    ):
        if property_name == "temperature":
            match = re.search(
                r"TEMP\s*=\s*(\d+(?:\.\d+)?)",
                text,
                re.IGNORECASE
            )
        elif property_name == "vibration":
            match = re.search(
                r"VIBRATION\s*=\s*(\d+(?:\.\d+)?)",
                text,
                re.IGNORECASE
            )
        else:
            match = None

        if match:
            return {
                "property": property_name,
                "role": "OBSERVED",
                "value": float(match.group(1)),
                "document_id": claim.get("document_id"),
                "claim": claim
            }

    # --------------------------------------------------------
    # Normal operating range
    # Example:
    # Normal motor operating temperature: 20°C to 75°C.
    # --------------------------------------------------------

    if "normal" in lower and len(numbers) >= 2:
        return {
            "property": property_name,
            "role": "NORMAL_RANGE",
            "minimum": numbers[0],
            "maximum": numbers[1],
            "document_id": claim.get("document_id"),
            "claim": claim
        }

    # --------------------------------------------------------
    # Maximum limit
    # Example:
    # Maximum continuous operating temperature: 80°C.
    # --------------------------------------------------------

    if (
        "maximum" in lower
        or re.search(r"\bmax(?:imum)?\b", lower)
    ) and numbers:
        return {
            "property": property_name,
            "role": "MAX_LIMIT",
            "value": numbers[-1],
            "document_id": claim.get("document_id"),
            "claim": claim
        }

    # --------------------------------------------------------
    # Minimum limit
    # --------------------------------------------------------

    if (
        "minimum" in lower
        or re.search(r"\bmin(?:imum)?\b", lower)
    ) and numbers:
        return {
            "property": property_name,
            "role": "MIN_LIMIT",
            "value": numbers[-1],
            "document_id": claim.get("document_id"),
            "claim": claim
        }

    # --------------------------------------------------------
    # Threshold / rule
    # Example:
    # Temperature above 80°C requires inspection.
    # --------------------------------------------------------

    if (
        "above" in lower
        or "below" in lower
        or "exceed" in lower
        or "exceeded" in lower
    ) and numbers:
        return {
            "property": property_name,
            "role": "THRESHOLD_RULE",
            "value": numbers[-1],
            "document_id": claim.get("document_id"),
            "claim": claim
        }

    return None


# ============================================================
# PAIRWISE COMPARISON
# ============================================================

def detect_pair_issue(fact_a: dict, fact_b: dict):
    if not fact_a or not fact_b:
        return None

    if fact_a["property"] != fact_b["property"]:
        return None

    # Only cross-document comparisons belong in
    # multi-source conflict detection.
    if fact_a.get("document_id") == fact_b.get("document_id"):
        return None

    # --------------------------------------------------------
    # OBSERVED value vs MAX limit
    # --------------------------------------------------------

    if fact_a["role"] == "OBSERVED" and fact_b["role"] == "MAX_LIMIT":
        if fact_a["value"] > fact_b["value"]:
            return {
                "is_conflict": True,
                "status": "POTENTIAL_VIOLATION",
                "reason": (
                    "An observed value exceeds the maximum "
                    "documented limit."
                ),
                "property": [fact_a["property"]],
                "limit": fact_b["value"],
                "observed_value": fact_a["value"]
            }

    if fact_b["role"] == "OBSERVED" and fact_a["role"] == "MAX_LIMIT":
        if fact_b["value"] > fact_a["value"]:
            return {
                "is_conflict": True,
                "status": "POTENTIAL_VIOLATION",
                "reason": (
                    "An observed value exceeds the maximum "
                    "documented limit."
                ),
                "property": [fact_a["property"]],
                "limit": fact_a["value"],
                "observed_value": fact_b["value"]
            }

    # --------------------------------------------------------
    # OBSERVED value vs MIN limit
    # --------------------------------------------------------

    if fact_a["role"] == "OBSERVED" and fact_b["role"] == "MIN_LIMIT":
        if fact_a["value"] < fact_b["value"]:
            return {
                "is_conflict": True,
                "status": "POTENTIAL_VIOLATION",
                "reason": (
                    "An observed value falls below the minimum "
                    "documented limit."
                ),
                "property": [fact_a["property"]],
                "limit": fact_b["value"],
                "observed_value": fact_a["value"]
            }

    if fact_b["role"] == "OBSERVED" and fact_a["role"] == "MIN_LIMIT":
        if fact_b["value"] < fact_a["value"]:
            return {
                "is_conflict": True,
                "status": "POTENTIAL_VIOLATION",
                "reason": (
                    "An observed value falls below the minimum "
                    "documented limit."
                ),
                "property": [fact_a["property"]],
                "limit": fact_a["value"],
                "observed_value": fact_b["value"]
            }

    # --------------------------------------------------------
    # MAX LIMIT vs MAX LIMIT
    # Actual contradiction only when two sources specify
    # different maximum limits.
    # --------------------------------------------------------

    if (
        fact_a["role"] == "MAX_LIMIT"
        and fact_b["role"] == "MAX_LIMIT"
    ):
        if fact_a["value"] != fact_b["value"]:
            return {
                "is_conflict": True,
                "status": "CONFLICT",
                "reason": (
                    "Different source documents specify "
                    "different maximum limits for the same property."
                ),
                "property": [fact_a["property"]],
                "values_a": [str(fact_a["value"])],
                "values_b": [str(fact_b["value"])]
            }

    # --------------------------------------------------------
    # MIN LIMIT vs MIN LIMIT
    # --------------------------------------------------------

    if (
        fact_a["role"] == "MIN_LIMIT"
        and fact_b["role"] == "MIN_LIMIT"
    ):
        if fact_a["value"] != fact_b["value"]:
            return {
                "is_conflict": True,
                "status": "CONFLICT",
                "reason": (
                    "Different source documents specify "
                    "different minimum limits for the same property."
                ),
                "property": [fact_a["property"]],
                "values_a": [str(fact_a["value"])],
                "values_b": [str(fact_b["value"])]
            }

    return None


# ============================================================
# MAIN CONFLICT DETECTION
# ============================================================

def detect_conflict(claim_a: dict, claim_b: dict):
    fact_a = parse_claim_fact(claim_a)
    fact_b = parse_claim_fact(claim_b)

    if not fact_a or not fact_b:
        return {
            "is_conflict": False,
            "status": "NO_CONFLICT",
            "reason": "The claims do not contain comparable structured facts."
        }

    result = detect_pair_issue(fact_a, fact_b)

    if result:
        return result

    return {
        "is_conflict": False,
        "status": "NO_CONFLICT",
        "reason": "No direct contradiction or limit violation was detected."
    }


def detect_conflicts(claims: list):
    conflicts = []

    for i in range(len(claims)):
        for j in range(i + 1, len(claims)):

            claim_a = claims[i]
            claim_b = claims[j]

            if claim_a.get("id") == claim_b.get("id"):
                continue

            result = detect_conflict(claim_a, claim_b)

            if not result.get("is_conflict"):
                continue

            conflicts.append({
                "id": (
                    f"{claim_a.get('id')}-"
                    f"{claim_b.get('id')}"
                ),
                "claim_a": claim_a,
                "claim_b": claim_b,
                "conflict": result,
                "reason": result.get(
                    "reason",
                    "Conflicting information detected."
                )
            })

    return conflicts