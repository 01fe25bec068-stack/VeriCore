
import re
from collections import Counter


MIN_RELEVANCE_SCORE = 0.20
MIN_SHARED_TERMS = 2

STOP_WORDS = {
    "the", "a", "an", "and", "or", "is", "are", "was", "were",
    "to", "of", "in", "on", "for", "with", "as", "by", "this",
    "that", "from", "it", "be", "at", "can", "will", "should",
    "every", "each", "during", "while", "also", "must", "may",
    "shall", "has", "have", "had", "been", "being", "their",
    "its", "into", "above", "below", "before", "after", "than",
    "then", "when", "where", "which", "who", "what", "how",
}

GENERIC_HEADINGS = {
    "recommended maintenance",
    "operating limits",
    "safety guidance",
    "inspection details",
    "maintenance report",
}

UNIT_NORMALIZATIONS = [
    (re.compile(r"°\s*c\b", re.IGNORECASE), " celsius "),
    (re.compile(r"\bmm\s*/\s*s\b", re.IGNORECASE),
     " millimeters_per_second "),
    (re.compile(r"\bcm\s*/\s*s\b", re.IGNORECASE),
     " centimeters_per_second "),
    (re.compile(r"\bkg\s*/\s*m\s*(?:³|3)\b", re.IGNORECASE),
     " kilograms_per_cubic_meter "),
]


def normalize_text(text: str) -> str:
    """Normalize units and whitespace before tokenization."""
    text = str(text or "").lower()

    for pattern, replacement in UNIT_NORMALIZATIONS:
        text = pattern.sub(replacement, text)

    return text


def tokenize(text: str) -> list[str]:
    """Convert text into normalized, explainable comparison tokens."""
    text = normalize_text(text)

    # Preserve normalized compound units containing underscores.
    words = re.findall(r"\b[a-z0-9_]+\b", text)

    return [
        word for word in words
        if word not in STOP_WORDS and not word.isdigit()
    ]


def calculate_relevance(claim_text: str, page_text: str) -> float:
    """
    Calculate lexical overlap.

    This score measures word overlap only. It does not establish
    that a passage supports, contradicts, or verifies a claim.
    """
    claim_words = tokenize(claim_text)
    page_words = tokenize(page_text)

    if not claim_words or not page_words:
        return 0.0

    claim_counts = Counter(claim_words)
    page_counts = Counter(page_words)

    matched_words = sum(
        min(count, page_counts[word])
        for word, count in claim_counts.items()
        if word in page_counts
    )

    return round(matched_words / len(set(claim_words)), 3)


def split_passages(text: str) -> list[str]:
    """Split extracted page text into usable passages."""
    text = str(text or "").strip()

    if not text:
        return []

    # Split on paragraph boundaries first.
    passages = [
        part.strip()
        for part in re.split(r"\n\s*\n+", text)
        if part.strip()
    ]

    if len(passages) <= 1:
        # Fall back to sentence-like passages for plain-text pages.
        passages = [
            part.strip()
            for part in re.split(r"(?<=[.!?])\s+", text)
            if part.strip()
        ]

    return passages or [text]


def is_generic_heading(text: str) -> bool:
    """Exclude passages that consist only of a generic heading."""
    cleaned = re.sub(r"^\s*[\d.\-:)\s]+", "", text.lower()).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.rstrip(":") in GENERIC_HEADINGS


def retrieve_evidence(
    claim_text: str,
    documents: dict,
    top_k: int = 5,
) -> list[dict]:
    """
    Retrieve candidate evidence passages with document/page provenance.

    Results are candidates for review, not confirmed support.
    """
    results = []

    if not claim_text or not claim_text.strip() or top_k <= 0:
        return results

    claim_tokens = set(tokenize(claim_text))

    if not claim_tokens:
        return results

    for document in documents.values():
        for page in document.get("pages", []):
            page_text = str(page.get("text", "") or "").strip()

            if not page_text:
                continue

            for passage in split_passages(page_text):
                if is_generic_heading(passage):
                    continue

                passage_tokens = set(tokenize(passage))
                shared_terms = sorted(claim_tokens & passage_tokens)

                if len(shared_terms) < MIN_SHARED_TERMS:
                    continue

                score = calculate_relevance(claim_text, passage)

                if score < MIN_RELEVANCE_SCORE:
                    continue

                results.append({
                    "document_id": document.get("id"),
                    "filename": document.get("filename"),
                    "source": document.get("filename"),
                    "page": page.get("page"),
                    "text": passage,
                    "relevance_score": score,
                    "shared_terms": shared_terms,
                    "evidence_type": "CANDIDATE",
                })

    # Rank by score, then by the number of matching terms.
    results.sort(
        key=lambda item: (
            item["relevance_score"],
            len(item["shared_terms"]),
        ),
        reverse=True,
    )

    # Remove duplicate passages from the same source and page.
    unique_results = []
    seen = set()

    for item in results:
        key = (
            item.get("document_id"),
            item.get("page"),
            item.get("text", "").strip().lower(),
        )

        if key in seen:
            continue

        seen.add(key)
        unique_results.append(item)

        if len(unique_results) >= top_k:
            break

    return unique_results


def retrieve_evidence_for_claim(
    claim: dict,
    documents: dict,
    top_k: int = 5,
) -> dict:
    """Retrieve candidate evidence for an existing claim."""
    claim_text = claim.get("text", "")

    evidence = retrieve_evidence(claim_text, documents, top_k)

    return {
        "claim_id": claim.get("id"),
        "claim_text": claim_text,
        "evidence_count": len(evidence),
        "evidence": evidence,
    }
