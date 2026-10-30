"""Per-job AI briefs for Daniel's tab (strategy, keywords, eligibility checks)."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic

from ai import create, model_name, text_of
from common import job_key

ET = ZoneInfo("America/New_York")
EST_COST = 0.05  # conservative per-brief estimate for the budget guard

BRIEF_SCHEMA = {
    "type": "object",
    "properties": {
        "one_liner": {"type": "string"},
        "fit_rating": {"type": "string", "enum": ["Strong", "Good", "Stretch", "Long shot"]},
        "fit_summary": {"type": "string"},
        "eligibility": {"type": "array", "items": {"type": "string"}},
        "keywords": {"type": "array", "items": {"type": "string"}},
        "strategy": {"type": "array", "items": {"type": "string"}},
        "resume_bullets": {"type": "array", "items": {"type": "string"}},
        "interview_questions": {"type": "array", "items": {"type": "string"}},
        "watch_outs": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "one_liner", "fit_rating", "fit_summary", "eligibility", "keywords", "strategy",
        "resume_bullets", "interview_questions", "watch_outs",
    ],
    "additionalProperties": False,
}

SYSTEM = (
    "You are an experienced public-sector career coach in the Washington DC region. You know federal "
    "hiring (USAJOBS, specialized experience, hiring paths, self-assessment questionnaires, structured "
    "interviews), Virginia state hiring, and Northern Virginia local government hiring. You give specific, "
    "honest advice grounded in the posting text. You never invent facts about the candidate or the posting. "
    "Current rule to respect: since September 27, 2025, OPM limits resumes submitted through USAJOBS to two "
    "pages, so federal advice must fit a concise two-page resume (dates, hours per week, and specialized "
    "experience stated briefly)."
)

INSTRUCTIONS = """Write a short application brief for the candidate below about the job posting below.

Guidelines:
- one_liner: what this job actually is, in plain English (max 25 words).
- fit_rating and fit_summary (2-3 sentences): how well the candidate's known background fits, and why.
- eligibility: 2-5 must-check items taken from the posting (who may apply, specialized experience at the next-lower grade, education, clearance, residency, licenses, time-in-grade). Say plainly if the posting is limited to current federal employees or other special groups.
- keywords: 10-15 exact words or phrases from the posting that should appear in the candidate's resume (federal screeners and HR systems match on them).
- strategy: 4-6 concrete steps for this application (how to frame the candidate's consulting and emergency-management experience, what to emphasize, questionnaire tips, deadlines, documents).
- resume_bullets: 2-3 example resume bullets the candidate can adapt, with [brackets] for facts the candidate must fill in. Do not invent results.
- interview_questions: 3-4 likely questions.
- watch_outs: 1-4 risks (closing soon, status-only, travel, shift work, degree requirement, low pay, etc.). Empty list if none.
Keep every item to one or two sentences. Refer to the candidate by name or as "you"; do not use gendered pronouns for the candidate."""


def brief_path(out_dir: Path, job_id: str) -> Path:
    return out_dir / f"{job_key(job_id)}.json"


def _prompt(profile: str, job: dict, detail: str) -> str:
    facts = {
        "title": job.get("title"),
        "organization": job.get("org"),
        "department": job.get("department"),
        "level": job.get("level"),
        "location": job.get("location"),
        "grade": job.get("grade"),
        "salary": [job.get("salary_min"), job.get("salary_max"), job.get("salary_period")],
        "opens": job.get("posted"),
        "closes": job.get("closes") or "open until filled / not stated",
        "who_may_apply": job.get("who_may_apply"),
        "telework": job.get("telework"),
        "remote": job.get("remote"),
        "url": job.get("url"),
    }
    return (
        f"{INSTRUCTIONS}\n\n<candidate>\n{profile}\n</candidate>\n\n"
        f"<posting_facts>\n{json.dumps(facts, indent=1)}\n</posting_facts>\n\n"
        f"<posting_text>\n{detail[:20000] or job.get('summary') or '(no description available; rely on the title and facts)'}\n</posting_text>"
    )


def generate_briefs(client, budget, profile: str, candidates: list[tuple[dict, str]], out_dir: Path, log, workers: int = 4) -> int:
    """candidates: (job, detail_text) pairs, already ordered by priority."""
    out_dir.mkdir(parents=True, exist_ok=True)
    todo = []
    for job, detail in candidates:
        if not budget.allows(EST_COST * (len(todo) + 1)):
            log(f"  briefs: stopping at {len(todo)}, monthly AI budget nearly used (${budget.spent:.2f} of ${budget.limit:.2f})")
            break
        todo.append((job, detail))
    if not todo:
        return 0

    def work(job: dict, detail: str):
        message = create(
            client,
            max_tokens=8000,
            system=SYSTEM,
            messages=[{"role": "user", "content": _prompt(profile, job, detail)}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": BRIEF_SCHEMA}},
        )
        return job, message

    made = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(work, job, detail) for job, detail in todo]
        for future in as_completed(futures):
            try:
                job, message = future.result()
            except anthropic.APIError as exc:
                log(f"  briefs: API error {type(exc).__name__}: {str(exc)[:200]}")
                continue
            budget.record("briefs:daniel", message.usage, message.model)
            if message.stop_reason == "refusal":
                log(f"  briefs: declined for {job['id']}")
                continue
            try:
                data = json.loads(text_of(message))
            except json.JSONDecodeError:
                log(f"  briefs: unreadable output for {job['id']} (stop={message.stop_reason})")
                continue
            data.update({
                "job_id": job["id"],
                "model": message.model or model_name(),
                "generated_at": datetime.now(ET).isoformat(timespec="minutes"),
            })
            brief_path(out_dir, job["id"]).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
            made += 1
    log(f"  briefs: wrote {made} new briefs")
    return made
