"""Match score, topic tags and resume fit, tuned to Daniel's 2026 resume.

The match score blends what Daniel wants (government, policy, emergency management) with what his resume
backs up (see daniel_profile.py). It orders the list and never hides a job; the resume-fit level feeds the
site's "Resume fit" filter and the per-job tips.
"""

from __future__ import annotations

import re

from daniel_profile import ANGLES, GAPS, LEVELS

# Election registrars, not museum or university registrars.
REGISTRAR = r"(general|voter|election)s? registrar|registrar of voters"
# Disaster recovery, not "peer recovery", "cost recovery" or "data recovery".
RECOVERY = r"(disaster|emergency|incident|community|long-term) recovery|recovery (planner|planning|programs?|operations|support function)"
# Emergency exercises, not "exercise judgment" or "exercise authority".
EXERCISES = (r"(conduct|design|develop|plan|run|facilitat|evaluat|coordinat|support|participat)\w*,?( in| and \w+)? exercises\b|"
             r"\b(coop|continuity|response|training|emergency|preparedness) exercises\b|"
             r"exercise (design|program|plann|coordinat|officer|specialist|evaluat|facilitat)|(tabletop|full[- ]scale|functional) exercise|\bhseep\b")

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
         r"continuity of (operations|government)", r"all-hazards?", r"response (coordinator|specialist)", EXERCISES],
        ["0089", "0080"],
    ),
    (
        "Public Health",
        [r"public health", r"health (emergency|preparedness|security|department|district)", r"epidemi", r"pandemic",
         r"vaccin", r"immuniz", r"outbreak", r"health ?care coalition", r"hospital preparedness", r"centers for disease control", r"\baspr\b",
         r"rural health", r"medicaid", r"health (care )?policy"],
        ["0685"],
    ),
    (
        "Program & Management Analysis",
        [r"program (analyst|specialist|manager|coordinator|officer)", r"management analyst", r"management and program",
         r"project (manager|coordinator|specialist)", r"operations (analyst|specialist|coordinator)",
         r"performance", r"business analyst", r"research analyst", r"\banalyst\b"],
        ["0301", "0343", "0340", "1101"],
    ),
    (
        "Logistics & Procurement",
        [r"logistic", r"supply chain", r"\bsupply (specialist|technician|management)", r"inventory", r"(?<!data )warehous",
         r"procurement", r"(?<!talent )(?<!land )acquisition", r"\bcontract(s|ing)? (specialist|officer|administrat|manag)", r"purchas", r"mass care"],
        ["0346", "2001", "2003", "2010", "1102", "1105", "1106"],
    ),
    (
        "Grants & Budget",
        [r"\bgrants?\b", r"budget", r"financ", r"fiscal"],
        ["0560", "0501", "1109"],
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
        "International Affairs",
        [r"international (affairs|relations|cooperation|programs?|development|trade)", r"foreign (affairs|policy|service|assistance)",
         r"diploma", r"human rights", r"refugee", r"humanitarian"],
        ["0130", "0131", "0136"],
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

# Strong signals for what Daniel wants (policy, politics, public service) and what his resume backs up
# (emergency management, public health response, exercises, logistics, FEMA programs).
BOOST_PATTERNS = [
    (r"legislat|government(al)? (affairs|relations)|intergovernmental|congression|policy (analyst|advisor|specialist)", 30),
    (rf"emergency management|disaster|\bfema\b|preparedness|{RECOVERY}|hazard mitigation|resilien", 28),
    (r"public health (emergency|preparedness)|health (emergency|security|preparedness)|health ?care coalition|hospital preparedness|\bphep\b|\baspr\b", 26),
    (rf"\belection|\bvoter|{REGISTRAR}", 26),
    (r"constituent|community (engagement|relations|liaison)|outreach|public affairs|public information|external affairs", 24),
    (EXERCISES, 22),
    (r"rural health|\brhtp\b|health (care )?policy", 20),
    (r"program (analyst|specialist|manager|coordinator)|management (and program )?analyst|policy", 18),
    (r"logistic|supply chain|mass care|resource (request|ordering|typing|mobilization)|continuity of operations", 16),
    (r"international (affairs|relations|cooperation|programs?)|foreign affairs", 12),
    (r"\bgrants?\b|budget analyst|contract specialist", 10),
    (r"\baide\b|chief of staff|special assistant|liaison|coordinator", 10),
]

SERIES_BOOST = {
    "0089": 28, "0685": 22, "0301": 18, "0343": 20, "1035": 22, "0101": 18, "0130": 18, "0131": 18,
    "0340": 14, "0346": 14, "0136": 10, "1101": 12, "2003": 10, "0560": 8, "1102": 8, "0080": 6, "0132": 8,
    "2001": 6, "2010": 6, "0201": 4,
}

# Roles that usually need a license, a specific degree or trade certification Daniel is unlikely to have, or that sit
# well above his experience.
PENALTY_PATTERNS = [
    (r"\bnurse|nursing|physician|medical (officer|doctor|technolog)|pharmac|dental|dentist|veterinar|psycholog|therapist|"
     r"clinical|radiolog(?!ical)|surgeon|paramedic|emt\b|phlebotom|health technician|emergency medical|medical technician|"
     r"behavioral health|\bmental health|social work", 45),
    (r"engineer|electrician|mechanic|plumb|hvac|welder|carpent|machinist|custodian|janitor|groundskeep|"
     r"laborer|\boperator\b|driver|maintenance worker|painter|heavy mobile|fleet (maintenance|technician)|"
     r"maintenance (technician|supervisor)|kennel|canine|animal care", 40),
    (r"police officer|correctional officer|firefighter|sheriff|deputy sheriff|detention officer|corrections|dispatcher|"
     r"telecommunicator|paramilitary|\bt32\b|title 32|(?<!non-)(?<!non )dual[- ]status|military technician", 35),
    (r"teacher|instructor|professor|librarian|lifeguard|recreation leader|camp counselor|child care|child (and|&) youth|"
     r"youth program|child development|special needs|c & y program|\bcys\b", 25),
    (r"attorney|counsel\b|paralegal|judge|law clerk", 18),
    (r"accountant|auditor|actuar|economist|statistician|chemist|physicist|biolog(?!ical,? (and )?radiolog)|geolog|hydrolog|scientist|archivist|"
     r"curator|conservator|film restoration|\bconstruction|inspector\b(?! general)|research technician|"
     r"laboratory technician|science technician|operations research|real property|housing finance|"
     r"\bfleet (operations|management|manager|services)", 20),
    (r"it specialist|software|developer|cyber|\bnetwork (engineer|administrat|specialist|architect|operations|security|technician)|"
     r"database|systems administrator|programmer|\barchitect|"
     r"\bit (project|program|manager)\b|information technology", 15),
    (r"student trainee|pathways|intern\b|internship|summer", 15),
    # Senior posts: the job leads an office, which his resume doesn't show yet. "Executive Assistant to the Director"
    # and "Office of the Chief of Staff" name the boss, not the job; assistant and associate directors cost less.
    (r"^(?!.*\b(assistant|aide) to\b).*?(?:(?<!the )(?<!to )(?<!assistant )(?<!associate )\bdirector\b|"
     r"\bexecutive (director|officer)\b|(?<!the )(?<!to )\bchief\b)", 15),
    (r"^(?!.*\b(assistant|aide) to\b).*?\b(assistant|associate) director\b", 8),
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


# Common resume keywords in public-sector announcements; matched against the posting text. The ones from
# Daniel's resume (logistics, exercises, public health, proposals) come first, so they make the cut.
KEYWORD_BANK = [
    "emergency management", "disaster recovery", "hazard mitigation", "preparedness", "continuity of operations",
    "COOP", "NIMS", "ICS", "incident command", "Stafford Act", "Public Assistance", "Individual Assistance",
    "after-action report", "exercise design", "tabletop exercise", "full-scale exercise", "HSEEP", "situational awareness",
    "emergency operations center", "WebEOC", "public health", "public health preparedness", "mass care", "vaccination",
    "medical countermeasures", "healthcare coalition", "pandemic", "outbreak", "rural health", "Medicaid",
    "logistics", "supply chain", "inventory", "procurement", "acquisition", "vendor management", "purchasing",
    "proposal writing", "proposals", "solicitations", "market research", "SAM.gov", "statement of work",
    "stakeholder engagement", "legislative analysis", "policy analysis", "policy development", "briefing materials",
    "constituent services", "intergovernmental relations", "public outreach", "community engagement",
    "strategic communications", "talking points", "press releases", "social media", "public speaking",
    "program management", "project management", "program evaluation", "performance measures", "data analysis",
    "budget formulation", "budget execution", "grants management", "grant compliance", "grant applications",
    "contract oversight", "COR", "cost estimates", "risk management", "election administration", "voter registration",
    "records management", "FOIA", "regulations", "compliance", "standard operating procedures", "process improvement",
    "Lean Six Sigma", "customer service", "intake", "case management", "claims", "data entry", "onboarding", "travel",
    "meeting minutes", "interpersonal skills", "written communication", "oral communication", "coordination", "liaison",
    "negotiation", "consensus building", "research", "report writing", "presentations", "Microsoft Excel", "SharePoint",
    "database", "GIS", "supervision", "team leadership", "training", "scheduling", "meeting facilitation", "interagency",
    "federal, state, and local", "local government", "board of supervisors", "city council", "General Assembly",
    "Congress", "appropriations", "public policy", "public administration", "international affairs", "security clearance",
    "volunteer management", "interviewing",
]


def keywords_in(text: str, limit: int = 12) -> list[str]:
    low = text.lower()
    hits = []
    for kw in KEYWORD_BANK:
        pattern = rf"(?<![a-z]){re.escape(kw.lower())}(?![a-z])"
        if re.search(pattern, low):
            hits.append(kw)
        if len(hits) >= limit:
            break
    return hits


# ---------------------------------------------------------------- resume fit

_ANGLES = [(a["id"], a["weight"], [re.compile(p) for p in a["patterns"]]) for a in ANGLES]
_GAPS = [(g["id"], [re.compile(p) for p in g["patterns"]]) for g in GAPS]
WEIGHTS = {a["id"]: a["weight"] for a in ANGLES}
# How much a gap lowers the fit; most are cheap to close or explain, a few are hard requirements.
GAP_COST = {"contracting": 10, "clearance": 3, "language": 4, "pmp": 3, "budget": 3, "supervision": 3, "tools": 2,
            "eoc_tools": 2, "ics_advanced": 2, "grant_compliance": 2, "cem": 2}
# Series covered by OPM's administrative and management group standard, where graduate study can stand in for
# specialized experience at GS-7 and GS-9.
GROUP_SERIES = {"0018", "0080", "0089", "0130", "0131", "0132", "0201", "0260", "0301", "0340", "0341", "0343",
                "0346", "0501", "0560", "0685", "1035", "1101", "2003", "2010"}
# Pay plans numbered like the GS: GW (wildland firefighters) and the SEC, NCUA, FDIC, CFTC and FAA grades.
GS_LIKE = ("GS", "GG", "GL", "GM", "GW", "SK", "CU", "CG", "CT", "FG")
SENIOR_PLANS = ("ES", "SL", "ST", "SR", "SN", "SO", "IE", "IP")  # senior executive and senior professional pay plans
TS_SCI = re.compile(r"\bts/sci\b|top secret")


def grade_span(grade: str) -> tuple[str, int, int] | None:
    """("GS", 11, 13) for "GS-11/13"; None when the grade gives no number."""
    m = re.match(r"([A-Z]{2})-0*(\d+)(?:/0*(\d+))?", (grade or "").upper())
    if not m:
        return None
    low = int(m.group(2))
    return m.group(1), low, int(m.group(3) or low)


def resume_fit(job: dict, text: str) -> dict:
    """How well Daniel's resume answers a posting.

    Returns {"score": 0-100, "level": "Strong"|"Good"|"Possible"|"Stretch", "angles": [strengths to lead with],
    "gaps": [things the posting asks for that the resume doesn't show], "flags": [grade and eligibility notes]}.
    """
    title = (job.get("title") or "").lower()
    body = f"{title} {text}".lower()
    hits = []
    for angle_id, weight, patterns in _ANGLES:
        in_title = any(p.search(title) for p in patterns)
        count = sum(1 for p in patterns if p.search(body))
        if in_title or count:
            hits.append((((3 if in_title else 0) + 0.7 * min(count, 2)) * weight, angle_id))
    hits.sort(key=lambda h: -h[0])
    # The two strongest strengths say whether the job is about something he has done (a title match counts most);
    # each further hands-on strength the posting touches (not the general ones such as writing) adds a little.
    first = hits[0][0] if hits else 0
    second = hits[1][0] if len(hits) > 1 else 0
    hands_on = sum(1 for _, angle_id in hits[2:] if WEIGHTS[angle_id] >= 0.8)
    score = 28 + 6 * first + 4 * second + 2 * min(hands_on, 4)

    gaps = [gap_id for gap_id, patterns in _GAPS if any(p.search(body) for p in patterns)]
    # A COR duty or "works with contracting officers" doesn't make a job a contracting job.
    if "contracting" in gaps and "1102" not in (job.get("series") or []) and not re.search(r"contract|procurement|purchas|acquisition", title):
        gaps.remove("contracting")
    score -= min(12, sum(GAP_COST.get(g, 0) for g in gaps))
    if "clearance" in gaps and TS_SCI.search(body):
        score -= 6

    for pattern, points in PENALTY_PATTERNS:
        if re.search(pattern, title):
            score -= points
            break
    if (job.get("grade") or "").upper().startswith(("WG", "WL", "WS")):
        score -= 25

    flags = []
    span = grade_span(job.get("grade") or "")
    series = set(job.get("series") or [])
    if span and span[0] in GS_LIKE:
        _, low, high = span
        if low <= 9 <= high or low <= 7 <= high:
            score += 6
            if series & GROUP_SERIES:
                flags.append("gs_edu")
        if low <= 12 and high >= 11:
            score += 6
            flags.append("gs_11_12")
        if low >= 14:
            score -= 25
            flags.append("gs_14")
        elif low >= 13:
            score -= 8
            flags.append("gs_13")
        if high <= 5:
            score -= 14
            flags.append("gs_low")
        elif high <= 7:
            score -= 6
            flags.append("gs_low")
    elif span and span[0] in SENIOR_PLANS:
        score -= 30
        flags.append("gs_14")
    elif span and span[0] == "CC":
        # Public Health Service Commissioned Corps billets ("O-6 Billet"), which usually go to commissioned officers.
        score -= 25
        flags.append("commissioned")
    elif not (job.get("grade") or "").upper().startswith(("WG", "WL", "WS")):
        # No GS-style grade (state, local and legislative jobs, federal pay bands): the level is unknown, so the job
        # gets what a typical reachable GS grade adds, instead of trailing federal jobs that state theirs.
        score += 6
    if job.get("open_to_public") is False:
        score -= 18
        flags.append("status_only")

    level = (job.get("level") or "").lower()
    kind = next((k for k in ("federal", "state", "local") if k in level), "")
    if re.search(r"house|senate|congress|council|legislat|general assembly", level):
        kind = "legislative"
    if kind:
        flags.append(f"level_{kind}")

    score = int(max(0, min(100, round(score))))
    return {"score": score, "level": fit_level(score), "angles": [a for _, a in hits[:4]], "gaps": gaps[:4], "flags": flags}


def fit_level(score: int) -> str:
    return next(name for cut, name in LEVELS if score >= cut)


def blended_score(interest: int, fit: dict) -> int:
    """The list's match score: 40% what Daniel wants, 60% what his resume backs up."""
    return int(round(0.4 * interest + 0.6 * fit["score"]))
