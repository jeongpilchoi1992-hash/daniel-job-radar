"""Heuristic match score and topic tags tuned to Daniel's profile.

The score only orders the list and decides which jobs get an AI brief first;
it never hides a job.
"""

from __future__ import annotations

import re

# Election registrars, not museum or university registrars.
REGISTRAR = r"(general|voter|election)s? registrar|registrar of voters"
# Disaster recovery, not "peer recovery", "cost recovery" or "data recovery".
RECOVERY = r"(disaster|emergency|incident|community|long-term) recovery|recovery (planner|planning|programs?|operations|support function)"

# (tag, title/description patterns, federal series codes). Patterns are matched against the title and summary,
# so anchor short words: "election" is inside "selection" and "media" inside "immediately".
TOPICS: list[tuple[str, list[str], list[str]]] = [
    (
        "Policy & Legislative",
        [r"\bpolic(y|ies)\b", r"legislat", r"government(al)? (affairs|relations)", r"intergovernmental",
         r"congression", r"\baide\b", r"chief of staff", r"special assistant", r"\badvoca", r"board of supervisors",
         r"\bcouncil\b", r"regulat(ory|ions) (analyst|specialist)", r"political", r"public policy"],
        ["0101", "0130", "0131", "0110", "0180"],
    ),
    (
        "Emergency Management",
        [r"emergenc", r"disaster", r"\bfema\b", RECOVERY, r"hazard mitigation", r"preparedness", r"resilien",
         r"continuity of (operations|government)", r"all-hazards?", r"response (coordinator|specialist)"],
        ["0089", "0080"],
    ),
    (
        "Program & Management Analysis",
        [r"program (analyst|specialist|manager|coordinator|officer)", r"management analyst", r"management and program",
         r"project (manager|coordinator|specialist)", r"operations (analyst|specialist|coordinator)",
         r"performance", r"business analyst", r"research analyst", r"\banalyst\b"],
        ["0301", "0343", "0340", "1101", "0346"],
    ),
    (
        "Communications & Outreach",
        [r"communicat", r"public (affairs|information|relations)", r"outreach", r"community (engagement|relations|liaison)",
         r"constituent", r"\bpress\b", r"\bmedia\b|multimedia", r"external affairs", r"spokes", r"engagement", r"\bliaison\b",
         r"ombuds", r"customer (service|experience)"],
        ["1035", "1001", "1082", "1083"],
    ),
    (
        "Elections & Civic",
        [r"\belection", r"\bvoter", REGISTRAR, r"civic", r"census", r"redistrict", r"clerk to the board"],
        [],
    ),
    (
        "Grants, Budget & Contracts",
        [r"\bgrants?\b", r"budget", r"contract", r"procurement", r"acquisition", r"financ", r"fiscal"],
        ["0560", "1102", "0501", "1109"],
    ),
    (
        "Security & Intelligence",
        [r"intelligence", r"security (specialist|analyst|administrat)", r"counterterror", r"investigat"],
        ["0132", "0080", "1801", "1811"],
    ),
    (
        "Admin & Operations",
        [r"administrat", r"executive assistant", r"office manager", r"coordinator", r"support services",
         r"human resources", r"\bhr\b", r"training", r"specialist"],
        ["0303", "0342", "0201", "0203", "0318", "1712"],
    ),
]

# Strong signals for Daniel's interests (politics/policy, people skills, emergency management background).
BOOST_PATTERNS = [
    (r"legislat|government(al)? (affairs|relations)|intergovernmental|congression|policy (analyst|advisor|specialist)", 30),
    (rf"emergency management|disaster|\bfema\b|preparedness|{RECOVERY}|hazard mitigation|resilien", 28),
    (rf"\belection|\bvoter|{REGISTRAR}", 26),
    (r"constituent|community (engagement|relations|liaison)|outreach|public affairs|public information|external affairs", 24),
    (r"program (analyst|specialist|manager|coordinator)|management (and program )?analyst|policy", 18),
    (r"\bgrants?\b|budget analyst|contract specialist", 10),
    (r"\baide\b|chief of staff|special assistant|liaison|coordinator", 10),
]

SERIES_BOOST = {
    "0089": 28, "0301": 18, "0343": 20, "1035": 22, "0101": 18, "0130": 18, "0131": 18,
    "0340": 14, "1101": 12, "0560": 8, "1102": 8, "0080": 6, "0132": 8, "0201": 4,
}

