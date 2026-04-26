#!/usr/bin/env python
"""Generate `tests/golden/cases.json` with ≥ 50 synthetic regression cases.

The cases here are HAND-CURATED templates (NOT randomly generated). Each
matches the `RawItem` shape consumed by `tests/golden/runner.py`. Running
this script is idempotent — the output is a stable JSON file that gets
checked in.

Categories (PRD §5.1.3):
  1. earnings (beat / miss / in-line)
  2. policy day (Fed / ECB / BOE)
  3. calm day (light flow)
  4. breaking news (single-source events)
  5. macro (CPI / PCE / NFP / GDP)
  6. HKEX filings (buybacks / dividends / suspensions)
  7. SEC filings (8-K / 10-Q / 13G)
  8. research PDF (sector reports / initiations)
  9. conflict (Reuters vs Bloomberg, official vs news)
  10. (extra) single-source vs multi-source corroboration

Edit the lists below to add / remove cases — re-run the script to refresh
`cases.json`.
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "cases.json"

VERSION = "2026-04-26.1"

# Common timestamps anchored to brief 2026-04-25 freeze window.
TS = {
    # Anchored at an evening "freeze-eve" UTC slot — well within the
    # 24h / 36h / 12h time-window rules.
    "official_evening": "2026-04-24T20:00:00+00:00",
    "official_late": "2026-04-24T21:30:00+00:00",
    "news_evening": "2026-04-24T20:30:00+00:00",
    "news_late": "2026-04-24T22:00:00+00:00",
    "market_close": "2026-04-24T20:45:00+00:00",
    "hkex_morning": "2026-04-24T23:30:00+00:00",
    "asia_open": "2026-04-25T01:30:00+00:00",
    "fetch_default": "2026-04-25T00:30:00+00:00",
    "research_pdf": "2026-04-23T09:00:00+00:00",
}


def _ev(
    *,
    source_name: str,
    source_tier: str,
    source_url: str,
    title: str,
    excerpt: str,
    detected_tickers: list[str],
    asset_class: str | None,
    published_at: str,
    fetched_at: str | None = None,
) -> dict:
    return {
        "source_name": source_name,
        "source_tier": source_tier,
        "source_url": source_url,
        "title": title,
        "excerpt": excerpt,
        "detected_tickers": detected_tickers,
        "asset_class": asset_class,
        "published_at": published_at,
        "fetched_at": fetched_at or TS["fetch_default"],
    }


# ---------------------------------------------------------------------------
# Existing 9 cases — preserved verbatim from the prior cases.json so
# regression baselines don't shift when we run this script.
# ---------------------------------------------------------------------------


PRESERVED_CASES: list[dict] = [
    {
        "id": "earnings_beat_clean",
        "scenario": "earnings",
        "summary": "NVDA earnings beat reported by 4 sources, all directional alignment.",
        "evidence_count": 4,
        "expected": {"judgement_count": 1, "polarity": "positive", "conflict": False},
        "evidence_pool_input": [
            _ev(source_name="sec_edgar", source_tier="official",
                source_url="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001045810&type=8-K",
                title="NVDA 8-K: Q4 revenue beat consensus by 5%",
                excerpt="NVIDIA reported revenue of US$22.1B, beating consensus of US$21.0B by 5%. Data center segment revenue rose 18% sequentially. Guidance raised for Q1.",
                detected_tickers=["NVDA"], asset_class="us_equity",
                published_at="2026-04-24T20:05:00+00:00"),
            _ev(source_name="reuters", source_tier="news",
                source_url="https://www.reuters.com/technology/nvidia-q4-results",
                title="Nvidia beats forecasts, raises guidance",
                excerpt="Reuters: Nvidia beat Q4 expectations and raised forward guidance, citing strong AI infrastructure demand. Shares up 6% afterhours.",
                detected_tickers=["NVDA"], asset_class="us_equity",
                published_at="2026-04-24T20:30:00+00:00", fetched_at="2026-04-25T00:31:00+00:00"),
            _ev(source_name="bloomberg", source_tier="news",
                source_url="https://www.bloomberg.com/news/nvda-q4-beat",
                title="Nvidia beat: data-center revenue up 18%",
                excerpt="Bloomberg: data center revenue rose 18% sequentially, beating Street estimates. Margins expanded. Q1 outlook raised.",
                detected_tickers=["NVDA"], asset_class="us_equity",
                published_at="2026-04-24T20:35:00+00:00", fetched_at="2026-04-25T00:32:00+00:00"),
            _ev(source_name="yfinance", source_tier="market",
                source_url="https://finance.yahoo.com/quote/NVDA",
                title="NVDA after-hours +6.0%",
                excerpt="Last 6%; previous close $920. Volume above 30-day average. Sentiment positive on guidance raise.",
                detected_tickers=["NVDA"], asset_class="us_equity",
                published_at="2026-04-24T20:45:00+00:00", fetched_at="2026-04-25T00:33:00+00:00"),
        ],
    },
    {
        "id": "earnings_miss_with_conflict",
        "scenario": "earnings",
        "summary": "NVDA Q1 guidance cut. Reuters quotes 8%, Bloomberg quotes 10% — flagged conflict.",
        "evidence_count": 4,
        "expected": {"judgement_count": 1, "conflict": True, "requires_review": True},
        "evidence_pool_input": [
            _ev(source_name="sec_edgar", source_tier="official",
                source_url="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001045810&type=8-K",
                title="NVDA 8-K: Q1 guidance cut",
                excerpt="NVIDIA cut Q1 data-center revenue guidance citing supply constraints. Magnitude undisclosed in 8-K.",
                detected_tickers=["NVDA"], asset_class="us_equity",
                published_at="2026-04-24T20:00:00+00:00"),
            _ev(source_name="reuters", source_tier="news",
                source_url="https://www.reuters.com/technology/nvidia-cuts-q1",
                title="Nvidia cuts Q1 guidance by 8%",
                excerpt="Reuters: Nvidia cut Q1 data-center revenue outlook by 8% versus consensus, citing supply constraints. Shares down afterhours.",
                detected_tickers=["NVDA"], asset_class="us_equity",
                published_at="2026-04-24T20:30:00+00:00", fetched_at="2026-04-25T00:31:00+00:00"),
            _ev(source_name="bloomberg", source_tier="news",
                source_url="https://www.bloomberg.com/news/nvda-q1-warn",
                title="Nvidia trims Q1 outlook ~10%",
                excerpt="Bloomberg: Nvidia trimmed Q1 data-center outlook approximately 10% — magnitude differs from Reuters' 8% read.",
                detected_tickers=["NVDA"], asset_class="us_equity",
                published_at="2026-04-24T20:35:00+00:00", fetched_at="2026-04-25T00:32:00+00:00"),
            _ev(source_name="yfinance", source_tier="market",
                source_url="https://finance.yahoo.com/quote/NVDA",
                title="NVDA after-hours -6.0%",
                excerpt="Last -6%; previous close $920. Volume well above 30-day average; selling concentrated post-guidance.",
                detected_tickers=["NVDA"], asset_class="us_equity",
                published_at="2026-04-24T20:45:00+00:00", fetched_at="2026-04-25T00:33:00+00:00"),
        ],
    },
    {
        "id": "policy_day_macro",
        "scenario": "policy",
        "summary": "Williams 'mildly restrictive' speech; rates desk reaction in 3 sources.",
        "evidence_count": 3,
        "expected": {"judgement_count": 1, "asset_class": "us_treasury"},
        "evidence_pool_input": [
            _ev(source_name="fed_speeches", source_tier="official",
                source_url="https://www.newyorkfed.org/newsevents/speeches/2026/wil260424",
                title="Williams: policy 'mildly restrictive'; one more hike on the table",
                excerpt="NY Fed President John Williams said policy is 'mildly restrictive' and a further hike of 25 bps cannot be ruled out if core inflation stalls.",
                detected_tickers=[], asset_class="us_treasury",
                published_at="2026-04-24T18:00:00+00:00"),
            _ev(source_name="reuters", source_tier="news",
                source_url="https://www.reuters.com/markets/williams-mildly-restrictive",
                title="Treasuries sell off after Williams comments",
                excerpt="Reuters: 10-year UST yield rose 6 bps to 4.45%; market pricing one more hike with 38% probability.",
                detected_tickers=["TLT"], asset_class="us_treasury",
                published_at="2026-04-24T19:00:00+00:00", fetched_at="2026-04-25T00:31:00+00:00"),
            _ev(source_name="yfinance", source_tier="market",
                source_url="https://finance.yahoo.com/quote/TLT",
                title="TLT close -1.2%",
                excerpt="TLT closed -1.2%; long-end UST under pressure on hawkish Williams.",
                detected_tickers=["TLT"], asset_class="us_treasury",
                published_at="2026-04-24T20:00:00+00:00", fetched_at="2026-04-25T00:32:00+00:00"),
        ],
    },
    {
        "id": "calm_day_no_priority",
        "scenario": "calm_day",
        "summary": "Light news flow; expected output reverts to base_case + summary only.",
        "evidence_count": 8,
        "expected": {"judgement_count": 0},
        "evidence_pool_input": [
            _ev(source_name="yfinance", source_tier="market",
                source_url="https://finance.yahoo.com/quote/SPY",
                title="SPY +0.10%",
                excerpt="Index flat; volume light; no major sector moves.",
                detected_tickers=["SPY"], asset_class="us_equity",
                published_at="2026-04-24T20:00:00+00:00"),
            _ev(source_name="reuters", source_tier="news",
                source_url="https://www.reuters.com/markets/quiet-session",
                title="Wall Street logs quiet session",
                excerpt="Reuters: equities edged higher in a quiet session; no notable single-stock movers.",
                detected_tickers=[], asset_class="us_equity",
                published_at="2026-04-24T20:30:00+00:00", fetched_at="2026-04-25T00:31:00+00:00"),
        ],
    },
    {
        "id": "breaking_news_singlesource",
        "scenario": "breaking",
        "summary": "Single-source breaking — should mark requires_review until corroborated.",
        "evidence_count": 1,
        "expected": {"requires_review": True},
        "evidence_pool_input": [
            _ev(source_name="newsapi", source_tier="news",
                source_url="https://newsapi.org/breaking/nvda-fab-fire",
                title="Reports of fab fire affecting NVDA supplier",
                excerpt="Single-source report of a fab fire affecting an NVDA supplier; details unconfirmed; awaiting corroboration.",
                detected_tickers=["NVDA"], asset_class="us_equity",
                published_at="2026-04-25T00:15:00+00:00"),
            _ev(source_name="yfinance", source_tier="market",
                source_url="https://finance.yahoo.com/quote/NVDA",
                title="NVDA -0.8% afterhours",
                excerpt="Light afterhours move; volume below average.",
                detected_tickers=["NVDA"], asset_class="us_equity",
                published_at="2026-04-25T00:20:00+00:00"),
        ],
    },
    {
        "id": "macro_pulse_pce",
        "scenario": "macro",
        "summary": "PCE prints in line; macro_pulse only.",
        "evidence_count": 6,
        "expected": {"judgement_count": 0},
        "evidence_pool_input": [
            _ev(source_name="bls_release", source_tier="official",
                source_url="https://www.bls.gov/news.release/pce.htm",
                title="PCE 2.6% YoY, in line",
                excerpt="Headline PCE rose 2.6% YoY, matching consensus; core PCE 2.7% YoY, in line.",
                detected_tickers=[], asset_class="us_treasury",
                published_at="2026-04-25T08:30:00+00:00", fetched_at="2026-04-25T08:35:00+00:00"),
            _ev(source_name="reuters", source_tier="news",
                source_url="https://www.reuters.com/markets/pce-in-line",
                title="PCE in line; markets little changed",
                excerpt="Reuters: PCE in line with expectations; rates and equities little changed post-print.",
                detected_tickers=[], asset_class="us_treasury",
                published_at="2026-04-25T08:45:00+00:00", fetched_at="2026-04-25T08:50:00+00:00"),
        ],
    },
    {
        "id": "hkex_filing_buyback",
        "scenario": "hkex",
        "summary": "Tencent buyback authorization; should pull HKEX 7:30 HKT filing as primary.",
        "evidence_count": 2,
        "expected": {"judgement_count": 1, "primary_source_tier": "official"},
        "evidence_pool_input": [
            _ev(source_name="hkex_filings", source_tier="official",
                source_url="https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0425/2026042500201.pdf",
                title="0700.HK: enlargement of share buyback authorisation",
                excerpt="0700.HK announces enlargement of share buyback authorisation by 50%; aggregate value expanded to HK$200B.",
                detected_tickers=["0700.HK"], asset_class="hk_equity",
                published_at="2026-04-24T23:30:00+00:00", fetched_at="2026-04-25T00:00:00+00:00"),
            _ev(source_name="reuters", source_tier="news",
                source_url="https://www.reuters.com/markets/asia/tencent-buyback",
                title="Tencent expands buyback authorisation",
                excerpt="Reuters: Tencent enlarged buyback authorisation; supportive for HK internet sector valuation.",
                detected_tickers=["0700.HK"], asset_class="hk_equity",
                published_at="2026-04-25T00:05:00+00:00"),
        ],
    },
    {
        "id": "sec_8k_revenue_warn",
        "scenario": "sec",
        "summary": "Revenue warning 8-K — official tier wins primary slot.",
        "evidence_count": 3,
        "expected": {"primary_source_tier": "official"},
        "evidence_pool_input": [
            _ev(source_name="sec_edgar", source_tier="official",
                source_url="https://www.sec.gov/Archives/edgar/data/0000320193/8-k-revenue-warning",
                title="AAPL 8-K: revenue warning",
                excerpt="AAPL filed an 8-K disclosing a Q3 revenue shortfall vs. internal plan; cites currency and demand softness.",
                detected_tickers=["AAPL"], asset_class="us_equity",
                published_at="2026-04-24T20:30:00+00:00"),
            _ev(source_name="reuters", source_tier="news",
                source_url="https://www.reuters.com/technology/aapl-revenue-warning",
                title="Apple warns on Q3 revenue",
                excerpt="Reuters: Apple warned on Q3 revenue, citing currency and softer demand. Shares down afterhours.",
                detected_tickers=["AAPL"], asset_class="us_equity",
                published_at="2026-04-24T20:45:00+00:00", fetched_at="2026-04-25T00:31:00+00:00"),
        ],
    },
    {
        "id": "research_pdf_external_ticker",
        "scenario": "research_pdf",
        "summary": "Goldman PDF mentions BIDU (external) — pool ingests with warning, no universe expansion.",
        "evidence_count": 18,
        "expected": {"external_ticker_warning": True, "auto_expand_universe": False},
        "evidence_pool_input": [
            _ev(source_name="research_pdf", source_tier="research",
                source_url="file://research_pdfs/goldman_china_internet.pdf#page=4",
                title="Goldman China Internet — BIDU initiation",
                excerpt="Goldman initiates BIDU at Buy with HK$165 target; cross-reads bullish for tencent and Alibaba ecosystems.",
                detected_tickers=["BIDU"], asset_class="us_equity",
                published_at="2026-04-23T09:00:00+00:00", fetched_at="2026-04-25T00:00:00+00:00"),
            _ev(source_name="research_pdf", source_tier="research",
                source_url="file://research_pdfs/goldman_china_internet.pdf#page=5",
                title="Goldman China Internet — sector valuations",
                excerpt="China internet sector trades at 14x forward earnings, modest discount to historical average.",
                detected_tickers=[], asset_class="hk_equity",
                published_at="2026-04-23T09:00:00+00:00", fetched_at="2026-04-25T00:00:00+00:00"),
        ],
    },
]


# ---------------------------------------------------------------------------
# Generated cases — 41 more across the 9 categories
# ---------------------------------------------------------------------------


def _earnings(
    cid: str, ticker: str, asset: str, summary: str,
    direction: str, magnitude_pct: int, official_text: str,
    reuters_text: str, bloomberg_text: str, market_pct: float,
) -> dict:
    return {
        "id": cid,
        "scenario": "earnings",
        "summary": summary,
        "evidence_count": 4,
        "expected": {"judgement_count": 1, "polarity": direction, "conflict": False},
        "evidence_pool_input": [
            _ev(source_name="sec_edgar", source_tier="official",
                source_url=f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&q={ticker}",
                title=f"{ticker} 8-K: quarterly result",
                excerpt=official_text,
                detected_tickers=[ticker], asset_class=asset,
                published_at=TS["official_evening"]),
            _ev(source_name="reuters", source_tier="news",
                source_url=f"https://www.reuters.com/markets/{ticker.lower()}-q",
                title=f"{ticker} {direction}: Reuters",
                excerpt=reuters_text,
                detected_tickers=[ticker], asset_class=asset,
                published_at=TS["news_evening"]),
            _ev(source_name="bloomberg", source_tier="news",
                source_url=f"https://www.bloomberg.com/news/{ticker.lower()}-q",
                title=f"{ticker} {direction}: Bloomberg",
                excerpt=bloomberg_text,
                detected_tickers=[ticker], asset_class=asset,
                published_at=TS["news_late"]),
            _ev(source_name="yfinance", source_tier="market",
                source_url=f"https://finance.yahoo.com/quote/{ticker}",
                title=f"{ticker} after-hours {market_pct:+.1f}%",
                excerpt=f"Last {market_pct:+.1f}%; volume above 30-day average. Move concentrated post-results.",
                detected_tickers=[ticker], asset_class=asset,
                published_at=TS["market_close"]),
        ],
    }


def _policy(cid: str, speaker: str, body: str, market_text: str, magnitude_bps: int) -> dict:
    return {
        "id": cid,
        "scenario": "policy",
        "summary": f"{speaker} policy speech; rates desk reaction.",
        "evidence_count": 3,
        "expected": {"judgement_count": 1, "asset_class": "us_treasury"},
        "evidence_pool_input": [
            _ev(source_name="fed_speeches", source_tier="official",
                source_url=f"https://www.federalreserve.gov/speeches/{speaker.lower().replace(' ','_')}",
                title=f"{speaker}: monetary policy outlook",
                excerpt=body,
                detected_tickers=[], asset_class="us_treasury",
                published_at="2026-04-24T18:00:00+00:00"),
            _ev(source_name="reuters", source_tier="news",
                source_url=f"https://www.reuters.com/markets/{speaker.lower().replace(' ','-')}-speech",
                title=f"USTs react to {speaker} comments",
                excerpt=market_text,
                detected_tickers=["TLT"], asset_class="us_treasury",
                published_at=TS["news_evening"]),
            _ev(source_name="yfinance", source_tier="market",
                source_url="https://finance.yahoo.com/quote/TLT",
                title=f"TLT moves {magnitude_bps:+d} bps in yield",
                excerpt=f"TLT yield {magnitude_bps:+d} bps; long-end pressure.",
                detected_tickers=["TLT"], asset_class="us_treasury",
                published_at=TS["market_close"]),
        ],
    }


def _calm_day(cid: str, market: str, summary_text: str) -> dict:
    return {
        "id": cid,
        "scenario": "calm_day",
        "summary": f"Quiet session in {market}; no priority judgments expected.",
        "evidence_count": 2,
        "expected": {"judgement_count": 0},
        "evidence_pool_input": [
            _ev(source_name="yfinance", source_tier="market",
                source_url="https://finance.yahoo.com/quote/SPY",
                title="SPY ±0.05%",
                excerpt=f"{market}: index little changed; sector dispersion minimal; no notable single-stock movers.",
                detected_tickers=["SPY"], asset_class="us_equity",
                published_at=TS["market_close"]),
            _ev(source_name="reuters", source_tier="news",
                source_url="https://www.reuters.com/markets/quiet",
                title=f"{market} closes near unchanged",
                excerpt=summary_text,
                detected_tickers=[], asset_class="us_equity",
                published_at=TS["news_evening"]),
        ],
    }


def _breaking(cid: str, ticker: str, headline: str, body: str) -> dict:
    return {
        "id": cid,
        "scenario": "breaking",
        "summary": f"Single-source breaking on {ticker}; should mark requires_review.",
        "evidence_count": 2,
        "expected": {"requires_review": True},
        "evidence_pool_input": [
            _ev(source_name="newsapi", source_tier="news",
                source_url=f"https://newsapi.org/breaking/{ticker.lower()}-{cid}",
                title=headline,
                excerpt=body,
                detected_tickers=[ticker], asset_class="us_equity",
                published_at="2026-04-25T00:15:00+00:00"),
            _ev(source_name="yfinance", source_tier="market",
                source_url=f"https://finance.yahoo.com/quote/{ticker}",
                title=f"{ticker} -1.0% afterhours",
                excerpt="Afterhours light volume move; awaiting corroboration.",
                detected_tickers=[ticker], asset_class="us_equity",
                published_at="2026-04-25T00:20:00+00:00"),
        ],
    }


def _macro(cid: str, indicator: str, official_excerpt: str, news_excerpt: str) -> dict:
    return {
        "id": cid,
        "scenario": "macro",
        "summary": f"{indicator} release; macro_pulse update.",
        "evidence_count": 2,
        "expected": {"judgement_count": 0},
        "evidence_pool_input": [
            _ev(source_name="bls_release", source_tier="official",
                source_url=f"https://www.bls.gov/news.release/{indicator.lower()}.htm",
                title=f"{indicator} released",
                excerpt=official_excerpt,
                detected_tickers=[], asset_class="us_treasury",
                published_at="2026-04-25T08:30:00+00:00", fetched_at="2026-04-25T08:35:00+00:00"),
            _ev(source_name="reuters", source_tier="news",
                source_url=f"https://www.reuters.com/markets/{indicator.lower()}",
                title=f"{indicator} reaction summary",
                excerpt=news_excerpt,
                detected_tickers=[], asset_class="us_treasury",
                published_at="2026-04-25T08:45:00+00:00", fetched_at="2026-04-25T08:50:00+00:00"),
        ],
    }


def _hkex(cid: str, ticker: str, headline_official: str, body_official: str, news_excerpt: str) -> dict:
    return {
        "id": cid,
        "scenario": "hkex",
        "summary": f"{ticker} HKEX filing — official tier primary.",
        "evidence_count": 2,
        "expected": {"judgement_count": 1, "primary_source_tier": "official"},
        "evidence_pool_input": [
            _ev(source_name="hkex_filings", source_tier="official",
                source_url=f"https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0425/{cid}.pdf",
                title=headline_official,
                excerpt=body_official,
                detected_tickers=[ticker], asset_class="hk_equity",
                published_at=TS["hkex_morning"], fetched_at="2026-04-25T00:00:00+00:00"),
            _ev(source_name="reuters", source_tier="news",
                source_url=f"https://www.reuters.com/markets/asia/{ticker.lower().replace('.','-')}",
                title=f"{ticker} filing — Reuters readout",
                excerpt=news_excerpt,
                detected_tickers=[ticker], asset_class="hk_equity",
                published_at="2026-04-25T00:05:00+00:00"),
        ],
    }


def _sec(cid: str, ticker: str, filing_kind: str, body_official: str, news_excerpt: str) -> dict:
    return {
        "id": cid,
        "scenario": "sec",
        "summary": f"{ticker} {filing_kind} — official tier primary.",
        "evidence_count": 2,
        "expected": {"primary_source_tier": "official"},
        "evidence_pool_input": [
            _ev(source_name="sec_edgar", source_tier="official",
                source_url=f"https://www.sec.gov/Archives/edgar/data/{ticker.lower()}/{filing_kind.lower()}",
                title=f"{ticker} {filing_kind}",
                excerpt=body_official,
                detected_tickers=[ticker], asset_class="us_equity",
                published_at=TS["official_evening"]),
            _ev(source_name="reuters", source_tier="news",
                source_url=f"https://www.reuters.com/technology/{ticker.lower()}-{cid}",
                title=f"{ticker} {filing_kind} — Reuters",
                excerpt=news_excerpt,
                detected_tickers=[ticker], asset_class="us_equity",
                published_at=TS["news_evening"]),
        ],
    }


def _research(cid: str, bank: str, ticker: str, headline: str, body: str) -> dict:
    return {
        "id": cid,
        "scenario": "research_pdf",
        "summary": f"{bank} research PDF on {ticker}.",
        "evidence_count": 2,
        "expected": {"external_ticker_warning": False, "auto_expand_universe": False},
        "evidence_pool_input": [
            _ev(source_name="research_pdf", source_tier="research",
                source_url=f"file://research_pdfs/{bank.lower()}_{ticker.lower()}.pdf#page=4",
                title=headline,
                excerpt=body,
                detected_tickers=[ticker], asset_class="us_equity",
                published_at=TS["research_pdf"], fetched_at="2026-04-25T00:00:00+00:00"),
            _ev(source_name="research_pdf", source_tier="research",
                source_url=f"file://research_pdfs/{bank.lower()}_{ticker.lower()}.pdf#page=5",
                title=f"{bank} appendix — peer comp",
                excerpt=f"Peer comp table; {ticker} trades at modest premium to sector median.",
                detected_tickers=[ticker], asset_class="us_equity",
                published_at=TS["research_pdf"], fetched_at="2026-04-25T00:00:00+00:00"),
        ],
    }


def _conflict(cid: str, ticker: str, source_a_text: str, source_b_text: str) -> dict:
    return {
        "id": cid,
        "scenario": "conflict",
        "summary": f"Two news sources disagree on {ticker} magnitude — should flag conflict.",
        "evidence_count": 3,
        "expected": {"conflict": True, "requires_review": True},
        "evidence_pool_input": [
            _ev(source_name="reuters", source_tier="news",
                source_url=f"https://www.reuters.com/markets/{ticker.lower()}-{cid}",
                title=f"{ticker}: Reuters read",
                excerpt=source_a_text,
                detected_tickers=[ticker], asset_class="us_equity",
                published_at=TS["news_evening"]),
            _ev(source_name="bloomberg", source_tier="news",
                source_url=f"https://www.bloomberg.com/news/{ticker.lower()}-{cid}",
                title=f"{ticker}: Bloomberg read",
                excerpt=source_b_text,
                detected_tickers=[ticker], asset_class="us_equity",
                published_at=TS["news_late"]),
            _ev(source_name="yfinance", source_tier="market",
                source_url=f"https://finance.yahoo.com/quote/{ticker}",
                title=f"{ticker} -2% afterhours",
                excerpt="Afterhours move on conflicting reports; volume elevated.",
                detected_tickers=[ticker], asset_class="us_equity",
                published_at=TS["market_close"]),
        ],
    }


def _single_vs_multi(cid: str, ticker: str, single_text: str) -> dict:
    """Edge: only one source — pipeline must tag as such (no conflict)."""
    return {
        "id": cid,
        "scenario": "single_source",
        "summary": f"Only one source covers {ticker} event.",
        "evidence_count": 1,
        "expected": {"judgement_count": 0, "requires_review": True},
        "evidence_pool_input": [
            _ev(source_name="reuters", source_tier="news",
                source_url=f"https://www.reuters.com/{cid}",
                title=f"{ticker} sole-source coverage",
                excerpt=single_text,
                detected_tickers=[ticker], asset_class="us_equity",
                published_at=TS["news_evening"]),
        ],
    }


GENERATED_CASES: list[dict] = [
    # ----- earnings (6 more) -----
    _earnings(
        "earnings_aapl_inline", "AAPL", "us_equity",
        "AAPL Q2 in-line; muted reaction.",
        "neutral", 0,
        "AAPL reported Q2 revenue of US$95.4B, in line with consensus US$95.0B; iPhone segment flat YoY; services +12%.",
        "Reuters: Apple Q2 in line; services growth at 12%; muted afterhours reaction.",
        "Bloomberg: Apple in line on revenue; iPhone segment flat; afterhours mixed.",
        0.3,
    ),
    _earnings(
        "earnings_msft_beat", "MSFT", "us_equity",
        "MSFT cloud revenue beats — guidance raised.",
        "positive", 7,
        "MSFT reported revenue of US$66.5B, beating consensus US$62.0B by 7%. Azure +29% YoY. Q4 guidance raised.",
        "Reuters: Microsoft Azure +29%; raises Q4 guidance.",
        "Bloomberg: Microsoft tops on cloud growth; outlook raised.",
        4.2,
    ),
    _earnings(
        "earnings_tsla_miss", "TSLA", "us_equity",
        "TSLA delivery miss — margins compressed.",
        "negative", 12,
        "TSLA reported deliveries 432K vs consensus 490K, missing by 12%. Auto gross margin 14.3%, below 16% Street.",
        "Reuters: Tesla delivery miss; gross margin 14.3% disappoints.",
        "Bloomberg: Tesla deliveries miss by 12%; margin compression continues.",
        -8.5,
    ),
    _earnings(
        "earnings_googl_beat", "GOOGL", "us_equity",
        "GOOGL ads + cloud beat; afterhours +5%.",
        "positive", 4,
        "GOOGL reported revenue US$95.0B beating US$91.5B by 4%. Ad revenue +14% YoY; Cloud +28%.",
        "Reuters: Alphabet ads +14%, cloud +28%; beat consensus.",
        "Bloomberg: Alphabet ad and cloud strength drive beat.",
        5.0,
    ),
    _earnings(
        "earnings_meta_inline", "META", "us_equity",
        "META in line; capex guide raised.",
        "neutral", 2,
        "META reported revenue US$42.0B in line; capex guide raised to US$80B for 2026 — AI infrastructure build-out.",
        "Reuters: Meta in line on revenue; capex raised.",
        "Bloomberg: Meta capex guide raised; revenue in line.",
        -1.0,
    ),
    _earnings(
        "earnings_amd_beat", "AMD", "us_equity",
        "AMD data center revenue beats; AI accelerator commentary positive.",
        "positive", 6,
        "AMD reported revenue US$7.0B beating US$6.6B by 6%. MI300 ramp on track; data center +51% YoY.",
        "Reuters: AMD data center +51%; MI300 demand strong.",
        "Bloomberg: AMD beat on data center; AI accelerator commentary upbeat.",
        4.8,
    ),
    # ----- policy (5 more) -----
    _policy(
        "policy_powell_cautious",
        "Powell",
        "Powell stressed patience: 'we will be careful' before adjusting policy further; data-dependent posture maintained.",
        "Reuters: 10y UST -3 bps to 4.40%; market reads Powell as marginally dovish vs Williams.",
        -3,
    ),
    _policy(
        "policy_logan_hawkish",
        "Logan",
        "Dallas Fed's Logan said additional tightening 'remains an option' and warned core services inflation 'sticky'.",
        "Reuters: 2y UST +5 bps to 4.92%; pricing for one more hike rises to 42% probability.",
        5,
    ),
    _policy(
        "policy_daly_dovish",
        "Daly",
        "SF Fed's Daly: real rates already restrictive; further hikes risk overshooting on labor market.",
        "Reuters: USTs rally; 10y -4 bps; rate cuts pulled forward to early Q4.",
        -4,
    ),
    _policy(
        "policy_ecb_hold",
        "Lagarde",
        "ECB holds rates at 4.0%; Lagarde emphasizes data-dependence and no pre-commitment to cut path.",
        "Reuters: bunds rally on hold-and-wait read; EUR/USD steady; ECB-priced cuts unchanged.",
        -2,
    ),
    _policy(
        "policy_boe_cut_signal",
        "Bailey",
        "BOE's Bailey signals UK labor market easing supports near-term cut path; growth still subdued.",
        "Reuters: 10y gilts -8 bps; sterling weakens on cut signal; CPI projection unchanged.",
        -8,
    ),
    # ----- calm day (4 more) -----
    _calm_day("calm_day_friday_summer", "US",
              "Friday summer-doldrums session; volume 30% below 30-day average; Russell 2000 +0.04%."),
    _calm_day("calm_day_asia_holiday", "Asia",
              "Asian session muted on Tokyo holiday; HSI +0.2%; KOSPI -0.1%; HSCEI flat."),
    _calm_day("calm_day_pre_fomc", "US",
              "Pre-FOMC session; SPX -0.05%; positioning light into tomorrow's release."),
    _calm_day("calm_day_post_holiday", "US",
              "Post-holiday session; light institutional flow; rate-sensitives mixed."),
    # ----- breaking (5 more) -----
    _breaking("breaking_aapl_recall", "AAPL",
              "Reports of AAPL device recall — battery defect", "Single-source claim of battery-defect recall in latest iPhone batch; manufacturer not yet commented; awaiting corroboration."),
    _breaking("breaking_msft_outage", "MSFT",
              "MSFT Azure regional outage", "Single-source: Azure US-East region experiencing partial outage; service health dashboard not yet updated."),
    _breaking("breaking_tsla_fsd", "TSLA",
              "Reports of NHTSA inquiry into TSLA FSD", "Single-source: NHTSA may open inquiry into Tesla FSD beta; agency not yet confirmed; awaiting press release."),
    _breaking("breaking_googl_antitrust", "GOOGL",
              "Reports of EU antitrust probe expansion", "Single-source: Brussels reportedly expanding antitrust probe to include AI search products; EU not yet confirmed."),
    _breaking("breaking_amd_supply", "AMD",
              "Reports of AMD wafer-supply disruption", "Single-source: TSMC reportedly facing temporary capacity allocation issue affecting AMD orders; both companies declined comment."),
    # ----- macro (5 more) -----
    _macro("macro_cpi_inline", "CPI",
           "Headline CPI rose 3.0% YoY, matching consensus; core CPI 3.4% YoY, in line.",
           "Reuters: CPI in line; rates desk shrugs; equities flat."),
    _macro("macro_cpi_hot", "CPI_hot",
           "Headline CPI rose 3.4% YoY vs consensus 3.1%; core CPI 3.7% YoY vs 3.5% expected — hot print.",
           "Reuters: hotter CPI; 2y UST +9 bps; rate cut expectations pushed to 2027."),
    _macro("macro_nfp_strong", "NFP",
           "Nonfarm payrolls +320K vs consensus +180K; unemployment 3.7% vs 3.9%; AHE +0.4% MoM.",
           "Reuters: stronger NFP; rates sell off; equities mixed on hawkish read."),
    _macro("macro_ism_weak", "ISM",
           "ISM Manufacturing 47.2 vs consensus 49.0 — fifth consecutive contraction reading.",
           "Reuters: manufacturing weakness persists; cyclicals underperform; bonds bid."),
    _macro("macro_jobless_rising", "ICSA",
           "Initial jobless claims 248K vs 215K consensus; 4-week MA rising; subtle labor-market loosening.",
           "Reuters: jobless rising; soft-landing narrative gets fresh support."),
    # ----- HKEX (4 more) -----
    _hkex("hkex_baba_special_div", "9988.HK",
          "9988.HK special dividend declared",
          "9988.HK board declared special dividend HK$5.20/share, payable July 2026; aggregate HK$15B return to shareholders.",
          "Reuters: Alibaba special dividend; signals capital return acceleration."),
    _hkex("hkex_meituan_buyback", "3690.HK",
          "3690.HK extends share buyback programme",
          "3690.HK extends share buyback authorisation by HK$30B; programme runs through Q4 2026.",
          "Reuters: Meituan extends buyback; supportive signal for HK consumer-internet sector."),
    _hkex("hkex_xiaomi_dual_listing", "1810.HK",
          "1810.HK dual-listing application filed",
          "1810.HK files dual-listing application on Shanghai STAR Market; targets H2 2026 completion.",
          "Reuters: Xiaomi dual-listing filing; signals onshore-funding diversification."),
    _hkex("hkex_galaxy_suspension", "0027.HK",
          "0027.HK trading suspension pending announcement",
          "0027.HK requests trading suspension pending material price-sensitive announcement; expected resumption next session.",
          "Reuters: Galaxy Entertainment suspension — market awaits announcement."),
    # ----- SEC (4 more) -----
    _sec("sec_aapl_10q", "AAPL", "10-Q",
         "AAPL filed 10-Q with detailed segment breakdown; services gross margin 71.7% vs 70.9% prior quarter.",
         "Reuters: Apple 10-Q reveals services margin expansion."),
    _sec("sec_msft_10k", "MSFT", "10-K",
         "MSFT filed 10-K with FY2026 detail; AI and cloud disclosures expanded; capex commitments US$58B over 2 yrs.",
         "Reuters: Microsoft 10-K shows scale of AI infrastructure spend."),
    _sec("sec_brk_13f", "BRK.B", "13F",
         "BRK.B filed 13F: trimmed AAPL position by 25%; added new financial-services name.",
         "Reuters: Berkshire trims Apple stake by 25%; signals portfolio rebalancing."),
    _sec("sec_googl_8k_settlement", "GOOGL", "8-K",
         "GOOGL filed 8-K disclosing US$1.4B settlement of historical advertising-practices class action.",
         "Reuters: Alphabet settles long-running ad-practices litigation for US$1.4B."),
    # ----- research PDF (4 more) -----
    _research("research_ms_nvda_upgrade", "MorganStanley", "NVDA",
              "Morgan Stanley upgrades NVDA to Overweight with US$1100 PT",
              "Morgan Stanley raises NVDA to Overweight; US$1100 PT (from US$950); cites resilient hyperscaler capex outlook."),
    _research("research_jpm_aapl_neutral", "JPMC", "AAPL",
              "JPMC moves AAPL to Neutral",
              "JPMC moves AAPL to Neutral from Overweight; cites maturing iPhone cycle; PT US$210."),
    _research("research_barclays_msft_ow", "Barclays", "MSFT",
              "Barclays initiates MSFT at Overweight",
              "Barclays initiates MSFT at OW; PT US$520; thesis: AI infrastructure leadership compounds enterprise GTM advantage."),
    _research("research_db_tlt_underweight", "DeutscheBank", "TLT",
              "Deutsche Bank flags long-end UST risk",
              "Deutsche Bank rates strategy: long-end UST exposure looks rich; recommends underweight TLT into Q3 supply."),
    # ----- conflict (4 more) -----
    _conflict("conflict_nvda_growth_rate", "NVDA",
              "Reuters: Nvidia data-center revenue +18% sequentially.",
              "Bloomberg: Nvidia data-center revenue +22% sequentially — reading differs from Reuters' 18%."),
    _conflict("conflict_aapl_iphone_units", "AAPL",
              "Reuters: Apple iPhone units flat YoY at ~52M.",
              "Bloomberg: Apple iPhone units up 4% YoY to ~54M — read differs from Reuters' flat."),
    _conflict("conflict_tsla_deliveries", "TSLA",
              "Reuters: Tesla deliveries 442K — beats consensus 432K.",
              "Bloomberg: Tesla deliveries 432K — misses consensus 442K (estimates differ across sources)."),
    _conflict("conflict_msft_capex", "MSFT",
              "Reuters: Microsoft capex guide raised to US$72B for 2026.",
              "Bloomberg: Microsoft capex guide raised to US$80B for 2026 — significant magnitude divergence."),
    # ----- single-source (4 more) -----
    _single_vs_multi("single_aapl_supplier", "AAPL",
                     "Single-source claim of new AAPL supplier in India; details unconfirmed; only one outlet covers."),
    _single_vs_multi("single_msft_partnership", "MSFT",
                     "Single-source: MSFT in advanced talks for new partnership in healthcare AI; both parties decline comment."),
    _single_vs_multi("single_googl_acquisition", "GOOGL",
                     "Single-source: GOOGL reportedly evaluating SaaS acquisition; awaiting independent corroboration."),
    _single_vs_multi("single_amd_design_win", "AMD",
                     "Single-source: AMD reportedly secured a design win at major hyperscaler; not yet corroborated."),
]


def main() -> None:
    cases = PRESERVED_CASES + GENERATED_CASES
    seen: set[str] = set()
    for c in cases:
        if c["id"] in seen:
            raise SystemExit(f"duplicate case id: {c['id']}")
        seen.add(c["id"])

    payload = {
        "version": VERSION,
        "description": (
            "Curated golden cases for BriefAlpha pipeline regression. Each case "
            "carries an evidence_pool_input snapshot (synthetic RawItem-shaped "
            "dicts) + expected metrics. The runner in `tests/golden/runner.py` "
            "feeds the pool into the 9 pipeline stages, calls Stage A/B/C via "
            "the LLM wrapper (stub provider in CI), runs the validator on each "
            "LLM response, and emits an aggregate metrics report at "
            "`tests/golden/golden_metrics.json`. Regenerate this file with "
            "`python tests/golden/generate_cases.py`."
        ),
        "cases": cases,
    }
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT} ({len(cases)} cases)")


if __name__ == "__main__":
    main()
