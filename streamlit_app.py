"""
Internship Radar - Streamlit dashboard.

Finds fresher-friendly internships and ranks them against Rust, TypeScript,
CSS, and JavaScript skills.
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
WINDOWS = {
    "Today only": 0,
    "Last 3 days": 2,
    "Last week": 6,
    "All open internships": None,
}

st.set_page_config(page_title="Internship Radar", page_icon="🎓", layout="wide")


@st.cache_data(ttl=1800)
def load_jobs():
    if not JOBS_FILE.exists():
        return [], None
    data = json.loads(JOBS_FILE.read_text(encoding="utf-8"))
    return data.get("jobs", []), data.get("updated")


def live_scan():
    seen = {}
    seen_path = ROOT / "docs" / "seen.json"
    if seen_path.exists():
        seen = json.loads(seen_path.read_text(encoding="utf-8"))
    jobs, _ = radar.scan(seen)
    return jobs


def age_days(first_seen):
    try:
        seen = datetime.strptime(first_seen, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return 0
    return max(0, (datetime.now(timezone.utc).date() - seen).days)


def load_tracker():
    if not TRACKER_FILE.exists():
        return {}
    df = pd.read_csv(TRACKER_FILE).dropna(subset=["id"])
    if df.empty:
        return {}
    return df.set_index("id")["status"].to_dict()


def save_tracker(d):
    rows = [{"id": k, "status": v} for k, v in d.items() if v and v != "Not applied"]
    pd.DataFrame(rows, columns=["id", "status"]).to_csv(TRACKER_FILE, index=False)


st.title("🎓 Internship Radar")
st.caption("Fresher internships matching Rust, TypeScript, CSS, and JavaScript")

if "jobs" not in st.session_state:
    jobs, updated = load_jobs()
    st.session_state.jobs = jobs
    st.session_state.updated = updated

top = st.columns([3, 1])
with top[1]:
    if st.button("Rescan internships", use_container_width=True):
        with st.spinner("Scanning internship boards..."):
            st.session_state.jobs = live_scan()
            st.session_state.updated = datetime.now(timezone.utc).isoformat()
        st.rerun()

jobs = st.session_state.jobs
updated = st.session_state.updated

if not jobs:
    st.warning("No internship scan data yet. Click **Rescan internships**, or run the GitHub Action once.")
    st.stop()

with top[0]:
    when = "unknown"
    if updated:
        try:
            dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            when = (dt + timedelta(hours=5, minutes=30)).strftime("%d %b %Y, %I:%M %p IST")
        except ValueError:
            when = updated
    n_new = sum(1 for j in jobs if age_days(j.get("firstSeen")) == 0)
    n_week = sum(1 for j in jobs if age_days(j.get("firstSeen")) <= 6)
    st.caption("%d open internships · %d new today · %d this week · last scan %s" %
               (len(jobs), n_new, n_week, when))

with st.sidebar:
    st.header("Filters")
    window = st.radio("First seen", list(WINDOWS), index=1)
    only_blr = st.checkbox("Bangalore only", value=True)
    only_fresher = st.checkbox("Fresher-friendly only", value=True)
    min_score = st.slider("Minimum match score", 0, 160, 12, step=5)
    companies = sorted({j["company"] for j in jobs})
    picked = st.multiselect("Companies", companies)
    search = st.text_input("Search internship or skill", "")

    st.divider()
    st.caption("Resume skills: Rust · TypeScript · CSS · JavaScript")

cutoff = WINDOWS[window]
rows = []
for j in jobs:
    if cutoff is not None and age_days(j.get("firstSeen")) > cutoff:
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

if "tracker" not in st.session_state:
    st.session_state.tracker = load_tracker()
tracker = st.session_state.tracker

tabs = st.tabs(["Open internships (%d)" % len(rows), "My applications"])

with tabs[0]:
    if not rows:
        st.info("Nothing matches these filters. Loosen them in the sidebar.")
    for j in rows:
        age = age_days(j.get("firstSeen"))
        badge = " :green-badge[NEW]" if age == 0 else (" :gray-badge[%dd ago]" % age if age <= 6 else "")
        blr = " :blue-badge[Bangalore]" if j.get("bangalore") else ""
        fresh = " :orange-badge[fresher]" if j.get("fresher") else ""
        yrs = " :gray-badge[%dy exp]" % j["years"] if j.get("years") else ""

        with st.container(border=True):
            c = st.columns([6, 2, 2])
            with c[0]:
                st.markdown("**[%s](%s)**%s%s%s%s" % (j["title"], j["url"], badge, blr, fresh, yrs))
                st.caption("%s · %s" % (j["company"], j.get("location") or "India"))
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
    st.caption("Statuses are temporary on Streamlit Cloud. Download the CSV to keep a copy.")
    restore = st.file_uploader("Restore saved tracker CSV", type="csv")
    if restore is not None:
        try:
            df_in = pd.read_csv(restore).dropna(subset=["id"])
            restored = df_in.set_index("id")["status"].to_dict()
            st.session_state.tracker.update(restored)
            save_tracker(st.session_state.tracker)
            st.success("Restored %d tracked internships." % len(restored))
        except Exception as exc:
            st.error("Could not read that file: %s" % exc)

    tracker = st.session_state.tracker
    applied_ids = {k for k, v in tracker.items() if v and v != "Not applied"}
    mine = [j for j in jobs if j["id"] in applied_ids]
    if not mine:
        st.info("Nothing tracked yet. Set a status in **Open internships**.")
    else:
        df = pd.DataFrame([{
            "Status": tracker.get(j["id"], ""), "Internship": j["title"],
            "Company": j["company"], "Location": j.get("location", ""),
            "Score": j.get("score", 0), "Link": j["url"],
        } for j in mine]).sort_values("Status")
        st.dataframe(df, use_container_width=True, hide_index=True,
                     column_config={"Link": st.column_config.LinkColumn("Link", display_text="Open")})
        st.download_button("Download internship tracker as CSV", df.to_csv(index=False),
                           "internship-tracker.csv", "text/csv")
