// Daniel's improved 2026 resume and the notes that go with it. One source for the Word files and the site's
// "Resume & tips" page (see build.js). Text in { hl: "..." } is a placeholder or a fact to confirm; it is
// highlighted in yellow in Word and on the page.
//
// No phone number, email or street address here: this repository and the site are public.

const hl = (text) => ({ hl: text });

const resume = {
  name: "Daniel Marfurt-Levy",
  // The public download shows placeholders; build.js can swap in real contact details for a private copy.
  contact: ["Manassas, VA", hl("[Phone]"), hl("[Email]"), hl("[LinkedIn URL]")],
  headline: "Emergency Management  |  Public Health Response  |  Logistics  |  Exercises  |  FEMA Programs",
  summary:
    "Emergency management and public health operations professional with seven years at IEM supporting FEMA, state " +
    "agencies, and local governments. Oversaw multi-state logistics for COVID-19 mass vaccination and monoclonal antibody sites, " +
    "facilitated tabletop exercises and FEMA full-scale exercises, and researched and wrote proposals for multimillion-dollar government " +
    "contracts. Works independently, writes clearly, and builds working relationships at every level of government. M.A. in " +
    "Global Affairs; former AmeriCorps VISTA with Habitat for Humanity.",
  skills: [
    ["Emergency management", "exercise facilitation (full-scale, tabletop), Simulation Cell, after-action reports, NIMS/ICS, emergency planning"],
    ["Public health response", "mass vaccination and monoclonal antibody sites, mpox response support, healthcare preparedness"],
    ["Operations and logistics", "multi-state procurement, inventory tracking, vendor relationships, site stand-up, onboarding"],
    ["Analysis and writing", "research, Excel pivot tables, proposals (SAM.gov, GovWin), meeting minutes, client documents"],
    ["Tools", "Microsoft Office Suite, Certify, GovWin, SAM.gov, Claude, Microsoft Copilot"],
  ],
  experience: [
    {
      org: "IEM International",
      dates: "June 2019 – August 2026",
      // Non-breaking spaces keep each date range on one line.
      titles: "Project Operations Specialist (Sep 2024 – Aug 2026)  ·  Operations Specialist (Jun 2021 – Aug 2024)  ·  Associate Assistant (Jun 2019 – Jun 2021)",
      groups: [
        {
          heading: "Public health response and logistics",
          bullets: [
            ["Oversaw logistics for COVID-19 mass vaccination and monoclonal antibody sites in Texas, Nevada, Virginia, and Florida at the same time (2021–2022), procuring and tracking medical supplies across six states."],
            ["As part of the logistics team, supported multi-state procurement and distribution of medical supplies, equipment, and vaccines for mass care sites that administered more than ", hl("1.3 million"), " vaccinations and 87,000+ monoclonal antibody infusions."],
            ["Built Excel pivot-table reports on spending and order status, and set up relationships with medical supply, truck rental, and other vendors to keep sites stocked."],
            ["Helped stand up new mass care sites and served as on-site assistant to project managers."],
            ["Took minutes at a state public health agency's weekly meetings during the mpox response (Dec 2022 – Mar 2023)."],
          ],
        },
        {
          heading: "Exercises and emergency planning",
          bullets: [
            ["Facilitated full-scale and tabletop exercises for federal, state, and private-sector clients, in person and virtually (2022–2024)."],
            ["Led a Simulation Cell (SimCell) unit at FEMA full-scale exercises two years in a row and delivered detailed notes used to write the after-action reports."],
            ["Brought emergency management best practices into a large travel company's emergency forms and kept minutes at its weekly meetings (Feb – Aug 2024)."],
            ["Took part in public health seminars on response and recovery roles (2022–2024) and attended the American Public Health Association and National Healthcare Coalition Preparedness conferences (2022)."],
          ],
        },
        {
          heading: "FEMA programs, grants, and recovery",
          bullets: [
            ["Helped sequence onboarding for FEMA Public Assistance employees by organizing spreadsheets and analyzing the data for decision makers (2019–2020)."],
            ["Helped counties update their applications for COVID-19 emergency grants at the start of the pandemic (2020)."],
            ["Led a five-person intake center for ReBuild NC after Hurricane Matthew, answering homeowners' application questions (2019)."],
            ["Aligned training goals between Emergency Management Institute courses and FEMA field guide training manuals (", hl("Oct\u00a02018\u00a0–\u00a0Jun\u00a02019"), ")."],
          ],
        },
        {
          heading: "Business development and policy research",
          bullets: [
            ["Identified multimillion-dollar contract opportunities in GovWin, ", hl("BidPro"), ", SAM.gov, and the ", hl("DHS Acquisition Planning Forecast System (APFS)"), ", and led proposal writing (2019–2024)."],
            ["Tracked state implementation of the Rural Health Transformation Program from November 2025, identifying which states were executing well and which were struggling."],
            ["Provided scholarly research that helped a state public health agency's analysts review trauma-incident training recertification (", hl("2018"), ")."],
          ],
        },
        {
          heading: "Office operations (2019–2024)",
          bullets: [
            ["Handled office manager duties: office security, first-line IT troubleshooting with IT support, deliveries, and conference supplies; assisted with employee onboarding and offboarding."],
            ["Answered employee travel-expense questions in Certify and booked flights for corporate-level staff."],
          ],
        },
      ],
    },
    {
      org: "National Language Service Corps",
      title: "Support Services Specialist",
      dates: "April 2018 – June 2018",
      bullets: [
        ["Contacted and screened translator volunteers for Department of Defense (DoD) language requests: vetted resumes, offered assignments to registered volunteers, conducted 10 scripted interviews, and reported results to the manager."],
      ],
    },
    {
      org: "CorVel",
      title: "EDI Claims Specialist",
      dates: "October 2017 – February 2018",
      bullets: [
        ["Processed hundreds of workers' compensation claims a day for California and Virginia, completing forms from PDF documentation and recording the compensation awarded to each claimant."],
        ["Supported teammates after finishing assigned work."],
      ],
    },
  ],
  service: {
    org: "Habitat for Humanity",
    title: "AmeriCorps VISTA",
    dates: hl("[Month Year – Month Year]"),
    where: hl("[Affiliate, City, State]"),
    bullets: [[hl("[Add one or two results: volunteers recruited, families served, funds raised, or programs started.]")]],
  },
  education: [
    { degree: "Master of Arts, Global Affairs", school: "George Mason University", date: "May 2016",
      note: "Coursework: Economic Globalization and Development; Global Trade Relations; The New Cuba: Foreign Investment; Regional Ethnography of the Middle East; Social Movements and Human Rights; Gender and Violence" },
    { degree: hl("[Bachelor's degree, major]"), school: hl("[College or university]"), date: hl("[Year]") },
  ],
  certifications: [
    ["EMI Professional Development Series Certificate, FEMA Emergency Management Institute"],
    ["FEMA Independent Study: IS-100 (Incident Command System), IS-120 (Introduction to Exercises), IS-700 (National Incident Management System), IS-800 (National Response Framework), IS-2500 (National Prevention Framework), IS-2600 (National Protection Framework); full list on request"],
    ["Lean Six Sigma Yellow Belt"],
  ],
};

