import { useEffect, useRef, useState } from "react";
import "./App.css";

type Page =
  | "dashboard"
  | "documents"
  | "claims"
  | "conflicts"
  | "evidence"
  | "gaps"
  | "timeline"
  | "report"
  | "verification"
  | "audit"
  | "settings";

type DocumentPage = {
  page: number;
  text: string;
};

type DocumentItem = {
  id: string;
  name: string;
  type: string;
  status: string;
  pages: number;
  uploadedAt?: string;
  pageTexts?: DocumentPage[];
};

type ClaimEvidence = {
  source?: string;
  page?: number;
  text?: string;
};

type ClaimItem = {
  id: string;
  text: string;
  status: string;
  source: string;
  page: number;
  evidence?: ClaimEvidence;
};

type Conflict = {
  id: string;
  claimId1: string;
  claimId2: string;
  title: string;
  type: string;
  source1: string;
  value1: string;
  page1: string;
  source2: string;
  value2: string;
  page2: string;
  description: string;
};

function App() {
  const [page, setPage] = useState<Page>("dashboard");

  const [documents, setDocuments] =
    useState<DocumentItem[]>([]);

  const [claims, setClaims] =
    useState<ClaimItem[]>([]);

  const [liveConflicts, setLiveConflicts] =
    useState<Conflict[]>([]);

  const [isProcessing, setIsProcessing] = useState(false);

  const [showNewProject, setShowNewProject] = useState(false);

  const [projectName, setProjectName] = useState("");
  const [projectDescription, setProjectDescription] =
    useState("");

  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);

  const [toast, setToast] = useState("");

  const [selectedConflict, setSelectedConflict] =
    useState<Conflict | null>(null);

  const [decision, setDecision] = useState("");

  const [usedEvidence, setUsedEvidence] =
    useState<string[]>([]);

  const [auditEvents, setAuditEvents] = useState([
    "Verification workspace created",
    "4 source documents processed",
    "44 claims extracted",
    "3 conflicts detected",
  ]);

  const newProjectFileInput =
    useRef<HTMLInputElement | null>(null);

  const documentFileInput =
    useRef<HTMLInputElement | null>(null);

  function notify(message: string) {
    setToast(message);

    setTimeout(() => {
      setToast("");
    }, 2500);
  }

  function handleProjectFiles(
    event: React.ChangeEvent<HTMLInputElement>
  ) {
    const files = Array.from(event.target.files || []);

    if (!files.length) return;

    setSelectedFiles(files);

    notify(
      `${files.length} source ${
        files.length === 1 ? "file" : "files"
      } selected`
    );
  }

  async function loadDocuments() {
    try {
      const response = await fetch(
        "https://vericore.onrender.com/api/documents"
      );

      if (!response.ok) {
        throw new Error("Failed to load documents");
      }

      const data = await response.json();

      const backendDocuments: DocumentItem[] =
        (data.documents || []).map((doc: any) => ({
          id: String(doc.id),
          name: doc.filename,
          type: doc.file_type,
          status:
            doc.status?.toLowerCase() === "processed"
              ? "Processed"
              : doc.status || "Unknown",
          pages: Array.isArray(doc.pages)
            ? doc.pages.length
            : Number(doc.pages || 0),
          uploadedAt: doc.uploaded_at || "",
          pageTexts: Array.isArray(doc.pages)
            ? doc.pages.map((page: any) => ({
                page: Number(page.page || 1),
                text: String(page.text || ""),
              }))
            : [],
        }));

      setDocuments(backendDocuments);
    } catch (error) {
      console.error("Failed to load documents:", error);
      notify("Could not connect to veriCore backend");
    }
  }

  async function loadClaims() {
    try {
      const response = await fetch(
        "https://vericore.onrender.com/api/claims"
      );

      if (!response.ok) {
        throw new Error("Failed to load claims");
      }

      const data = await response.json();

      const backendClaims: ClaimItem[] =
        (data.claims || []).map((claim: any) => ({
          id: String(claim.id),
          text: claim.text || "",
          status: claim.status || "UNVERIFIED",
          source: claim.source || "Unknown source",
          page: Number(claim.page || 1),
          evidence:
            claim.evidence &&
            typeof claim.evidence === "object" &&
            !Array.isArray(claim.evidence)
              ? {
                  source: claim.evidence.source,
                  page: Number(claim.evidence.page || claim.page || 1),
                  text: String(claim.evidence.text || ""),
                }
              : undefined,
        }));

      setClaims(backendClaims);
    } catch (error) {
      console.error("Failed to load claims:", error);
      notify("Could not load claims from backend");
    }
  }

  async function loadConflicts() {
    try {
      const [conflictsResponse, decisionsResponse] =
        await Promise.all([
          fetch("https://vericore.onrender.com/api/conflicts"),
          fetch("https://vericore.onrender.com/api/verification/decisions"),
        ]);

      if (!conflictsResponse.ok) {
        throw new Error("Failed to load conflicts");
      }

      const conflictData = await conflictsResponse.json();
      const decisionData = decisionsResponse.ok
        ? await decisionsResponse.json()
        : { decisions: [] };

      const resolvedIds = new Set<string>(
        (decisionData.decisions || [])
          .filter(
            (item: any) =>
              item.decision === "ACCEPT_CLAIM" ||
              item.decision === "REJECT_CLAIM"
          )
          .map((item: any) => String(item.claim_id))
      );

      const backendConflicts: Conflict[] =
        (conflictData.conflicts || [])
          .filter(
            (item: any) =>
              item.claim_a?.id && item.claim_b?.id
          )
          .map((item: any) => {
            const c = item.conflict || {};
            const property =
              c.property?.[0] || "documented fact";
            const title =
              c.status === "POTENTIAL_VIOLATION"
                ? `${String(property).replace(/^./, (char: string) => char.toUpperCase())} limit violation`
                : `${String(property).replace(/^./, (char: string) => char.toUpperCase())} conflict`;

            return {
              id: String(item.id),
              claimId1: String(item.claim_a.id),
              claimId2: String(item.claim_b.id),
              title,
              type:
                c.status === "POTENTIAL_VIOLATION"
                  ? "Potential limit violation"
                  : "Direct value conflict",
              source1: item.claim_a.source || "Source 1",
              value1: item.claim_a.text || "",
              page1: `Page ${item.claim_a.page || 1}`,
              source2: item.claim_b.source || "Source 2",
              value2: item.claim_b.text || "",
              page2: `Page ${item.claim_b.page || 1}`,
              description:
                item.reason ||
                c.reason ||
                "Conflicting information detected.",
            };
          })
          .filter(
            (item: Conflict) =>
              !resolvedIds.has(item.claimId1) &&
              !resolvedIds.has(item.claimId2)
          );

      setLiveConflicts(backendConflicts);
    } catch (error) {
      console.error("Failed to load conflicts:", error);
      notify("Could not load conflicts from backend");
    }
  }

  useEffect(() => {
    loadDocuments();
    loadClaims();
    loadConflicts();
  }, []);

  async function handleDocumentUpload(
    event: React.ChangeEvent<HTMLInputElement>
  ) {
    const files = Array.from(event.target.files || []);

    if (!files.length) {
      return;
    }

    const formData = new FormData();

    files.forEach((file) => {
      formData.append("files", file);
    });

    try {
      notify("Uploading documents...");

      const response = await fetch(
        "https://vericore.onrender.com/api/documents/upload",
        {
          method: "POST",
          body: formData,
        }
      );

      const data = await response.json();

      if (!response.ok || data.success !== true) {
        throw new Error(
          data.detail ||
            data.message ||
            "Upload failed"
        );
      }

      // Immediately show the documents returned by the upload
      // endpoint, including duplicate-document responses.
      const uploadedDocuments: DocumentItem[] =
        (data.documents || []).map((doc: any) => ({
          id: String(doc.id),
          name: doc.filename,
          type: doc.file_type,
          status:
            String(doc.status || "").toLowerCase() ===
            "processed"
              ? "Processed"
              : String(doc.status || "").toLowerCase() ===
                "already_exists"
              ? "Already exists"
              : doc.status || "Unknown",
          pages: Number(doc.pages || 0),
        }));

      setDocuments((current) => {
        const merged = [...current];

        for (const uploaded of uploadedDocuments) {
          const index = merged.findIndex(
            (item) => item.id === uploaded.id
          );

          if (index >= 0) {
            merged[index] = uploaded;
          } else {
            merged.push(uploaded);
          }
        }

        return merged;
      });

      // Refresh from the backend as the final source of truth.
      await loadDocuments();

      setAuditEvents((current) => [
        `${uploadedDocuments.length} source ${
          uploadedDocuments.length === 1
            ? "document"
            : "documents"
        } uploaded`,
        ...current,
      ]);

      const duplicateCount = uploadedDocuments.filter(
        (doc) => doc.status === "Already exists"
      ).length;

      if (
        duplicateCount === uploadedDocuments.length &&
        duplicateCount > 0
      ) {
        notify(
          "Document already exists — no duplicate created"
        );
      } else {
        notify(
          `${uploadedDocuments.length} document${
            uploadedDocuments.length === 1 ? "" : "s"
          } uploaded successfully`
        );
      }
    } catch (error) {
      console.error("Upload failed:", error);
      notify(
        `Document upload failed: ${
          error instanceof Error
            ? error.message
            : "unknown error"
        }`
      );
    } finally {
      event.target.value = "";
    }
  }

  async function processDocuments() {
    if (!documents.length) {
      notify("Upload documents first");
      return;
    }

    setIsProcessing(true);
    notify("Processing documents...");

    try {
      let extractedCount = 0;

      for (const document of documents) {
        const response = await fetch(
          `https://vericore.onrender.com/api/claims/extract/${document.id}`,
          { method: "POST" }
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(
            data.detail || `Failed to process ${document.name}`
          );
        }

        extractedCount += Number(
          data.claims_extracted || 0
        );
      }

      // Refresh the claims shown in the UI.
      await loadClaims();

      // Run conflict detection after claims are extracted.
      const conflictResponse = await fetch(
        "https://vericore.onrender.com/api/conflicts/detect",
        { method: "POST" }
      );

      if (!conflictResponse.ok) {
        throw new Error("Conflict detection failed");
      }

      await loadConflicts();

      setAuditEvents((current) => [
        `Document processing completed: ${extractedCount} claims extracted`,
        ...current,
      ]);

      notify(
        `Processing complete — ${extractedCount} claims extracted`
      );
    } catch (error) {
      console.error("Document processing failed:", error);
      notify("Document processing failed");
    } finally {
      setIsProcessing(false);
    }
  }

  function createProject() {
    if (!projectName.trim()) {
      notify("Please enter a project name");
      return;
    }

    setShowNewProject(false);

    setAuditEvents((current) => [
      `Project "${projectName}" created`,
      ...current,
    ]);

    notify("Verification project created");

    setProjectName("");
    setProjectDescription("");
    setSelectedFiles([]);

    setPage("dashboard");
  }

  async function recordDecision(
    selectedDecision: string,
    claimId: string
  ) {
    if (!selectedDecision || !claimId) {
      notify("Select a decision first");
      return;
    }

    const apiDecision =
      selectedDecision === "Keep Unresolved"
        ? "KEEP_UNRESOLVED"
        : "ACCEPT_CLAIM";

    try {
      const response = await fetch(
        "https://vericore.onrender.com/api/verification/decision",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            claim_id: claimId,
            decision: apiDecision,
            reason:
              selectedDecision === "Keep Unresolved"
                ? "Conflict intentionally retained for human review."
                : `Human reviewer selected ${selectedDecision}.`,
            reviewer: "human-reviewer",
          }),
        }
      );

      const data = await response.json();

      if (!response.ok || data.success !== true) {
        throw new Error(
          data.detail ||
            data.message ||
            "Verification decision failed"
        );
      }

      await loadClaims();
      await loadConflicts();

      setAuditEvents((current) => [
        `Decision recorded: ${selectedDecision}`,
        ...current,
      ]);

      notify("Verification decision recorded");
      setSelectedConflict(null);
      setDecision("");
    } catch (error) {
      console.error("Verification decision failed:", error);
      notify(
        `Decision failed: ${
          error instanceof Error ? error.message : "unknown error"
        }`
      );
    }
  }

  function useEvidence(
    source: string,
    value: string
  ) {
    const item = `${source}: ${value}`;

    setUsedEvidence((current) => {
      if (current.includes(item)) {
        return current;
      }

      return [...current, item];
    });

    setAuditEvents((current) => [
      `Evidence selected from ${source}`,
      ...current,
    ]);

    notify("Evidence added to verification");
  }

  function renderPage() {
    switch (page) {
      case "dashboard":
        return (
          <Dashboard
            documentsCount={documents.length}
            claimsCount={claims.length}
            supportedCount={claims.filter((claim) =>
              claim.status.toUpperCase() === "VERIFIED"
            ).length}
            conflictCount={liveConflicts.length}
            conflicts={liveConflicts}
            onOpenReport={() => setPage("report")}
            onOpenConflict={(conflict) =>
              setSelectedConflict(conflict)
            }
          />
        );

      case "documents":
        return (
          <Documents
            documents={documents}
            inputRef={documentFileInput}
            onUpload={handleDocumentUpload}
            onProcess={processDocuments}
            isProcessing={isProcessing}
          />
        );

      case "claims":
        return <Claims claims={claims} />;

      case "conflicts":
        return (
          <Conflicts
            conflicts={liveConflicts}
            onOpen={(conflict) =>
              setSelectedConflict(conflict)
            }
          />
        );

      case "evidence":
        return (
          <Evidence
            claims={claims}
            usedEvidence={usedEvidence}
            onUseEvidence={useEvidence}
          />
        );

      case "gaps":
        return (
          <EvidenceGaps
            conflicts={liveConflicts}
            claims={claims}
          />
        );

      case "timeline":
        return (
          <Timeline
            documents={documents}
            claims={claims}
          />
        );

      case "report":
        return <Report />;

      case "verification":
        return (
          <Verification
            conflicts={liveConflicts}
            usedEvidence={usedEvidence}
            onUseEvidence={useEvidence}
            onRecordDecision={recordDecision}
          />
        );

      case "audit":
        return <AuditTrail events={auditEvents} />;

      case "settings":
        return <Settings />;

      default:
        return (
          <Dashboard
            documentsCount={documents.length}
            claimsCount={claims.length}
            supportedCount={claims.filter((claim) =>
              claim.status.toUpperCase() === "VERIFIED"
            ).length}
            conflictCount={liveConflicts.length}
            conflicts={liveConflicts}
            onOpenReport={() => setPage("report")}
            onOpenConflict={(conflict) =>
              setSelectedConflict(conflict)
            }
          />
        );
    }
  }

  return (
    <div className="app">

      <Sidebar
        page={page}
        setPage={setPage}
        conflictCount={liveConflicts.length}
      />

      <main className="main">

        <Topbar
          onNewProject={() =>
            setShowNewProject(true)
          }
        />

        <div className="page-content">
          {renderPage()}
        </div>

      </main>

      {showNewProject && (
        <div className="modal-backdrop">

          <div className="new-project-modal">

            <button
              className="modal-close"
              onClick={() =>
                setShowNewProject(false)
              }
            >
              ×
            </button>

            <div className="eyebrow">
              NEW WORKSPACE
            </div>

            <h2>
              Create verification project
            </h2>

            <p className="modal-subtitle">
              Start a new multi-source verification
              workspace.
            </p>

            <label>
              Project name
            </label>

            <input
              className="form-input"
              value={projectName}
              onChange={(e) =>
                setProjectName(e.target.value)
              }
              placeholder="Example: MX-204"
            />

            <label>
              Description
            </label>

            <textarea
              className="form-textarea"
              value={projectDescription}
              onChange={(e) =>
                setProjectDescription(
                  e.target.value
                )
              }
              placeholder="What are you trying to verify?"
            />

            <label
              className="project-upload-box"
              onClick={() =>
                newProjectFileInput.current?.click()
              }
            >

              <input
                ref={newProjectFileInput}
                type="file"
                multiple
                accept=".pdf,.txt,.doc,.docx,.png,.jpg,.jpeg"
                onChange={handleProjectFiles}
              />

              <div className="upload-icon">
                ↑
              </div>

              <strong>
                Upload source documents
              </strong>

              <span>
                PDF, scanned documents, reports and
                text sources
              </span>

              <small>
                Click here to choose files
              </small>

              {selectedFiles.length > 0 && (
                <div className="selected-files">
                  {selectedFiles.map(
                    (file) => (
                      <div
                        className="selected-file"
                        key={file.name}
                      >
                        ✓ {file.name}
                      </div>
                    )
                  )}
                </div>
              )}

            </label>

            <div className="modal-actions">

              <button
                className="btn secondary"
                onClick={() =>
                  setShowNewProject(false)
                }
              >
                Cancel
              </button>

              <button
                className="btn primary"
                onClick={createProject}
              >
                Create Project
              </button>

            </div>

          </div>

        </div>
      )}

      {selectedConflict && (
        <ConflictModal
          conflict={selectedConflict}
          decision={decision}
          setDecision={setDecision}
          onClose={() =>
            setSelectedConflict(null)
          }
          onUseEvidence={useEvidence}
          onRecordDecision={(selectedDecision, claimId) => {
            recordDecision(selectedDecision, claimId);
          }}
        />
      )}

      {toast && (
        <div className="toast">
          <span>✓</span>
          {toast}
        </div>
      )}

    </div>
  );
}

