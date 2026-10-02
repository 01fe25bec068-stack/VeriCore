import re
from difflib import SequenceMatcher


# ---------------------------------------------------------
# TEXT NORMALIZATION
# ---------------------------------------------------------

def normalize_text(text: str) -> str:
    """
    Normalize text for reliable comparison.
    """
    text = str(text or "").lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s°.-]", "", text)
    return text.strip()


# ---------------------------------------------------------
# NUMBER / UNIT EXTRACTION
# ---------------------------------------------------------

def extract_numbers(text: str):
    """
    Extract numeric values.

    Examples:
        80 C       -> [80.0]
        500 hours  -> [500.0]
        2.5 bar    -> [2.5]
    """
    numbers = re.findall(
        r"(?<!\w)\d+(?:\.\d+)?",
        normalize_text(text)
    )

    return [float(number) for number in numbers]


def extract_units(text: str):
    """
    Extract common engineering / measurement units.
    """

    pattern = (
        r"(?:"
        r"°c|celsius|"
        r"°f|fahrenheit|"
        r"hours?|hrs?|"
        r"minutes?|mins?|"
        r"seconds?|secs?|"
        r"days?|"
        r"kg|g|"
        r"v|volts?|"
        r"a|amps?|"
        r"mm|cm|m|"
        r"hz|khz|mhz|"
        r"rpm|"
        r"bar|psi|"
        r"kw|mw|"
        r"w|"
        r"percent|%"
        r")"
    )

    return re.findall(
        pattern,
        normalize_text(text)
    )


# ---------------------------------------------------------
# KEYWORD EXTRACTION
# ---------------------------------------------------------

STOP_WORDS = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "of",
    "to",
    "and",
    "or",
    "in",
    "on",
    "for",
    "with",
    "by",
    "from",
    "this",
    "that",
    "it",
    "as",
    "at",
    "if",
    "than",
    "then",
    "into",
    "during",
    "after",
    "before",
    "must",
    "should",
    "shall",
    "may",
    "can",
    "will",
    "requires",
    "required",
    "every",
    "above",
    "below",
    "maximum",
    "minimum"
}


def extract_keywords(text: str):
    """
    Extract meaningful words while ignoring common grammar words.
    """

    words = re.findall(
        r"[a-zA-Z][a-zA-Z0-9-]*",
        normalize_text(text)
    )

    return {
        word
        for word in words
        if word not in STOP_WORDS and len(word) > 2
    }


# ---------------------------------------------------------
# SUBJECT / PROPERTY DETECTION
# ---------------------------------------------------------

def extract_subject(text: str):
    """
    Try to identify the main subject of a claim.

    Examples:
        MX-400 Industrial Motor
        Machine 204
        battery
        bearing
    """

    text_normalized = normalize_text(text)

    # Common equipment/entity identifiers
    entity_patterns = [
        r"\bmx[- ]?\d+\b",
        r"\bmachine[- ]?\d+\b",
        r"\bunit[- ]?\d+\b",
        r"\bmodel[- ]?[a-z0-9-]+\b"
    ]

    for pattern in entity_patterns:
        match = re.search(pattern, text_normalized)

        if match:
            return match.group(0).replace(" ", "")

    # Otherwise use the first meaningful noun-like keywords
    keywords = extract_keywords(text_normalized)

    return " ".join(sorted(keywords)[:4])


def extract_property(text: str):
    """
    Identify the property/fact being discussed.

    This is the important part that prevents unrelated
    numerical claims from being classified as conflicts.
    """

    text_normalized = normalize_text(text)

    property_patterns = [
        # Temperature
        (
            r"(maximum|minimum|max|min)?\s*"
            r"(operating\s+)?temperature"
        ),

        # Maintenance
        (
            r"(maintenance|inspection|service)"
            r"(\s+interval|\s+period|\s+frequency)?"
        ),

        # Speed
        r"(maximum|minimum|max|min)?\s*(operating\s+)?speed",

        # Pressure
        r"(maximum|minimum|max|min)?\s*(operating\s+)?pressure",

        # Voltage
        r"(maximum|minimum|max|min)?\s*(operating\s+)?voltage",

        # Current
        r"(maximum|minimum|max|min)?\s*(operating\s+)?current",

        # Power
        r"(maximum|minimum|max|min)?\s*(rated\s+)?power",

        # Capacity
        r"(maximum|minimum|max|min)?\s*capacity",

        # Weight
        r"(maximum|minimum|max|min)?\s*weight",

        # Flow
        r"(maximum|minimum|max|min)?\s*flow",

        # Humidity
        r"(maximum|minimum|max|min)?\s*humidity",

        # Lifetime
        r"(service\s+life|lifetime|life\s+expectancy)",

        # Frequency
        r"(operating\s+)?frequency",

        # General limit
        r"(maximum|minimum|max|min)\s+limit"
    ]

    for pattern in property_patterns:
        match = re.search(pattern, text_normalized)

        if match:
            return re.sub(
                r"\s+",
                " ",
                match.group(0)
            ).strip()

    return None


