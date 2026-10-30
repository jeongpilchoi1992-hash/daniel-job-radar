"""Free link checks for job postings found by the AI search.

Every refresh re-opens each posting: links that are gone, say the job is
closed, passed their deadline, or dropped off the employer's own job board
are removed. No AI and no paid services.
"""

from __future__ import annotations

import re
from datetime import date
from urllib.parse import urlparse

from boards import board_id, detect, posting_key
from common import parse_date

CLOSED_PATTERNS = re.compile(
    r"no longer (accepting|available|open)|position has been filled|job (posting )?(has )?(expired|closed)|"
    r"this (job|position|posting|vacancy) (is|has been) (closed|filled|removed)|"
    r"applications? (are|is) (now )?closed|posting (has )?closed|job not found|page not found|"
    r"this job is no longer|we couldn't find (that|this) job",
    re.I,
)


def _workday_status(session, url: str) -> tuple[str, str] | None:
    """Workday pages are rendered by JavaScript, so ask the board's public API about the posting instead."""
    board = detect(url)
    m = re.search(r"/job/.+$", urlparse(url).path)
    if not board or board["type"] != "workday" or not m:
        return None
    base = f"https://{board['host']}/wday/cxs/{board['tenant']}/{board['site']}"
    try:
        resp = session.get(base + m.group(0), headers={"Accept": "application/json"}, timeout=(10, 40))
        if resp.status_code == 404:
            probe = session.post(f"{base}/jobs", json={"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""}, timeout=(10, 40))
            return ("dead", "no longer on the employer's job board") if probe.ok else ("unverified", "job board did not answer")
        if resp.status_code >= 400:
            return "unverified", f"HTTP {resp.status_code}"
        info = resp.json().get("jobPostingInfo") or {}
    except Exception as exc:  # noqa: BLE001 - network problems should not delete a job
        return "unverified", f"fetch failed: {type(exc).__name__}"
    if not info:
        return "dead", "no longer on the employer's job board"
    if info.get("canApply") is False:
        return "dead", "applications closed"
    return "ok", "listed on the employer's job board"


def verify(session, job: dict, today: date) -> tuple[str, str]:
    """Return (status, note): status is 'ok', 'unverified' (blocked/unknown) or 'dead'."""
    closes = parse_date(job.get("closes"))
    if closes and closes < today:
        return "dead", "deadline passed"
    workday = _workday_status(session, job["url"])
    if workday:
        return workday
    try:
        resp = session.get(job["url"], timeout=(10, 40), allow_redirects=True)
    except Exception as exc:  # noqa: BLE001 - network problems should not delete a job
        return "unverified", f"fetch failed: {type(exc).__name__}"
    if resp.status_code in (404, 410):
        return "dead", f"HTTP {resp.status_code}"
    if resp.status_code >= 400:
        return "unverified", f"HTTP {resp.status_code}"
    body = resp.text[:400000]
    if CLOSED_PATTERNS.search(body):
        return "dead", "page says closed"
    # Redirected to a generic careers page: the posting is gone.
    if resp.history and re.search(r"/(careers|jobs)/?(\?.*)?$", resp.url) and not re.search(r"/(careers|jobs)/?(\?.*)?$", job["url"]):
        return "dead", "redirected to careers home"
    return "ok", "link checked"


def refresh(session, name: str, jobs: list[dict], today: date, log, live_boards: dict[str, set[str]] | None = None) -> list[dict]:
    """Re-verify every AI-found posting and drop dead or stale ones.

    live_boards maps a job board (or a host such as the Senate's job board) to the
    postings it lists today, only for boards read in full, so a posting that left
    its board is removed even when its page still loads.
    """
    kept = []
    unreachable: set[str] = set()
    for job in jobs:
        board = detect(job["url"])
        host = urlparse(job["url"]).netloc.lower()
        listed = (live_boards or {}).get(board_id(board) if board else host)
        if listed is not None and posting_key(job["url"]) not in listed:
            status, note = "dead", "no longer listed on the employer's job board"
        elif host in unreachable:
            status, note = "unverified", "site not reachable this run"
        else:
            status, note = verify(session, job, today)
            if note.startswith("fetch failed: Connect"):
                unreachable.add(host)
        found = parse_date(job.get("found_on")) or today
        age = (today - found).days
        if status == "dead":
            log(f"  {name}: removed {job['title'][:60]!r} ({note})")
            continue
        if status == "unverified":
            # Some sites block automated checks; give them a week before giving up.
            job["unverified_runs"] = job.get("unverified_runs", 0) + 1
            if job["unverified_runs"] >= 14 or age > (30 if job.get("closes") else 21):
                log(f"  {name}: removed {job['title'][:60]!r} (could not verify: {note})")
                continue
        else:
            job["unverified_runs"] = 0
            job["verified_on"] = today.isoformat()
        if not job.get("closes") and age > 45:
            log(f"  {name}: removed {job['title'][:60]!r} (older than 45 days, no deadline)")
            continue
        job["check"] = note
        kept.append(job)
    return kept


