"""Claude helpers: client setup, a monthly spend guard, and the request wrapper."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic

ET = ZoneInfo("America/New_York")
DEFAULT_MODEL = "claude-opus-5-5"

# USD per million tokens, and per web search. Used only for the budget guard.
PRICES = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-fable-5-1": (10.0, 50.0),
}
WEB_SEARCH_USD = 0.01


def model_name() -> str:
    return os.environ.get("AI_MODEL", "").strip() or DEFAULT_MODEL


def make_client() -> anthropic.Anthropic | None:
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        return None
    return anthropic.Anthropic(max_retries=3, timeout=600)


class Budget:
    """Caps Claude spend for one run and keeps a monthly history in data/usage.json."""

    def __init__(self, path: Path, run_limit: float):
        self.path = path
        self.limit = run_limit
        self.spent = 0.0  # this run
        self.month = datetime.now(ET).strftime("%Y-%m")
        data = {}
        if path.exists():
            try:
                data = json.loads(path.read_text())
            except json.JSONDecodeError:
                data = {}
        self.history = data.get("history", {})
        self.by_task: dict[str, float] = {}
        self.calls = 0

    @property
    def remaining(self) -> float:
        return self.limit - self.spent

    def allows(self, estimate: float) -> bool:
        return self.spent + estimate <= self.limit

    def record(self, task: str, usage, model: str) -> float:
        price_in, price_out = PRICES.get(model, PRICES[DEFAULT_MODEL])
        tokens_in = (usage.input_tokens or 0) + (getattr(usage, "cache_creation_input_tokens", 0) or 0) * 1.25
        tokens_in += (getattr(usage, "cache_read_input_tokens", 0) or 0) * 0.1
        cost = tokens_in / 1e6 * price_in + (usage.output_tokens or 0) / 1e6 * price_out
        server = getattr(usage, "server_tool_use", None)
        searches = (getattr(server, "web_search_requests", 0) or 0) if server else 0
        cost += searches * WEB_SEARCH_USD
        self.spent += cost
        self.calls += 1
        self.by_task[task] = round(self.by_task.get(task, 0.0) + cost, 4)
        return cost

    def save(self) -> None:
        if not self.calls:
            return
        month = self.history.get(self.month, {"usd": 0.0, "calls": 0, "runs": []})
        month["usd"] = round(month.get("usd", 0.0) + self.spent, 4)
        month["calls"] = month.get("calls", 0) + self.calls
        month.setdefault("runs", []).append({
            "at": datetime.now(ET).isoformat(timespec="minutes"),
            "usd": round(self.spent, 4),
            "by_task": self.by_task,
        })
        self.history[self.month] = month
        keep = dict(sorted(self.history.items())[-12:])
        self.path.write_text(json.dumps({"history": keep}, indent=2) + "\n")

    def month_total(self) -> float:
        return round(self.history.get(self.month, {}).get("usd", 0.0), 2)


def create(client: anthropic.Anthropic, **params):
    """Messages call with server-side refusal fallback; streams so long turns don't time out."""
    params.setdefault("model", model_name())
    try:
        with client.beta.messages.stream(
            betas=["server-side-fallback-2026-07-01"], fallbacks="default", **params
        ) as stream:
            return stream.get_final_message()
    except anthropic.BadRequestError as exc:
        if "fallback" not in str(exc).lower():
            raise
    # Fallbacks not available for this key or model: same request without them.
    with client.beta.messages.stream(**params) as stream:
        return stream.get_final_message()


def text_of(message) -> str:
    return "".join(block.text for block in message.content if getattr(block, "type", "") == "text")
