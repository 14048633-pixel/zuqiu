# -*- coding: utf-8 -*-
import io, os, sys
sys.path.insert(0, r"D:\足球分析\prediction_v2")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import scan_upcoming as SU
events, _ = SU.parse_snapshots()
want = {"欧冠资格","西乙","西甲","墨超"}
seen = set()
for ev in events:
    if ev["league"] in want:
        key = (ev["league"], ev["home"], ev["away"])
        if key in seen: continue
        seen.add(key)
        # 只打印与目标相关的
        h,a = ev["home"].lower(), ev["away"].lower()
        hit = any(w in (h+a) for w in ["dinamo","viking","levski","aek","gijon","sabadell","deportivo","elche","necaxa","leon","pachuca","puebla"])
        if hit:
            print("%s | %s vs %s | %s" % (ev["league"], ev["home"], ev["away"], ev["ct"]))
