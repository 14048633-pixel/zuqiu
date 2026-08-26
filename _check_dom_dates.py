# -*- coding: utf-8 -*-
import pandas as pd, json, io, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
f = pd.read_parquet(ROOT + r"\data\raw\soccer-dataset\fixtures.parquet")
f = f[f["is_played"] == True].copy()
f["dt"] = pd.to_datetime(f["date_utc"], errors="coerce")
v3 = json.load(io.open(ROOT + r"\data\raw\football_data\bsd_team_stats_norm_v3_20260818.json", encoding="utf-8"))
for nm, (hf_id, dom_lid) in v3["team_map"].items():
    sub = f[((f["home_team_id"]==hf_id)|(f["away_team_id"]==hf_id)) & (f["league_id"]==dom_lid)]
    if len(sub)==0:
        print("%-26s 0场" % nm); continue
    mx = sub["dt"].max().date(); mn = sub["dt"].min().date()
    recent = (sub["dt"] > pd.Timestamp("2025-01-01")).sum()
    print("%-26s n=%-4d 近%s ~ %s | 2025年后=%d" % (nm, len(sub), mn, mx, recent))
