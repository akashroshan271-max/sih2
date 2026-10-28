"""
Patch the SIH2 PPT PDF into a corrected deck.

The text changes are page-specific. Page indices here are 0-based:
  0 = cover/meta
  1 = problem / idea / solution
  2 = technical approach
  3 = feasibility and viability
  4 = impact and benefits
  5 = research and references
"""

from pathlib import Path
from pypdf import PdfReader, PdfWriter


def new_text_for_page(page_index: int, original_text: str) -> str:
    # Page 2 (index 1): problem / idea / solution
    if page_index == 1:
        fixed = original_text
        fixed = fixed.replace(
            "Compilance Monitoring and Alert Management System",
            "Compliance Monitoring and Alert Management System",
        )
        fixed = fixed.replace(
            "A unified, handbook-aware digital orchestration engine\r\n"
            "featuring deterministic state machines, real-time pendency\r\n"
            "tracking, and proactive document compliance validation.",
            "A handbook-aware orchestration layer that routes applications across\r\n"
            "Scrutiny, EVC, SAC/SHC, validates lease and live-lease evidence, tracks\r\n"
            "stage-wise pendency, and keeps role-based views for institutions, officers,\r\n"
            "and committees.",
        )
        fixed = fixed.replace(
            "Handbook-Trained State Machine: Enforces deterministic\r\n"
            "regulatory logic.",
            "Rule-driven stage machine: enforces the permitted Scrutiny -> EVC ->\r\n"
            "SAC/SHC transition logic.",
        )
        fixed = fixed.replace(
            "Live Lease Compliance Guard: Real-time expiry and\r\n"
            "duration validation.",
            "Live Lease Compliance Guard: validates lease status, expiry, and\r\n"
            "APH-linked lease conditions before approval.",
        )
        fixed = fixed.replace(
            "Clause-Linked Evidence Auditing: Connects extracted data\r\n"
            "directly to APH clauses.",
            "Clause-Linked Evidence Auditing: ties extraction and rule outcomes to\r\n"
            "traceable APH clause evidence in the audit trail.",
        )
        fixed = fixed.replace(
            "Human-in-the-Loop Safeguards: Automates triage while\r\n"
            "preserving statutory discretion.",
            "Human-in-the-Loop Safeguards: automates triage but keeps officer\r\n"
            "approval, rejection, and exception discretion intact.",
        )
        return fixed

    # Page 3 (index 2): technical approach
    if page_index == 2:
        fixed = original_text
        fixed = fixed.replace(
            "Next.js 14 & React 18: Officer dashboards and application\r\n"
            "workspaces",
            "React / Next.js-style dashboards and application workspaces (TypeScript,\r\n"
            "Tailwind CSS)",
        )
        fixed = fixed.replace(
            "XState: FSM orchestrating handbook-compliant, multi-stage\r\n"
            "transition logic.",
            "Server-side deterministic Python transition engine drives allowed stage\r\n"
            "changes; the client UI mirrors those transitions.",
        )
        fixed = fixed.replace(
            "PostgreSQL: Relational database for workflows, users, and state\r\n"
            "logs.",
            "Relational database for workflows, users, and state logs (SQLite in the\r\n"
            "current prototype; PostgreSQL intended for deployment).",
        )
        fixed = fixed.replace(
            "Redis & Celery: Async background task queue & proactive SLA\r\n"
            "timers.",
            "Background SLA scanning and task queue designed for Celery/Redis (plan\r\n"
            "for scheduled dwell-time alerts).",
        )
        fixed = fixed.replace(
            "MinIO / AWS S3: High-capacity encrypted storage for deeds, videos.",
            "Document storage designed for S3/MinIO-style backend (plan for secure,\r\n"
            "high-volume deed archives).",
        )
        fixed = fixed.replace(
            "Google Gemini 2.5 Flash: Multi-modal OCR parsing lease\r\n"
            "dates/NOCs.",
            "Planned AI extraction via a Gemini-class model to turn lease/deed content\r\n"
            "into structured JSON for validation.",
        )
        fixed = fixed.replace(
            "OpenCV: Extract metadata/geotags from inspection logs.",
            "Planned media extraction (e.g. OpenCV) for inspection-log metadata as\r\n"
            "future scope.",
        )
        return fixed

    # Page 4 (index 3): feasibility and viability
    if page_index == 3:
        fixed = original_text
        fixed = fixed.replace(
            "AI Extraction: Gemini 2.5 Flash parses unstructured lease & land\r\n"
            "deeds into strict JSON schemas.",
            "AI Extraction: planned Gemini-style extraction turns unstructured lease and\r\n"
            "land-deed content into strict JSON for validation.",
        )
        fixed = fixed.replace(
            "State Orchestration: Finite State Machine controls transitions\r\n"
            "across Scrutiny, EVC, SAC, and SHC.",
            "State Orchestration: backend transition engine controls permitted moves\r\n"
            "across Scrutiny, EVC, SAC, and SHC.",
        )
        fixed = fixed.replace(
            "Core Tech Stack: Built on Next.js 14, FastAPI, PostgreSQL,\r\n"
            "Celery, and Redis.",
            "Target core stack: React/Next.js-style frontend, FastAPI + Pydantic backend,\r\n"
            "and relational storage with a background task queue.",
        )
        fixed = fixed.replace(
            "Scalable Storage: PostgreSQL indexing paired with S3/MinIO for\r\n"
            "secure, high-volume document archives.",
            "Target storage: relational indexing plus S3/MinIO-style document archives for\r\n"
            "secure, high-volume records.",
        )
        fixed = fixed.replace(
            "Multi-Tier Escalation: Auto-flagging overdue files at 15, 30, and\r\n"
            "45-day intervals.",
            "Multi-Tier Escalation: planned auto-flagging for overdue files at configured\r\n"
            "15/30/45-day intervals; current prototype centers on dashboard alerts.",
        )
        return fixed

    # Page 5 (index 4): impact and benefits
    if page_index == 4:
        fixed = original_text
        fixed = fixed.replace(
            "Scalable Digital Infrastructure: Uses modular APIs, PostgreSQL,\r\n"
            "background processing, and scalable cloud document storage.",
            "Scalable Digital Infrastructure: designed modular APIs, relational storage,\r\n"
            "background SLA scanning, and cloud document storage for future scale.",
        )
        return fixed

    # Page 6 (index 5): research and references
    if page_index == 5:
        fixed = original_text
        fixed = fixed.replace(
            "AI Extraction using Google Gemini 2.5 Flash: converting unstructured lease-document\r\n"
            "content into JSON.",
            "Planned AI extraction using a Gemini-class model: converting unstructured\r\n"
            "lease-document content into structured JSON.",
        )
        fixed = fixed.replace(
            "Dual-Layer FSM: Client-side XState wizards backed by a server-side Python transition\r\n"
            "engine.",
            "Workflow orchestration: server-side Python transition engine enforces allowed\r\n"
            "stage changes; a client-side FSM wizard layer is intended to match it.",
        )
        return fixed

    return original_text


