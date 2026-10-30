"""AI job discovery: Claude searches the web for openings that match a profile.

Results are verified from this runner (the posting URL must load and must not
say it is closed) and re-checked on every run, so dead links drop off.
"""

from __future__ import annotations

import json
import re
from datetime import date

from ai import create, text_of
from common import job_key, parse_date, shorten

SUBMIT_TOOL = {
    "name": "submit_jobs",
    "description": "Submit the verified job openings you found. Call this exactly once, at the end.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "jobs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "employer": {"type": "string"},
                        "location": {"type": "string"},
                        "url": {"type": "string", "description": "Direct link to this specific posting"},
                        "posted": {"type": "string", "description": "YYYY-MM-DD or empty"},
                        "deadline": {"type": "string", "description": "YYYY-MM-DD or empty if not stated"},
                        "segment": {"type": "string", "description": "Short group label, e.g. 'International organization'"},
                        "work_authorization": {"type": "string", "description": "What the posting says about visas, citizenship or nationality; 'Not stated' if silent"},
                        "salary": {"type": "string", "description": "Pay as stated, or empty"},
                        "fit_score": {"type": "integer", "description": "0-100 realistic chance this person gets an interview"},
                        "fit_summary": {"type": "string", "description": "2-3 sentences: what the job is and why it fits or stretches this person"},
                        "keywords": {"type": "array", "items": {"type": "string"}},
                        "strategy": {"type": "array", "items": {"type": "string"}},
                        "watch_outs": {"type": "array", "items": {"type": "string"}},
                        "evidence": {"type": "string", "description": "Short phrase from the posting page showing it is open"},
                    },
                    "required": [
                        "title", "employer", "location", "url", "posted", "deadline", "segment",
                        "work_authorization", "salary", "fit_score", "fit_summary", "keywords",
                        "strategy", "watch_outs", "evidence",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["jobs"],
        "additionalProperties": False,
    },
}

CLOSED_PATTERNS = re.compile(
    r"no longer (accepting|available|open)|position has been filled|job (posting )?(has )?(expired|closed)|"
    r"this (job|position|posting|vacancy) (is|has been) (closed|filled|removed)|"
    r"applications? (are|is) (now )?closed|posting (has )?closed|job not found|page not found|"
    r"this job is no longer|we couldn't find (that|this) job",
    re.I,
)


def run_discovery(client, budget, name: str, profile: dict, focus: str, known: list[dict], today: date, log) -> list[dict]:
    """One focused search session; returns normalized jobs (unverified)."""
    cfg = profile["discovery"]
    known_urls = sorted({j["url"] for j in known})[:200]

    system = (
        "You are a meticulous job researcher. You find real, currently open job postings on the web "
        "and judge fit honestly. You never invent postings, URLs, dates, or salary figures."
    )
    rules = [
        f"Today's date is {today.isoformat()}.",
        "Use web_search to find specific job postings, then use web_fetch to open each promising posting and confirm it is still open.",
        "Only submit postings you confirmed are open (posting page loaded, no 'closed/filled/expired' notice, deadline not passed).",
        "Prefer the employer's own career site or ATS link (Workday, Greenhouse, Lever, iCIMS, Taleo, SuccessFactors, Oracle, Cornerstone, governmentjobs.com) over aggregators. Never submit a generic careers home page or a search results page.",
        "Skip any URL in the already-known list below; the goal is new openings.",
        f"Submit at most {int(cfg.get('max_new_jobs', 10))} jobs, best fit first. Fewer is fine; quality over quantity.",
        "For each job give 8-12 resume keywords copied from the posting's own language, 3-5 concrete application strategy tips tailored to this person, and honest watch-outs (eligibility, visa, required degree or license, seniority gap).",
        "Finish by calling the submit_jobs tool exactly once. Do not write the job list as plain text.",
    ]
    if profile.get("cfa_rule"):
        rules.append(profile["cfa_rule"])
    prompt = "\n\n".join([
        f"# Candidate\n{profile['profile']}",
        f"# Goal\n{cfg['goal']}",
        f"# Focus for this search\n{focus}",
        "# Rules\n" + "\n".join(f"- {r}" for r in rules),
        "# Already known postings (skip these)\n" + ("\n".join(known_urls) if known_urls else "(none yet)"),
    ])

    estimate = 2.0
    if not budget.allows(estimate):
        log(f"  discovery {name}: skipped, monthly AI budget nearly used (${budget.spent:.2f} of ${budget.limit:.2f})")
        return []

    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": int(cfg.get("max_searches", 8))}]
    if int(cfg.get("max_fetches", 10)) > 0:
        tools.append({
            "type": "web_fetch_20260209", "name": "web_fetch",
            "max_uses": int(cfg.get("max_fetches", 10)), "max_content_tokens": 6000,
        })
    tools.append(SUBMIT_TOOL)
    messages = [{"role": "user", "content": prompt}]
    submitted = None
    response = None
    for _ in range(5):
        response = create(
            client,
            max_tokens=32000,
            system=system,
            tools=tools,
            messages=messages,
            output_config={"effort": "medium"},
            cache_control={"type": "ephemeral"},
        )
        cost = budget.record(f"discovery:{name}", response.usage, response.model)
        log(f"  discovery {name}: stop={response.stop_reason} cost=${cost:.3f}")
        for block in response.content:
            if getattr(block, "type", "") == "tool_use" and block.name == "submit_jobs":
                submitted = block.input
        if submitted is not None or response.stop_reason != "pause_turn":
            break
        messages = [messages[0], {"role": "assistant", "content": response.content}]

    if submitted is None and response is not None:
        submitted = _json_fallback(text_of(response))
    if response is not None and response.stop_reason == "refusal":
        log(f"  discovery {name}: model declined the request")
    jobs = (submitted or {}).get("jobs") or []
    log(f"  discovery {name}: model returned {len(jobs)} jobs for: {focus[:70]}")
    return [_normalize(name, j, today) for j in jobs if j.get("url", "").startswith("http")]


