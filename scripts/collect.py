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
from daniel_profile import LEVELS, public_profile  # noqa: E402
from scoring import blended_score, fit_level, keywords_in, resume_fit, score_job, tags_for  # noqa: E402
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


def import_postings(entry: dict, postings: list[dict], today: date, log) -> None:
    """Add hand-checked postings from config/daniel_postings.json to the AI-found list, once each.

    They are re-checked and retired like the launch search's postings. An id is remembered after its first import,
    so a posting removed as closed does not come back on the next run."""
    imported = set(entry.get("imported") or [])
    present = {j.get("id") for j in entry.get("jobs", [])}
    for posting in postings:
        if not isinstance(posting, dict) or not posting.get("url") or not posting.get("title"):
            continue
        posting_id = posting.get("id") or f"ai:daniel:{job_key(posting['url'])}"
        if posting_id in imported or posting_id in present:
            imported.add(posting_id)
            continue
        closes = parse_date(posting.get("closes"))
        if closes and closes < today:
            imported.add(posting_id)
            continue
        job = {"source": "ai:daniel", "apply_url": posting["url"], "posted": None, "closes": None, "salary_text": "",
               "match": {"score": posting.get("score", 50), "tags": [posting.get("level", "")]}, **posting}
        job.update(id=posting_id, found_on=posting.get("found_on") or today.isoformat(), unverified_runs=0, dead_runs=0)
        job.pop("score", None)
        entry.setdefault("jobs", []).append(job)
        imported.add(posting_id)
        log(f"[import] added {job['title'][:70]!r} ({(job.get('org') or '')[:40]})")
    entry["imported"] = sorted(imported)


def revise(record: dict, changes: dict) -> None:
    """Apply one revision: a whole field, or numbered items of a list field ({"2": "new text", "4": null})."""
    for field, value in changes.items():
        current = record.get(field)
        numbered = isinstance(value, dict) and bool(value) and all(k == "+" or str(k).isdigit() for k in value)
        if isinstance(value, dict) and (isinstance(current, list) or (current is None and numbered)):
            items = list(current or [])
            for index in sorted((int(i) for i in value if str(i).isdigit()), reverse=True):
                if 0 <= index < len(items):
                    if value[str(index)] is None:
                        del items[index]
                    else:
                        items[index] = value[str(index)]
            for extra in value.get("+", []) if isinstance(value.get("+"), list) else []:
                items.append(extra)
            record[field] = items
        elif isinstance(value, dict) and isinstance(current, dict):
            revise(current, value)
        else:
            record[field] = value


def apply_brief_revisions(briefs_dir: Path, discovered: list[dict], revisions: dict, log) -> None:
    """Bring launch briefs in line with Daniel's resume (config/brief_revisions.json), once per revision version.

    The launch briefs were written before the resume was on file, so some guessed at his degree or duties; the
    revisions replace those lines. A brief already at this version is left alone, so list edits never apply twice."""
    version = revisions.get("version")
    if not version:
        return
    done = 0
    for key, changes in (revisions.get("briefs") or {}).items():
        path = briefs_dir / f"{key}.json"
        if not path.exists():
            continue
        brief = load_json(path, {})
        if brief.get("resume_revision") == version:
            continue
        revise(brief, changes)
        brief["resume_revision"] = version
        path.write_text(json.dumps(brief, ensure_ascii=False, indent=1) + "\n")
        done += 1
    by_id = {j.get("id"): j for j in discovered}
    for job_id, changes in (revisions.get("discovered") or {}).items():
        job = by_id.get(job_id)
        if not job or job.get("resume_revision") == version:
            continue
        revise(job, changes)
        job["resume_revision"] = version
        done += 1
    if done:
        log(f"[revise] updated {done} briefs to match Daniel's resume ({version})")


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
        rate_daniel_job(job, details.get(job["id"]))
    return list(jobs.values()), statuses, details


# USAJOBS text comes in "Label:" blocks. The labels ("Travel:", "Security clearance:", "How you will be evaluated:")
# and the yes/no fields are on every federal posting, so they are not words the posting chose.
_FIELD_BLOCKS = re.compile(r"(?m)^(Telework eligible|Remote|Promotion potential|Travel|Hiring paths):\n.*$")
_LABEL_LINES = re.compile(r"(?m)^[A-Z][A-Za-z ]{2,40}:$")


def posting_words(detail: str) -> str:
    return _LABEL_LINES.sub("", _FIELD_BLOCKS.sub("", detail))


def rate_daniel_job(job: dict, detail: str | None) -> None:
    """Score a daily-source job against Daniel's resume. A job kept from an earlier run (its source failed this
    time) keeps the fit worked out from its full posting text; one without a stored fit is scored from its title,
    summary and the keywords found last time."""
    known = " ".join(job.get("keywords_auto") or [])
    text = " ".join([job.get("summary", ""), posting_words(detail) if detail is not None else known])
    if detail is None and isinstance(job.get("resume"), dict) and isinstance(job["resume"].get("score"), int):
        fit = job["resume"]
        fit["level"] = fit_level(fit["score"])
    else:
        fit = resume_fit(job, text)
    job["resume"] = fit
    job["match"] = {
        "score": blended_score(score_job(job), fit),
        "tags": tags_for(f"{job.get('title', '')} {job.get('summary', '')}", job.get("series") or []),
    }
    if detail is not None:
        job["keywords_auto"] = keywords_in(" ".join([job.get("title", ""), text]))


