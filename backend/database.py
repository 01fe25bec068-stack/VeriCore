import sqlite3
from pathlib import Path


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "vericore.db"


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


# ============================================================
# INITIALIZE DATABASE
# ============================================================

def initialize_database():

    connection = get_connection()
    cursor = connection.cursor()

    # --------------------------------------------------------
    # DOCUMENTS
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            file_type TEXT,
            size INTEGER,
            sha256 TEXT,
            uploaded_at TEXT,
            status TEXT
        )
    """)

    # --------------------------------------------------------
    # DOCUMENT PAGES
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_pages (
            document_id TEXT NOT NULL,
            page INTEGER NOT NULL,
            text TEXT,

            PRIMARY KEY (document_id, page),

            FOREIGN KEY (document_id)
            REFERENCES documents(id)
            ON DELETE CASCADE
        )
    """)

    # --------------------------------------------------------
    # CLAIMS
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS claims (
            id TEXT PRIMARY KEY,
            document_id TEXT,
            source TEXT,
            page INTEGER,
            text TEXT,
            status TEXT,
            evidence_source TEXT,
            evidence_page INTEGER,
            evidence_text TEXT,

            FOREIGN KEY (document_id)
            REFERENCES documents(id)
            ON DELETE CASCADE
        )
    """)

    # --------------------------------------------------------
    # ENTITIES
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entities (
            id TEXT PRIMARY KEY,
            canonical_name TEXT NOT NULL,
            variants TEXT,
            mentions INTEGER DEFAULT 0
        )
    """)

    # --------------------------------------------------------
    # CONFLICTS
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conflicts (
            id TEXT PRIMARY KEY,
            claim_a_id TEXT,
            claim_b_id TEXT,
            status TEXT,
            reason TEXT,
            created_at TEXT,

            FOREIGN KEY (claim_a_id)
            REFERENCES claims(id)
            ON DELETE CASCADE,

            FOREIGN KEY (claim_b_id)
            REFERENCES claims(id)
            ON DELETE CASCADE
        )
    """)

    # --------------------------------------------------------
    # VERIFICATION RESULTS
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS verification_results (
            id TEXT PRIMARY KEY,
            claim_id TEXT,
            status TEXT,
            confidence REAL,
            reason TEXT,
            conflict_count INTEGER DEFAULT 0,
            verified_at TEXT,

            FOREIGN KEY (claim_id)
            REFERENCES claims(id)
            ON DELETE CASCADE
        )
    """)

    # --------------------------------------------------------
    # HUMAN VERIFICATION DECISIONS
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS verification_decisions (
            id TEXT PRIMARY KEY,
            claim_id TEXT,
            decision TEXT,
            reason TEXT,
            reviewer TEXT,
            timestamp TEXT,

            FOREIGN KEY (claim_id)
            REFERENCES claims(id)
            ON DELETE CASCADE
        )
    """)

    # --------------------------------------------------------
    # AUDIT TRAIL
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_trail (
            id TEXT PRIMARY KEY,
            timestamp TEXT,
            action TEXT,
            document_id TEXT,
            details TEXT
        )
    """)

    # --------------------------------------------------------
    # REPORTS
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id TEXT PRIMARY KEY,
            title TEXT,
            generated_at TEXT,
            report_data TEXT
        )
    """)

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    connection.commit()
    connection.close()


# ============================================================
# DATABASE STATUS
# ============================================================

def database_status():

    connection = get_connection()
    cursor = connection.cursor()

    tables = [
        "documents",
        "document_pages",
        "claims",
        "entities",
        "conflicts",
        "verification_results",
        "verification_decisions",
        "audit_trail",
        "reports"
    ]

    result = {}

    for table in tables:

        cursor.execute(
            f"SELECT COUNT(*) FROM {table}"
        )

        result[table] = cursor.fetchone()[0]

    connection.close()

    return result


# ============================================================
# TEST DATABASE
# ============================================================

if __name__ == "__main__":

    initialize_database()

    print("========================================")
    print("veriCore database initialized.")
    print("========================================")

    print(f"\nDatabase location:")
    print(DB_PATH)

    print("\nCurrent records:")

    status = database_status()

    for table, count in status.items():
        print(f"{table}: {count}")

    print("\nDatabase setup complete.")