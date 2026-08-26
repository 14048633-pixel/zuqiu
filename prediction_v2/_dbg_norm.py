# -*- coding: utf-8 -*-
import json, os, sys, io
ROOT = r"D:\足球分析"
v2 = json.load(io.open(os.path.join(ROOT, "analysis_records", "bsd_v2_2026-08-17.json"), encoding="utf-8"))
GEN = {"fc", "afc", "cf", "sc", "ac", "as", "us", "cd", "de", "sd", "ud", "ssc", "gnk", "ca", "esg"}
def norm(s):
    s = "".join(c for c in str(s or "") if c.isalnum() or c.isspace()).lower()
    return " ".join(w for w in s.split() if w not in GEN)
for eid in ("223567", "223572", "223579", "587701"):
    ev = ((v2["data"][eid])["prediction"])["event"]
    print(eid, "|", repr(norm(ev["home_team"])), "vs", repr(norm(ev["away_team"])), "|", ev["event_date"])
