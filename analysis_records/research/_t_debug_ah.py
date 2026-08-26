# -*- coding: utf-8 -*-
import sys, json
sys.stdout.reconfigure(encoding="utf-8")
f = json.load(open(r"D:\足球分析\analysis_records\research\odds_live_0822_matched_final.json", encoding="utf-8"))
for eid in ("211321", "222618"):
    ev = f["matches"][eid]
    print("###", eid, ev["home_team"], "vs", ev["away_team"])
    for bk in (ev.get("bookmakers") or [])[:3]:
        for mk in bk.get("markets") or []:
            if mk.get("key") == "spreads":
                print("  book:", bk.get("key"))
                for oc in (mk.get("outcomes") or []):
                    print("    ", json.dumps(oc, ensure_ascii=False))
print("=== AFB raw structure ===")
ev = f["matches"]["211687"]
print(type(ev.get("bookmakers")), len(ev.get("bookmakers") or []))
e0 = (ev.get("bookmakers") or [])[0]
print("first el keys:", list(e0.keys()) if isinstance(e0, dict) else e0)
print(json.dumps(e0, ensure_ascii=False)[:600])
