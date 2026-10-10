

import json

import hashlib

import uuid

from datetime import datetime

from pathlib import Path

import fitz

from fastapi import FastAPI, UploadFile, File, HTTPException

from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel

from database import get_connection, initialize_database, DB_PATH

from claims import extract_claims_from_document

from conflicts import detect_conflicts

from verification import verify_claims

from comparison import compare_claims, compare_claim_set

from evidence import retrieve_evidence_for_claim

from entities import resolve_entities

# ============================================================

# APP

# ============================================================

app = FastAPI(

    title="veriCore Backend",

    description="Multi-source document verification system",

    version="1.0.0"

)

app.add_middleware(

    CORSMiddleware,

    allow_origins=[

        "http://localhost:5173",

        "http://localhost:5174",

        "https://vericore-1.onrender.com",

    ],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],

)

# ============================================================

# STORAGE

# ============================================================

BASE_DIR = Path(__file__).resolve().parent

UPLOAD_DIR = BASE_DIR / "uploads"

UPLOAD_DIR.mkdir(exist_ok=True)

documents = {}

claims = []

audit_trail = []

verification_decisions = []

generated_report = None

# ============================================================

# MODELS

# ============================================================

class VerificationDecision(BaseModel):

    claim_id: str

    decision: str

    reason: str = ""

    reviewer: str = "human-reviewer"

# ============================================================

# HELPERS

# ============================================================

def now():

    return datetime.utcnow().isoformat()

def calculate_hash(data: bytes) -> str:

    return hashlib.sha256(data).hexdigest()

def extract_pdf(data: bytes):

    pages = []

    pdf = fitz.open(stream=data, filetype="pdf")

    try:

        for page_number, page in enumerate(pdf, start=1):

            pages.append({

                "page": page_number,

                "text": page.get_text("text").strip()

            })

    finally:

        pdf.close()

    return pages

def extract_text_file(data: bytes):

    return [{"page": 1, "text": data.decode("utf-8", errors="ignore").strip()}]

def safe_json(value):

    try:

        return json.dumps(value, ensure_ascii=False)

    except TypeError:

        return json.dumps(str(value), ensure_ascii=False)

def parse_json(value, default=None):

    if value is None:

        return default

    try:

        return json.loads(value)

    except (TypeError, json.JSONDecodeError):

        return default

def first_evidence(claim):

    evidence = claim.get("evidence", [])

    if isinstance(evidence, dict):

        return evidence

    if isinstance(evidence, list) and evidence:

        return evidence[0]

    return None

