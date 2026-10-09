import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shelfcast.data import generate_synthetic  # noqa: E402
from shelfcast.llm import FakeLLM  # noqa: E402


def planner_responder(messages, n):
    """A rule-based stand-in for the model: lifts holiday and promotion weeks."""
    brief = messages[-1]["content"]
    events = re.search(r"events: (.*)", brief).group(1)
    mult, drivers = 1.0, []
    if "Holiday" in events or "event:" in events:
        mult *= 1.5
        drivers.append({"name": "holiday", "effect_pct": 50, "evidence": "past lift"})
    if "Promotion" in events:
        mult *= 1.4
        drivers.append({"name": "promotion", "effect_pct": 40, "evidence": "past promos"})
    if "planner notes" in brief and "closed" in brief:
        mult *= 0.5
        drivers.append({"name": "closure", "effect_pct": -50, "evidence": "notes"})
    out = []
    for k in range(n):
        out.append(json.dumps({
            "analysis": "rule based",
            "drivers": drivers,
            "median_multiplier": mult * (1 + 0.02 * (k - n // 2)),
            "downside_spread": 1.0,
            "upside_spread": 1.2 if mult > 1 else 1.0,
            "confidence": "medium",
        }))
    return out


def evidence_responder(messages, n):
    """Uses the lifts printed in the brief, as a careful planner would."""
    brief = messages[-1]["content"]
    events = re.search(r"events: (.*)", brief).group(1)
    mult = 1.0
    for lift in re.findall(r"\[(?:event week|week before the event)\]: median x([\d.]+) vs baseline", brief):
        mult *= float(lift)
    promo = re.search(r"PAST PROMOTIONS: .*?median x([\d.]+) vs", brief)
    if "Promotion" in events and promo:
        mult *= float(promo.group(1))
    ans = json.dumps({"analysis": "evidence", "drivers": [], "median_multiplier": mult,
                      "downside_spread": 1.0, "upside_spread": 1.0, "confidence": "medium"})
    return [ans] * n


@pytest.fixture(scope="session")
def synthetic():
    return generate_synthetic()


@pytest.fixture
def fake_llm():
    return FakeLLM(planner_responder)
