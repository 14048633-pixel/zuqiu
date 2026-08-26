# -*- coding: utf-8 -*-
import io, json
ROOT = r"D:\足球分析"
mev = json.load(io.open(ROOT + r"\analysis_records\key46_model_ev_20260818_2316.json", encoding="utf-8"))
key = json.load(io.open(ROOT + r"\analysis_records\key46_20260818_2307.json", encoding="utf-8"))["results"]
by = {r["id"]: r for r in key}

def mkt_dir(r):
    bo = r.get("bsd_ou25") or {}
    to = (r.get("to") or {}).get("ou25") or {}
    return (bo.get("dir"), to.get("dir"))

rows = []
for r in mev:
    if r.get("ev_ou") is None: continue
    k = by.get(r["id"], {})
    bd, td = mkt_dir(k)
    rows.append({
        "kickoff": r["kickoff"], "league": r["league"], "home": r["home"], "away": r["away"],
        "model": r["model_ou"], "ev": r["ev_ou"], "bsd": bd, "to": td,
    })

sel = [x for x in rows if x["ev"] is not None and x["ev"] >= 0.05]
agree_bsd = sum(1 for x in sel if x["bsd"] and x["model"].replace("2.5","") == x["bsd"].replace("2.5",""))
dis_bsd = sum(1 for x in sel if x["bsd"] and x["model"].replace("2.5","") != x["bsd"].replace("2.5",""))
agree_to = sum(1 for x in sel if x["to"] and x["model"].replace("2.5","") == x["to"].replace("2.5",""))
dis_to = sum(1 for x in sel if x["to"] and x["model"].replace("2.5","") != x["to"].replace("2.5",""))
print("正EV场次(≥5%%): %d 场" % len(sel))
print("vs BSD方向: 一致 %d / 相反 %d / 无盘 %d" % (agree_bsd, dis_bsd, sum(1 for x in sel if not x["bsd"])))
print("vs the-odds方向: 一致 %d / 相反 %d / 无盘 %d" % (agree_to, dis_to, sum(1 for x in sel if not x["to"])))
print("双源都有且双源一致方向: %d 场" % sum(1 for x in sel if x["bsd"] and x["to"] and x["bsd"]==x["to"]))
print()
print("| 时间 | 对阵 | 模型 | EV | BSD | the-odds | 模型vs双源 |")
for x in sorted(sel, key=lambda z: -z["ev"]):
    tag = []
    if x["bsd"] and x["model"].replace("2.5","")==x["bsd"].replace("2.5",""): tag.append("BSD同")
    elif x["bsd"]: tag.append("BSD反")
    else: tag.append("BSD无")
    if x["to"] and x["model"].replace("2.5","")==x["to"].replace("2.5",""): tag.append("TO同")
    elif x["to"]: tag.append("TO反")
    else: tag.append("TO无")
    print("| %s | %s vs %s | %s | %+.1f%% | %s | %s | %s |" % (
        x["kickoff"], x["home"], x["away"], x["model"], x["ev"]*100, x["bsd"] or "—", x["to"] or "—", "+".join(tag)))
