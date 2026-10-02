# ============================================================
# VERIFICATION
# ============================================================
# Purpose:
# Determine whether a claim is verified, conflicting, partially
# supported, or unresolved using:
#
#   1. Detected conflicts
#   2. Retrieved supporting evidence
#   3. Source/page traceability
#
# Important:
# The evidence automatically attached during claim extraction is
# the claim's own source passage. That proves provenance, but it
# is NOT independent verification. We therefore ignore an exact
# self-copy of the claim when evaluating supporting evidence.
#
# Human review remains a separate layer.
# A human decision can later override the automated result.
# ============================================================


def get_related_conflicts(claim_id: str, conflicts: list):
    """Return all conflicts involving a particular claim."""

    related = []

    for conflict in conflicts:
        claim_a = conflict.get("claim_a", {})
        claim_b = conflict.get("claim_b", {})

        if (
            claim_a.get("id") == claim_id
            or claim_b.get("id") == claim_id
        ):
            related.append(conflict)

    return related


def normalize_evidence(evidence):
    """Convert evidence into a consistent list format."""

    if not evidence:
        return []

    if isinstance(evidence, dict):
        return [evidence]

    if isinstance(evidence, list):
        return [
            item
            for item in evidence
            if isinstance(item, dict)
        ]

    return []


def _clean(value):
    """Normalize text for safe comparison."""

    if value is None:
        return ""

    return " ".join(str(value).split()).strip().lower()


def is_self_evidence(claim: dict, evidence_item: dict):
    """
    Return True when an evidence item is simply the same passage
    from which the claim itself was extracted.

    Such evidence is useful for provenance, but must not count as
    corroborating evidence.
    """

    claim_text = _clean(claim.get("text"))
    evidence_text = _clean(evidence_item.get("text"))

    if not claim_text or not evidence_text:
        return False

    if claim_text != evidence_text:
        return False

    claim_document_id = claim.get("document_id")
    evidence_document_id = evidence_item.get("document_id")

    claim_source = _clean(claim.get("source"))
    evidence_source = _clean(evidence_item.get("source"))

    same_document = (
        bool(claim_document_id)
        and bool(evidence_document_id)
        and claim_document_id == evidence_document_id
    )

    same_source = (
        bool(claim_source)
        and bool(evidence_source)
        and claim_source == evidence_source
    )

    claim_page = claim.get("page")
    evidence_page = evidence_item.get("page")

    same_page = (
        claim_page is not None
        and evidence_page is not None
        and claim_page == evidence_page
    )

    return (same_document or same_source) and same_page


def analyze_evidence(claim: dict):
    """
    Analyze actual supporting evidence attached to a claim.

    The claim's own exact source passage is excluded because it
    provides provenance, not corroboration.

    Returns:
        evidence_count
        source_count
        independent_source_count
        has_direct_support
    """

    raw_evidence = normalize_evidence(
        claim.get("evidence")
    )

    claim_document_id = claim.get("document_id")
    claim_source = _clean(claim.get("source"))

    supporting_evidence = []

    for item in raw_evidence:
        if not is_self_evidence(claim, item):
            supporting_evidence.append(item)

    source_documents = set()
    independent_documents = set()
    has_direct_support = False

    for item in supporting_evidence:
        evidence_document_id = item.get("document_id")
        evidence_source = _clean(item.get("source"))

        source_key = (
            evidence_document_id
            or evidence_source
        )

        if source_key:
            source_documents.add(str(source_key))

        same_document = (
            bool(claim_document_id)
            and bool(evidence_document_id)
            and evidence_document_id == claim_document_id
        )

        same_source = (
            bool(claim_source)
            and bool(evidence_source)
            and evidence_source == claim_source
        )

        if same_document or same_source:
            has_direct_support = True
        else:
            independent_key = (
                evidence_document_id
                or evidence_source
            )

            if independent_key:
                independent_documents.add(
                    str(independent_key)
                )

    return {
        "evidence_count": len(supporting_evidence),
        "source_count": len(source_documents),
        "independent_source_count": len(
            independent_documents
        ),
        "has_direct_support": has_direct_support
    }


def determine_verification_status(
    claim: dict,
    conflicts: list
):
    """
    Determine automated verification status.

    Priority:

        1. Conflict
        2. Independent supporting evidence
        3. Direct supporting evidence from the same document
        4. Traceable source only
        5. Unresolved
    """

    claim_id = claim.get("id")

    # --------------------------------------------------------
    # 1. Conflict takes priority.
    # --------------------------------------------------------

    related_conflicts = get_related_conflicts(
        claim_id,
        conflicts
    )

    if related_conflicts:
        return {
            "status": "CONFLICTING",
            "confidence": 0.0,
            "reason": (
                "Conflicting information was detected "
                "for this claim. Human review is required."
            ),
            "conflict_count": len(related_conflicts)
        }

    # --------------------------------------------------------
    # 2. Analyze actual supporting evidence.
    # --------------------------------------------------------

    evidence_info = analyze_evidence(claim)

    evidence_count = evidence_info[
        "evidence_count"
    ]

    independent_source_count = evidence_info[
        "independent_source_count"
    ]

    has_direct_support = evidence_info[
        "has_direct_support"
    ]

    # --------------------------------------------------------
    # 3. Independent corroboration.
    # --------------------------------------------------------

    if independent_source_count > 0:
        return {
            "status": "VERIFIED",
            "confidence": 0.95,
            "reason": (
                "The claim is supported by evidence "
                "from an independent source document."
            ),
            "conflict_count": 0,
            "evidence_count": evidence_count,
            "independent_source_count": independent_source_count,
            "evidence_type": "INDEPENDENT"
        }

    # --------------------------------------------------------
    # 4. Supporting passage from the same source document.
    # --------------------------------------------------------

    if has_direct_support:
        return {
            "status": "VERIFIED",
            "confidence": 0.85,
            "reason": (
                "The claim is supported by a separate "
                "traceable passage in its source document."
            ),
            "conflict_count": 0,
            "evidence_count": evidence_count,
            "independent_source_count": 0,
            "evidence_type": "DIRECT_SOURCE"
        }

    # --------------------------------------------------------
    # 5. No corroborating evidence, but source/page exists.
    # --------------------------------------------------------

    source = claim.get("source")
    page = claim.get("page")

    if source and page is not None:
        return {
            "status": "PARTIALLY_SUPPORTED",
            "confidence": 0.50,
            "reason": (
                "The claim has a traceable source and page, "
                "but no separate supporting evidence was found."
            ),
            "conflict_count": 0,
            "evidence_count": evidence_count,
            "independent_source_count": 0,
            "evidence_type": "SOURCE_ONLY"
        }

    # --------------------------------------------------------
    # 6. No reliable support.
    # --------------------------------------------------------

    return {
        "status": "UNRESOLVED",
        "confidence": 0.0,
        "reason": (
            "No reliable supporting evidence or "
            "traceable source was found."
        ),
        "conflict_count": 0,
        "evidence_count": 0,
        "independent_source_count": 0,
        "evidence_type": "NONE"
    }


def verify_claims(
    claims: list,
    conflicts: list
):
    """Verify every claim using conflicts and available evidence."""

    verified_claims = []

    for claim in claims:
        verification = determine_verification_status(
            claim,
            conflicts
        )

        verified_claims.append({
            **claim,
            "verification": verification
        })

    return verified_claims
