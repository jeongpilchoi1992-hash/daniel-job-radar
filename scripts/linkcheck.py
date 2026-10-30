"""Free link checks for job postings found by the AI search.

Every refresh re-opens each posting: links that are gone, say the job is
closed, passed their deadline, or dropped off the employer's own job board
are removed. No AI and no paid services.
"""

from __future__ import annotations

import re
from datetime import date
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from boards import board_id, detect, posting_key
from common import parse_date

# Status lines a job page shows once the posting is gone. They are matched only against the page's title,
# headings, alert banners and opening text, never the whole description, which can say things like
# "applications are accepted until the position has been filled".
_LEAD = r"(?:^|[.!?|:]\s*|\bsorry,?\s*)"  # a status line starts a sentence; "after the posting has closed" does not
CLOSED_PATTERNS = re.compile(
    rf"{_LEAD}(?:the |this )?(?:job )?(?:posting|vacancy|job|position|announcement) (?:has )?(?:expired|closed)\b|"
    r"\bthis (?:job )?(?:posting|vacancy|job|position|announcement) (?:has )?(?:expired|closed)\b|"
    rf"{_LEAD}(?:the|this) (?:job|position|posting|vacancy|requisition|opportunity) (?:you are looking for |you requested )?"
    r"(?:is|has been) (?:no longer|closed|filled|removed|expired)|"
    r"\bthis (?:job|position|posting|vacancy|requisition|opportunity) (?:is|has been) (?:no longer|closed|filled|removed|expired)|"
    r"no longer (?:accepting applications|available|open|active)|applications? (?:are|is) (?:now )?closed|"
    r"job not found|page not found|we couldn't find (?:that|this) job|this job is no longer",
    re.I,
)
STATUS_ELEMENTS = "title, h1, h2, h3, [role=alert], [class*=alert], [class*=banner], [class*=notice], [class*=message], [class*=expired], [class*=closed]"
DEAD_STRIKES = 2  # 'dead' verdicts in a row before an AI-found posting is removed (a deadline that passed counts at once)


def _status_text(html_text: str) -> str:
    soup = BeautifulSoup(html_text[:600000], "html.parser")
    for tag in soup(["script", "style", "template", "noscript", "svg"]):
        tag.decompose()
    bits = [el.get_text(" ", strip=True)[:300] for el in soup.select(STATUS_ELEMENTS)]
    main = soup.find("main") or soup.body or soup
    bits.append(main.get_text(" ", strip=True)[:1000])
    return " | ".join(bits)


def _workday_status(session, url: str) -> tuple[str, str] | None:
    """Workday pages are rendered by JavaScript, so ask the board's public API about the posting instead."""
    board = detect(url)
    m = re.search(r"/job/.+?(?=/apply\b|/?$)", urlparse(url).path)
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


def verify(session, job: dict, today: date, listed: bool = False) -> tuple[str, str]:
    """Return (status, note): status is 'ok', 'unverified' (blocked/unknown) or 'dead'.

    listed=True means the posting is on its employer's board, read in full this run, so its page text is not
    used to call it closed.
    """
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
    if listed:
        return "ok", "listed on the employer's job board"
    if CLOSED_PATTERNS.search(_status_text(resp.text)):
        return "dead", "page says closed"
    # Redirected to a generic careers page: the posting is gone.
    if resp.history and re.search(r"/(careers|jobs)/?(\?.*)?$", resp.url) and not re.search(r"/(careers|jobs)/?(\?.*)?$", job["url"]):
        return "dead", "redirected to careers home"
    return "ok", "link checked"


def refresh(session, name: str, jobs: list[dict], today: date, log, live_boards: dict[str, set[str]] | None = None,
            out_of_time=lambda: False) -> list[dict]:
    """Re-verify every AI-found posting and drop dead or stale ones.

    live_boards maps a job board (or a host such as the Senate's job board) to the
    postings it lists today, only for boards read in full, so a posting that left
    its board is removed even when its page still loads.
    """
    kept = []
    unreachable: set[str] = set()
    for job in jobs:
        if out_of_time():
            kept.append(job)  # not checked this run; left as it was
            continue
        board = detect(job["url"])
        host = urlparse(job["url"]).netloc.lower()
        listed = (live_boards or {}).get(board_id(board) if board else host)
        on_board = listed is not None and posting_key(job["url"]) in listed
        if listed is not None and not on_board:
            status, note = "dead", "no longer listed on the employer's job board"
        elif host in unreachable:
            status, note = "unverified", "site not reachable this run"
        else:
            status, note = verify(session, job, today, listed=on_board)
            if note.startswith("fetch failed: Connect"):
                unreachable.add(host)
        found = parse_date(job.get("found_on")) or today
        age = (today - found).days
        closes = parse_date(job.get("closes"))
        if status == "dead":
            # These postings cannot be found again, so a one-off glitch must not remove them.
            job["dead_runs"] = job.get("dead_runs", 0) + 1
            if note == "deadline passed" or job["dead_runs"] >= DEAD_STRIKES:
                log(f"  {name}: removed {job['title'][:60]!r} ({note})")
                continue
            log(f"  {name}: {job['title'][:60]!r} looks closed ({note}); checking again next run")
            job["check"] = f"may have closed: {note}"
            kept.append(job)
            continue
        job["dead_runs"] = 0
        if status == "unverified":
            # Some sites block automated checks. A posting with a future deadline stays until then; one without
            # gets a week of failed checks in a row, or three weeks if it was never verified at all.
            job["unverified_runs"] = job.get("unverified_runs", 0) + 1
            if not closes and (job["unverified_runs"] >= 14 or (not job.get("verified_on") and age > 21)):
                log(f"  {name}: removed {job['title'][:60]!r} (could not verify: {note})")
                continue
        else:
            job["unverified_runs"] = 0
            job["verified_on"] = today.isoformat()
        if not closes and age > 45:
            log(f"  {name}: removed {job['title'][:60]!r} (older than 45 days, no deadline)")
            continue
        job["check"] = note
        kept.append(job)
    return kept
