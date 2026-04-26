from briefalpha_api.pipeline.artifact import _build_evidence_card


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
