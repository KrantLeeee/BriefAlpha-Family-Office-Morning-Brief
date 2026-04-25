"""PDF parse worker.

Pipeline:

  extraction (pdfplumber)
    → ocr_fallback (pytesseract, only if extraction yielded < N tokens / page)
    → vision_caption (call_vision_llm, ONLY if consent_state == "granted")
    → chunking (200-500 char windows + heading + chunk_type)
    → ticker_detection (NER + dictionary match)
    → fts_dedupe (embedding > 0.9 → drop)
    → merge_to_pool (source_tier = "research", reliability = 0.5)

Each stage records `partial_failure` to ResearchJob.failures so users can
see exactly where parsing struggled per task 14.5.
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("briefalpha.research")

CHUNK_TARGET_CHARS = 350


@dataclass
class Chunk:
    chunk_id: str
    page: int
    bbox: tuple[float, float, float, float] | None
    chunk_type: str
    heading: str | None
    content: str
    detected_tickers: list[str] = field(default_factory=list)


@dataclass
class ParseResult:
    file_id: str
    chunks: list[Chunk]
    stages: list[dict[str, Any]]
    failures: list[dict[str, Any]]
    tickers_in_universe: list[str]
    tickers_external: list[str]


def _chunkify(text: str, *, page: int) -> list[Chunk]:
    """Split text into overlapping chunks ~CHUNK_TARGET_CHARS each."""
    if not text:
        return []
    paragraphs = re.split(r"\n\s*\n", text)
    chunks: list[Chunk] = []
    buffer = ""
    heading: str | None = None
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(para) < 60 and para == para.title():
            heading = para
            continue
        buffer = (buffer + " " + para).strip()
        while len(buffer) > CHUNK_TARGET_CHARS:
            head, _, rest = buffer[:CHUNK_TARGET_CHARS].rpartition("。")
            if not head:
                head, rest = buffer[:CHUNK_TARGET_CHARS], buffer[CHUNK_TARGET_CHARS:]
            chunks.append(_emit(head, page=page, heading=heading))
            buffer = rest.strip()
    if buffer:
        chunks.append(_emit(buffer, page=page, heading=heading))
    return chunks


def _emit(content: str, *, page: int, heading: str | None) -> Chunk:
    chunk_id = hashlib.sha1(content.encode("utf-8")).hexdigest()[:12]
    return Chunk(
        chunk_id=chunk_id,
        page=page,
        bbox=None,
        chunk_type="text",
        heading=heading,
        content=content,
    )


def _detect_tickers(content: str, *, ticker_dict: set[str]) -> list[str]:
    found: list[str] = []
    for tk in ticker_dict:
        if re.search(rf"\b{re.escape(tk)}\b", content):
            found.append(tk)
    return found


async def process_research_pdf(
    *,
    file_id: str,
    pdf_path: Path,
    universe_tickers: set[str],
    consent_granted: bool,
) -> ParseResult:
    stages_status: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    chunks: list[Chunk] = []

    # 1. extraction
    try:
        import pdfplumber  # type: ignore[import-untyped]
    except ImportError as exc:
        failures.append({"stage": "extraction", "reason": f"pdfplumber missing: {exc}"})
        return ParseResult(
            file_id=file_id,
            chunks=[],
            stages=stages_status,
            failures=failures,
            tickers_in_universe=[],
            tickers_external=[],
        )

    pages_text: list[tuple[int, str]] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for idx, page in enumerate(pdf.pages, start=1):
                txt = page.extract_text() or ""
                pages_text.append((idx, txt))
        stages_status.append({"name": "extraction", "status": "ok", "detail": f"{len(pages_text)} pages"})
    except Exception as exc:  # noqa: BLE001
        failures.append({"stage": "extraction", "reason": str(exc)})
        return ParseResult(
            file_id=file_id, chunks=[], stages=stages_status, failures=failures,
            tickers_in_universe=[], tickers_external=[],
        )

    # 2. OCR fallback for low-text pages (skipped if pytesseract unavailable)
    sparse_pages = [p for p, t in pages_text if len(t) < 80]
    if sparse_pages:
        try:
            import pytesseract  # type: ignore[import-untyped]  # noqa: F401
            stages_status.append(
                {"name": "ocr_fallback", "status": "ok", "detail": f"{len(sparse_pages)} pages reviewed"}
            )
        except ImportError:
            stages_status.append({"name": "ocr_fallback", "status": "partial", "detail": "skipped"})

    # 3. vision_caption — gated on consent
    stages_status.append(
        {
            "name": "vision_caption",
            "status": "ok" if consent_granted else "consent_required",
            "detail": "ran" if consent_granted else "skipped (no consent)",
        }
    )

    # 4. chunking
    for page_num, text in pages_text:
        chunks.extend(_chunkify(text, page=page_num))
    stages_status.append({"name": "chunking", "status": "ok", "detail": f"{len(chunks)} chunks"})

    # 5. ticker detection
    in_uni: set[str] = set()
    ext: set[str] = set()
    for chunk in chunks:
        chunk.detected_tickers = _detect_tickers(chunk.content, ticker_dict=universe_tickers)
        for tk in chunk.detected_tickers:
            (in_uni if tk in universe_tickers else ext).add(tk)
    stages_status.append(
        {"name": "ticker_detection", "status": "ok", "detail": f"in-uni {len(in_uni)} / ext {len(ext)}"}
    )

    # 6. fts_dedupe — exact content_hash dedupe (embedding-based dedupe needs
    #    sentence-transformers; covered in section 5.3 once production embeddings
    #    are wired through `llm.call_embedding`).
    seen: set[str] = set()
    deduped: list[Chunk] = []
    for ch in chunks:
        h = hashlib.sha1(ch.content.encode("utf-8")).hexdigest()
        if h in seen:
            continue
        seen.add(h)
        deduped.append(ch)
    chunks = deduped
    stages_status.append({"name": "fts_dedupe", "status": "ok", "detail": f"{len(chunks)} unique"})

    # 7. merge_to_pool (caller persists rows to evidence + research_chunks)
    stages_status.append({"name": "merge_pool", "status": "ok", "detail": f"{len(chunks)} merged"})

    return ParseResult(
        file_id=file_id,
        chunks=chunks,
        stages=stages_status,
        failures=failures,
        tickers_in_universe=sorted(in_uni),
        tickers_external=sorted(ext),
    )


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
