"""Legislative-branch job boards near home: U.S. Senate, U.S. House, and the DC Council.

All three publish their openings on public pages, so this needs no keys. Each
fetcher records the postings it saw in LISTED (by host) when it read the whole
board, so the link check can drop launch-day AI finds that left the board.
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup

from boards import posting_key
from common import PartialResult, salary_range, shorten, strip_html
from places import haversine_miles, lookup

LISTED: dict[str, set[str]] = {}

SKIP_TITLE = re.compile(r"\bintern(s|ship|ships)?\b", re.I)


def _job(source: str, org: str, title: str, location: str, url: str, home, radius: int, **extra) -> dict | None:
    if not title or not url or SKIP_TITLE.search(title):
        return None
    coords = lookup(location)
    if not coords:
        return None
    distance = round(haversine_miles(home, coords), 1)
    if distance > radius + 0.5:
        return None
    salary_text = extra.pop("salary_text", "")
    sal_min, sal_max, period = salary_range(salary_text)
    job = {
        "id": f"{source}:{posting_key(url)}",
        "source": source,
        "level": "Legislative",
        "title": shorten(title, 160),
        "org": org,
        "department": org,
        "location": location,
        "distance_mi": distance,
        "remote": False,
        "telework": None,
        "salary_min": sal_min,
        "salary_max": sal_max,
        "salary_period": period,
        "salary_text": shorten(salary_text, 80),
        "grade": "",
        "schedule": "",
        "appointment": "",
        "posted": None,
        "closes": None,
        "open_to_public": True,
        "who_may_apply": "",
        "clearance": "",
        "url": url,
        "apply_url": url,
        "summary": "",
        "series": [],
        "categories": [],
    }
    job.update(extra)
    return job


# --------------------------------------------------------------------------- U.S. Senate

SENATE_JOBS = "https://careers.employment.senate.gov/jobs"
SENATE_PAGE = 25  # the board adds 25 postings per page; ?page=N lists the first N*25


def fetch_senate(session, home, radius: int) -> list[dict]:
    resp = session.get(SENATE_JOBS, timeout=60)
    resp.raise_for_status()
    m = re.search(r"([\d,]+)\s+Jobs?\b", BeautifulSoup(resp.text, "html.parser").get_text(" "))
    total = int(m.group(1).replace(",", "")) if m else 0
    if total > SENATE_PAGE:
        resp = session.get(SENATE_JOBS, params={"page": math.ceil(total / SENATE_PAGE)}, timeout=60)
        resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    cards = soup.select("li[data-testid=jobs-list-item]")
    if not cards:
        raise RuntimeError(f"No job cards on {resp.url} ({len(resp.text)} bytes); the page layout may have changed.")
    jobs, listed = [], set()
    for card in cards:
        link = card.select_one("a[data-testid=jobs-list-item-link]") or card.find("a", href=re.compile(r"/job/"))
        if not link:
            continue
        url = link["href"]
        listed.add(posting_key(url))
        lines = [d.get_text(" ", strip=True) for d in card.select(".location .small")]
        office = lines[0] if len(lines) > 1 else "U.S. Senate"
        location = lines[-1] if lines else ""
        cells = {}
        for row in card.select("table tr"):
            tds = row.find_all("td")
            if len(tds) == 2:
                cells[tds[0].get_text(" ", strip=True).lower()] = tds[1].get_text(" ", strip=True)
        if re.search(r"intern", cells.get("position type", ""), re.I):
            continue
        org = office if re.search(r"senat|committee|secretary|sergeant|chaplain|capitol", office, re.I) else f"U.S. Senate: {office}"
        job = _job("senate", org, link.get_text(" ", strip=True), location, url, home, radius,
                   salary_text=cells.get("salary", ""), summary=f"U.S. Senate opening with {office}.")
        if job:
            jobs.append(job)
    print(f"  senate: {len(cards)} of {total} postings read, {len(jobs)} near home (internships left out)")
    if not total or len(cards) < total:
        raise PartialResult(jobs, f"Read {len(cards)} of the {total or 'unknown number of'} postings the board lists.")
    LISTED["careers.employment.senate.gov"] = listed
    return jobs


# --------------------------------------------------------------------------- U.S. House (Cornerstone career sites)

HOUSE_HOST = "https://house.csodfed.com"
HOUSE_SITES = {
    19: "U.S. House: Member and committee offices",
    7: "U.S. House Resume Bank",
    1: "U.S. House: Chief Administrative Officer",
    5: "U.S. House: Office of the Clerk",
    6: "U.S. House: Sergeant at Arms",
    17: "U.S. House: Office of the Legislative Counsel",
    18: "U.S. House: Office of Inspector General",
}


def _csod_token(session, site: int) -> str:
    resp = session.get(f"{HOUSE_HOST}/ux/ats/careersite/{site}/home", params={"c": "house"}, timeout=60)
    resp.raise_for_status()
    m = re.search(r'"token"\s*:\s*"([^"]+)"', resp.text)
    if not m:
        raise RuntimeError(f"No access token on the House career site {site} page ({len(resp.text)} bytes).")
    return m.group(1)


def fetch_house(session, home, radius: int) -> list[dict]:
    jobs: dict[str, dict] = {}
    listed: set[str] = set()
    complete = True
    for site, org in HOUSE_SITES.items():
        token = _csod_token(session, site)
        seen = 0
        for page in range(1, 21):
            body = {
                "careerSiteId": site, "careerSitePageId": site, "pageNumber": page, "pageSize": 50,
                "cultureId": 1, "searchText": "", "cultureName": "en-US", "states": [], "countryCodes": [],
                "cities": [], "placeID": "", "radius": None, "postingsWithinDays": None,
                "customFieldCheckboxKeys": [], "customFieldDropdowns": [], "customFieldRadios": [],
            }
            resp = session.post(f"{HOUSE_HOST}/services/x/career-site/v1/search", json=body, timeout=60,
                                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
            if resp.status_code >= 400:
                raise RuntimeError(f"House career site {site} search returned HTTP {resp.status_code}: {resp.text[:200]}")
            data = (resp.json() or {}).get("data") or {}
            reqs = data.get("requisitions") or []
            for req in reqs:
                rid = req.get("requisitionId")
                url = f"{HOUSE_HOST}/ux/ats/careersite/{site}/home/requisition/{rid}?c=house"
                listed.add(posting_key(url))
                places = req.get("locations") or []
                where = [", ".join(x for x in [p.get("city"), p.get("state")] if x) for p in places]
                location = next((w for w in where if lookup(w)), where[0] if where else "Washington, DC")
                posted = (req.get("postingEffectiveDate") or "")[:10] or None
                job = _job("house", org, req.get("displayJobTitle") or "", location, url, home, radius,
                           posted=posted, summary=shorten(strip_html(req.get("externalDescription") or ""), 420))
                if job:
                    jobs[job["id"]] = job
            seen += len(reqs)
            total = int(data.get("totalCount") or 0)
            if not reqs or seen >= total:
                complete = complete and seen >= total and (total > 0 or not reqs)
                break
        else:
            complete = False  # stopped at the page limit
    print(f"  house: {len(listed)} postings on {len(HOUSE_SITES)} career sites, {len(jobs)} near home (internships left out)")
    if not complete:
        raise PartialResult(list(jobs.values()), "A House career site listed more postings than were read.")
    LISTED["house.csodfed.com"] = listed
    return list(jobs.values())


# --------------------------------------------------------------------------- DC Council

DC_COUNCIL_FEED = "https://dccouncil.gov/jobs-solicitations/feed/"
NOT_A_JOB = re.compile(r"form dc2000|application for employment|volunteer|solicitation|request for (proposal|quote|information)|\brf[pqi]\b", re.I)


def fetch_dc_council(session, home, radius: int) -> list[dict]:
    resp = session.get(DC_COUNCIL_FEED, timeout=60)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    jobs = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        url = (item.findtext("link") or "").strip()
        if not title or NOT_A_JOB.search(title):
            continue
        try:
            posted = parsedate_to_datetime(item.findtext("pubDate") or "").date().isoformat()
        except (TypeError, ValueError):
            posted = None
        summary = shorten(strip_html(item.findtext("description") or "").split("The post ")[0], 420)
        job = _job("dccouncil", "Council of the District of Columbia", title, "Washington, DC", url, home, radius,
                   posted=posted, summary=summary)
        if job:
            jobs.append(job)
    print(f"  dc council: {len(jobs)} job postings in the feed")
    return jobs
