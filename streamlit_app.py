"""
Job Radar - Streamlit dashboard.

Reads the daily scan committed by GitHub Actions (docs/jobs.json), and can also
rescan live on demand. Includes a lightweight application tracker so you can mark
what you've applied to and when to follow up.

Run locally:  streamlit run streamlit_app.py
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

import radar

ROOT = Path(__file__).parent
JOBS_FILE = ROOT / "docs" / "jobs.json"
TRACKER_FILE = ROOT / "tracker.csv"

STATUSES = ["Not applied", "Applied", "Referral asked", "OA / test", "Interview", "Offer", "Rejected"]

st.set_page_config(page_title="Job Radar", page_icon="\U0001F4E1", layout="wide")


# --- data -------------------------------------------------------------------

@st.cache_data(ttl=1800)
def load_jobs():
    """Load the last committed scan."""
    if not JOBS_FILE.exists():
        return [], None
    data = json.loads(JOBS_FILE.read_text(encoding="utf-8"))
    return data.get("jobs", []), data.get("updated")


def live_scan():
    """Rescan every board right now."""
    seen = {}
    seen_path = ROOT / "docs" / "seen.json"
    if seen_path.exists():
        seen = json.loads(seen_path.read_text(encoding="utf-8"))
    jobs, _ = radar.scan(seen)
    return jobs


def load_tracker():
    """Read saved statuses. Note this file does not survive a Streamlit Cloud
    redeploy - use the CSV download/restore in the My applications tab."""
    if not TRACKER_FILE.exists():
        return {}
    df = pd.read_csv(TRACKER_FILE).dropna(subset=["id"])
    if df.empty:
        return {}
    return df.set_index("id")["status"].to_dict()


def save_tracker(d):
    rows = [{"id": k, "status": v} for k, v in d.items() if v and v != "Not applied"]
    df = pd.DataFrame(rows, columns=["id", "status"])
    df.to_csv(TRACKER_FILE, index=False)


# --- header -----------------------------------------------------------------

st.title("\U0001F4E1 Job Radar")

if "jobs" not in st.session_state:
    jobs, updated = load_jobs()
    st.session_state.jobs = jobs
    st.session_state.updated = updated

top = st.columns([3, 1])
with top[1]:
    if st.button("Rescan now", use_container_width=True):
        with st.spinner("Scanning job boards..."):
            st.session_state.jobs = live_scan()
            st.session_state.updated = datetime.now(timezone.utc).isoformat()
        st.rerun()

jobs = st.session_state.jobs
updated = st.session_state.updated

if not jobs:
    st.warning(
        "No scan data yet. Click **Rescan now**, or run the GitHub Action once "
        "so it commits `docs/jobs.json`."
    )
    st.stop()

with top[0]:
    when = "unknown"
    if updated:
        try:
            dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            when = (dt + timedelta(hours=5, minutes=30)).strftime("%d %b %Y, %I:%M %p IST")
        except ValueError:
            when = updated
    n_new = sum(1 for j in jobs if j.get("isNew"))
    st.caption("%d open roles  ·  %d new today  ·  last scan %s" % (len(jobs), n_new, when))


# --- filters ----------------------------------------------------------------

with st.sidebar:
    st.header("Filters")
    only_new = st.checkbox("New today only", value=False)
    only_blr = st.checkbox("Bangalore only", value=True)
    only_fresher = st.checkbox("Fresher-friendly only", value=False)
    min_score = st.slider("Minimum match score", 0, 120, 15, step=5)
    companies = sorted({j["company"] for j in jobs})
    picked = st.multiselect("Companies", companies, default=[])
    search = st.text_input("Search title or skill", "")

    st.divider()
    st.caption(
        "Scores rank roles by skill overlap, fresher signals and location. "
        "A 30 you're excited about beats a 70 you aren't."
    )

rows = []
for j in jobs:
    if only_new and not j.get("isNew"):
        continue
    if only_blr and not j.get("bangalore"):
        continue
    if only_fresher and not j.get("fresher"):
        continue
    if j.get("score", 0) < min_score:
        continue
    if picked and j["company"] not in picked:
        continue
    if search:
        blob = (j["title"] + " " + " ".join(j.get("skills", []))).lower()
        if search.lower() not in blob:
            continue
    rows.append(j)


# --- tracker state ----------------------------------------------------------

if "tracker" not in st.session_state:
    st.session_state.tracker = load_tracker()
tracker = st.session_state.tracker

tabs = st.tabs(["Open roles (%d)" % len(rows), "My applications"])

with tabs[0]:
    if not rows:
        st.info("Nothing matches these filters. Loosen them in the sidebar.")
    for j in rows:
        badge = " :green-badge[NEW]" if j.get("isNew") else ""
        blr = " :blue-badge[Bangalore]" if j.get("bangalore") else ""
        fresh = " :orange-badge[fresher]" if j.get("fresher") else ""
        yrs = " :gray-badge[%dy exp]" % j["years"] if j.get("years") else ""

        with st.container(border=True):
            c = st.columns([6, 2, 2])
            with c[0]:
                st.markdown("**[%s](%s)**%s%s%s%s" % (j["title"], j["url"], badge, blr, fresh, yrs))
                st.caption("%s  ·  %s" % (j["company"], j.get("location") or "India"))
                if j.get("skills"):
                    st.caption("Matched: " + ", ".join(j["skills"]))
            with c[1]:
                st.metric("Score", j.get("score", 0))
            with c[2]:
                cur = tracker.get(j["id"], "Not applied")
                new = st.selectbox(
                    "Status", STATUSES, index=STATUSES.index(cur) if cur in STATUSES else 0,
                    key="s_" + j["id"], label_visibility="collapsed",
                )
                if new != cur:
                    tracker[j["id"]] = new
                    save_tracker(tracker)

with tabs[1]:
    st.caption(
        ":warning: Statuses are stored on the server's temporary disk, which is wiped "
        "whenever the app redeploys (roughly daily, after each scan). **Download the CSV "
        "below to keep your history**, and restore it here afterwards."
    )

    restore = st.file_uploader("Restore a saved tracker CSV", type="csv")
    if restore is not None:
        try:
            df_in = pd.read_csv(restore).dropna(subset=["id"])
            restored = df_in.set_index("id")["status"].to_dict()
            st.session_state.tracker.update(restored)
            save_tracker(st.session_state.tracker)
            st.success("Restored %d tracked roles." % len(restored))
        except Exception as exc:
            st.error("Could not read that file: %s" % exc)

    tracker = st.session_state.tracker
    applied_ids = {k for k, v in tracker.items() if v and v != "Not applied"}
    mine = [j for j in jobs if j["id"] in applied_ids]
    if not mine:
        st.info(
            "Nothing tracked yet. Set a status on any role in the **Open roles** tab "
            "and it will appear here."
        )
    else:
        df = pd.DataFrame([{
            "Status": tracker.get(j["id"], ""),
            "Role": j["title"],
            "Company": j["company"],
            "Location": j.get("location", ""),
            "Score": j.get("score", 0),
            "Link": j["url"],
        } for j in mine]).sort_values("Status")
        st.dataframe(
            df, use_container_width=True, hide_index=True,
            column_config={"Link": st.column_config.LinkColumn("Link", display_text="Open")},
        )
        st.caption(
            "Follow up on anything sitting at **Applied** for more than 5 days - "
            "a short note to a recruiter or engineer at the company is where most "
            "extra interviews come from."
        )
        st.download_button(
            "Download tracker as CSV",
            df.to_csv(index=False),
            "job-tracker.csv",
            "text/csv",
        )
