import pytest

from briefalpha_api.pipeline.artifact import classify_link_kind


@pytest.mark.parametrize("url,expected", [
    # external — public URLs
    ("https://www.sec.gov/Archives/edgar/foo", "external"),
    ("http://example.com", "external"),
    ("https://www1.hkexnews.hk/listedco/listconews/sehk/x.htm", "external"),
    # internal_demo — fixture URL scheme
    ("briefalpha://demo/ev_nvda_8k", "internal_demo"),
    ("briefalpha://demo/anything", "internal_demo"),
    # internal_research — internal viewer routes
    ("research://abc-123", "internal_research"),
    ("yfinance://NVDA", "internal_research"),
    # unavailable
    ("", "unavailable"),
    (None, "unavailable"),
    ("#", "unavailable"),
    # unknown scheme falls through to unavailable
    ("ftp://x", "unavailable"),
    ("data:text/plain;base64,xxx", "unavailable"),
])
def test_classify_link_kind(url, expected):
    assert classify_link_kind(url) == expected
