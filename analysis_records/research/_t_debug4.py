# -*- coding: utf-8 -*-
import sys, json, re
sys.stdout.reconfigure(encoding="utf-8")
def uniq(s):
    return re.sub(r"[^a-z0-9 ]", "", (str(s or "")).lower()).strip()
f = json.load(open(r"D:\足球分析\analysis_records\research\odds_live_0822_matched_final.json", encoding="utf-8"))
ev = f["matches"]["211321"]
h, a = uniq(ev["home_team"]), uniq(ev["away_team"])
print("h=", h, "a=", a)
for bk in ev.get("bookmakers") or []:
    for mk in bk.get("markets") or []:
        if mk.get("key") != "spreads": continue
        for oc in mk.get("outcomes") or []:
            nm = uniq(oc.get("name")); pt = oc.get("point")
            side = None
            if nm == h: side = "home"
            elif nm == a: side = "away"
            print(repr(nm), "pt:", pt, "-> side:", side, "| bk:", bk.get("key"))
