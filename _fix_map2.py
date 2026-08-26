# -*- coding: utf-8 -*-
import pandas as pd, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
f = pd.read_parquet(ROOT + r"\data\raw\soccer-dataset\fixtures.parquet")
t = pd.read_parquet(ROOT + r"\data\raw\soccer-dataset\teams.parquet")
nm_of = {r["id"]: r["name"] for _, r in t.iterrows()}
# Drita: 查 lid138 里 Drita 的 id
kos = f[f["league_id"]==138]
drita_ids = set(kos[kos["home_team_id"].map(nm_of.get)=="Drita"]["home_team_id"]) | set(kos[kos["away_team_id"].map(nm_of.get)=="Drita"]["away_team_id"])
print("Drita ids in Kosovo league:", drita_ids)
# Saburtalo 1448 赛程
sub = f[(f["home_team_id"]==1448)|(f["away_team_id"]==1448)]
sub = sub[sub["is_played"]==True]
print("Saburtalo(1448) n=", len(sub), "max=", sub["date_utc"].max().date(), "leagues=", sub["league_id"].value_counts().head(3).to_dict())
# 冰岛 lid 100000165 队伍
ic = f[f["league_id"]==100000165]
ids = set(ic["home_team_id"]) | set(ic["away_team_id"])
print("Iceland lid100000165 n=", len(ic), "max=", ic["date_utc"].max().date())
print("  teams:", [nm_of.get(i) for i in list(ids)[:15]])
