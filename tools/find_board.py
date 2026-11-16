#!/usr/bin/env python3
"""
Find which public job board a company uses.

    python tools/find_board.py razorpay swiggy zomato flipkart

Paste anything it finds into companies.json, commit, and the next scan picks it up.
Adding companies is the single biggest improvement you can make to the radar.
"""

import sys
import json
import urllib.request
import urllib.error

UA = {"User-Agent": "Mozilla/5.0 (compatible; job-radar/1.0)"}


def probe(url):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None


def count(j, key):
    if j is None:
        return 0
    if key is None:
        return len(j) if isinstance(j, list) else 0
    return len(j.get(key) or []) if isinstance(j, dict) else 0


def main():
    names = sys.argv[1:]
    if not names:
        print(__doc__)
        return

    for n in names:
        cap = "".join(p[:1].upper() + p[1:] for p in n.split("-"))
        gh = count(probe("https://boards-api.greenhouse.io/v1/boards/%s/jobs" % n), "jobs")
        lv = count(probe("https://api.lever.co/v0/postings/%s?mode=json" % n), None)
        ab = count(probe("https://api.ashbyhq.com/posting-api/job-board/%s" % cap), "jobs")

        hits = []
        if gh:
            hits.append('greenhouse: "%s" (%d jobs)' % (n, gh))
        if lv:
            hits.append('lever: "%s" (%d jobs)' % (n, lv))
        if ab:
            hits.append('ashby: "%s" (%d jobs)' % (cap, ab))

        print("%-20s %s" % (n, "   ".join(hits) if hits else "- no public board found"))


if __name__ == "__main__":
    main()
