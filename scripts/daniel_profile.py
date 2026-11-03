"""Daniel's resume (2026), as the site uses it to match jobs.

Everything here comes from the resume Daniel shared. Contact details are left out on purpose: the site is
public. Each "angle" is one strength on the resume, with the posting words that call for it and the resume
line to lead with when they do. Each "gap" is something postings often ask for that the resume does not show
yet, with a tip. The collector matches these against every posting and writes the result as job["resume"];
the display text (not the patterns) goes into data/jobs.json so the site can show it.
"""

from __future__ import annotations

SUMMARY = (
    "Emergency management and public health operations professional, about seven years at IEM supporting FEMA, "
    "state agencies and local governments: multi-state COVID-19 logistics, tabletop and FEMA full-scale "
    "exercises, proposal research, and office operations. M.A., Global Affairs, George Mason University (2016). "
    "Former AmeriCorps VISTA with Habitat for Humanity. Lives in Manassas, VA, and follows politics and policy closely."
)

FACTS = [
    "M.A., Global Affairs, George Mason University (May 2016)",
    "IEM, June 2019 – August 2026: Associate Assistant, Operations Specialist, Project Operations Specialist",
    "EMI Professional Development Series certificate; FEMA IS-100, 120, 700, 800, 2500, 2600",
    "Lean Six Sigma Yellow Belt",
    "No security clearance listed on the resume",
]

# Phrases the resume backs up. A posting keyword that matches one of these shows as "on his resume";
# the rest show as "add only if true".
CLAIMS = [
    "emergency management", "disaster recovery", "preparedness", "public assistance", "exercise", "after-action",
    "logistics", "supply", "procurement", "inventory", "vendor", "public health", "vaccin", "pandemic",
    "grant application", "proposal", "solicitation review", "sam.gov", "market research", "research", "data analysis",
    "microsoft excel", "excel", "microsoft office", "spreadsheet", "report writing", "reporting", "minutes",
    "written communication", "documentation", "onboarding", "travel", "customer service", "interpersonal skills",
    "interview", "coordination", "stakeholder", "federal, state, and local", "local government",
    "project management", "operations specialist", "project operations", "office management", "nims", "ics",
    "is-100", "is-120", "is-700", "is-800", "is-2500", "is-2600",
    "incident command", "fema", "process improvement", "lean six sigma", "training", "meeting facilitation", "facilitat",
    "intake", "claims", "data entry", "community engagement", "volunteer", "international",
    "policy analysis", "public policy", "rural health", "oral communication", "team leadership",
]
# Posting phrases that contain one of the claims but mean work the resume doesn't show ("False Claims Act", "exercise of
# options", "media interviews"). They show as "add only if true". Regular expressions, matched without case.
NOT_CLAIMS = [
    r"claims act", r"fraud", r"operations? research|operational research", r"media interview", r"witness", r"verbatim",
    r"exercise of", r"research,? (and )?development|\br&d\b", r"\bconcur\b", r"microsoft project|visio",
    r"(legislative|policy|regulatory|budgetary)\b.*\bproposals?", r"interagency",
]

