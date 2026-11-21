#!/usr/bin/env python3
"""
Internship Radar: finds fresher-friendly internships from public company job boards,
scores them for Rust, HTML, CSS, and JavaScript skills, and writes docs/jobs.json.
"""

from __future__ import annotations

import json
import re
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
UA = {"User-Agent": "Mozilla/5.0 (compatible; internship-radar/1.0)"}
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

TAG_RE = re.compile(r"<[^>]*>")
ENT_RE = re.compile(r"&[a-z]+;", re.I)
WS_RE = re.compile(r"\s+")

SENIOR_RE = re.compile(
    r"\b(senior|sr|staff|principal|lead|leader|director|head|vp|chief|architect|"
    r"manager|mgr|iii|iv|ii|3|4|5)\b", re.I,
)
LEVEL_RE = re.compile(
    r"(?:sde|sse|swe|lvl|level|grade|band)[ _-]*[2-9]"
    r"|\bl[ _-]?[2-9]\b"
    r"|\b(?:engineer|developer|analyst|scientist|programmer|architect)\s*[-_]?[2-9]\b",
    re.I,
)
INTERNSHIP_RE = re.compile(
    r"\b(internship|intern|apprentice|trainee|graduate trainee|co-op|coop|working student)\b",
    re.I,
)
TECH_ROLE_RE = re.compile(
    r"\b(engineer|developer|sde|programmer|software|web|frontend|front.?end|"
    r"full.?stack|backend|back.?end|rust|javascript|html|css|ui|ux|mobile|data|qa|test|research)\b",
    re.I,
)
NON_TECH_RE = re.compile(
    r"\b(sales|marketing|recruit|talent|hr|people|finance|account|legal|writer|"
    r"product manage|program manage|project manage|customer success|operations|logistics|"
    r"business development|specialist)\b", re.I,
)
INDIA_RE = re.compile(
    r"\b(india|bangalore|bengaluru|hyderabad|pune|chennai|mumbai|delhi|gurgaon|"
    r"gurugram|noida|kolkata|ahmedabad|jaipur|kochi|coimbatore|indore|"
    r"bhubaneswar|chandigarh|nagpur|mysore|mysuru)\b", re.I,
)
NON_INDIA_RE = re.compile(
    r"\b(usa|u\.s\.|united states|america|canada|toronto|vancouver|mexico|brazil|"
    r"poland|warsaw|germany|berlin|munich|france|paris|spain|madrid|portugal|lisbon|"
    r"netherlands|amsterdam|ireland|dublin|uk|united kingdom|london|sweden|norway|"
    r"denmark|switzerland|israel|tel aviv|australia|sydney|melbourne|new zealand|"
    r"singapore|japan|tokyo|korea|china|hong kong|taiwan|dubai|uae|nyc|new york|"
    r"san francisco|seattle|austin|boston|chicago|denver|los angeles|california|texas)\b",
    re.I,
)
YEARS_RE = re.compile(r"(\d{1,2})\s*(?:\+|-|–|to)?\s*(\d{1,2})?\s*(?:\+)?\s*years?", re.I)


def strip_html(h):
    return WS_RE.sub(" ", ENT_RE.sub(" ", TAG_RE.sub(" ", h or ""))).strip()


def get_json(url, retries=3):
    for _ in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
        except Exception:
            pass
    return None


def greenhouse(token):
    j = get_json("https://boards-api.greenhouse.io/v1/boards/%s/jobs?content=true" % token)
    if not j or "jobs" not in j:
        return []
    return [{
        "id": "gh-%s-%s" % (token, x.get("id")), "company": token,
        "title": x.get("title") or "", "location": (x.get("location") or {}).get("name") or "",
        "url": x.get("absolute_url") or "", "posted": (x.get("updated_at") or "")[:10],
        "text": strip_html(x.get("content") or "")[:4000],
    } for x in j["jobs"]]


def lever(token):
    j = get_json("https://api.lever.co/v0/postings/%s?mode=json" % token)
    if not isinstance(j, list):
        return []
    out = []
    for x in j:
        created = x.get("createdAt")
        posted = datetime.fromtimestamp(created / 1000, timezone.utc).strftime("%Y-%m-%d") if created else ""
        lists = " ".join(l.get("content", "") for l in (x.get("lists") or []))
        out.append({
            "id": "lv-%s-%s" % (token, x.get("id")), "company": token,
            "title": x.get("text") or "", "location": (x.get("categories") or {}).get("location") or "",
            "url": x.get("hostedUrl") or "", "posted": posted,
            "text": strip_html((x.get("descriptionPlain") or "") + " " + lists)[:4000],
        })
    return out


