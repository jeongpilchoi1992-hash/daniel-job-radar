"""Job source collectors.

Each collector returns a list of job dicts in the shared shape (see collect.py).
A private "_detail" key carries the full posting text for the AI step; it is
dropped before anything is written to disk.
"""

from __future__ import annotations

import os
import re
import time
from datetime import date, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from common import BROWSER_UA, PartialResult, SourceSkipped, parse_date, salary_range, shorten, strip_html
from places import haversine_miles, lookup

# --------------------------------------------------------------------------- USAJOBS

USAJOBS_URL = "https://data.usajobs.gov/api/search"


def _first(items, key=None, default=None):
    if not items:
        return default
    item = items[0]
    return item.get(key, default) if key and isinstance(item, dict) else item


def fetch_usajobs(session, cfg: dict, home: tuple[float, float]) -> list[dict]:
    key = os.environ.get("USAJOBS_API_KEY", "").strip()
    email = os.environ.get("USAJOBS_EMAIL", "").strip()
    if not key or not email:
        raise SourceSkipped("Add USAJOBS_API_KEY and USAJOBS_EMAIL repository secrets to load federal jobs.")

    headers = {"Host": "data.usajobs.gov", "User-Agent": email, "Authorization-Key": key}
    radius = int(cfg.get("radius_miles", 50))
    queries = [{"LocationName": cfg.get("location", "Manassas, Virginia"), "Radius": radius}]
    if cfg.get("include_remote", True):
        queries.append({"RemoteIndicator": "True"})

    seen: dict[str, dict] = {}
    for query in queries:
        page = 1
        while True:
            params = {**query, "ResultsPerPage": 500, "Page": page}
            resp = session.get(USAJOBS_URL, headers=headers, params=params, timeout=90)
            if resp.status_code in (401, 403):
                raise RuntimeError(f"USAJOBS rejected the key/email (HTTP {resp.status_code}). Check the secrets.")
            resp.raise_for_status()
            result = resp.json().get("SearchResult", {})
            items = result.get("SearchResultItems") or []
            for item in items:
                job = _usajobs_job(item, home, radius)
                if job and job["id"] not in seen:
                    seen[job["id"]] = job
            pages = int(str((result.get("UserArea") or {}).get("NumberOfPages") or 1) or 1)
            print(f"  usajobs {query} page {page}/{pages}: {len(items)} items")
            if page >= pages or not items or page >= 20:
                break
            page += 1
            time.sleep(1)
    return list(seen.values())


