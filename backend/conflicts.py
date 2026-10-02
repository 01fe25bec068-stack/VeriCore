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


def extract_property_value(text: str, property_name: str):
    """
    Extract the numeric value associated with the detected property.

    This avoids accidentally using section numbers such as:
        "3. Safety Guidance ..."

    as if they were engineering limits.
    """

    if not text or not property_name:
        return None

    patterns = {
        "temperature": [
            r"(?:temperature|temp)\s*(?:[:=]\s*)?"
            r"(?:measured|reading(?:\s+was)?|is|at)?\s*"
            r"(\d+(?:\.\d+)?)\s*°?\s*[CF]",
            r"(?:temperature|temp)[^0-9]{0,40}"
            r"(\d+(?:\.\d+)?)\s*°?\s*C",
        ],
        "vibration": [
            r"vibration[^0-9]{0,40}"
            r"(\d+(?:\.\d+)?)\s*mm/s",
        ],
        "pressure": [
            r"pressure[^0-9]{0,40}"
            r"(\d+(?:\.\d+)?)\s*(?:bar|kpa|pa)",
        ],
        "voltage": [
            r"voltage[^0-9]{0,40}"
            r"(\d+(?:\.\d+)?)\s*(?:v|kv|mv)",
        ],
        "current": [
            r"current[^0-9]{0,40}"
            r"(\d+(?:\.\d+)?)\s*(?:a|ma)",
        ],
        "power": [
            r"power[^0-9]{0,40}"
            r"(\d+(?:\.\d+)?)\s*(?:w|kw)",
        ],
        "speed": [
            r"speed[^0-9]{0,40}"
            r"(\d+(?:\.\d+)?)\s*rpm",
        ],
        "frequency": [
            r"frequency[^0-9]{0,40}"
            r"(\d+(?:\.\d+)?)\s*(?:hz|khz|mhz)",
        ],
        "capacity": [
            r"capacity[^0-9]{0,40}"
            r"(\d+(?:\.\d+)?)",
        ],
    }

    for pattern in patterns.get(property_name, []):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1))

    return None


def extract_range_values(text: str, property_name: str):
    """
    Extract a normal operating range without using unrelated
    document section numbers.
    """

    if not text or not property_name:
        return None

    unit_pattern = {
        "temperature": r"°?\s*C",
        "vibration": r"mm/s",
        "pressure": r"(?:bar|kpa|pa)",
        "voltage": r"(?:v|kv|mv)",
        "current": r"(?:a|ma)",
        "power": r"(?:w|kw)",
        "speed": r"rpm",
        "frequency": r"(?:hz|khz|mhz)",
        "capacity": r"",
    }.get(property_name, "")

    if unit_pattern:
        pattern = (
            rf"(?:{property_name}|temp)"
            rf"[^0-9]{{0,60}}"
            rf"(\d+(?:\.\d+)?)\s*{unit_pattern}"
            rf"\s*(?:to|-)\s*"
            rf"(\d+(?:\.\d+)?)\s*{unit_pattern}"
        )

        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            return float(match.group(1)), float(match.group(2))

    return None


def extract_limit_value(text: str, property_name: str, limit_word: str):
    """
    Extract a maximum/minimum value tied to the property.

    Example:
        Maximum continuous operating temperature: 80°C.
    """

    if not text or not property_name:
        return None

    property_words = {
        "temperature": r"(?:temperature|temp)",
        "vibration": r"vibration",
        "pressure": r"pressure",
        "voltage": r"voltage",
        "current": r"current",
        "power": r"power",
        "speed": r"speed",
        "frequency": r"frequency",
        "capacity": r"capacity",
    }

    property_pattern = property_words.get(
        property_name,
        re.escape(property_name)
    )

    # Property-specific limit phrase.
    pattern = (
        rf"\b{limit_word}\b"
        rf"(?:\s+\w+){{0,8}}"
        rf"\s+{property_pattern}"
        rf"[^0-9]{{0,50}}"
        rf"(\d+(?:\.\d+)?)"
    )

    match = re.search(pattern, text, re.IGNORECASE)

    if match:
        return float(match.group(1))

    # Alternate wording:
    # maximum of 80°C for temperature
    pattern = (
        rf"\b{limit_word}\b"
        rf"[^0-9]{{0,40}}"
        rf"(\d+(?:\.\d+)?)"
        rf"\s*°?\s*C"
        if property_name == "temperature"
        else
        rf"\b{limit_word}\b"
        rf"[^0-9]{{0,40}}"
        rf"(\d+(?:\.\d+)?)"
    )

    match = re.search(pattern, text, re.IGNORECASE)

    if match:
        return float(match.group(1))

    return None


