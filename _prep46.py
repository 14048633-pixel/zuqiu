# -*- coding: utf-8 -*-
"""批量拉 46 场重点联赛 (欧冠7/欧联12/欧协联24/中超1/西甲2)
BSD: events/{id}/odds/ + prediction/  -> 市场盘口 + BSD预测
the-odds-api: 欧冠7/中超1/西甲2 交叉验证
"""
import sys, io, json, urllib.request, time, collections
from datetime import datetime, timezone, timedelta
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = r"D:\足球分析"
env = {}
for line in io.open(ROOT + r"\.env", encoding="utf-8"):
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    env[k.strip()] = v.split("#")[0].strip()
BTOK = env.get("BZZOIRO_API_KEY", "").strip('"').strip("'")
OKEY = env.get("ODDS_API_KEY_3") or env.get("ODDS_API_KEY")

def bsd_get(path):
    req = urllib.request.Request("https://sports.bzzoiro.com/api/v2" + path,
                                 headers={"User-Agent": "Mozilla/5.0", "Authorization": "Token " + BTOK})
    return json.load(urllib.request.urlopen(req, timeout=40))

def devig3(a, b, c):
    ia, ib, ic = 1/a, 1/b, 1/c
    s = ia + ib + ic
    return ia/s, ib/s, ic/s
def devig2(a, b):
    ia, ib = 1/a, 1/b
    s = ia + ib
    return ia/s, ib/s

scan = json.load(io.open(ROOT + r"\analysis_records\scan48h_20260818_2300.json", encoding="utf-8"))
KEY_LG = {"欧冠", "欧联", "欧协联", "中超", "西甲"}
targets = [m for m in scan["matches"] if m["league"] in KEY_LG]
print("目标场次:", len(targets))
for t in targets:
    print("  ", t["id"], t["league"], t["kickoff"], t["home"], "vs", t["away"])