def mark_not_eligible(job: dict) -> None:
    """The brief read the whole posting and found a requirement he can't meet, so the resume fit says so too."""
    fit = job.get("resume")
    if not isinstance(fit, dict):
        return
    fit["score"] = min(fit.get("score", 0), LEVELS[-2][0] - 1)
    fit["level"] = fit_level(fit["score"])
    fit.setdefault("flags", [])
    if "brief_not_eligible" not in fit["flags"]:
        fit["flags"].insert(0, "brief_not_eligible")
    job.setdefault("match", {})["score"] = blended_score(score_job(job), fit)


# An AI-found posting's summary mixes what the job is with how Daniel fits it ("His work helping counties ..."). The
# sentences about him quote his resume, so they are left out before the posting is matched against that resume.
_ABOUT_HIM = re.compile(r"[^.!?]*\b(?:daniel|daniel's|his|he|him)\b[^.!?]*[.!?]?", re.I)


def posting_summary(job: dict) -> str:
    text = re.sub(r"\bU\.S\.", "US", str(job.get("summary") or ""))
    return _ABOUT_HIM.sub(" ", text)


def rate_ai_job(job: dict) -> None:
    """AI-found postings keep the launch search's own score as the "what Daniel wants" half of the match."""
    brief = job.get("brief") if isinstance(job.get("brief"), dict) else {}
    keywords = " ".join(str(k) for k in brief.get("keywords") or [])
    text = " ".join([posting_summary(job), keywords, str(brief.get("evidence") or "")])
    fit = resume_fit(job, text)
    match = job.setdefault("match", {})
    match.setdefault("ai", match.get("score") or 0)
    match["score"] = blended_score(match["ai"], fit)
    job["resume"] = fit


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


def first_days(previous, jobs: list[dict], key: str) -> dict[str, str]:
    """The first day each source was read, kept from run to run. With it the site can tell a posting that
    appeared later (so the day it was first seen is about when it was posted) from one that was already listed
    when the source was first read."""
    iso = re.compile(r"\d{4}-\d{2}-\d{2}")
    days = {k: v for k, v in (previous if isinstance(previous, dict) else {}).items()
            if isinstance(k, str) and isinstance(v, str) and iso.fullmatch(v)}
    for job in jobs:
        source, seen = job.get("source"), job.get(key)
        if isinstance(source, str) and isinstance(seen, str) and iso.fullmatch(seen) and seen < days.get(source, "9999"):
            days[source] = seen
    return dict(sorted(days.items()))


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
    import_postings(discovered_doc["daniel"], load_json(CONFIG / "daniel_postings.json", []), today, log)

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
    apply_brief_revisions(briefs_dir, discovered_doc["daniel"]["jobs"], load_json(CONFIG / "brief_revisions.json", {}), log)
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
        if job["brief"] and load_json(brief_path(briefs_dir, job["id"]), {}).get("fit_rating") == "Not eligible":
            mark_not_eligible(job)
    log(f"[cleanup] removed {removed} briefs for closed jobs")

    # ---- Write the site data
    discovered_daniel = discovered_doc["daniel"]["jobs"]
    discovered_jp = discovered_doc["jp"]["jobs"]
    home = (settings["home"]["lat"], settings["home"]["lon"])
    for job in discovered_daniel:
        # The same topic tags and resume fit as the daily jobs, so the site's filters include AI-found postings.
        job["topics"] = tags_for(f"{job.get('title') or ''} {job.get('summary') or ''}", [])
        rate_ai_job(job)
        # Miles from home when the location names one known place, so the distance filter covers them too.
        # Unknown or several places ("Washington, DC or Member district offices") stay None and show at every
        # distance.
        location = job.get("location") or ""
        several = re.search(r"\bor\b|district offices?|various|multiple", location, re.I)
        where = None if several else lookup(location)
        job["distance_mi"] = round(haversine_miles(home, where), 1) if where else None
    jobs.sort(key=lambda j: (-j["match"]["score"], j.get("closes") or "9999"))
    now = datetime.now(ET).isoformat(timespec="minutes")
    doc = {
        "generated_at": now,
        "today": today.isoformat(),
        "ai": {"briefs": sum(1 for j in jobs if j.get("brief"))},
        "daniel": {
            "home": settings["home"],
            "radius_miles": settings.get("radius_miles", 50),
            "profile": public_profile(),
            "sources": statuses,
            "jobs": jobs,
            "since": first_days(previous_doc.get("daniel", {}).get("since"), jobs, "first_seen"),
            "discovered": discovered_daniel,
            "discovery_last_run": discovered_doc["daniel"].get("last_run"),
        },
        "jp": {
            "discovered": discovered_jp,
            "board_jobs": board_jobs,
            "since": first_days(previous_doc.get("jp", {}).get("since"), board_jobs, "found_on"),
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