# ---------------------------------------------------------
# FACT SIGNATURE
# ---------------------------------------------------------

def build_fact_signature(text: str):
    """
    Build a simplified representation of what the claim
    is actually talking about.

    Example:

        "MX-400 maximum operating temperature is 80 C"

    becomes approximately:

        subject: mx-400
        property: maximum operating temperature
    """

    return {
        "subject": extract_subject(text),
        "property": extract_property(text)
    }


# ---------------------------------------------------------
# SIMILARITY
# ---------------------------------------------------------

def calculate_similarity(text_a: str, text_b: str) -> float:
    """
    Calculate textual similarity between two claims.
    """

    return SequenceMatcher(
        None,
        normalize_text(text_a),
        normalize_text(text_b)
    ).ratio()


def calculate_keyword_overlap(text_a: str, text_b: str) -> float:
    """
    Calculate meaningful keyword overlap.
    """

    words_a = extract_keywords(text_a)
    words_b = extract_keywords(text_b)

    if not words_a or not words_b:
        return 0.0

    intersection = words_a.intersection(words_b)
    union = words_a.union(words_b)

    return len(intersection) / len(union)


# ---------------------------------------------------------
# SAME FACT CHECK
# ---------------------------------------------------------

def same_fact(claim_a: dict, claim_b: dict):
    """
    Decide whether two claims describe the same factual property.

    A conflict should only be considered when the claims are
    sufficiently related.
    """

    text_a = claim_a.get("text", "")
    text_b = claim_b.get("text", "")

    fact_a = build_fact_signature(text_a)
    fact_b = build_fact_signature(text_b)

    subject_a = fact_a["subject"]
    subject_b = fact_b["subject"]

    property_a = fact_a["property"]
    property_b = fact_b["property"]

    # -----------------------------------------------------
    # Strong property match
    # -----------------------------------------------------

    if property_a and property_b:

        property_similarity = SequenceMatcher(
            None,
            property_a,
            property_b
        ).ratio()

        if property_similarity >= 0.70:

            # If both subjects are known, require them to match.
            if subject_a and subject_b:

                subject_similarity = SequenceMatcher(
                    None,
                    subject_a,
                    subject_b
                ).ratio()

                if subject_similarity >= 0.70:
                    return True, fact_a, fact_b

                return False, fact_a, fact_b

            return True, fact_a, fact_b

    # -----------------------------------------------------
    # Fallback: meaningful keyword overlap
    # -----------------------------------------------------

    keyword_overlap = calculate_keyword_overlap(
        text_a,
        text_b
    )

    if keyword_overlap >= 0.55:
        return True, fact_a, fact_b

    return False, fact_a, fact_b


# ---------------------------------------------------------
# MAIN CLAIM COMPARISON
# ---------------------------------------------------------