def extract_threshold_value(text: str, property_name: str):
    """
    Extract a threshold only when the threshold's numeric value is
    explicitly tied to the property.
    """

    if not text or not property_name:
        return None

    property_words = {
        "temperature": r"(?:temperature|temp)",
        "vibration": r"vibration",
        "pressure": r"pressure",
        "voltage": r"voltage",
        "current": r"current",
        "power": r"power",
        "speed": r"speed",
        "frequency": r"frequency",
        "capacity": r"capacity",
    }

    property_pattern = property_words.get(
        property_name,
        re.escape(property_name)
    )

    pattern = (
        rf"{property_pattern}"
        rf"[^0-9]{{0,20}}"
        rf"(?:above|below|exceed(?:s|ed)?)"
        rf"[^0-9]{{0,20}}"
        rf"(\d+(?:\.\d+)?)"
    )

    match = re.search(pattern, text, re.IGNORECASE)

    if match:
        return float(match.group(1))

    pattern = (
        rf"(?:above|below|exceed(?:s|ed)?)"
        rf"[^0-9]{{0,20}}"
        rf"(\d+(?:\.\d+)?)"
        rf"[^A-Za-z0-9]{{0,20}}"
        rf"{property_pattern}"
    )

    match = re.search(pattern, text, re.IGNORECASE)

    if match:
        return float(match.group(1))

    return None