/* =========================================
   SIDEBAR
========================================= */

function Sidebar({
  page,
  setPage,
  conflictCount,
}: {
  page: Page;
  setPage: (page: Page) => void;
  conflictCount: number;
}) {
  const items: {
    id: Page;
    label: string;
    icon: string;
  }[] = [
    {
      id: "dashboard",
      label: "Dashboard",
      icon: "⌂",
    },
    {
      id: "documents",
      label: "Documents",
      icon: "▣",
    },
    {
      id: "claims",
      label: "Claims",
      icon: "◇",
    },
    {
      id: "conflicts",
      label: "Conflicts",
      icon: "△",
    },
    {
      id: "evidence",
      label: "Evidence",
      icon: "→",
    },
    {
      id: "gaps",
      label: "Evidence Gaps",
      icon: "○",
    },
    {
      id: "timeline",
      label: "Timeline",
      icon: "◷",
    },
    {
      id: "report",
      label: "Report",
      icon: "▤",
    },
    {
      id: "verification",
      label: "Verification",
      icon: "✓",
    },
    {
      id: "audit",
      label: "Audit Trail",
      icon: "≡",
    },
  ];

  return (
    <aside className="sidebar">

      <div className="brand">

        <div className="brand-mark">
          V
        </div>

        <div>
          <div className="brand-name">
            veriCore
          </div>

          <div className="brand-subtitle">
            VERIFICATION ENGINE
          </div>
        </div>

      </div>

      <div className="workspace-label">
        WORKSPACE
      </div>

      <div className="project-card">
        <div className="status-dot" />

        <div>
          <strong>MX-204</strong>
          <span>Active project</span>
        </div>

        <span className="chevron">
          ˅
        </span>
      </div>

      <nav className="nav">

        {items.map((item) => (
          <button
            key={item.id}
            className={`nav-item ${
              page === item.id
                ? "active"
                : ""
            }`}
            onClick={() =>
              setPage(item.id)
            }
          >

            <span className="nav-icon">
              {item.icon}
            </span>

            <span>
              {item.label}
            </span>

            {item.id === "conflicts" &&
              conflictCount > 0 && (
                <span className="nav-badge">
                  {conflictCount}
                </span>
              )}

          </button>
        ))}

      </nav>

      <div className="sidebar-bottom">

        <div className="system-status">
          <span />
          System ready
        </div>

        <button
          className="settings-link"
          onClick={() =>
            setPage("settings")
          }
        >
          ⚙ Settings
        </button>

      </div>

    </aside>
  );
}

