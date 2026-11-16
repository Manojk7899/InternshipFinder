#!/usr/bin/env node
// Job radar: pulls fresher-friendly dev/AI roles from public company job boards,
// scores them against Kushala's profile, and writes docs/jobs.json for the dashboard.
// No API keys, no login, no personal data. Runs on GitHub Actions.

import { readFile, writeFile, mkdir } from 'node:fs/promises';

const UA = { 'User-Agent': 'Mozilla/5.0 (compatible; job-radar/1.0)' };
const TODAY = new Date().toISOString().slice(0, 10);

const strip = (h = '') =>
  h.replace(/<[^>]*>/g, ' ').replace(/&[a-z]+;/gi, ' ').replace(/\s+/g, ' ').trim();

async function getJSON(url) {
  for (let i = 0; i < 3; i++) {
    try {
      const r = await fetch(url, { headers: UA, signal: AbortSignal.timeout(20000) });
      if (r.ok) return await r.json();
      if (r.status === 404) return null;
    } catch { /* retry */ }
    await new Promise(r => setTimeout(r, 800 * (i + 1)));
  }
  return null;
}

// ---------- sources ----------

async function greenhouse(token) {
  const j = await getJSON(`https://boards-api.greenhouse.io/v1/boards/${token}/jobs?content=true`);
  if (!j?.jobs) return [];
  return j.jobs.map(x => ({
    id: `gh-${token}-${x.id}`,
    company: token,
    title: x.title || '',
    location: x.location?.name || '',
    url: x.absolute_url,
    posted: (x.updated_at || '').slice(0, 10),
    text: strip(x.content || '').slice(0, 4000),
  }));
}

async function lever(token) {
  const j = await getJSON(`https://api.lever.co/v0/postings/${token}?mode=json`);
  if (!Array.isArray(j)) return [];
  return j.map(x => ({
    id: `lv-${token}-${x.id}`,
    company: token,
    title: x.text || '',
    location: x.categories?.location || '',
    url: x.hostedUrl,
    posted: x.createdAt ? new Date(x.createdAt).toISOString().slice(0, 10) : '',
    text: strip(`${x.descriptionPlain || ''} ${(x.lists || []).map(l => l.content).join(' ')}`).slice(0, 4000),
  }));
}

async function ashby(token) {
  const j = await getJSON(`https://api.ashbyhq.com/posting-api/job-board/${token}?includeCompensation=false`);
  if (!j?.jobs) return [];
  return j.jobs.map(x => ({
    id: `ab-${token}-${x.id}`,
    company: token,
    title: x.title || '',
    location: x.location || '',
    url: x.jobUrl || x.applyUrl,
    posted: (x.publishedAt || '').slice(0, 10),
    text: strip(x.descriptionHtml || '').slice(0, 4000),
  }));
}

// ---------- scoring ----------

// Hard filters: seniority, non-engineering roles, and explicit years-of-experience.
const SENIOR_RE = /\b(senior|sr|staff|principal|lead|leader|director|head|vp|chief|architect|manager|mgr|iii|iv|ii|3|4|5)\b/i;
const LEVEL_RE = /(?:sde|sse|swe|lvl|level|grade|band)[ _-]*[2-9]/i;
const JUNIOR_OK_RE = /\b(sde\s*-?\s*(1|i)|software engineer\s*-?\s*(1|i)|engineer\s*-?\s*(1|i))\b/i;
const TECH_ROLE_RE = /\b(engineer|developer|sde|programmer|software|data scien|machine learning|ml|ai|full.?stack|backend|back.?end|frontend|front.?end|android|mobile|qa|sdet|test|devops|analyst|research)\b/i;
const NON_TECH_RE = /\b(sales|marketing|recruit|talent|hr|people|finance|account|legal|writer|content|design|ux|ui designer|product manage|program manage|project manage|customer success|business development|operations|supply|logistics|partner|enablement|product research|specialist)\b/i;