def _json_fallback(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _normalize(name: str, j: dict, today: date) -> dict:
    deadline = parse_date(j.get("deadline"))
    return {
        "id": f"ai:{name}:{job_key(j['url'].split('#')[0])}",
        "source": f"ai:{name}",
        "level": j.get("segment") or "AI search",
        "title": shorten(j.get("title", ""), 160),
        "org": shorten(j.get("employer", ""), 120),
        "location": shorten(j.get("location", ""), 120),
        "url": j["url"].strip(),
        "apply_url": j["url"].strip(),
        "posted": (parse_date(j.get("posted")) or today).isoformat(),
        "closes": deadline.isoformat() if deadline else None,
        "salary_text": shorten(j.get("salary", ""), 100),
        "work_authorization": shorten(j.get("work_authorization", ""), 240),
        "summary": shorten(j.get("fit_summary", ""), 600),
        "match": {"score": max(0, min(100, int(j.get("fit_score") or 0))), "tags": [j.get("segment") or "AI search"]},
        "brief": {
            "fit_summary": j.get("fit_summary", ""),
            "keywords": [shorten(k, 60) for k in (j.get("keywords") or [])][:15],
            "strategy": [shorten(s, 400) for s in (j.get("strategy") or [])][:6],
            "watch_outs": [shorten(s, 300) for s in (j.get("watch_outs") or [])][:5],
            "evidence": shorten(j.get("evidence", ""), 200),
        },
        "found_on": today.isoformat(),
    }


def verify(session, job: dict, today: date) -> tuple[str, str]:
    """Return (status, note): status is 'ok', 'unverified' (blocked/unknown) or 'dead'."""
    closes = parse_date(job.get("closes"))
    if closes and closes < today:
        return "dead", "deadline passed"
    try:
        resp = session.get(job["url"], timeout=40, allow_redirects=True)
    except Exception as exc:  # noqa: BLE001 - network problems should not delete a job
        return "unverified", f"fetch failed: {type(exc).__name__}"
    if resp.status_code in (404, 410):
        return "dead", f"HTTP {resp.status_code}"
    if resp.status_code >= 400:
        return "unverified", f"HTTP {resp.status_code}"
    body = resp.text[:400000]
    if CLOSED_PATTERNS.search(body):
        return "dead", "page says closed"
    # Redirected to a generic careers page: the posting is gone.
    if resp.history and re.search(r"/(careers|jobs)/?(\?.*)?$", resp.url) and not re.search(r"/(careers|jobs)/?(\?.*)?$", job["url"]):
        return "dead", "redirected to careers home"
    return "ok", "link checked"


def refresh(session, name: str, existing: list[dict], fresh: list[dict], today: date, log) -> list[dict]:
    """Merge new discoveries with existing ones, re-verify everything, drop dead or stale postings."""
    by_id = {j["id"]: j for j in existing}
    for job in fresh:
        if job["id"] not in by_id:
            by_id[job["id"]] = job
    kept = []
    for job in by_id.values():
        status, note = verify(session, job, today)
        found = parse_date(job.get("found_on")) or today
        age = (today - found).days
        if status == "dead":
            log(f"  {name}: removed {job['title'][:60]!r} ({note})")
            continue
        if status == "unverified":
            job["unverified_runs"] = job.get("unverified_runs", 0) + 1
            if job["unverified_runs"] >= 6 or age > 21:
                log(f"  {name}: removed {job['title'][:60]!r} (could not verify: {note})")
                continue
        else:
            job["unverified_runs"] = 0
            job["verified_on"] = today.isoformat()
        if not job.get("closes") and age > 45:
            log(f"  {name}: removed {job['title'][:60]!r} (older than 45 days, no deadline)")
            continue
        job["check"] = note
        kept.append(job)
    return kept