// What changed between the PDF and the improved version.
const changes = [
  ["“Daniel provides value by performing tasks independently…” (third person, one long paragraph)", "A five-line professional summary in resume voice that opens with the jobs he is going after"],
  ["Fourteen IEM bullets in no order, some in third person (“he participated”)", "Grouped under five headings (public health response, exercises, FEMA programs, business development, office operations), strongest work first"],
  ["“IEM International | June 2019 – Present”", "“June 2019 – August 2026”, so the dates match his last title"],
  ["“over 1.3 vaccines administered”", "“more than 1.3 million vaccinations” (highlighted to confirm)"],
  ["“lead writing solicitations”", "“led proposal writing”: agencies write solicitations, and contractors answer them"],
  ["“DHS APHS”", "“DHS Acquisition Planning Forecast System (APFS)” (highlighted to confirm)"],
  ["“Diagnosed basic IT tasks based on IT support recommendations”", "“first-line IT troubleshooting with IT support”"],
  ["“a highly renown transportation company”, “analysists”, “Entailed calling…”", "Typos and filler removed throughout"],
  ["“LLM User- Claude/Co-Pilot”", "“Tools: … Claude, Microsoft Copilot”"],
  ["“FEMA Emergency Management Courses- 100, 120, 700, 800, 2500, 2600”", "Each IS course named, so screeners and keyword filters recognize them"],
  ["Skills list of five general items", "A core skills block in the words postings use (exercises, logistics, public health, proposals)"],
  ["Street address in the header", "City and state only, plus placeholders for phone, email and LinkedIn"],
];