# (id, short label, resume line to lead with, posting patterns, weight, keywords he can claim)
ANGLES: list[dict] = [
    {
        "id": "exercises",
        "label": "FEMA exercises",
        "cite": "Facilitated full-scale and tabletop exercises for federal, state and private clients (2022–2024), led a "
                "Simulation Cell unit at FEMA full-scale exercises two years in a row, and wrote the notes used for after-action reports.",
        # Exercises the noun, not the verb ("exercises supervision", "exercises judgment").
        "patterns": [r"(conduct|design|develop|plan|run|facilitat|evaluat|coordinat|support|participat)\w*,?( in| and \w+)? exercises\b",
                     r"\b(coop|continuity|response|training|emergency|preparedness) exercises\b|(drills|trainings?|workshops) (and|&) exercises",
                     r"exercise (design|program|plan|planning|planner|coordinat|develop|evaluat|facilitat|series|control|officer|specialist)",
                     r"(tabletop|functional|full[- ]scale|preparedness|emergency|discussion[- ]based|operations[- ]based) exercise",
                     r"\bhseep\b", r"after[- ]action", r"(?<!performance )improvement plan", r"\bsimcell\b|simulation cell",
                     r"\b(emergency|evacuation|preparedness|disaster) drills?\b"],
        "weight": 1.0,
        "keywords": ["exercise facilitation", "tabletop exercises", "full-scale exercises", "Simulation Cell (SimCell)", "after-action reports"],
    },
    {
        "id": "logistics",
        "label": "COVID-19 logistics",
        "cite": "Oversaw logistics for COVID-19 mass vaccination and monoclonal antibody sites in Texas, Nevada, Virginia and "
                "Florida (2021–2022), and procured and tracked medical supplies across six states.",
        "patterns": [r"logistic", r"supply chain", r"\bsuppl(y|ies)\b", r"inventory", r"(?<!data )warehous", r"\bdistribution\b", r"resource (request|ordering|typing|mobilization)",
                     r"commodit", r"property (management|accountability|book)", r"asset management", r"shipping|receiving", r"\bfleet\b(?! (and|&) family)",
                     r"procur", r"purchas", r"mass care", r"points? of (dispensing|distribution)", r"\bvendors?\b"],
        "weight": 1.0,
        "keywords": ["logistics", "supply chain", "procurement", "inventory tracking", "vendor relations", "mass care operations"],
    },
    {
        "id": "public_health",
        "label": "Public health response",
        "cite": "Supported COVID-19 mass vaccination and monoclonal antibody sites (87,000+ infusions), took minutes at a state "
                "public health agency's weekly meetings during the mpox response (2022–23), and attended the APHA and National "
                "Healthcare Coalition Preparedness conferences (2022).",
        "patterns": [r"public health", r"health (emergency|security|preparedness|department|district)", r"pandemic", r"vaccin", r"immuniz",
                     r"outbreak", r"epidemi", r"health ?care coalition", r"hospital preparedness", r"\bphep\b", r"\bhpp\b", r"\baspr\b",
                     "centers for disease control", r"strategic national stockpile", r"medical countermeasure", r"biodefense|biological (threats?|agents?|incidents?|weapons?|select agents?)", r"infectious disease",
                     r"\bmpox\b|\bcovid"],
        "weight": 1.0,
        "keywords": ["public health emergency preparedness", "mass vaccination", "pandemic response", "medical countermeasures", "outbreak response"],
    },
    {
        "id": "rural_health",
        "label": "Rural Health Transformation",
        "cite": "Has tracked how states carry out the Rural Health Transformation Program since November 2025, including which "
                "states are on track and which are struggling.",
        "patterns": [r"rural (health|hospitals?|clinics?|health ?care|providers?)", r"\brhtp\b", r"rural health transformation", r"medicaid", r"\bcms\b", r"centers for medicare",
                     r"health (care )?(policy|reform|systems? transformation)", r"critical access", r"health (care )?access"],
        "weight": 1.0,
        "keywords": ["Rural Health Transformation Program", "rural health", "state implementation tracking", "health policy"],
    },
    {
        "id": "fema_grants",
        "label": "FEMA programs & grants",
        "cite": "Helped sequence onboarding for FEMA Public Assistance staff by organizing spreadsheets and analyzing the data "
                "for decision makers (2019–2020), and helped counties update their COVID-19 emergency grant applications (2020).",
        "patterns": [r"\bfema\b", r"public assistance", r"stafford act", r"\bgrants?\b(?![- ]funded)", r"(fema|disaster|grant|public assistance) reimburse|reimburse\w* (from|by) fema", r"sub-?recipient|subgrant",
                     r"disaster recovery|recovery (program|operations|grant)", r"hazard mitigation", r"\bbric\b", r"\bempg\b", r"\bhsgp\b"],
        "weight": 1.0,
        "keywords": ["FEMA Public Assistance", "grant applications", "disaster grants", "county and local applicants"],
    },
    {
        "id": "intake",
        "label": "Disaster intake team lead",
        "cite": "Led a five-person intake center for ReBuild NC after Hurricane Matthew (2019), helping homeowners through "
                "application questions.",
        "patterns": [r"\bintake\b", r"case ?manag", r"casework", r"applicants? (assistance|services|support)", r"housing (recovery|assistance)",
                     r"individual assistance", r"homeowner", r"walk-in", r"eligibility (determination|review|interview)", r"survivor"],
        "weight": 0.9,
        "keywords": ["intake", "applicant assistance", "team lead", "customer service", "disaster survivors"],
    },
    {
        "id": "proposals",
        "label": "Proposals & contract research",
        "cite": "Found and screened multimillion-dollar opportunities on SAM.gov, GovWin, BidPro and the DHS forecast (2019–2024) "
                "and led proposal writing.",
        "patterns": [r"proposal", r"solicitation", r"\brf[pqi]s?\b", r"request for (proposal|quote|information)", r"business development|\bcapture\b",
                     r"sam\.gov", r"\bcontracts?\b|contracting", r"acquisition", r"statement of work|\bsow\b|\bpws\b", r"market research",
                     r"grant writ"],
        "weight": 0.8,
        "keywords": ["proposal writing", "solicitation review", "SAM.gov", "market research", "business development"],
    },
    {
        "id": "project_ops",
        "label": "Project operations",
        "cite": "Operations Specialist and Project Operations Specialist at IEM (2021–2026): assisted project managers on site "
                "and helped stand up new mass care sites. His resume summary also names deputy project manager work, not yet tied "
                "to a project or dates.",
        "patterns": [r"project (manag|coordinat|operations|support|specialist|officer|assistant)",
                     r"program (support|operations|coordinat|specialist|assistant)", r"operations (specialist|coordinat|support|manag|officer)",
                     r"deputy (project|program) (manag|direct|lead|coordinat)",
                     r"stand(ing|s)? up (a |an |the |new )*(\w+ ){0,2}(sites?|programs?|offices?|teams?|operations?|centers?)\b"],
        "weight": 0.9,
        "keywords": ["project management", "program support", "operations coordination", "on-site project support"],
    },
    {
        "id": "em_planning",
        "label": "Emergency management",
        "cite": "Worked in emergency management and public health at IEM from 2019 to 2026 with FEMA, state agencies, local "
                "governments and a large travel company, including emergency forms built on EM best practices (2024).",
        # "Emergency" alone also names EMT, 911, snow-plow and crisis-counseling jobs, which are not emergency management.
        "patterns": [r"(?<!operator )emergenc(?!y (medical|room|department|vehicle|communications?|dispatch|call|telecommunicat|"
                     r"response (officer|dispatch|team member)|services? (&|and) crisis|veterinar|repair|maintenance))",
                     # Not "continuity of care", "security incidents" or "hazardous materials".
                     r"continuity of (operations|government)|continuity (plan|program)|business continuity", r"\bcoop\b",
                     r"crisis (management|communication|response (plan|team)|action|leadership|planning|coordinat)", r"preparedness",
                     r"incident (command|action plan|management team)|(major|emergency|disaster|mass casualty) incidents?", r"resilien",
                     r"disaster", r"all[- ]hazards?|natural hazards?|multi[- ]hazards?|hazard (mitigation|vulnerability)",
                     r"response (and|&) recovery", r"homeland security"],
        "weight": 1.0,
        "keywords": ["emergency management", "emergency planning", "preparedness", "response and recovery"],
    },
    {
        "id": "nims",
        "label": "FEMA / EMI training",
        "cite": "EMI Professional Development Series certificate and FEMA courses IS-100, IS-120, IS-700, IS-800, IS-2500 and IS-2600.",
        "patterns": [r"\bnims\b", r"\bics\b", r"incident command", r"national response framework", r"\bnrf\b", r"emergency operations? cent",
                     r"\beoc\b", r"\bemi\b", r"independent study", r"\bis-\d{3}"],
        "weight": 0.8,
        "keywords": ["NIMS (IS-700)", "ICS (IS-100)", "National Response Framework (IS-800)", "EMI Professional Development Series"],
    },
    {
        "id": "intergov",
        "label": "Federal, state & local clients",
        "cite": "Worked at every level of government (FEMA, state agencies, county governments) and with a major transportation company.",
        "patterns": [r"intergovernmental", r"federal,? state,? (and|&) local", r"state and local", r"local (government|jurisdiction)s?",
                     r"interagency", r"stakeholder", r"\bliaison\b", r"partner(s|ships?)\b", r"coordinat"],
        "weight": 0.7,
        "keywords": ["federal, state, and local partners", "interagency coordination", "stakeholder engagement"],
    },
    {
        "id": "analysis",
        "label": "Research & data analysis",
        "cite": "Built Excel pivot-table trackers of multi-state COVID-19 spending, organized FEMA onboarding data for decision makers, "
                "and wrote research for a state health agency's trauma training review (2018).",
        "patterns": [r"analy[sz]", r"\bresearch", r"\bdata\b", r"excel|spreadsheet|pivot", r"metrics|dashboard", r"\breport(s|ing)\b",
                     r"program evaluat|evaluat(e|es|ing) (the )?(effectiveness|programs?|data|polic)"],
        "weight": 0.6,
        "keywords": ["research and analysis", "data analysis", "Microsoft Excel (pivot tables)", "reporting"],
    },
    {
        "id": "writing",
        "label": "Minutes & writing",
        "cite": "Kept minutes at weekly meetings (a state health agency during mpox, 2022–23; a large travel company, 2024) "
                "and writes proposals and client-focused documents.",
        "patterns": [r"\bminutes\b", r"meetings?\b", r"\bwrit(e|es|ing|ten)\b", r"correspondence", r"briefing", r"\bmemos?\b",
                     r"documentation", r"\bedit(ing|s)?\b", r"talking points"],
        "weight": 0.6,
        "keywords": ["meeting minutes", "written communication", "documentation", "client-focused documents"],
    },
    {
        "id": "office_ops",
        "label": "Office operations",
        "cite": "Handled office manager duties at IEM (2019–2024): office security, first-line IT help, deliveries, conference "
                "supplies, Certify expense questions and flights for corporate-level staff, and helped with onboarding and offboarding.",
        # Office work itself, not "administrative leave", "travel required" or "work schedule".
        "patterns": [r"office (manag|administr|operations|services|support)",
                     r"administrative (support|services|assistant|officer|specialist|duties|operations|management)", r"onboard|offboard",
                     r"travel (arrangements?|coordinat|book|planning|expenses?|vouchers?|authorizations?|claims)",
                     r"facilit(y|ies) (manag|operations|security)", r"executive (assistant|support)",
                     r"schedul(e|es|ing) (meetings|appointments|travel|calendars?)|calendar management", r"purchase card|p-?card",
                     r"front desk|reception", r"badg|access control|physical security",
                     r"conference (planning|logistics|support|coordinat|rooms?|services)|(plan|coordinat)\w* conferences"],
        "weight": 0.6,
        "keywords": ["office management", "onboarding and offboarding", "travel coordination", "expense reporting (Certify)", "office security"],
    },
    {
        "id": "volunteers",
        "label": "Volunteer recruiting & interviews",
        "cite": "Vetted resumes of language volunteers for Department of Defense requests and ran ten scripted interviews at the "
                "National Language Service Corps (2018).",
        "patterns": [r"\binterview", r"recruit", r"\bvolunteers?\b", r"vetting|screen(ing)? (applicants|candidates|resumes)",
                     r"human resources|staffing|talent acquisition", r"department of defense|\bdod\b"],
        "weight": 0.5,
        "keywords": ["interviewing", "volunteer recruitment", "candidate screening", "Department of Defense"],
    },
    {
        "id": "claims",
        "label": "Claims processing",
        "cite": "Processed hundreds of workers' compensation claims a day for California and Virginia at CorVel (2017–2018).",
        "patterns": [r"\bclaims?\b", r"data entry", r"\bbenefits (processing|specialist|program)", r"workers'? comp", r"adjudicat",
                     r"case processing", r"records (management|processing)"],
        "weight": 0.5,
        "keywords": ["claims processing", "data entry", "attention to detail", "high-volume processing"],
    },
    {
        "id": "global",
        "label": "Global affairs (M.A.)",
        "cite": "M.A., Global Affairs, George Mason University (2016): globalization and development, global trade, foreign "
                "investment, Middle East ethnography, social movements and human rights.",
        "patterns": [r"international", r"\bforeign\b", r"\bglobal\b", r"\btrade\b", r"human rights", r"middle east", r"diploma",
                     r"refugee|humanitarian|migration", r"development (assistance|finance|program)", r"geopolit", r"national security"],
        "weight": 0.6,
        "keywords": ["international affairs", "global trade and development", "human rights", "Middle East"],
    },
    {
        "id": "policy",
        "label": "Policy & politics",
        "cite": "Has tracked states' Rural Health Transformation Program rollout since November 2025, including which states are "
                "on track and which are struggling; M.A. in Global Affairs (2016).",
        "patterns": [r"\bpolic(y|ies)\b", r"legislat", r"congress", r"politic(?!al (affiliation|activit))", r"government(al)? (affairs|relations)", r"general assembly",
                     r"board of supervisors", r"\bcouncil\b", r"constituent", r"\belection", r"\bvoter"],
        "weight": 0.6,
        "keywords": ["policy analysis", "policy tracking", "public policy", "state implementation"],
    },
    {
        "id": "community",
        "label": "AmeriCorps VISTA",
        "cite": "Former AmeriCorps VISTA with Habitat for Humanity, working through the lens of building communities.",
        "patterns": [r"\bcommunity\b", r"nonprofit|non-profit", r"americorps|\bvista\b", r"\bhousing\b", r"outreach", r"engagement"],
        "weight": 0.6,
        "keywords": ["community engagement", "AmeriCorps VISTA", "nonprofit experience", "housing"],
    },
    {
        "id": "process",
        "label": "Lean Six Sigma",
        "cite": "Lean Six Sigma Yellow Belt.",
        "patterns": [r"process improvement", r"\blean\b", r"six sigma", r"continuous improvement", r"efficienc", r"quality (assurance|improvement)",
                     r"streamlin"],
        "weight": 0.5,
        "keywords": ["process improvement", "Lean Six Sigma Yellow Belt"],
    },
    {
        "id": "ai_tools",
        "label": "AI tools",
        "cite": "Uses AI tools (Claude, Microsoft Copilot).",
        "patterns": [r"artificial intelligence", r"\bai\b", r"generative", r"copilot", r"machine learning", r"large language", r"\bllms?\b"],
        "weight": 0.4,
        "keywords": ["AI tools (Claude, Microsoft Copilot)"],
    },
]

