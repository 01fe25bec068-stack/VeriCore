import re
import uuid


# ============================================================
# ENTITY RESOLUTION
# ============================================================
# Purpose:
# Detect technical entity identifiers from uploaded documents
# and group different textual variants of the same entity.
#
# Examples:
#   MX-400        -> MX400
#   MX400         -> MX400
#   mx-400        -> MX400
#   MX400-MTR-07  -> MX400MTR07
#
# No demo entities are hardcoded.
# ============================================================


# ------------------------------------------------------------
# Common words that should never become entities
# ------------------------------------------------------------

ENTITY_STOPWORDS = {
    "LOG",
    "NOTE",
    "SYSTEM",
    "DEVICE",
    "MACHINE",
    "MODEL",
    "ASSET",
    "EQUIPMENT",
    "UNIT",
    "SENSOR",
    "COMPONENT",
    "SERIAL",
    "PART",
    "NUMBER",
    "ID",
    "DATA",
    "TEST",
    "STATUS",
    "NORMAL",
    "WARNING",
    "ALERT",
    "CONFIDENTIAL",
}


# ------------------------------------------------------------
# Explicit labels that introduce entity identifiers
#
# Examples:
#   Device: MX400-MTR-07
#   Model: MX-400
#   Asset ID: PUMP-204
#   Serial Number: SN-2048
# ------------------------------------------------------------

ENTITY_LABEL_PATTERN = re.compile(
    r"\b(?:"
    r"machine|machine\s+id|"
    r"model|"
    r"asset|asset\s+id|"
    r"device|device\s+id|"
    r"equipment|equipment\s+id|"
    r"unit|unit\s+id|"
    r"sensor|sensor\s+id|"
    r"system|system\s+id|"
    r"component|component\s+id|"
    r"serial|serial\s+number|"
    r"part|part\s+number"
    r")\b"
    r"\s*(?:id)?\s*[:=#-]?\s*"
    r"([A-Za-z]{1,12}(?:[-_/]?[A-Za-z0-9]){1,20})",
    re.IGNORECASE,
)


# ------------------------------------------------------------
# Generic technical identifiers
#
# Requires:
#   letters + separator/optional separator + digits
#
# Examples:
#   MX-400
#   MX400
#   PUMP-204
#   SN-2048
#   DEV_120
#
# This prevents ordinary words such as LOG and NOTE from
# becoming entities because they contain no numeric component.
# ------------------------------------------------------------

GENERIC_ENTITY_PATTERN = re.compile(
    r"\b[A-Za-z]{2,12}[-_/]?\d{2,10}\b"
)


def normalize_entity(value: str) -> str:
    """
    Normalize an entity identifier so different formatting
    styles resolve to the same canonical entity.

    Examples:
        MX-400       -> MX400
        mx_400       -> MX400
        MX/400       -> MX400
        MX400-MTR-07 -> MX400MTR07
    """

    value = value.strip().upper()

    # Remove spaces and separators.
    value = re.sub(r"[\s\-_\/]+", "", value)

    # Keep only letters and digits.
    value = re.sub(r"[^A-Z0-9]", "", value)

    return value


def is_valid_entity(value: str) -> bool:
    """
    Validate whether a candidate looks like a real technical
    identifier rather than an ordinary word.
    """

    if not value:
        return False

    normalized = normalize_entity(value)

    if not normalized:
        return False

    # Reject known ordinary words.
    if normalized in ENTITY_STOPWORDS:
        return False

    # A technical identifier must contain both letters and digits.
    has_letters = bool(re.search(r"[A-Z]", normalized))
    has_digits = bool(re.search(r"\d", normalized))

    if not (has_letters and has_digits):
        return False

    # Avoid extremely long accidental matches.
    if len(normalized) > 30:
        return False

    return True


def extract_entity_candidates(text: str):
    """
    Extract possible technical entity identifiers from a text block.
    """

    if not text:
        return []

    candidates = []

    # --------------------------------------------------------
    # 1. Entities introduced by explicit labels
    # --------------------------------------------------------

    for match in ENTITY_LABEL_PATTERN.finditer(text):
        value = match.group(1).strip()

        if is_valid_entity(value):
            candidates.append(value)

    # --------------------------------------------------------
    # 2. Generic technical identifiers
    # --------------------------------------------------------

    for match in GENERIC_ENTITY_PATTERN.finditer(text):
        value = match.group(0).strip()

        if is_valid_entity(value):
            candidates.append(value)

    # --------------------------------------------------------
    # Preserve order while removing duplicates.
    # --------------------------------------------------------

    unique = []
    seen = set()

    for candidate in candidates:

        normalized = normalize_entity(candidate)

        if not normalized:
            continue

        if normalized in seen:
            continue

        seen.add(normalized)
        unique.append(candidate)

    return unique


def resolve_entities(documents: dict):
    """
    Resolve entities across all uploaded documents.

    Parameters:
        documents:
            Dictionary of uploaded documents.

    Returns:
        List of resolved entity objects.
    """

    entity_groups = {}

    # ========================================================
    # Scan every document and every page
    # ========================================================

    for document_id, document in documents.items():

        filename = document.get("filename", "")

        for page in document.get("pages", []):

            page_number = page.get("page", 1)
            page_text = page.get("text", "")

            if not page_text.strip():
                continue

            candidates = extract_entity_candidates(page_text)

            # =================================================
            # Group candidates by canonical form
            # =================================================

            for candidate in candidates:

                canonical_name = normalize_entity(candidate)

                if not canonical_name:
                    continue

                if canonical_name not in entity_groups:

                    entity_groups[canonical_name] = {
                        "id": str(uuid.uuid4()),
                        "canonical_name": canonical_name,
                        "variants": set(),
                        "mentions": 0,
                        "sources": set(),
                        "references": []
                    }

                entity = entity_groups[canonical_name]

                entity["variants"].add(candidate.upper())
                entity["mentions"] += 1
                entity["sources"].add(filename)

                entity["references"].append({
                    "document_id": document_id,
                    "source": filename,
                    "page": page_number,
                    "text": page_text
                })

    # ========================================================
    # Convert internal sets into JSON-friendly lists
    # ========================================================

    resolved_entities = []

    for entity in entity_groups.values():

        resolved_entities.append({
            "id": entity["id"],
            "canonical_name": entity["canonical_name"],
            "variants": sorted(entity["variants"]),
            "mentions": entity["mentions"],
            "sources": sorted(entity["sources"]),
            "references": entity["references"]
        })

    # Stable ordering makes API results easier to inspect.
    resolved_entities.sort(
        key=lambda item: item["canonical_name"]
    )

    return resolved_entities