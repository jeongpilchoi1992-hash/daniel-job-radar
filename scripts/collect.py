"""Refresh the job data behind the site, using free public sources only.

Steps: collect postings from every source, drop closed ones, score them, read
the employer job boards learned from the launch-day AI search, re-check every
AI-found link, and write data/jobs.json. Nothing here calls an AI service.
"""

from __future__ import annotations

import json
import re
import sys
import time
import traceback
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import PartialResult, SourceSkipped, job_key, make_session, parse_date  # noqa: E402
from boards import detect as detect_board  # noqa: E402
from boards import board_id, fetch_board, infer_focus, posting_key, relevant, to_site_job  # noqa: E402
from legislature import LISTED, fetch_dc_council, fetch_house, fetch_senate  # noqa: E402
from linkcheck import refresh as refresh_links  # noqa: E402
from places import haversine_miles, lookup  # noqa: E402
from scoring import keywords_in, score_job, tags_for  # noqa: E402
from sources import NeogovGate, fetch_neogov, fetch_usajobs, fetch_virginia  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CONFIG = ROOT / "config"
ET = ZoneInfo("America/New_York")

STALE_DAYS = 10  # keep a failed source's jobs at most this long after we last saw them
# The workflow job stops at 90 minutes; after this many, board reads and link checks are skipped (and their
# postings left as they were) so the run still saves its data.
RUN_BUDGET_MINUTES = 70
STARTED = time.monotonic()


def out_of_time() -> bool:
    return time.monotonic() - STARTED > RUN_BUDGET_MINUTES * 60
BRIEF_GRACE_DAYS = 30  # keep a launch brief this long after its job was last listed (unless its deadline passed)


def log(message: str) -> None:
    print(message, flush=True)


def load_json(path: Path, default):
    """A missing file gives the default; a malformed one stops the run before anything is overwritten."""
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path} is not valid JSON ({exc}); fix it and run again.") from exc


def brief_path(briefs_dir: Path, job_id: str) -> Path:
    return briefs_dir / f"{job_key(job_id)}.json"


def still_open(job: dict, today: date) -> bool:
    closes = parse_date(job.get("closes"))
    return closes is None or closes >= today


