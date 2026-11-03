// Builds Daniel's improved resume and the notes that go with it from content.js:
//   assets/resume/Daniel_Marfurt-Levy_Resume_2026.docx      the improved resume (contact placeholders)
//   assets/resume/Daniel_Resume_Notes_and_Tips.docx         what changed, what to confirm, what to add
//   index.html                                              the "Resume & tips" page, between its markers
//
// Run from the repository root:  NODE_PATH=$(npm root -g) node tools/resume/build.js   (needs the docx package)
// A private copy with real contact details can be written outside the repository:
//   RESUME_CONTACT="City, ST ZIP|phone|email" RESUME_OUT=/path/outside/the/repo/file.docx node tools/resume/build.js

const fs = require("fs");
const path = require("path");
const {
  AlignmentType, BorderStyle, Document, Footer, LevelFormat, Packer, PageNumber, Paragraph, ShadingType, Table, TableCell,
  TableRow, TabStopType, TextRun, WidthType,
} = require("docx");
const { resume, changes, checks, tips } = require("./content");

const ROOT = path.resolve(__dirname, "../..");
const FONT = "Calibri";
const NAVY = "1F3D7A";
const MARGIN = 820; // DXA (about 0.57 in)
const WIDTH = 12240 - 2 * MARGIN; // text width on US Letter
const SIZE = 20; // half-points (10 pt)

// ---------------------------------------------------------------- text helpers

const isHl = (part) => part && typeof part === "object" && "hl" in part;
const plain = (parts) => (Array.isArray(parts) ? parts : [parts]).map((p) => (isHl(p) ? p.hl : p)).join("");
function runs(parts, opts = {}) {
  return (Array.isArray(parts) ? parts : [parts]).map((part) =>
    new TextRun({ text: isHl(part) ? part.hl : part, font: FONT, size: SIZE, ...opts, ...(isHl(part) ? { highlight: "yellow" } : {}) }));
}
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const html = (parts) => (Array.isArray(parts) ? parts : [parts]).map((p) => (isHl(p) ? `<mark>${esc(p.hl)}</mark>` : esc(p))).join("");

// ---------------------------------------------------------------- resume (Word)

function heading(text) {
  return new Paragraph({
    spacing: { before: 150, after: 60 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: NAVY, space: 1 } },
    children: [new TextRun({ text: text.toUpperCase(), font: FONT, size: 21, bold: true, color: NAVY, characterSpacing: 20 })],
  });
}
const bullet = (parts) => new Paragraph({ numbering: { reference: "dot", level: 0 }, spacing: { after: 30 }, children: runs(parts) });
// Bold left text with a right-aligned date on the same line.
function roleLine(left, right, before = 110) {
  return new Paragraph({
    spacing: { before, after: 20 },
    tabStops: [{ type: TabStopType.RIGHT, position: WIDTH }],
    keepNext: true,
    children: [...runs(left, { bold: true }), new TextRun({ text: "\t", font: FONT, size: SIZE }), ...runs(right)],
  });
}

