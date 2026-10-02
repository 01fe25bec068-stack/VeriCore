import re
import uuid


CLAIM_KEYWORDS = [
    "maximum",
    "minimum",
    "requires",
    "required",
    "must",
    "should",
    "operating",
    "temperature",
    "pressure",
    "voltage",
    "current",
    "power",
    "speed",
    "capacity",
    "frequency",
    "maintenance",
    "inspection",
    "inspect",
    "interval",
    "limit",
    "rating",
    "recommended",
    "normal",
    "warning",
    "critical",
    "record",
    "check",
    "stop",
    "isolate",
]


def normalize_claim(text: str):
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_into_sentences(text: str):
    """
    Split normal prose into sentences while keeping structured
    system-log records as separate statements.
    """

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = [line.strip() for line in text.split("\n") if line.strip()]

    parts = []
    current = ""

    for line in lines:

        # Timestamped system-log record
        if re.match(r"^\d{2}:\d{2}:\d{2}\s*\|", line):
            if current:
                parts.append(current)
                current = ""

            parts.append(line)
            continue

        # Normal continuation of the previous line
        if current:
            current += " " + line
        else:
            current = line

        # Complete normal sentence
        if re.search(r"[.!?]$", current):
            parts.append(current)
            current = ""

    if current:
        parts.append(current)

    return [
        normalize_claim(part)
        for part in parts
        if normalize_claim(part)
    ]

def is_heading_or_metadata(sentence: str):
    text = sentence.strip()

    if not text:
        return True

    # Document title / obvious metadata
    if "— Operating & Safety Manual" in text:
        return True

    if re.match(
        r"^(document id|revision|classification)\s*:",
        text,
        re.IGNORECASE
    ):
        return True

    # Numbered section headings such as:
    # 1. Operating Limits
    # 2. Recommended Maintenance
    # 3. Safety Guidance
    if re.match(
        r"^\d+\.\s+[A-Za-z][A-Za-z\s&/-]*$",
        text
    ):
        return True

    # Short heading-like phrases without factual content
    words = text.split()

    if len(words) <= 5 and not re.search(
        r"\d+(?:\.\d+)?\s*"
        r"(?:°c|°f|v|kv|mv|a|ma|w|kw|hz|khz|mhz|rpm|"
        r"bar|kpa|pa|hours?|hrs?|minutes?|mins?|seconds?|"
        r"days?|months?|years?|%|mm|cm|m|kg|g)\b",
        text.lower()
    ):
        if not re.search(
            r"\b(is|are|was|were|requires|required|must|should|"
            r"inspect|check|record|stop|isolate)\b",
            text.lower()
        ):
            return True

    return False


def looks_like_claim(sentence: str):
    if is_heading_or_metadata(sentence):
        return False

    lower = sentence.lower()

    has_number = bool(
        re.search(
            r"\b\d+(?:\.\d+)?\s*"
            r"(?:°c|°f|v|kv|mv|a|ma|w|kw|hz|khz|mhz|rpm|"
            r"bar|kpa|pa|hours?|hrs?|mins?|minutes?|seconds?|"
            r"days?|months?|years?|%|mm|cm|m|kg|g)\b",
            lower
        )
    )

    has_claim_keyword = any(
        keyword in lower
        for keyword in CLAIM_KEYWORDS
    )

    # A claim should normally contain either a measurable value
    # or an explicit operational/policy statement.
    return has_number or has_claim_keyword


def extract_claims_from_document(document: dict):
    extracted_claims = []

    document_id = document["id"]
    filename = document["filename"]

    for page in document.get("pages", []):
        page_number = page["page"]
        page_text = page.get("text", "")

        if not page_text.strip():
            continue

        sentences = split_into_sentences(page_text)

        for sentence in sentences:

            if not looks_like_claim(sentence):
                continue

            claim_text = normalize_claim(sentence)

            # Ignore extremely short fragments.
            if len(claim_text.split()) < 4:
                continue

            claim = {
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "source": filename,
                "page": page_number,
                "text": claim_text,
                "status": "UNVERIFIED",
                "evidence": {
                    "source": filename,
                    "page": page_number,
                    "text": claim_text
                }
            }

            extracted_claims.append(claim)

    return extracted_claims