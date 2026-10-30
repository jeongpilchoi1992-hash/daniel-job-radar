"""Free daily sources for J.P.'s tab: public job-board APIs of specific employers.

Boards are learned from the one-time AI search (any discovered posting hosted on
Workday, Greenhouse, Lever, SmartRecruiters or Ashby becomes a board we read
every day) plus any boards listed in config/boards.json. No API keys, no AI.
"""

from __future__ import annotations

import re
import time
from urllib.parse import urlparse

from common import job_key, shorten, strip_html

FINANCE_TITLE = re.compile(
    r"invest|portfolio|fund|capital market|asset manage|wealth|equity|credit|fixed income|treasury|"
    r"financial (analyst|officer|specialist)|finance (analyst|officer|associate|manager)|corporate development|"
    r"strategy|strategic|m&a|merger|acquisition|private (equity|debt|market)|due diligence|investor relations|"
    r"risk (analyst|officer|associate|manager)|research analyst|economist|korea|korean|asia|"
    r"operations officer|financial sector|banking|securities|analyst|associate",
    re.I,
)
SKIP_TITLE = re.compile(r"intern\b|internship|software|engineer|developer|nurse|driver|warehouse|technician|"
                        r"recruiter|sales (rep|representative)|customer service|administrative assistant|receptionist", re.I)
REGION = re.compile(
    r"washington|district of columbia|\bdc\b|new york|\bny\b|united states|\busa\b|\bus\b|remote|"
    r"seoul|korea|singapore|hong kong|virginia|maryland|new jersey|los angeles|san francisco|chicago|boston",
    re.I,
)
KOREA_HINT = re.compile(r"korea|korean|seoul", re.I)


def detect(url: str) -> dict | None:
    """Map a posting URL to the board it belongs to, if it is on a supported ATS."""
    parsed = urlparse(url)
    host, parts = parsed.netloc.lower(), [p for p in parsed.path.split("/") if p]
    m = re.match(r"^([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com$", host)
    if m and parts:
        site_parts = [p for p in parts if not re.fullmatch(r"[a-z]{2}-[A-Z]{2}", p)]
        if site_parts and site_parts[0] != "job":
            return {"type": "workday", "host": host, "tenant": m.group(1), "site": site_parts[0]}
    if host in ("boards.greenhouse.io", "job-boards.greenhouse.io") and parts:
        return {"type": "greenhouse", "token": parts[0]}
    if host == "jobs.lever.co" and parts:
        return {"type": "lever", "company": parts[0]}
    if host == "jobs.smartrecruiters.com" and parts:
        return {"type": "smartrecruiters", "company": parts[0]}
    if host == "jobs.ashbyhq.com" and parts:
        return {"type": "ashby", "org": parts[0]}
    return None


def board_id(board: dict) -> str:
    return ":".join(str(board.get(k, "")) for k in ("type", "host", "tenant", "site", "token", "company", "org") if board.get(k))


def posting_key(url: str) -> str:
    """The part of a posting URL that identifies the job on its board."""
    parsed = urlparse(url)
    m = re.search(r"gh_jid=(\d+)", parsed.query)
    if m:
        return m.group(1)
    parts = [p for p in parsed.path.split("/") if p and p not in ("apply", "application")]
    if not parts:
        return url.lower()
    if parsed.netloc.endswith("greenhouse.io"):
        m = re.search(r"/jobs/(\d+)", parsed.path)
        return m.group(1) if m else parts[-1]
    if parsed.netloc == "jobs.smartrecruiters.com":
        return parts[1].split("-")[0] if len(parts) > 1 else parts[-1]
    if parsed.netloc in ("jobs.lever.co", "jobs.ashbyhq.com"):
        return parts[1].lower() if len(parts) > 1 else parts[-1].lower()
    return parts[-1].lower()


def fetch_board(session, board: dict, employer: str, log) -> tuple[list[dict], bool]:
    """All postings on a board, and whether the list is complete."""
    kind = board["type"]
    if kind == "workday":
        return _workday(session, board, employer, log)
    return _fetch_simple(session, board, employer), True