function resumeDoc(contact) {
  const r = resume;
  const body = [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 20 },
      children: [new TextRun({ text: r.name.toUpperCase(), font: FONT, size: 36, bold: true, color: NAVY, characterSpacing: 30 })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 30 },
      children: contact.flatMap((part, i) => [...(i ? [new TextRun({ text: "  |  ", font: FONT, size: SIZE, color: "666666" })] : []), ...runs(part)]) }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 },
      children: [new TextRun({ text: r.headline, font: FONT, size: 19, bold: true, color: "444444" })] }),
    heading("Professional summary"),
    new Paragraph({ spacing: { after: 40 }, children: runs(r.summary) }),
    heading("Core skills"),
    ...r.skills.map(([label, text]) => new Paragraph({ spacing: { after: 20 },
      children: [new TextRun({ text: `${label}: `, font: FONT, size: SIZE, bold: true }), ...runs(text)] })),
    heading("Experience"),
  ];
  r.experience.forEach((job, n) => {
    body.push(roleLine(job.title ? [`${job.title}  |  `, job.org] : job.org.toUpperCase(), job.dates, n ? 140 : 60));
    if (job.titles) body.push(new Paragraph({ spacing: { after: 30 }, children: runs(job.titles, { italics: true, color: "333333" }) }));
    for (const group of job.groups || []) {
      body.push(new Paragraph({ spacing: { before: 70, after: 20 }, keepNext: true,
        children: [new TextRun({ text: group.heading, font: FONT, size: SIZE, bold: true, color: NAVY })] }));
      body.push(...group.bullets.map(bullet));
    }
    body.push(...(job.bullets || []).map(bullet));
  });
  const s = r.service;
  body.push(heading("Community service"));
  body.push(roleLine([`${s.title}  |  ${s.org}, `, s.where], [s.dates], 40));
  body.push(...s.bullets.map(bullet));
  body.push(heading("Education"));
  r.education.forEach((e, i) => {
    body.push(roleLine([...(Array.isArray(e.degree) ? e.degree : [e.degree]), "  |  ", e.school], [e.date], i ? 60 : 40));
    if (e.note) body.push(new Paragraph({ spacing: { after: 20 }, children: runs(e.note, { size: 19 }) }));
  });
  body.push(heading("Certifications and training"));
  body.push(...r.certifications.map(bullet));

  return new Document({
    creator: "Job Radar",
    title: `${r.name} – Resume 2026`,
    styles: { default: { document: { run: { font: FONT, size: SIZE } } } },
    numbering: { config: [{ reference: "dot", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 300, hanging: 200 } } } }] }] },
    sections: [{
      properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 700, bottom: 700, left: MARGIN, right: MARGIN } } },
      footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
        children: [`${r.name}  ·  page `, PageNumber.CURRENT, " of ", PageNumber.TOTAL_PAGES].map((part) =>
          new TextRun({ children: [part], font: FONT, size: 16, color: "777777" })) })] }) },
      children: body,
    }],
  });
}

// ---------------------------------------------------------------- notes (Word)

function notesDoc() {
  const h1 = (t) => new Paragraph({ spacing: { after: 80 }, children: [new TextRun({ text: t, font: FONT, size: 34, bold: true, color: NAVY })] });
  const h2 = (t) => new Paragraph({ spacing: { before: 260, after: 80 }, keepNext: true,
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: NAVY, space: 1 } },
    children: [new TextRun({ text: t, font: FONT, size: 24, bold: true, color: NAVY })] });
  const p = (parts, opts) => new Paragraph({ spacing: { after: 80 }, children: runs(parts, { size: 21, ...opts }) });
  const item = (parts) => new Paragraph({ numbering: { reference: "dot", level: 0 }, spacing: { after: 50 }, children: runs(parts, { size: 21 }) });
  const cellBorder = { style: BorderStyle.SINGLE, size: 4, color: "C8CEDB" };
  const borders = { top: cellBorder, bottom: cellBorder, left: cellBorder, right: cellBorder };
  const col = [Math.round(WIDTH * 0.46), WIDTH - Math.round(WIDTH * 0.46)];
  const cell = (text, w, head) => new TableCell({
    width: { size: w, type: WidthType.DXA }, borders, margins: { top: 60, bottom: 60, left: 100, right: 100 },
    shading: head ? { type: ShadingType.CLEAR, color: "auto", fill: "E6EDFF" } : undefined,
    children: [new Paragraph({ children: runs(text, { size: 19, bold: !!head }) })],
  });
  const table = new Table({
    width: { size: WIDTH, type: WidthType.DXA }, columnWidths: col,
    rows: [new TableRow({ tableHeader: true, children: [cell("Before (PDF)", col[0], true), cell("After (improved Word file)", col[1], true)] }),
      ...changes.map(([was, now]) => new TableRow({ children: [cell(was, col[0]), cell(now, col[1])] }))],
  });
  const body = [
    h1("Resume notes for Daniel"),
    p("These notes go with the improved resume (Daniel_Marfurt-Levy_Resume_2026.docx). Yellow highlights in that file mark placeholders and facts to confirm. Everything else came from the 2026 PDF, reworded and reorganized.", { color: "444444" }),
    h2("1. Check these before sending"),
    ...checks.map(([title, text]) => item([{ hl: title }, ` ${text}`])),
    h2("2. What changed"),
    table,
    new Paragraph({ pageBreakBefore: true, children: [] }),
    h2("3. What would make it stronger"),
  ];
  for (const group of tips) {
    body.push(new Paragraph({ spacing: { before: 140, after: 60 }, keepNext: true, children: [new TextRun({ text: group.heading, font: FONT, size: 22, bold: true })] }));
    body.push(...group.items.map(item));
  }
  body.push(p("The Job Radar site matches every job against this resume and shows, for each one, which resume lines to lead with and which gaps to close first.", { color: "444444", italics: true }));
  return new Document({
    creator: "Job Radar",
    title: "Resume notes for Daniel",
    styles: { default: { document: { run: { font: FONT, size: 21 } } } },
    numbering: { config: [{ reference: "dot", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 360, hanging: 240 } } } }] }] },
    sections: [{ properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1000, bottom: 1000, left: MARGIN, right: MARGIN } } }, children: body }],
  });
}

