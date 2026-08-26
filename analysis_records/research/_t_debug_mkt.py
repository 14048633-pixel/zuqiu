# -*- coding: utf-8 -*-
import sys, json, re
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\足球分析\analysis_records\research")
f = json.load(open(r"D:\足球分析\analysis_records\research\odds_live_0822_matched_final.json", encoding="utf-8"))
ev = f["matches"]["209535"]
# inline copy of best_market totals logic
res = {}
for bk in ev.get("bookmakers") or []:
    for mk in bk.get("markets") or []:
        if mk.get("key") != "totals":
            continue
        for oc in mk.get("outcomes") or []:
            nm = str(oc.get("name", "")); low = nm.lower(); pt = oc.get("point")
            print("tot oc:", nm, pt, oc.get("price"))
            if low.startswith("over"): side = "over"
            elif low.startswith("under"): side = "under"
            else: continue
            try:
                line = float(pt)
            except Exception as e:
                print("  line fail:", pt); continue
            r = res.setdefault(line, {})
            r.setdefault(side, []).append((oc.get("price"), bk.get("key")))
print("res:", json.dumps(res, ensure_ascii=False)[:400])
