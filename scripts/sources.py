"""Job source collectors.

Each collector returns a list of job dicts in the shared shape (see collect.py).
A private "_detail" key carries the full posting text for the AI step; it is
dropped before anything is written to disk.
"""

from __future__ import annotations

import os
import re
import time
import xml.etree.ElementTree as ET
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from common import SourceSkipped, parse_date, salary_range, shorten, strip_html
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

NEOGOV_NS = {"joblisting": "http://www.neogov.com/namespaces/JobListing"}
NEOGOV_FEEDS = [
    "https://www.governmentjobs.com/SearchEngine/JobsFeed?agency={slug}",
    "https://agency.governmentjobs.com/jobfeed.cfm?agency={slug}",
]
NEOGOV_LIST = "https://www.governmentjobs.com/careers/home/index?agency={slug}&sort=PostingDate&isDescendingSort=true&page={page}"


def fetch_neogov(session, agency: dict, home: tuple[float, float], radius: int) -> list[dict]:
    slug = agency["slug"]
    errors = []
    for template in NEOGOV_FEEDS:
        url = template.format(slug=slug)
        try:
            resp = session.get(url, timeout=60)
        except Exception as exc:  # noqa: BLE001 - try the next strategy
            errors.append(f"{url}: {exc}")
            continue
        if resp.ok and "<rss" in resp.text[:2000]:
            jobs = _parse_neogov_rss(resp.text, agency, home, radius)
            print(f"  neogov {slug}: feed {url} -> {len(jobs)} jobs")
            return jobs
        errors.append(f"{url}: HTTP {resp.status_code}")

    jobs: list[dict] = []
    for page in range(1, 30):
        url = NEOGOV_LIST.format(slug=slug, page=page)
        resp = session.get(url, headers={"X-Requested-With": "XMLHttpRequest"}, timeout=60)
        if not resp.ok:
            errors.append(f"{url}: HTTP {resp.status_code}")
            break
        batch = _parse_neogov_html(resp.text, agency, home, radius)
        new = [j for j in batch if j["id"] not in {x["id"] for x in jobs}]
        if not new:
            break
        jobs.extend(new)
        time.sleep(1)
    if not jobs and errors:
        raise RuntimeError("; ".join(errors[-3:]))
    print(f"  neogov {slug}: html list -> {len(jobs)} jobs")
    return jobs


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


def _parse_neogov_rss(xml_text: str, agency: dict, home, radius) -> list[dict]:
    root = ET.fromstring(xml_text.encode("utf-8"))
    jobs = []
    for item in root.iter("item"):
        def tag(name: str) -> str:
            el = item.find(f"joblisting:{name}", NEOGOV_NS)
            return (el.text or "").strip() if el is not None and el.text else ""

        title = (item.findtext("title") or "").strip()
        location = ", ".join(x for x in [tag("location"), tag("state")] if x)
        base = _neogov_base(agency, title, location, home, radius)
        if not base or not title:
            continue
        job_id = tag("jobId") or (item.findtext("guid") or item.findtext("link") or title)
        link = (item.findtext("link") or "").strip()
        closes_raw = tag("advertiseToDateTime")
        sal_min, sal_max = _num(tag("minimumSalary")), _num(tag("maximumSalary"))
        interval = tag("salaryInterval").lower()
        description = strip_html(item.findtext("description") or "")
        categories = [c.findtext("Category") or "" for c in item.iter("category")]
        base.update({
            "id": f"neogov:{agency['slug']}:{job_id}",
            "department": tag("department"),
            "salary_min": sal_min,
            "salary_max": sal_max,
            "salary_period": "hour" if "hour" in interval else ("year" if sal_min or sal_max else None),
            "schedule": tag("jobType"),
            "appointment": "",
            "posted": _iso(tag("advertiseFromDate") or item.findtext("pubDate")),
            "closes": None if re.search(r"continuous", closes_raw, re.I) else _iso(closes_raw),
            "url": link,
            "apply_url": link,
            "summary": shorten(description, 420),
            "categories": [c for c in categories if c],
            "_detail": description,
        })
        jobs.append(base)
    return jobs


def _parse_neogov_html(html_text: str, agency: dict, home, radius) -> list[dict]:
    soup = BeautifulSoup(html_text, "html.parser")
    jobs = []
    for li in soup.select("li.list-item"):
        link = li.select_one("a.item-details-link") or li.find("a", href=re.compile(r"/jobs/\d+"))
        if not link:
            continue
        href = urljoin("https://www.governmentjobs.com", link.get("href", "").split("?")[0])
        m = re.search(r"/jobs/(\d+)", href)
        title = link.get_text(" ", strip=True)
        meta = [x.get_text(" ", strip=True) for x in li.select("ul.list-meta li")]
        location = meta[0] if meta else ""
        base = _neogov_base(agency, title, location, home, radius)
        if not base or not m:
            continue
        pay_text = next((x for x in meta if "$" in x), "")
        sal_min, sal_max, period = salary_range(pay_text)
        text = li.get_text(" ", strip=True)
        closes = None
        cm = re.search(r"(?:Closing|Closes|Deadline)[^0-9A-Za-z]*(\w+ \d{1,2},? \d{4}|\d{1,2}/\d{1,2}/\d{4})", text, re.I)
        if cm:
            closes = _iso(cm.group(1))
        desc = li.select_one(".list-entry, .list-description")
        summary = desc.get_text(" ", strip=True) if desc else ""
        base.update({
            "id": f"neogov:{agency['slug']}:{m.group(1)}",
            "department": next((x for x in meta[2:] if "$" not in x), ""),
            "salary_min": sal_min,
            "salary_max": sal_max,
            "salary_period": period,
            "schedule": pay_text.split(" - ")[0] if " - " in pay_text else "",
            "appointment": "",
            "posted": None,
            "closes": closes,
            "url": href,
            "apply_url": href,
            "summary": shorten(summary, 420),
            "categories": [],
            "_detail": summary,
        })
        jobs.append(base)
    return jobs


# --------------------------------------------------------------------------- Commonwealth of Virginia

VA_SEARCH = "https://www.jobs.virginia.gov/jobs/search?page={page}"


def fetch_virginia(session, cfg: dict, home: tuple[float, float], radius: int) -> list[dict]:
    jobs: dict[str, dict] = {}
    max_pages = int(cfg.get("max_pages", 200))
    total_rows = 0
    for page in range(1, max_pages + 1):
        resp = session.get(VA_SEARCH.format(page=page), timeout=60)
        resp.raise_for_status()
        rows = _parse_virginia_rows(resp.text)
        if not rows:
            break
        total_rows += len(rows)
        for row in rows:
            coords = lookup(row["location"])
            if not coords:
                continue
            distance = round(haversine_miles(home, coords), 1)
            if distance > radius + 0.5:
                continue
            jobs[row["id"]] = {**row, "distance_mi": distance}
        if "page=%d" % (page + 1) not in resp.text and "page=%d\"" % (page + 1) not in resp.text:
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
        cells = [td.get_text(" ", strip=True) for td in tds]
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
            "categories": [c.strip() for c in col(cells, "category", 1).split(",") if c.strip()],
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
