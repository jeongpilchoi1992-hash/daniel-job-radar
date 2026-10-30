"""Temporary diagnostics for the launch (removed before merge)."""

import re
import time

import requests
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"


def session():
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    return s


def senate():
    s = session()
    r = s.get("https://careers.employment.senate.gov/jobs", timeout=40)
    soup = BeautifulSoup(r.text, "html.parser")
    link = soup.find("a", href=re.compile(r"/job/"))
    node = link
    for _ in range(6):
        if node.parent is None:
            break
        node = node.parent
        if len(node.find_all("a", href=re.compile(r"/job/"))) > 1:
            break
    card = link
    for _ in range(4):
        if card.parent is not None and len(card.parent.find_all("a", href=re.compile(r"/job/"))) <= 2:
            card = card.parent
    print("SENATE first card html:", str(card)[:3000].replace("\n", " "))
    print("SENATE container tag:", node.name, node.get("class"), node.get("id"))
    for a in soup.find_all("a", href=re.compile(r"page|offset|start", re.I)):
        print("  paging link:", a.get("href")[:150], "|", a.get_text(" ", strip=True)[:30])
    for el in soup.select("[class*=paginat], [class*=pager], nav"):
        print("  pager:", str(el)[:600].replace("\n", " "))
    counts = re.findall(r"[\d,]+\s+(?:jobs?|results?|openings?|positions?)", soup.get_text(" "), re.I)[:5]
    print("  counts:", counts)
    for q in ("?page=2", "?p=2", "/page/2"):
        time.sleep(2)
        rr = s.get("https://careers.employment.senate.gov/jobs" + q, timeout=40)
        links = sorted({a["href"] for a in BeautifulSoup(rr.text, "html.parser").find_all("a", href=re.compile(r"/job/"))})
        print(f"  {q}: {rr.status_code} {len(links)} links first={links[:2]}")
    detail = s.get(link["href"] if link["href"].startswith("http") else "https://careers.employment.senate.gov" + link["href"], timeout=40)
    dsoup = BeautifulSoup(detail.text, "html.parser")
    text = re.sub(r"\s+", " ", dsoup.get_text(" "))
    i = text.find("Posted")
    print("SENATE detail:", detail.status_code, text[max(0, i - 600):i + 1500] if i >= 0 else text[:2000])


def dc_council():
    s = session()
    r = s.get("https://dccouncil.gov/jobs-solicitations/feed/", timeout=40)
    print("DC feed:", r.status_code, r.headers.get("content-type"), len(r.text))
    print(r.text[:2500].replace("\n", " "))


def house():
    s = session()
    for url in ("https://www.house.gov/employment/positions-with-members-and-committees",
                "https://www.house.gov/employment/positions-with-other-house-organizations"):
        r = s.get(url, timeout=40)
        soup = BeautifulSoup(r.text, "html.parser")
        main = soup.find("main") or soup
        print("HOUSE", url, r.status_code, len(r.text))
        print("  text:", re.sub(r"\s+", " ", main.get_text(" "))[:2500])
        for a in main.find_all("a", href=True)[:60]:
            print("   link:", a["href"][:160], "|", a.get_text(" ", strip=True)[:60])


if __name__ == "__main__":
    senate()
    dc_council()
    house()