def persist_document(document):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""

        INSERT OR REPLACE INTO documents

        (id, filename, file_type, size, sha256, uploaded_at, status)

        VALUES (?, ?, ?, ?, ?, ?, ?)

    """, (

        document["id"],

        document["filename"],

        document["file_type"],

        document.get("size", 0),

        document["sha256"],

        document["uploaded_at"],

        document["status"]

    ))

    cursor.execute(

        "DELETE FROM document_pages WHERE document_id = ?",

        (document["id"],)

    )

    for page in document.get("pages", []):

        cursor.execute("""

            INSERT OR REPLACE INTO document_pages

            (document_id, page, text)

            VALUES (?, ?, ?)

        """, (

            document["id"],

            page["page"],

            page.get("text", "")

        ))

    connection.commit()

    connection.close()

def persist_claim(claim):

    evidence = first_evidence(claim) or {}

    connection = get_connection()

    connection.execute("""

        INSERT OR REPLACE INTO claims

        (id, document_id, source, page, text, status,

         evidence_source, evidence_page, evidence_text)

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)

    """, (

        claim.get("id"),

        claim.get("document_id"),

        claim.get("source"),

        claim.get("page"),

        claim.get("text", ""),

        claim.get("status", "UNVERIFIED"),

        evidence.get("source"),

        evidence.get("page"),

        evidence.get("text")

    ))

    connection.commit()

    connection.close()

def load_claim_from_row(row):

    claim = {

        "id": row["id"],

        "document_id": row["document_id"],

        "source": row["source"],

        "page": row["page"],

        "text": row["text"],

        "status": row["status"] or "UNVERIFIED"

    }

    if row["evidence_source"] is not None:

        claim["evidence"] = [{

            "source": row["evidence_source"],

            "page": row["evidence_page"],

            "text": row["evidence_text"]

        }]

    return claim

def load_state():

    global generated_report

    documents.clear()

    claims.clear()

    audit_trail.clear()

    verification_decisions.clear()

    connection = get_connection()

    cursor = connection.cursor()

    document_rows = cursor.execute(

        "SELECT * FROM documents ORDER BY uploaded_at"

    ).fetchall()

    for row in document_rows:

        pages = cursor.execute("""

            SELECT page, text

            FROM document_pages

            WHERE document_id = ?

            ORDER BY page

        """, (row["id"],)).fetchall()

        documents[row["id"]] = {

            "id": row["id"],

            "filename": row["filename"],

            "file_type": row["file_type"],

            "size": row["size"],

            "sha256": row["sha256"],

            "uploaded_at": row["uploaded_at"],

            "status": row["status"],

            "pages": [

                {"page": p["page"], "text": p["text"] or ""}

                for p in pages

            ]

        }

    claim_rows = cursor.execute(

        "SELECT * FROM claims ORDER BY rowid"

    ).fetchall()

    for row in claim_rows:

        claims.append(load_claim_from_row(row))

    audit_rows = cursor.execute(

        "SELECT * FROM audit_trail ORDER BY timestamp"

    ).fetchall()

    for row in audit_rows:

        audit_trail.append({

            "id": row["id"],

            "timestamp": row["timestamp"],

            "action": row["action"],

            "document_id": row["document_id"],

            "details": parse_json(row["details"], {})

        })

    decision_rows = cursor.execute(

        "SELECT * FROM verification_decisions ORDER BY timestamp"

    ).fetchall()

    for row in decision_rows:

        verification_decisions.append({

            "id": row["id"],

            "claim_id": row["claim_id"],

            "decision": row["decision"],

            "reason": row["reason"] or "",

            "reviewer": row["reviewer"] or "human-reviewer",

            "timestamp": row["timestamp"]

        })

    report_row = cursor.execute("""

        SELECT report_data

        FROM reports

        ORDER BY generated_at DESC

        LIMIT 1

    """).fetchone()

    generated_report = (

        parse_json(report_row["report_data"], None)

        if report_row else None

    )

    connection.close()

def add_audit_event(action, document_id=None, details=None):

    event = {

        "id": str(uuid.uuid4()),

        "timestamp": now(),

        "action": action,

        "document_id": document_id,

        "details": details or {}

    }

    audit_trail.append(event)

    connection = get_connection()

    connection.execute("""

        INSERT INTO audit_trail

        (id, timestamp, action, document_id, details)

        VALUES (?, ?, ?, ?, ?)

    """, (

        event["id"],

        event["timestamp"],

        event["action"],

        event["document_id"],

        safe_json(event["details"])

    ))

    connection.commit()

    connection.close()

def persist_conflicts(conflicts):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("DELETE FROM conflicts")

    for conflict in conflicts:

        claim_a = conflict.get("claim_a", {})

        claim_b = conflict.get("claim_b", {})

        claim_a_id = claim_a.get("id")

        claim_b_id = claim_b.get("id")

        if not claim_a_id or not claim_b_id:

            continue

        cursor.execute("""

            INSERT INTO conflicts

            (id, claim_a_id, claim_b_id, status, reason, created_at)

            VALUES (?, ?, ?, ?, ?, ?)

        """, (

            str(uuid.uuid4()),

            claim_a_id,

            claim_b_id,

            "CONFLICTING",

            conflict.get("reason", "Conflicting information found."),

            now()

        ))

    connection.commit()

    connection.close()

def persist_verification_results(results):

    connection = get_connection()

    cursor = connection.cursor()

    for result in results:

        claim_id = result.get("id") or result.get("claim_id")

        verification = result.get("verification", {})

        if not claim_id:

            continue

        status = (

            verification.get("status")

            or result.get("status")

            or "UNVERIFIED"

        )

        confidence = verification.get("confidence")

        reason = verification.get("reason", "")

        conflict_count = verification.get("conflict_count", 0)

        cursor.execute("""

            INSERT OR REPLACE INTO verification_results

            (id, claim_id, status, confidence, reason,

             conflict_count, verified_at)

            VALUES (?, ?, ?, ?, ?, ?, ?)

        """, (

            str(uuid.uuid4()),

            claim_id,

            status,

            confidence,

            reason,

            conflict_count,

            now()

        ))

    connection.commit()

    connection.close()

# ============================================================

# STARTUP

# ============================================================

@app.on_event("startup")

def startup():

    initialize_database()

    load_state()

# ============================================================

# BASIC ROUTES

# ============================================================

@app.get("/")

def root():

    return {

        "system": "veriCore",

        "status": "running",

        "message": "Multi-source verification backend is online.",

        "database": str(DB_PATH)

    }

@app.get("/api/health")

def health():

    return {

        "status": "healthy",

        "documents": len(documents),

        "claims": len(claims)

    }

# ============================================================

# DOCUMENT UPLOAD

# ============================================================

@app.post("/api/documents/upload")

async def upload_documents(files: list[UploadFile] = File(...)):

    uploaded = []

    for file in files:

        if not file.filename:

            continue

        extension = Path(file.filename).suffix.lower()

        if extension not in [".pdf", ".txt"]:

            raise HTTPException(

                status_code=400,

                detail=(

                    f"Unsupported file type: {extension}. "

                    "Currently supported: PDF and TXT."

                )

            )

        data = await file.read()

        if not data:

            raise HTTPException(

                status_code=400,

                detail=f"{file.filename} is empty."

            )

        file_hash = calculate_hash(data)

        # ----------------------------------------------------

        # Duplicate protection

        #

        # SHA-256 identifies the actual file contents. If the

        # exact same file was already uploaded, reuse the

        # existing document instead of creating another logical

        # document and another set of claims.

        # ----------------------------------------------------

        existing_document = next(

            (

                document

                for document in documents.values()

                if document.get("sha256") == file_hash

            ),

            None

        )

        if existing_document:

            # The document record may exist without extracted pages

            # after a database cleanup. In that case, restore the

            # extracted text on the existing record instead of creating

            # a duplicate document.

            if not existing_document.get("pages"):

                pages = (

                    extract_pdf(data)

                    if extension == ".pdf"

                    else extract_text_file(data)

                )

                existing_document["size"] = len(data)

                existing_document["pages"] = pages

                existing_document["status"] = "processed"

                persist_document(existing_document)

                add_audit_event(

                    "DOCUMENT_TEXT_RESTORED",

                    existing_document["id"],

                    {

                        "filename": file.filename,

                        "pages": len(pages),

                        "sha256": file_hash

                    }

                )

                uploaded.append({

                    "id": existing_document["id"],

                    "filename": existing_document["filename"],

                    "file_type": existing_document["file_type"],

                    "pages": len(pages),

                    "status": "restored_existing"

                })

            else:

                add_audit_event(

                    "DUPLICATE_DOCUMENT_DETECTED",

                    existing_document["id"],

                    {

                        "filename": file.filename,

                        "existing_document_id": existing_document["id"],

                        "sha256": file_hash

                    }

                )

                uploaded.append({

                    "id": existing_document["id"],

                    "filename": existing_document["filename"],

                    "file_type": existing_document["file_type"],

                    "pages": len(existing_document.get("pages", [])),

                    "status": "already_exists"

                })

            continue

        document_id = str(uuid.uuid4())

        save_path = UPLOAD_DIR / f"{document_id}{extension}"

        save_path.write_bytes(data)

        pages = (

            extract_pdf(data)

            if extension == ".pdf"

            else extract_text_file(data)

        )

        document = {

            "id": document_id,

            "filename": file.filename,

            "file_type": extension.replace(".", "").upper(),

            "size": len(data),

            "sha256": file_hash,

            "uploaded_at": now(),

            "pages": pages,

            "status": "processed"

        }

        documents[document_id] = document

        persist_document(document)

        add_audit_event(

            "DOCUMENT_UPLOADED",

            document_id,

            {

                "filename": file.filename,

                "pages": len(pages),

                "sha256": file_hash

            }

        )

        uploaded.append({

            "id": document_id,

            "filename": file.filename,

            "file_type": document["file_type"],

            "pages": len(pages),

            "status": "processed"

        })

    return {

        "success": True,

        "message": "Documents uploaded and text extracted.",

        "documents": uploaded

    }

@app.get("/api/documents")

def get_documents():

    return {

        "success": True,

        "count": len(documents),

        "documents": list(documents.values())

    }

@app.get("/api/documents/{document_id}")

def get_document(document_id: str):

    document = documents.get(document_id)

    if not document:

        raise HTTPException(

            status_code=404,

            detail="Document not found."

        )

    return {"success": True, "document": document}


@app.delete("/api/documents/{document_id}")
def delete_document(document_id: str):
    global generated_report

    document = documents.get(document_id)

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    filename = document.get("filename", "Unknown document")
    extension = Path(filename).suffix.lower()
    file_path = UPLOAD_DIR / f"{document_id}{extension}"

    connection = get_connection()

    try:
        cursor = connection.cursor()

        # Capture claim IDs BEFORE deleting the document.
        rows = cursor.execute(
            "SELECT id FROM claims WHERE document_id = ?",
            (document_id,)
        ).fetchall()

        deleted_claim_ids = {
            row["id"] for row in rows
        }

        # Record the deletion so the audit history is preserved.
        event = {
            "id": str(uuid.uuid4()),
            "timestamp": now(),
            "action": "DOCUMENT_DELETED",
            "document_id": document_id,
            "details": {
                "filename": filename,
                "deleted_claim_count": len(deleted_claim_ids)
            }
        }

        cursor.execute("""
            INSERT INTO audit_trail
            (id, timestamp, action, document_id, details)
            VALUES (?, ?, ?, ?, ?)
        """, (
            event["id"],
            event["timestamp"],
            event["action"],
            event["document_id"],
            safe_json(event["details"])
        ))

        # Foreign-key cascades delete associated pages, claims,
        # conflicts, verification results and decisions.
        cursor.execute(
            "DELETE FROM documents WHERE id = ?",
            (document_id,)
        )

        connection.commit()

    except Exception as exc:
        connection.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not delete the document. Check the backend logs."
        ) from exc

    finally:
        connection.close()

    # Update the in-memory state after the database succeeds.
    documents.pop(document_id, None)

    claims[:] = [
        claim for claim in claims
        if claim.get("document_id") != document_id
    ]

    verification_decisions[:] = [
        decision for decision in verification_decisions
        if decision.get("claim_id") not in deleted_claim_ids
    ]

    # Remove the uploaded file, if it exists.
    try:
        if file_path.is_file():
            file_path.unlink()
    except OSError:
        # The database deletion succeeded; report file cleanup
        # can be retried manually if necessary.
        pass

    # Preserve historical audit events and invalidate the current
    # in-memory report so it cannot be mistaken for a fresh report.
    audit_trail.append(event)
    generated_report = None

    return {
        "success": True,
        "message": "Document deleted successfully.",
        "document_id": document_id,
        "filename": filename,
        "deleted_claims": len(deleted_claim_ids)
    }


@app.get("/api/documents/search")

def search_documents(q: str):

    if not q.strip():

        raise HTTPException(

            status_code=400,

            detail="Search query cannot be empty."

        )

    query = q.lower()

    results = []

    for document in documents.values():

        for page in document.get("pages", []):

            text = page.get("text", "")

            if query in text.lower():

                results.append({

                    "document_id": document["id"],

                    "filename": document["filename"],

                    "page": page["page"],

                    "text": text

                })

    return {

        "success": True,

        "query": q,

        "matches": len(results),

        "results": results

    }

# ============================================================

# CLAIMS

# ============================================================

@app.get("/api/claims")

def get_claims():

    return {

        "success": True,

        "count": len(claims),

        "claims": claims

    }

@app.post("/api/claims/extract/{document_id}")

def extract_document_claims(document_id: str):

    document = documents.get(document_id)

    if not document:

        raise HTTPException(

            status_code=404,

            detail="Document not found."

        )

    extracted = extract_claims_from_document(document)

    saved = []

    # Build signatures for claims that already exist.

    # This prevents the same document/page/text from being

    # inserted again even though extraction generates a new UUID.

    existing_signatures = {

        (

            claim.get("document_id"),

            claim.get("page"),

            claim.get("text", "").strip()

        )

        for claim in claims

    }

    for claim in extracted:

        claim_text = claim.get(

            "text",

            ""

        ).strip()

        signature = (

            document_id,

            claim.get("page"),

            claim_text

        )

        # Skip an already-existing claim.

        if signature in existing_signatures:

            continue

        # Make sure every new claim has an ID.

        claim["id"] = (

            claim.get("id")

            or str(uuid.uuid4())

        )

        claim["document_id"] = document_id

        claim["source"] = document["filename"]

        claim.setdefault(

            "status",

            "UNVERIFIED"

        )

        claims.append(claim)

        persist_claim(claim)

        saved.append(claim)

        # Prevent duplicates within the same extraction response.

        existing_signatures.add(signature)

    add_audit_event(

        "CLAIMS_EXTRACTED",

        document_id,

        {

            "filename": document["filename"],

            "claims_extracted": len(saved)

        }

    )

    return {

        "success": True,

        "document_id": document_id,

        "filename": document["filename"],

        "claims_extracted": len(saved),

        "claims": saved

    }

# ============================================================

# CONFLICTS

# ============================================================

@app.post("/api/conflicts/detect")

def detect_all_conflicts():

    conflicts = detect_conflicts(claims)

    persist_conflicts(conflicts)

    add_audit_event(

        "CONFLICT_DETECTION",

        details={

            "claims_checked": len(claims),

            "conflicts_found": len(conflicts)

        }

    )

    return {

        "success": True,

        "claims_checked": len(claims),

        "conflicts_found": len(conflicts),

        "conflicts": conflicts

    }

@app.get("/api/conflicts")

def get_conflicts():

    conflicts = detect_conflicts(claims)

    persist_conflicts(conflicts)

    return {

        "success": True,

        "count": len(conflicts),

        "conflicts": conflicts

    }

# ============================================================

# VERIFICATION

# ============================================================

def refresh_claim_evidence():

    """

    Retrieve supporting evidence for every claim before automated

    verification.

    The claim's own extracted passage remains available for

    provenance, while the verification module decides whether

    retrieved evidence is actual corroboration.

    """

    retrieved_count = 0

    for claim in claims:

        try:

            result = retrieve_evidence_for_claim(

                claim,

                documents

            )

            evidence = result.get("evidence", [])

            if evidence:

                # The current SQLite schema stores one evidence passage

                # per claim. Put corroborating evidence first so that

                # the most useful evidence survives a server restart.

                claim_text = " ".join(

                    str(claim.get("text", "")).split()

                ).strip().lower()

                claim_source = str(

                    claim.get("source", "")

                ).strip().lower()

                claim_page = claim.get("page")

                def is_self_evidence(item):

                    evidence_text = " ".join(

                        str(item.get("text", "")).split()

                    ).strip().lower()

                    evidence_source = str(

                        item.get("source", "")

                    ).strip().lower()

                    evidence_page = item.get("page")

                    return (

                        evidence_text == claim_text

                        and evidence_source == claim_source

                        and evidence_page == claim_page

                    )

                supporting = [

                    item

                    for item in evidence

                    if isinstance(item, dict)

                    and not is_self_evidence(item)

                ]

                self_evidence = [

                    item

                    for item in evidence

                    if isinstance(item, dict)

                    and is_self_evidence(item)

                ]

                claim["evidence"] = supporting + self_evidence

                persist_claim(claim)

                retrieved_count += len(evidence)

        except Exception:

            # One failed evidence lookup must not prevent the

            # remaining claims from being verified.

            continue

    return retrieved_count

def build_verification_results(refresh_evidence=True):

    """

    Run the complete automated verification pipeline.

    Order:

        1. Retrieve supporting evidence

        2. Detect cross-document conflicts

        3. Verify claims

    """

    if refresh_evidence:

        refresh_claim_evidence()

    conflicts = detect_conflicts(claims)

    persist_conflicts(conflicts)

    verified_claims = verify_claims(

        claims,

        conflicts

    )

    # Update in-memory and persistent claim status.

    for result in verified_claims:

        result_id = result.get("id") or result.get("claim_id")

        original = next(

            (

                item

                for item in claims

                if item.get("id") == result_id

            ),

            None

        )

        if original:

            verification = result.get("verification", {})
            verification_status = verification.get("status")

            # Preserve the latest human decision when automated verification
            # runs again. Keep the automated assessment in "verification".
            latest_decision = get_latest_decision_map().get(result_id)
            decision_status = {
                "ACCEPT_CLAIM": "VERIFIED",
                "REJECT_CLAIM": "REJECTED",
                "KEEP_UNRESOLVED": "NEEDS_REVIEW",
            }

            if latest_decision:
                final_status = decision_status.get(
                    latest_decision.get("decision"),
                    verification_status or result.get("status", "UNVERIFIED")
                )
            else:
                final_status = verification_status or result.get(
                    "status", "UNVERIFIED"
                )

            original["status"] = final_status
            original["verification"] = verification

            # Reflect the final human-aware status in the response too.
            result["status"] = final_status
            persist_claim(original)

    persist_verification_results(

        verified_claims

    )

    return conflicts, verified_claims

@app.post("/api/verification/run")

def run_verification():

    conflicts, verified_claims = build_verification_results(

        refresh_evidence=True

    )

    add_audit_event(

        "VERIFICATION_RUN",

        details={

            "claims_checked": len(claims),

            "conflicts_found": len(conflicts),

            "verified_claims": sum(

                1

                for result in verified_claims

                if result.get("verification", {}).get("status")

                == "VERIFIED"

            )

        }

    )

    return {

        "success": True,

        "claims_checked": len(claims),

        "conflicts_found": len(conflicts),

        "verified_claims": verified_claims

    }

@app.get("/api/verification")

def get_verification_results():

    conflicts = detect_conflicts(claims)

    verified_claims = verify_claims(claims, conflicts)
    latest_decisions = get_latest_decision_map()
    decision_status = {
        "ACCEPT_CLAIM": "VERIFIED",
        "REJECT_CLAIM": "REJECTED",
        "KEEP_UNRESOLVED": "NEEDS_REVIEW",
    }

    for result in verified_claims:
        claim_id = result.get("id") or result.get("claim_id")
        decision = latest_decisions.get(claim_id)
        if decision:
            result["status"] = decision_status.get(
                decision.get("decision"),
                result.get("status", "UNVERIFIED")
            )

    return {
        "success": True,
        "count": len(verified_claims),
        "claims": verified_claims
    }

# ============================================================

# HUMAN VERIFICATION DECISION

# ============================================================

@app.post("/api/verification/decision")

def record_verification_decision(decision: VerificationDecision):

    claim = next(

        (item for item in claims if item.get("id") == decision.claim_id),

        None

    )

    if not claim:

        raise HTTPException(

            status_code=404,

            detail="Claim not found."

        )

    allowed_decisions = [

        "ACCEPT_CLAIM",

        "REJECT_CLAIM",

        "KEEP_UNRESOLVED"

    ]

    if decision.decision not in allowed_decisions:

        raise HTTPException(

            status_code=400,

            detail=f"Invalid decision. Use one of: {allowed_decisions}"

        )

    if decision.decision == "ACCEPT_CLAIM":

        claim["status"] = "VERIFIED"

    elif decision.decision == "REJECT_CLAIM":

        claim["status"] = "REJECTED"

    else:

        claim["status"] = "NEEDS_REVIEW"

    persist_claim(claim)

    record = {

        "id": str(uuid.uuid4()),

        "claim_id": decision.claim_id,

        "decision": decision.decision,

        "reason": decision.reason,

        "reviewer": decision.reviewer,

        "timestamp": now()

    }

    verification_decisions.append(record)

    connection = get_connection()

    connection.execute("""

        INSERT INTO verification_decisions

        (id, claim_id, decision, reason, reviewer, timestamp)

        VALUES (?, ?, ?, ?, ?, ?)

    """, (

        record["id"],

        record["claim_id"],

        record["decision"],

        record["reason"],

        record["reviewer"],

        record["timestamp"]

    ))

    connection.commit()

    connection.close()

    add_audit_event(

        "HUMAN_VERIFICATION_DECISION",

        claim.get("document_id"),

        {

            "claim_id": decision.claim_id,

            "decision": decision.decision,

            "reason": decision.reason,

            "reviewer": decision.reviewer

        }

    )

    return {

        "success": True,

        "message": "Verification decision recorded.",

        "decision": record,

        "updated_claim": claim

    }

@app.get("/api/verification/decisions")

def get_verification_decisions():

    return {

        "success": True,

        "count": len(verification_decisions),

        "decisions": verification_decisions

    }

# ============================================================

# EVIDENCE

# ============================================================

@app.post("/api/evidence/retrieve/{claim_id}")

def retrieve_claim_evidence(claim_id: str):

    claim = next(

        (item for item in claims if item.get("id") == claim_id),

        None

    )

    if not claim:

        raise HTTPException(

            status_code=404,

            detail="Claim not found."

        )

    result = retrieve_evidence_for_claim(claim, documents)

    if result.get("evidence"):

        claim["evidence"] = result["evidence"]

        persist_claim(claim)

    add_audit_event(

        "EVIDENCE_RETRIEVED",

        claim.get("document_id"),

        {

            "claim_id": claim_id,

            "evidence_count": result.get("evidence_count", 0)

        }

    )

    return {

        "success": True,

        **result

    }

# ============================================================

# ENTITIES

# ============================================================

@app.get("/api/entities")

def get_entities():

    resolved_entities = resolve_entities(documents)

    connection = get_connection()

    cursor = connection.cursor()

    # --------------------------------------------------------

    # Preserve existing entity IDs for the same canonical name.

    # This makes entity IDs stable across refreshes/restarts.

    # --------------------------------------------------------

    existing_rows = cursor.execute("""

        SELECT id, canonical_name

        FROM entities

    """).fetchall()

    existing_ids = {

        row["canonical_name"]: row["id"]

        for row in existing_rows

    }

    # Rebuild the current entity snapshot.

    cursor.execute("DELETE FROM entities")

    for entity in resolved_entities:

        canonical_name = entity.get(

            "canonical_name",

            ""

        )

        entity_id = existing_ids.get(

            canonical_name

        ) or str(uuid.uuid4())

        # Put the stable ID back into the response object.

        entity["id"] = entity_id

        cursor.execute("""

            INSERT INTO entities

            (

                id,

                canonical_name,

                variants,

                mentions

            )

            VALUES (?, ?, ?, ?)

        """, (

            entity_id,

            canonical_name,

            safe_json(

                entity.get("variants", [])

            ),

            entity.get("mentions", 0)

        ))

    connection.commit()

    connection.close()

    return {

        "success": True,

        "count": len(resolved_entities),

        "entities": resolved_entities

    }

def get_latest_decision_map():

    """Return the latest human decision for each claim."""

    latest = {}

    for decision in verification_decisions:

        claim_id = decision.get("claim_id")

        if claim_id:

            latest[claim_id] = decision

    return latest

def normalize_report_status(claim, claim_conflicts, decision=None):

    """Map automated and human verification states to report states."""

    if decision:

        if decision.get("decision") == "ACCEPT_CLAIM":

            return "VERIFIED"

        if decision.get("decision") == "REJECT_CLAIM":

            return "REJECTED"

        return "NEEDS_REVIEW"

    # A detected cross-document conflict must remain reviewable until a

    # human resolves it, even if one side of the automated check is

    # otherwise supported.

    if claim_conflicts:

        return "NEEDS_REVIEW"

    raw_status = str(claim.get("status", "UNVERIFIED")).upper()

    if raw_status in {"VERIFIED", "SUPPORTED", "ACCEPTED"}:

        return "VERIFIED"

    if raw_status in {"REJECTED"}:

        return "REJECTED"

    if raw_status in {"NEEDS_REVIEW", "CONFLICTING", "AMBIGUOUS"}:

        return "NEEDS_REVIEW"

    return "UNRESOLVED"

# ============================================================

# REPORT

# ============================================================

@app.post("/api/report/generate")

def generate_consolidated_report():

    global generated_report

    if not claims:

        raise HTTPException(

            status_code=400,

            detail="No claims available. Extract claims before generating a report."

        )

    # Refresh automated verification before building the report.

    conflicts, verified_claims = build_verification_results(

        refresh_evidence=True

    )

    decision_map = get_latest_decision_map()

    conflict_claim_ids = {}

    for conflict in conflicts:

        claim_a = conflict.get("claim_a", {})

        claim_b = conflict.get("claim_b", {})

        if claim_a.get("id"):

            conflict_claim_ids.setdefault(

                claim_a["id"], []

            ).append(conflict)

        if claim_b.get("id"):

            conflict_claim_ids.setdefault(

                claim_b["id"], []

            ).append(conflict)

    report_claims = []

    verified_count = 0

    rejected_count = 0

    review_count = 0

    unresolved_count = 0

    for claim in claims:

        claim_id = claim.get("id")

        document = documents.get(claim.get("document_id"), {})

        decision = decision_map.get(claim_id)

        claim_conflicts = conflict_claim_ids.get(claim_id, [])

        status = normalize_report_status(

            claim,

            claim_conflicts,

            decision

        )

        if status == "VERIFIED":

            verified_count += 1

        elif status == "REJECTED":

            rejected_count += 1

        elif status == "NEEDS_REVIEW":

            review_count += 1

        else:

            unresolved_count += 1

        evidence = claim.get("evidence", [])

        if not evidence:

            try:

                evidence_result = retrieve_evidence_for_claim(

                    claim, documents

                )

                evidence = evidence_result.get("evidence", [])

            except Exception:

                evidence = []

        provenance = {

            "document_id": claim.get("document_id"),

            "filename": claim.get(

                "source",

                document.get("filename")

            ),

            "page": claim.get("page"),

            "document_hash": document.get("sha256")

        }

        report_claims.append({

            "claim_id": claim_id,

            "claim": claim.get("text", ""),

            "status": status,

            "source": {

                "document_id": claim.get("document_id"),

                "filename": claim.get(

                    "source",

                    document.get("filename")

                ),

                "page": claim.get("page")

            },

            "evidence": evidence,

            "conflicts": claim_conflicts,

            "human_decision": decision,

            "provenance": provenance

        })

    generated_report = {

        "report_id": str(uuid.uuid4()),

        "generated_at": now(),

        "system": "veriCore",

        "title": "Consolidated Verified Document",

        "summary": {

            "documents": len(documents),

            "claims": len(claims),

            "verified_claims": verified_count,

            "rejected_claims": rejected_count,

            "needs_review": review_count,

            "unresolved_claims": unresolved_count,

            "conflicts": len(conflicts)

        },

        "documents": [

            {

                "id": document["id"],

                "filename": document["filename"],

                "file_type": document["file_type"],

                "sha256": document["sha256"],

                "uploaded_at": document["uploaded_at"]

            }

            for document in documents.values()

        ],

        "claims": report_claims,

        "verification_decisions": verification_decisions,

        "audit_reference": {

            "audit_events": len(audit_trail)

        }

    }

    connection = get_connection()

    connection.execute("""

        INSERT INTO reports

        (id, title, generated_at, report_data)

        VALUES (?, ?, ?, ?)

    """, (

        generated_report["report_id"],

        generated_report["title"],

        generated_report["generated_at"],

        safe_json(generated_report)

    ))

    connection.commit()

    connection.close()

    add_audit_event(

        "CONSOLIDATED_REPORT_GENERATED",

        details={

            "report_id": generated_report["report_id"],

            "documents": len(documents),

            "claims": len(claims),

            "conflicts": len(conflicts)

        }

    )

    return {

        "success": True,

        "message": "Consolidated verified report generated.",

        "report": generated_report

    }

@app.get("/api/report")

def get_consolidated_report():

    if generated_report is None:

        raise HTTPException(

            status_code=404,

            detail="No report has been generated yet."

        )

    return {

        "success": True,

        "report": generated_report

    }

# ============================================================

# AUDIT

# ============================================================

@app.get("/api/audit")

def get_audit_trail():

    return {

        "success": True,

        "count": len(audit_trail),

        "events": audit_trail

    }

# ============================================================

# SYSTEM STATUS

# ============================================================

@app.get("/api/status")

def system_status():

    return {

        "system": "veriCore",

        "status": "ready",

        "database": str(DB_PATH),

        "statistics": {

            "documents": len(documents),

            "claims": len(claims),

            "audit_events": len(audit_trail),

            "verification_decisions": len(verification_decisions)

        },

        "modules": {

            "document_ingestion": True,

            "text_extraction": True,

            "provenance": True,

            "hashing": True,

            "claim_extraction": True,

            "entity_resolution": True,

            "conflict_detection": True,

            "verification": True,

            "report_generation": True,

            "persistent_database": True

        }

    }

# ============================================================

# COMPARISON

# ============================================================

@app.post("/api/claims/compare")

def compare_all_claims():

    if len(claims) < 2:

        return {

            "success": True,

            "count": 0,

            "comparisons": [],

            "message": "At least two claims are required for comparison."

        }

    comparisons = compare_claim_set(claims)

    return {

        "success": True,

        "count": len(comparisons),

        "comparisons": comparisons

    }

@app.post("/api/claims/compare/{claim_a_id}/{claim_b_id}")

def compare_two_claims(claim_a_id: str, claim_b_id: str):

    claim_a = next(

        (claim for claim in claims if claim.get("id") == claim_a_id),

        None

    )

    claim_b = next(

        (claim for claim in claims if claim.get("id") == claim_b_id),

        None

    )

    if not claim_a:

        raise HTTPException(

            status_code=404,

            detail="First claim not found."

        )

    if not claim_b:

        raise HTTPException(

            status_code=404,

            detail="Second claim not found."

        )

    result = compare_claims(claim_a, claim_b)

    return {

        "success": True,

        "claim_a": claim_a,

        "claim_b": claim_b,

        "comparison": result

    }

# ============================================================

# RUN DIRECTLY

# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(

        "app:app",

        host="127.0.0.1",

        port=8000,

        reload=True

    )
