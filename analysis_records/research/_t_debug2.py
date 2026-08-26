# -*- coding: utf-8 -*-
import sys, json, re
sys.stdout.reconfigure(encoding="utf-8")
f = json.load(open(r"D:\足球分析\analysis_records\research\odds_live_0822_matched_final.json", encoding="utf-8"))
ev = f["matches"]["211321"]
print("home:", ev["home_team"], "| away:", ev["away_team"])
# dump all spreads outcomes across books
from collections import defaultdict
res = defaultdict(lambda: defaultdict(list))
for bk in ev.get("bookmakers") or []:
    for mk in bk.get("markets") or []:
        if mk.get("key") != "spreads": continue
        for oc in mk.get("outcomes") or []:
            print("  spread:", repr(oc.get("name")), "pt:", oc.get("point"), "price:", oc.get("price"), "bk:", bk.get("key"))
