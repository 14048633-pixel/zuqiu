# -*- coding: utf-8 -*-
import sys, json
sys.stdout.reconfigure(encoding="utf-8")
root = r"D:\足球分析"
want_home = {"Aldosivi","Real Betis","Jaguares de Córdoba","Estudiantes de Río Cuarto"}
d = json.load(open(root + r"\analysis_records\scans\scan_window_20260821_ah5.json", encoding="utf-8"))
for m in d["matches"]:
    if m.get("home") in want_home:
        print(m.get("league"), "|", m.get("home"), "vs", m.get("away"), "| snap=", m.get("snap"))
