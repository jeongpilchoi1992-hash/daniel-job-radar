"""Refresh the job data behind the site.

Steps: collect postings from every source, drop closed ones, score them, and
write data/jobs.json. Only when RUN_AI=true (a manual workflow run) does it
also call Claude: AI briefs for the best matches and AI web searches for both
tabs. Links found by AI search are re-checked on every run either way.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ai import Budget, make_client, model_name  # noqa: E402
from common import SourceSkipped, job_key, make_session, parse_date  # noqa: E402
from discover import refresh as refresh_discovered  # noqa: E402
from discover import run_discovery  # noqa: E402
from insights import brief_path, generate_briefs  # noqa: E402
from scoring import keywords_in, score_job, tags_for  # noqa: E402
from sources import fetch_neogov, fetch_usajobs, fetch_virginia, virginia_detail  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CONFIG = ROOT / "config"
ET = ZoneInfo("America/New_York")

STALE_DAYS = 10  # keep a failed source's jobs at most this long after we last saw them


def log(message: str) -> None:
    print(message, flush=True)


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def still_open(job: dict, today: date) -> bool:
    closes = parse_date(job.get("closes"))
    return closes is None or closes >= today


def collect_daniel(session, settings: dict, today: date, previous: dict[str, dict]) -> tuple[list[dict], list[dict], dict[str, str]]:
    home = (settings["home"]["lat"], settings["home"]["lon"])
    radius = int(settings.get("radius_miles", 50))
    plans = [("usajobs", "USAJOBS (federal)", lambda: fetch_usajobs(session, settings.get("usajobs", {}), home))]
    plans.append(("virginia", "Commonwealth of Virginia", lambda: fetch_virginia(session, settings.get("virginia", {}), home, radius)))
    for agency in settings.get("neogov_agencies", []):
        plans.append((f"neogov:{agency['slug']}", agency["name"], lambda a=agency: fetch_neogov(session, a, home, radius)))

    jobs: dict[str, dict] = {}
    details: dict[str, str] = {}
    statuses = []
    for source_id, label, fetch in plans:
        log(f"[{source_id}] {label}")
        status = {"id": source_id, "name": label, "status": "ok", "count": 0, "message": ""}
        fresh = None
        try:
            fresh = fetch()
        except SourceSkipped as exc:
            status.update(status="skipped", message=str(exc))
        except Exception as exc:  # noqa: BLE001 - one broken source must not stop the run
            status.update(status="error", message=f"{type(exc).__name__}: {str(exc)[:300]}")
            traceback.print_exc()

        if fresh is not None:
            for job in fresh:
                if not still_open(job, today) or not job.get("title"):
                    continue
                detail = job.pop("_detail", "") or ""
                old = previous.get(job["id"], {})
                job["first_seen"] = old.get("first_seen") or today.isoformat()
                job["last_seen"] = today.isoformat()
                jobs[job["id"]] = job
                details[job["id"]] = detail
                status["count"] += 1
        else:
            kept = 0
            for job in previous.values():
                if job.get("source") != source_id or not still_open(job, today):
                    continue
                last_seen = parse_date(job.get("last_seen")) or today
                if (today - last_seen).days > STALE_DAYS:
                    continue
                jobs[job["id"]] = job
                kept += 1
            status["count"] = kept
            if kept:
                status["message"] = (status["message"] + f" Showing {kept} jobs from the last successful run.").strip()
        log(f"  -> {status['status']} {status['count']} jobs {status['message'][:160]}")
        statuses.append(status)

    for job in jobs.values():
        text = " ".join([job.get("title", ""), job.get("summary", ""), details.get(job["id"], "")])
        job["match"] = {"score": score_job(job), "tags": tags_for(f"{job.get('title', '')} {job.get('summary', '')}", job.get("series") or [])}
        if job["id"] in details:
            job["keywords_auto"] = keywords_in(text)
    return list(jobs.values()), statuses, details


def pick_brief_candidates(jobs: list[dict], details: dict[str, str], briefs_dir: Path, settings: dict) -> list[dict]:
    min_score = int(os.environ.get("AI_MIN_SCORE") or settings.get("ai_min_score", 50))
    pool = [
        j for j in jobs
        if not brief_path(briefs_dir, j["id"]).exists()
        and j["id"] in details
        and j.get("open_to_public") is not False
        and j["match"]["score"] >= min_score
    ]
    pool.sort(key=lambda j: (-j["match"]["score"], j.get("closes") or "9999"))
    return pool


def main() -> int:
    today = datetime.now(ET).date()
    settings = load_json(CONFIG / "settings.json", {})
    profiles = load_json(CONFIG / "profiles.json", {})
    DATA.mkdir(exist_ok=True)
    briefs_dir = DATA / "briefs"
    session = make_session()

    previous_doc = load_json(DATA / "jobs.json", {})
    previous = {j["id"]: j for j in previous_doc.get("daniel", {}).get("jobs", [])}

    jobs, statuses, details = collect_daniel(session, settings, today, previous)

    # ---- AI work runs only when someone starts the workflow with "run_ai" checked.
    # Scheduled refreshes never call the Anthropic API.
    run_ai = os.environ.get("RUN_AI", "").lower() == "true"
    client = make_client() if run_ai else None
    budget = Budget(DATA / "usage.json", float(os.environ.get("AI_BUDGET_USD") or settings.get("ai_run_budget_usd", 25)))
    if run_ai and client is None:
        log("RUN_AI is set but ANTHROPIC_API_KEY is missing; skipping AI work.")
    if client is None:
        log("[ai] off for this run (scheduled refreshes use free sources only)")
    else:
        max_briefs = int(os.environ.get("AI_MAX_BRIEFS") or settings.get("ai_max_briefs_per_run", 150))
        candidates = pick_brief_candidates(jobs, details, briefs_dir, settings)[:max_briefs]
        for job in candidates:
            if job["source"] == "virginia" and not details.get(job["id"]):
                try:
                    details[job["id"]] = virginia_detail(session, job["url"])
                except Exception as exc:  # noqa: BLE001
                    log(f"  detail fetch failed for {job['url']}: {exc}")
        log(f"[briefs] {len(candidates)} jobs queued (model {model_name()}, budget left ${budget.remaining:.2f})")
        generate_briefs(client, budget, profiles["daniel"]["profile"], [(j, details.get(j["id"], "")) for j in candidates], briefs_dir, log)

    # ---- AI discovery for both tabs (one focused search per search group); links are re-checked every run
    discovered_doc = load_json(DATA / "discovered.json", {})
    for name in ("daniel", "jp"):
        entry = discovered_doc.get(name, {"jobs": [], "last_run": None})
        fresh: list[dict] = []
        cfg = profiles[name]["discovery"]
        if client is not None and cfg.get("enabled"):
            for focus in cfg.get("search_groups", []):
                log(f"[discovery:{name}] {focus[:80]}")
                try:
                    fresh += run_discovery(client, budget, name, profiles[name], focus, entry.get("jobs", []) + fresh, today, log)
                except Exception as exc:  # noqa: BLE001 - keep going with the other groups
                    log(f"  discovery {name} failed: {type(exc).__name__}: {str(exc)[:300]}")
                    traceback.print_exc()
            entry["last_run"] = today.isoformat()
        log(f"[verify:{name}] {len(entry.get('jobs', []))} known + {len(fresh)} new")
        entry["jobs"] = refresh_discovered(session, name, entry.get("jobs", []), fresh, today, log)
        discovered_doc[name] = entry
    budget.save()
    if client is not None:
        log(f"[ai] this run spent about ${budget.spent:.2f} ({budget.by_task})")

    # ---- Remove briefs for jobs that are gone
    live = {job_key(j["id"]) for j in jobs}
    removed = 0
    if briefs_dir.exists():
        for path in briefs_dir.glob("*.json"):
            if path.stem not in live:
                path.unlink()
                removed += 1
    for job in jobs:
        job["brief"] = job_key(job["id"]) if brief_path(briefs_dir, job["id"]).exists() else None
    log(f"[cleanup] removed {removed} briefs for closed jobs")

    # ---- Write the site data
    discovered_daniel = discovered_doc["daniel"]["jobs"]
    discovered_jp = discovered_doc["jp"]["jobs"]
    jobs.sort(key=lambda j: (-j["match"]["score"], j.get("closes") or "9999"))
    now = datetime.now(ET).isoformat(timespec="minutes")
    doc = {
        "generated_at": now,
        "today": today.isoformat(),
        "ai": {
            "model": model_name(),
            "briefs": sum(1 for j in jobs if j.get("brief")),
            "month_spend_usd": budget.month_total(),
        },
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
            "discovery_last_run": discovered_doc["jp"].get("last_run"),
        },
    }
    (DATA / "jobs.json").write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n")
    (DATA / "discovered.json").write_text(json.dumps(discovered_doc, ensure_ascii=False, indent=1) + "\n")
    log(f"[done] {len(jobs)} gov jobs, {len(discovered_daniel)} + {len(discovered_jp)} AI-found jobs; AI spend this month ${budget.spent:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