def replace_page_contents(page, new_raw_bytes: bytes) -> None:
    contents = page.get_contents()
    contents.set_data(new_raw_bytes)


def main() -> None:
    src = Path(r"C:\Users\Akash Roshan\Downloads\SIH2 (2).pdf")
    reader = PdfReader(str(src))
    print("INPUT PAGES:", len(reader.pages))

    writer = PdfWriter()
    for i in range(len(reader.pages)):
        writer.add_page(reader.pages[i])

    modified = []
    for i in range(len(reader.pages)):
        contents = writer.pages[i].get_contents()
        old_raw = contents.get_data()
        try:
            old_text = old_raw.decode("latin-1")
        except Exception:
            old_text = old_raw.decode("utf-8", errors="replace")
        new_text = new_text_for_page(i, old_text)
        if new_text != old_text:
            modified.append(i)
            new_raw = new_text.encode("latin-1")
            try:
                new_raw.decode("latin-1")
            except Exception:
                new_raw = old_raw
                print("SKIPPED PAGE", i + 1, "encoding unsafe")
            replace_page_contents(writer.pages[i], new_raw)

    out = Path(r"C:\Users\Akash Roshan\Downloads\SIH2-updated.pptx")
    with out.open("wb") as f:
        writer.write(f)
    print("WROTE UPDATED DECK:", out)
    print("PAGES MODIFIED:", [i + 1 for i in modified])

    check = PdfReader(str(out))
    notes = []
    for i in range(len(check.pages)):
        raw = check.pages[i].get_contents().get_data()
        try:
            txt = raw.decode("latin-1")
        except Exception:
            txt = raw.decode("utf-8", errors="replace")
        if i == 1:
            notes.append("PAGE2_CorrectSpell:" + str("Compliance Monitoring" in txt))
            notes.append(
                "PAGE2_Orchestration:" + str("orchestration layer" in txt)
            )
        if i == 2:
            notes.append(
                "PAGE3_PythonEngine:" + str("Server-side deterministic Python" in txt)
            )
            notes.append("PAGE3_XStateRemoved:" + str("XState" not in txt))
            notes.append(
                "PAGE3_PostgresClarified:" + str("PostgreSQL" not in txt)
            )
        if i == 3:
            notes.append(
                "PAGE4_GeminiPlanned:"
                + str("planned Gemini-style extraction" in txt)
            )
    print("\n".join(notes))


if __name__ == "__main__":
    main()
