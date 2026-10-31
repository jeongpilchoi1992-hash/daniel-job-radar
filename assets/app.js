(() => {
  "use strict";

  const PAGE_SIZES = [30, 50, 100];
  const state = {
    data: null,
    tab: "daniel",
    perPage: savedPerPage(),
    page: { daniel: 1, jp: 1 },
    pages: { daniel: 1, jp: 1 },
    topics: new Set(),
    jpSegments: new Set(),
    briefs: new Map(),
    daniel: [],
    jp: [],
  };

  // The page size this viewer picked last time, when the browser lets the site remember it.
  function savedPerPage() {
    try {
      const n = Number(localStorage.getItem("perPage"));
      return PAGE_SIZES.includes(n) ? n : PAGE_SIZES[0];
    } catch {
      return PAGE_SIZES[0];
    }
  }

  const $ = (sel) => document.querySelector(sel);
  const esc = (value) =>
    String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const safeUrl = (url) => (/^https?:\/\//i.test(url || "") ? url : "#");
  const num = (n) => Number(n || 0).toLocaleString("en-US");
  const words = (text) => text.trim().toLowerCase().split(/\s+/).filter(Boolean);

  // ---------- dates

  const HOME_TZ = "America/New_York";
  const REGION_TZ = { korea: "Asia/Seoul", hk: "Asia/Hong_Kong", sg: "Asia/Singapore" };
  const todays = new Map();

  // Today's date (YYYY-MM-DD) in a time zone. Daniel's jobs use Virginia's date and J.P.'s Seoul, Hong Kong and
  // Singapore roles their own, so "closes today" is right wherever the viewer is. It is worked out at most once
  // a minute, because one filter pass asks for it thousands of times.
  function todayISO(tz = HOME_TZ) {
    let entry = todays.get(tz);
    if (!entry) {
      let format = null;
      try {
        format = new Intl.DateTimeFormat("en-US", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit" });
      } catch {
        // An unknown time zone falls back to UTC below.
      }
      entry = { format, at: 0, value: "" };
      todays.set(tz, entry);
    }
    const now = Date.now();
    if (now - entry.at > 60000) {
      entry.at = now;
      if (entry.format) {
        const part = Object.fromEntries(entry.format.formatToParts(new Date(now)).map((p) => [p.type, p.value]));
        entry.value = `${part.year}-${part.month}-${part.day}`;
      } else {
        entry.value = new Date(now).toISOString().slice(0, 10);
      }
    }
    return entry.value;
  }
  const jobToday = (job) => todayISO(job._tz || HOME_TZ);
  const stillOpen = (job) => !job._window || job._window.to >= jobToday(job);

  // Dates arrive as YYYY-MM-DD, except the House feed's M/D/YYYY. Anything else, or a day that does not exist
  // ("2026-02-30"), counts as unknown.
  function isoDate(value) {
    const text = String(value || "");
    const us = /^(\d{1,2})\/(\d{1,2})\/(\d{4})/.exec(text);
    const iso = /^\d{4}-\d{2}-\d{2}/.test(text) ? text.slice(0, 10) : us ? `${us[3]}-${us[1].padStart(2, "0")}-${us[2].padStart(2, "0")}` : "";
    const time = iso ? Date.parse(iso + "T00:00:00Z") : NaN;
    return Number.isFinite(time) && new Date(time).toISOString().startsWith(iso) ? iso : "";
  }
  // "" when the result falls outside the dates a browser can hold.
  function addDays(iso, n) {
    const time = Date.parse(iso + "T00:00:00Z") + n * 86400000;
    return Number.isFinite(time) && Math.abs(time) <= 8.64e15 ? new Date(time).toISOString().slice(0, 10) : "";
  }
  function daysBetween(a, b) {
    return Math.round((Date.parse(b + "T00:00:00Z") - Date.parse(a + "T00:00:00Z")) / 86400000);
  }
  // Dates are calendar days, so they are printed in UTC; the viewer's own time zone must not shift them.
  const dayText = (iso, opts) => new Date(iso + "T12:00:00Z").toLocaleDateString("en-US", { ...opts, timeZone: "UTC" });
  const fmtDate = (iso) => (iso ? dayText(iso, { month: "short", day: "numeric", year: "numeric" }) : "");
  // "Nov 7 – 13, 2026", "Nov 28 – Dec 4, 2026" or "Dec 28, 2026 – Jan 3, 2027"
  function fmtRange(from, to) {
    if (from.slice(0, 4) !== to.slice(0, 4)) return `${fmtDate(from)} – ${fmtDate(to)}`;
    const start = dayText(from, { month: "short", day: "numeric" });
    const end = from.slice(0, 7) === to.slice(0, 7) ? dayText(to, { day: "numeric" }) : dayText(to, { month: "short", day: "numeric" });
    return `${start} – ${end}, ${to.slice(0, 4)}`;
  }

  // ---------- deadlines

  // County boards round deadlines down: "Closes in 1 week" means 7 to 13 days after the day the board was read,
  // and "1 month" 30 to 59 days. The collector stores the last possible day in `closes`, so a job is never
  // dropped early; the first possible day is worked out here, and the filters, sorting and warnings use it.
  const ROUNDED = { week: 6, month: 29, year: 364 };
  function closingWindow(job) {
    const to = isoDate(job.closes);
    if (!to) return null;
    const m = /closes\s+in\s+(?:an?|\d+)\s+(week|month|year)s?\b/i.exec(job.closes_text || "");
    return { from: (m && addDays(to, -ROUNDED[m[1].toLowerCase()])) || to, to };
  }

  // Every card shows its deadline on a line of its own; a posting without one is open until the employer fills it.
  function deadline(job) {
    const seen = isoDate(job.last_seen);
    const read = seen ? ` on ${fmtDate(seen)}` : "";
    const listed = job.closes_text ? ` title="${esc(`Listed as “${job.closes_text}”${read}`)}"` : "";
    const win = job._window;
    if (!win) return `<p class="due"${listed}><span>Deadline</span><b>Open until filled</b></p>`;
    const today = jobToday(job);
    const first = daysBetween(today, win.from);
    const last = daysBetween(today, win.to);
    const cls = first <= 3 ? "bad" : first <= 7 ? "warn" : "";
    const date = win.from === win.to ? fmtDate(win.to) : fmtRange(win.from, win.to);
    const when =
      last <= 0 ? "closes today"
      : win.from === win.to ? (last === 1 ? "closes tomorrow" : `${last} days left`)
      : first <= 0 ? `up to ${last} days left`
      : `${first}–${last} days left`;
    return `<p class="due ${cls}"${listed}><span>Deadline</span><b>${esc(date)}</b><em>${esc(when)}</em></p>`;
  }
  function deadlineMatch(job, rule) {
    if (!rule) return true;
    if (rule === "none") return !job._window;
    return !!job._window && daysBetween(jobToday(job), job._window.from) <= Number(rule);
  }
  const closeKey = (job) => (job._window ? job._window.from + job._window.to : "9999");

  // ---------- posting dates

  // Employer job boards only say "Posted 3 Days Ago", so count back from the day the board was last read.
  function postedFromText(job) {
    const m = /posted\s+(today|yesterday|(\d+)\+?\s+days?\s+ago)/i.exec(job.posted_text || "");
    const read = isoDate(job.last_seen || job.found_on);
    if (!m || !read) return "";
    return addDays(read, m[2] ? -Number(m[2]) : /yesterday/i.test(m[1]) ? -1 : 0);
  }

  // The first day this site read each source. A job first seen after that day is new; one seen on that day was
  // already listed, so the day it was first seen says nothing about when it was posted. The collector records
  // these days in `since`; older data falls back to the earliest day any listed job of the source was seen.
  function sourceStarts(data) {
    const starts = new Map();
    const note = (source, day) => {
      day = isoDate(day);
      if (source && day && (!starts.has(source) || day < starts.get(source))) starts.set(source, day);
    };
    for (const j of records(data.daniel.jobs)) note(j.source, j.first_seen);
    for (const j of [...records(data.daniel.discovered), ...records(data.jp.discovered), ...records(data.jp.board_jobs)]) note(j.source, j.found_on);
    const since = (v) => (v && typeof v === "object" && !Array.isArray(v) ? v : {});
    for (const [source, day] of Object.entries({ ...since(data.daniel.since), ...since(data.jp.since) })) note(source, day);
    return starts;
  }

  // The day a job was posted, or "" when nothing says: the source's own date, an employer board's "Posted 3
  // Days Ago", or the day this site first saw it when that came after the source was first read.
  function postedOn(job, starts) {
    const posted = isoDate(job.posted) || postedFromText(job);
    if (posted) return posted;
    const seen = isoDate(job.first_seen || job.found_on);
    const start = starts.get(job.source);
    return seen && start && seen > start ? seen : "";
  }
  const isNew = (job) => !!job._posted && daysBetween(job._posted, jobToday(job)) <= 1;
  // Newest first; jobs with no posting date go last, the most recently seen of them first.
  const newKey = (job) => (job._posted ? "1" + job._posted : "0" + job._seen);

  // ---------- pay

  const PERIOD_LABEL = { hour: "/hr", day: "/day", week: "/wk", biweek: " every 2 wks", month: "/mo", year: "/yr" };
  const PER_YEAR = { hour: 2080, day: 260, week: 52, biweek: 26, month: 12, year: 1 };
  function fmtMoney(n) {
    if (typeof n !== "number" || !Number.isFinite(n)) return "";
    return n >= 1000 ? "$" + Math.round(n).toLocaleString("en-US") : "$" + n.toFixed(2);
  }
  function pay(job) {
    if (job.salary_min == null && job.salary_max == null) return job.salary_text || "";
    const lo = fmtMoney(job.salary_min);
    const hi = fmtMoney(job.salary_max);
    const range = lo && hi && lo !== hi ? `${lo} – ${hi}` : lo || hi;
    return range + (PERIOD_LABEL[job.salary_period] || "");
  }

  // Pay written as text ("FT Hourly W BN - $46,160 - $80,780 Annually") is read like the collector's
  // salary_range(): the unit word after the amounts wins, then any unit word, then the size of the amounts.
  const AMOUNT = /\$\s?(\d[\d,]*(?:\.\d+)?)(\s*k\b)?/gi;
  const BARE_AMOUNT = /\b\d{2,3},\d{3}(?:\.\d+)?\b/g;
  const PERIOD_WORD =
    /(annual(?:ly)?|yearly|per (?:year|annum)|a year|\/\s*(?:yr|year)\b)|(hourly|per hour|an hour|\/\s*(?:hr|hour)\b)|(monthly|per month|a month|\/\s*mo(?:nth)?\b)|(bi-?weekly|per pay period)|(weekly|per week|a week|\/\s*wk\b)|(daily|per day|a day)/i;
  const PERIODS = ["year", "hour", "month", "biweek", "week", "day"];
  function periodIn(text) {
    const m = PERIOD_WORD.exec(text);
    return m ? PERIODS[m.slice(1).findIndex(Boolean)] : "";
  }
  // A year of pay at the top of the range, for sorting and the pay filter; 0 when the posting gives none.
  function yearlyPay(job) {
    if (job.salary_max || job.salary_min) return (job.salary_max || job.salary_min) * (PER_YEAR[job.salary_period] || 1);
    const text = String(job.salary_text ?? "");
    const amount = (digits, times, m) => ({ value: parseFloat(digits.replace(/,/g, "")) * times, end: m.index + m[0].length });
    let found = [...text.matchAll(AMOUNT)].map((m) => amount(m[1], m[2] ? 1000 : 1, m));
    if (!found.length) found = [...text.matchAll(BARE_AMOUNT)].map((m) => amount(m[0], 1, m));
    found = found.filter((f) => f.value > 0);
    if (!found.length) return 0;
    const top = Math.max(...found.map((f) => f.value));
    let period = periodIn(text.slice(found[found.length - 1].end)) || periodIn(text);
    if (period === "hour" && top >= 1000) period = "year";
    else if (["year", "month", "biweek", "week"].includes(period) && top <= 300) period = "hour";
    else if (!period) period = top >= 1000 ? "year" : top <= 300 ? "hour" : "";
    return period ? top * PER_YEAR[period] : 0;
  }

  // ---------- where J.P.'s roles are

  // Read from free-text locations such as "Seoul, Korea, Republic of", "USA, Washington DC" or "Jersey City New
  // Jersey United States". The DC and New York areas need a named place in the metro area (with its state, where
  // the name is common elsewhere); the rest of the U.S. needs a U.S. marker, a state name or a state code.
  // Upper-case codes are matched case-sensitively, and a role listed in two places ("Hong Kong / Singapore")
  // belongs to both.
  const DC_PLACES =
    "arlington|alexandria|fairfax|falls church|mclean|tysons|reston|herndon|chantilly|vienna|rosslyn|crystal city|centreville|manassas|ashburn|leesburg|sterling|dulles|springfield|bethesda|rockville|silver spring|chevy chase|college park|gaithersburg|germantown|bowie|largo|landover|hyattsville|greenbelt|potomac|national harbor|suitland";
  const NY_PLACES =
    "manhattan|brooklyn|queens|bronx|staten island|flushing|long island city|jersey city|hoboken|newark|weehawken|secaucus|teaneck|rutherford|fort lee|paramus|ridgefield park|englewood cliffs|palisades park|leonia|edgewater|hackensack|stamford|greenwich|white plains|purchase";
  // Places and regions abroad. A two-letter code does not make a location American when one of these is named:
  // other countries' states have codes too ("Chennai, TN, India", "Perth, WA, Australia"), and some state codes
  // are country codes ("Frankfurt, DE" is Germany, "Bangalore, IN" India). City names shared with sizeable U.S.
  // towns (Vancouver, Berlin, Hamburg, Malta, and Bogota without its accent) are left out.
  const ABROAD = [
    /\b(?:canada|qu[eé]bec|british columbia|alberta|manitoba|saskatchewan|nova scotia|toronto|montr[eé]al|calgary|mississauga|winnipeg|germany|deutschland|hessen?|bavaria|bayern|frankfurt|eschborn|munich|m[uü]nchen|d[uü]sseldorf|cologne|k[oö]ln|stuttgart|india|maharashtra|karnataka|tamil nadu|telangana|haryana|gujarat|kerala|uttar pradesh|west bengal|bangalore|bengaluru|mumbai|delhi|gurgaon|gurugram|hyderabad|chennai|pune|noida|kolkata|israel|tel[\s-]?aviv|jerusalem|haifa|herzliya|ramat gan|cayman|george town|maca[uo]|valletta|sliema|colombia|bogotá|medell[ií]n|indonesia|jakarta|argentina|buenos aires|australia|italy|italia|brazil|brasil|tbilisi|batumi)(?![a-z])/i,
    /,\s*(?:ontario|new brunswick|newfoundland|prince edward island)\s*,/i,
    /,\s*(?:ON|QC|BC|AB|MB|SK|NS|NB|NL|PE)\s*,/,
  ];
  const abroad = (where) => ABROAD.some((re) => re.test(where));
  const REGIONS = [
    ["korea", [/seoul|korea|incheon|songdo|busan|pangyo|yeouido|gangnam/i, /\bKR\b/]],
    ["hk", [/hong\s?kong|kowloon/i, /\bHK\b/]],
    ["sg", [/singapore/i]],
    ["dc", [/washington,?\s*d\.?\s?c\b|district of columbia/i, { test: (w) => /\bDC\b/.test(w) && !abroad(w) }, new RegExp(`\\b(?:${DC_PLACES})\\b[^/;]*\\b(?:VA|MD|Virginia|Maryland)\\b`, "i")]],
    [
      "ny",
      [
        // "New York" first; after a dash or a U.S. marker ("USA - New York", "US-NY-New York") only when no
        // other city follows it ("USA, New York, Albany").
        /^\s*new york\b|(?:[-–—]|\b(?:USA?|United States),?)\s*new york\b(?!\s*[-–—,]\s*(?!new york\b|ny\b|nyc\b|united states|usa?\b)[a-z])|new york,?\s+(?:NY|new york)\b|new york city|\bNYC\b/i,
        new RegExp(`\\b(?:${NY_PLACES})\\b[^/;]*\\b(?:NJ|NY|CT|New Jersey|New York|Connecticut)\\b`, "i"),
      ],
    ],
  ];
  const US_STATES =
    "alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|virginia|wisconsin|wyoming";
  const US_CODES = "AK|AL|AZ|CT|DC|FL|GA|HI|IA|KS|LA|MA|MD|ME|MI|MN|MS|NC|ND|NE|NH|NJ|NM|NV|NY|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VA|VT|WA|WI|WV|WY";
  // A U.S. marker or a state name counts on its own; a state code only when nothing abroad is named.
  const US_NAMED = [/united states|\bUSA\b|\bU\.S\.(?:A\.)?(?![A-Za-z])/i, /\bUS\b/, new RegExp(`\\b(?:${US_STATES})\\b`, "i")];
  const US_CODED = [
    new RegExp(`,\\s*(?:${US_CODES})\\b`),
    // These codes are also country codes, so they count only at the end of a location or before a ZIP code, a
    // bracket, a separator or "or" ("San Jose, CA 95134", "Hybrid (Denver, CO)", "Chicago, IL or Remote").
    /,\s*(?:AR|CA|CO|DE|ID|IL|IN|KY|MO|MT)\s*(?:\d{5}(?:-\d{4})?)?\s*(?:$|[()/;|,\-–—]|(?:or|and|&)\s)/,
    // The two state names left out above, after a city: "Atlanta, Georgia" and "Seattle, Washington", but not
    // "Washington, DC" or "Tbilisi, Georgia".
    /,\s*(?:georgia|washington)\b(?!\s*,?\s*d\.?\s?c\b)/i,
  ];
  const inUS = (where) => US_NAMED.some((re) => re.test(where)) || (US_CODED.some((re) => re.test(where)) && !abroad(where));
  // Each place in a list ("New York, NY / San Francisco, CA") is read on its own, so this one is in the New York
  // area and elsewhere in the U.S.; a location that names no known place is "other".
  function regionsOf(job) {
    const found = new Set();
    for (const part of String(job.location ?? "").split(/\s*[/;|]\s*/)) {
      const here = REGIONS.filter(([, tests]) => tests.some((re) => re.test(part))).map(([key]) => key);
      for (const key of here) found.add(key);
      if (!here.length && inUS(part)) found.add("us");
    }
    if (!found.size) found.add("other");
    return found;
  }

  // ---------- data

  async function load() {
    let data = null;
    try {
      const res = await fetch("data/jobs.json", { cache: "no-store" });
      if (!res.ok) throw new Error(res.status);
      data = await res.json();
    } catch (err) {
      // Only a missing or unreadable file means the first refresh has not run yet.
    }
    if (data && typeof data === "object") prepare(data);
    if (!data || typeof data !== "object" || (!state.daniel.length && !state.jp.length)) {
      state.data = null;
      $("#updated").textContent = "No data yet";
      $("#daniel-jobs").innerHTML = `<li class="empty">The first data refresh has not finished yet. Check back in a few minutes.</li>`;
      return;
    }
    state.data = data;
    const updated = new Date(data.generated_at);
    $("#updated").textContent = "";
    if (Number.isFinite(updated.getTime())) {
      $("#updated").textContent = "Updated " + updated.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
      if (Date.now() - updated.getTime() > 36 * 3600 * 1000) {
        $("#updated").textContent += " · the twice-daily refresh is behind, so some postings may have closed";
        $("#updated").classList.add("stale");
      }
    }
    // Each part is drawn on its own, so a problem in one cannot leave the others (or the #jp link) undone.
    if (location.hash.replace("#", "") === "jp") selectTab("jp");
    for (const draw of [buildTopicChips, buildJpChips, renderDaniel, renderJp, renderSources, writeAiNote]) {
      try {
        draw();
      } catch (err) {
        console.warn("Job Radar: part of the page could not be drawn", err);
      }
    }
  }
  function writeAiNote() {
    const d = state.data;
    const aiDate = [d.daniel.discovery_last_run, d.jp.discovery_last_run].map(isoDate).filter(Boolean).sort().pop();
    if (aiDate)
      $("#ai-note").textContent = `AI briefs and AI web searches were made once on ${fmtDate(aiDate)}; the twice-daily refresh uses free public sources only.`;
  }

  const LEGISLATIVE = /senate|house|congress|council|legislat|general assembly/i;

  // One odd record must not empty the page: lists that are not lists count as empty, entries that are not
  // objects are skipped, and a job whose fields cannot be read keeps plain defaults (no date, pay or deadline).
  const records = (value) => (Array.isArray(value) ? value.filter((j) => j && typeof j === "object") : []);
  const hay = (...parts) => parts.flat().map((p) => String(p ?? "")).join(" ").toLowerCase();
  const asText = (v) => (typeof v === "string" ? v : typeof v === "number" && Number.isFinite(v) ? String(v) : "");
  const asList = (v) => (Array.isArray(v) ? v.map(asText).filter(Boolean) : asText(v) ? [asText(v)] : []);
  const asNumber = (v) => (typeof v === "number" ? (Number.isFinite(v) ? v : null) : typeof v === "string" && v.trim() && Number.isFinite(+v) ? +v : null);
  const TEXT_FIELDS = ["id", "url", "apply_url", "title", "org", "department", "location", "summary", "level", "grade", "schedule",
    "clearance", "who_may_apply", "work_authorization", "employer_type", "salary_text", "salary_period", "closes_text", "posted_text"];
  function tidy(job) {
    for (const key of TEXT_FIELDS) if (job[key] != null) job[key] = asText(job[key]);
    for (const key of ["salary_min", "salary_max", "distance_mi"]) if (job[key] != null) job[key] = asNumber(job[key]);
    for (const key of ["categories", "keywords_auto"]) if (job[key] != null) job[key] = asList(job[key]);
    const match = job.match && typeof job.match === "object" ? job.match : {};
    job.match = { ...match, score: asNumber(match.score), tags: asList(match.tags) };
  }
  function annotate(job, read) {
    try {
      tidy(job);
      read(job);
    } catch (err) {
      console.warn("Job Radar: could not read a job", job.id || job.url, err);
      Object.assign(job, { _tz: HOME_TZ, _seen: "", _posted: "", _yearly: 0, _window: null, _hay: hay(job.title) });
      if (!job._regions) job._regions = new Set(["other"]);
    }
  }
  // Works out once, at load, what the filters and sorts need for every job: posting day, yearly pay, deadline
  // window and search text, plus regions and local time zone for J.P.'s roles.
  function prepare(data) {
    if (!data.daniel || typeof data.daniel !== "object") data.daniel = {};
    if (!data.jp || typeof data.jp !== "object") data.jp = {};
    const starts = sourceStarts(data);
    const ai = records(data.daniel.discovered).map((j) => ({
      ...j,
      aiFound: true,
      open_to_public: true,
      distance_mi: j.distance_mi ?? null,
      level: LEGISLATIVE.test(j.level || "") ? "Legislative" : j.level,
      match: { ...j.match, tags: Array.isArray(j.topics) ? j.topics : [] },
    }));
    state.daniel = records(data.daniel.jobs).concat(ai);
    for (const job of state.daniel)
      annotate(job, () => {
        job._tz = HOME_TZ;
        job._seen = isoDate(job.first_seen || job.found_on);
        job._posted = postedOn(job, starts);
        job._yearly = yearlyPay(job);
        job._window = closingWindow(job);
        job._hay = hay(job.title, job.org, job.department, job.location, job.summary, job.categories || [], job.keywords_auto || []);
      });
    const found = records(data.jp.discovered);
    const urls = new Set(found.map((j) => j.url));
    state.jp = found.concat(records(data.jp.board_jobs).filter((j) => !urls.has(j.url)));
    for (const job of state.jp)
      annotate(job, () => {
        job._regions = regionsOf(job);
        job._tz = REGION_TZ[[...job._regions].find((r) => REGION_TZ[r])] || HOME_TZ;
        job._seen = isoDate(job.first_seen || job.found_on);
        job._posted = postedOn(job, starts);
        job._yearly = 0;
        job._window = closingWindow(job);
        job._hay = hay(job.title, job.org, job.location, job.summary);
      });
  }
  const danielJobs = () => state.daniel.filter(stillOpen);
  const jpJobs = () => state.jp.filter(stillOpen);

  // Pay and posting date are checked last. A job that lists no pay (or no posting date) cannot be judged by that
  // filter, so it is left out and counted for the note on the count line.
  function payAndDate(job, minPay, postedDays, missing) {
    if (minPay && job._yearly && job._yearly < minPay) return false;
    if (postedDays && job._posted && daysBetween(job._posted, jobToday(job)) >= postedDays) return false;
    const noPay = minPay > 0 && !job._yearly;
    const noDate = postedDays > 0 && !job._posted;
    if (noPay && noDate) missing.both++;
    else if (noPay) missing.pay++;
    else if (noDate) missing.date++;
    return !noPay && !noDate;
  }
  const newMissing = () => ({ pay: 0, date: 0, both: 0 });
  const missingNote = (missing) =>
    (missing.pay ? ` · ${num(missing.pay)} more list no pay` : "") +
    (missing.date ? ` · ${num(missing.date)} more have no posting date` : "") +
    (missing.both ? ` · ${num(missing.both)} more list neither pay nor a posting date` : "");

  // ---------- Daniel tab

  function buildTopicChips() {
    const counts = new Map();
    for (const job of danielJobs()) for (const t of job.match?.tags || []) counts.set(t, (counts.get(t) || 0) + 1);
    const order = [...counts.entries()].filter(([t]) => t !== "Other").sort((a, b) => b[1] - a[1]);
    $("#topics").innerHTML = order
      .map(([t, n]) => `<button class="chip" aria-pressed="false" data-topic="${esc(t)}">${esc(t)} <span aria-hidden="true">· ${n}</span></button>`)
      .join("");
  }

  function filteredDaniel(all, missing) {
    const q = words($("#q").value);
    const level = $("#level").value;
    const maxDist = Number($("#distance").value);
    const minPay = Number($("#pay").value);
    const due = $("#deadline").value;
    const postedDays = Number($("#posted").value);
    const onlyPublic = $("#public").checked;
    const onlyTelework = $("#telework").checked;
    const onlyBrief = $("#briefed").checked;
    const jobs = all.filter((j) => {
      if (level === "ai" ? !j.aiFound : level && j.level !== level) return false;
      if (onlyPublic && j.open_to_public === false) return false;
      if (onlyTelework && !(j.remote || j.telework)) return false;
      if (onlyBrief && !(j.brief || j.aiFound)) return false;
      if (!j.remote && j.distance_mi != null && j.distance_mi > maxDist) return false;
      if (!deadlineMatch(j, due)) return false;
      if (state.topics.size && !(j.match?.tags || []).some((t) => state.topics.has(t))) return false;
      if (q.length && !q.every((w) => j._hay.includes(w))) return false;
      return payAndDate(j, minPay, postedDays, missing);
    });
    const by = {
      match: (a, b) => (b.match?.score || 0) - (a.match?.score || 0) || closeKey(a).localeCompare(closeKey(b)),
      closing: (a, b) => closeKey(a).localeCompare(closeKey(b)),
      new: (a, b) => newKey(b).localeCompare(newKey(a)),
      pay: (a, b) => b._yearly - a._yearly,
      near: (a, b) => (a.distance_mi ?? 999) - (b.distance_mi ?? 999),
    }[$("#sort").value];
    return jobs.sort(by);
  }

  function renderDaniel() {
    const all = danielJobs();
    const today = todayISO();
    $("#daniel-stats").innerHTML = [
      [all.length, "open jobs"],
      [all.filter(isNew).length, "new in last 2 days"],
      [all.filter((j) => j._window && daysBetween(today, j._window.from) <= 7).length, "closing within 7 days"],
      [all.filter((j) => j.brief || j.aiFound).length, "with AI brief"],
    ]
      .map(([n, l]) => `<div class="stat"><b>${num(n)}</b><span>${l}</span></div>`)
      .join("");
    const missing = newMissing();
    const shown = paginate("daniel", filteredDaniel(all, missing), "job", missingNote(missing));
    $("#daniel-jobs").innerHTML = shown.length
      ? shown.map(safely(danielCard)).join("")
      : `<li class="empty">No jobs match these filters. Try a wider distance or fewer topics, or <button class="reset" type="button" data-reset="daniel">reset the filters</button>.</li>`;
  }

  // ---------- pages

  const narrow = window.matchMedia("(max-width: 600px)");

  // Cuts a filtered list to the page being viewed, and writes its count line and page buttons.
  function paginate(tab, jobs, noun, note = "") {
    const pages = Math.max(1, Math.ceil(jobs.length / state.perPage));
    const page = (state.page[tab] = Math.min(Math.max(1, state.page[tab] || 1), pages));
    state.pages[tab] = pages;
    const start = (page - 1) * state.perPage;
    const shown = jobs.slice(start, start + state.perPage);
    $(`#${tab}-count`).textContent =
      (!jobs.length
        ? `No matching ${noun}s`
        : `${num(jobs.length)} matching ${noun}${jobs.length === 1 ? "" : "s"}` +
          (pages > 1 ? ` · showing ${num(start + 1)}–${num(start + shown.length)}` : "")) + note;
    $(`#${tab}-pager`).innerHTML = pagerHtml(tab, page, pages);
    return shown;
  }

  // Previous, the first and last pages, the pages either side of this one (two on wide screens, one on phones),
  // and next.
  function pagerHtml(tab, page, pages) {
    if (pages <= 1) return "";
    const reach = narrow.matches ? 1 : 2;
    const near = new Set([1, pages]);
    for (let p = page - reach; p <= page + reach; p++) if (p > 1 && p < pages) near.add(p);
    // A one-page gap shows that page instead of "…", unless its number has three digits and would not fit.
    for (const p of [...near]) if (near.has(p + 2) && !near.has(p + 1) && p + 1 < 100) near.add(p + 1);
    const items = [];
    let last = 0;
    for (const p of [...near].sort((a, b) => a - b)) {
      if (p - last > 1) items.push(`<span class="gap" aria-hidden="true">…</span>`);
      items.push(`<button class="page" type="button" data-pager="${tab}" data-page="${p}" aria-label="Page ${p}"${p === page ? ' aria-current="page"' : ""}>${p}</button>`);
      last = p;
    }
    // The words stay readable to screen readers on phones, where only the arrows show.
    const step = (p, word, off) =>
      `<button class="page step" type="button" data-pager="${tab}" data-page="${p}"${off ? " disabled" : ""}>` +
      (word === "Prev" ? `<span aria-hidden="true">‹</span><span class="step-word">Prev</span>` : `<span class="step-word">Next</span><span aria-hidden="true">›</span>`) +
      `</button>`;
    return step(page - 1, "Prev", page === 1) + items.join("") + step(page + 1, "Next", page === pages);
  }
  const redrawPagers = () => {
    if (!state.data) return;
    for (const tab of ["daniel", "jp"]) $(`#${tab}-pager`).innerHTML = pagerHtml(tab, state.page[tab], state.pages[tab]);
  };
  if (narrow.addEventListener) narrow.addEventListener("change", redrawPagers);

  // After a page change, jump back to the top of the list (just below the sticky bar) and put keyboard focus
  // there, the way a search results page does.
  function showListTop(tab) {
    const head = $(`#${tab}-top`);
    const bar = document.querySelector(".topbar");
    const barHeight = bar ? bar.offsetHeight : 0;
    const at = head.getBoundingClientRect().top;
    if (at < barHeight) window.scrollTo(0, at + window.scrollY - barHeight - 12);
    $(`#${tab}-count`).focus({ preventScroll: true });
  }

  function safely(draw) {
    return (job) => {
      try {
        return draw(job);
      } catch (err) {
        console.warn("Job Radar: could not draw a job", job.id || job.url, err);
        return `<li class="job"><div class="job-head"><div><h3><a href="${esc(safeUrl(job.url))}" target="_blank" rel="noopener">${esc(job.title || "Untitled job")}</a></h3></div></div></li>`;
      }
    };
  }

  function scoreBox(score, label = "match") {
    const cls = score >= 70 ? "hi" : score >= 50 ? "mid" : "";
    return `<div class="score ${cls}" title="Heuristic fit score">${score ?? "–"}<small>${label}</small></div>`;
  }

  function danielCard(job) {
    const where = job.remote ? "Remote" : job.distance_mi != null ? `${job.location} · ${job.distance_mi} mi` : job.location;
    const badges = [
      isNew(job) ? `<span class="badge new">New</span>` : "",
      job.aiFound ? `<span class="badge ok">Found by AI search</span>` : `<span class="badge">${esc(job.level)}</span>`,
      job.open_to_public === false ? `<span class="badge bad" title="${esc(job.who_may_apply)}">Not open to the public</span>` : "",
      job.telework ? `<span class="badge">Telework eligible</span>` : "",
      job.clearance ? `<span class="badge warn">Clearance: ${esc(job.clearance)}</span>` : "",
      ...(job.match?.tags || []).filter((t) => t !== "Other").map((t) => `<span class="badge">${esc(t)}</span>`),
    ].join("");
    const meta = [where, job.grade, pay(job), job.schedule].filter(Boolean).map((m) => `<span>${esc(m)}</span>`).join("");
    const hasBrief = job.brief || job.aiFound;
    return `<li class="job">
      <div class="job-head">
        <div>
          <h3><a href="${esc(safeUrl(job.url))}" target="_blank" rel="noopener">${esc(job.title)}</a></h3>
          <div class="org">${esc(job.org)}${job.department && job.department !== job.org ? " · " + esc(job.department) : ""}</div>
        </div>
        ${scoreBox(job.match?.score)}
      </div>
      ${deadline(job)}
      <div class="meta">${meta}</div>
      <div class="badges">${badges}</div>
      ${job.summary ? `<p class="summary">${esc(job.summary)}</p>` : ""}
      <div class="actions">
        <button class="btn ${hasBrief ? "primary" : "ai"}" data-brief="${esc(job.id)}">${hasBrief ? "AI brief: strategy & keywords" : "Quick keywords + ask Claude"}</button>
        <a class="btn" href="${esc(safeUrl(job.apply_url || job.url))}" target="_blank" rel="noopener">Apply / view posting ↗</a>
      </div>
    </li>`;
  }

  function renderSources() {
    const rows = records(state.data.daniel.sources).map((s) => {
      const cls = s.status === "error" ? "bad" : s.status === "skipped" || s.status === "partial" ? "warn" : "";
      const label =
        s.status === "ok" ? `${s.count}`
        : s.status === "skipped" ? "paused"
        : s.status === "partial" ? `${s.count} (partly updated)`
        : s.count ? `${s.count} (from earlier run)`
        : "unavailable";
      return `<li title="${esc(s.message)}"><span>${esc(s.name)}</span><span class="${cls}">${esc(label)}</span></li>`;
    });
    const ai = records(state.data.daniel.discovered);
    rows.push(`<li><span>AI web search</span><span>${ai.length}</span></li>`);
    $("#daniel-sources").innerHTML = rows.join("");
  }

  // ---------- J.P. tab

  function buildJpChips() {
    const counts = new Map();
    const regions = new Map();
    for (const job of jpJobs()) {
      counts.set(job.level, (counts.get(job.level) || 0) + 1);
      for (const r of job._regions) regions.set(r, (regions.get(r) || 0) + 1);
    }
    $("#jp-segments").innerHTML = [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([t, n]) => `<button class="chip" aria-pressed="false" data-segment="${esc(t)}">${esc(t)} <span aria-hidden="true">· ${n}</span></button>`)
      .join("");
    for (const opt of $("#jp-region").options) {
      if (!opt.value) continue;
      opt.dataset.label = opt.dataset.label || opt.textContent;
      opt.textContent = `${opt.dataset.label} (${regions.get(opt.value) || 0})`;
      opt.disabled = !regions.get(opt.value) && !opt.selected;
    }
    const kws = ["cross-border investment", "strategic equity investment", "fund of funds", "private debt", "due diligence", "investment committee", "subsidiary oversight", "IFRS", "performance attribution", "securities lending", "Korean / English bilingual", "Bloomberg", "Capital IQ", "financial modeling"];
    $("#jp-keywords").innerHTML = kws.map((k) => `<span>${esc(k)}</span>`).join("");
  }

  function filteredJp(all, missing) {
    const q = words($("#jp-q").value);
    const region = $("#jp-region").value;
    const source = $("#jp-source").value;
    const due = $("#jp-deadline").value;
    const postedDays = Number($("#jp-posted").value);
    const jobs = all.filter((j) => {
      if (state.jpSegments.size && !state.jpSegments.has(j.level)) return false;
      if (region && !j._regions.has(region)) return false;
      if ((source === "ai" && j.from_board) || (source === "board" && !j.from_board)) return false;
      if (!deadlineMatch(j, due)) return false;
      if (q.length && !q.every((w) => j._hay.includes(w))) return false;
      return payAndDate(j, 0, postedDays, missing);
    });
    const by = {
      // AI-checked picks (scored for interview odds) first, then board roles (scored by keywords).
      match: (a, b) => !!a.from_board - !!b.from_board || (b.match?.score || 0) - (a.match?.score || 0),
      new: (a, b) => newKey(b).localeCompare(newKey(a)),
      closing: (a, b) => closeKey(a).localeCompare(closeKey(b)),
    }[$("#jp-sort").value];
    return jobs.sort(by);
  }

  function renderJp() {
    const jp = state.data.jp;
    const all = jpJobs();
    $("#jp-stats").innerHTML = [
      [all.length, "open roles"],
      [all.filter((j) => j._posted && daysBetween(j._posted, jobToday(j)) <= 2).length, "new in last 3 days"],
      [jp.boards || 0, "employer job boards checked daily"],
    ]
      .map(([n, l]) => `<div class="stat"><b>${num(n)}</b><span>${l}</span></div>`)
      .join("");
    const list = $("#jp-jobs");
    if (!all.length) {
      $("#jp-count").textContent = "";
      $("#jp-pager").innerHTML = "";
      list.innerHTML = `<li class="empty">No openings yet. Results appear here after the first data refresh.</li>`;
      return;
    }
    const missing = newMissing();
    const shown = paginate("jp", filteredJp(all, missing), "opening", missingNote(missing));
    list.innerHTML = shown.length
      ? shown.map(safely(jpCard)).join("")
      : `<li class="empty">No openings match these filters. Try another region, or <button class="reset" type="button" data-reset="jp">reset the filters</button>.</li>`;
  }

  function jpCard(job) {
    const badges = [
      isNew(job) ? `<span class="badge new">New</span>` : "",
      `<span class="badge ${job.from_board ? "" : "ok"}">${esc(job.level)}</span>`,
      job.work_authorization ? `<span class="badge" title="${esc(job.work_authorization)}">Work authorization: ${esc(job.work_authorization.slice(0, 60))}${job.work_authorization.length > 60 ? "…" : ""}</span>` : "",
      job.from_board ? "" : isoDate(job.verified_on) ? `<span class="badge">Link checked ${esc(fmtDate(isoDate(job.verified_on)))}</span>` : `<span class="badge warn">Link not verified yet</span>`,
    ].join("");
    const meta = [job.location, job.employer_type, job.salary_text].filter(Boolean).map((m) => `<span>${esc(m)}</span>`).join("");
    return `<li class="job">
      <div class="job-head">
        <div>
          <h3><a href="${esc(safeUrl(job.url))}" target="_blank" rel="noopener">${esc(job.title)}</a></h3>
          <div class="org">${esc(job.org)}</div>
        </div>
        ${job.from_board ? scoreBox(job.match?.score, "keywords") : scoreBox(job.match?.score, "fit")}
      </div>
      ${deadline(job)}
      <div class="meta">${meta}</div>
      <div class="badges">${badges}</div>
      ${job.summary ? `<p class="summary">${esc(job.summary)}</p>` : ""}
      <div class="actions">
        <button class="btn ${job.from_board ? "ai" : "primary"}" data-brief="${esc(job.id)}" data-tabref="jp">${job.from_board ? "Quick look + ask Claude" : "AI brief: strategy & keywords"}</button>
        <a class="btn" href="${esc(safeUrl(job.url))}" target="_blank" rel="noopener">Apply / view posting ↗</a>
      </div>
    </li>`;
  }

  // ---------- Brief dialog

  function askClaudeUrl(job, who) {
    const profile =
      who === "jp"
        ? "J.P., a Korean national with 6+ years in capital markets (cross-border investments, fund of funds, subsidiary oversight; passed Level II of the CFA Program)"
        : "Daniel, who lives in Manassas VA, recently worked at an emergency-management consulting firm (IEM), knows U.S. politics very well, and wants a government job";
    const win = job._window;
    const closes = !win ? "not stated" : win.from === win.to ? win.to : `between ${win.from} and ${win.to}`;
    const prompt = `Help ${profile} apply to this job. Read the posting, then give: eligibility checks, 10-15 resume keywords from the posting, a tailored application strategy, and likely interview questions.\n\nJob: ${job.title}\nEmployer: ${job.org}\nLocation: ${job.location || ""}\nCloses: ${closes}\nPosting: ${job.url}`;
    return "https://claude.ai/new?q=" + encodeURIComponent(prompt);
  }

  const list = (items) => (asList(items).length ? `<ul>${asList(items).map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : "<p>None noted.</p>");
  const kwBox = (items) => `<div class="kwbox">${asList(items).map((k) => `<span>${esc(k)}</span>`).join("")}</div>`;

  async function openBrief(id, tabRef) {
    const pool = tabRef === "jp" ? jpJobs() : danielJobs();
    const job = pool.find((j) => j.id === id);
    if (!job) return;
    const who = tabRef === "jp" ? "jp" : "daniel";
    const body = $("#brief-body");
    const head = `<h2 id="brief-title">${esc(job.title)}</h2><div class="org">${esc(job.org)} · ${esc(job.location || "")}</div>${deadline(job)}`;
    const footer = (kws) => `<div class="brief-foot">
        <a class="btn primary" href="${esc(safeUrl(job.apply_url || job.url))}" target="_blank" rel="noopener">Apply / view posting ↗</a>
        <a class="btn ai" href="${esc(askClaudeUrl(job, who))}" target="_blank" rel="noopener">Ask Claude a follow-up ↗</a>
        ${kws.length ? `<button class="btn" data-copy>Copy keywords</button>` : ""}
      </div>`;
    // A brief that finishes loading after the reader moved on must not replace the newer one.
    const seq = (state.briefSeq = (state.briefSeq || 0) + 1);
    state.briefOpenedAt = Date.now();
    if (!$("#brief").open) $("#brief").showModal();

    let keywords = [];
    if (job.aiFound || (who === "jp" && !job.from_board)) {
      const b = job.brief || {};
      keywords = asList(b.keywords);
      const foot = footer(keywords);
      body.innerHTML = `${head}
        <div class="fit"><b>Fit ${esc(job.match?.score ?? "")}/100</b><span>${esc(b.fit_summary || job.summary || "")}</span></div>
        ${job.work_authorization ? `<h3>Work authorization</h3><p>${esc(job.work_authorization)}</p>` : ""}
        <h3>Resume keywords</h3>${kwBox(keywords)}
        <h3>Application strategy</h3>${list(b.strategy)}
        <h3>Watch-outs</h3>${list(b.watch_outs)}
        ${b.evidence ? `<p class="note">Posting check: “${esc(b.evidence)}”. ${isoDate(job.verified_on) ? "Link re-checked " + esc(fmtDate(isoDate(job.verified_on))) + "." : ""}</p>` : ""}
        ${foot}`;
    } else if (job.brief) {
      body.innerHTML = `${head}<p class="note">Loading AI brief…</p>`;
      let b = state.briefs.get(job.brief);
      if (!b) {
        try {
          const res = await fetch(`data/briefs/${encodeURIComponent(job.brief)}.json`, { cache: "no-store" });
          b = await res.json();
          state.briefs.set(job.brief, b);
        } catch {
          b = null;
        }
        if (seq !== state.briefSeq || !$("#brief").open) return;
      }
      if (!b) {
        body.innerHTML = `${head}<p class="note">Could not load the brief. Try again after the next refresh.</p>${footer([])}`;
        return;
      }
      keywords = asList(b.keywords);
      const foot = footer(keywords);
      body.innerHTML = `${head}
        <p class="oneliner">${esc(b.one_liner)}</p>
        <div class="fit"><b>${esc(b.fit_rating)} fit</b><span>${esc(b.fit_summary)}</span></div>
        <h3>Check eligibility first</h3>${list(b.eligibility)}
        <h3>Resume keywords</h3>${kwBox(keywords)}
        <h3>Application strategy</h3>${list(b.strategy)}
        <h3>Resume bullets to adapt</h3><ul class="bullet-tpl">${asList(b.resume_bullets).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
        <h3>Likely interview questions</h3>${list(b.interview_questions)}
        <h3>Watch-outs</h3>${list(b.watch_outs)}
        <p class="note">Generated by ${esc(b.model)} on ${esc(fmtDate(isoDate(b.generated_at)))} from the posting text. Verify details on the official announcement.</p>
        ${foot}`;
    } else {
      keywords = asList(job.keywords_auto);
      const foot = footer(keywords);
      const note = job.from_board
        ? `This role was picked up from ${esc(job.org || "the employer")}'s own job board, which is checked every day. “Ask Claude a follow-up” opens Claude with the posting ready for a tailored brief.`
        : "Pre-written AI briefs cover the strongest matches from the launch-day AI run. For this job, “Ask Claude a follow-up” opens Claude with the posting ready for an instant brief.";
      body.innerHTML = `${head}
        <p class="oneliner">${esc(job.summary || "")}</p>
        ${keywords.length || !job.from_board ? `<h3>Keywords spotted in this posting</h3>${keywords.length ? kwBox(keywords) : "<p>No standard keywords found in the listing text.</p>"}` : ""}
        <p class="note">${note}</p>
        ${foot}`;
    }
    const copy = body.querySelector("[data-copy]");
    if (copy)
      copy.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(keywords.join(", "));
          copy.textContent = "Copied ✓";
        } catch {
          copy.textContent = "Copy failed";
        }
      });
  }

  // ---------- tabs and events

  function selectTab(tab) {
    state.tab = tab;
    for (const btn of document.querySelectorAll(".tab")) btn.setAttribute("aria-selected", String(btn.dataset.tab === tab));
    $("#panel-daniel").hidden = tab !== "daniel";
    $("#panel-jp").hidden = tab !== "jp";
    history.replaceState(null, "", tab === "jp" ? "#jp" : "#");
    // A Ctrl- or middle-click on "Job Radar" then opens the same tab.
    $("#brand").setAttribute("href", tab === "jp" ? "./#jp" : "./");
  }

  const RENDER = { daniel: () => renderDaniel(), jp: () => renderJp() };

  // Puts a tab's filters back to how the page first loads (the defaults are the HTML's own checked and
  // selected values) and clears its chips.
  function resetControls(tab) {
    const box = $(`#${tab}-filters`);
    for (const el of box.querySelectorAll("input, select")) {
      if (el.type === "checkbox") el.checked = el.defaultChecked;
      else if (el.tagName === "SELECT") el.selectedIndex = Math.max(0, [...el.options].findIndex((o) => o.defaultSelected));
      else el.value = "";
    }
    for (const chip of box.querySelectorAll(".chip")) chip.setAttribute("aria-pressed", "false");
    (tab === "jp" ? state.jpSegments : state.topics).clear();
    state.page[tab] = 1;
  }

  document.addEventListener("click", (e) => {
    const tab = e.target.closest(".tab");
    if (tab) return selectTab(tab.dataset.tab);
    const brief = e.target.closest("[data-brief]");
    if (brief) return openBrief(brief.dataset.brief, brief.dataset.tabref);
    const pager = e.target.closest("[data-pager]");
    if (pager && state.data) {
      const which = pager.dataset.pager;
      const page = Number(pager.dataset.page);
      if (page === state.page[which]) return;
      state.page[which] = page;
      RENDER[which]();
      return showListTop(which);
    }
    const reset = e.target.closest("[data-reset]");
    if (reset && state.data) {
      const which = reset.dataset.reset;
      const inList = !!reset.closest(".empty");
      resetControls(which);
      RENDER[which]();
      // The button inside an empty list is gone after the redraw, so keep keyboard focus on the count line.
      if (inList) $(`#${which}-count`).focus();
      return;
    }
    const chip = e.target.closest(".chip");
    if (chip && state.data) {
      const pressed = chip.getAttribute("aria-pressed") !== "true";
      chip.setAttribute("aria-pressed", String(pressed));
      if (chip.dataset.topic) {
        pressed ? state.topics.add(chip.dataset.topic) : state.topics.delete(chip.dataset.topic);
        state.page.daniel = 1;
        renderDaniel();
      } else if (chip.dataset.segment) {
        pressed ? state.jpSegments.add(chip.dataset.segment) : state.jpSegments.delete(chip.dataset.segment);
        state.page.jp = 1;
        renderJp();
      }
    }
  });

  // Any filter change starts the list again from page 1. The search boxes wait for a pause in typing.
  for (const tab of ["daniel", "jp"]) {
    let typing = 0;
    for (const el of $(`#${tab}-filters`).querySelectorAll("input, select")) {
      const update = () => {
        state.page[tab] = 1;
        if (state.data) RENDER[tab]();
      };
      if (el.type === "search")
        el.addEventListener("input", () => {
          clearTimeout(typing);
          typing = setTimeout(update, 150);
        });
      else el.addEventListener("change", update);
    }
  }

  // Both tabs share one page size; switching it keeps the first job on screen within the new page.
  for (const sel of document.querySelectorAll("[data-per-page]")) {
    sel.value = String(state.perPage);
    sel.addEventListener("change", () => {
      const before = state.perPage;
      state.perPage = Number(sel.value);
      for (const other of document.querySelectorAll("[data-per-page]")) other.value = sel.value;
      for (const t of ["daniel", "jp"]) state.page[t] = Math.floor(((state.page[t] - 1) * before) / state.perPage) + 1;
      try {
        localStorage.setItem("perPage", sel.value);
      } catch {
        // Private windows can refuse storage; the choice then lasts until the page is closed.
      }
      if (state.data) {
        renderDaniel();
        renderJp();
      }
    });
  }

  // "Job Radar" reloads the page (keeping the open tab) so the newest refresh shows. A Ctrl- or Cmd-click still
  // opens it in a new tab.
  $("#brand").addEventListener("click", (e) => {
    if (e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    location.reload();
  });

  // Close on a backdrop click, but not on the second click of a double-click that opened it, or when a text
  // selection that started inside the dialog ends outside it.
  let downOnBackdrop = false;
  $("#brief").addEventListener("pointerdown", (e) => {
    downOnBackdrop = e.target === $("#brief");
  });
  $("#brief").addEventListener("click", (e) => {
    if (e.target === $("#brief") && downOnBackdrop && Date.now() - (state.briefOpenedAt || 0) > 400) $("#brief").close();
  });

  // A reload starts at the top with every filter cleared, even in browsers that would put back the old scroll
  // position (before the list has loaded, so it lands somewhere random) or the old filter values.
  if ("scrollRestoration" in history) history.scrollRestoration = "manual";
  resetControls("daniel");
  resetControls("jp");
  load();
})();