# Things postings ask for that the resume does not show yet.
GAPS: list[dict] = [
    {
        "id": "ics_advanced",
        "label": "ICS-200/300/400",
        # ICS-200 and above, also in lists such as "ICS 100/200/700" or "IS-100, 200 and 700"; not "caseload is 200".
        "patterns": [r"\b(?:(?:ics|nims)[- ]?|is-)(?:\d{3,4}\s*(?:[,/&]|and|-|through|to)\s*(?:is-|ics-?\s?)?)*?[234]00\b"],
        "tip": "Asks for ICS courses beyond his IS-100. IS-200 is free online at training.fema.gov and takes a few hours, so "
               "finish it before applying; ICS-300 and 400 are classroom courses run through VDEM and local emergency offices.",
    },
    {
        "id": "hseep",
        "label": "HSEEP",
        "patterns": [r"\bhseep\b", r"homeland security exercise and evaluation"],
        "tip": "Names HSEEP. His FEMA exercise work and IS-120 (which introduces HSEEP) fit, so write \"HSEEP\" into the exercise "
               "bullet if those exercises followed it. FEMA's HSEEP course (K0146) is the next step; it needs a sponsoring agency's "
               "signature and the State Training Officer's approval.",
    },
    {
        "id": "eoc_tools",
        "label": "EOC software / GIS",
        "patterns": [r"webeoc", r"\bveoc\b", r"juvare", r"everbridge", r"crisis ?track", r"\bgis\b", r"arcgis|esri"],
        "tip": "Names software that isn't on the resume (WebEOC, GIS or similar). Add any he used on FEMA or COVID-19 projects; "
               "otherwise name the systems he has used (GovWin, SAM.gov, Certify).",
    },
    {
        "id": "clearance",
        "label": "Security clearance",
        # Only real clearance requirements: nearly every federal job runs a background check, which no resume can fix.
        "patterns": [r"\b(top )?secret\b(?! service)", r"\bts/sci\b", r"\bsci (eligib|access|clearance)", r"\bq clearance\b",
                     r"(secret|top secret|ts|sci) (security )?clearance",
                     r"(?<!\bno )security clearance (is )?(required|at the)(?!\s*[:?]\s*(no|none|n/a|not)\b)"],
        "tip": "Needs a Secret or higher security clearance, and the resume lists none. The agency can sponsor one after an offer, "
               "but it adds months; if FEMA contract work gave him a Public Trust or other investigation, add it with the year.",
    },
    {
        "id": "supervision",
        "label": "Supervision",
        # "Under general supervision" and "Non-Supervisory" are boilerplate, not a request for supervisors.
        "patterns": [r"(?<!non-)(?<!non)\bsupervisory\b", r"supervis(e|es|ing) (a |the )?(staff|team|employees|personnel|subordinate|work of)",
                     r"lead(s|ing)? (a )?(team|staff)", r"manag(e|es|ing) (a )?(team|staff)", r"team lead"],
        "tip": "Asks for supervision. Lead with the five-person ReBuild NC intake team and the Simulation Cell unit he led at FEMA exercises, with "
               "team sizes, and any staff he trained.",
    },
    {
        "id": "budget",
        "label": "Budget",
        "patterns": [r"budget (formulation|execution|development|analysis|preparation)", r"appropriations (law|process|committee|request)",
                     r"financial management", r"cost (estimat|analysis)", r"fiscal (analysis|management|oversight|planning)"],
        "tip": "Asks for budget work. Use the pivot-table spending tracking for six-state COVID-19 purchases, and add dollar "
               "amounts he managed or tracked if he can.",
    },
    {
        "id": "grant_compliance",
        "label": "Grant compliance",
        "patterns": [r"2 cfr|uniform guidance", r"sub-?recipient", r"\bnofos?\b|notice of funding", r"grants? (management|compliance|monitoring|administration)",
                     r"closeout"],
        "tip": "Uses grant-compliance terms (2 CFR 200, NOFOs, subrecipient monitoring) that aren't on his resume. Lead with the "
               "county COVID-19 grant applications and FEMA Public Assistance support, and add only terms he worked with.",
    },
    {
        "id": "contracting",
        "label": "Federal contracting",
        # Counted only on contracting jobs (see resume_fit): a COR duty elsewhere doesn't need FAC-C.
        "patterns": [r"\bfac-?c\b", r"fac-?cor", r"\bdawia\b", r"contracting officer", r"\b1102\b",
                     r"contracting warrant|warranted contracting|\bwarrant (authority|level|holder)", r"contract specialist"],
        "tip": "Federal contracting wants pre- and post-award experience and FAC-C or DAWIA training. His proposal and purchasing "
               "work was on the contractor side, so aim at the lowest grade offered and show, in his own words, how that work meets "
               "each part of the specialized-experience statement.",
    },
    {
        "id": "legislative",
        "label": "Politics on paper",
        # Skips boilerplate such as "a legislative branch agency" and "political affiliation" in EEO statements.
        "patterns": [r"legislat(?!ive branch)", r"congressional (affairs|relations|liaison|staff|inquir|correspondence|testimony|hearing)",
                     r"general assembly", r"capitol hill", r"constituent (services|casework|correspondence|mail|inquir|relations)",
                     r"politic(?!al (affiliation|activit))", r"board of supervisors", r"city council"],
        "tip": "Politics is his strength, but the resume doesn't show it yet. Add a line on following federal and Virginia "
               "legislation, any civic volunteering (campaign or party work only for legislative or political offices), and the "
               "Rural Health Transformation Program tracking as policy work.",
    },
    {
        "id": "language",
        "label": "Second language",
        "patterns": [r"spanish", r"bilingual", r"foreign language", r"language proficiency"],
        "tip": "Asks for a second language. List any language he speaks and the level, or leave it off.",
    },
    {
        "id": "tools",
        "label": "Named software",
        "patterns": [r"sharepoint", r"power ?bi", r"tableau", r"salesforce", r"\bcrm\b", r"smartsheet", r"microsoft project|\bms project\b",
                     r"access database", r"\bsql\b", r"python"],
        "tip": "Names software beyond Microsoft Office. Add the ones he has really used; Excel pivot tables, Certify, GovWin and "
               "SAM.gov are worth naming already.",
    },
    {
        "id": "cem",
        "label": "CEM credential",
        "patterns": [r"certified emergency manager", r"\bcem\b", r"professional emergency manager"],
        "tip": "Values IAEM's Certified Emergency Manager (CEM). With an M.A. and about seven years in emergency management he "
               "may meet the experience and education parts already; the training hours, contributions and exam come next "
               "(details on iaem.org).",
    },
    {
        "id": "pmp",
        "label": "PMP",
        "patterns": [r"\bpmp\b", r"project management professional", r"\bcapm\b"],
        "tip": "Asks for the PMP. It needs 36 months leading projects plus 35 hours of training; the CAPM is the entry-level "
               "option if he wants the letters on the resume soon.",
    },
]

