"""Free daily sources for J.P.'s tab: public job-board APIs of specific employers.

Boards are learned from the one-time AI search (any discovered posting hosted on
Workday, Greenhouse, Lever, SmartRecruiters or Ashby becomes a board we read
every day) plus any boards listed in config/boards.json. No API keys, no AI.
"""

from __future__ import annotations

import re
import time
from urllib.parse import unquote, urlparse

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
                        r"recruiter|sales (rep|representative)|customer service|administrative assistant|receptionist|"
                        r"information technology|technology (operations|support|infrastructure|analyst|specialist|risk|audit)|\bcyber|\bIT\b|"
                        r"data (engineer|scientist)|\bQA\b|\bKYC\b|\bAML\b|anti-money|"
                        r"payroll|facilities|executive assistant|secretary|office manager", re.I)
# Finance titles that count at U.S. subsidiaries of Korean companies (mostly non-finance employers).
US_FINANCE_TITLE = re.compile(r"financ|treasury|invest|fp&a|corporate development|m&a|strateg|capital|portfolio|"
                              r"\brisk\b|credit|economist", re.I)
KOREA_HINT = re.compile(r"korea|korean|seoul", re.I)
ASIA_HUB = re.compile(r"seoul|korea|singapore|hong kong", re.I)
IFI_HINT = re.compile(r"international organi[sz]ation|multilateral|development bank|\bIMF\b|monetary fund|world bank|\bIFC\b|"
                      r"\bMIGA\b|\bIDB\b|\bADB\b|\bAIIB\b|\bEBRD\b|climate fund|green growth", re.I)
KOREAN_US_HINT = re.compile(r"u\.?s\.? (subsidiary|office|affiliate|branch)|korean.{0,40}(u\.?s\.?|america)", re.I)

# What a board is read for (board["focus"]):
#   asia      global firms: finance roles in Seoul, Singapore or Hong Kong, or any role tied to Korea
#   korea_us  U.S. subsidiaries of Korean companies (visa-friendly): finance roles anywhere
#   ifi       international financial institutions: finance and economics roles anywhere
WORKDAY_SEARCHES = {
    "asia": ["Korea", "Korean", "Seoul"],
    "korea_us": ["finance", "financial", "treasury", "investment", "strategy"],
    "ifi": [],
}
WORKDAY_FULL_READ = 400  # boards up to this size are read in full; bigger ones are searched
REQ_ID = re.compile(r"(?:\d{1,4}[-_])?[A-Z]{0,4}[-_]?\d{3,}(?:[-_]\d+)*(?:[-_][A-Z]{1,4})?", re.I)  # requisition numbers like JR043128 or 26-R8965


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


def infer_focus(level: str, org: str) -> str:
    """Pick a board's focus from the AI-found posting that revealed it."""
    text = f"{level} {org}"
    if IFI_HINT.search(text):
        return "ifi"
    if KOREAN_US_HINT.search(text):
        return "korea_us"
    return "asia"


def board_id(board: dict) -> str:
    return ":".join(str(board.get(k, "")) for k in ("type", "host", "tenant", "site", "token", "company", "org") if board.get(k))


def posting_key(url: str) -> str:
    """The part of a posting URL that identifies the job on its board."""
    parsed = urlparse(url)
    m = re.search(r"gh_jid=(\d+)", parsed.query)
    if m:
        return m.group(1)
    path = unquote(parsed.path)
    if parsed.netloc.endswith("myworkdayjobs.com"):
        # .../job/<place>/<Title>_<requisition id>[/apply/...]: the requisition id survives title edits.
        m = re.search(r"/job/(?:.*/)?[^/]*?_([^/_]+)/?(?:/apply\b.*)?$", path)
        if m:
            return m.group(1).lower()
    parts = [p for p in path.split("/") if p and p not in ("apply", "application")]
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
    if kind == "smartrecruiters":
        return _smartrecruiters(session, board, employer)
    return _fetch_simple(session, board, employer), True