def compare_claims(claim_a: dict, claim_b: dict):
    """
    Compare two claims.

    Possible results:

        AGREEMENT
        CONFLICT
        DIFFERENT
        INSUFFICIENT_EVIDENCE
    """

    text_a = normalize_text(claim_a.get("text", ""))
    text_b = normalize_text(claim_b.get("text", ""))

    if not text_a or not text_b:
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "reason": "One or both claims contain no usable text."
        }

    # -----------------------------------------------------
    # Exact match
    # -----------------------------------------------------

    if text_a == text_b:
        return {
            "status": "AGREEMENT",
            "reason": "The claims contain identical text.",
            "similarity": 1.0
        }

    # -----------------------------------------------------
    # Determine whether they describe the same fact
    # -----------------------------------------------------

    related, fact_a, fact_b = same_fact(
        claim_a,
        claim_b
    )

    numbers_a = extract_numbers(text_a)
    numbers_b = extract_numbers(text_b)

    units_a = extract_units(text_a)
    units_b = extract_units(text_b)

    similarity = calculate_similarity(
        text_a,
        text_b
    )

    keyword_overlap = calculate_keyword_overlap(
        text_a,
        text_b
    )

    # -----------------------------------------------------
    # DIFFERENT FACTS
    # -----------------------------------------------------

    if not related:

        return {
            "status": "DIFFERENT",
            "reason": (
                "The claims do not describe the same factual "
                "property, so they are not treated as a conflict."
            ),
            "similarity": round(similarity, 3),
            "keyword_overlap": round(keyword_overlap, 3),
            "fact_a": fact_a,
            "fact_b": fact_b
        }

    # -----------------------------------------------------
    # Same fact + same numerical values
    # -----------------------------------------------------

    if numbers_a and numbers_b:

        if numbers_a == numbers_b:

            return {
                "status": "AGREEMENT",
                "reason": (
                    "The claims describe the same fact and "
                    "contain the same numerical value."
                ),
                "values": {
                    "claim_a": numbers_a,
                    "claim_b": numbers_b
                },
                "units": {
                    "claim_a": units_a,
                    "claim_b": units_b
                },
                "fact_a": fact_a,
                "fact_b": fact_b,
                "similarity": round(similarity, 3)
            }

        # -------------------------------------------------
        # Same fact + different values = CONFLICT
        # -------------------------------------------------

        return {
            "status": "CONFLICT",
            "reason": (
                "The claims describe the same factual property "
                "but contain different numerical values."
            ),
            "values": {
                "claim_a": numbers_a,
                "claim_b": numbers_b
            },
            "units": {
                "claim_a": units_a,
                "claim_b": units_b
            },
            "fact_a": fact_a,
            "fact_b": fact_b,
            "similarity": round(similarity, 3)
        }

    # -----------------------------------------------------
    # Same fact + highly similar text
    # -----------------------------------------------------

    if similarity >= 0.75 or keyword_overlap >= 0.65:

        return {
            "status": "AGREEMENT",
            "reason": (
                "The claims describe the same fact and "
                "are highly similar."
            ),
            "similarity": round(similarity, 3),
            "keyword_overlap": round(keyword_overlap, 3),
            "fact_a": fact_a,
            "fact_b": fact_b
        }

    # -----------------------------------------------------
    # Same topic but not enough evidence
    # -----------------------------------------------------

    return {
        "status": "INSUFFICIENT_EVIDENCE",
        "reason": (
            "The claims appear related, but there is not "
            "enough evidence to classify them as agreement "
            "or conflict."
        ),
        "similarity": round(similarity, 3),
        "keyword_overlap": round(keyword_overlap, 3),
        "fact_a": fact_a,
        "fact_b": fact_b
    }


# ---------------------------------------------------------
# COMPARE CLAIM SET
# ---------------------------------------------------------

def compare_claim_set(claims: list):
    """
    Compare claims against one another.

    Claims from the same exact claim ID are skipped.
    """

    comparisons = []

    for i in range(len(claims)):

        for j in range(i + 1, len(claims)):

            claim_a = claims[i]
            claim_b = claims[j]

            if claim_a.get("id") == claim_b.get("id"):
                continue

            result = compare_claims(
                claim_a,
                claim_b
            )

            comparisons.append({

                "claim_a": {
                    "id": claim_a.get("id"),
                    "document_id": claim_a.get("document_id"),
                    "source": claim_a.get("source"),
                    "page": claim_a.get("page"),
                    "text": claim_a.get("text")
                },

                "claim_b": {
                    "id": claim_b.get("id"),
                    "document_id": claim_b.get("document_id"),
                    "source": claim_b.get("source"),
                    "page": claim_b.get("page"),
                    "text": claim_b.get("text")
                },

                "comparison": result
            })

    return comparisons