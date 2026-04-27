from __future__ import annotations

from briefalpha_api.research.worker import _build_mention_map, _detect_tickers


def test_research_ticker_detection_uses_aliases() -> None:
    mention_map = _build_mention_map({"NVDA", "0700.HK", "TLT"})

    found = _detect_tickers(
        "NVIDIA data center growth and Tencent buybacks matter more than noise.",
        mention_map=mention_map,
    )

    assert found == ["0700.HK", "NVDA"]
