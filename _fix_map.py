# -*- coding: utf-8 -*-
import pandas as pd, sys, unicodedata, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
f = pd.read_parquet(ROOT + r"\data\raw\soccer-dataset\fixtures.parquet")
t = pd.read_parquet(ROOT + r"\data\raw\soccer-dataset\teams.parquet")
def norm(s):
    s = unicodedata.normalize("NFKD", str(s).lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", "", s)
# 1) Austria Vienna (627) 赛程
for tid, nm in [(627, "Austria Vienna"), (1203, "Ferencvarosi TC")]:
    sub = f[(f["home_team_id"]==tid)|(f["away_team_id"]==tid)]
    sub = sub[sub["is_played"]==True] if "is_played" in sub.columns else sub
    print(nm, tid, "n=", len(sub), "max=", sub["date_utc"].max().date() if len(sub) else "-")
    if len(sub):
        print("   leagues:", sub["league_id"].value_counts().head(4).to_dict())
# 2) 找格鲁吉亚 Iberia: 搜 saburtalo / iberia
for _, r in t.iterrows():
    n = norm(r["name"])
    if "saburtalo" in n or ("iberia" in n and "chile" not in str(r.get("fd_name")).lower()):
        print("IBERIA cand:", r["id"], r["name"], r.get("fd_name"))
# 3) 科索沃联赛 lid=138 的队伍
kos = f[f["league_id"]==138]
if len(kos):
    ids = set(kos["home_team_id"]) | set(kos["away_team_id"])
    names = {r["id"]: r["name"] for _, r in t.iterrows() if r["id"] in ids}
    print("Kosovo lid138 fixtures:", len(kos), "max:", kos["date_utc"].max().date())
    print("   teams:", list(names.values())[:20])
else:
    print("Kosovo lid138: 0 fixtures")
# 4) Víkingur 冰岛: 查 lid 100000165 (1. Deild) 是否有
vic = f[(f["home_team_id"]==1850)|(f["away_team_id"]==1850)]
print("Vikingur total:", len(vic), vic["league_id"].value_counts().to_dict())