def collect_daniel(session, settings: dict, today: date, previous: dict[str, dict], learned_agencies: list[dict]) -> tuple[list[dict], list[dict], dict[str, str]]:
    home = (settings["home"]["lat"], settings["home"]["lon"])
    radius = int(settings.get("radius_miles", 50))
    plans = [("usajobs", "USAJOBS (federal)", lambda: fetch_usajobs(session, settings.get("usajobs", {}), home))]
    plans.append(("senate", "U.S. Senate", lambda: fetch_senate(session, home, radius)))
    plans.append(("house", "U.S. House of Representatives", lambda: fetch_house(session, home, radius)))
    plans.append(("dccouncil", "Council of the District of Columbia", lambda: fetch_dc_council(session, home, radius)))
    plans.append(("virginia", "Commonwealth of Virginia", lambda: fetch_virginia(session, settings.get("virginia", {}), home, radius)))
    configured = {a["slug"] for a in settings.get("neogov_agencies", [])}
    agencies = settings.get("neogov_agencies", []) + [a for a in learned_agencies if a["slug"] not in configured]
    # governmentjobs.com may cut us off part way, so each run starts with a different agency.
    shift = (today.toordinal() * 2 + (datetime.now(ET).hour >= 12)) % max(len(agencies), 1)
    gate = NeogovGate()
    for agency in agencies[shift:] + agencies[:shift]:
        plans.append((f"neogov:{agency['slug']}", agency["name"], lambda a=agency: fetch_neogov(gate, a, home, radius, today)))

    jobs: dict[str, dict] = {}
    details: dict[str, str] = {}
    statuses = []
    for source_id, label, fetch in plans:
        log(f"[{source_id}] {label}")
        status = {"id": source_id, "name": label, "status": "ok", "count": 0, "message": ""}
        fresh, complete = None, True
        try:
            fresh = fetch()
        except PartialResult as exc:
            fresh, complete = exc.jobs, False
            status.update(status="partial", message=str(exc)[:300])
        except SourceSkipped as exc:
            status.update(status="skipped", message=str(exc))
        except Exception as exc:  # noqa: BLE001 - one broken source must not stop the run
            status.update(status="error", message=f"{type(exc).__name__}: {str(exc)[:300]}")
            if "stopped answering" not in str(exc):
                traceback.print_exc()

        before = sum(1 for j in previous.values() if j.get("source") == source_id)
        if complete and fresh is not None and before >= 10 and len(fresh) < before / 2:
            # A source that suddenly lists far fewer jobs is more likely broken than emptied overnight.
            complete = False
            status.update(status="partial", message=f"Listed {len(fresh)} jobs after {before} last run; keeping the earlier ones.")
        for job in fresh or []:
            if not still_open(job, today) or not job.get("title"):
                continue
            detail = job.pop("_detail", "") or ""
            old = previous.get(job["id"], {})
            job["first_seen"] = old.get("first_seen") or today.isoformat()
            job["last_seen"] = today.isoformat()
            jobs[job["id"]] = job
            details[job["id"]] = detail
            status["count"] += 1
        if fresh is None or not complete:
            # Keep what this source showed recently, until the posting closes.
            kept = 0
            for job in previous.values():
                if job.get("source") != source_id or job["id"] in jobs or not still_open(job, today):
                    continue
                last_seen = parse_date(job.get("last_seen")) or today
                if (today - last_seen).days > STALE_DAYS:
                    continue
                jobs[job["id"]] = job
                kept += 1
            status["count"] += kept
            if kept:
                status["message"] = (status["message"] + f" Also showing {kept} jobs from earlier runs.").strip()
        log(f"  -> {status['status']} {status['count']} jobs {status['message'][:160]}")
        statuses.append(status)

    for job in jobs.values():
        text = " ".join([job.get("title", ""), job.get("summary", ""), details.get(job["id"], "")])
        job["match"] = {"score": score_job(job), "tags": tags_for(f"{job.get('title', '')} {job.get('summary', '')}", job.get("series") or [])}
        if job["id"] in details:
            job["keywords_auto"] = keywords_in(text)
    return list(jobs.values()), statuses, details


def learn_sources(discovered_doc: dict, settings: dict, log) -> list[dict]:
    """Remember job boards behind AI-found postings (kept even after those postings close).

    Returns this run's employer boards: the learned ones plus config/boards.json, which is read fresh every run
    (and never copied into data/discovered.json, so edits and deletions there take effect)."""
    jp = discovered_doc["jp"]
    boards = {board_id(b): b for b in jp.get("boards", [])}
    for job in jp.get("jobs", []):
        board = detect_board(job["url"])
        if board and board_id(board) not in boards:
            board["employer"] = job.get("org", "")
            board["focus"] = infer_focus(job.get("level", ""), job.get("org", ""))
            boards[board_id(board)] = board
            log(f"[learn] new board for J.P.: {board_id(board)} ({board['employer']})")
    jp["boards"] = list(boards.values())
    for extra in load_json(CONFIG / "boards.json", []):
        boards[board_id(extra)] = extra

    daniel = discovered_doc["daniel"]
    known = {a["slug"] for a in settings.get("neogov_agencies", [])} | {a["slug"] for a in daniel.get("neogov_agencies", [])}
    learned = list(daniel.get("neogov_agencies", []))
    for job in daniel.get("jobs", []):
        m = re.search(r"governmentjobs\.com/careers/([a-z0-9]+)/", job.get("url", ""), re.I)
        if m and m.group(1).lower() not in known:
            slug = m.group(1).lower()
            known.add(slug)
            where = lookup(job.get("location", ""))
            home = (settings["home"]["lat"], settings["home"]["lon"])
            if not where or haversine_miles(home, where) > settings.get("radius_miles", 50) + 0.5:
                log(f"[learn] skipped job board {slug}: {job.get('location')!r} is not a known place within range")
                continue
            learned.append({"slug": slug, "name": job.get("org") or slug, "level": "Local", "default_location": job.get("location", "")})
            log(f"[learn] new county/city job board for Daniel: {slug} ({job.get('org')})")
    daniel["neogov_agencies"] = learned
    return list(boards.values())


