from briefalpha_api.fixtures.brief import get_demo_brief, get_demo_source_health


def test_fixture_has_system_envelope():
    b = get_demo_brief()
    assert b["system"]["mode"] == "demo"
    assert b["system"]["status"] == "ready"
    assert b["system"]["data_quality"] == "fixture"


def test_fixture_macro_pulse_has_8_items():
    items = get_demo_brief()["macro_pulse"]
    assert len(items) == 8
    for item in items:
        assert {"name", "value", "delta", "threshold", "status"} <= set(item.keys())
        assert item["status"] in {"ok", "watch", "alert"}


def test_fixture_judgements_have_review_field():
    judgements = get_demo_brief()["judgements"]
    j1 = next(j for j in judgements if j["id"] == "j1")
    assert j1["review"] is not None
    assert j1["review"]["reason"] == "source_conflict"
    assert j1["review"]["status"] == "open"
    j2 = next(j for j in judgements if j["id"] == "j2")
    assert j2["review"] is None


def test_fixture_evidence_uses_internal_demo_scheme():
    for j in get_demo_brief()["judgements"]:
        for ev in j["evidence"]:
            assert ev["link_kind"] == "internal_demo"
            assert ev["source_link"].startswith("briefalpha://demo/")
        for sup in j["supplementary_sources"]:
            assert sup["link_kind"] == "internal_demo"
            assert sup["source_link"].startswith("briefalpha://demo/")


def test_fixture_playbook_events_have_related_evidence():
    for ev in get_demo_brief()["playbook_events"]:
        assert isinstance(ev["related_evidence_ids"], list)
        assert all(isinstance(x, str) for x in ev["related_evidence_ids"])


def test_fixture_source_health_rows_marked_demo():
    sh = get_demo_source_health()
    assert all(row["is_demo"] is True for row in sh["rows"])