# Roles that usually need a license, a specific degree, or trade certification Daniel is unlikely to have.
PENALTY_PATTERNS = [
    (r"\bnurse|nursing|physician|medical (officer|doctor|technolog)|pharmac|dental|dentist|veterinar|psycholog|therapist|"
     r"clinical|radiolog|surgeon|paramedic|emt\b|phlebotom|health technician", 45),
    (r"engineer|electrician|mechanic|plumb|hvac|welder|carpent|machinist|custodian|janitor|groundskeep|"
     r"laborer|equipment operator|bus operator|driver|maintenance worker|painter|heavy mobile", 40),
    (r"police officer|correctional officer|firefighter|sheriff|deputy sheriff|detention officer|corrections", 35),
    (r"teacher|instructor|professor|librarian|lifeguard|recreation leader|camp counselor|child care", 25),
    (r"attorney|counsel\b|paralegal|judge|law clerk", 18),
    (r"accountant|auditor|actuar|economist|statistician|chemist|physicist|biologist|geolog|hydrolog|scientist", 20),
    (r"it specialist|software|developer|cyber|network|database|systems administrator|programmer", 15),
    (r"student trainee|pathways|intern\b|internship|summer", 15),
]
PENALTY_SERIES_PREFIX = ("06", "08", "13", "15", "0602", "0610", "0620", "1300")


def tags_for(text: str, series: list[str]) -> list[str]:
    found: list[str] = []
    low = text.lower()
    for tag, patterns, codes in TOPICS:
        if any(code in series for code in codes) or any(re.search(p, low) for p in patterns):
            found.append(tag)
    if "Admin & Operations" in found and len(found) > 1:
        found.remove("Admin & Operations")
    return found[:3] or ["Other"]


def score_job(job: dict) -> int:
    title = (job.get("title") or "").lower()
    body = " ".join([title, (job.get("summary") or "").lower(), " ".join(job.get("categories") or []).lower()])
    series = job.get("series") or []

    score = 30
    title_hits = 0
    for pattern, points in BOOST_PATTERNS:
        if re.search(pattern, title):
            score += points
            title_hits += 1
        elif re.search(pattern, body):
            score += points // 3
    score += max((SERIES_BOOST.get(code, 0) for code in series), default=0)

    for pattern, points in PENALTY_PATTERNS:
        if re.search(pattern, title):
            score -= points
            break
    if any(code.startswith(PENALTY_SERIES_PREFIX) for code in series) and not title_hits:
        score -= 15
    if (job.get("grade") or "").upper().startswith(("WG", "WL", "WS")):
        score -= 25

    if job.get("open_to_public") is True:
        score += 8
    elif job.get("open_to_public") is False:
        score -= 20

    distance = job.get("distance_mi")
    if job.get("remote"):
        score += 4
    elif distance is not None:
        if distance <= 15:
            score += 6
        elif distance <= 30:
            score += 3
        elif distance > 45:
            score -= 4

    salary_max = job.get("salary_max") or 0
    if job.get("salary_period") == "hour" and salary_max and salary_max < 22:
        score -= 10

    return max(0, min(100, score))


# Common resume keywords in public-sector announcements; matched against the posting text.
KEYWORD_BANK = [
    "stakeholder engagement", "legislative analysis", "policy analysis", "policy development", "briefing materials",
    "constituent services", "intergovernmental relations", "public outreach", "community engagement",
    "strategic communications", "talking points", "press releases", "social media", "public speaking",
    "program management", "project management", "program evaluation", "performance measures", "data analysis",
    "budget formulation", "budget execution", "grants management", "grant compliance", "contract oversight",
    "procurement", "acquisition", "COR", "statement of work", "cost estimates", "risk management",
    "emergency management", "disaster recovery", "hazard mitigation", "preparedness", "continuity of operations",
    "COOP", "NIMS", "ICS", "incident command", "Stafford Act", "Public Assistance", "Individual Assistance",
    "after-action report", "exercise design", "HSEEP", "situational awareness", "emergency operations center",
    "election administration", "voter registration", "records management", "FOIA", "regulations", "compliance",
    "standard operating procedures", "process improvement", "customer service", "interpersonal skills",
    "written communication", "oral communication", "coordination", "liaison", "negotiation", "consensus building",
    "research", "report writing", "presentations", "Microsoft Excel", "SharePoint", "database", "GIS",
    "supervision", "team leadership", "training", "scheduling", "meeting facilitation", "interagency",
    "federal, state, and local", "local government", "board of supervisors", "city council", "General Assembly",
    "Congress", "appropriations", "public policy", "public administration", "security clearance",
]


def keywords_in(text: str, limit: int = 10) -> list[str]:
    low = text.lower()
    hits = []
    for kw in KEYWORD_BANK:
        pattern = rf"(?<![a-z]){re.escape(kw.lower())}(?![a-z])"
        if re.search(pattern, low):
            hits.append(kw)
        if len(hits) >= limit:
            break
    return hits
