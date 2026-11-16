# How Job Radar works

Everything the app does, end to end: where the jobs come from, what gets thrown away,
how the match score is calculated, and how to change any of it.

- **Live dashboard:** https://nrnjobfinder.streamlit.app/
- **Static fallback:** `https://nrnravi.github.io/JobFinder/` (if GitHub Pages is enabled)

---

## 1. The shape of the thing

There are two moving parts and one data file between them.

```
                    ┌──────────────────────────┐
  GitHub Actions    │  radar.py                │   07:00 IST daily
  (cron)       ───▶ │  fetch → filter → score  │ ──┐
                    └──────────────────────────┘   │
                                                   ▼
                                        docs/jobs.json   (committed to the repo)
                                                   │
                        ┌──────────────────────────┴───────────────────┐
                        ▼                                              ▼
            streamlit_app.py                                  docs/index.html
            (Streamlit Cloud)                                 (GitHub Pages)
            filters + tracker                                 read-only fallback
```

`radar.py` is the whole engine. The Streamlit app imports it, so "Rescan now" in the UI
runs exactly the same code the nightly job runs — there is no second implementation that
can drift out of sync.

| File | What it is |
|---|---|
| `radar.py` | Fetch, filter, score. Run it directly or import `scan()`. |
| `streamlit_app.py` | The dashboard and application tracker. |
| `companies.json` | Which job boards to scan. |
| `scoring.json` | All the tunable numbers. |
| `docs/jobs.json` | Output of the last scan. Committed, so it is the shared state. |
| `docs/seen.json` | Job ID → date first observed. This is what makes "NEW" meaningful. |
| `docs/index.html` | Static dashboard for GitHub Pages. |
| `tools/find_board.py` | Discovers a company's board token. |
| `.github/workflows/radar.yml` | The daily schedule. |

---

## 2. Where the jobs come from

Companies that use Greenhouse, Lever or Ashby as their applicant tracking system get a
**public, unauthenticated JSON endpoint** listing their open roles. That is the entire
data source. No scraping, no login, no API key, no terms-of-service grey area — these
endpoints exist so job boards can syndicate listings.

| Source | Endpoint | Notes |
|---|---|---|
| Greenhouse | `boards-api.greenhouse.io/v1/boards/<token>/jobs?content=true` | `content=true` returns the full description; without it there is nothing to match skills against. Token is lowercase. |
| Lever | `api.lever.co/v0/postings/<token>?mode=json` | Returns a bare array, not an object. Token is lowercase. |
| Ashby | `api.ashbyhq.com/posting-api/job-board/<token>` | **Token is case-sensitive** — `Sarvam` works, `sarvam` returns nothing. |

Each adapter normalises its source into the same dict:

```python
{"id", "company", "title", "location", "url", "posted", "text"}
```

`text` is the description with HTML stripped, truncated to 4000 characters. It is used for
matching and then dropped — it never reaches `jobs.json`, which is why the output file
stays small.

Fetches run across 12 threads and retry three times. A board that 404s or times out
returns an empty list, so one dead company cannot fail the run.

---

## 3. The pipeline, in order

```
fetch all boards
   ↓
hard filters      ← rejects outright, no score computed
   ↓
scoring           ← everything surviving gets a number
   ↓
minScore cutoff   ← currently 15
   ↓
de-duplicate      ← by company + title, keeping the higher score
   ↓
mark NEW          ← anything not in seen.json
   ↓
sort + write jobs.json
```

Order matters. The hard filters run *before* scoring, so a senior role can never score its
way in on a strong skills match.

---

## 4. The hard filters

These are pass/fail. A posting hitting any of them is discarded.

**1. Non-engineering titles** — `NON_TECH_RE`
Rejects sales, marketing, recruiting, HR, finance, legal, content, writing, design,
product/program/project management, customer success, operations, logistics and
"specialist" roles.

**2. Must look like an engineering role** — `TECH_ROLE_RE`
The title must contain one of: engineer, developer, sde, programmer, software, data
scien\*, machine learning, ml, ai, full stack, backend, frontend, android, mobile, qa,
sdet, test, devops, analyst, research.

