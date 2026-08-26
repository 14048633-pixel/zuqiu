# -*- coding: utf-8 -*-
import sys, io, json
from datetime import datetime, timezone, timedelta
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
v3 = json.load(io.open(ROOT + r"\analysis_records\key46_ev_v3_20260818_2319.json", encoding="utf-8"))
key46 = json.load(io.open(ROOT + r"\analysis_records\key46_20260818_2307.json", encoding="utf-8"))["results"]
k_by_id = {r["id"]: r for r in key46}
v2 = json.load(io.open(ROOT + r"\analysis_records\key46_ev_v2_20260818_2317.json", encoding="utf-8"))
v2_by = {r["id"]: r for r in v2}

out = []
for r in v3:
    o = (k_by_id.get(r["id"]) or {}).get("bsd_odds") or {}
    hw, dw, aw = o.get("home_win"), o.get("draw"), o.get("away_win")
    dirl = r["bsd_dir"]
    prob = r["bsd_prob"] / 100.0
    price = {"主胜": hw, "平局": dw, "客胜": aw}.get(dirl)
    others = [x for k, x in {"主胜": hw, "平局": dw, "客胜": aw}.items() if k != dirl]
    row = dict(r)
    row["odds_1x2"] = price
    if price:
        orr = 1.0 / price + sum(1.0 / x for x in others if x)
        row["ev_bet"] = round(prob * price - 1.0, 4)
        row["edge_vs_fair"] = round((prob / (prob / orr)) - 1.0, 4)
    po = r.get("ou_prob")
    if po is not None:
        ov, un = o.get("over_25_goals"), o.get("under_25_goals")
        if r["ou_dir"] == "大2.5" and ov:
            row["ev_ou_bet"] = round(po / 100.0 * ov - 1.0, 4)
        elif r["ou_dir"] == "小2.5" and un:
            row["ev_ou_bet"] = round(po / 100.0 * un - 1.0, 4)
    v2r = v2_by.get(r["id"]) or {}
    row["lam_dev"] = v2r.get("lam_dev")
    row["our_lam"] = v2r.get("our_lam")
    out.append(row)

fn = "key46_ev_final2_%s.json" % datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M")
io.open(ROOT + r"\analysis_records\\" + fn, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))

print("== 46场 最终EV (BSD概率 x 市场价 - 1) ==")
pos = []
for r in sorted(out, key=lambda x: x["kickoff"]):
    e1 = ("%+.1f%%" % (r["ev_bet"] * 100)) if r.get("ev_bet") is not None else "—"
    e2 = ("%+.1f%%" % (r["ev_ou_bet"] * 100)) if r.get("ev_ou_bet") is not None else "—"
    print("%s | %-4s | %-28s | %s %s%% @%s | EV%s | OU %s %s%% EV%s | λdev%s" % (
        r["kickoff"], r["league"], r["home"] + "/" + r["away"], r["bsd_dir"], r["bsd_prob"],
        r.get("odds_1x2"), e1, r.get("ou_dir", "—"), r.get("ou_prob", ""), e2, r.get("lam_dev")))
    if (r.get("ev_bet") or -9) > 0:
        pos.append(r)
print("\nEV_bet > 0: %d 场" % len(pos))
for r in pos:
    print("  +%+.1f%% %s %s vs %s" % (r["ev_bet"] * 100, r["kickoff"], r["home"], r["away"]))