/* =========================================
   TOPBAR
========================================= */

function Topbar({
  onNewProject,
}: {
  onNewProject: () => void;
}) {
  return (
    <header className="topbar">

      <div className="breadcrumbs">
        WORKSPACE
        <span>/</span>
        <strong>VERIFICATION</strong>
      </div>

      <div className="top-actions">

        <button className="icon-button">
          ◇
        </button>

        <button
          className="btn primary small"
          onClick={onNewProject}
        >
          + New Project
        </button>

      </div>

    </header>
  );
}

/* =========================================
   DASHBOARD
========================================= */

function Dashboard({
  documentsCount,
  claimsCount,
  supportedCount,
  conflictCount,
  conflicts,
  onOpenReport,
  onOpenConflict,
}: {
  documentsCount: number;
  claimsCount: number;
  supportedCount: number;
  conflictCount: number;
  conflicts: Conflict[];
  onOpenReport: () => void;
  onOpenConflict: (c: Conflict) => void;
}) {
  const supportedPercent = claimsCount
    ? Math.round((supportedCount / claimsCount) * 100)
    : 0;
  return (
    <section>

      <PageHeading
        title="Verification Dashboard"
        description="Monitor source documents, claims, evidence and unresolved verification issues."
      />

      <div className="project-heading">

        <div>
          <div className="eyebrow">
            ACTIVE VERIFICATION PROJECT
          </div>

          <h2>
            MX-204 Technical Verification
          </h2>

          <p>
            Consolidating information from multiple
            technical sources into one verifiable
            document.
          </p>
        </div>

        <div className="processing-status">
          <span />
          Processing complete
        </div>

      </div>

      <div className="stats-grid">

        <StatCard
          label="SOURCE DOCUMENTS"
          value={String(documentsCount).padStart(2, "0")}
          text="Source documents loaded"
        />

        <StatCard
          label="CLAIMS ANALYZED"
          value={String(claimsCount).padStart(2, "0")}
          text="Factual claims extracted"
        />

        <StatCard
          label="SUPPORTED"
          value={String(supportedCount).padStart(2, "0")}
          text="Claims currently verified"
          green
        />

        <StatCard
          label="NEEDS REVIEW"
          value={String(conflictCount).padStart(2, "0")}
          text="Conflicts requiring review"
          warning
        />

      </div>

      <div className="dashboard-grid">

        <div className="panel">

          <div className="panel-header">

            <div>
              <span className="eyebrow">
                VERIFICATION QUEUE
              </span>

              <h3>
                Needs your attention
              </h3>
            </div>

            <span className="count-pill">
              {conflictCount} items
            </span>

          </div>

          {conflicts.length === 0 ? (
            <div className="table-row">
              <strong>No conflicts detected</strong>
              <span>Processing has not produced unresolved conflicts.</span>
            </div>
          ) : (
            conflicts.slice(0, 3).map((conflict) => (
              <ConflictRow
                key={conflict.id}
                conflict={conflict}
                onClick={() => onOpenConflict(conflict)}
              />
            ))
          )}

        </div>

        <div className="panel">

          <div className="panel-header">

            <div>
              <span className="eyebrow">
                EVIDENCE STATUS
              </span>

              <h3>
                Verification overview
              </h3>
            </div>

          </div>

          <div
  className="donut"
  style={{
    background: `conic-gradient(
      #9ae878 0deg ${supportedPercent * 3.6}deg,
      #30434d ${supportedPercent * 3.6}deg 360deg
    )`,
  }}
>
            <div>
              <strong>{supportedPercent}%</strong>
              <span>supported</span>
            </div>
          </div>

          <div className="legend">

            <Legend
              label="Supported"
              value={String(supportedCount)}
              green
            />

            <Legend
              label="Partial"
              value="0"
            />

            <Legend
              label="Conflicting"
              value={String(conflictCount)}
              warning
            />

            <Legend
              label="Unsupported"
              value="0"
            />

          </div>

        </div>

      </div>

      <div className="bottom-grid">

        <div className="panel">

          <div className="panel-header">
            <div>
              <span className="eyebrow">
                PROCESSING ACTIVITY
              </span>

              <h3>
                Project activity
              </h3>
            </div>

            <span className="muted">
              Just now
            </span>
          </div>

          <div className="activity-item">
            <span className="activity-dot green" />
            Source documents processed
            <span>{documentsCount}</span>
          </div>

          <div className="activity-item">
            <span className="activity-dot" />
            Claims extracted
            <span>{claimsCount}</span>
          </div>

          <div className="activity-item">
            <span className="activity-dot warning" />
            Conflicts requiring review
            <span>{conflictCount}</span>
          </div>

        </div>

        <div className="panel report-preview">

          <div className="panel-header">
            <div>
              <span className="eyebrow">
                CONSOLIDATED OUTPUT
              </span>

              <h3>
                Verification report
              </h3>
            </div>

            <button
              className="text-button"
              onClick={onOpenReport}
            >
              Open report →
            </button>
          </div>

          <p>
            A source-traceable consolidated document
            containing verified claims, conflicts,
            evidence and unresolved gaps.
          </p>

          <button
            className="btn secondary"
            onClick={onOpenReport}
          >
            View consolidated report
          </button>

        </div>

      </div>

    </section>
  );
}