**3. Seniority** — `SENIOR_RE`, with a `JUNIOR_OK_RE` exemption
Rejects senior, sr, staff, principal, lead, director, head, vp, chief, architect, manager,
and the roman numerals `ii`/`iii`/`iv`. The exemption exists because `SENIOR_RE` would
otherwise reject "SDE I" and "Software Engineer 1".

**4. Numeric levels** — `LEVEL_RE`
Rejects `SDE2`, `SDE-3`, `L2`, `Level 4`, `Band 3`, and `<role> <2-9>` patterns like
"Security Engineer 2". This last one was added after "Security Engineer 2" was observed
passing: `SENIOR_RE` listed the digits 3, 4 and 5 but not 2.

**5. Explicit experience demands** — `min_years()`
Scans the title and the first 2500 characters of the description for an "N years" pattern
and takes the **highest** number found. 3 or more, and the posting is rejected.

**6. Geography** — `INDIA_RE` / `NON_INDIA_RE`
A posting is kept if it names an Indian city or India itself, matched on **word
boundaries** so that "Indiana" does not read as "India". Otherwise it is kept only if it
says "Remote" with no other country attached — so "Remote" passes, "Remote - India"
passes, and "Remote - USA", "Remote, Poland" and "San Francisco, CA, or Remote" do not.

---

## 5. How the match score is calculated

The score is a sum of four parts. There is no normalisation and no maximum — it is an
ordering device, not a percentage.

### a. Skill overlap
Every key in `scoring.json → skills` that appears anywhere in **title + location +
description** adds its points. Current weights:

| Points | Skills |
|---|---|
| 8 | generative ai, genai |
| 7 | fastapi, llm, ai engineer |
| 6 | python, react, django, machine learning, computer vision, full stack |
| 5 | flask, kotlin, android, tensorflow, pytorch, scikit, opencv, deep learning |
| 4 | javascript, rest api, backend, frontend |
| 3 | typescript, node, sql, mysql, mongodb, pandas, numpy, aws |
| 2 | git |

These are weighted toward the profile the radar was built for: Python/React/FastAPI with
generative AI. Change them and the ranking changes.

### b. Fresher signals
Keys in `scoring.json → fresherSignals`, weighted by **where** they appear:

- in the **title** → the weight is **doubled**
- in the first 1800 characters of the description → the weight is **halved**
- in the title, it wins; the body is only checked if the title did not match