// Returns the highest "N years" figure demanded anywhere in the text, or 0 if none stated.
function minYears(text) {
  let min = 0;
  const re = /(\d{1,2})\s*(?:\+|-|–|to)?\s*(\d{1,2})?\s*(?:\+)?\s*year/gi;
  let m;
  while ((m = re.exec(text))) {
    const lo = parseInt(m[1], 10);
    if (lo > 0 && lo < 25) min = Math.max(min, lo);
  }
  return min;
}

function score(job, cfg) {
  const title = job.title.toLowerCase();
  const body = (job.text || '').toLowerCase();
  const hay = title + ' ' + job.location.toLowerCase() + ' ' + body;

  // --- hard filters ---
  if (NON_TECH_RE.test(title)) return null;
  if (!TECH_ROLE_RE.test(title)) return null;
  if (SENIOR_RE.test(title) && !JUNIOR_OK_RE.test(title)) return null;
  if (LEVEL_RE.test(title)) return null;
  for (const bad of cfg.disqualify) if (title.includes(bad)) return null;

  // Reject anything demanding 3+ years up front.
  const years = minYears(title + ' ' + body.slice(0, 2500));
  if (years >= 3) return null;

  let s = 0;
  const matched = [];
  for (const [k, v] of Object.entries(cfg.skills))
    if (hay.includes(k)) { s += v; matched.push(k); }

  // Fresher signals count double in the title, where they actually mean something.
  let fresher = false;
  for (const [k, v] of Object.entries(cfg.fresherSignals)) {
    if (title.includes(k)) { s += v * 2; fresher = true; }
    else if (body.slice(0, 1800).includes(k)) { s += Math.round(v / 2); fresher = true; }
  }
  if (years > 0 && years <= 2) { s += 15; fresher = true; }

  const loc = (job.title + ' ' + job.location).toLowerCase();
  let inIndia = false;
  for (const [k, v] of Object.entries(cfg.locationBoost))
    if (loc.includes(k)) { s += v; if (k !== 'remote') inIndia = true; }
  if (!inIndia && !loc.includes('remote')) return null;

  return {
    ...job, text: undefined, score: s, fresher, years,
    bangalore: loc.includes('bangalore') || loc.includes('bengaluru'),
    skills: matched.slice(0, 8),
  };
}

// ---------- main ----------

const cfg = JSON.parse(await readFile(new URL('./scoring.json', import.meta.url), 'utf8'));
const companies = JSON.parse(await readFile(new URL('./companies.json', import.meta.url), 'utf8'));

let seen = {};
try { seen = JSON.parse(await readFile(new URL('./docs/seen.json', import.meta.url), 'utf8')); } catch {}

const tasks = [
  ...(companies.greenhouse || []).map(c => greenhouse(c)),
  ...(companies.lever || []).map(c => lever(c)),
  ...(companies.ashby || []).map(c => ashby(c)),
];

const raw = (await Promise.all(tasks)).flat();
console.log(`fetched ${raw.length} raw postings from ${tasks.length} boards`);

const scored = raw.map(j => score(j, cfg)).filter(j => j && j.score >= cfg.minScore);

// de-dupe by company+title
const byKey = new Map();
for (const j of scored) {
  const k = `${j.company}::${j.title.toLowerCase()}`;
  if (!byKey.has(k) || byKey.get(k).score < j.score) byKey.set(k, j);
}

const jobs = [...byKey.values()].map(j => {
  j.firstSeen = seen[j.id] || TODAY;
  j.isNew = j.firstSeen === TODAY;
  return j;
}).sort((a, b) =>
  (b.isNew - a.isNew) || (b.bangalore - a.bangalore) || (b.score - a.score)
);

for (const j of jobs) seen[j.id] = j.firstSeen;

await mkdir(new URL('./docs/', import.meta.url), { recursive: true });
await writeFile(new URL('./docs/jobs.json', import.meta.url),
  JSON.stringify({ updated: new Date().toISOString(), count: jobs.length, jobs }, null, 1));
await writeFile(new URL('./docs/seen.json', import.meta.url), JSON.stringify(seen));

const fresh = jobs.filter(j => j.isNew).length;
console.log(`kept ${jobs.length} matches (${fresh} new today, ${jobs.filter(j => j.bangalore).length} in Bangalore)`);
