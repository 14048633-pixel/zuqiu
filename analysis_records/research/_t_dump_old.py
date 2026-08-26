# -*- coding: utf-8 -*-
import sys, json
sys.stdout.reconfigure(encoding="utf-8")
d = json.load(open(r"D:\足球分析\analysis_records\scans\scan_window_20260821_ah5.json", encoding="utf-8"))
for m in d["matches"]:
    if m.get("home") in ("Al-Riyadh", "SV Waldhof Mannheim", "Arsenal", "FC Petrolul Ploiești", "Tondela"):
        print("=====", m["league"], m["home"], "vs", m["away"], "| snap:", m.get("snap"))
        for b in m.get("bets") or []:
            print("  ", b["name"], "| odds=", b["odds"], "| prob=", round(b.get("prob", 0), 4), "| ev=", round(b.get("ev", 0), 4))
