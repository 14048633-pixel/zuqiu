# -*- coding: utf-8 -*-
import sys, io, json
from datetime import datetime, timezone, timedelta
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
d = json.load(io.open(ROOT + r"\analysis_records\key46_ev_v3_20260818_2319.json", encoding="utf-8"))

def ev(prob_pct, price, others):
    if not price or prob_pct is None:
        return None
    orr = 1.0 / price + sum(1.0 / x for x in others if x)
    return round((prob_pct / 100.0 / orr) * price - 1.0, 4)

# 需要 others: 从 key46 拿共识赔率
key46 = json.load(io.open(ROOT + r"\analysis_records\key46_20260818_2307.json", encoding="utf-8"))["results"]
k_by_id = {r["id"]: r for r in key46}

out = []
for r in d:
    o = (k_by_id.get(r["id"]) or {}).get("bsd_odds") or {}
    hw, dw, aw = o.get("home_win"), o.get("draw"), o.get("away_win")
    row = dict(r)
    dirl = r["bsd_dir"]
    prob = r["bsd_prob"]
    price = {"主胜": hw, "平局": dw, "客胜": aw}.get(dirl)
    others = [x for k, x in {"主胜": hw, "平局": dw, "客胜": aw}.items() if k != dirl]
    row["ev_1x2"] = ev(prob, price, others)
    row["odds_1x2"] = price
    # OU 已在原数据算好(正确口径), 保留
    out.append(row)

fn = "key46_ev_final_%s.json" % datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M")
io.open(ROOT + r"\analysis_records\\" + fn, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))

print("== 46场 最终EV (BSD预测 vs 市场) ==")
for r in sorted(out, key=lambda x: x["kickoff"]):
    e1 = ("%+.1f%%" % (r["ev_1x2"] * 100)) if r.get("ev_1x2") is not None else "—"
    e2 = ("%+.1f%%" % (r["ev_ou"] * 100)) if r.get("ev_ou") is not None else "—"
    agree = "✓" if r["bsd_dir"] == r.get("our_dir") else "✗"
    print("%s | %-4s | %-28s | BSD%s %s%% EV%s | OU %s %s%% EV%s | 我们%s%s" % (
        r["kickoff"], r["league"], r["home"] + "/" + r["away"],
        r["bsd_dir"], r["bsd_prob"], e1, r.get("ou_dir", "—"), r.get("ou_prob", ""), e2,
        r.get("our_dir", "—"), agree))

print("\n== 1X2 EV>5% 且 BSD/我们同向 ==")
for r in sorted(out, key=lambda x: -(x.get("ev_1x2") or 0)):
    if (r.get("ev_1x2") or 0) > 0.05 and r["bsd_dir"] == r.get("our_dir"):
        print("  +%+.1f%% | %s | %s vs %s | %s %.0f%% @%.2f" % (
            r["ev_1x2"] * 100, r["kickoff"], r["home"], r["away"], r["bsd_dir"], r["bsd_prob"], r["odds_1x2"]))
print("\n== OU EV>5% ==")
for r in sorted(out, key=lambda x: -(x.get("ev_ou") or 0)):
    if (r.get("ev_ou") or 0) > 0.05:
        print("  +%+.1f%% | %s | %s vs %s | %s %s%%" % (
            r["ev_ou"] * 100, r["kickoff"], r["home"], r["away"], r.get("ou_dir"), r.get("ou_prob")))
