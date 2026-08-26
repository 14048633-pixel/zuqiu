# -*- coding: utf-8 -*-
"""验证: rows(odds_compare) vs matched_final 队名一致性"""
import json, io
rows = json.load(io.open("analysis_records/research/odds_compare_0822_rows.json", encoding="utf-8"))
d = json.load(io.open("analysis_records/research/odds_live_0822_matched_final.json", encoding="utf-8"))
ms = d["matches"]
for r in rows:
    eid = str(r["eid"])
    ev = ms.get(eid)
    if not ev: continue
    rh, ra = r["home"], r["away"]
    eh, ea = ev.get("home_team"), ev.get("away_team")
    if rh != eh or ra != ea:
        print("DIFF eid=%-8s rows: %-22s vs %-20s | final: %-22s vs %-20s" % (eid, rh, ra, eh, ea))