# Notes worked out from a job's grade, level and who may apply (keys match resume_fit()).
FLAGS = {
    "gs_edu": "GS-7 and GS-9 in most administrative series can be met with related graduate study instead of experience "
              "(one year for GS-7, a master's for GS-9). Check the Education section to see whether a Global Affairs M.A. "
              "counts, and upload his George Mason transcript.",
    "gs_11_12": "GS-11/12 asks for a year of specialized experience at the next lower grade. Answer each part of the posting's "
                "specialized-experience sentence with IEM work for FEMA and state clients, in his own words, with dates and "
                "hours per week.",
    "gs_13": "GS-13 needs a year at GS-12 level: planning or leading work, not supporting it. Apply only if the "
             "specialized experience reads like his IEM projects.",
    "gs_14": "GS-14 and above usually need years of senior leadership. This is a long shot from his current resume.",
    "gs_low": "Below his experience level, but a way into the agency. Use it as a foot in the door if the work appeals.",
    "commissioned": "Posted under the Public Health Service Commissioned Corps pay plan. These billets usually go to "
                    "commissioned officers, not civilians, so read the Who May Apply section before spending time on it.",
    "brief_not_eligible": "The brief below found a requirement the resume doesn't meet, such as who may apply, a license or "
                          "military service. Read its eligibility notes before spending time on it.",
    "status_only": "Limited to current or former federal employees or other status groups. Contractor time at IEM doesn't "
                   "give federal status, so check the hiring paths before spending time on it.",
    "level_federal": "Federal resume: two pages at most. Give month/year dates and hours per week for each job, and answer "
                     "the posting's specialized-experience sentence in his own words; agencies give pasted announcement text no credit.",
    "level_state": "Virginia state jobs screen on the application itself: paste the strongest resume bullets into each job's "
                   "duties and answer every supplemental question in full.",
    "level_local": "County and city boards check minimum qualifications first, so put the M.A., FEMA course numbers and "
                   "years in emergency management where a screener sees them.",
    "level_legislative": "Member offices favor ties to their own state, so Virginia roots help most with Virginia members; "
                         "institutional offices (Sergeant at Arms, Chief Administrative Officer) hire on skills, and DC Council "
                         "offices look for DC knowledge. Send a short cover note naming the issues he follows.",
}

# Cutoffs checked on a full refresh (2 November 2026, about 3,250 jobs): roughly the top 5 jobs are Strong, the next 50
# Good and the next 220 Possible.
LEVELS = [(65, "Strong"), (57, "Good"), (47, "Possible"), (0, "Stretch")]


def public_profile() -> dict:
    """What the site shows: labels, resume lines and tips, without the matching patterns."""
    return {
        "summary": SUMMARY,
        "facts": FACTS,
        "claims": CLAIMS,
        "not_claims": NOT_CLAIMS,
        "angles": {a["id"]: {"label": a["label"], "cite": a["cite"], "keywords": a["keywords"]} for a in ANGLES},
        "gaps": {g["id"]: {"label": g["label"], "tip": g["tip"]} for g in GAPS},
        "flags": FLAGS,
        "levels": [name for _, name in LEVELS],
    }
