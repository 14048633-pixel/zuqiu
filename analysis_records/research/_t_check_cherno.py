# -*- coding: utf-8 -*-
import sys, json, re
sys.stdout.reconfigure(encoding="utf-8")
f = json.load(open(r"D:\足球分析\analysis_records\research\odds_live_0822_matched_final.json", encoding="utf-8"))
ev = f["matches"]["211687"]
for bk in ev.get("bookmakers") or []:
    for b in bk.get("bets") or []:
        nm = b.get("name") or ""
        if "handicap" in nm.lower():
            for v in b.get("values") or []:
                mm = re.match(r"^\s*(Home|Away)\s+([+-]\d+(?:\.\d+)?)\s*$", str(v.get("value")))
                if mm and abs(abs(float(mm.group(2))) - 0.75) < 0.01:
                    print(bk.get("name"), v.get("value"), v.get("odd"))
