"""User-facing ticker display helpers.

Internal storage and UI payloads both keep canonical ticker codes such as
``0700.HK``. Avoid global text replacement: short numeric fragments like
``5.0%`` are too easy to confuse with HK stock codes.
"""
from __future__ import annotations

from typing import Any


def display_name_for_ticker(ticker: str) -> str:
    return ticker


def display_text(value: str) -> str:
    return value


def display_tree(value: Any, *, _key: str | None = None) -> Any:
    return value