/* =========================================
   DOCUMENTS
========================================= */

function Documents({
  documents,
  inputRef,
  onUpload,
  onProcess,
  isProcessing,
}: {
  documents: DocumentItem[];
  inputRef: React.RefObject<HTMLInputElement | null>;
  onUpload: (
    event: React.ChangeEvent<HTMLInputElement>
  ) => void;
  onProcess: () => void;
  isProcessing: boolean;
}) {
  return (
    <section>

      <PageHeading
        title="Documents"
        description="Manage the source material used for verification."
      />

      <div
        className="upload-area"
        onClick={() =>
          inputRef.current?.click()
        }
      >

        <input
          ref={inputRef}
          type="file"
          multiple
          hidden
          accept=".pdf,.txt"
          onChange={onUpload}
        />

        <div className="upload-icon">
          ↑
        </div>

        <h3>
          Upload source documents
        </h3>

        <p>
          Add PDFs, scanned documents, reports or
          text sources.
        </p>

        <button
          className="btn secondary"
          onClick={(event) => {
            event.stopPropagation();
            inputRef.current?.click();
          }}
        >
          Choose files
        </button>

      </div>

      <div style={{ marginTop: "16px", display: "flex", justifyContent: "flex-end" }}>
        <button
          className="btn primary"
          onClick={onProcess}
          disabled={isProcessing || documents.length === 0}
        >
          {isProcessing
            ? "Processing documents..."
            : "Process documents"}
        </button>
      </div>

      <div className="documents-grid">

        {documents.map((doc) => (
          <div
            className="document-card"
            key={doc.id}
          >

            <div className="document-icon">
              {doc.type === "PDF"
                ? "PDF"
                : "DOC"}
            </div>

            <div className="document-info">

              <h3>{doc.name}</h3>

              <p>
                {doc.type} •{" "}
                {doc.pages
                  ? `${doc.pages} pages`
                  : "Not processed yet"}
              </p>

              <span
                className={`status ${
                  doc.status ===
                  "Processed"
                    ? "success"
                    : ""
                }`}
              >
                {doc.status}
              </span>

            </div>

            <button className="more-button">
              ⋯
            </button>

          </div>
        ))}

      </div>

    </section>
  );
}

/* =========================================
   CLAIMS
========================================= */

function Claims({ claims }: { claims: ClaimItem[] }) {
  function displayStatus(status: string) {
    switch (status.toUpperCase()) {
      case "VERIFIED":
        return "Supported";
      case "CONFLICTING":
        return "Conflicting";
      case "NEEDS_REVIEW":
        return "Needs review";
      case "REJECTED":
        return "Rejected";
      default:
        return "Unverified";
    }
  }

  return (
    <section>

      <PageHeading
        title="Claims"
        description="Claims extracted from the available source documents."
      />

      <div className="table-panel">

        <div className="table-head">
          <span>CLAIM</span>
          <span>SOURCE</span>
          <span>STATUS</span>
        </div>

        {claims.length === 0 ? (
          <div className="table-row">
            <strong>No claims available</strong>
            <span>Run document processing first</span>
            <span className="claim-status">Unverified</span>
          </div>
        ) : (
          claims.map((claim) => {
            const label = displayStatus(claim.status);
            const supported = label === "Supported";

            return (
              <div className="table-row" key={claim.id}>
                <strong>{claim.text}</strong>
                <span>
                  {claim.source} · Page {claim.page}
                </span>
                <span
                  className={`claim-status ${
                    supported ? "supported" : "conflicting"
                  }`}
                >
                  {label}
                </span>
              </div>
            );
          })
        )}

      </div>

    </section>
  );
}

/* =========================================
   CONFLICTS
========================================= */

function Conflicts({
  conflicts,
  onOpen,
}: {
  conflicts: Conflict[];
  onOpen: (conflict: Conflict) => void;
}) {
  return (
    <section>

      <PageHeading
        title="Conflicts"
        description="Review differences between sources before creating the verified document."
      />

      <div className="conflict-list">

        {conflicts.length === 0 ? (
          <div className="panel">
            <strong>No conflicts detected</strong>
            <p className="muted">Run document processing to compare the extracted claims.</p>
          </div>
        ) : conflicts.map((conflict) => (
          <div
            className="conflict-card"
            key={conflict.id}
          >

            <div className="conflict-top">

              <div>
                <span className="warning-label">
                  {conflict.type}
                </span>

                <h2>
                  {conflict.title}
                </h2>

                <p>
                  {conflict.description}
                </p>
              </div>

              <button
                className="btn primary"
                onClick={() =>
                  onOpen(conflict)
                }
              >
                Review →
              </button>

            </div>

            <div className="source-comparison">

              <SourceValue
                label={conflict.source1}
                value={conflict.value1}
                page={conflict.page1}
              />

              <div className="versus">
                VS
              </div>

              <SourceValue
                label={conflict.source2}
                value={conflict.value2}
                page={conflict.page2}
              />

            </div>

          </div>
        ))}

      </div>

    </section>
  );
}

/* =========================================
   EVIDENCE
========================================= */

