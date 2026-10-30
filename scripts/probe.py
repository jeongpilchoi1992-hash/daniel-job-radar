"""One-off diagnostics: checks which public job endpoints answer from GitHub Actions.

Prints status codes and short snippets so the collector can be tuned from the
workflow logs. Requests are spaced out because governmentjobs.com throttles bursts.
"""

from __future__ import annotations

import os
import re
import sys
import time

import requests

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0 Safari/537.36"
)
GAP = 6  # seconds between governmentjobs.com requests


def get(url: str, **headers) -> requests.Response | None:
    h = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml,application/json;q=0.9,*/*;q=0.8"}
    h.update(headers)
    t = time.time()
    try:
        r = requests.get(url, headers=h, timeout=(15, 30))
        print(f"  [{time.time() - t:.1f}s] {r.status_code} {r.headers.get('content-type', '')[:40]} len={len(r.text)} {url}")
        return r
    except requests.RequestException as exc:
        print(f"  [{time.time() - t:.1f}s] ! {type(exc).__name__} {url}")
        return None


def snip(text: str, n: int) -> str:
    return re.sub(r"\s+", " ", text)[:n]


def section(name: str) -> None:
    print("\n" + "=" * 16 + f" {name} " + "=" * 16)


def probe_neogov() -> None:
    section("NEOGOV endpoints (fairfaxcounty)")
    tries = [
        ("https://www.governmentjobs.com/careers/home/index?agency=fairfaxcounty&sort=PostingDate&isDescendingSort=true", {"X-Requested-With": "XMLHttpRequest"}),
        ("https://www.governmentjobs.com/careers/home/index?agency=fairfaxcounty&sort=PostingDate&isDescendingSort=true&page=2", {"X-Requested-With": "XMLHttpRequest"}),
        ("https://www.governmentjobs.com/SearchEngine/JobsFeed?agency=fairfaxcounty", {}),
        ("https://agency.governmentjobs.com/jobfeed.cfm?agency=fairfaxcounty", {}),
        ("https://www.governmentjobs.com/careers/fairfaxcounty", {}),
    ]
    for url, headers in tries:
        r = get(url, **headers)
        if r is not None:
            body = r.text
            i = body.find("list-item")
            print("    final:", r.url[:120])
            print("    head:", snip(body, 600))
            if i >= 0:
                print("    list-item area:", snip(body[max(0, i - 200): i + 3000], 3200))
            for pat in [r"rss|feed", r"data-[a-z-]+=\"[^\"]{0,80}\"", r"pagination[^>]{0,200}", r"/careers/home/index[^\"' ]*"]:
                found = sorted(set(re.findall(pat, body, re.I)))[:10]
                print(f"    {pat!r}: {found}")
        time.sleep(GAP)

    section("More NEOGOV slugs")
    for slug in ["fallschurch", "fallschurchva", "fairfaxva", "fauquier", "fauquiercounty", "staffordcounty",
                 "staffordcountyva", "manassaspark", "leesburgva", "herndonva", "fredericksburgva", "pgcounty"]:
        r = get(f"https://www.governmentjobs.com/careers/{slug}")
        if r is not None:
            m = re.search(r"<title[^>]*>(.*?)</title>", r.text, re.S | re.I)
            print(f"    {slug}: final={r.url[:80]} title={snip(m.group(1), 90) if m else ''!r}")
        time.sleep(GAP)


def probe_virginia() -> None:
    section("Virginia jobs")
    r = get("https://www.jobs.virginia.gov/jobs/search?page=1")
    if r is None:
        return
    html = r.text
    print("    rows:", len(re.findall(r"<tr", html, re.I)), "| tables:", len(re.findall(r"<table", html, re.I)))
    m = re.search(r"Displaying[^<]{0,80}", html)
    print("    ", m.group(0) if m else "no 'Displaying' text")
    i = html.find("<table")
    print("    table:", snip(html[i: i + 3500], 3500))
    names = sorted(set(re.findall(r"name=\"([^\"]+)\"", html)))[:50]
    print("    input names:", names)
    links = re.findall(r"href=\"([^\"]*/jobs/(?!search)[^\"]+)\"", html)
    print("    job links:", links[:3])
    if links:
        url = links[0] if links[0].startswith("http") else "https://www.jobs.virginia.gov" + links[0]
        time.sleep(2)
        d = get(url)
        if d is not None:
            for pat in [r"application/ld\+json", r"\"@type\"\s*:\s*\"JobPosting\"", r"validThrough", r"pageuppeople[^\"' ]*"]:
                print(f"    detail {pat!r}: {len(re.findall(pat, d.text))}")
            k = d.text.find("ld+json")
            if k >= 0:
                print("    ld+json:", snip(d.text[k: k + 2000], 2000))
            j = d.text.find("<main")
            print("    main:", snip(re.sub(r"<[^>]+>", " ", d.text[j: j + 6000]), 1500))


def probe_usajobs() -> None:
    section("USAJOBS")
    key, email = os.environ.get("USAJOBS_API_KEY", ""), os.environ.get("USAJOBS_EMAIL", "")
    print(f"    key set: {bool(key)}  email set: {bool(email)}")
    if not key or not email:
        return
    url = "https://data.usajobs.gov/api/search?LocationName=Manassas,%20Virginia&Radius=50&ResultsPerPage=1"
    try:
        r = requests.get(url, headers={"Host": "data.usajobs.gov", "User-Agent": email, "Authorization-Key": key}, timeout=60)
    except requests.RequestException as exc:
        print("    !", exc)
        return
    print(f"    {r.status_code} len={len(r.text)}")
    print("    " + snip(r.text, 6000))


if __name__ == "__main__":
    which = sys.argv[1:] or ["usajobs", "virginia", "neogov"]
    for name in which:
        {"usajobs": probe_usajobs, "virginia": probe_virginia, "neogov": probe_neogov}[name]()