def collect_boards(session, boards: list[dict], jp_entry: dict, previous: list[dict], today: date,
                   log) -> tuple[list[dict], dict[str, set[str]], dict[str, set[str]]]:
    """Read every known employer board (free public APIs) and keep finance roles that fit J.P.

    Also returns the postings each board lists today: for boards read in full (so a posting missing there has
    closed), and for every board read this run, including big boards that were only searched."""
    prev_by_board: dict[str, list[dict]] = {}
    for job in previous:
        prev_by_board.setdefault(job.get("source", ""), []).append(job)
    first_seen = {j["id"]: j.get("found_on") for j in previous}
    today_iso = today.isoformat()
    discovered_keys = {posting_key(j["url"]) for j in jp_entry.get("jobs", [])}
    out: dict[str, dict] = {}
    live: dict[str, set[str]] = {}
    seen: dict[str, set[str]] = {}
    for board in boards:
        bid = board_id(board)
        if out_of_time():
            log(f"[board] {bid} skipped: out of time this run")
            for job in prev_by_board.get(f"board:{bid}", []):
                out[job["id"]] = job
            continue
        try:
            raw, complete = fetch_board(session, board, board.get("employer", ""), log)
        except Exception as exc:  # noqa: BLE001 - keep yesterday's list for a failing board
            log(f"[board] {bid} failed: {type(exc).__name__}: {str(exc)[:200]}")
            for job in prev_by_board.get(f"board:{bid}", []):
                last_seen = parse_date(job.get("last_seen") or job.get("found_on")) or today
                if (today - last_seen).days <= STALE_DAYS:
                    out[job["id"]] = job
            continue
        seen[bid] = {posting_key(item["url"]) for item in raw}
        if complete and raw:
            live[bid] = seen[bid]
        kept = 0
        for item in raw:
            if not relevant(item, board.get("focus", "asia")) or posting_key(item["url"]) in discovered_keys:
                continue
            job = to_site_job(item, today_iso, None, board.get("focus", "asia"))
            job["found_on"] = first_seen.get(job["id"]) or today_iso
            job["last_seen"] = today_iso
            out[job["id"]] = job
            kept += 1
        log(f"[board] {bid}: {len(raw)} postings, {kept} relevant")
        time.sleep(1)
    return sorted(out.values(), key=lambda j: -j["match"]["score"]), live, seen


def drop_ai_duplicates(jobs: list[dict], ai_found: list[dict], log) -> list[dict]:
    """Show a posting once: the AI-found copy (with its brief) wins over the same posting from a daily source."""
    # Hosts are compared without ports: the USAJOBS feed links www.usajobs.gov:443.
    keys = {(urlparse(j["url"]).hostname, posting_key(j["url"])) for j in ai_found}
    # The AI search sometimes linked a page inside a posting (its announcement), so a posting also matches its sub-pages.
    paths = [(urlparse(j["url"]).hostname, urlparse(j["url"]).path.rstrip("/") + "/") for j in ai_found]
    kept = []
    for job in jobs:
        host = urlparse(job["url"]).hostname
        path = urlparse(job["url"]).path.rstrip("/") + "/"
        if (host, posting_key(job["url"])) in keys or any(h == host and p.startswith(path) and path.count("/") > 2 for h, p in paths):
            continue
        kept.append(job)
    if len(kept) < len(jobs):
        log(f"[dedupe] {len(jobs) - len(kept)} postings already shown as AI-found jobs")
    return kept