def _fetch_simple(session, board: dict, employer: str) -> list[dict]:
    kind = board["type"]
    if kind == "greenhouse":
        resp = session.get(f"https://boards-api.greenhouse.io/v1/boards/{board['token']}/jobs", params={"content": "true"}, timeout=60)
        resp.raise_for_status()
        return [
            _job(board, employer, j.get("title"), (j.get("location") or {}).get("name"), j.get("absolute_url"),
                 (j.get("updated_at") or "")[:10], strip_html(j.get("content") or ""))
            for j in resp.json().get("jobs", [])
        ]
    if kind == "lever":
        resp = session.get(f"https://api.lever.co/v0/postings/{board['company']}", params={"mode": "json"}, timeout=60)
        resp.raise_for_status()
        out = []
        for j in resp.json():
            created = j.get("createdAt")
            posted = time.strftime("%Y-%m-%d", time.gmtime(created / 1000)) if isinstance(created, (int, float)) else ""
            out.append(_job(board, employer, j.get("text"), (j.get("categories") or {}).get("location"), j.get("hostedUrl"),
                            posted, j.get("descriptionPlain") or ""))
        return out
    if kind == "smartrecruiters":
        out = []
        for offset in range(0, 1000, 100):
            resp = session.get(f"https://api.smartrecruiters.com/v1/companies/{board['company']}/postings",
                               params={"limit": 100, "offset": offset}, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            for j in data.get("content", []):
                loc = j.get("location") or {}
                url = f"https://jobs.smartrecruiters.com/{board['company']}/{j.get('id')}"
                out.append(_job(board, employer, j.get("name"), ", ".join(x for x in [loc.get("city"), loc.get("country")] if x), url,
                                (j.get("releasedDate") or "")[:10], ""))
            if offset + 100 >= int(data.get("totalFound") or 0):
                break
        return out
    if kind == "ashby":
        resp = session.get(f"https://api.ashbyhq.com/posting-api/job-board/{board['org']}", timeout=60)
        resp.raise_for_status()
        return [
            _job(board, employer, j.get("title"), j.get("location"), j.get("jobUrl"), (j.get("publishedAt") or "")[:10],
                 j.get("descriptionPlain") or "")
            for j in resp.json().get("jobs", [])
        ]
    return []


def _workday(session, board: dict, employer: str, log) -> tuple[list[dict], bool]:
    base = f"https://{board['host']}/wday/cxs/{board['tenant']}/{board['site']}"
    out: list[dict] = []
    total = 0
    for offset in range(0, 600, 20):
        resp = session.post(f"{base}/jobs", json={"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": ""}, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        postings = data.get("jobPostings") or []
        if offset == 0:
            total = int(data.get("total") or 0)
        for p in postings:
            path = p.get("externalPath") or ""
            url = f"https://{board['host']}/en-US/{board['site']}{path}"
            out.append(_job(board, employer, p.get("title"), p.get("locationsText"), url, "", " ".join(p.get("bulletFields") or []),
                            posted_text=p.get("postedOn") or ""))
        if not postings or offset + 20 >= total:
            break
        time.sleep(0.5)
    return out, len(out) >= total


def _job(board: dict, employer: str, title, location, url, posted: str, text: str, posted_text: str = "") -> dict:
    return {
        "board": board_id(board),
        "title": shorten(title or "", 160),
        "org": employer,
        "location": shorten(location or "", 120),
        "url": url or "",
        "posted": posted or "",
        "posted_text": posted_text,
        "text": text or "",
    }


def relevant(job: dict) -> bool:
    title = job["title"]
    if not title or not job["url"] or SKIP_TITLE.search(title) or not FINANCE_TITLE.search(title):
        return False
    return not job["location"] or bool(REGION.search(job["location"]))


def score(job: dict) -> int:
    title, text = job["title"].lower(), (job["title"] + " " + job.get("text", "")).lower()
    s = 40
    for pattern, pts in [
        (r"invest|portfolio|fund|private (equity|debt|market)|capital market", 18),
        (r"strategy|strategic|corporate development|m&a|due diligence", 14),
        (r"korea|korean|seoul", 20),
        (r"asia|apac|cross-border|international", 8),
        (r"associate|analyst|officer|avp|assistant vice president", 6),
    ]:
        if re.search(pattern, title):
            s += pts
        elif re.search(pattern, text):
            s += pts // 3
    if re.search(r"\b(senior|director|head of|managing director|vice president|principal|lead)\b", title):
        s -= 12
    if re.search(r"\b(junior|entry|graduate)\b", title):
        s -= 8
    return max(0, min(100, s))


def to_site_job(job: dict, today_iso: str, first_seen: str | None) -> dict:
    segment = "Korea / Asia focus" if KOREA_HINT.search(job["title"] + " " + job["location"]) else "Employer job board"
    return {
        "id": f"board:{job_key(job['url'])}",
        "source": f"board:{job['board']}",
        "level": segment,
        "title": job["title"],
        "org": job["org"],
        "location": job["location"],
        "url": job["url"],
        "apply_url": job["url"],
        "posted": job["posted"] or None,
        "posted_text": job.get("posted_text", ""),
        "closes": None,
        "summary": shorten(job.get("text", ""), 300),
        "match": {"score": score(job), "tags": [segment]},
        "found_on": first_seen or today_iso,
        "from_board": True,
    }
