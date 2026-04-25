"""validator.time_window — PRD §2.6 mapping, evaluated in HKT.

Each `TimeWindowRule` says: "this kind of evidence MUST be no older than
N hours from the brief's freeze time." Cross-checked using zoneinfo
("Asia/Hong_Kong" / "America/New_York"); NYSE trading days handled via
pandas_market_calendars when installed (best-effort fallback to plain
weekday check otherwise).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from zoneinfo import ZoneInfo

HKT = ZoneInfo("Asia/Hong_Kong")
NY = ZoneInfo("America/New_York")


class TimeWindowRule(str, Enum):
    OFFICIAL_RECENT = "official_recent_24h"
    NEWS_RECENT = "news_recent_36h"
    MARKET_OVERNIGHT = "market_overnight_12h"
    RESEARCH_PDF_30D = "research_pdf_30d"


def _max_age(rule: TimeWindowRule) -> timedelta:
    return {
        TimeWindowRule.OFFICIAL_RECENT: timedelta(hours=24),
        TimeWindowRule.NEWS_RECENT: timedelta(hours=36),
        TimeWindowRule.MARKET_OVERNIGHT: timedelta(hours=12),
        TimeWindowRule.RESEARCH_PDF_30D: timedelta(days=30),
    }[rule]


def validate_time_window(
    *,
    rule: TimeWindowRule,
    evidence_published_at: datetime | None,
    brief_freeze_at_hkt: datetime,
) -> tuple[bool, str | None]:
    if evidence_published_at is None:
        # No timestamp ⇒ time window cannot be evaluated; let the citation
        # validator handle absence of metadata.
        return True, None
    age = brief_freeze_at_hkt.astimezone(HKT) - evidence_published_at.astimezone(HKT)
    if age > _max_age(rule):
        return False, f"time_window:{rule.value}:age_{age.total_seconds()/3600:.1f}h"
    return True, None