def ashby(token):
    j = get_json("https://api.ashbyhq.com/posting-api/job-board/%s" % token)
    if not j or "jobs" not in j:
        return []
    return [{
        "id": "ab-%s-%s" % (token, x.get("id")), "company": token,
        "title": x.get("title") or "", "location": x.get("location") or "",
        "url": x.get("jobUrl") or x.get("applyUrl") or "", "posted": (x.get("publishedAt") or "")[:10],
        "text": strip_html(x.get("descriptionHtml") or "")[:4000],
    } for x in j["jobs"]]


def min_years(text):
    best = 0
    for m in YEARS_RE.finditer(text):
        lo = int(m.group(1))
        if 0 < lo < 25:
            best = max(best, lo)
    return best


def score(job, cfg):
    title = (job.get("title") or "").lower()
    body = (job.get("text") or "").lower()
    loc_raw = job.get("location") or ""
    hay = title + " " + loc_raw.lower() + " " + body

    # Internship listings must still look like technical openings.
    if not INTERNSHIP_RE.search(title + " " + body[:1800]):
        return None
    if NON_TECH_RE.search(title):
        return None
    if not TECH_ROLE_RE.search(title):
        return None
    if SENIOR_RE.search(title):
        return None
    if LEVEL_RE.search(title):
        return None
    for bad in cfg["disqualify"]:
        if bad in title:
            return None

    years = min_years(title + " " + body[:2500])
    if years >= 3:
        return None

    s = 0
    matched = []
    for k, v in cfg["skills"].items():
        if k in hay:
            s += v
            matched.append(k)

    fresher = False
    for k, v in cfg["fresherSignals"].items():
        if k in title:
            s += v * 2
            fresher = True
        elif k in body[:1800]:
            s += round(v / 2)
            fresher = True

    if 0 < years <= 2:
        s += 10
        fresher = True

    loc = (title + " " + loc_raw).lower()
    for k, v in cfg["locationBoost"].items():
        if k in loc:
            s += v

    in_india = bool(INDIA_RE.search(loc))
    if not in_india:
        if "remote" not in loc or NON_INDIA_RE.search(loc):
            return None

    out = {k: v for k, v in job.items() if k != "text"}
    out.update({
        "score": s,
        "fresher": fresher,
        "internship": True,
        "years": years,
        "bangalore": ("bangalore" in loc or "bengaluru" in loc),
        "skills": matched[:10],
    })
    return out


def scan(seen=None):
    cfg = json.loads((ROOT / "scoring.json").read_text(encoding="utf-8"))
    companies = json.loads((ROOT / "companies.json").read_text(encoding="utf-8"))
    seen = dict(seen or {})

    tasks = [(greenhouse, c) for c in companies.get("greenhouse", [])]
    tasks += [(lever, c) for c in companies.get("lever", [])]
    tasks += [(ashby, c) for c in companies.get("ashby", [])]

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda t: t[0](t[1]), tasks))

    raw = [j for batch in results for j in batch]
    print("fetched %d raw postings from %d boards" % (len(raw), len(tasks)))

    scored = []
    for j in raw:
        r = score(j, cfg)
        if r and r["score"] >= cfg["minScore"]:
            scored.append(r)

    by_key = {}
    for j in scored:
        k = j["company"] + "::" + j["title"].lower()
        if k not in by_key or by_key[k]["score"] < j["score"]:
            by_key[k] = j

    jobs = []
    for j in by_key.values():
        j["firstSeen"] = seen.get(j["id"], TODAY)
        j["isNew"] = j["firstSeen"] == TODAY
        jobs.append(j)

    jobs.sort(key=lambda j: (not j["isNew"], not j["bangalore"], -j["score"]))
    for j in jobs:
        seen[j["id"]] = j["firstSeen"]
    return jobs, seen


def main():
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    seen_path = docs / "seen.json"
    seen = json.loads(seen_path.read_text(encoding="utf-8")) if seen_path.exists() else {}
    jobs, seen = scan(seen)

    payload = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "count": len(jobs),
        "jobs": jobs,
    }
    (docs / "jobs.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
    seen_path.write_text(json.dumps(seen), encoding="utf-8")

    fresh = sum(1 for j in jobs if j["isNew"])
    blr = sum(1 for j in jobs if j["bangalore"])
    print("kept %d internship matches (%d new today, %d in Bangalore)" % (len(jobs), fresh, blr))


if __name__ == "__main__":
    main()
