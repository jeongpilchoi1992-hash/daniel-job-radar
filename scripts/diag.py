"""Temporary diagnostics for the launch (removed before merge)."""

import re
import sys
import time
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, "scripts")
from places import haversine_miles, lookup  # noqa: E402

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
HOME = (38.7509, -77.4753)
T0 = time.time()
VA = "https://www.jobs.virginia.gov/jobs/search?"


def stamp():
    return f"[{time.time() - T0:6.1f}s]"


def session():
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    return s


def va_get(s, q):
    r = s.get(VA + q, timeout=60)
    soup = BeautifulSoup(r.text, "html.parser")
    trs = soup.select("table tbody tr")
    total = re.search(r"of\s*<b>\s*([\d,]+)\s*</b>\s*in total", r.text)
    locs = [td.get_text(" ", strip=True)[:20] for td in soup.select("td.job-search-results-location")[:3]]
    hdr = {k: v[:80] for k, v in r.headers.items() if k.lower().startswith(("x-amz", "server", "retry", "x-cache", "via", "cf-", "set-cookie"))}
    print(f"{stamp()} VA ?{q[:90]} -> {r.status_code} len={len(r.text)} rows={len(trs)} total={total.group(1) if total else None} {locs} {hdr}", flush=True)
    return r, soup


def virginia():
    s = session()
    r, soup = va_get(s, "page=1")
    print("  cookies:", [c.name for c in s.cookies])
    print("  input names:", sorted({i.get("name") for i in soup.select("form input[name]")}))
    cities = [i.get("value") for i in soup.select("input[name='cities[]']")]
    print("  cities[] count", len(cities))
    print("  ALL CITIES:", " | ".join(cities))
    near = [c for c in cities if (co := lookup(c)) and haversine_miles(HOME, co) <= 50.5]
    print("  NEAR:", near)
    time.sleep(20)
    va_get(s, "per_page=100")
    time.sleep(20)
    q = "&".join("cities%5B%5D=" + quote(c) for c in near)
    r, soup = va_get(s, q)
    m = re.search(r"of\s*<b>\s*([\d,]+)", r.text)
    total = int(m.group(1).replace(",", "")) if m else 0
    pages = (total + 29) // 30
    print(f"  near-city query: {total} jobs, {pages} pages")
    for page in range(2, min(pages, 30) + 1):
        time.sleep(12)
        r, _ = va_get(s, q + f"&page={page}")
        if r.status_code != 200:
            print("  non-200 body:", r.text[:700].replace("\n", " "))
            r2, _ = va_get(session(), q + f"&page={page}")
            print("  fresh session ->", r2.status_code)
            for wait in (60, 120, 240):
                time.sleep(wait)
                r3, _ = va_get(s, q + f"&page={page}")
                if r3.status_code == 200:
                    print(f"  recovered after waiting {wait}s more")
                    break
            break


def neogov():
    s = session()
    s.headers.update({"X-Requested-With": "XMLHttpRequest"})
    r = s.get("https://www.governmentjobs.com/careers/home/index?agency=arlington&sort=PostingDate&isDescendingSort=true&page=1", timeout=(8, 30))
    print("ARLINGTON 991 body:", r.text[:1000].replace("\n", " "))
    slugs = ["stafford", "fairfaxva", "leesburgva", "vienna", "fallschurchcity", "cityoffallschurch", "manassasparkva",
             "cityofmanassaspark", "townofherndon", "townofvienna", "fauquiercountyva", "culpeper", "culpepercounty",
             "culpepercountyva", "warrencountyva", "spotsylvania", "spotsylvaniacounty", "spotsylvaniacountyva",
             "fredericksburgcity", "cityoffredericksburg", "dumfries", "townofdumfries", "purcellville", "frontroyal",
             "frontroyalva", "winchester", "frederickcountyva", "fcva", "clarkecounty", "kinggeorgecounty", "kinggeorge",
             "princewilliam", "pwcs", "lcps", "fcps", "nvcc", "mwaa", "dcgov", "prtc", "omniride", "nvtc", "novaparks",
             "fairfaxwater", "loudounwater", "uosa", "warrenton", "townofwarrenton", "haymarket", "occoquan"]
    for slug in slugs:
        time.sleep(0.4)
        try:
            r = s.get(f"https://www.governmentjobs.com/careers/home/index?agency={slug}&sort=PostingDate&isDescendingSort=true&page=1", timeout=(8, 30))
        except Exception as exc:  # noqa: BLE001
            print(f"  neogov {slug}: {type(exc).__name__}")
            break
        m = re.search(r'id="job-postings-number"[^>]*>\s*([\d,]+)', r.text)
        if not m:
            print(f"  neogov {slug}: none ({len(r.text)})")
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        locs = [li.get_text(" ", strip=True)[:40] for li in soup.select("li.list-item ul.list-meta li")[:4]]
        try:
            page = s.get(f"https://www.governmentjobs.com/careers/{slug}", timeout=(8, 30)).text
            title = re.search(r"<title>(.*?)</title>", page, re.S)
            title = re.sub(r"\s+", " ", title.group(1)).strip() if title else None
        except Exception as exc:  # noqa: BLE001
            title = type(exc).__name__
        print(f"  neogov {slug}: postings={m.group(1)} title={title!r} meta={locs}")


def page_probe(name, url, link_pattern):
    s = session()
    try:
        r = s.get(url, timeout=40)
    except Exception as exc:  # noqa: BLE001
        print(f"{name}: {type(exc).__name__} {exc}"[:300])
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else None
    links = sorted({urljoin(r.url, a["href"]) for a in soup.find_all("a", href=True) if re.search(link_pattern, a["href"], re.I)})
    feeds = [l.get("href") for l in soup.find_all("link", type=re.compile("rss|atom|json", re.I))]
    scripts = [sc.get("src") for sc in soup.find_all("script", src=True)][:12]
    print(f"{name}: {r.status_code} final={r.url} len={len(r.text)} title={title!r}")
    print(f"  feeds={feeds}")
    print(f"  scripts={scripts}")
    print(f"  {len(links)} links: {links[:40]}")
    return r


def other_sources():
    page_probe("arlington careers", "https://www.arlingtonva.us/Government/Careers", r"job|career|apply|recruit")
    r = page_probe("arlington jobboard", "https://jobboard.arlingtonva.us/", r"/job/|search|api")
    if r is not None:
        print("  head:", r.text[:1500].replace("\n", " "))
        for m in re.finditer(r"https?://[^\"' ]*(?:api|graphql|search)[^\"' ]*", r.text):
            print("  endpoint:", m.group(0)[:160])
    page_probe("senate", "https://careers.employment.senate.gov/", r"/job/|jobs|search|rss|feed")
    page_probe("senate jobs", "https://careers.employment.senate.gov/jobs", r"/job/|page=|rss|feed")
    page_probe("dc council", "https://dccouncil.gov/jobs-solicitations/", r"jobs-solicitations/|vacanc")
    page_probe("house", "https://www.house.gov/employment", r"vacanc|employment|job|pdf")


if __name__ == "__main__":
    other_sources()
    neogov()
    virginia()