function Evidence({
  claims,
  usedEvidence,
  onUseEvidence,
}: {
  claims: ClaimItem[];
  usedEvidence: string[];
  onUseEvidence: (source: string, value: string) => void;
}) {
  const evidence = claims
    .map((claim) => {
      const source = claim.evidence?.source || claim.source;
      const page = Number(claim.evidence?.page || claim.page || 1);
      const value = String(
        claim.evidence?.text || claim.text || ""
      ).trim();

      return {
        id: claim.id,
        source,
        value,
        page: `Page ${page}`,
      };
    })
    .filter((item) => item.value);

  return (
    <section>

      <PageHeading
        title="Evidence"
        description="Source passages supporting or challenging extracted claims."
      />

      {usedEvidence.length > 0 && (
        <div className="selected-evidence-banner">
          <strong>
            Selected evidence
          </strong>

          <span>
            {usedEvidence.length} evidence item
            {usedEvidence.length !== 1
              ? "s"
              : ""}{" "}
            added to verification.
          </span>
        </div>
      )}

      {evidence.length === 0 ? (
        <div className="panel">
          <strong>No source evidence available</strong>
          <p className="muted">
            Process the uploaded documents to populate evidence from the backend.
          </p>
        </div>
      ) : (
        <div className="evidence-list">
          {evidence.map((item) => {
            const used = usedEvidence.includes(
              `${item.source}: ${item.value}`
            );

            return (
              <div
                className={`evidence-card ${
                  used ? "selected" : ""
                }`}
                key={item.id}
              >

                <div className="evidence-source">
                  <span className="document-icon small">
                    {item.source.toLowerCase().endsWith(".txt")
                      ? "TXT"
                      : "PDF"}
                  </span>

                  <div>
                    <strong>
                      {item.source}
                    </strong>

                    <span>
                      {item.page}
                    </span>
                  </div>
                </div>

                <p>
                  “{item.value}”
                </p>

                <button
                  className="btn secondary"
                  disabled={used}
                  onClick={() =>
                    onUseEvidence(
                      item.source,
                      item.value
                    )
                  }
                >
                  {used
                    ? "Evidence selected"
                    : "Use this evidence"}
                </button>

              </div>
            );
          })}
        </div>
      )}

    </section>
  );
}

function EvidenceGaps({
  conflicts,
  claims,
}: {
  conflicts: Conflict[];
  claims: ClaimItem[];
}) {
  const gapItems = [
    ...conflicts.map((conflict) => ({
      id: `conflict-${conflict.id}`,
      status: "CONFLICTING",
      title: conflict.title,
      description: `${conflict.description} ${conflict.source1} vs ${conflict.source2}.`,
    })),
    ...claims
      .filter(
        (claim) =>
          claim.status.toUpperCase() === "NEEDS_REVIEW"
      )
      .filter(
        (claim) =>
          !conflicts.some(
            (conflict) =>
              conflict.claimId1 === claim.id ||
              conflict.claimId2 === claim.id
          )
      )
      .map((claim) => ({
        id: `claim-${claim.id}`,
        status: "NEEDS REVIEW",
        title: claim.source,
        description:
          "This claim is marked for human review and does not yet have a final verification decision.",
      })),
  ];

  return (
    <section>

      <PageHeading
        title="Evidence Gaps"
        description="Claims where available sources do not provide enough reliable evidence."
      />

      {gapItems.length === 0 ? (
        <div className="panel">
          <strong>No unresolved evidence gaps</strong>
          <p className="muted">
            The current backend data contains no unresolved conflicts or claims awaiting review.
          </p>
        </div>
      ) : (
        <div className="gap-grid">
          {gapItems.map((item) => (
            <div
              className={`gap-card ${
                item.status === "CONFLICTING" ? "warning" : ""
              }`}
              key={item.id}
            >

              <div className="gap-icon">
                {item.status === "CONFLICTING" ? "!" : "?"}
              </div>

              <div>
                <span>
                  {item.status}
                </span>

                <h2>
                  {item.title}
                </h2>

                <p>
                  {item.description}
                </p>
              </div>

            </div>
          ))}
        </div>
      )}

    </section>
  );
}

function Timeline({
  documents,
  claims,
}: {
  documents: DocumentItem[];
  claims: ClaimItem[];
}) {
  function parseSourceDate(document: DocumentItem) {
    const fullText = (document.pageTexts || [])
      .map((page) => page.text)
      .join(" ");

    const longDateMatch = fullText.match(
      /\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b/i
    );

    if (longDateMatch) {
      const parsed = new Date(longDateMatch[0]);
      if (!Number.isNaN(parsed.getTime())) {
        return parsed;
      }
    }

    const isoMatch = fullText.match(
      /\b20\d{2}-\d{2}-\d{2}\b/
    );

    if (isoMatch) {
      const parsed = new Date(isoMatch[0]);
      if (!Number.isNaN(parsed.getTime())) {
        return parsed;
      }
    }

    if (document.uploadedAt) {
      const parsed = new Date(document.uploadedAt);
      if (!Number.isNaN(parsed.getTime())) {
        return parsed;
      }
    }

    return null;
  }

  const events = documents
    .map((document) => {
      const sourceClaims = claims.filter(
        (claim) => claim.source === document.name
      );

      const date = parseSourceDate(document);

      const summary = sourceClaims
        .slice(0, 2)
        .map((claim) => claim.text)
        .filter(Boolean)
        .join(" ");

      return {
        id: document.id,
        date,
        year: date
          ? String(date.getFullYear())
          : "Date unknown",
        title: document.name,
        text:
          summary ||
          `Source document with ${document.pages} page${
            document.pages === 1 ? "" : "s"
          }.`,
        source: document.type || "SOURCE",
      };
    })
    .sort((a, b) => {
      const timeA = a.date ? a.date.getTime() : Number.MAX_SAFE_INTEGER;
      const timeB = b.date ? b.date.getTime() : Number.MAX_SAFE_INTEGER;

      if (timeA !== timeB) {
        return timeA - timeB;
      }

      return a.title.localeCompare(b.title);
    });

  return (
    <section>

      <PageHeading
        title="Timeline"
        description="Track how source documents and extracted evidence change across source dates."
      />

      {events.length === 0 ? (
        <div className="panel">
          <strong>No timeline events available</strong>
          <p className="muted">
            Upload and process source documents to build the timeline.
          </p>
        </div>
      ) : (
        <div className="timeline">

          {events.map((event) => (
            <div
              className="timeline-item"
              key={event.id}
            >

              <div className="timeline-year">
                {event.year}
              </div>

              <div className="timeline-line">
                <span />
              </div>

              <div className="timeline-content">

                <span className="eyebrow">
                  {event.source}
                </span>

                <h2>
                  {event.title}
                </h2>

                <p>
                  {event.text}
                </p>

              </div>

            </div>
          ))}

        </div>
      )}

    </section>
  );
}

/* =========================================
   REPORT
========================================= */

