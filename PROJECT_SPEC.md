# veriCore

## Product Name
veriCore — Multi-Source Verifiable Document Intelligence

## Core Idea

veriCore takes information from multiple documents and creates one
consolidated document whose claims can be traced back to their original
sources.

## Core Principle

SOURCE → CLAIM → EVIDENCE → CONFLICT → HUMAN VERIFICATION → VERIFIED DOCUMENT

## Main Problem

Information from different documents may:
- agree
- contradict each other
- refer to different entities
- describe changes over time
- lack sufficient evidence

veriCore identifies these situations instead of blindly combining
everything into one AI-generated answer.

## Core Workflow

1. Upload documents
2. Extract text / OCR
3. Preserve source and page information
4. Identify entities
5. Extract factual claims
6. Link claims to supporting evidence
7. Compare claims across sources
8. Classify conflicts
9. Detect evidence gaps
10. Allow human verification
11. Maintain an audit trail
12. Generate a consolidated verified document

## Signature Features

### 1. Claim–Evidence Graph
Shows how every important claim connects to its source evidence.

### 2. Intelligent Conflict Analysis
Classifies differences as:
- Direct contradiction
- Temporal change
- Condition mismatch
- Entity ambiguity
- Other / unresolved

### 3. Evidence Gap Detection
Identifies claims that do not have sufficient supporting evidence.

### 4. Human Verification Workspace
Allows a human to review conflicting evidence and record a decision.

### 5. What Changed?
Shows how important claims changed across documents/time.

### 6. Audit Trail
Records important processing and verification actions.

## Verification States

SUPPORTED
PARTIALLY_SUPPORTED
CONFLICTING
UNSUPPORTED
REQUIRES_HUMAN_REVIEW

## Important Rule

veriCore must never present an unsupported claim as verified.

## Demo Scenario

Use a fictional product/machine with multiple documents containing
overlapping information and intentional inconsistencies.

Example:
- Manufacturer Manual
- Inspection Report
- Maintenance Report
- Engineering Report

## Final Output

The system generates a consolidated document containing:
- Verified claims
- Conflicting claims
- Evidence/source references
- Verification status
- Important unresolved issues
- Provenance information