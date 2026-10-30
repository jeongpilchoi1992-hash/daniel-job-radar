"""Shared helpers for the collectors."""

from __future__ import annotations

import hashlib
import html
import re
from datetime import date, datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0 Safari/537.36"
)


class SourceSkipped(Exception):
    """A source was not run on purpose (for example, a missing API key)."""


class PartialResult(Exception):
    """A source stopped part of the way through; the jobs it did return are still good."""

    def __init__(self, jobs: list[dict], message: str):
        super().__init__(message)
        self.jobs = jobs


def make_session(quick: bool = False) -> requests.Session:
    """A session with polite retries; quick=True gives up fast on unreachable hosts."""
    session = requests.Session()
    retry = Retry(
        total=1 if quick else 4,
        connect=0 if quick else None,
        backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": BROWSER_UA, "Accept-Language": "en-US,en;q=0.9"})
    return session


def job_key(job_id: str) -> str:
    """Stable short file name for per-job files."""
    return hashlib.sha1(job_id.encode("utf-8")).hexdigest()[:16]


_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\r\f\v]+")


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</div>|</h\d>", "\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "\n- ", text)
    text = _TAG.sub(" ", text)
    text = html.unescape(text)
    text = _WS.sub(" ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def shorten(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",.;:") + "…"


def parse_date(value: str | None) -> date | None:
    """Parse the date formats used by the sources; None when unknown or 'Continuous'."""
    if not value:
        return None
    value = value.strip()
    if not value or re.search(r"continuous|until filled|open until", value, re.I):
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", value)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", value)
    if m:
        return date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
    cleaned = re.sub(r"\s+-\s+.*$", "", value)  # "Nov 30 2026 - 23:55 EST"
    cleaned = re.sub(r"\s+\d{1,2}:\d{2}.*$", "", cleaned)
    cleaned = cleaned.replace(",", " ")
    cleaned = re.sub(r"^(mon|tue|wed|thu|fri|sat|sun)[a-z]*\s+", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    for fmt in ("%b %d %Y", "%B %d %Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def money(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = re.search(r"\d[\d,]*(?:\.\d+)?", str(value))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def salary_range(text: str | None) -> tuple[float | None, float | None, str | None]:
    """Pull min/max and a period from free text like '$54,000 - $63,500' or '$17.00 per hour'."""
    if not text:
        return None, None, None
    amounts = [money(a) for a in re.findall(r"\$\s?\d[\d,]*(?:\.\d+)?", text)]
    amounts = [a for a in amounts if a]
    if not amounts:
        amounts = [money(a) for a in re.findall(r"\b\d{2,3},\d{3}(?:\.\d+)?\b", text)]
        amounts = [a for a in amounts if a]
    period = None
    low = text.lower()
    if "hour" in low or "/hr" in low:
        period = "hour"
    elif "year" in low or "annual" in low:
        period = "year"
    elif amounts and max(amounts) > 1000:
        period = "year"
    elif amounts:
        period = "hour"
    if not amounts:
        return None, None, period
    return min(amounts), max(amounts), period
