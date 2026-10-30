(() => {
  "use strict";

  const PAGE = 40;
  const state = {
    data: null,
    tab: "daniel",
    shown: PAGE,
    topics: new Set(),
    jpSegments: new Set(),
    briefs: new Map(),
  };

  const $ = (sel) => document.querySelector(sel);
  const esc = (value) =>
    String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const safeUrl = (url) => (/^https?:\/\//i.test(url || "") ? url : "#");

  // ---------- dates and money

  function todayISO() {
    return state.data?.today || new Date().toISOString().slice(0, 10);
  }
  function daysBetween(a, b) {
    return Math.round((Date.parse(b + "T00:00:00Z") - Date.parse(a + "T00:00:00Z")) / 86400000);
  }
  function closingBadge(closes) {
    if (!closes) return `<span class="badge">Open until filled</span>`;
    const left = daysBetween(todayISO(), closes);
    const label = left <= 0 ? "Closes today" : left === 1 ? "Closes tomorrow" : `Closes in ${left} days`;
    const cls = left <= 3 ? "bad" : left <= 7 ? "warn" : "";
    return `<span class="badge ${cls}" title="Closing date ${esc(closes)}">${label}</span>`;
  }
  function fmtMoney(n) {
    if (n == null) return "";
    return n >= 1000 ? "$" + Math.round(n).toLocaleString("en-US") : "$" + n.toFixed(2);
  }
  function pay(job) {
    if (job.salary_min == null && job.salary_max == null) return job.salary_text || "";
    const lo = fmtMoney(job.salary_min);
    const hi = fmtMoney(job.salary_max);
    const range = lo && hi && lo !== hi ? `${lo} – ${hi}` : lo || hi;
    return range + (job.salary_period === "hour" ? "/hr" : job.salary_period === "year" ? "/yr" : "");
  }
  function fmtDate(iso) {
    if (!iso) return "";
    return new Date(iso + "T12:00:00Z").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  }

  // ---------- data

  async function load() {
    try {
      const res = await fetch("data/jobs.json", { cache: "no-store" });
      if (!res.ok) throw new Error(res.status);
      state.data = await res.json();
    } catch (err) {
      $("#updated").textContent = "No data yet";
      $("#daniel-jobs").innerHTML = `<li class="empty">The first data refresh has not finished yet. Check back in a few minutes.</li>`;
      return;
    }
    const d = state.data;
    $("#updated").textContent = "Updated " + new Date(d.generated_at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
    if (d.ai && !d.ai.enabled && d.ai.note) $("#ai-note").textContent = d.ai.note;
    buildTopicChips();
    buildJpChips();
    renderDaniel();
    renderJp();
    renderSources();
    const hash = location.hash.replace("#", "");
    if (hash === "jp") selectTab("jp");
  }

  function danielJobs() {
    const d = state.data.daniel;
    const ai = (d.discovered || []).map((j) => ({ ...j, aiFound: true, open_to_public: true, distance_mi: null }));
    return d.jobs.concat(ai);
  }

  // ---------- Daniel tab

  function buildTopicChips() {
    const counts = new Map();
    for (const job of state.data.daniel.jobs) for (const t of job.match?.tags || []) counts.set(t, (counts.get(t) || 0) + 1);
    const order = [...counts.entries()].filter(([t]) => t !== "Other").sort((a, b) => b[1] - a[1]);
    $("#topics").innerHTML = order
      .map(([t, n]) => `<button class="chip" aria-pressed="false" data-topic="${esc(t)}">${esc(t)} <span aria-hidden="true">· ${n}</span></button>`)
      .join("");
  }

  function filteredDaniel() {
    const q = $("#q").value.trim().toLowerCase();
    const level = $("#level").value;
    const maxDist = Number($("#distance").value);
    const onlyPublic = $("#public").checked;
    const onlyBrief = $("#briefed").checked;
    let jobs = danielJobs().filter((j) => {
      if (level === "ai" ? !j.aiFound : level && j.level !== level) return false;
      if (onlyPublic && j.open_to_public === false) return false;
      if (onlyBrief && !(j.brief || j.aiFound)) return false;
      if (!j.remote && j.distance_mi != null && j.distance_mi > maxDist) return false;
      if (state.topics.size && !(j.match?.tags || []).some((t) => state.topics.has(t))) return false;
      if (q) {
        const hay = [j.title, j.org, j.department, j.location, j.summary, (j.categories || []).join(" "), (j.keywords_auto || []).join(" ")]
          .join(" ")
          .toLowerCase();
        if (!q.split(/\s+/).every((w) => hay.includes(w))) return false;
      }
      return true;
    });
    const sort = $("#sort").value;
    const by = {
      match: (a, b) => (b.match?.score || 0) - (a.match?.score || 0) || (a.closes || "9999").localeCompare(b.closes || "9999"),
      closing: (a, b) => (a.closes || "9999").localeCompare(b.closes || "9999"),
      new: (a, b) => (b.first_seen || b.found_on || "").localeCompare(a.first_seen || a.found_on || ""),
      pay: (a, b) => (b.salary_max || b.salary_min || 0) * (b.salary_period === "hour" ? 2080 : 1) - (a.salary_max || a.salary_min || 0) * (a.salary_period === "hour" ? 2080 : 1),
      near: (a, b) => (a.distance_mi ?? 999) - (b.distance_mi ?? 999),
    }[sort];
    return jobs.sort(by);
  }

  function renderDaniel() {
    const all = danielJobs();
    const jobs = filteredDaniel();
    const today = todayISO();
    const closingSoon = all.filter((j) => j.closes && daysBetween(today, j.closes) <= 7).length;
    const fresh = all.filter((j) => (j.first_seen || j.found_on) && daysBetween(j.first_seen || j.found_on, today) <= 1).length;
    const briefs = all.filter((j) => j.brief || j.aiFound).length;
    $("#daniel-stats").innerHTML = [
      [all.length, "open jobs"],
      [fresh, "new in last 2 days"],
      [closingSoon, "closing within 7 days"],
      [briefs, "with AI brief"],
    ]
      .map(([n, l]) => `<div class="stat"><b>${n}</b><span>${l}</span></div>`)
      .join("");
    $("#daniel-count").textContent = `${jobs.length} matching job${jobs.length === 1 ? "" : "s"}`;
    const list = $("#daniel-jobs");
    if (!jobs.length) {
      list.innerHTML = `<li class="empty">No jobs match these filters. Try widening the distance or clearing topics.</li>`;
      $("#daniel-more").hidden = true;
      return;
    }
    list.innerHTML = jobs.slice(0, state.shown).map(danielCard).join("");
    $("#daniel-more").hidden = jobs.length <= state.shown;
  }

  function scoreBox(score, label = "match") {
    const cls = score >= 70 ? "hi" : score >= 50 ? "mid" : "";
    return `<div class="score ${cls}" title="Heuristic fit score">${score ?? "–"}<small>${label}</small></div>`;
  }

  function danielCard(job) {
    const today = todayISO();
    const isNew = (job.first_seen || job.found_on) && daysBetween(job.first_seen || job.found_on, today) <= 1;
    const where = job.remote ? "Remote" : job.distance_mi != null ? `${job.location} · ${job.distance_mi} mi` : job.location;
    const badges = [
      isNew ? `<span class="badge new">New</span>` : "",
      job.aiFound ? `<span class="badge ok">Found by AI search</span>` : `<span class="badge">${esc(job.level)}</span>`,
      closingBadge(job.closes),
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
    const rows = (state.data.daniel.sources || []).map((s) => {
      const cls = s.status === "error" ? "bad" : s.status === "skipped" ? "warn" : "";
      const label = s.status === "ok" ? `${s.count}` : s.status === "skipped" ? "paused" : `${s.count} (stale)`;
      return `<li title="${esc(s.message)}"><span>${esc(s.name)}</span><span class="${cls}">${esc(label)}</span></li>`;
    });
    const ai = state.data.daniel.discovered || [];
    rows.push(`<li><span>AI web search</span><span>${ai.length}</span></li>`);
    $("#daniel-sources").innerHTML = rows.join("");
  }

  // ---------- J.P. tab

  function buildJpChips() {
    const counts = new Map();
    for (const job of state.data.jp.discovered || []) counts.set(job.level, (counts.get(job.level) || 0) + 1);
    $("#jp-segments").innerHTML = [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([t, n]) => `<button class="chip" aria-pressed="false" data-segment="${esc(t)}">${esc(t)} <span aria-hidden="true">· ${n}</span></button>`)
      .join("");
    const kws = ["cross-border investment", "strategic equity investment", "fund of funds", "private debt", "due diligence", "investment committee", "subsidiary oversight", "IFRS", "performance attribution", "securities lending", "Korean / English bilingual", "Bloomberg", "Capital IQ", "financial modeling"];
    $("#jp-keywords").innerHTML = kws.map((k) => `<span>${esc(k)}</span>`).join("");
  }

  function renderJp() {
    const jp = state.data.jp;
    const q = $("#jp-q").value.trim().toLowerCase();
    const jobs = (jp.discovered || [])
      .filter((j) => !state.jpSegments.size || state.jpSegments.has(j.level))
      .filter((j) => !q || [j.title, j.org, j.location, j.summary].join(" ").toLowerCase().includes(q))
      .sort((a, b) => (b.match?.score || 0) - (a.match?.score || 0));
    const all = jp.discovered || [];
    $("#jp-stats").innerHTML = [
      [all.length, "verified openings"],
      [all.filter((j) => daysBetween(j.found_on, todayISO()) <= 2).length, "found in last 3 days"],
      [jp.discovery_last_run ? fmtDate(jp.discovery_last_run) : "—", "last AI search"],
    ]
      .map(([n, l]) => `<div class="stat"><b>${esc(n)}</b><span>${l}</span></div>`)
      .join("");
    const list = $("#jp-jobs");
    if (!all.length) {
      list.innerHTML = `<li class="empty">The first AI search has not run yet. It runs every other day; results appear here with fit notes and verified links.</li>`;
      return;
    }
    list.innerHTML = jobs.length ? jobs.map(jpCard).join("") : `<li class="empty">No openings match this filter.</li>`;
  }

  function jpCard(job) {
    const badges = [
      `<span class="badge ok">${esc(job.level)}</span>`,
      closingBadge(job.closes),
      job.work_authorization ? `<span class="badge" title="${esc(job.work_authorization)}">Work authorization: ${esc(job.work_authorization.slice(0, 60))}${job.work_authorization.length > 60 ? "…" : ""}</span>` : "",
      job.verified_on ? `<span class="badge">Link checked ${esc(fmtDate(job.verified_on))}</span>` : `<span class="badge warn">Link not verified yet</span>`,
    ].join("");
    const meta = [job.location, job.salary_text].filter(Boolean).map((m) => `<span>${esc(m)}</span>`).join("");
    return `<li class="job">
      <div class="job-head">
        <div>
          <h3><a href="${esc(safeUrl(job.url))}" target="_blank" rel="noopener">${esc(job.title)}</a></h3>
          <div class="org">${esc(job.org)}</div>
        </div>
        ${scoreBox(job.match?.score, "fit")}
      </div>
      <div class="meta">${meta}</div>
      <div class="badges">${badges}</div>
      ${job.summary ? `<p class="summary">${esc(job.summary)}</p>` : ""}
      <div class="actions">
        <button class="btn primary" data-brief="${esc(job.id)}" data-tabref="jp">AI brief: strategy & keywords</button>
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
    const prompt = `Help ${profile} apply to this job. Read the posting, then give: eligibility checks, 10-15 resume keywords from the posting, a tailored application strategy, and likely interview questions.\n\nJob: ${job.title}\nEmployer: ${job.org}\nLocation: ${job.location || ""}\nCloses: ${job.closes || "not stated"}\nPosting: ${job.url}`;
    return "https://claude.ai/new?q=" + encodeURIComponent(prompt);
  }

  const list = (items) => (items && items.length ? `<ul>${items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : "<p>None noted.</p>");
  const kwBox = (items) => `<div class="kwbox">${(items || []).map((k) => `<span>${esc(k)}</span>`).join("")}</div>`;

  async function openBrief(id, tabRef) {
    const pool = tabRef === "jp" ? state.data.jp.discovered || [] : danielJobs();
    const job = pool.find((j) => j.id === id);
    if (!job) return;
    const who = tabRef === "jp" ? "jp" : "daniel";
    const body = $("#brief-body");
    const head = `<h2 id="brief-title">${esc(job.title)}</h2><div class="org">${esc(job.org)} · ${esc(job.location || "")}</div><div class="badges" style="margin-top:8px">${closingBadge(job.closes)}</div>`;
    const foot = `<div class="brief-foot">
        <a class="btn primary" href="${esc(safeUrl(job.apply_url || job.url))}" target="_blank" rel="noopener">Apply / view posting ↗</a>
        <a class="btn ai" href="${esc(askClaudeUrl(job, who))}" target="_blank" rel="noopener">Ask Claude a follow-up ↗</a>
        <button class="btn" data-copy>Copy keywords</button>
      </div>`;
    $("#brief").showModal();

    let keywords = [];
    if (job.aiFound || who === "jp") {
      const b = job.brief || {};
      keywords = b.keywords || [];
      body.innerHTML = `${head}
        <div class="fit"><b>Fit ${esc(job.match?.score ?? "")}/100</b><span>${esc(b.fit_summary || job.summary || "")}</span></div>
        ${job.work_authorization ? `<h3>Work authorization</h3><p>${esc(job.work_authorization)}</p>` : ""}
        <h3>Resume keywords</h3>${kwBox(keywords)}
        <h3>Application strategy</h3>${list(b.strategy)}
        <h3>Watch-outs</h3>${list(b.watch_outs)}
        ${b.evidence ? `<p class="note">Posting check: “${esc(b.evidence)}”. ${job.verified_on ? "Link re-checked " + esc(fmtDate(job.verified_on)) + "." : ""}</p>` : ""}
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
      }
      if (!b) {
        body.innerHTML = `${head}<p class="note">Could not load the brief. Try again after the next refresh.</p>${foot}`;
        return;
      }
      keywords = b.keywords || [];
      body.innerHTML = `${head}
        <p class="oneliner">${esc(b.one_liner)}</p>
        <div class="fit"><b>${esc(b.fit_rating)} fit</b><span>${esc(b.fit_summary)}</span></div>
        <h3>Check eligibility first</h3>${list(b.eligibility)}
        <h3>Resume keywords</h3>${kwBox(keywords)}
        <h3>Application strategy</h3>${list(b.strategy)}
        <h3>Resume bullets to adapt</h3><ul class="bullet-tpl">${(b.resume_bullets || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
        <h3>Likely interview questions</h3>${list(b.interview_questions)}
        <h3>Watch-outs</h3>${list(b.watch_outs)}
        <p class="note">Generated by ${esc(b.model)} on ${esc(fmtDate((b.generated_at || "").slice(0, 10)))} from the posting text. Verify details on the official announcement.</p>
        ${foot}`;
    } else {
      keywords = job.keywords_auto || [];
      body.innerHTML = `${head}
        <p class="oneliner">${esc(job.summary || "")}</p>
        <h3>Keywords spotted in this posting</h3>${keywords.length ? kwBox(keywords) : "<p>No standard keywords found in the listing text.</p>"}
        <p class="note">A full AI brief is generated automatically for the strongest matches (open to the public, good topic fit). For this one, use “Ask Claude” for an instant brief.</p>
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
  }

  document.addEventListener("click", (e) => {
    const tab = e.target.closest(".tab");
    if (tab) return selectTab(tab.dataset.tab);
    const brief = e.target.closest("[data-brief]");
    if (brief) return openBrief(brief.dataset.brief, brief.dataset.tabref);
    const chip = e.target.closest(".chip");
    if (chip) {
      const pressed = chip.getAttribute("aria-pressed") !== "true";
      chip.setAttribute("aria-pressed", String(pressed));
      if (chip.dataset.topic) {
        pressed ? state.topics.add(chip.dataset.topic) : state.topics.delete(chip.dataset.topic);
        state.shown = PAGE;
        renderDaniel();
      } else if (chip.dataset.segment) {
        pressed ? state.jpSegments.add(chip.dataset.segment) : state.jpSegments.delete(chip.dataset.segment);
        renderJp();
      }
    }
  });
  for (const id of ["#q", "#level", "#distance", "#sort", "#public", "#briefed"]) {
    $(id).addEventListener(id === "#q" ? "input" : "change", () => {
      state.shown = PAGE;
      if (state.data) renderDaniel();
    });
  }
  $("#jp-q").addEventListener("input", () => state.data && renderJp());
  $("#daniel-more").addEventListener("click", () => {
    state.shown += PAGE;
    renderDaniel();
  });
  $("#brief").addEventListener("click", (e) => {
    if (e.target === $("#brief")) $("#brief").close();
  });

  load();
})();
