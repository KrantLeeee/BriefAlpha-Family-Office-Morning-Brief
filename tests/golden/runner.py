"""Golden-set runner.

CI invocation:

    python -m tests.golden.runner

Outputs `golden_metrics.json` with PRD §6.1 + §6.4 indicators:

- citation_locatable_rate
- numbers_consistent_rate
- polarity_consistent_rate
- time_window_consistent_rate
- sensitive_output_pass_rate
- unsafe_generated_alias_count
- conservative_brief_triggered_rate
- no_direct_portfolio_link_rate

The MVP runner stub below loads the case bundle and produces a *target*
metrics structure; live wiring against `pipeline.run_brief` lands once we
finalize the offline fixture format for `evidence_pool_full`.
"""
from __future__ import annotations

import json
from pathlib import Path

CASES_PATH = Path(__file__).parent / "cases.json"
OUTPUT_PATH = Path(__file__).parent / "golden_metrics.json"


def main() -> None:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    metrics = {
        "case_count": len(cases),
        "citation_locatable_rate": None,
        "numbers_consistent_rate": None,
        "polarity_consistent_rate": None,
        "time_window_consistent_rate": None,
        "sensitive_output_pass_rate": None,
        "unsafe_generated_alias_count": 0,
        "conservative_brief_triggered_rate": None,
        "no_direct_portfolio_link_rate": None,
        "todo": "wire pipeline.run_brief here once offline evidence fixtures land",
    }
    OUTPUT_PATH.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
