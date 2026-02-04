#!/usr/bin/env python3
"""Generate signal coverage report from best-bets debug payloads."""
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

BASE_URL = os.getenv("BASE_URL", "https://web-production-7b2a.up.railway.app")
API_KEY = os.getenv("API_KEY", "")
SPORTS = os.getenv("SPORTS", "NBA NHL NFL MLB NCAAB").split()
SKIP_NETWORK = os.getenv("SKIP_NETWORK", "0") == "1"
MAX_GAMES = int(os.getenv("MAX_GAMES", "5"))
MAX_PROPS = int(os.getenv("MAX_PROPS", "5"))

KNOWN_SIGNALS = {
    "HARMONIC",
    "MSRF",
    "SERP",
    "OFFICIALS",
    "PARK",
    "LIVE",
    "GLITCH",
    "GEMATRIA",
    "PHASE8",
    "LUNAR",
    "MERCURY",
    "RIVALRY",
    "STREAK",
    "SOLAR",
}


def _fetch_json(url: str) -> Dict[str, Any]:
    req = Request(url, headers={"X-API-Key": API_KEY})
    with urlopen(req, timeout=60) as resp:
        payload = resp.read().decode("utf-8")
        return json.loads(payload)


def _extract_reason_keys(reasons: List[str]) -> List[str]:
    keys = []
    for reason in reasons:
        if not isinstance(reason, str) or not reason:
            continue
        if ":" in reason:
            key = reason.split(":", 1)[0].strip()
        elif "-" in reason:
            key = reason.split("-", 1)[0].strip()
        else:
            key = reason.strip()
        if key:
            keys.append(key)
    return keys


def _pull_reasons(pick: Dict[str, Any]) -> List[str]:
    reasons = []
    for field in [
        "ai_reasons",
        "research_reasons",
        "esoteric_reasons",
        "jarvis_reasons",
        "context_reasons",
        "confluence_reasons",
        "msrf_reasons",
        "serp_reasons",
        "live_reasons",
    ]:
        reasons.extend(pick.get(field, []) or [])
    return reasons


def main() -> int:
    report = {
        "date_et": datetime.now().strftime("%Y-%m-%d"),
        "base_url": BASE_URL,
        "sports": SPORTS,
        "status": "SKIPPED" if SKIP_NETWORK else "OK",
        "errors": [],
        "signal_counts": {},
        "always_fire": [],
        "never_fire": [],
        "zero_impact_signals": [],
    }

    if SKIP_NETWORK:
        report["errors"].append("SKIP_NETWORK=1")
    elif not API_KEY:
        report["status"] = "ERROR"
        report["errors"].append("API_KEY missing")
    else:
        total_picks = 0
        signal_counter = Counter()
        zero_impact = Counter()

        for sport in SPORTS:
            url = f"{BASE_URL}/live/best-bets/{sport}?debug=1&max_games={MAX_GAMES}&max_props={MAX_PROPS}"
            try:
                data = _fetch_json(url)
            except HTTPError as e:
                report["errors"].append(f"{sport}: HTTP {e.code}")
                continue
            except URLError as e:
                report["status"] = "ERROR"
                report["errors"].append(f"{sport}: {e}")
                continue

            picks = []
            picks.extend((data.get("game_picks") or {}).get("picks", []) or [])
            picks.extend((data.get("props") or {}).get("picks", []) or [])

            for pick in picks:
                total_picks += 1
                reasons = _pull_reasons(pick)
                keys = _extract_reason_keys(reasons)
                for key in keys:
                    signal_counter[key] += 1
                # zero impact checks for integration boosts
                if (pick.get("serp_reasons") or []) and pick.get("serp_boost", 0) == 0:
                    zero_impact["SERP"] += 1
                if (pick.get("msrf_reasons") or []) and pick.get("msrf_boost", 0) == 0:
                    zero_impact["MSRF"] += 1

        report["signal_counts"] = dict(signal_counter.most_common())
        if total_picks > 0:
            always_fire = [k for k, v in signal_counter.items() if v == total_picks]
            report["always_fire"] = sorted(always_fire)
            never_fire = sorted([k for k in KNOWN_SIGNALS if k not in signal_counter])
            report["never_fire"] = never_fire
        report["zero_impact_signals"] = dict(zero_impact)

    artifacts_dir = os.path.join(os.path.dirname(__file__), "..", "artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)
    artifact_path = os.path.join(artifacts_dir, "signal_coverage.json")
    with open(artifact_path, "w") as f:
        json.dump(report, f, indent=2, sort_keys=True)

    docs_path = os.path.join(os.path.dirname(__file__), "..", "docs", "SIGNAL_COVERAGE_REPORT.md")
    with open(docs_path, "w") as f:
        f.write("# Signal Coverage Report\n\n")
        f.write(f"Date ET: {report['date_et']}\n\n")
        f.write(f"Status: {report['status']}\n\n")
        if report["errors"]:
            f.write("## Errors\n")
            for err in report["errors"]:
                f.write(f"- {err}\n")
            f.write("\n")
        f.write("## Signal Counts\n")
        for key, count in report.get("signal_counts", {}).items():
            f.write(f"- {key}: {count}\n")
        f.write("\n")
        f.write("## Always Fire\n")
        for key in report.get("always_fire", []):
            f.write(f"- {key}\n")
        f.write("\n")
        f.write("## Never Fire (Known Set)\n")
        for key in report.get("never_fire", []):
            f.write(f"- {key}\n")
        f.write("\n")
        f.write("## Zero Impact Signals\n")
        for key, count in report.get("zero_impact_signals", {}).items():
            f.write(f"- {key}: {count}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
