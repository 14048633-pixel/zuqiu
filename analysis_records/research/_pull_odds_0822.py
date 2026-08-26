# -*- coding: utf-8 -*-
"""拉取 08-22 凌晨 27 场最新赔率(the-odds-api soccer 全量, 1 credit)并保存"""
import sys, os, json, io, time, unicodedata
from datetime import datetime, timezone
sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "src", "odds"))
sys.path.insert(0, os.path.join(ROOT, "prediction_v2", "src"))
from live_odds import fetch_league_odds

OUT = os.path.join(ROOT, "analysis_records", "research")
clean = json.load(io.open(os.path.join(ROOT, "analysis_records", "scan48h_20260821_0048_clean.json"), encoding="utf-8"))
targets = []
for m in clean["matches"]:
    if m["kickoff"].startswith("08-22"):
        targets.append({"id": m["id"], "league": m["league"], "league_en": m["league_en"],
                        "home": m["home"], "away": m["away"], "ko": m["kickoff_iso"]})
print("targets:", len(targets))

def norm(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c) and (c.isalnum() or c.isspace())).lower()
    for w in ("fc", "cf", "sc", "ac", "as", "us", "cd", "de", "sd", "ud", "ssc", "gnk", "ca", "esg", "fk", "ks", "sk", "sf", "if", "ik", "bk"):
        s = (" " + s + " ").replace(" " + w + " ", " ").strip()
    return " ".join(s.split())

def side_ok(a, b):
    sa, sb = set(a.split()), set(b.split())
    if not sa or not sb:
        return False
    return a == b or sa <= sb or sb <= sa or len(sa & sb) / len(sa | sb) >= 0.6

KEY = "8365acfd25968d4917f29474c2df5b2c"  # key5 rem=380
events, quota = fetch_league_odds(KEY, "soccer", markets="h2h,spreads,totals", regions="eu,uk,us", timeout=90)
print("quota:", quota, "n_events:", len(events))
ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
raw_fn = os.path.join(OUT, "odds_live_0822_%s.json" % ts.replace(":", "").replace("-", "").replace("T", "_"))
json.dump({"pulled_at": ts, "quota": quota, "n_events": len(events), "events": events},
          io.open(raw_fn, "w", encoding="utf-8"), ensure_ascii=False)
print("saved raw:", raw_fn)

matched = {}
for t in targets:
    nh, na = norm(t["home"]), norm(t["away"])
    best = None
    for ev in events:
        h, a, ct = ev.get("home_team"), ev.get("away_team"), ev.get("commence_time")
        if abs((datetime.fromisoformat(ct.replace("Z", "+00:00")) - datetime.fromisoformat(t["ko"].replace("Z", "+00:00"))).total_seconds()) > 3600:
            continue
        if side_ok(nh, norm(h)) and side_ok(na, norm(a)):
            best = ev
            break
    if best is None:
        print("NO MATCH:", t["league"], t["home"], "vs", t["away"], t["ko"])
    else:
        matched[t["id"]] = best
        print("OK:", t["id"], t["home"], "vs", t["away"], "<->", best["home_team"], "vs", best["away_team"], "| bk:", len(best.get("bookmakers") or []))
json.dump({"pulled_at": ts, "matched": {str(k): v for k, v in matched.items()}},
          io.open(os.path.join(OUT, "odds_live_0822_matched.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("matched:", len(matched), "/", len(targets))