// Facts to confirm before sending (each is highlighted in the Word file).
const checks = [
  ["1.3 million vaccinations.", "The PDF says “over 1.3 vaccines administered”. The edit assumes 1.3 million; replace it with the real number."],
  ["Dates before IEM.", "Two IEM bullets are dated 2018 (the EMI and FEMA training work from Oct 2018, and the state health agency research), but IEM starts in June 2019. Either the IEM start date is earlier, for example an internship, or those items belong to another role. Federal HR specialists check dates closely."],
  ["Tool names.", "“DHS APHS” was changed to the DHS Acquisition Planning Forecast System (APFS), and “BidPro” was kept. Correct either if the real name differs."],
  ["AmeriCorps VISTA.", "It appears only in the old summary. Add the dates, the Habitat for Humanity affiliate and city, and one or two results."],
  ["Bachelor's degree.", "Many postings screen for a bachelor's degree. List the school, major and year under the M.A."],
  ["Project roles.", "The old summary says he worked as a deputy project manager, planner, logistics specialist, research and development specialist and data analyst, but no bullet says where. If these were formal titles on IEM projects, add each one to the matching bullet or heading with its dates, because federal screeners only credit titles they can see."],
  ["Contact line.", "The download on this site has placeholders for phone, email and LinkedIn because the site is public. Fill them in before sending."],
];

// Tips: what would make the resume stronger.
const tips = [
  {
    heading: "Numbers to add",
    items: [
      "Exercises: how many he facilitated, how many agencies and players took part, and the size of the SimCell team he led.",
      "COVID-19 logistics: the number of sites, the dollar value of supplies tracked, and how many vendors he worked with.",
      "FEMA Public Assistance: how many employees the onboarding work covered; county grants: how many counties he helped.",
      "Proposals: how many bids he worked on, their total value, and any wins.",
      "For federal applications, hours per week and month/year dates for every job, plus each employer's city and state.",
    ],
  },
  {
    heading: "Activities worth adding",
    items: [
      "Greater Prince William Medical Reserve Corps (Virginia Department of Health): current, local public health preparedness work.",
      "Prince William County Office of Emergency Management volunteer programs (see its Get Involved page).",
      "Officer of election in Prince William County or Manassas: civic work that puts his politics knowledge on paper.",
      "Civic association or advocacy volunteering, plus campaign or party work for Hill, General Assembly or council jobs only. Politics is a strength that doesn't appear on the resume yet.",
      "Memberships and conferences: IAEM or the Virginia Emergency Management Association, alongside the APHA and NHCPC conferences he already lists.",
    ],
  },
  {
    heading: "Skills and training next",
    items: [
      "FEMA IS-200 (Basic Incident Command System for Initial Response): free online and often required with IS-100, 700 and 800.",
      "List the Professional Development Series courses by number (IS-230, 235, 240, 241, 242, 244 and IS-120): screeners search for them.",
      "HSEEP training (FEMA course K0146) for exercise jobs. It needs a sponsoring agency's signature and the State Training Officer's approval, so ask VDEM, a local emergency office or his MRC unit once he volunteers there. ICS-300 and 400 come through VDEM or a local office when a seat opens.",
      "Software he has really used beyond Office: WebEOC, SharePoint, Smartsheet, Power BI or a GIS tool. Name them only if true.",
      "Any Public Trust or security clearance from FEMA contract work, with the year. Say so if none.",
      "Any language besides English, with the level.",
    ],
  },
  {
    heading: "Tailoring for each application",
    items: [
      "Keep this version as the master. For each posting, answer each part of its specialized-experience sentence with his own work, in his own words, and use its keywords only where true. Don't paste the announcement's text: agencies such as HHS give pasted text no credit.",
      "USAJOBS takes two pages at most. Cut the office operations and claims bullets first when space runs short.",
      "For public health jobs, lead with the COVID-19 and mpox work; for emergency management jobs, lead with exercises and FEMA programs.",
      "Prepare a two-minute answer on the Rural Health Transformation Program: which states are doing well, which are struggling, and why. Few candidates can give one.",
    ],
  },
];

module.exports = { resume, changes, checks, tips };
