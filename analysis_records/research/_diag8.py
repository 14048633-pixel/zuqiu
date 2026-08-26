# -*- coding: utf-8 -*-
"""检查仍缺1X2的场次 raw h2h outcomes"""
import json, io, re, unicodedata
d = json.load(io.open("analysis_records/research/odds_live_0822_matched_final.json", encoding="utf-8"))
ms = d["matches"]
def uniq(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", s.lower())
for eid in ["207298", "222619", "223596", "211869"]:
    ev = ms.get(eid)
    if not ev: print(eid, "NO EV"); continue
    h, a = ev.get("home_team"), ev.get("away_team")
    print("eid=%s %s vs %s" % (eid, h, a))
    for bk in ev.get("bookmakers") or []:
        for mk in bk.get("markets") or []:
            if mk.get("key") == "h2h":
                for oc in mk.get("outcomes") or []:
                    print("   h2h outcome: %-22s uniq=%-22s price=%s" % (oc.get("name"), uniq(oc.get("name")), oc.get("price")))
        print("   book:", bk.get("key"), "markets:", [m.get("key") for m in bk.get("markets") or []])
    print()
