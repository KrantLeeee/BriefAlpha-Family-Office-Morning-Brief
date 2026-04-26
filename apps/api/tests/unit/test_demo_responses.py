import pytest

from briefalpha_api.qa.demo_responses import lookup


@pytest.mark.parametrize("question,expected_substring", [
    ("hi", "demo 模式"),
    ("hello there", "demo 模式"),
    ("你好", "demo 模式"),
    ("总结今日要点", "今日"),
    ("NVDA 为什么", "NVDA"),
    ("英伟达指引", "NVDA"),
    ("腾讯回购", "0700"),
    ("Fed Williams", "Williams"),
    ("待复核是什么", "待复核"),
    ("evidence 链接", "briefalpha://demo/"),
    ("How do I switch modes", "demo / live"),
    ("macro pulse", "8 项指标"),
])
def test_lookup_returns_canned_answer_for_known_keywords(question, expected_substring):
    answer = lookup(question)
    assert answer is not None
    assert expected_substring in answer


def test_lookup_returns_none_for_unknown_question():
    assert lookup("asdfqwerty random gibberish") is None


def test_lookup_is_case_insensitive():
    a = lookup("NVDA")
    b = lookup("nvda")
    assert a == b
