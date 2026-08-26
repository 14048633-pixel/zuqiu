# -*- coding: utf-8 -*-
import json, io, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
d = json.load(io.open(ROOT + r"\analysis_records\key46_v3_lambda_20260818_2357.json", encoding="utf-8"))
old = json.load(io.open(ROOT + r"\analysis_records\key46_model_ev_20260818_2316.json", encoding="utf-8"))
old_by = {r["id"]: r for r in old}
rows = sorted(d, key=lambda x: (x["kickoff"], x["home"]))
out = []
out.append("# 46 场 v3 λ 分析明细（2026-08-19）\n")
out.append("> 数据：key46_v3_lambda_20260818_2357.json ｜ 46 场全量（45 场有 EV，Beşiktaş/考纳斯缺市场赔率）\n")
out.append("| 开球 | 联赛 | 对阵 | 市场1X2 | v3 λ | 1X2方向 | 概率 | EV | 大小球 | 概率 | OU-EV | 数据源 | 旧模型 |")
out.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
def evstr(x):
    return ("%+.1f%%" % (x*100)) if x is not None else "—"
for r in rows:
    o = old_by.get(r["id"]) or {}
    mkt = "—"
    r2 = next((x for x in json.load(io.open(ROOT + r"\analysis_records\key46_20260818_2307.json", encoding="utf-8"))["results"] if x["id"]==r["id"]), None)
    bo = (r2 or {}).get("bsd_odds") or {}
    if bo.get("home_win"): mkt = "%s/%s/%s" % (bo.get("home_win"), bo.get("draw"), bo.get("away_win"))
    lam = "%s/%s" % (r["lam"][0], r["lam"][1]) if r["lam"] and r["lam"][0] else "—"
    d1 = r.get("model_dir","—"); p1 = r.get("model_dir_prob")
    e1 = evstr(r.get("ev_1x2"))
    ou = r.get("model_ou","—"); po = r.get("model_ou_prob")
    e2 = evstr(r.get("ev_ou"))
    old_dir = o.get("model_dir","—")
    chg = " ⚠翻转" if old_dir != d1 and d1 != "—" and old_dir != "—" else ""
    out.append("| %s | %s | %s vs %s | %s | %s | %s%s | %s%% | %s | %s | %s%% | %s | %s |" % (
        r["kickoff"], r["league"], r["home"], r["away"], mkt, lam, d1, chg,
        ("%.0f" % p1) if p1 else "—", e1, ou, ("%.0f" % po) if po else "—", e2, r.get("src_bias","")))
fp = ROOT + r"\analysis_records\key46_v3_lambda_detail_20260819.md"
io.open(fp, "w", encoding="utf-8").write("\n".join(out))
print("saved", fp, "| rows:", len(rows))