def _usajobs_job(item: dict, home, radius: int) -> dict | None:
    d = item.get("MatchedObjectDescriptor") or {}
    det = (d.get("UserArea") or {}).get("Details") or {}
    control = str(item.get("MatchedObjectId") or d.get("PositionID") or "").strip()
    if not control:
        return None

    remote = str(det.get("RemoteIndicator", "")).lower() == "true"
    telework = str(det.get("TeleworkEligible", "")).lower() == "true"
    coords = []
    for loc in d.get("PositionLocation") or []:
        try:
            coords.append((float(loc["Latitude"]), float(loc["Longitude"])))
        except (KeyError, TypeError, ValueError):
            continue
    distance = round(min(haversine_miles(home, c) for c in coords), 1) if coords else None
    if not remote and (distance is None or distance > radius + 0.5):
        return None

    pay = _first(d.get("PositionRemuneration")) or {}
    pay_min, pay_max = _num(pay.get("MinimumRange")), _num(pay.get("MaximumRange"))
    interval = (pay.get("Description") or pay.get("RateIntervalCode") or "").lower()
    period = "hour" if "hour" in interval or interval == "ph" else "year"

    plan = _first(d.get("JobGrade"), "Code", "") or ""
    low, high = det.get("LowGrade"), det.get("HighGrade")
    grade = ""
    if plan and low:
        grade = f"{plan}-{low}" + (f"/{high}" if high and high != low else "")

    paths = [str(p).lower() for p in (det.get("HiringPath") or [])]
    who = (det.get("WhoMayApply") or {}).get("Name") or ""
    open_to_public = ("public" in paths) if paths else (True if re.search(r"u\.?s\.? citizens|public", who, re.I) else None)

    series = [c.get("Code") for c in d.get("JobCategory") or [] if c.get("Code")]
    categories = [c.get("Name") for c in d.get("JobCategory") or [] if c.get("Name")]
    summary = det.get("JobSummary") or d.get("QualificationSummary") or ""
    url = d.get("PositionURI") or f"https://www.usajobs.gov/job/{control}"
    apply_url = _first(d.get("ApplyURI")) or url

    duties = det.get("MajorDuties") or []
    if isinstance(duties, str):
        duties = [duties]
    detail_parts = [
        ("Summary", summary),
        ("Major duties", "\n".join(f"- {strip_html(x)}" for x in duties)),
        ("Qualifications", d.get("QualificationSummary") or ""),
        ("Requirements", det.get("Requirements") or ""),
        ("Education", det.get("Education") or ""),
        ("How you will be evaluated", det.get("Evaluations") or ""),
        ("Key requirements", "\n".join(f"- {x}" for x in det.get("KeyRequirements") or [])),
        ("Who may apply", who),
        ("Hiring paths", ", ".join(paths)),
        ("Security clearance", str(det.get("SecurityClearance") or "")),
        ("Telework eligible", "Yes" if telework else "No"),
        ("Remote", "Yes" if remote else "No"),
        ("Promotion potential", str(det.get("PromotionPotential") or "")),
        ("Travel", str(det.get("TravelCode") or "")),
    ]

    clearance = str(det.get("SecurityClearance") or "").strip()
    return {
        "id": f"usajobs:{control}",
        "source": "usajobs",
        "level": "Federal",
        "title": (d.get("PositionTitle") or "").strip(),
        "org": d.get("OrganizationName") or "",
        "department": d.get("DepartmentName") or "",
        "location": d.get("PositionLocationDisplay") or "",
        "distance_mi": distance,
        "remote": remote,
        "telework": telework,
        "salary_min": pay_min,
        "salary_max": pay_max,
        "salary_period": period,
        "grade": grade,
        "schedule": _first(d.get("PositionSchedule"), "Name", "") or "",
        "appointment": _first(d.get("PositionOfferingType"), "Name", "") or "",
        "posted": _iso(d.get("PublicationStartDate")),
        "closes": _iso(d.get("ApplicationCloseDate")),
        "open_to_public": open_to_public,
        "who_may_apply": shorten(who, 160),
        "clearance": "" if clearance.lower() in ("", "not required", "none", "not applicable") else clearance,
        "url": url,
        "apply_url": apply_url,
        "summary": shorten(strip_html(summary), 420),
        "series": series,
        "categories": categories,
        "_detail": "\n\n".join(f"{k}:\n{strip_html(v)}" for k, v in detail_parts if v and strip_html(v)),
    }


def _num(value) -> float | None:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _iso(value) -> str | None:
    parsed = parse_date(str(value)) if value else None
    return parsed.isoformat() if parsed else None


# --------------------------------------------------------------------------- NEOGOV (governmentjobs.com)

NEOGOV_LIST = "https://www.governmentjobs.com/careers/home/index?agency={slug}&sort=PostingDate&isDescendingSort=true&page={page}"