// ---------------------------------------------------------------- the site's "Resume & tips" page

function resumeHtml() {
  const r = resume;
  const role = (left, right) => `<p class="role"><span>${html(left)}</span><span>${html(right)}</span></p>`;
  const ul = (items) => `<ul>${items.map((b) => `<li>${html(b)}</li>`).join("")}</ul>`;
  const jobs = r.experience.map((job) => [
    role(job.title ? [`${job.title} | `, job.org] : job.org, job.dates),
    job.titles ? `<p class="sub">${html(job.titles)}</p>` : "",
    ...(job.groups || []).map((g) => `<h6>${esc(g.heading)}</h6>${ul(g.bullets)}`),
    job.bullets ? ul(job.bullets) : "",
  ].join("")).join("");
  const s = r.service;
  const paper = `<div class="paper" aria-label="Preview of the improved resume">
      <h4>${esc(r.name)}</h4>
      <p class="contact">${r.contact.map(html).join(" | ")}</p>
      <p><b>${esc(r.headline)}</b></p>
      <h5>Professional summary</h5><p>${html(r.summary)}</p>
      <h5>Core skills</h5>${r.skills.map(([l, t]) => `<p><b>${esc(l)}:</b> ${html(t)}</p>`).join("")}
      <h5>Experience</h5>${jobs}
      <h5>Community service</h5>${role([`${s.title} | ${s.org}, `, s.where], [s.dates])}${ul(s.bullets)}
      <h5>Education</h5>${r.education.map((e) => role([...(Array.isArray(e.degree) ? e.degree : [e.degree]), " | ", e.school], [e.date]) + (e.note ? `<p>${html(e.note)}</p>` : "")).join("")}
      <h5>Certifications and training</h5>${ul(r.certifications)}
    </div>`;
  return `
        <div class="resume-grid">
          <div class="resume-view">
            <section class="card resume-card">
              <h2>An improved resume, ready to download</h2>
              <p>The 2026 resume, reorganized around the jobs this site finds: strongest work first, grouped under clear headings, typos and filler removed, and the keywords postings use. Yellow highlights mark placeholders and facts to confirm before sending.</p>
              <div class="downloads">
                <a class="btn primary" href="assets/resume/Daniel_Marfurt-Levy_Resume_2026.docx" download>Improved resume <small>Word, 2 pages</small></a>
                <a class="btn" href="assets/resume/Daniel_Resume_Notes_and_Tips.docx" download>Notes and tips <small>Word</small></a>
              </div>
              <p class="fine">This site is public, so the download leaves out his phone, email and street address. Add them at the top before sending.</p>
              <details class="preview">
                <summary>Preview the improved resume</summary>
                ${paper}
              </details>
            </section>
            <section class="card resume-card check">
              <h3>Check these before sending</h3>
              <ol>${checks.map(([t, x]) => `<li><b>${esc(t)}</b> ${esc(x)}</li>`).join("")}</ol>
            </section>
            <section class="card resume-card">
              <h2>What would make it stronger</h2>
              <div class="tip-groups">
                ${tips.map((g) => `<div class="tip-group"><h3>${esc(g.heading)}</h3>${ul(g.items)}</div>`).join("")}
              </div>
            </section>
            <section class="card resume-card">
              <h2>What changed from the PDF</h2>
              <ul class="changes">${changes.map(([was, now]) => `<li><span class="was">${esc(was)}</span><span class="now">${esc(now)}</span></li>`).join("")}</ul>
            </section>
          </div>
          <aside class="side">
            <section class="card side-card">
              <h2>How the job list uses this resume</h2>
              <p class="profile-line">Every job is matched against the strengths on the resume. Its card shows a resume fit (Strong, Good, Possible or Stretch) and the resume lines to lead with, and its brief adds the gaps to close first, such as IS-200, HSEEP, or a clearance.</p>
              <p class="fine"><button class="linkish" type="button" data-subtab="jobs">Back to the jobs &rarr;</button></p>
            </section>
            <section class="card side-card">
              <h2>Lead with, by job type</h2>
              <ul class="tips">
                <li><strong>Emergency management:</strong> Tabletop and FEMA full-scale exercises, leading a SimCell unit, after-action notes, FEMA Public Assistance onboarding.</li>
                <li><strong>Public health preparedness:</strong> COVID-19 vaccination and monoclonal antibody sites, mpox response meetings, the APHA and healthcare coalition conferences.</li>
                <li><strong>Logistics and procurement:</strong> six-state medical supply purchasing and tracking, vendor relationships, pivot-table spending reports.</li>
                <li><strong>Policy and legislative:</strong> Rural Health Transformation Program tracking, the M.A. in Global Affairs, and his political knowledge (add it to the resume).</li>
                <li><strong>Program analyst and operations:</strong> on-site support to project managers, standing up new mass care sites, onboarding data for FEMA decision makers, Lean Six Sigma (add the deputy project manager role once he confirms where and when).</li>
              </ul>
            </section>
          </aside>
        </div>
        `;
}

