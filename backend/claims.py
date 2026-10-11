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
    Split PDF/OCR text into statements while preserving
    separate lines and normal sentence boundaries.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    parts = []

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Keep timestamped system-log records separate.
        if re.match(r"^\d{2}:\d{2}:\d{2}\s\|", line):
            parts.append(line)
            continue

        # Split a line at sentence-ending punctuation when
        # followed by whitespace and another sentence.
        sentences = re.split(r"(?<=[.!?])\s+", line)

        for sentence in sentences:
            sentence = normalize_claim(sentence.strip())
            if sentence:
                parts.append(sentence)

    return parts



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

    lower = text.lower()

    # Keep factual specification statements even when OCR
    # misreads a numeric value or unit.
    factual_keywords = (
        "temperature", "vibration", "pressure", "voltage",
        "current", "power", "speed", "capacity", "frequency",
        "maintenance", "inspection", "inspect", "interval",
        "limit", "rating", "requires", "required", "must",
        "should", "recommended", "warning", "critical",
        "record", "check", "stop", "isolate"
    )

    if any(keyword in lower for keyword in factual_keywords):
        return False

    # Short phrases without factual content are likely headings.
    words = text.split()

    if len(words) <= 5:
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

        # OCR may return multiple statements on one line.
        # Split on newlines first, then use the existing
        # sentence splitter on each line.
        lines = [
            line.strip()
            for line in page_text.splitlines()
            if line.strip()
        ]

        sentences = []
        for line in lines:
            sentences.extend(split_into_sentences(line))

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