def extract_threshold_rule(text: str, property_name: str):
    """
    Extract an explicit directional threshold rule.

    Returns:
        {"value": <number>, "direction": "above"|"below"} or None

    Examples:
        "Temperature above 80°C requires inspection." -> above, 80
        "Normal vibration below 4.5 mm/s RMS." -> below, 4.5
    """

    if not text or not property_name:
        return None

    property_words = {
        "temperature": r"(?:temperature|temp)",
        "vibration": r"vibration",
        "pressure": r"pressure",
        "voltage": r"voltage",
        "current": r"current",
        "power": r"power",
        "speed": r"speed",
        "frequency": r"frequency",
        "capacity": r"capacity",
    }

    property_pattern = property_words.get(
        property_name,
        re.escape(property_name)
    )

    # Property first:
    # "vibration below 4.5 mm/s"
    for direction in ("above", "below"):
        pattern = (
            rf"{property_pattern}"
            rf"[^0-9]{{0,20}}"
            rf"{direction}"
            rf"[^0-9]{{0,20}}"
            rf"(\d+(?:\.\d+)?)"
        )

        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            return {
                "value": float(match.group(1)),
                "direction": direction,
            }

    # Direction first:
    # "above 80°C temperature ..."
    for direction in ("above", "below"):
        pattern = (
            rf"{direction}"
            rf"[^0-9]{{0,20}}"
            rf"(\d+(?:\.\d+)?)"
            rf"[^A-Za-z0-9]{{0,20}}"
            rf"{property_pattern}"
        )

        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            return {
                "value": float(match.group(1)),
                "direction": direction,
            }

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

    # --------------------------------------------------------
    # 1. Structured system-log observation
    # --------------------------------------------------------

    if "|" in text:

        value = extract_property_value(
            text,
            property_name
        )

        if value is not None:

            return {
                "property": property_name,
                "role": "OBSERVED",
                "value": value,
                "document_id": claim.get("document_id"),
                "claim": claim
            }

    # --------------------------------------------------------
    # 2. Normal operating range
    # --------------------------------------------------------

    if "normal" in lower:

        value_range = extract_range_values(
            text,
            property_name
        )

        if value_range:

            return {
                "property": property_name,
                "role": "NORMAL_RANGE",
                "minimum": value_range[0],
                "maximum": value_range[1],
                "document_id": claim.get("document_id"),
                "claim": claim
            }

    # --------------------------------------------------------
    # 3. Maximum limit
    # --------------------------------------------------------

    if (
        "maximum" in lower
        or "max continuous" in lower
        or re.search(r"\bmax\b", lower)
    ):

        value = extract_limit_value(
            text,
            property_name,
            "maximum"
        )

        if value is not None:

            return {
                "property": property_name,
                "role": "MAX_LIMIT",
                "value": value,
                "document_id": claim.get("document_id"),
                "claim": claim
            }

    # --------------------------------------------------------
    # 4. Minimum limit
    # --------------------------------------------------------

    if (
        "minimum" in lower
        or re.search(r"\bmin(?:imum)?\b", lower)
    ):

        value = extract_limit_value(
            text,
            property_name,
            "minimum"
        )

        if value is not None:

            return {
                "property": property_name,
                "role": "MIN_LIMIT",
                "value": value,
                "document_id": claim.get("document_id"),
                "claim": claim
            }

    # --------------------------------------------------------
    # 5. General observed measurement
    # --------------------------------------------------------

    observed_value = extract_property_value(
        text,
        property_name
    )

    if (
        observed_value is not None
        and any(
            word in lower
            for word in [
                "measured",
                "reading",
                "observed",
                "recorded",
                "value",
            ]
        )
    ):

        return {
            "property": property_name,
            "role": "OBSERVED",
            "value": observed_value,
            "document_id": claim.get("document_id"),
            "claim": claim
        }

    # --------------------------------------------------------
    # 6. Explicit threshold / rule
    # --------------------------------------------------------

    if (
        "above" in lower
        or "below" in lower
        or "exceed" in lower
        or "exceeded" in lower
    ):

        threshold = extract_threshold_rule(
            text,
            property_name
        )

        if threshold is not None:

            return {
                "property": property_name,
                "role": "THRESHOLD_RULE",
                "value": threshold["value"],
                "direction": threshold["direction"],
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

    if (
        fact_a["role"] == "OBSERVED"
        and fact_b["role"] == "MAX_LIMIT"
        and fact_a["value"] > fact_b["value"]
    ):

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

    if (
        fact_b["role"] == "OBSERVED"
        and fact_a["role"] == "MAX_LIMIT"
        and fact_b["value"] > fact_a["value"]
    ):

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

    if (
        fact_a["role"] == "OBSERVED"
        and fact_b["role"] == "MIN_LIMIT"
        and fact_a["value"] < fact_b["value"]
    ):

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

    if (
        fact_b["role"] == "OBSERVED"
        and fact_a["role"] == "MIN_LIMIT"
        and fact_b["value"] < fact_a["value"]
    ):

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
    # OBSERVED value vs directional threshold rule
    # --------------------------------------------------------
    #
    # A "below X" rule acts as an upper threshold:
    #   observed > X => violation
    #
    # An "above X" rule is treated as a trigger/inspection
    # condition rather than a minimum operating requirement.
    #
    # Therefore:
    #   "Temperature above 80°C requires inspection"
    #
    # does NOT make 74°C or 78°C a violation.
    #
    # But:
    #   "Normal vibration below 4.5 mm/s"
    #
    # DOES make 5.1 mm/s a violation.

    if (
        fact_a["role"] == "OBSERVED"
        and fact_b["role"] == "THRESHOLD_RULE"
    ):

        direction = fact_b.get("direction")

        if (
            direction == "below"
            and fact_a["value"] > fact_b["value"]
        ):

            return {
                "is_conflict": True,
                "status": "POTENTIAL_VIOLATION",
                "reason": (
                    "An observed value exceeds the documented "
                    "threshold."
                ),
                "property": [fact_a["property"]],
                "limit": fact_b["value"],
                "observed_value": fact_a["value"]
            }

    if (
        fact_b["role"] == "OBSERVED"
        and fact_a["role"] == "THRESHOLD_RULE"
    ):

        direction = fact_a.get("direction")

        if (
            direction == "below"
            and fact_b["value"] > fact_a["value"]
        ):

            return {
                "is_conflict": True,
                "status": "POTENTIAL_VIOLATION",
                "reason": (
                    "An observed value exceeds the documented "
                    "threshold."
                ),
                "property": [fact_a["property"]],
                "limit": fact_a["value"],
                "observed_value": fact_b["value"]
            }

    # --------------------------------------------------------
    # MAX LIMIT vs MAX LIMIT
    # --------------------------------------------------------

    if (
        fact_a["role"] == "MAX_LIMIT"
        and fact_b["role"] == "MAX_LIMIT"
        and fact_a["value"] != fact_b["value"]
    ):

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
        and fact_a["value"] != fact_b["value"]
    ):

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
            "reason": (
                "The claims do not contain comparable "
                "structured facts."
            )
        }

    result = detect_pair_issue(
        fact_a,
        fact_b
    )

    if result:
        return result

    return {
        "is_conflict": False,
        "status": "NO_CONFLICT",
        "reason": (
            "No direct contradiction or limit violation "
            "was detected."
        )
    }


def detect_conflicts(claims: list):

    conflicts = []

    for i in range(len(claims)):

        for j in range(i + 1, len(claims)):

            claim_a = claims[i]
            claim_b = claims[j]

            if claim_a.get("id") == claim_b.get("id"):
                continue

            result = detect_conflict(
                claim_a,
                claim_b
            )

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