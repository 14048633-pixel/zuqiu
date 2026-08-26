# -*- coding: utf-8 -*-
import sys, io, json, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
tok = ""
for line in io.open(r"D:\足球分析\.env", encoding="utf-8"):
    line = line.strip()
    if line.startswith("BZZOIRO_API_KEY="):
        tok = line.split("=", 1)[1].strip().strip('"').strip("'")
d = json.load(io.open(r"D:\足球分析\analysis_records\scan48h_20260818_2300.json", encoding="utf-8"))
for m in d["matches"]:
    if m["league"] in ("欧联", "欧协联") and m["kickoff"].startswith("08-21"):
        print(m["id"], m["league"], m["home"], "vs", m["away"], m["kickoff"])
