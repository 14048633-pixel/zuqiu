# -*- coding: utf-8 -*-
import pandas as pd, json, io, sys, unicodedata, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
t = pd.read_parquet(ROOT + r"\data\raw\soccer-dataset\teams.parquet")
f = pd.read_parquet(ROOT + r"\data\raw\soccer-dataset\fixtures.parquet")
# 候选映射
cand = {
    "FC Ararat-Armenia": 1892, "FC Drita": 4965, "FC Hradec Králové": 1798,
    "FK Borac Banja Luka": 1418, "FK Crvena Zvezda": 1305, "FK Jablonec": 1800,
    "FK Kauno Žalgiris": 1937, "FK Partizan": 1320, "HNK Hajduk Split": 1168,
    "HNK Rijeka": 1166, "Hapoel Be'er Sheva": 1218, "Hapoel Tel Aviv": 1225,
    "Inter Club d'Escaldes": 1869, "Kairat Almaty": 1885, "LASK": 631,
    "Larne FC": 1849, "Lincoln Red Imps": 1842, "Maccabi Tel Aviv": 1224,
    "NK Celje": 1251, "Omonia Nicosia": 1182, "Pafos FC": 1185, "Qarabağ FK": 1268,
    "Riga FC": 4738, "Shamrock Rovers": 900, "Víkingur Reykjavík": 1850,
    "ŠK Slovan Bratislava": 1236,
    "Dinamo City": 4982, "FC Iberia 1999": 100005640, "FC Viktoria Plzeň": 1805,
    "Ferencváros TC": 1203, "GNK Dinamo Zagreb": 1162, "KF Egnatia": 1840,
    "Klaksvíkar Ítróttarfelag": 1846, "Red Bull Salzburg": 619, "SK Rapid Wien": 622,
    "Sabah FK": 1275, "FK Austria Wien": None,
}
# 联赛id->名字
cat = pd.read_parquet(ROOT + r"\data\raw\soccer-dataset\league_catalogue.parquet")
lid_name = {}
for _, r in cat.iterrows():
    if pd.notna(r.get("dataset_league_id")):
        lid_name[int(r["dataset_league_id"])] = str(r["af_name"]) + "|" + str(r["af_country"])
# Austria Wien 搜索
def norm(s):
    s = unicodedata.normalize("NFKD", str(s).lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", "", s)
for _, r in t.iterrows():
    if "wien" in norm(r["name"]) or "vienna" in norm(r["name"]):
        print("WIEN cand:", r["id"], r["name"])
for nm, tid in cand.items():
    if tid is None: continue
    sub = f[(f["home_team_id"]==tid) | (f["away_team_id"]==tid)]
    sub = sub[sub["is_played"]==True] if "is_played" in sub.columns else sub
    sub = sub[sub["status_norm"]=="played"] if "status_norm" in sub.columns and (sub["status_norm"]=="played").any() else sub
    if len(sub)==0:
        print("%-26s hf=%s 赛程=0" % (nm, tid)); continue
    cnt = sub["league_id"].value_counts().head(3)
    lst = [lid_name.get(int(l), str(l))+"="+str(n) for l, n in cnt.items()]
    print("%-26s hf=%-10s n=%4d 近%sd-%sd %s" % (nm, tid, len(sub), sub["date_utc"].max().date(), sub["date_utc"].min().date(), "; ".join(lst[:3])))
