"""APScheduler cron jobs.

Per design.md §8 + tasks 12.x:

| Cron                      | Action                                              |
|---------------------------|-----------------------------------------------------|
| every weekday 06:50 HKT   | refresh sensitive_entity_dictionary                 |
| every weekday 07:00 HKT   | rolling ingestion                                   |
| every weekday 07:55 HKT   | freeze evidence_pool + run_brief                    |
| every weekday 16:00 HKT   | purge alias_map ciphertext                          |
| every day 03:30 HKT       | clean PDF metadata + audit_log retention sweep      |
| every 5 minutes           | aggregate source_health snapshot to redis           |
| every Monday 04:00 HKT    | refresh SEC + HKEX symbol maps                      |
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from briefalpha_api.anonymization import delete_alias_map
from briefalpha_api.settings import DATA_DIR

log = logging.getLogger("briefalpha.scheduler")
HKT = "Asia/Hong_Kong"


def _purge_alias_maps() -> None:
    """Delete every alias_map ciphertext at 16:00 HKT."""
    folder: Path = DATA_DIR / "alias_maps"
    if not folder.exists():
        return
    for path in folder.glob("*.enc"):
        brief_id = path.stem
        try:
            delete_alias_map(brief_id)
        except Exception as exc:  # noqa: BLE001
            log.warning("alias_map purge failed %s: %s", brief_id, exc)


async def _run_brief_job() -> None:
    # Wired up to pipeline.run when production credentials land.
    log.info("run_brief tick at %s", datetime.now())


async def _refresh_dictionary() -> None:
    log.info("sensitive_entity_dictionary refresh tick")


async def _aggregate_source_health() -> None:
    log.info("source_health aggregation tick")


def build_scheduler(jobstore_url: str | None = None) -> AsyncIOScheduler:
    if jobstore_url is None:
        jobstore_url = f"sqlite:///{DATA_DIR / 'briefalpha.db'}"
    scheduler = AsyncIOScheduler(
        jobstores={"default": SQLAlchemyJobStore(url=jobstore_url)},
        timezone=HKT,
    )

    scheduler.add_job(
        _refresh_dictionary,
        trigger=CronTrigger(day_of_week="mon-fri", hour=6, minute=50),
        id="refresh_sensitive_dict",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_brief_job,
        trigger=CronTrigger(day_of_week="mon-fri", hour=7, minute=0),
        id="rolling_ingestion",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_brief_job,
        trigger=CronTrigger(day_of_week="mon-fri", hour=7, minute=55),
        id="freeze_and_run_brief",
        replace_existing=True,
    )
    scheduler.add_job(
        _purge_alias_maps,
        trigger=CronTrigger(hour=16, minute=0),
        id="purge_alias_maps",
        replace_existing=True,
    )
    scheduler.add_job(
        _aggregate_source_health,
        trigger=CronTrigger(minute="*/5"),
        id="source_health_snapshot",
        replace_existing=True,
    )
    return scheduler
