# -*- coding: utf-8 -*-
"""检查11场缺失场的原始快照数据结构"""
import json, io
d = json.load(io.open("analysis_records/research/odds_live_0822_matched_final.json", encoding="utf-8"))
ms = d["matches"]
missing_ids = {"207298","212165","212167","222619","223596","222620","580488","580491","580487","580486","580493","580494","580492","580490"}
for eid, ev in ms.items():
    h, a = ev.get("home_team"), ev.get("away_team")
    if ev.get("source") != "the-odds-api":
        continue
    bks = ev.get("bookmakers") or []
    mkts = set()
    for bk in bks:
        for mk in bk.get("markets") or []:
            mkts.add(mk.get("key"))
    if h and ("SJK" in h or "Preußen" in h or "Waldhof" in h or "Al-Hazem" in h or "Aldosivi" in h or "Al Faisaly" in h or "Clermont" in h or "Boulogne" in h or "Cracovia" in h or "Marseille" in h or "Hansa" in h):
        print("%-8s %-20s vs %-18s source=%-12s markets=%s" % (eid, h, a, ev.get("source"), sorted(mkts)))
