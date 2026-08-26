# -*- coding: utf-8 -*-
import json, io, sys, statistics
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
d = json.load(io.open(ROOT + r"\analysis_records\key46_v3_lambda_20260818_2357.json", encoding="utf-8"))
key46 = {r["id"]: r for r in json.load(io.open(ROOT + r"\analysis_records\key46_20260818_2307.json", encoding="utf-8"))["results"]}
old = {r["id"]: r for r in json.load(io.open(ROOT + r"\analysis_records\key46_model_ev_20260818_2316.json", encoding="utf-8"))}

lam_sums = [r["lam"][0]+r["lam"][1] for r in d if r["lam"] and r["lam"][0]]
ov25 = [r.get("model_over25") for r in d if r.get("model_over25") is not None]
print("λ总和: min=%.2f med=%.2f max=%.2f | 均值=%.2f" % (min(lam_sums), statistics.median(lam_sums), max(lam_sums), statistics.mean(lam_sums)))
print("模型大2.5概率: min=%.1f med=%.1f max=%.1f | 均值=%.1f | 大球场次(>50%%): %d/%d" % (
    min(ov25), statistics.median(ov25), max(ov25), statistics.mean(ov25), sum(1 for v in ov25 if v > 50), len(ov25)))
# 市场隐含大球 (去水)
mkt_ov = []
for r in d:
    k = key46.get(r["id"]) or {}
    o = k.get("bsd_odds") or {}
    ov, un = o.get("over_25_goals"), o.get("under_25_goals")
    if ov and un:
        imp = (1.0/ov) / (1.0/ov + 1.0/un) * 100
        mkt_ov.append(imp)
print("市场去水大2.5隐含: min=%.1f med=%.1f max=%.1f | 均值=%.1f" % (
    min(mkt_ov), statistics.median(mkt_ov), max(mkt_ov), statistics.mean(mkt_ov)))
# 模型 vs 市场 偏差
diff = []
for r in d:
    k = key46.get(r["id"]) or {}
    o = k.get("bsd_odds") or {}
    ov, un = o.get("over_25_goals"), o.get("under_25_goals")
    if ov and un and r.get("model_over25") is not None:
        imp = (1.0/ov)/(1.0/ov+1.0/un)*100
        diff.append(r["model_over25"] - imp)
print("模型-市场 大球概率差: 均值=%+.1fpp | 模型偏小球场次: %d/%d" % (
    statistics.mean(diff), sum(1 for x in diff if x < 0), len(diff)))
# 旧模型 OU 方向
old_ou = [r.get("model_ou") for r in old.values() if r.get("model_ou")]
from collections import Counter
print("\n旧模型 OU 方向:", dict(Counter(old_ou)), "| n=", len(old_ou))
print("新模型 OU 方向:", dict(Counter(r.get("model_ou") for r in d if r.get("model_ou"))))
# 样例: λ总和低 vs 市场
print("\n== 低λ总和样例 ==")
for r in sorted(d, key=lambda x: x["lam"][0]+x["lam"][1])[:6]:
    k = key46.get(r["id"]) or {}
    o = k.get("bsd_odds") or {}
    print("%-40s λ和=%.2f 模型大=%.0f%% 市场大≈%.0f%% (大%s 小%s)" % (
        r["home"]+"/"+r["away"], r["lam"][0]+r["lam"][1], r.get("model_over25", 0),
        (1/o["over_25_goals"])/(1/o["over_25_goals"]+1/o["under_25_goals"])*100 if o.get("over_25_goals") and o.get("under_25_goals") else 0,
        o.get("over_25_goals"), o.get("under_25_goals")))
