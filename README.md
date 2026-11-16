# Job Radar

A free, no-login job tracker for fresher software / AI roles in Bangalore.

It runs every morning on GitHub Actions, pulls openings straight from companies'
own public job boards (Greenhouse, Lever, Ashby), filters out anything senior or
non-engineering, scores what's left against a fresher AI/full-stack profile, and
publishes the results as a web page.

Nothing to install. No API keys. No account to connect. No laptop has to be on.

**Dashboard:** `https://<your-username>.github.io/job-radar/`

---

## One-time setup (about 5 minutes)

1. Create a **public** repo named `job-radar` on GitHub and push this folder to it.
2. Go to **Settings → Pages**. Under "Build and deployment", set
   **Source: Deploy from a branch**, **Branch: `main`**, **Folder: `/docs`**. Save.
3. Go to **Settings → Actions → General**. Under "Workflow permissions", select
   **Read and write permissions**. Save. (This lets the daily run commit its results.)
4. Go to the **Actions** tab, pick **Job Radar**, and click **Run workflow** to do the
   first run now instead of waiting for tomorrow morning.

After a minute or two the dashboard URL above will be live. Bookmark it on your phone.

> The repo must be public for GitHub Pages to work on a free account — which is why
> **no resume, phone number or email is stored in here.** Keep it that way.

---

## What it does each morning

Runs at **07:00 IST**, and for each company board:

- pulls every open posting
- drops anything senior, staff, principal, lead, manager, SDE 2+, or demanding 3+ years
- drops non-engineering roles (sales, HR, content, product management, …)
- drops anything outside India that isn't remote
- scores the rest on skill overlap, fresher signals and Bangalore location
- marks anything it has never seen before as **NEW**

Then it commits `docs/jobs.json` and the page updates itself.

---

## Using it

Open the dashboard and work the **New today** filter first — those are roles posted
since yesterday, where being early genuinely matters. Then **Bangalore**, then
**Fresher-friendly**.

The number on the right of each row is the match score. It is a sorting aid, not a
verdict: a 30 you're excited about beats a 70 you aren't.

---

## Tuning it

**Add more companies.** Find a company's board token first:

```
node tools/find-board.mjs razorpay swiggy zomato flipkart
```

Anything it reports as found, paste into `companies.json` under the right section.
Commit, and the next run picks it up. More companies is the single biggest
improvement you can make — 20 boards is a start, 100 is a real radar.

**Change what counts as a match.** Edit `scoring.json`:

- `skills` — points per matching technology. Add what you learn.
- `fresherSignals` — phrases that mean "open to freshers". Worth double in a job title.
- `disqualify` / `seniorityPenalty` — what to reject or push down.
- `minScore` — raise it if there's too much noise, lower it to see more.

**Run it locally** to test a change before committing:

```
node radar.mjs
```

---

## What this deliberately does not do

It does not auto-apply. Mass auto-applying gets LinkedIn accounts restricted, and
tailored applications plus referrals convert far better than volume. The radar finds
and ranks the jobs; the applying, tailoring and follow-up stay human.
