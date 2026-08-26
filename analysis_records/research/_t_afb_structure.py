# -*- coding: utf-8 -*-
import sys, json
sys.stdout.reconfigure(encoding="utf-8")
f = json.load(open(r"D:\足球分析\analysis_records\research\odds_live_0822_matched_final.json", encoding="utf-8"))
ev = f["matches"]["211687"]
for bk in ev.get("bookmakers") or []:
    if bk.get("name") != "Bet365":
        continue
    for i, b in enumerate(bk.get("bets") or []):
        nm = b.get("name") or ""
        if "handicap" in nm.lower():
            print("BET entry", i, "| name:", repr(nm))
            for v in b.get("values") or []:
                print("    ", v.get("value"), v.get("odd"))