function Report() {
  const [report, setReport] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  async function loadReport() {
    try {
      setLoading(true);
      setError("");

      const response = await fetch(
        "https://vericore.onrender.com/api/report"
      );

      if (response.status === 404) {
        setReport(null);
        return;
      }

      if (!response.ok) {
        throw new Error("Failed to load report");
      }

      const data = await response.json();
      setReport(data.report || null);
    } catch (err) {
      console.error("Report load failed:", err);
      setError(
        err instanceof Error
          ? err.message
          : "Failed to load report"
      );
    } finally {
      setLoading(false);
    }
  }

  async function generateReport() {
    try {
      setGenerating(true);
      setError("");

      const response = await fetch(
        "https://vericore.onrender.com/api/report/generate",
        {
          method: "POST",
        }
      );

      const data = await response.json();

      if (!response.ok || data.success !== true) {
        throw new Error(
          data.detail ||
            data.message ||
            "Report generation failed"
        );
      }

      setReport(data.report || null);
    } catch (err) {
      console.error(
        "Report generation failed:",
        err
      );
      setError(
        err instanceof Error
          ? err.message
          : "Report generation failed"
      );
    } finally {
      setGenerating(false);
    }
  }

  useEffect(() => {
    loadReport();
  }, []);

  function statusClass(status: string) {
    return status === "VERIFIED"
      ? "report-status supported"
      : "report-status conflicting";
  }

  function sourceLabel(item: any) {
    const source = item.source || {};
    return `${source.filename || "Unknown source"} · p.${
      source.page || 1
    }`;
  }

  return (
    <section>

      <PageHeading
        title="Verified Report"
        description="Consolidated output generated from the available source documents."
      />

      <div className="report-toolbar">

        <div>
          <span className="eyebrow">
            CONSOLIDATED OUTPUT
          </span>

          <h2>
            VeriCore Verified Document
          </h2>
        </div>

        <div style={{ display: "flex", gap: "10px" }}>
          <button
            className="btn secondary"
            onClick={loadReport}
            disabled={loading || generating}
          >
            Refresh
          </button>

          <button
            className="btn primary"
            onClick={generateReport}
            disabled={generating}
          >
            {generating
              ? "Generating..."
              : "Generate Report"}
          </button>
        </div>

      </div>

      {loading ? (
        <article className="report-document">
          <div className="report-cover">
            <span className="eyebrow">
              VERICORE VERIFIED DOCUMENT
            </span>
            <h1>Loading report...</h1>
            <p>
              Reading the latest verified report
              from the backend.
            </p>
          </div>
        </article>
      ) : error ? (
        <article className="report-document">
          <div className="report-cover">
            <span className="warning-label">
              REPORT ERROR
            </span>
            <h1>Could not load report</h1>
            <p>{error}</p>
            <button
              className="btn primary"
              onClick={generateReport}
            >
              Generate Report
            </button>
          </div>
        </article>
      ) : !report ? (
        <article className="report-document">
          <div className="report-cover">
            <span className="eyebrow">
              VERICORE VERIFIED DOCUMENT
            </span>
            <h1>No report generated yet</h1>
            <p>
              Process the uploaded documents and
              generate the consolidated report.
            </p>
            <button
              className="btn primary"
              onClick={generateReport}
              disabled={generating}
            >
              {generating
                ? "Generating..."
                : "Generate Report"}
            </button>
          </div>
        </article>
      ) : (
        <article className="report-document">

          <div className="report-cover">

            <span className="eyebrow">
              VERICORE VERIFIED DOCUMENT
            </span>

            <h1>
              {report.title ||
                "Consolidated Verified Document"}
            </h1>

            <p>
              Generated {report.generated_at
                ? new Date(
                    report.generated_at
                  ).toLocaleString()
                : "recently"}
              .
            </p>

          </div>

          <ReportSection
            number="01"
            title="Verification Summary"
          >
            <InfoLine
              label="Source documents"
              value={String(
                report.summary?.documents || 0
              )}
              status="SUPPORTED"
            />

            <InfoLine
              label="Claims analyzed"
              value={String(
                report.summary?.claims || 0
              )}
              status="SUPPORTED"
            />

            <InfoLine
              label="Verified claims"
              value={String(
                report.summary?.verified_claims || 0
              )}
              status="SUPPORTED"
            />

            <InfoLine
              label="Needs review"
              value={String(
                report.summary?.needs_review || 0
              )}
              status={
                Number(
                  report.summary?.needs_review || 0
                ) > 0
                  ? "CONFLICTING"
                  : "SUPPORTED"
              }
            />

            <InfoLine
              label="Conflicts"
              value={String(
                report.summary?.conflicts || 0
              )}
              status={
                Number(
                  report.summary?.conflicts || 0
                ) > 0
                  ? "CONFLICTING"
                  : "SUPPORTED"
              }
            />
          </ReportSection>

          <ReportSection
            number="02"
            title="Source Documents"
          >
            {(report.documents || []).map(
              (document: any) => (
                <InfoLine
                  key={document.id}
                  label={document.filename}
                  value={
                    document.file_type || "FILE"
                  }
                  status="SUPPORTED"
                />
              )
            )}
          </ReportSection>

          <ReportSection
            number="03"
            title="Claims & Verification"
          >
            {(report.claims || []).map(
              (item: any) => (
                <div
                  className="report-conflict"
                  key={item.claim_id}
                >
                  <strong>{item.claim}</strong>

                  <p>
                    {sourceLabel(item)}
                  </p>

                  <span
                    className={statusClass(
                      item.status
                    )}
                  >
                    {item.status ||
                      "UNVERIFIED"}
                  </span>

                  {item.human_decision && (
                    <p>
                      Human decision:{" "}
                      {item.human_decision.decision}
                    </p>
                  )}
                </div>
              )
            )}
          </ReportSection>

          <ReportSection
            number="04"
            title="Conflicts Requiring Review"
          >
            {(report.claims || [])
              .filter(
                (item: any) =>
                  Array.isArray(item.conflicts) &&
                  item.conflicts.length > 0
              )
              .map((item: any) => (
                <div
                  className="report-conflict"
                  key={`conflict-${item.claim_id}`}
                >
                  <strong>
                    {item.claim}
                  </strong>

                  <p>
                    {item.conflicts
                      .map(
                        (conflict: any) =>
                          conflict.reason ||
                          conflict.conflict?.reason ||
                          "Conflicting information detected."
                      )
                      .join(" | ")}
                  </p>

                  <span className="warning-label">
                    HUMAN REVIEW REQUIRED
                  </span>
                </div>
              ))}

            {Number(
              report.summary?.conflicts || 0
            ) === 0 && (
              <div className="report-gap">
                <strong>
                  No conflicts detected
                </strong>
              </div>
            )}
          </ReportSection>

          <ReportSection
            number="05"
            title="Source Provenance"
          >
            <ul className="source-list">
              {(report.documents || []).map(
                (document: any) => (
                  <li key={document.id}>
                    {document.filename} · SHA-256{" "}
                    {document.sha256 || "unavailable"}
                  </li>
                )
              )}
            </ul>
          </ReportSection>

          <div className="report-footer">

            <strong>
              VeriCore verification rule
            </strong>

            <p>
              The report preserves claim status,
              source provenance, conflicts and human
              decisions instead of inventing certainty.
            </p>

          </div>

        </article>
      )}

    </section>
  );
}
/* =========================================
   VERIFICATION
========================================= */

