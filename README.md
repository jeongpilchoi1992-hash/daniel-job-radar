# Job Radar

A two-tab job board published with GitHub Pages and refreshed twice a day by GitHub Actions.

- **Daniel (public service):** federal, Virginia state, and Northern Virginia local government openings within 50 miles of Manassas, VA.
- **J.P. (global finance):** openings that fit J.P.'s resume as a Korean national: international financial institutions in Washington DC, visa-friendly U.S. finance roles, and global firms in Seoul, Singapore and Hong Kong.

Closed postings drop off automatically, and every job links to its official posting.

## Where the jobs come from

| Source | What it covers | How |
| --- | --- | --- |
| USAJOBS Search API | Federal jobs within 50 miles of Manassas, plus remote federal jobs | Official API (free key) |
| U.S. Senate Employment Office | Senate member, committee and officer jobs in DC and nearby (internships left out) | Public job board |
| U.S. House career sites | Member, committee and House officer jobs in DC and nearby | Public career-site search |
| DC Council | Council jobs | Public RSS feed |
| jobs.virginia.gov | Commonwealth of Virginia agencies in nearby cities, plus remote state jobs | Public search pages, filtered to nearby cities |
| governmentjobs.com | Fairfax County, City of Fairfax, Fairfax Water, Prince William, Manassas, Alexandria, Loudoun, Leesburg, Vienna, Stafford, Culpeper, Front Royal, Frederick County, and any county or city board learned from the launch search | Public listing pages |
| Employer job boards (Workday, Greenhouse, Lever, SmartRecruiters, Ashby) | Finance roles at employers found by the launch search for J.P. | Public job-board APIs |
| Launch-day AI search | Congressional, General Assembly and other postings no feed covers; J.P.'s international and Korea-focused roles | Claude with web search, run once at launch |

governmentjobs.com sometimes stops answering cloud servers part way through a run. When that happens, the site keeps each county's earlier listings until their closing dates and fills in the rest on the next run.

jobs.virginia.gov challenges clients that send more than about six requests in five minutes, so the refresh asks only for nearby cities, reads 50 jobs per page, and waits about a minute between pages (roughly ten minutes per run). Arlington County moved its hiring to its own site, which blocks automated visitors, so Arlington County jobs appear only when the launch search found them.

## AI use and cost

Claude wrote the application briefs and ran the web searches **once, at launch**. Those results are stored in `data/`, and the code that called the Anthropic API was removed afterwards. The twice-daily refresh uses only the free sources above, so it spends no AI credit. Postings found by the launch search are re-checked on every refresh and removed when they close.

For jobs without a stored brief, the site's "Ask Claude" button opens claude.ai with the posting filled in, using the viewer's own Claude account.

## Setup

1. Repository secrets (Settings → Secrets and variables → Actions): `USAJOBS_API_KEY` and `USAJOBS_EMAIL` (the email registered at developer.usajobs.gov).
2. Settings → Pages → Source: **GitHub Actions**.
3. The workflow runs at 6:15 AM and 6:15 PM Eastern, on every push to `main`, and on demand from the Actions tab.

Settings live in `config/settings.json` (home location, radius, nearby Virginia cities, county job boards) and `config/boards.json` (extra employer job boards for J.P.'s tab, optional).
