"""Temporary diagnostics for the launch (removed before merge)."""

import re
import time

import requests
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"


def rows(html):
    soup = BeautifulSoup(html, "html.parser")
    trs = soup.select("table tbody tr")
    locs = [tr.select_one("td.job-search-results-location") for tr in trs]
    return len(trs), [l.get_text(" ", strip=True)[:25] for l in locs[:4] if l]


def virginia():
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    r = s.get("https://www.jobs.virginia.gov/jobs/search?page=1", timeout=60)
    soup = BeautifulSoup(r.text, "html.parser")
    print("VA page1", r.status_code, len(r.text), rows(r.text))
    for m in re.finditer(r"([\d,]+)\s+(?:jobs?|results?|positions?|openings?)\b", soup.get_text(" ")):
        print("  count text:", m.group(0))
        break
    for form in soup.find_all("form"):
        print("FORM", form.get("action"), form.get("method"), form.get("data-controller"), form.get("data-turbo-frame"))
        for el in form.find_all(["input", "select", "textarea"]):
            if el.name == "select":
                opts = [(o.get("value", "")[:40], o.get_text(" ", strip=True)[:30]) for o in el.find_all("option")]
                print("   select", el.get("name"), len(opts), opts[:25])
            else:
                print("   input", el.get("name"), el.get("type"), (el.get("value") or "")[:120])
    for el in soup.select("[class*=paginat], nav[aria-label*=agination], turbo-frame"):
        print("PAGINATION/FRAME", str(el)[:1500])
        break
    for a in soup.find_all("a", href=re.compile(r"page=")):
        print("  page link:", a.get("href")[:200], a.get_text(" ", strip=True)[:20])
    for el in soup.find_all(attrs={"data-controller": True}):
        print("  controller:", el.name, el.get("data-controller"), {k: v[:100] for k, v in el.attrs.items() if k.startswith("data-") and k != "data-controller"})
    for script in soup.find_all("script", src=True):
        if "controller" in script["src"] or "jobs" in script["src"]:
            print("  script:", script["src"])
    tests = [
        "page=6", "page=7", "page=8",
        "cities[]=Fairfax", "cities%5B%5D=Fairfax&page=1", "search_cities=Fairfax", "query=Fairfax", "query=Manassas",
        "sort=closing_at", "per_page=100", "limit=100",
    ]
    for q in tests:
        time.sleep(1)
        rr = s.get("https://www.jobs.virginia.gov/jobs/search?" + q, timeout=60)
        print(f"  ?{q}: {rr.status_code} {rows(rr.text)}")
    # Controller source (how the table and filters talk to the server)
    for src in re.findall(r'"(/assets/sites/controllers/jobs/[^"]+\.js)"', r.text)[:4]:
        js = s.get("https://www.jobs.virginia.gov" + src, timeout=60).text
        print("JS", src, len(js), js[:1200].replace("\n", " "))


def neogov():
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "X-Requested-With": "XMLHttpRequest"})
    slugs = ["arlington", "arlingtoncounty", "arlingtonva", "arlingtoncountyva", "fairfaxva", "cityoffairfax", "fallschurch",
             "fallschurchva", "manassaspark", "fauquier", "fauquiercounty", "staffordcounty", "staffordcountyva", "leesburg",
             "leesburgva", "herndon", "herndonva", "vienna", "viennava", "fredericksburg", "fredericksburgva", "warrentonva",
             "princegeorgescounty", "pgc", "mwcog", "nvrc", "vre", "nvta", "vdem"]
    for slug in slugs:
        try:
            r = s.get(f"https://www.governmentjobs.com/careers/home/index?agency={slug}&sort=PostingDate&isDescendingSort=true&page=1", timeout=(8, 30))
        except Exception as exc:  # noqa: BLE001
            print(f"  neogov {slug}: {type(exc).__name__}")
            break
        m = re.search(r'id="job-postings-number"[^>]*>\s*([\d,]+)', r.text)
        first = re.search(r'class="item-details-link"[^>]*href="(/careers/[^/]+)/', r.text)
        print(f"  neogov {slug}: {r.status_code} len={len(r.text)} postings={m.group(1) if m else None} first={first.group(1) if first else None}")
        time.sleep(0.4)


if __name__ == "__main__":
    virginia()
    neogov()
