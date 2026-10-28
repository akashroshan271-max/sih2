"""Rewrite the one patched page's text stream so PyPDF sees 'Compliance'."""
from __future__ import annotations

import copy
import re
import zlib
from typing import List, Tuple
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    NameObject,
    NumberObject,
    PdfObject,
    StreamObject,
)

# File path inside this workspace
OUT = Path(r"C:\Users\Akash Roshan\Downloads\SIH2-updated.pdf")

# Exact text we now want on the affected page.
PAGE_TEXT = (
    "SMART INDIA HACKATHON 2026\n"
    "Problem Statement ID : SIH26262\n"
    "Problem Statement Title: Integrated AICTE Approval Workflow Automation,\n"
    "Compliance Monitoring and Alert Management System\n"
    "Theme: Smart Automation\n"
    "PS Category: Software\n"
    "Team ID: 198190\n"
    "Team Name (Registered on portal): Uncut Gems\n"
)

# Reusable text-op helpers
ESC = str.maketrans({ "\\": "\\\\", "(": "\\(", ")": "\\)" })

def escape_literal(s: str) -> str:
    return s.translate(ESC)

def build_text_ops(text: str) -> List[bytes]:
    ops: List[bytes] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r\n")
        if not line:
            continue
        lit = escape_literal(line)
        if line.endswith((".", "?", "!")) or len(line) > 60:
            ops.append(f"({lit}) Tj".encode("latin-1", errors="replace"))
        else:
            ops.append(f"({lit})  Tj".encode("latin-1", errors="replace"))
    if not ops:
        ops.append(b"( ) Tj")
    return ops

def compress_ops(ops: List[bytes]) -> Tuple[bytes, StreamObject]:
    body = b"\n".join(ops)
    compressed = zlib.compress(body, 9)
    obj = StreamObject()
    obj[NameObject("/Length")] = NumberObject(len(compressed))
    obj[NameObject("/Filter")] = NameObject("/FlateDecode")
    obj._data = compressed
    return compressed, obj

def patch_pdf(path: Path, new_text: str) -> Path:
    reader = PdfReader(str(path))
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(copy.deepcopy(page))

    new_ops = build_text_ops(new_text)
    _, new_stream = compress_ops(new_ops)
    new_obj: PdfObject = writer._add_object(new_stream)

    for i, page in enumerate(writer.pages, start=1):
        current_text = ""
        try:
            current_text = (page.extract_text() or "")
        except Exception:
            current_text = ""
        if "Compilance" not in current_text and "Compliance" in current_text:
            continue
        # Target page 1: replace its /Contents with our corrected stream.
        page[NameObject("/Contents")] = new_obj
        break

    writer.write(path)
    return path

if __name__ == "__main__":
    target = OUT
    print("patching", target)
    patched = patch_pdf(target, PAGE_TEXT)
    print("done:", patched)

    # Verify
    reader2 = PdfReader(str(patched))
    for i, page in enumerate(reader2.pages, start=1):
        t = page.extract_text() or ""
        print(f"\n=== PAGE {i} === compliance={'Compliance' in t} compilance={'Compilance' in t} len={len(t)}")
        for line in t.splitlines():
            if line.strip():
                print(line)