// ---------------------------------------------------------------- write

async function main() {
  const out = path.join(ROOT, "assets/resume");
  fs.mkdirSync(out, { recursive: true });
  fs.writeFileSync(path.join(out, "Daniel_Marfurt-Levy_Resume_2026.docx"), await Packer.toBuffer(resumeDoc(resume.contact)));
  fs.writeFileSync(path.join(out, "Daniel_Resume_Notes_and_Tips.docx"), await Packer.toBuffer(notesDoc()));
  if (process.env.RESUME_CONTACT && process.env.RESUME_OUT) {
    const target = path.resolve(process.env.RESUME_OUT);
    // Compare real paths, ignoring case, so a symlink or a differently cased path into the repository is caught too.
    const real = (p) => fs.realpathSync.native(p).toLowerCase();
    const rel = path.relative(real(ROOT), real(path.dirname(target)));
    if (!(rel === ".." || rel.startsWith(".." + path.sep) || path.isAbsolute(rel))) {
      throw new Error("RESUME_OUT must be outside the repository: it holds contact details.");
    }
    const contact = process.env.RESUME_CONTACT.split("|").map((s) => s.trim()).filter(Boolean);
    fs.writeFileSync(target, await Packer.toBuffer(resumeDoc([...contact, resume.contact[3]])));
    console.log("private copy:", target);
  }
  const index = path.join(ROOT, "index.html");
  const page = fs.readFileSync(index, "utf8");
  const start = "<!-- resume page: built by tools/resume/build.js -->";
  const end = "<!-- end of resume page -->";
  const block = `${start}${resumeHtml()}${end}`;
  let next;
  if (page.includes(start)) next = page.slice(0, page.indexOf(start)) + block + page.slice(page.indexOf(end) + end.length);
  else if (page.includes("<!--RESUME-VIEW-->")) next = page.replace("<!--RESUME-VIEW-->", block);
  else throw new Error("index.html has no place for the resume page");
  fs.writeFileSync(index, next);
  console.log("built resume, notes and the resume page");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
