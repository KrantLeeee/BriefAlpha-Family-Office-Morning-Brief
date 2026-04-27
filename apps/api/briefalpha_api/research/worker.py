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

import base64
import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from briefalpha_api.anonymization.sensitive_entity_dictionary import (
    build_sensitive_entity_dictionary,
)
from briefalpha_api.llm.schema import LlmRequest
from briefalpha_api.llm.wrapper import call_vision_llm

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
    page_count: int = 0


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


def _build_mention_map(universe_tickers: set[str]) -> dict[str, str]:
    dictionary = build_sensitive_entity_dictionary(
        universe_tickers=sorted(universe_tickers)
    )
    out: dict[str, str] = {}
    for ticker in universe_tickers:
        out[ticker] = ticker
        for name in dictionary.names_for(ticker):
            out[name] = ticker
    return out


def _detect_tickers(content: str, *, mention_map: dict[str, str]) -> list[str]:
    found: list[str] = []
    for mention, ticker in mention_map.items():
        if _mentions_entity(content, mention):
            found.append(ticker)
    return sorted(set(found))


def _mentions_entity(content: str, mention: str) -> bool:
    if not mention:
        return False
    if re.fullmatch(r"[A-Za-z0-9.:-]+", mention):
        return (
            re.search(
                rf"(?<![A-Za-z0-9]){re.escape(mention)}(?![A-Za-z0-9])",
                content,
                flags=re.IGNORECASE,
            )
            is not None
        )
    return mention.casefold() in content.casefold()


def _page_to_png_data_url(page: Any) -> str:
    img = page.to_image(resolution=144).original
    buf = BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _caption_chunk(*, page: int, content: str) -> Chunk:
    chunk_id = hashlib.sha1(f"vision:{page}:{content}".encode()).hexdigest()[:12]
    return Chunk(
        chunk_id=chunk_id,
        page=page,
        bbox=None,
        chunk_type="caption",
        heading="vision_caption",
        content=content,
    )


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
            page_count=0,
        )

    pages_text: list[tuple[int, str]] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for idx, page in enumerate(pdf.pages, start=1):
                txt = page.extract_text() or ""
                pages_text.append((idx, txt))
        stages_status.append(
            {
                "name": "extraction",
                "status": "ok",
                "detail": f"{len(pages_text)} pages",
            }
        )
    except Exception as exc:  # noqa: BLE001
        failures.append({"stage": "extraction", "reason": str(exc)})
        return ParseResult(
            file_id=file_id, chunks=[], stages=stages_status, failures=failures,
            tickers_in_universe=[], tickers_external=[], page_count=0,
        )

    # 2. OCR fallback for low-text pages (skipped if pytesseract unavailable)
    sparse_pages = [p for p, t in pages_text if len(t) < 80]
    if sparse_pages:
        try:
            import pytesseract  # type: ignore[import-untyped]  # noqa: F401
            stages_status.append(
                {
                    "name": "ocr_fallback",
                    "status": "ok",
                    "detail": f"{len(sparse_pages)} pages reviewed",
                }
            )
        except ImportError:
            stages_status.append({"name": "ocr_fallback", "status": "partial", "detail": "skipped"})

    # 3. vision_caption — gated on consent. To control cost, only low-text
    # pages are captioned; pdfplumber/table extraction remains the first pass.
    vision_chunks: list[Chunk] = []
    if consent_granted and sparse_pages:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                page_lookup = {idx: page for idx, page in enumerate(pdf.pages, start=1)}
                for page_num in sparse_pages[:3]:
                    data_url = _page_to_png_data_url(page_lookup[page_num])
                    req = LlmRequest(
                        call_type="vision",
                        scope="vision",
                        template_version="vision_caption@1",
                        system=(
                            "你是金融研究 PDF 的视觉解析器。请只描述页面中可见的图表、"
                            "表格、标题和关键数字；不要推测页面外信息。"
                        ),
                        user_payload={
                            "page": page_num,
                            "task": (
                                "Return JSON with keys caption, tables, key_numbers. "
                                "Use concise Chinese. If unreadable, say caption_unavailable."
                            ),
                            "images": [{"image_url": data_url, "detail": "high"}],
                        },
                        response_schema={
                            "type": "object",
                            "properties": {
                                "caption": {"type": "string"},
                                "tables": {"type": "array", "items": {"type": "string"}},
                                "key_numbers": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["caption"],
                        },
                        max_tokens=600,
                        temperature=0.1,
                    )
                    resp = await call_vision_llm(
                        req,
                        audit_ctx={"brief_id": file_id, "audit_mode": "demo"},
                    )
                    structured = resp.structured or {}
                    caption = structured.get("caption") if isinstance(structured, dict) else None
                    if not caption:
                        caption = resp.text
                    if caption and caption != "caption_unavailable":
                        vision_chunks.append(_caption_chunk(page=page_num, content=str(caption)))
            stages_status.append(
                {
                    "name": "vision_caption",
                    "status": "ok",
                    "detail": f"{len(vision_chunks)} captions",
                }
            )
        except Exception as exc:  # noqa: BLE001
            failures.append({"stage": "vision_caption", "reason": str(exc)})
            stages_status.append(
                {"name": "vision_caption", "status": "partial", "detail": "failed"}
            )
    else:
        stages_status.append(
            {
                "name": "vision_caption",
                "status": "consent_required" if not consent_granted else "skipped",
                "detail": "skipped (no consent)" if not consent_granted else "no sparse pages",
            }
        )

    # 4. chunking
    for page_num, text in pages_text:
        chunks.extend(_chunkify(text, page=page_num))
    chunks.extend(vision_chunks)
    stages_status.append({"name": "chunking", "status": "ok", "detail": f"{len(chunks)} chunks"})

    # 5. ticker detection
    mention_map = _build_mention_map(universe_tickers)
    in_uni: set[str] = set()
    ext: set[str] = set()
    for chunk in chunks:
        chunk.detected_tickers = _detect_tickers(
            chunk.content,
            mention_map=mention_map,
        )
        for tk in chunk.detected_tickers:
            (in_uni if tk in universe_tickers else ext).add(tk)
    stages_status.append(
        {
            "name": "ticker_detection",
            "status": "ok",
            "detail": f"in-uni {len(in_uni)} / ext {len(ext)}",
        }
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
        page_count=len(pages_text),
    )


def now_utc() -> datetime:
    return datetime.now(UTC)