function Verification({
  conflicts,
  usedEvidence,
  onUseEvidence,
  onRecordDecision,
}: {
  conflicts: Conflict[];
  usedEvidence: string[];
  onUseEvidence: (source: string, value: string) => void;
  onRecordDecision: (selectedDecision: string, claimId: string) => Promise<void>;
}) {
  const [selectedDecision, setSelectedDecision] = useState("");
  const conflict = conflicts[0] || null;

  if (!conflict) {
    return (
      <section>
        <PageHeading
          title="Verification"
          description="Resolve conflicting claims using source evidence and record a human decision."
        />
        <div className="panel">
          <h3>No unresolved conflicts</h3>
          <p className="muted">Run document processing to populate the verification queue.</p>
        </div>
      </section>
    );
  }

  return (
    <section>
      <PageHeading
        title="Verification"
        description="Resolve conflicting claims using source evidence and record a human decision."
      />

      <div className="verification-layout">
        <div className="verification-main">
          <div className="verification-header">
            <div>
              <span className="eyebrow">CLAIM VERIFICATION</span>
              <h2>{conflict.title}</h2>
              <span className="warning-label">CONFLICTING</span>
            </div>
          </div>

          <p className="verification-description">
            {conflict.description}
          </p>

          <div className="evidence-comparison">
            <EvidenceBox
              source="SOURCE 1"
              title={conflict.source1}
              value={conflict.value1}
              page={conflict.page1}
              claimId={conflict.claimId1}
              used={usedEvidence.some((e) => e.includes(conflict.source1))}
              onUse={(evidenceText) => onUseEvidence(conflict.source1, evidenceText)}
            />

            <EvidenceBox
              source="SOURCE 2"
              title={conflict.source2}
              value={conflict.value2}
              page={conflict.page2}
              claimId={conflict.claimId2}
              used={usedEvidence.some((e) => e.includes(conflict.source2))}
              onUse={(evidenceText) => onUseEvidence(conflict.source2, evidenceText)}
            />
          </div>

          <div className="verification-rule">
            <strong>veriCore rule</strong>
            <span>
              If evidence cannot be reliably reconciled, the system keeps the conflict visible rather than inventing certainty.
            </span>
          </div>

          <div className="decision-section">
            <h3>Record verification decision</h3>

            <div className="decision-options">
              <button
                className={`decision-option ${selectedDecision === "Accept source 1" ? "selected" : ""}`}
                onClick={() => setSelectedDecision("Accept source 1")}
              >
                <strong>Use source 1</strong>
                <span>{conflict.source1}</span>
              </button>

              <button
                className={`decision-option ${selectedDecision === "Accept source 2" ? "selected" : ""}`}
                onClick={() => setSelectedDecision("Accept source 2")}
              >
                <strong>Use source 2</strong>
                <span>{conflict.source2}</span>
              </button>

              <button
                className={`decision-option ${selectedDecision === "Keep Unresolved" ? "selected" : ""}`}
                onClick={() => setSelectedDecision("Keep Unresolved")}
              >
                <strong>Keep unresolved</strong>
                <span>Preserve the conflict</span>
              </button>
            </div>

            <button
              className="btn primary"
              disabled={!selectedDecision}
              onClick={async () => {
                const claimId =
                  selectedDecision === "Accept source 2"
                    ? conflict.claimId2
                    : conflict.claimId1;
                await onRecordDecision(selectedDecision, claimId);
                setSelectedDecision("");
              }}
            >
              Record Decision
            </button>
          </div>
        </div>

        <aside className="verification-side">
          <div className="panel">
            <span className="eyebrow">CURRENT STATUS</span>
            <div className="big-status warning">REVIEW REQUIRED</div>
            <p>
              This claim remains visible until a human decision is recorded.
            </p>
          </div>

          <div className="panel">
            <span className="eyebrow">SELECTED EVIDENCE</span>
            {usedEvidence.length === 0 ? (
              <p className="muted">No evidence selected yet.</p>
            ) : (
              usedEvidence.map((item) => (
                <div className="mini-evidence" key={item}>
                  ✓ {item}
                </div>
              ))
            )}
          </div>
        </aside>
      </div>
    </section>
  );
}

/* =========================================
   AUDIT TRAIL
========================================= */

function AuditTrail({
  events,
}: {
  events: string[];
}) {
  const [backendEvents, setBackendEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadBackendAudit() {
      try {
        const response = await fetch(
          "https://vericore.onrender.com/api/audit"
        );

        if (!response.ok) {
          throw new Error("Failed to load audit trail");
        }

        const data = await response.json();
        setBackendEvents(
          Array.isArray(data.events)
            ? data.events
            : []
        );
      } catch (error) {
        console.error(
          "Failed to load audit trail:",
          error
        );
        setBackendEvents([]);
      } finally {
        setLoading(false);
      }
    }

    loadBackendAudit();
  }, []);

  const displayEvents =
    backendEvents.length > 0
      ? backendEvents
      : events.map((event) => ({
          id: event,
          action: event,
          timestamp: "",
          details: {},
        }));

  function formatTimestamp(timestamp: string) {
    if (!timestamp) {
      return "Verification workspace · local event";
    }

    const date = new Date(timestamp);

    if (Number.isNaN(date.getTime())) {
      return timestamp;
    }

    return date.toLocaleString();
  }

  function formatDetails(details: any) {
    if (
      !details ||
      typeof details !== "object" ||
      Object.keys(details).length === 0
    ) {
      return "";
    }

    return Object.entries(details)
      .map(([key, value]) => {
        const label = key
          .replace(/_/g, " ")
          .replace(/^./, (char) => char.toUpperCase());

        return `${label}: ${String(value)}`;
      })
      .join(" · ");
  }

  return (
    <section>

      <PageHeading
        title="Audit Trail"
        description="A record of important actions performed during verification."
      />

      <div className="audit-list">

        {loading ? (
          <div className="audit-item">
            <div className="audit-icon">
              …
            </div>
            <div>
              <strong>Loading audit history...</strong>
              <span>
                Reading events from the veriCore backend.
              </span>
            </div>
          </div>
        ) : displayEvents.length === 0 ? (
          <div className="audit-item">
            <div className="audit-icon">
              ✓
            </div>
            <div>
              <strong>No audit events yet</strong>
              <span>
                Backend audit history is currently empty.
              </span>
            </div>
          </div>
        ) : (
          displayEvents.map((event, index) => {
            const detailsText = formatDetails(
              event.details
            );

            return (
              <div
                className="audit-item"
                key={`${event.id || event.action}-${index}`}
              >

                <div className="audit-icon">
                  ✓
                </div>

                <div>
                  <strong>
                    {event.action || "AUDIT_EVENT"}
                  </strong>

                  <span>
                    {formatTimestamp(event.timestamp)}
                  </span>

                  {detailsText && (
                    <small>
                      {detailsText}
                    </small>
                  )}
                </div>

              </div>
            );
          })
        )}

      </div>

    </section>
  );
}

/* =========================================
   SETTINGS
========================================= */

function Settings() {
  return (
    <section>

      <PageHeading
        title="Settings"
        description="Configure verification workspace behaviour."
      />

      <div className="settings-grid">

        <div className="setting-card">
          <div>
            <strong>
              Evidence-first verification
            </strong>

            <p>
              Keep claims tied to source evidence.
            </p>
          </div>

          <div className="toggle active">
            <span />
          </div>
        </div>

        <div className="setting-card">
          <div>
            <strong>
              Preserve unresolved conflicts
            </strong>

            <p>
              Never silently replace conflicting values.
            </p>
          </div>

          <div className="toggle active">
            <span />
          </div>
        </div>

        <div className="setting-card">
          <div>
            <strong>
              Audit logging
            </strong>

            <p>
              Record verification actions.
            </p>
          </div>

          <div className="toggle active">
            <span />
          </div>
        </div>

      </div>

    </section>
  );
}

/* =========================================
   SMALL COMPONENTS
========================================= */

function PageHeading({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="page-heading">

      <div className="eyebrow">
        WORKSPACE / VERIFICATION
      </div>

      <h1>{title}</h1>

      <p>{description}</p>

    </div>
  );
}

function StatCard({
  label,
  value,
  text,
  green,
  warning,
}: {
  label: string;
  value: string;
  text: string;
  green?: boolean;
  warning?: boolean;
}) {
  return (
    <div className="stat-card">

      <span>
        {label}
      </span>

      <strong
        className={
          green
            ? "green-text"
            : warning
            ? "warning-text"
            : ""
        }
      >
        {value}
      </strong>

      <small>
        {text}
      </small>

    </div>
  );
}

function ConflictRow({
  conflict,
  onClick,
}: {
  conflict: Conflict;
  onClick: () => void;
}) {
  return (
    <button
      className="conflict-row"
      onClick={onClick}
    >

      <div className="conflict-symbol">
        {conflict.type === "Evidence gap"
          ? "?"
          : "!"}
      </div>

      <div className="conflict-row-content">

        <strong>
          {conflict.title}
        </strong>

        <span className="conflict-value">
          {conflict.value1}{" "}
          {conflict.type !==
            "Evidence gap" && "→"}{" "}
          {conflict.type !==
            "Evidence gap" &&
            conflict.value2}
        </span>

        <small>
          {conflict.description}
        </small>

      </div>

      <span className="arrow">
        →
      </span>

    </button>
  );
}

function Legend({
  label,
  value,
  green,
  warning,
}: {
  label: string;
  value: string;
  green?: boolean;
  warning?: boolean;
}) {
  return (
    <div className="legend-row">

      <span
        className={`legend-dot ${
          green
            ? "green"
            : warning
            ? "warning"
            : ""
        }`}
      />

      <span>
        {label}
      </span>

      <strong>
        {value}
      </strong>

    </div>
  );
}

