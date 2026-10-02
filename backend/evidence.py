import re
from collections import Counter


def tokenize(text: str):
    """
    Convert text into normalized words for comparison.
    """
    words = re.findall(r"\b[a-zA-Z0-9]+\b", text.lower())

    # Ignore very common words that don't help identify evidence
    stop_words = {
        "the", "a", "an", "and", "or", "is", "are",
        "was", "were", "to", "of", "in", "on", "for",
        "with", "as", "by", "this", "that", "from",
        "it", "be", "at", "can", "will", "should"
    }

    return [word for word in words if word not in stop_words]


def calculate_relevance(claim_text: str, page_text: str):
    """
    Calculate a simple explainable relevance score based
    on overlapping words between the claim and document page.
    """

    claim_words = tokenize(claim_text)
    page_words = tokenize(page_text)

    if not claim_words or not page_words:
        return 0.0

    claim_counts = Counter(claim_words)
    page_counts = Counter(page_words)

    matched_words = 0

    for word, count in claim_counts.items():
        if word in page_counts:
            matched_words += min(count, page_counts[word])

    score = matched_words / len(set(claim_words))

    return round(score, 3)


def retrieve_evidence(claim_text: str, documents: dict, top_k: int = 5):
    """
    Search all uploaded documents and return the most
    relevant passages for a claim.

    Every result keeps its original document and page
    information for provenance.
    """

    results = []

    if not claim_text or not claim_text.strip():
        return results

    for document in documents.values():

        for page in document.get("pages", []):

            page_text = page.get("text", "").strip()

            if not page_text:
                continue

            score = calculate_relevance(
                claim_text,
                page_text
            )

            if score <= 0:
                continue

            results.append({
                "document_id": document.get("id"),
                "filename": document.get("filename"),
                "page": page.get("page"),
                "text": page_text,
                "relevance_score": score
            })

    # Highest relevance first
    results.sort(
        key=lambda item: item["relevance_score"],
        reverse=True
    )

    return results[:top_k]


def retrieve_evidence_for_claim(claim: dict, documents: dict, top_k: int = 5):
    """
    Retrieve evidence using the text of an existing claim.
    """

    claim_text = claim.get("text", "")

    evidence = retrieve_evidence(
        claim_text,
        documents,
        top_k
    )

    return {
        "claim_id": claim.get("id"),
        "claim_text": claim_text,
        "evidence_count": len(evidence),
        "evidence": evidence
    }