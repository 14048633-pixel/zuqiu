# -*- coding: utf-8 -*-
"""自检3: 缺亚盘场次 + 其 books 实际来源"""
import json, io
d = json.load(io.open("analysis_records/research/rerun_0822_intel.json", encoding="utf-8"))
for m in d["matches"]:
    r = m["result"]
    tags = r.get("risk_tags") or []
    if "缺亚盘" in tags:
        books = m.get("books") or {}
        print("%-10s %-22s vs %-20s books=%s" % (
            m["league"], m["home"], m["away"], json.dumps(books, ensure_ascii=False)))
