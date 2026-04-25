"""validator.polarity — direction-word consistency."""
from __future__ import annotations

POSITIVE = {
    "beat", "raise", "raised", "raises", "raising",
    "上调", "超预期", "上修", "上扬", "强劲", "扩张",
}
NEGATIVE = {
    "miss", "missed", "cut", "cuts", "cutting",
    "下调", "不及预期", "下修", "下挫", "疲软", "收缩",
}


def _polarity(text: str) -> str | None:
    t = text.lower()
    pos = any(w.lower() in t for w in POSITIVE)
    neg = any(w.lower() in t for w in NEGATIVE)
    if pos and not neg:
        return "positive"
    if neg and not pos:
        return "negative"
    if pos and neg:
        return "mixed"
    return None


def validate_polarity(
    *,
    answer_text: str,
    excerpt_text: str,
) -> tuple[bool, str | None]:
    a = _polarity(answer_text)
    e = _polarity(excerpt_text)
    # Only flag if BOTH sides have an unambiguous polarity and they disagree.
    if a is None or e is None or a == "mixed" or e == "mixed":
        return True, None
    if a != e:
        return False, f"polarity:mismatch:answer={a},excerpt={e}"
    return True, None
