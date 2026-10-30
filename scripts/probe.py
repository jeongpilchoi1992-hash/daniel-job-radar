"""One-off diagnostics: checks which public job endpoints answer from GitHub Actions.

Prints status codes and short snippets so the collector can be tuned from the
workflow logs. Safe to delete once the sources are stable.
"""

from __future__ import annotations

import os
import re
import sys

import requests

UA_BOT = "daniel-job-radar/1.0 (+https://github.com/jeongpilchoi1992-hash/daniel-job-radar)"
UA_BROWSER = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0 Safari/537.36"
)

NEOGOV_SLUGS = [
    "fairfaxcounty", "pwcgov", "pwcounty", "princewilliamcounty", "pwcva",
    "arlington", "arlingtonva", "arlingtoncounty", "alexandria", "alexandriava",
    "cityofalexandria", "loudoun", "loudouncounty", "manassas", "manassasva",
    "manassascity", "cityofmanassas", "manassaspark", "manassasparkva",
    "fairfaxva", "cityoffairfax", "fairfaxcity", "fallschurch", "fallschurchva",
    "fauquier", "fauquiercounty", "stafford", "staffordcounty", "staffordcountyva",
    "leesburg", "leesburgva", "herndon", "herndonva", "viennava", "fredericksburg",
    "fredericksburgva", "spotsylvania", "spotsylvaniacounty", "pgc", "pgcounty",
    "princegeorgescountymd", "montgomerycountymd", "mwcog", "nvrc", "vre",
    "omniride", "fairfaxwater", "dc", "dcgov",
]


def get(url: str, ua: str = UA_BROWSER, **kw) -> requests.Response | None:
    headers = {"User-Agent": ua, "Accept": "text/html,application/xhtml+xml,application/xml,application/json;q=0.9,*/*;q=0.8"}
    headers.update(kw.pop("headers", {}))
    try:
        return requests.get(url, headers=headers, timeout=30, **kw)
    except requests.RequestException as exc:
        print(f"  ! {url} -> {type(exc).__name__}: {exc}")
        return None


