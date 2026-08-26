# -*- coding: utf-8 -*-
"""自检2: 伤停覆盖不全的场次 vs match_package 拉取状态"""
import json, io, glob
d = json.load(io.open("analysis_records/research/rerun_0822_intel.json", encoding="utf-8"))
ms = d["matches"]
def eid_of(m):
    eid = str(m["id"])
    return eid[5:] if eid.startswith("apifb") else eid
for m in ms:
    r = m["result"]
    tags = r.get("risk_tags") or []
    if "伤停覆盖不全" in tags:
        eid = eid_of(m)
        fp = "analysis_records/match_package/%s.json" % eid
        try:
            pkg = json.load(io.open(fp, encoding="utf-8"))
            inj = pkg.get("injuries") or {}
            lu = pkg.get("lineups") or {}
            print("%-8s %-24s vs %-20s inj_h=%s inj_a=%s covered=%s/%s lu_status=%s conf=%s/%s" % (
                eid, m["home"], m["away"],
                len(inj.get("home") or []), len(inj.get("away") or []),
                inj.get("home_covered"), inj.get("away_covered"),
                lu.get("lineup_status"), (lu.get("confidence") or {}).get("home"), (lu.get("confidence") or {}).get("away")))
        except Exception as ex:
            print("%-8s %s vs %s NO PKG (%s)" % (eid, m["home"], m["away"], ex))