function SourceValue({
  label,
  value,
  page,
}: {
  label: string;
  value: string;
  page: string;
}) {
  return (
    <div className="source-value">

      <span className="eyebrow">
        {label}
      </span>

      <strong>
        {value}
      </strong>

      <small>
        {page}
      </small>

    </div>
  );
}

function ReportSection({
  number,
  title,
  children,
}: {
  number: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="report-section">

      <div className="report-section-title">
        <span>
          {number}
        </span>

        <h2>
          {title}
        </h2>
      </div>

      <div className="report-section-content">
        {children}
      </div>

    </section>
  );
}

function InfoLine({
  label,
  value,
  status,
  source,
}: {
  label: string;
  value: string;
  status: string;
  source?: string;
}) {
  return (
    <div className="info-line">

      <div>
        <strong>{label}</strong>

        {source && (
          <small>{source}</small>
        )}
      </div>

      <strong>{value}</strong>

      <span
        className={
          status === "SUPPORTED"
            ? "report-status supported"
            : "report-status conflicting"
        }
      >
        {status}
      </span>

    </div>
  );
}

function EvidenceBox({
  source,
  title,
  value,
  page,
  claimId,
  used,
  onUse,
}: {
  source: string;
  title: string;
  value: string;
  page: string;
  claimId: string;
  used: boolean;
  onUse: (evidenceText: string) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [evidenceText, setEvidenceText] = useState("");

  function makeSnippet(items: any[]) {
    if (!items.length) {
      return "No supporting evidence was retrieved for this claim.";
    }

    const normalizedValue = String(value || "")
      .replace(/\s+/g, " ")
      .trim();

    const valueWords = normalizedValue
      .toLowerCase()
      .split(/[^a-z0-9°.%]+/)
      .filter((word) => word.length >= 3)
      .slice(0, 10);

    let best = String(items[0]?.text || "");
    let bestScore = -1;

    for (const item of items) {
      const text = String(item?.text || "").replace(
        /\s+/g,
        " "
      ).trim();
      const lower = text.toLowerCase();
      const score = valueWords.reduce(
        (total, word) => total + (lower.includes(word) ? 1 : 0),
        0
      );

      if (score > bestScore) {
        bestScore = score;
        best = text;
      }
    }

    // For timestamped logs, show the single matching record.
    if (/^\d{2}:\d{2}:\d{2}\s*\|/.test(normalizedValue)) {
      const lines = best.split(/\n|(?=\d{2}:\d{2}:\d{2}\s*\|)/);
      const matchingLine = lines.find((line) =>
        line.includes(normalizedValue)
      );
      if (matchingLine) return matchingLine.trim();
    }

    // For prose pages, prefer the sentence containing the main claim.
    const sentences = best.split(/(?<=[.!?])\s+/);
    const sentence = sentences.find((item) => {
      const lower = item.toLowerCase();
      return valueWords.some((word) => lower.includes(word));
    });

    return (sentence || best).trim();
  }

  async function loadEvidence() {
    if (!claimId) {
      setEvidenceText("This conflict has no claim ID.");
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(
        `https://vericore.onrender.com/api/evidence/retrieve/${claimId}`,
        { method: "POST" }
      );

      const data = await response.json();

      if (!response.ok || data.success !== true) {
        throw new Error(
          data.detail || data.message || "Evidence retrieval failed"
        );
      }

      const snippet = makeSnippet(data.evidence || []);
      setEvidenceText(snippet);
    } catch (error) {
      console.error("Evidence retrieval failed:", error);
      setEvidenceText(
        `Evidence retrieval failed: ${
          error instanceof Error ? error.message : "unknown error"
        }`
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={`evidence-box ${used ? "selected" : ""}`}>
      <span className="eyebrow">{source}</span>
      <h3>{title}</h3>
      <strong>{value}</strong>
      <span className="evidence-page">{page}</span>

      <p>
        {evidenceText ||
          "Click Retrieve evidence to fetch the original supporting passage."}
      </p>

      <div className="evidence-actions">
        <button
          className="btn secondary"
          onClick={loadEvidence}
          disabled={loading}
        >
          {loading
            ? "Retrieving evidence..."
            : "Retrieve evidence"}
        </button>

        <button
          className="btn secondary"
          onClick={() => onUse(evidenceText || value)}
          disabled={!evidenceText || used}
        >
          {used ? "Evidence selected" : "Use this evidence"}
        </button>
      </div>
    </div>
  );
}

function ConflictModal({
  conflict,
  decision,
  setDecision,
  onClose,
  onUseEvidence,
  onRecordDecision,
}: {
  conflict: Conflict;
  decision: string;
  setDecision: (value: string) => void;
  onClose: () => void;
  onUseEvidence: (
    source: string,
    value: string
  ) => void;
  onRecordDecision: (selectedDecision: string, claimId: string) => void;
}) {
  return (
    <div className="modal-backdrop">

      <div className="conflict-modal">

        <button
          className="modal-close"
          onClick={onClose}
        >
          ×
        </button>

        <span className="eyebrow">
          CLAIM VERIFICATION
        </span>

        <h2>
          {conflict.title}
        </h2>

        <span className="warning-label">
          CONFLICTING
        </span>

        <p className="modal-description">
          {conflict.description}
        </p>

        <div className="modal-evidence-grid">

          <EvidenceBox
            source="SOURCE 1"
            title={conflict.source1}
            value={conflict.value1}
            page={conflict.page1}
            claimId={conflict.claimId1}
            used={false}
            onUse={(evidenceText) =>
              onUseEvidence(
                conflict.source1,
                evidenceText
              )
            }
          />

          <EvidenceBox
            source="SOURCE 2"
            title={conflict.source2}
            value={conflict.value2}
            page={conflict.page2}
            claimId={conflict.claimId2}
            used={false}
            onUse={(evidenceText) =>
              onUseEvidence(
                conflict.source2,
                evidenceText
              )
            }
          />

        </div>

        <div className="verification-rule">
          <strong>
            veriCore rule
          </strong>

          <span>
            If evidence cannot be reliably reconciled,
            keep the conflict visible rather than
            inventing certainty.
          </span>
        </div>

        <div className="modal-decision">

          <h3>
            Decision
          </h3>

          <div className="decision-options">

            <button
              className={`decision-option ${
                decision ===
                "Accept source 1"
                  ? "selected"
                  : ""
              }`}
              onClick={() =>
                setDecision(
                  "Accept source 1"
                )
              }
            >
              <strong>
                Use source 1
              </strong>

              <span>
                {conflict.source1}
              </span>
            </button>

            <button
              className={`decision-option ${
                decision ===
                "Accept source 2"
                  ? "selected"
                  : ""
              }`}
              onClick={() =>
                setDecision(
                  "Accept source 2"
                )
              }
            >
              <strong>
                Use source 2
              </strong>

              <span>
                {conflict.source2}
              </span>
            </button>

            <button
              className={`decision-option ${
                decision ===
                "Keep Unresolved"
                  ? "selected"
                  : ""
              }`}
              onClick={() =>
                setDecision(
                  "Keep Unresolved"
                )
              }
            >
              <strong>
                Keep Unresolved
              </strong>

              <span>
                Preserve the conflict
              </span>
            </button>

          </div>

        </div>

        <div className="modal-actions">

          <button
            className="btn secondary"
            onClick={onClose}
          >
            Close
          </button>

          <button
            className="btn primary"
            disabled={!decision}
            onClick={() => {
              const claimId =
                decision === "Accept source 2"
                  ? conflict.claimId2
                  : conflict.claimId1;
              onRecordDecision(decision, claimId);
            }}
          >
            Record Decision
          </button>

        </div>

      </div>

    </div>
  );
}

export default App;