def _smartrecruiters(session, board: dict, employer: str) -> tuple[list[dict], bool]:
    out: dict[str, dict] = {}
    total = 0
    for offset in range(0, 5000, 100):
        resp = session.get(f"https://api.smartrecruiters.com/v1/companies/{board['company']}/postings",
                           params={"limit": 100, "offset": offset}, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        total = int(data.get("totalFound") or 0)
        content = data.get("content") or []
        for j in content:
            loc = j.get("location") or {}
            url = f"https://jobs.smartrecruiters.com/{board['company']}/{j.get('id')}"
            out[url] = _job(board, employer, j.get("name"), ", ".join(x for x in [loc.get("city"), loc.get("country")] if x), url,
                            (j.get("releasedDate") or "")[:10], "")
        if not content or offset + 100 >= total:
            break
    return list(out.values()), len(out) >= total


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
    """Small boards are read in full; big ones are searched for the roles that fit the board's focus."""
    base = f"https://{board['host']}/wday/cxs/{board['tenant']}/{board['site']}"
    focus = board.get("focus") or "asia"
    found: dict[str, dict] = {}

    def page(search: str, offset: int) -> dict:
        resp = session.post(f"{base}/jobs", json={"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": search}, timeout=60)
        resp.raise_for_status()
        return resp.json()

    def add(postings: list[dict], korea_search: bool) -> None:
        for p in postings:
            path = p.get("externalPath") or ""
            if not path:
                continue
            if path not in found:
                url = f"https://{board['host']}/en-US/{board['site']}{path}"
                # bulletFields usually hold just the requisition number, which is no use as a summary.
                bullets = [b for b in p.get("bulletFields") or [] if not REQ_ID.fullmatch(b.strip())]
                found[path] = _job(board, employer, p.get("title"), p.get("locationsText"), url, "",
                                   " ".join(bullets), posted_text=p.get("postedOn") or "")
            if korea_search:
                found[path]["korea_search"] = True

    first = page("", 0)
    total = int(first.get("total") or 0)
    searches = WORKDAY_SEARCHES.get(focus) or []
    if total <= WORKDAY_FULL_READ or not searches:
        add(first.get("jobPostings") or [], False)
        for offset in range(20, min(total, 600), 20):
            time.sleep(0.5)
            postings = page("", offset).get("jobPostings") or []
            if not postings:
                break
            add(postings, False)
        return list(found.values()), len(found) >= total
    for query in searches:
        hits = None
        for offset in range(0, 100, 20):
            time.sleep(0.5)
            data = page(query, offset)
            if hits is None:
                hits = int(data.get("total") or 0)
            postings = data.get("jobPostings") or []
            add(postings, focus == "asia")
            if not postings or offset + 20 >= hits:
                break
    log(f"[board] {board_id(board)}: {total} postings on the board, searched for {', '.join(searches)}")
    return list(found.values()), False


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


def relevant(job: dict, focus: str = "asia") -> bool:
    title = job["title"]
    if not title or not job["url"] or SKIP_TITLE.search(title):
        return False
    if focus == "korea_us":
        return bool(US_FINANCE_TITLE.search(title))
    if not FINANCE_TITLE.search(title):
        return False
    if focus == "ifi" or job.get("korea_search") or KOREA_HINT.search(f"{title} {job['location']}"):
        return True
    return bool(ASIA_HUB.search(job["location"]))


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


def jp_segment(location: str, about: str, focus: str = "") -> str:
    """One of a few filter chips for J.P.'s tab; `about` is the employer name plus any AI label."""
    if focus == "ifi" or IFI_HINT.search(about):
        return "International organization"
    if re.search(r"seoul|korea|incheon|songdo|busan", location, re.I):
        return "Seoul / Korea"
    if re.search(r"hong kong|singapore", location, re.I):
        return "Hong Kong / Singapore"
    if focus == "korea_us" or KOREAN_US_HINT.search(about):
        return "Korean company in the U.S."
    return "U.S. and other"


def to_site_job(job: dict, today_iso: str, first_seen: str | None, focus: str = "asia") -> dict:
    segment = jp_segment(job["location"], job["org"], focus)
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
