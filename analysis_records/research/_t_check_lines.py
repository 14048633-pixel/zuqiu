# -*- coding: utf-8 -*-
import sys, json
sys.stdout.reconfigure(encoding="utf-8")
f = json.load(open(r"D:\足球分析\analysis_records\research\odds_live_0822_matched_final.json", encoding="utf-8"))
for eid in ("222618", "212165", "212144", "374898", "222621"):
    ev = f["matches"][eid]
    print("###", eid, ev["home_team"], "vs", ev["away_team"])
    lines = {}
    for bk in (ev.get("bookmakers") or [])[:8]:
        for mk in bk.get("markets") or []:
            if mk.get("key") != "totals": continue
            for oc in mk.get("outcomes") or []:
                pt = oc.get("point")
                if pt is None: continue
                lines.setdefault(float(pt), []).append((oc.get("name"), oc.get("price"), bk.get("key")))
    for k in sorted(lines):
        print("  line", k, "->", lines[k][:3], "... n=", len(lines[k]))