A title is a far stronger signal than a sentence buried in a description, which is what the
doubling encodes. Weights run from 10 ("intern") to 25 ("fresher", "0-1 year", "graduate
engineer", "new grad", "entry level"). Any match also sets the `fresher` flag the UI filters on.

A stated requirement of 1–2 years adds a further **+15** and sets the flag, since in India
that usually still means a fresher is considered.

### c. Location
`bangalore` / `bengaluru` +20, `india` +10, `remote` +6, other Indian metros +4. These stack:
a Bangalore role gets both the +20 and the +10 for India.

### d. Seniority penalties
`scoring.json → seniorityPenalty` subtracts points for weaker signals that are not outright
disqualifying. In practice most such roles are already gone by the hard filters, so this is
a safety net rather than the main mechanism.

### Worked example — the real top result

**SDE I at Hevo Data, Bangalore. Score: 90.**

```
skills            python            +6
                  typescript        +3
                  rest api          +4
fresher signals   "sde i" in TITLE  +30   (weight 15, doubled)
                  "0-1 year" in body +12   (weight 25, halved)
                  "intern" in body   +5    (weight 10, halved)
location          bangalore         +20
                  india             +10
                                   ────
                                     90
```

Nearly half the score comes from the fresher signals, which is the intent: a perfect skills
match on a role that will not consider a fresher is worth nothing.

### After scoring

- Anything below `minScore` (15) is dropped.
- Duplicates are collapsed on `company + lowercase title`, keeping the higher score.
- `firstSeen` comes from `seen.json`, or today if the ID has never been observed.
  **This is why `seen.json` is committed** — delete it and every job looks new again.
- `isNew` is also written, but both dashboards ignore it and compute the age from
  `firstSeen` at render time instead. If the daily job fails for two days, a stored
  `isNew` would be wrong while a computed age stays right.
- Sort order: new first, then Bangalore, then score descending.

---

## 6. The dashboard

`streamlit_app.py` reads `docs/jobs.json` (cached 30 minutes). **Rescan now** calls
`radar.scan()` live instead, taking about 15 seconds.

Sidebar filters: the **first-seen window**, Bangalore only, fresher-friendly only, minimum
score, company, and a text search over title and matched skills.

### The first-seen window

The window answers "what has turned up since I last looked", and defaults to **Last 3 days**
rather than today:

| Window | Keeps postings first seen |
|---|---|
| Today only | today |
| **Last 3 days** (default) | today, yesterday, the day before |
| Last week | the last 7 days |
| All open roles | no limit |

A today-only view is fragile — skip a Saturday and Friday's finds become invisible among
hundreds of older rows. The three-day default means missing a day costs nothing.

Age is computed from `firstSeen` against the current date **every time the page renders**,
never read from a stored flag, so a missed scan cannot leave a stale "NEW" badge behind.
Postings carry a `NEW` badge on day zero and a `3d ago` badge up to six days old.

Note that this is the date the **radar first saw** the posting, not the date the company
published it. A board added to `companies.json` today arrives with all of its roles marked
new. It is also not an archive: a role that gets filled disappears from the next scan
entirely, so the window shows roles that are both recent **and** still open.

**The application tracker** lets you set a status per role (Not applied → Applied →
Referral asked → OA/test → Interview → Offer/Rejected). Tracked roles appear on the
**My applications** tab.

> **Important limitation.** Streamlit Community Cloud gives the app an **ephemeral
> filesystem**. `tracker.csv` is wiped whenever the app redeploys — which happens
> automatically every time the daily scan commits new jobs, so roughly daily. There is no
> persistent storage on the free tier. The tab therefore has a **Download CSV** button and a
> **Restore from CSV** uploader, and warns about this in the UI. Download it after a session
> of applying, or keep the real tracker in a Google Sheet and treat the app as read-only.

---

## 7. The daily job

`.github/workflows/radar.yml` runs at `30 1 * * *` UTC (07:00 IST), and can be triggered by
hand from the Actions tab. It checks out the repo, runs `python radar.py`, and commits
`docs/jobs.json` and `docs/seen.json` if they changed.

It needs **Settings → Actions → General → Workflow permissions → Read and write**.
Without it the run succeeds but the commit fails, and the dashboard silently stops updating.

The workflow commits as `job-radar <actions@github.com>`. If you push while it has committed
ahead of you, rebase rather than force-push, and merge `seen.json` by keeping the **earliest**
date per ID — overwriting it resets everyone's NEW flags.

---

## 8. Adding companies

The single highest-value change available. Find a token:

```
python tools/find_board.py razorpay swiggy zomato flipkart
```

It probes all three providers (trying both lowercase and PascalCase for Ashby) and prints
what it finds. Paste the hits into `companies.json` and commit.

Not every company has a public board — Flipkart, Zomato and Razorpay do not, and those have
to be checked by hand on their own career sites.

The current list is 63 boards and includes global companies (Stripe, GitLab, Databricks,
Snowflake, MongoDB, Okta) because they all hire in Bangalore; their non-India roles are
removed by the geography filter. In practice they carry more matching Bangalore openings
than most Indian startups on the list.

---

## 9. Known limitations

- **Only companies using Greenhouse, Lever or Ashby are visible.** Most Indian service
  companies (TCS, Infosys, Wipro, Accenture, Cognizant) use their own portals and run
  scheduled drives. Those need manual alerts — see `docs/playbook.html`.
- **The tracker is not durable** on the free Streamlit tier. See section 6.
- **Scores are not comparable across companies** that write descriptions at different
  lengths — a verbose JD mentions more keywords and scores higher. Treat the score as a
  sorting aid, not a ranking of fit.
- **`seen.json` grows forever.** It is small (one line per job ID), but after a year it is
  worth pruning entries older than a few months.
- **No deduplication across companies**, only within one. The same role cross-posted by two
  staffing firms would appear twice.

---

## 10. Running it locally

```
pip install -r requirements.txt

python radar.py                  # one scan, writes docs/jobs.json
streamlit run streamlit_app.py   # the dashboard on localhost:8501
python tools/find_board.py zoho  # look up a board token
```

Python 3.12. `radar.py` itself uses only the standard library; `requirements.txt` exists for
the Streamlit app.

To see the effect of a scoring change, delete `docs/seen.json` first so every result is
recomputed from scratch, then diff the resulting `jobs.json`.
