# Job Radar

A free job tracker for fresher software / AI roles in Bangalore.

Every morning it pulls openings straight from companies' own public job boards
(Greenhouse, Lever, Ashby), filters out anything senior or non-engineering, scores
what's left against a fresher AI / full-stack profile, and shows the results in a
dashboard with an application tracker.

No API keys. No login. No account to connect. No laptop has to stay on.

**▶ Live dashboard: https://nrnjobfinder.streamlit.app/**

---

## Documentation

- **[HOW-IT-WORKS.md](HOW-IT-WORKS.md)** — the full picture: data sources, every filter, how
  the match score is calculated (with a worked example), the daily job, and known limitations.
- **[The Volume Track playbook](docs/playbook.html)** — the manual half of the search: the
  service-company drives and portal alerts this radar cannot see. Served at
  `https://nrnravi.github.io/JobFinder/playbook.html` when Pages is enabled.

---

## The two pieces

| | What it is | Where it runs |
|---|---|---|
| **The scan** | `radar.py` — fetches, filters, scores, writes `docs/jobs.json` | GitHub Actions, 07:00 IST daily, free |
| **The dashboard** | `streamlit_app.py` — browse, filter, track applications | Streamlit Community Cloud, free |

There is also a zero-dependency static page at `docs/index.html` (GitHub Pages) as an
always-on fallback — Streamlit apps sleep when idle and take a few seconds to wake.

---

## Setup

### 1. GitHub Actions (the daily scan)

1. **Settings → Actions → General → Workflow permissions** → select
   **Read and write permissions** → Save.
   *Without this the daily run cannot commit its results.*
2. **Actions** tab → **Job Radar** → **Run workflow** to do the first scan now
   instead of waiting until tomorrow morning.

### 2. Streamlit Community Cloud (the dashboard)

Already deployed at **https://nrnjobfinder.streamlit.app/** — bookmark it on your phone.

To redeploy from scratch: **share.streamlit.io** → sign in with GitHub → **Create app →
Deploy a public app from GitHub**, repository `nrnravi/JobFinder`, branch `main`, main file
path `streamlit_app.py`.

It redeploys automatically whenever the daily scan commits new jobs.

### 3. GitHub Pages (optional fallback)

**Settings → Pages** → Source: **Deploy from a branch**, Branch: `main`,
Folder: **`/docs`**. Gives you `https://nrnravi.github.io/JobFinder/`.

> The repo is public, so **no resume, phone number or email is stored in it.**
> Keep it that way.

---

## Using it

The view opens on **Last 3 days**, so anything found while you were away is still there —
missing a day costs nothing. Narrow to **Today only** when you are checking daily, widen to
**Last week** after a break, and stack **Bangalore** and **Fresher-friendly** on top.

Apply to the newest first: being early genuinely matters on fresher roles.

Set a **status** on any role and it moves to the **My applications** tab. Follow up on
anything sitting at *Applied* for more than 5 days: a short note to a recruiter or an
engineer at that company is where most extra interviews come from.

The score is a sorting aid, not a verdict. A 30 you're excited about beats a 70 you aren't.

---

## What each run does

- pulls every open posting from the boards in `companies.json`
- drops senior / staff / principal / lead / manager / SDE 2+ / L2+ roles
- drops anything demanding 3+ years
- drops non-engineering roles (sales, HR, content, product management, …)
- drops anything outside India that isn't remote
- scores the rest on skill overlap, fresher signals and Bangalore location
- marks anything never seen before as **NEW**

---

## Tuning it

**Add more companies** — the single biggest improvement available. Find a company's
board token:

```
python tools/find_board.py razorpay swiggy zomato flipkart
```

Paste whatever it finds into `companies.json`, commit, and the next scan picks it up.
18 boards is a start; 100 is a real radar. Not every company has a public board —
Flipkart and Zomato don't, so those still need checking by hand.

**Change what counts as a match** — edit `scoring.json`:

- `skills` — points per matching technology. Add what you learn.
- `fresherSignals` — phrases meaning "open to freshers"; worth double in a job title.
- `disqualify` / `seniorityPenalty` — what to reject or push down.
- `minScore` — raise it for less noise, lower it to see more.

**Test a change before committing:**

```
python radar.py                  # run a scan locally
streamlit run streamlit_app.py   # view the dashboard locally
```

---

## What this deliberately does not do

It does not auto-apply. Mass auto-applying gets LinkedIn accounts restricted, and
tailored applications plus referrals convert far better than volume. The radar finds
and ranks the jobs; applying, tailoring and following up stay human.

It also only sees companies with public job boards — mostly product companies and
startups. Service companies (TCS, Infosys, Wipro, Accenture) run separate off-campus
drives that need Naukri and Unstop alerts set up by hand.