def title_of(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    return re.sub(r"\s+", " ", m.group(1)).strip()[:120] if m else ""


def snippet(text: str, n: int = 1500) -> str:
    return re.sub(r"\s+", " ", text)[:n]


def section(name: str) -> None:
    print("\n" + "=" * 20 + f" {name} " + "=" * 20, flush=True)


def probe_neogov() -> None:
    section("NEOGOV agency slugs")
    for slug in NEOGOV_SLUGS:
        r = get(f"https://www.governmentjobs.com/careers/{slug}")
        if r is None:
            continue
        print(f"  {slug:24s} {r.status_code} final={r.url[:80]} title={title_of(r.text)!r}")

    section("NEOGOV feeds / ajax (fairfaxcounty)")
    urls = [
        "https://www.governmentjobs.com/SearchEngine/JobsFeed?agency=fairfaxcounty",
        "https://agency.governmentjobs.com/jobfeed.cfm?agency=fairfaxcounty",
        "https://agency.governmentjobs.com/fairfaxcounty/default.cfm?format=xml&promotionaljobs=0&transfer=0",
        "https://www.governmentjobs.com/careers/fairfaxcounty/rss",
        "https://www.governmentjobs.com/careers/fairfaxcounty/jobs/feed",
        "https://www.governmentjobs.com/careers/home/index?agency=fairfaxcounty&sort=PostingDate&isDescendingSort=true",
    ]
    for url in urls:
        for ua in (UA_BOT, UA_BROWSER):
            r = get(url, ua=ua, headers={"X-Requested-With": "XMLHttpRequest"} if "home/index" in url else {})
            if r is None:
                continue
            print(f"\n  [{('bot' if ua == UA_BOT else 'browser')}] {url}\n  -> {r.status_code} {r.headers.get('content-type')} final={r.url[:100]} len={len(r.text)}")
            print("  " + snippet(r.text, 1200))

    section("NEOGOV careers page structure (fairfaxcounty)")
    r = get("https://www.governmentjobs.com/careers/fairfaxcounty")
    if r is not None:
        html = r.text
        for pat in [r"jobs/feed[^\"']*", r"rss[^\"']{0,80}", r"/careers/home/index[^\"']*", r"data-[a-z-]*url=\"[^\"]+\"", r"list-item[^>]{0,200}"]:
            found = sorted(set(re.findall(pat, html, re.I)))[:8]
            print(f"  pattern {pat!r}: {found}")
        i = html.find("list-item")
        print("  around list-item: " + snippet(html[max(0, i - 300): i + 2500], 2800))

    section("governmentjobs.com location search")
    for url in [
        "https://www.governmentjobs.com/jobs?location=Manassas%2C%20VA&distance=50",
        "https://www.governmentjobs.com/jobs?keyword=&location=Manassas,+VA&distance=50&page=1",
    ]:
        for xhr in (False, True):
            r = get(url, headers={"X-Requested-With": "XMLHttpRequest"} if xhr else {})
            if r is None:
                continue
            print(f"\n  xhr={xhr} {url}\n  -> {r.status_code} {r.headers.get('content-type')} len={len(r.text)} title={title_of(r.text)!r}")
            i = r.text.find("job-item")
            print("  " + snippet(r.text[max(0, i - 200): i + 2000] if i >= 0 else r.text, 2000))


def probe_virginia() -> None:
    section("Virginia jobs (jobs.virginia.gov)")
    for url in [
        "https://www.jobs.virginia.gov/jobs/search?page=1",
        "https://www.jobs.virginia.gov/jobs/search?query=Fairfax",
        "https://www.jobs.virginia.gov/jobs/search?location=Fairfax",
        "https://www.jobs.virginia.gov/jobs/search?city%5B%5D=Fairfax",
        "https://www.jobs.virginia.gov/jobs/search?cities%5B%5D=Fairfax",
    ]:
        r = get(url)
        if r is None:
            continue
        html = r.text
        rows = len(re.findall(r"<tr", html, re.I))
        m = re.search(r"Displaying[^<]{0,80}", html)
        print(f"\n  {url}\n  -> {r.status_code} len={len(html)} rows={rows} {m.group(0) if m else ''}")
        if url.endswith("page=1"):
            names = sorted(set(re.findall(r"name=\"([^\"]+)\"", html)))[:60]
            print(f"  input names: {names}")
            forms = re.findall(r"<form[^>]*>", html, re.I)[:5]
            print(f"  forms: {forms}")
            scripts = re.findall(r"<script[^>]+src=\"([^\"]+)\"", html, re.I)[:15]
            print(f"  scripts: {scripts}")
            i = html.find("<tbody")
            print("  first rows: " + snippet(html[i: i + 3000], 3000))
            j = html.find("City")
            print("  facet area: " + snippet(html[j: j + 1500], 1500))

    section("PageUp feeds")
    for url in [
        "https://careers.pageuppeople.com/1125/cw/en-us/rss",
        "https://careers.pageuppeople.com/1125/caw/en-us/rss",
        "https://careers.pageuppeople.com/1125/cw/en-us/listing/",
    ]:
        r = get(url)
        if r is not None:
            print(f"  {url} -> {r.status_code} {r.headers.get('content-type')} len={len(r.text)} {snippet(r.text, 300)}")

    section("Virginia job detail")
    r = get("https://www.jobs.virginia.gov/jobs/search?page=1")
    if r is not None:
        links = re.findall(r"href=\"(https://www\.jobs\.virginia\.gov/jobs/(?!search)[^\"]+)\"", r.text)
        if links:
            d = get(links[0])
            if d is not None:
                print(f"  {links[0]} -> {d.status_code} len={len(d.text)}")
                for pat in [r"application/ld\+json", r"JobPosting", r"datePosted", r"validThrough", r"pageuppeople[^\"']*"]:
                    print(f"  {pat}: {len(re.findall(pat, d.text))} {re.findall(pat, d.text)[:2]}")
                k = d.text.find("ld+json")
                if k >= 0:
                    print("  ld+json: " + snippet(d.text[k: k + 2500], 2500))


def probe_usajobs() -> None:
    section("USAJOBS")
    key = os.environ.get("USAJOBS_API_KEY")
    email = os.environ.get("USAJOBS_EMAIL")
    if not key or not email:
        print("  skipped: USAJOBS_API_KEY / USAJOBS_EMAIL not set")
        return
    r = get(
        "https://data.usajobs.gov/api/search?LocationName=Manassas,%20Virginia&Radius=50&ResultsPerPage=2",
        ua=email,
        headers={"Host": "data.usajobs.gov", "Authorization-Key": key},
    )
    if r is not None:
        print(f"  -> {r.status_code} len={len(r.text)}")
        print("  " + snippet(r.text, 4000))


if __name__ == "__main__":
    which = sys.argv[1:] or ["neogov", "virginia", "usajobs"]
    if "neogov" in which:
        probe_neogov()
    if "virginia" in which:
        probe_virginia()
    if "usajobs" in which:
        probe_usajobs()
