
# ============================================================
# VERIFICATION
# ============================================================
# Candidate evidence is not automatically confirmed support.
# Conflicts remain reviewable by a human.
# Human decisions are handled separately by app.py.
# ============================================================

def get_related_conflicts(claim_id: str, conflicts: list):
    """Return conflicts involving this claim."""
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
    """Normalize evidence into a list of dictionaries."""
    if isinstance(evidence, dict):
        return [evidence]

    if isinstance(evidence, list):
        return [item for item in evidence if isinstance(item, dict)]

    return []


def _clean(value):
    """Normalize whitespace and case for comparisons."""
    return " ".join(str(value or "").split()).strip().lower()


def is_self_evidence(claim: dict, evidence_item: dict) -> bool:
    """Identify the exact source passage from which a claim came."""
    claim_text = _clean(claim.get("text"))
    evidence_text = _clean(evidence_item.get("text"))

    if not claim_text or claim_text != evidence_text:
        return False

    claim_doc = claim.get("document_id")
    evidence_doc = evidence_item.get("document_id")

    same_document = bool(claim_doc and evidence_doc and claim_doc == evidence_doc)

    claim_source = _clean(claim.get("source"))
    evidence_source = _clean(evidence_item.get("source"))
    same_source = bool(claim_source and evidence_source and claim_source == evidence_source)

    claim_page = claim.get("page")
    evidence_page = evidence_item.get("page")
    same_page = claim_page is not None and evidence_page is not None and claim_page == evidence_page

    return same_page and (same_document or same_source)


def analyze_evidence(claim: dict):
    """
    Count candidate passages and independent sources.

    IMPORTANT: Independent origin and lexical relevance do not
    establish semantic support. Candidates remain unconfirmed
    unless a separate trusted support-checking step confirms them.
    """
    evidence = normalize_evidence(claim.get("evidence"))
    candidates = [
        item for item in evidence
        if not is_self_evidence(claim, item)
    ]

    source_documents = set()
    independent_documents = set()

    claim_doc = claim.get("document_id")
    claim_source = _clean(claim.get("source"))

    for item in candidates:
        evidence_doc = item.get("document_id")
        evidence_source = _clean(item.get("source") or item.get("filename"))

        source_key = evidence_doc or evidence_source
        if source_key:
            source_documents.add(str(source_key))

        same_document = bool(claim_doc and evidence_doc and claim_doc == evidence_doc)
        same_source = bool(claim_source and evidence_source and claim_source == evidence_source)

        if not same_document and not same_source and source_key:
            independent_documents.add(str(source_key))

    return {
        "evidence_count": len(candidates),
        "source_count": len(source_documents),
        "independent_source_count": len(independent_documents),
        "has_direct_support": False,
        "support_confirmed": False,
    }


def determine_verification_status(claim: dict, conflicts: list):
    """Return a conservative automated verification assessment."""

    related_conflicts = get_related_conflicts(claim.get("id"), conflicts)

    if related_conflicts:
        return {
            "status": "CONFLICTING",
            "confidence": 0.0,
            "reason": "Conflicting information was detected. Human review is required.",
            "conflict_count": len(related_conflicts),
            "evidence_type": "CONFLICT",
        }

    evidence_info = analyze_evidence(claim)

    # Only an explicit support confirmation may qualify a claim
    # for VERIFIED. Retrieval scores and source counts alone do not.
    if claim.get("evidence_support_confirmed") is True:
        return {
            "status": "VERIFIED",
            "confidence": 0.95,
            "reason": "A separate support-checking step explicitly confirmed the evidence.",
            "conflict_count": 0,
            "evidence_count": evidence_info["evidence_count"],
            "independent_source_count": evidence_info["independent_source_count"],
            "evidence_type": "CONFIRMED_SUPPORT",
        }

    source = claim.get("source")
    page = claim.get("page")

    if evidence_info["evidence_count"] > 0:
        return {
            "status": "PARTIALLY_SUPPORTED",
            "confidence": 0.5,
            "reason": (
                "Candidate passages were retrieved, but their semantic "
                "support has not been confirmed."
            ),
            "conflict_count": 0,
            "evidence_count": evidence_info["evidence_count"],
            "independent_source_count": evidence_info["independent_source_count"],
            "evidence_type": "CANDIDATE_ONLY",
        }

    if source and page is not None:
        return {
            "status": "PARTIALLY_SUPPORTED",
            "confidence": 0.5,
            "reason": "The claim has a traceable source and page, but no separate supporting evidence was confirmed.",
            "conflict_count": 0,
            "evidence_count": 0,
            "independent_source_count": 0,
            "evidence_type": "SOURCE_ONLY",
        }

    return {
        "status": "UNRESOLVED",
        "confidence": 0.0,
        "reason": "No reliable supporting evidence or traceable source was found.",
        "conflict_count": 0,
        "evidence_count": 0,
        "independent_source_count": 0,
        "evidence_type": "NONE",
    }


def verify_claims(claims: list, conflicts: list):
    """Assess every claim while preserving its original fields."""
    results = []

    for claim in claims:
        verification = determine_verification_status(claim, conflicts)
        results.append({
            **claim,
            "verification": verification,
        })

    return results