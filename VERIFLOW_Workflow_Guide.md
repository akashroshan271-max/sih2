# VERIFLOW — AICTE Approval Process Workflow Guide

## Document Version: 0.3 (2026-10-27)
**Generated from codebase inspection + live verification**

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [The 5 Statutory Phases](#2-the-5-statutory-phases)
3. [State Machine & Transitions](#3-state-machine--transitions)
4. [Rule 1 — Lease‑Deed Gate](#4-rule-1--lease-deed-gate)
5. [Gemini AI — Lease Deed Extraction](#5-gemini-ai--lease-deed-extraction)
6. [Tutorial — Using the Site for Each Phase](#6-tutorial--using-the-site-for-each-phase)
7. [All Features Summary](#7-all-features-summary)
8. [Appendix — Demo Accounts & Commands](#8-appendix--demo-accounts--commands)

---

## 1. System Overview

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 14.2.15, React 18.3.1, TypeScript, Tailwind CSS |
| **Backend** | FastAPI (Python), SQLAlchemy 2.0, PostgreSQL |
| **Auth** | JWT tokens, OIDC via Freebuff `Sign in with Freebuff` |
| **AI** | `google-genai` 1.75.0 → `gemini-3.6-flash` (verified working, ~11s response) |
| **Deployment** | Cloudflare Workers + Sites (isolated preview/production) |
| **SLA/Dwell** | 15/30/45‑day thresholds (L1/L2/L3 escalations) |
| **Audit** | SHA‑256 chained audit log per application |

Both servers are currently running:
- **Backend** PID 48940 (`/health` OK, login 200 in 0.26s, CORS from `127.0.0.1:3000` → 200)
- **Frontend** PID 61596 (serving `http://127.0.0.1:3000`, title: "VERIFLOW · AICTE approval command centre")
- Preview registered in this thread's Preview tab.

**Demo account**: `ro.mumbai@aicte.gov.in` / `veriflow@2026` (Regional Officer, watches all stages, verifies audit chain).

---

## 2. The 5 Statutory Phases (APH 2024‑27, Chapter II)

The workflow follows a **fixed linear order**. Each phase has a designated officer desk.

| Phase | Status | Role (email) | Desk | UI Label | Key Function |
|---|---|---|---|---|---|
| **Phase 1** | `scrutiny` | `scrutiny.officer@aicte.gov.in` | Scrutiny cell | "Phase 1 · evidence & Rule 1" | Receives all applications; verifies lease compliance (Rule 1) before any move |
| **Phase 2** | `evc` | `evc.member@aicte.gov.in` | Expert Visit Committee | "Phase 2 · expert visit" | On‑site inspection for **NEW** / **EXPANSION** types only |
| **Phase 3** | `sac` | `sac.member@aicte.gov.in` | Standing Approval Committee | "Phase 3 · committee decision" | Committee review; can advance to APPROVED / REJECTED or SHC |
| **Phase 4** | `shc` | `shc.member@aicte.gov.in` | Standing Hearing Committee | "Phase 4 · hearing" | Final hearing; only APPROVED / REJECTED exits |
| **Oversight** | — | `ro.mumbai@aicte.gov.in` | Regional office | "Oversight · read‑only across stages" | Sees every desk, watches SLA clock, verifies audit chain |

> **Note**: The 5 desks each sign in separately; each sees only the dockets waiting at their stage.

### Phase‑to‑Status Mapping

```
Phase 1   → status = "scrutiny"
Phase 2   → status = "evc"
Phase 3   → status = "sac"
Phase 4   → status = "shc"
Oversight → status = any (regional officer sees all)
```

---

## 3. State Machine & Transitions

All legal transitions live in `backend/app/services/workflow.py`, function `allowed_transitions(application)`.

### 3.1. Terminal Statuses

```python
TERMINAL_STATUSES = {ApplicationStatus.APPROVED, ApplicationStatus.REJECTED}
```
Once an application reaches `APPROVED` or `REJECTED`, **no further transitions** are permitted.

### 3.2. `EVC_REQUIRED_TYPES`

```python
EVC_REQUIRED_TYPES = {ApplicationType.NEW, ApplicationType.EXPANSION}
```
Only NEW and EXPANSION applications must pass through the Expert Visit Committee (EVC). RENEWAL and CLOSURE skip EVC.

### 3.3. Permitted Transitions Table

| From Status | Application Type | Permitted Next States |
|---|---|---|
| **SCRUTINY** | NEW / EXPANSION | `EVC`, `REJECTED` |
| **SCRUTINY** | RENEWAL / CLOSURE | `SAC`, `REJECTED` |
| **EVC** | any | `SAC`, `SHC`, `REJECTED` |
| **SAC** | any | `APPROVED`, `REJECTED`, `SHC` |
| **SHC** | any | `APPROVED`, `REJECTED` |
| **APPROVED / REJECTED** | — | *terminal — no transitions* |

### 3.3.1. Visual Flow

```
Application created (SCRUTINY)
    │
    ├──► NEW/EXPANSION: SCRUTINY → EVC               (Phase 2)
    │       │
    │       ├──► EVC → SAC                            (Phase 3)
    │       │       └──► SAC → APPROVED / REJECTED
    │       │           └──► SAC → SHC → APPROVED / REJECTED   (Phase 4)
    │       └──► EVC → REJECTED
    │
    └──► RENEWAL/CLOSURE: SCRUTINY → SAC               (skips EVC)
            │
            ├──► SAC → APPROVED / REJECTED
            │       └──► SAC → SHC → APPROVED / REJECTED
            └──► Ultimately: APPROVED or REJECTED (terminal)
```

### 3.4. Transition Execution (POST `/workspace/applications/{id}/transition`)

The backend (`WorkflowService.transition()`) serialises every move:

1. **Row lock** (`with_for_update=True`) — prevents concurrent double‑advance.
2. **Terminal check** — if already APPROVED/REJECTED → `InvalidTransition`.
3. **Permitted check** — `allowed_transitions()`; if target ∉ permitted → `InvalidTransition` with the list of allowed states.
4. **Rule 1 gate** — if leaving SCRUTINY → evaluate live lease; if not compliant → `LeaseRuleBlocked` (422, docket stays).
5. **Apply transition**:
   - `application.status = target`
   - `application.stage_entry_timestamp = now` (Rule 3 — SLA clock restarts)
   - If target is terminal → `application.decided_at = now`, `application.decision_remarks = remarks`
6. **Audit log** — write `AuditLog` with:
   - `action="stage.transition"`
   - `actor`, `actor_role`
   - `from_status`, `to_status`
   - `payload`: `{remarks, application_type, lease_verdict}`
   - `occurred_at` timestamp
   - SHA‑256 chained hash (via `integrity.py`)
7. **Commit** — `db.commit()` + `db.refresh(application)`.

**Return**: `TransitionResult` with `from_status`, `to_status`, `audit_log`, `lease_verdict`.

**What happens next**:
- The docket immediately moves to the new stage's queue.
- The SLA dwell clock re‑starts at the new stage.
- An audit entry is permanently recorded; verifiable with `AuditService(db).verify(application.id)`.

---

## 4. Rule 1 — Lease‑Deed Gate (Hard Block)

**Location**: `backend/app/services/workflow.py`, lines 96‑117.

Before **any** transition out of `SCRUTINY`, the system evaluates the live lease deed:

```python
if from_status is ApplicationStatus.SCRUTINY and target in (EVC, SAC):
    lease_verdict = evaluate_live_lease(self.db, application, as_of=as_of)
    if not lease_verdict.compliant:
        raise LeaseRuleBlocked(lease_verdict)
```

### 4.1. What `evaluate_live_lease` Checks (from `backend/app/services/compliance.py`)

| Check | What It Validates |
|---|---|
| Lease start/end dates | Must be present; `end > start` |
| Land area | Must be positive (after unit conversion: 1 acre = 4046.8564224 m², 1 ha = 10000 m², 1 ft² = 0.09290304 m², 1 yd² = 0.83612736 m²) |
| Survey numbers | Must be present as non‑empty array; each listed individually, never merged ranges |
| Lease term vs. course duration | Lease must cover the full course duration |

### 4.2. Verdict Meanings (from `frontend/lib/constants.ts` → `LEASE_CODE_LABEL`)

| Code | Label (badge) | Meaning |
|---|---|---|
| `lease_valid` | "Live lease verified" | All checks pass → gate opens |
| `lease_deed_missing` | "No lease deed on file" | Document missing → docket stuck at Scrutiny |
| `lease_not_extracted` | "Lease dates not readable" | AI could not parse the PDF |
| `lease_not_commenced` | "Lease not yet in force" | Start date is in the future |
| `lease_expired` | "Lease expired" | End date is in the past |
| `lease_too_short` | "Lease shorter than course" | Lease term < proposed course duration |

### 4.3. If Non‑Compliant

- `LeaseRuleBlocked` error (HTTP 422) is raised.
- An audit entry `lease_rule.blocked` is written with the verdict.
- The docket **cannot move** until the lease is fixed or a new deed is uploaded.

### 4.4. Live Verification

I ran the extractor on a synthetic lease deed and obtained:
- `lease_start_date = 2021‑07‑01`
- `lease_end_date = 2031‑06‑30`
- `total_land_area_sqm = 10117.14` (2.5 acres → m² correctly converted)
- `survey_numbers = ["118/2", "118/3", "119"]`
- confidence **1.0**, zero issues.

All field assertions passed.

---

## 5. Gemini AI — Lease Deed Extraction Workflow

### 5.1. Upload & Extraction Steps

1. **Institution** uploads a lease‑deed PDF (or image) via the docket workspace.
2. **Frontend** sends the document to `POST /api/v1/documents/{id}/extract` (or extraction triggers on upload).
3. **Backend** calls `GeminiLeaseExtractor` with `genai.Client(api_key=settings.gemini_api_key)`.
4. **Model**: `gemini-3.6-flash` (the only flash model this API key reliably responds to; 3.7/3.8 returned 503/504 under demand at test time).
5. **Prompt** (from `backend/app/services/gemini.py`, `LEASE_PROMPT`): Strict schema extraction requesting exactly:
   - `lease_start_date` — `"YYYY-MM-DD"` or `null`
   - `lease_end_date` — `"YYYY-MM-DD"` or `null`
   - `total_land_area_sqm` — number (sq m), with conversion rules
   - `survey_numbers` — `array[string]`, each individually listed; never merged ranges
6. **Response validation**:
   - Must be valid JSON matching the schema.
   - If any field is missing/invalid → `extraction_status = NEEDS_REVIEW` (badge "Needs review", turmeric tone).
   - If contradictory (e.g., `end ≤ start`) → issues flagged, confidence < 1.0.
   - If all 4 fields present and valid → `extraction_status = EXTRACTED` (badge "Extracted", teal tone), confidence 1.0.
7. **Data stored** on the `Document` model:
   - `extraction_status` (PENDING→PROCESSING→EXTRACTED/NEEDS_REVIEW/FAILED)
   - `extraction_model` = `"gemini-3.6-flash"`
   - `extraction_confidence` (0.0–1.0)
   - `extracted_json_data` (raw Gemini JSON, for audit trail)
   - `lease_start_date`, `lease_end_date`, `total_land_area_sqm`, `survey_numbers` (direct columns).

### 5.2. Extraction Status Behaviour

| Status | Badge | Tone | What Happens |
|---|---|---|---|
| **EXTRACTED** | "Extracted" | teal | All 4 fields present & valid → Rule 1 gate passes → officer can transition out of Scrutiny. |
| **NEEDS_REVIEW** | "Needs review" | turmeric | Some field missing/ambiguous → officer must manual‑verify or re‑upload; transition out of Scrutiny blocked. |
| **FAILED** | "Extraction failed" | seal | Model error, safety block, or malformed PDF → officer uploads a new PDF or proceeds without AI (statutory rules still applied locally). |

### 5.3. Gemini Model Choice Rationale

During verification I smoke‑tested every flash model this API key can see:

| Model | Result |
|---|---|
| `gemini-3.8-flash` | 503/504 (high demand at test time) |
| `gemini-3.7-flash` | 503 (high demand) |
| `gemini-3.6-flash` | **OK — 11s response** |
| `gemini-3.5-flash` | OK — 18s response |
| `gemini-flash-latest` | 504 (deadline exceeded) |

The default is now `gemini-3.6-flash` everywhere: `config.py`, `.env`, `.env.example`, seed data, tests, and comments. If you want a different model, flip `GEMINI_MODEL` in `backend/.env` and restart.

### 5.4. Unit Conversion Rules (embedded in the prompt)

```
1 acre  = 4046.8564224 m²
1 hectare = 10000 m²
1 sq ft = 0.09290304 m²
1 sq yd = 0.83612736 m²
```

The model is told to convert any area it reads to **square metres** and return the number under `total_land_area_sqm`.

### 5.5. Audit Trail

The raw Gemini JSON is stored under `extracted_json_data` on the `Document`. This is the **source of truth** for any later compliance check or officer review. The `LeaseVerdict` object (from `evaluate_live_lease`) also serialises its `as_dict()` into the stage‑transition audit payload.

---

## 6. Tutorial — Using the Site for Each Phase

> **Prerequisite**: Both servers are running (backend :8000, frontend :3000). Preview is registered in this thread's Preview tab.

### 6.1. Login

1. Open `http://127.0.0.1:3000` in a browser tab (or click the Preview panel).
2. The login page shows 5 statutory phases listed on the left:
   - Phase 1 — Scrutiny cell
   - Phase 2 — Expert Visit Committee
   - Phase 3 — Standing Approval Committee
   - Phase 4 — Standing Hearing Committee
   - Oversight — Regional office
3. Enter **Official email** and **Password**.
4. Use any demo account (passwords all share `DEMO_PASSWORD` = `veriflow@2026`):

| Email | Role | Desk |
|---|---|---|
| `scrutiny.officer@aicte.gov.in` | scrutiny_officer | Phase 1 |
| `evc.member@aicte.gov.in` | evc_member | Phase 2 |
| `sac.member@aicte.gov.in` | sac_member | Phase 3 |
| `shc.member@aicte.gov.in` | shc_member | Phase 4 |
| `ro.mumbai@aicte.gov.in` | regional_officer | Oversight (sees all) |

5. Click **Sign in**. You are redirected to the workspace appropriate for your role (regional → `/dashboard`, all others → `/workspace`).

### 6.2. Phase 1 — Scrutiny Officer

**What you see**: Docket queue with applications awaiting lease validation.

1. Each docket shows:
   - Application number, institution, academic year.
   - Associated documents with `extraction_status` badges (pending / extracting / extracted / needs_review / failed).
   - SLA dwell days counter (L1 at 15d, L2 at 30d, L3 at 45d).
   - Allowed transition buttons (green when permitted, gray when not).
2. **If a lease deed has been uploaded**:
   - The Gemini extractor runs automatically.
   - Badge shows "Extracted" (teal) if all 4 fields present & valid.
   - Badge shows "Needs review" (turmeric) if some field missing/ambiguous.
   - Badge shows "Extraction failed" (seal) if model error.
3. **Rule 1 gate**: Click **Transition to EVC** (for NEW/EXPANSION) or **Transition to SAC** (for RENEWAL/CLOSURE).
   - Backend validates: `allowed?` + `Rule 1 lease compliant?`.
   - If lease non‑compliant → `LeaseRuleBlocked` error, docket stays at Scrutiny, badge turns "No lease deed on file" (gray).
   - If compliant → transition commits, SLA clock restarts, docket moves to next stage's queue.
4. **If no lease deed**: Upload a PDF via the "Upload document" button. After upload, extraction runs; once status = EXTRACTED, the transition button becomes enabled.

**Transition button locations**:
- Top‑right of each docket card: `→ EVC`, `→ SAC`, `→ Approve`, `→ Reject`.
- Only permitted transitions are shown (the disabled ones are grayed out).

### 6.3. Phase 2 — EVC Member

**What you see**: Dockets at `status = "evc"`.

1. Each docket is a NEW or EXPANSION application that has already passed Scrutiny.
2. **Actions**:
   - Review the expert‑visit report (attached document or notes).
   - Click **Transition to SAC** to advance to the Standing Approval Committee.
   - Click **Transition to REJECTED** to deny the application.
3. The SLA clock restarts at `stage_entry_timestamp` = now.
4. An audit entry `stage.transition` is written; the regional officer can later verify the chain.

### 6.4. Phase 3 — SAC Member

**What you see**: Dockets at `status = "sac"`.

1. Applications that have completed EVC (or skipped it for RENEWAL/CLOSURE).
2. **Actions**:
   - Review the lease verdict and any audit notes.
   - Decide: **Transition to APPROVED**, **Transition to REJECTED**, or **Transition to SHC** (if the docket requires a hearing).
3. If **APPROVED**: `decided_at` = now, `decision_remarks` are stored.
4. If **SHC**: The docket moves to Phase 4.

### 6.5. Phase 4 — SHC Member

**What you see**: Dockets at `status = "shc"`.

1. Final‑stage applications that have reached the Standing Hearing Committee.
2. **Actions**:
   - Review the record (all prior audit entries are visible).
   - Decide: **Transition to APPROVED** or **Transition to REJECTED**.
3. Both are terminal — no further transitions are permitted.
4. The regional officer’s dashboard shows the final status and SLA status (whether any thresholds were breached).

### 6.6. Oversight — Regional Officer

**What you see** (dashboard at `/dashboard`):

1. **All applications** across every stage, with current status badges.
2. **SLA monitor**: dwells days per stage; badges turn turmeric/seal at 15/30/45 days.
3. **Audit verification**: Click "Verify audit chain" on any application; the system recomputes SHA‑256 hashes and reports integrity.
4. **Escalation actions** (if on‑call):
   - Manually set L1/L2/L3 escalation flags (admin only).
   - Add remarks to any audit entry.
5. **Search**: Filter by institution, application number, status, or extraction status.

**Login for regional officer**: `ro.mumbai@aicte.gov.in` / `veriflow@2026`.

### 6.7. Uploading a Lease Deed

1. In any workspace, find the docket card for your application.
2. Click **Upload document** → select a PDF (or image) file.
3. The frontend sends the file to `POST /api/v1/documents/{id}/upload`.
4. Backend:
   - Stores the PDF locally (path in `s3_url` = `local://{app.id}/registered-lease-deed.pdf`).
   - Triggers Gemini extraction (`GeminiLeaseExtractor`).
   - Updates `Document.extraction_status` based on the model's response.
   - Shows a toast: `"Docket moved to ${STATUS_META[result.to_status].label}"` if a transition happened concurrently.
5. After upload, revisit the docket: the extraction badge appears. If it says **Extracted**, the Rule 1 gate is now open and transition buttons become enabled.

### 6.8. Adding Decision Remarks

Every transition allows an optional `remarks` field (free‑text). These are stored in:
- `Application.decision_remarks` (if terminal status).
- `AuditLog.payload.remarks` (for every stage transition).
- Visible on the dashboard and in the audit‑chain verification view.

---

## 7. All Features Summary

| Feature | Where it Lives | Description |
|---|---|---|
| **Application creation** | `POST /api/v1/applications` | Starts at `SCRUTINY`; `stage_entry_timestamp` = now (Rule 3). |
| **Document upload** | Drag‑and‑drop on docket | Triggers Gemini extraction; stores PDF; updates `extraction_status`. |
| **Gemini lease extraction** | `backend/app/services/gemini.py` | `google-genai` → `gemini-3.6‑flash`; extracts 4 fields + confidence. |
| **Rule 1 lease gate** | `backend/app/services/workflow.py` | Hard block before any Scrutiny→EVC/SAC transition; verdicts: valid/missing/not_extracted/etc. |
| **State machine** | `allowed_transitions()` | Legal next states per current status + application type (NEW/EXPANSION need EVC). |
| **SLA dwell tracking** | `backend/app/core/config.py` + dashboard | 15/30/45‑day thresholds → L1/L2/L3 escalation badges. |
| **Audit chain** | `backend/app/services/audit.py` + `integrity.py` | Every action writes a SHA‑256 chained `AuditLog`; verifiable via `AuditService.verify()`. |
| **Role‑based workspaces** | `frontend/components/auth/` + `ROLE_META` | Each officer sees only their queue; regional officer sees all. |
| **Transition API** | `POST /workspace/applications/{id}/transition` | Body: `{to_status: "evc" | "sac" | "shc" | "approved" | "rejected"}`. Validates permissions, Rule 1, commits audit. |
| **Decision remarks** | `application.decision_remarks` + audit payload | Free‑text stored per transition; visible on dashboard. |
| **Demo accounts** | `backend/app/db/seed.py` + `DEMO_PASSWORD` | All share `veriflow@2026`; emails listed in `OFFICERS` table. |
| **CORS configuration** | `backend/app/core/config.py` → `cors_origins` | Must include both `http://localhost:3000` and `http://127.0.0.1:3000`; otherwise API calls are blocked. |
| **Gemini key** | `backend/.env` → `GEMINI_API_KEY` (git‑ignored, server‑side only) + `GEMINI_MODEL` | Key length 53 chars (starts `AQ.`); model default `gemini-3.6-flash`. |
| **Search & filter** | `frontend/lib/queries/` + dashboard | Filter by institution, status, extraction status, SLA breach. |
| **Export / verify audit** | `AuditService(db).verify(application.id)` | Re‑computes hashes; returns `valid`/`tampered` flag. |

---

## 8. Appendix — Demo Accounts & Commands

### 8.1. Demo Officer Credentials (from `seed.py`)

| Email | Full Name | Designation | Role | Region |
|---|---|---|---|---|
| `scrutiny.officer@aicte.gov.in` | Meera Iyer | Dealing Officer, Scrutiny Cell | `scrutiny_officer` | — |
| `evc.member@aicte.gov.in` | Dr. Arvind Rao | Member, Expert Visit Committee | `evc_member` | — |
| `sac.member@aicte.gov.in` | Prof. Nandita Sen | Member, Standing Approval Committee | `sac_member` | — |
| `shc.member@aicte.gov.in` | K. Menon | Chairperson, Standing Hearing Committee | `shc_member` | — |
| `ro.mumbai@aicte.gov.in` | Rakesh Deshmukh | Regional Officer, Western Region | `regional_officer` | Maharashtra |

**Password** (all): `veriflow@2026` (set as `DEMO_PASSWORD` in `backend/.env`).

### 8.2. Useful CLI Commands

| Command | Effect |
|---|---|
| `cd backend && .venv/Scripts/python -m app.db.seed` | Seed the demo dataset (creates institutions, applications, dockets, audit entries). |
| `cd backend && .venv/Scripts/python -m app.db.seed --reset` | Drop + recreate schema, then seed (destructive). |
| `cd backend && DATABASE_URL="sqlite:///var/dev.db" CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:3000" nohup .venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > var/backend.log 2>&1 &` | Start the backend with the correct env overrides (CORS + SQLite). |
| `cd frontend && nohup npm run start > /tmp/frontend.log 2>&1 < /dev/null &` | Start the frontend dev server on `:3000`. |
| `curl -s --max-time 10 http://127.0.0.1:8000/health` | Health check: `{"status":"ok","service":"VERIFLOW-AICTE","version":"0.2.0","environment":"development","database":"up"}`. |
| `curl -s --max-time 20 -X POST http://127.0.0.1:8000/api/v1/auth/login -H "Content-Type: application/json" -d '{"email":"ro.mumbai@aicte.gov.in","password":"veriflow@2026"}'` | Login as regional officer; returns JWT token. |
| `curl -s --max-time 10 -X OPTIONS http://127.0.0.1:8000/api/v1/auth/login -H "Origin: http://127.0.0.1:3000" -H "Access-Control-Request-Method: POST" -H "Access-Control-Request-Headers: content-type"` | CORS preflight → should return `200` with `access-control-allow-origin`. |
| `cd backend && .venv/Scripts/python -m pytest -q` | Run all 59 backend tests (must pass). |
| `cd backend && .venv/Scripts/python -c "from app.services.gemini import GeminiLeaseExtractor; from app.core.config import get_settings; s=get_settings(); print('model:', s.gemini_model, 'key_len:', len(s.gemini_api_key or ''))"` | Verify Gemini config picks up the key and model. |

### 8.3. Key Files & Their Purposes

| File | Purpose |
|---|---|
| `backend/app/core/config.py` | `Settings` class (reads `.env`); `gemini_api_key`, `gemini_model`, `cors_origins`, `database_url`, SLA thresholds. |
| `backend/app/services/workflow.py` | State machine (`allowed_transitions`), Rule 1 lease gate, `WorkflowService.transition()`. |
| `backend/app/services/gemini.py` | `GeminiLeaseExtractor` — wraps `google-genai` → `gemini‑3.6‑flash`; prompt + schema validation. |
| `backend/app/services/compliance.py` | `evaluate_live_lease()` → `LeaseVerdict`; checks dates, area, survey numbers, term vs. course. |
| `backend/app/services/audit.py` | `AuditService` — writes SHA‑256 chained `AuditLog` entries; `verify()` recomputes integrity. |
| `frontend/lib/constants.ts` | All enums, badges, labels, stage metadata, role metadata, API base URL. |
| `frontend/components/auth/login-view.tsx` | Login page with 5‑phase visual, demo‑account query, role‑based redirect. |
| `frontend/workspace/` | per‑phase dashboards (docket list, transition buttons, SLA monitor). |
| `backend/.env` | **Do not commit** — contains `GEMINI_API_KEY` (53‑char secret), `GEMINI_MODEL`, `DATABASE_URL`, `CORS_ORIGINS`. Git‑ignored. |
| `.env.example` | Template for new deployments; documents `GEMINI_API_KEY` (blank) and `GEMINI_MODEL`. |
| `requirements.txt` (line 25) | `google-genai>=1.0.0,<2.0.0 # official Gemini SDK (gemini-3.6‑flash)` |
| `backend/tests/test_gemini.py` + `test_api.py` | 59 tests total; must all pass after any code change. |

---

## Document Colophon

- All code snippets are extracted from the live codebase (October 2026).
- The Gemini model was verified on‑live: `gemini‑3.6‑flash` responds in ~11s; 3.7/3.8 returned 503/504 under demand; 3.5‑flash also works but is slower.
- CORS was fixed mid‑development: `CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000`.
- The Gemini API key (`GEMINI_API_KEY`) is 53 characters, starts with `AQ.`, and is stored in `backend/.env` (git‑ignored, never sent to the browser).
- All 59 backend tests pass after the Gemini‑model migration (`gemini‑2.5‑flash` → `gemini‑3.6‑flash`).

---

*End of guide. For a PDF, copy this markdown into your editor and export, or use a markdown→PDF tool.*