from briefalpha_api.pipeline.artifact import (
    _build_deep_read,
    _build_evidence_card,
    _build_playbook_events,
)


def test_evidence_card_stamps_link_kind_external():
    raw = {
        "evidence_id": "ev_x",
        "raw_source_url": "https://www.sec.gov/x",
        "title": "t",
        "excerpt": "e",
        "source_name": "SEC",
        "published_at": "2026-04-25T10:00:00Z",
    }
    card = _build_evidence_card(raw, 1)
    assert card["link_kind"] == "external"


def test_evidence_card_stamps_link_kind_internal_demo():
    raw = {
        "evidence_id": "ev_x",
        "source_link": "briefalpha://demo/ev_x",
        "title": "t",
        "excerpt": "e",
        "source_name": "demo",
        "published_at": "",
    }
    card = _build_evidence_card(raw, 1)
    assert card["link_kind"] == "internal_demo"


def test_evidence_card_stamps_link_kind_unavailable_when_no_url():
    raw = {
        "evidence_id": "ev_x",
        "title": "t",
        "excerpt": "e",
        "source_name": "x",
        "published_at": "",
    }
    card = _build_evidence_card(raw, 1)
    # source_link defaults to "#"; that maps to unavailable
    assert card["link_kind"] == "unavailable"


def test_evidence_card_converts_yfinance_to_external_yahoo_url():
    raw = {
        "evidence_id": "ev_x",
        "raw_source_url": "yfinance://AAPL",
        "title": "t",
        "excerpt": "e",
        "source_name": "yfinance",
        "published_at": "",
    }
    card = _build_evidence_card(raw, 1)
    assert card["link_kind"] == "external"
    assert card["source_link"] == "https://finance.yahoo.com/quote/AAPL"


def test_playbook_events_derive_related_evidence_from_related_judgements():
    events = _build_playbook_events(
        stage_c={
            "playbook_events": [
                {
                    "time_hkt": "21:30",
                    "label": "美股开盘观察 AAPL",
                    "detail": "观察成交量",
                    "related_judgement_ids": ["j1"],
                }
            ]
        },
        stage_b={"judgements": [{"rank": 1, "cited_evidence_ids": ["ev_aapl"]}]},
    )
    assert events[0]["related_evidence_ids"] == ["ev_aapl"]


def test_playbook_events_sort_by_beijing_time_and_recompute_next():
    events = _build_playbook_events(
        stage_c={
            "playbook_events": [
                {"time_hkt": "21:30", "label": "US open", "detail": "d"},
                {"time_hkt": "09:30", "label": "HK open", "detail": "d"},
            ]
        },
        stage_b=None,
    )
    assert [ev["time_hkt"] for ev in events] == ["09:30", "21:30"]
    assert events[0]["is_next"] is True
    assert events[1]["is_next"] is False


def test_deep_read_trail_features_cited_total_reflects_selected_pool():
    """Trail rows highlight what the LLM cited (`ev_cited` first), but the
    total reflects the brief's evidence base (`selected`) so it aligns
    with the source-health table on the same row of the layout. The old
    behavior surfaced just the citation count, which read as a fixture
    decoration when source-health reported many more raw items."""
    full = [
        {
            "evidence_id": "ev_cited",
            "source_tier": "news",
            "source_name": "finnhub",
            "title": "cited",
            "published_at": "2026-04-27T08:00:00+00:00",
            "raw_source_url": "https://example.com/cited",
        },
        {
            "evidence_id": "ev_raw",
            "source_tier": "official",
            "source_name": "sec",
            "title": "raw only",
            "published_at": "2026-04-27T07:00:00+00:00",
            "raw_source_url": "https://example.com/raw",
        },
    ]
    deep = _build_deep_read(
        selected=full,
        full=full,
        stage_a={"cited_evidence_ids": ["ev_cited"]},
        stage_b=None,
        stage_c=None,
    )

    assert deep["evidence_total"] == 2  # selected pool, not citation count
    assert deep["evidence_trail"][0]["label"] == "finnhub · cited"