def main() -> int:
    today = datetime.now(ET).date()
    settings = load_json(CONFIG / "settings.json", {})
    DATA.mkdir(exist_ok=True)
    briefs_dir = DATA / "briefs"
    session = make_session()

    previous_doc = load_json(DATA / "jobs.json", {})
    previous = {j["id"]: j for j in previous_doc.get("daniel", {}).get("jobs", [])}
    discovered_doc = load_json(DATA / "discovered.json", {})
    for name in ("daniel", "jp"):
        discovered_doc.setdefault(name, {"jobs": [], "last_run": None})

    jobs, statuses, _ = collect_daniel(session, settings, today, previous, discovered_doc["daniel"].get("neogov_agencies", []))

    # ---- Free daily sources learned from AI-found postings, then re-check every AI-found link
    boards = learn_sources(discovered_doc, settings, log)
    board_jobs, live_boards, seen_on_boards = collect_boards(session, boards, discovered_doc["jp"], previous_doc.get("jp", {}).get("board_jobs", []), today, log)
    checker = make_session(quick=True)
    for name in ("daniel", "jp"):
        entry = discovered_doc[name]
        log(f"[verify:{name}] {len(entry['jobs'])} AI-found postings")
        entry["jobs"] = refresh_links(checker, name, entry["jobs"], today, log, {**live_boards, **LISTED}, out_of_time, seen_on_boards)
    jobs = drop_ai_duplicates(jobs, discovered_doc["daniel"]["jobs"], log)

    # ---- Remove briefs for jobs that are gone. Briefs came from the one-time launch build and cannot be made
    # again, so one whose job drops out of the list is kept until its deadline passes or BRIEF_GRACE_DAYS go by.
    ledger = load_json(DATA / "briefs_seen.json", {})
    for job in jobs:
        if brief_path(briefs_dir, job["id"]).exists():
            ledger[job_key(job["id"])] = {"last_seen": today.isoformat(), "closes": job.get("closes")}
    removed = 0
    for path in sorted(briefs_dir.glob("*.json")) if briefs_dir.exists() else []:
        seen = ledger.setdefault(path.stem, {"last_seen": today.isoformat(), "closes": None})
        closes = parse_date(seen.get("closes"))
        last_seen = parse_date(seen.get("last_seen")) or today
        if (closes and closes < today) or (today - last_seen).days > BRIEF_GRACE_DAYS:
            path.unlink()
            removed += 1
    ledger = {k: v for k, v in sorted(ledger.items()) if (briefs_dir / f"{k}.json").exists()}
    (DATA / "briefs_seen.json").write_text(json.dumps(ledger, indent=0) + "\n")
    for job in jobs:
        job["brief"] = job_key(job["id"]) if brief_path(briefs_dir, job["id"]).exists() else None
    log(f"[cleanup] removed {removed} briefs for closed jobs")

    # ---- Write the site data
    discovered_daniel = discovered_doc["daniel"]["jobs"]
    discovered_jp = discovered_doc["jp"]["jobs"]
    for job in discovered_daniel:
        # The same topic tags as the daily jobs, so the site's topic filters include AI-found postings.
        job["topics"] = tags_for(f"{job.get('title', '')} {job.get('summary', '')}", [])
    jobs.sort(key=lambda j: (-j["match"]["score"], j.get("closes") or "9999"))
    now = datetime.now(ET).isoformat(timespec="minutes")
    doc = {
        "generated_at": now,
        "today": today.isoformat(),
        "ai": {"briefs": sum(1 for j in jobs if j.get("brief"))},
        "daniel": {
            "home": settings["home"],
            "radius_miles": settings.get("radius_miles", 50),
            "sources": statuses,
            "jobs": jobs,
            "discovered": discovered_daniel,
            "discovery_last_run": discovered_doc["daniel"].get("last_run"),
        },
        "jp": {
            "discovered": discovered_jp,
            "board_jobs": board_jobs,
            "boards": len(boards),
            "discovery_last_run": discovered_doc["jp"].get("last_run"),
        },
    }
    (DATA / "jobs.json").write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n")
    (DATA / "discovered.json").write_text(json.dumps(discovered_doc, ensure_ascii=False, indent=1) + "\n")
    log(f"[done] {len(jobs)} gov jobs, {len(discovered_daniel)} + {len(discovered_jp)} AI-found jobs, {len(board_jobs)} employer-board jobs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
