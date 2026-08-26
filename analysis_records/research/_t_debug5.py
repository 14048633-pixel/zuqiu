# -*- coding: utf-8 -*-
import sys, json, re
sys.stdout.reconfigure(encoding="utf-8")
def uniq(s):
    return re.sub(r"[^a-z0-9 ]", "", (str(s or "")).lower()).strip()
f = json.load(open(r"D:\足球分析\analysis_records\research\odds_live_0822_matched_final.json", encoding="utf-8"))
ev = f["matches"]["211321"]
h, a = uniq(ev.get("home_team")), uniq(ev.get("away_team"))
kind = "ah"
res = {}
for bk in ev.get("bookmakers") or []:
    for mk in bk.get("markets") or []:
        key = mk.get("key")
        if kind == "totals" and key != "totals": continue
        if kind == "ah" and key != "spreads": continue
        for oc in mk.get("outcomes") or []:
            nm = uniq(oc.get("name")); low = str(oc.get("name", "")).lower()
            pt = oc.get("point")
            if pt is None: continue
            try: line = float(pt)
            except Exception: continue
            if kind == "totals":
                if low.startswith("over"): side = "over"
                elif low.startswith("under"): side = "under"
                else: continue
            else:
                if nm == h: side = "home"
                elif nm == a: side = "away"
                else: continue
            res.setdefault(line, {}).setdefault(side, []).append((oc.get("price"), bk.get("key") or bk.get("title")))
print("RES keys:", sorted(res))
for k in sorted(res):
    print(" ", k, {s: [(p, b) for p, b in v] for s, v in res[k].items()})
