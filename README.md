# Job Radar

A two-tab job board published with GitHub Pages and refreshed twice a day by GitHub Actions.

- **Daniel (public service):** federal, Virginia state, and Northern Virginia local government openings within 50 miles of Manassas, VA.
- **J.P. (global finance):** openings that fit J.P.'s resume as a Korean national: international financial institutions in Washington DC, visa-friendly U.S. finance roles, and global firms in Seoul, Singapore and Hong Kong.

Closed postings drop off automatically, and every job links to the page where it is posted.

## Using the site

- Daniel's tab filters by level, distance from Manassas, pay, deadline, posting date, telework, and topic. J.P.'s tab filters by region, source (AI picks or employer job boards), deadline, posting date, and segment. **Reset filters** puts a tab back to its starting view.
- Pay uses the top of each job's range and counts hourly pay as 2,080 hours a year. Posting dates come from the source; Workday job boards only say "Posted 3 Days Ago", so those are counted back from the day the board was read. Some sources give no posting date (Virginia state and Senate listings), so a job from them counts as posted on the day it first appeared here, unless it was already listed the first time the site read that source. Jobs these filters cannot judge are left out, and the count line says how many.
- Every job shows its deadline on a line of its own, or "Open until filled" when the posting gives none. County boards round their deadlines ("Closes in 1 week" means 7 to 13 days), so those jobs show a date range, and the deadline filter and warnings use its first day.
- Deadlines for J.P.'s roles in Seoul, Hong Kong and Singapore follow local time there; everything else follows Eastern time.
- Lists come in pages of 30, 50 or 100 jobs, and the browser remembers the choice.
- Clicking "Job Radar" reloads the page with the latest data. Holding the mouse over it sends a few small ships flying out of the radar (original drawings in `assets/flyers.js`); they stay away on touch screens and when the device asks for reduced motion.

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

jobs.virginia.gov challenges clients that send more than about six requests in five minutes, so the refresh asks only for nearby cities, reads 50 jobs per page, and waits about a minute between pages (roughly ten minutes per run, and it stops at 30). If it cannot read every page, the jobs it missed stay listed from the previous run until their closing dates. Arlington County moved its hiring to its own site, which blocks automated visitors, so Arlington County jobs appear only when the launch search found them.

Distances come from coordinates for every town, postal city, county and independent city in Virginia, Maryland, DC and West Virginia (`scripts/gazetteer.json`, built from the ZIP code table of the MIT-licensed [zipcodes](https://github.com/seanpianka/zipcodes) package), plus a hand-checked list for Northern Virginia in `scripts/places.py`. A posting in another state is never counted as nearby.

## How postings are retired

- Jobs from the daily sources disappear when their source stops listing them or their closing date passes. If a source fails, or suddenly lists far fewer jobs than the last run, its earlier jobs stay for up to 10 days or until they close.
- Postings found by the launch search are re-checked every run. One is removed at once when its deadline passes, and otherwise only after two runs in a row find it closed (a 404 page, a "no longer accepting applications" notice, or gone from its employer's job board). Sites that block automated checks keep a posting until its deadline, or for a week without one.
- The launch briefs cannot be regenerated, so a brief is kept for 30 days after its job leaves the list (unless the job's deadline passed), in case the job comes back.

## AI use and cost

Claude wrote the application briefs and ran the web searches **once, at launch** (about $25 of API credit in total, see `data/ai_build.json`). Those results are stored in `data/`, and the code that called the Anthropic API was removed afterwards. The twice-daily refresh uses only the free sources above, so it spends no AI credit. Postings found by the launch search are re-checked on every refresh and removed when they close.

For jobs without a stored brief, the site's "Ask Claude" button opens claude.ai with the posting filled in, using the viewer's own Claude account.

## Setup

1. Repository secrets (Settings → Secrets and variables → Actions): `USAJOBS_API_KEY` and `USAJOBS_EMAIL` (the email registered at developer.usajobs.gov).
2. Settings → Pages → Source: **GitHub Actions**.
3. The workflow runs at 10:15 and 22:15 UTC (6:15 AM and PM Eastern in summer, 5:15 in winter), after pushes to `main` that change code or settings, and on demand from the Actions tab. After changing only files in `data/`, start it with **Run workflow** so the site picks up the change.

Settings live in `config/settings.json` (home location, radius, nearby Virginia cities and the Virginia time limit, county job boards) and `config/boards.json` (extra employer job boards for J.P.'s tab, optional; read fresh on every run).