class NeogovGate:
    """One shared connection to governmentjobs.com for the whole run.

    The site stops accepting new connections from cloud runners after a few
    requests, so every page goes over one keep-alive connection with short gaps,
    and the first refused connection ends NEOGOV for the run. Listings from
    agencies we could not reach are kept from earlier runs until they close.
    """

    def __init__(self):
        self.session = requests.Session()
        retry = Retry(total=1, connect=0, read=1, status=1, backoff_factor=1,
                      status_forcelist=(429, 502, 503, 504), allowed_methods=("GET",))
        self.session.mount("https://", HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=retry))
        self.session.headers.update({
            "User-Agent": BROWSER_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        self.blocked = ""
        self.count = 0

    def get(self, url: str, **kwargs):
        if self.blocked:
            raise RuntimeError(self.blocked)
        try:
            resp = self.session.get(url, timeout=(8, 40), **kwargs)
        except (requests.ConnectionError, requests.Timeout) as exc:
            self.blocked = f"governmentjobs.com stopped answering after {self.count} pages this run ({type(exc).__name__})."
            raise RuntimeError(self.blocked) from exc
        self.count += 1
        if self.count == 1:
            keep = ("server", "connection", "keep-alive", "via", "x-cache", "x-iinfo", "cf-ray")
            print("  neogov response headers:", {k: v for k, v in resp.headers.items() if k.lower() in keep})
        time.sleep(0.4)
        return resp


def fetch_neogov(gate: NeogovGate, agency: dict, home: tuple[float, float], radius: int, today: date) -> list[dict]:
    slug = agency["slug"]
    jobs: dict[str, dict] = {}
    total = None
    seen_raw = 0
    for page in range(1, 41):
        try:
            resp = gate.get(NEOGOV_LIST.format(slug=slug, page=page), headers={
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"https://www.governmentjobs.com/careers/{slug}",
            })
            resp.raise_for_status()
        except Exception as exc:
            if jobs:
                raise PartialResult(list(jobs.values()), f"Read {page - 1} of the listing pages. {exc}") from exc
            raise
        if total is None:
            m = re.search(r'id="job-postings-number"[^>]*>\s*([\d,]+)', resp.text)
            total = int(m.group(1).replace(",", "")) if m else None
        batch, raw = _parse_neogov_html(resp.text, agency, home, radius, today)
        if page == 1 and not raw and total is None:
            raise RuntimeError(f"No job listing found for agency '{slug}' (the agency name may have changed).")
        seen_raw += raw
        for job in batch:
            jobs.setdefault(job["id"], job)
        if not raw or (total is not None and seen_raw >= total):
            break
    print(f"  neogov {slug}: {seen_raw} postings listed (site says {total}), {len(jobs)} within {radius} mi")
    return list(jobs.values())


def _neogov_base(agency: dict, title: str, location: str, home, radius) -> dict | None:
    coords = lookup(location) or lookup(agency.get("default_location", ""))
    distance = round(haversine_miles(home, coords), 1) if coords else None
    if distance is not None and distance > radius + 0.5:
        return None
    return {
        "source": f"neogov:{agency['slug']}",
        "level": agency.get("level", "Local"),
        "title": title,
        "org": agency["name"],
        "location": location or agency.get("default_location", ""),
        "distance_mi": distance,
        "remote": bool(re.search(r"\bremote\b", f"{title} {location}", re.I)),
        "telework": None,
        "grade": "",
        "open_to_public": None,
        "who_may_apply": "",
        "clearance": "",
        "series": [],
    }


_REL = re.compile(r"(today|tomorrow|yesterday|(?:in )?(\d+|an?) (hour|day|week|month|year)s?(?: ago)?)", re.I)


def _relative(text: str, today: date, future: bool) -> tuple[date | None, date | None]:
    """'Posted 6 days ago' / 'Closes in 1 week' -> (earliest, latest) possible date."""
    m = _REL.search(text or "")
    if not m:
        return None, None
    word = m.group(1).lower()
    if word == "today":
        return today, today
    if word in ("tomorrow", "yesterday"):
        d = today + timedelta(days=1 if word == "tomorrow" else -1)
        return d, d
    n = 1 if m.group(2).lower() in ("a", "an") else int(m.group(2))
    unit = m.group(3).lower()
    span = {"hour": (0, 0), "day": (n, n), "week": (7 * n, 7 * n + 6), "month": (30 * n, 30 * n + 29), "year": (365 * n, 365 * n + 364)}[unit]
    if future:
        return today + timedelta(days=span[0]), today + timedelta(days=span[1])
    return today - timedelta(days=span[1]), today - timedelta(days=span[0])


def _parse_neogov_html(html_text: str, agency: dict, home, radius, today: date) -> tuple[list[dict], int]:
    soup = BeautifulSoup(html_text, "html.parser")
    items = soup.select("li.list-item[data-job-id]") or soup.select("li.list-item")
    jobs = []
    for li in items:
        link = li.select_one("a.item-details-link") or li.find("a", href=re.compile(r"/jobs/\d+"))
        if not link:
            continue
        href = urljoin("https://www.governmentjobs.com", link.get("href", "").split("?")[0])
        job_no = li.get("data-job-id") or (re.search(r"/jobs/(\d+)", href) or [None, None])[1]
        title = link.get_text(" ", strip=True)
        meta = [x.get_text(" ", strip=True) for x in li.select("ul.list-meta li")]
        pay_text = next((x for x in meta if "$" in x), "")
        department = next((x.split(":", 1)[1].strip() for x in meta if x.lower().startswith("department:")), "") or link.get("data-department-name", "")
        category = next((x.split(":", 1)[1].strip() for x in meta if x.lower().startswith("category:")), "")
        location = next((x for x in meta if "$" not in x and ":" not in x), "")
        base = _neogov_base(agency, title, location, home, radius)
        if not base or not job_no:
            continue
        sal_min, sal_max, period = salary_range(pay_text)
        starts = li.select_one(".list-entry-starts")
        ends = li.select_one(".list-entry-ends")
        ends_text = ends.get_text(" ", strip=True) if ends else ""
        posted = _relative(starts.get_text(" ", strip=True) if starts else "", today, future=False)[0]
        closes = None if re.search(r"continuous|until filled", ends_text, re.I) else _relative(ends_text, today, future=True)[1]
        desc = li.select_one(".list-entry")
        summary = desc.get_text(" ", strip=True) if desc else ""
        schedule = "Full-time" if re.match(r"\s*FT\b", pay_text) else "Part-time" if re.match(r"\s*PT\b", pay_text) else ""
        base.update({
            "id": f"neogov:{agency['slug']}:{job_no}",
            "department": department,
            "salary_min": sal_min,
            "salary_max": sal_max,
            "salary_period": period,
            "schedule": schedule,
            "appointment": "",
            "posted": posted.isoformat() if posted else None,
            "closes": closes.isoformat() if closes else None,
            "closes_text": ends_text,
            "url": href,
            "apply_url": href,
            "summary": shorten(summary, 420),
            "categories": [category] if category else [],
            "_detail": "\n".join(x for x in [f"Department: {department}" if department else "", pay_text, f"Category: {category}" if category else "", summary] if x),
        })
        jobs.append(base)
    return jobs, len(items)


# --------------------------------------------------------------------------- Commonwealth of Virginia

VA_SEARCH = "https://www.jobs.virginia.gov/jobs/search?page={page}"


def fetch_virginia(session, cfg: dict, home: tuple[float, float], radius: int) -> list[dict]:
    jobs: dict[str, dict] = {}
    max_pages = int(cfg.get("max_pages", 200))
    total_rows = 0
    seen: set[str] = set()
    for page in range(1, max_pages + 1):
        try:
            resp = session.get(VA_SEARCH.format(page=page), timeout=60)
            resp.raise_for_status()
        except Exception as exc:
            if jobs:
                raise PartialResult(list(jobs.values()), f"Stopped at page {page}: {type(exc).__name__}") from exc
            raise
        rows = [r for r in _parse_virginia_rows(resp.text) if r["id"] not in seen]
        if not rows:
            break
        total_rows += len(rows)
        for row in rows:
            seen.add(row["id"])
            places = [c for c in (lookup(part) for part in row["location"].split(";")) if c]
            if not places:
                continue
            distance = round(min(haversine_miles(home, c) for c in places), 1)
            if distance > radius + 0.5:
                continue
            jobs[row["id"]] = {**row, "distance_mi": distance}
        if "page=%d" % (page + 1) not in resp.text:
            break
        time.sleep(0.7)
    print(f"  virginia: scanned {total_rows} statewide rows, {len(jobs)} within {radius} mi")
    return list(jobs.values())


def _parse_virginia_rows(html_text: str) -> list[dict]:
    soup = BeautifulSoup(html_text, "html.parser")
    out = []
    table = soup.find("table")
    if not table:
        return out
    headers = [th.get_text(" ", strip=True).lower() for th in table.select("thead th")]

    def col(cells, name, fallback):
        for i, h in enumerate(headers):
            if name in h and i < len(cells):
                return cells[i]
        return cells[fallback] if fallback < len(cells) else ""

    for tr in table.select("tbody tr"):
        tds = tr.find_all("td")
        link = tr.find("a", href=True)
        if not tds or not link:
            continue
        cells = ["; ".join(li.get_text(" ", strip=True) for li in td.find_all("li")) or td.get_text(" ", strip=True) for td in tds]
        href = urljoin("https://www.jobs.virginia.gov", link["href"])
        if "/jobs/search" in href:
            continue
        title = link.get_text(" ", strip=True)
        hiring = col(cells, "hiring", 6)
        sal_min, sal_max, period = salary_range(hiring)
        out.append({
            "id": "virginia:" + href.rstrip("/").rsplit("/", 1)[-1],
            "source": "virginia",
            "level": "State",
            "title": title,
            "org": col(cells, "agency", 5) or "Commonwealth of Virginia",
            "department": "Commonwealth of Virginia",
            "location": col(cells, "location", 3),
            "remote": bool(re.search(r"\b(remote|telework)\b", title, re.I)),
            "telework": None,
            "salary_min": sal_min,
            "salary_max": sal_max,
            "salary_period": period,
            "salary_text": shorten(hiring, 80),
            "grade": "",
            "schedule": col(cells, "employment", 2),
            "appointment": "",
            "posted": None,
            "closes": _iso(col(cells, "closing", 4)),
            "open_to_public": True,
            "who_may_apply": "",
            "clearance": "",
            "url": href,
            "apply_url": href,
            "summary": "",
            "series": [],
            "categories": [c.strip() for c in col(cells, "category", 1).split(";") if c.strip()],
            "_detail": "",
        })
    return out


def virginia_detail(session, url: str) -> str:
    """Fetch a state posting's description (used only for jobs that get an AI brief)."""
    resp = session.get(url, timeout=60)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    main = soup.find("main") or soup.body or soup
    return shorten(main.get_text("\n", strip=True), 12000)
