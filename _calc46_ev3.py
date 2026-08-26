# -*- coding: utf-8 -*-
"""46场 EV v3: 重拉BSD prediction完整概率 -> vs BSD共识赔率 EV
EV口径: prob/orr*price-1 (与 _bsd_leg_ev 一致)
"""
import sys, io, os, json, urllib.request, time
from datetime import datetime, timezone, timedelta
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
tok = ""
for line in io.open(ROOT + r"\.env", encoding="utf-8"):
    line = line.strip()
    if line.startswith("BZZOIRO_API_KEY="):
        tok = line.split("=", 1)[1].strip().strip('"').strip("'")

def get(path, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request("https://sports.bzzoiro.com/api/v2" + path,
                                         headers={"User-Agent": "Mozilla/5.0", "Authorization": "Token " + tok})
            return json.load(urllib.request.urlopen(req, timeout=40))
        except Exception as e:
            if i == tries - 1:
                return {"__err__": "%s" % str(e)[:80]}
            time.sleep(2)

key46 = json.load(io.open(ROOT + r"\analysis_records\key46_20260818_2307.json", encoding="utf-8"))["results"]
model = json.load(io.open(ROOT + r"\analysis_records\key46_model_ev_20260818_2316.json", encoding="utf-8"))
m_by_id = {r["id"]: r for r in model}

def ev(prob, price, others):
    if not price or prob is None:
        return None
    orr = 1.0 / price + sum(1.0 / x for x in others if x)
    return round((prob / orr) * price - 1.0, 4)

out = []
for i, r in enumerate(key46):
    j = get("/events/%d/prediction/" % r["id"])
    mr = ((j.get("markets") or {}).get("match_result") or {})
    ou = ((j.get("markets") or {}).get("over_under") or {})
    eg = ((j.get("markets") or {}).get("expected_goals") or {})
    o = r.get("bsd_odds") or {}
    row = {"id": r["id"], "league": r["league"], "kickoff": r["kickoff"], "home": r["home"], "away": r["away"]}
    row["bsd_1x2"] = {"H": mr.get("prob_home"), "D": mr.get("prob_draw"), "A": mr.get("prob_away"), "dir": mr.get("predicted")}
    row["bsd_ou25"] = ou.get("prob_over_25")
    row["bsd_eg"] = eg
    hw, dw, aw = o.get("home_win"), o.get("draw"), o.get("away_win")
    nm = {"H": "主胜", "D": "平局", "A": "客胜"}
    d = mr.get("predicted")
    prob = {"H": mr.get("prob_home"), "D": mr.get("prob_draw"), "A": mr.get("prob_away")}.get(d)
    price = {"H": hw, "D": dw, "A": aw}.get(d)
    others = [x for k, x in {"H": hw, "D": dw, "A": aw}.items() if k != d]
    row["bsd_dir"] = nm.get(d); row["bsd_prob"] = prob
    row["ev_1x2"] = ev(prob, price, others)
    row["odds_1x2"] = price
    ov, un = o.get("over_25_goals"), o.get("under_25_goals")
    po = ou.get("prob_over_25")
    if po is not None and ov and un:
        row["ev_ou"] = ev(po / 100.0, ov, [un]) if po > 50 else ev((100 - po) / 100.0, un, [ov])
        row["ou_dir"] = "大2.5" if po > 50 else "小2.5"
        row["ou_prob"] = max(po, 100 - po)
    mrow = m_by_id.get(r["id"]) or {}
    row["our_lam"] = mrow.get("lam") or [None, None]
    row["our_dir"] = mrow.get("model_dir"); row["our_ou"] = mrow.get("model_ou")
    row["our_ou_prob"] = mrow.get("model_ou_prob")
    row["lam_dev"] = mrow.get("lam_dev")
    out.append(row)
    if (i + 1) % 10 == 0:
        print("... %d/%d" % (i + 1, len(key46)), flush=True)
    time.sleep(0.3)

fn = "key46_ev_v3_%s.json" % datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M")
io.open(ROOT + r"\analysis_records\\" + fn, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
print("saved", fn)

print("\n== 46场 EV v3 (BSD预测 vs 市场) ==")
pos = []
for r in sorted(out, key=lambda x: x["kickoff"]):
    e1 = ("%+.1f%%" % (r["ev_1x2"] * 100)) if r.get("ev_1x2") is not None else "—"
    e2 = ("%+.1f%%" % (r["ev_ou"] * 100)) if r.get("ev_ou") is not None else "—"
    agree = "✓" if r["bsd_dir"] == r.get("our_dir") else "✗"
    print("%s | %-4s | %-30s | BSD%s %s%% EV%s | OU %s %s%% EV%s | 我们%s(%s) %s | λdev%s" % (
        r["kickoff"], r["league"], r["home"] + "/" + r["away"],
        r["bsd_dir"], r["bsd_prob"], e1, r.get("ou_dir", "—"), r.get("ou_prob", ""), e2,
        r.get("our_dir", "—"), agree, r.get("our_ou", ""), r.get("lam_dev")))
    if (r.get("ev_1x2") or 0) > 0.05:
        pos.append(r)
print("\n1X2 EV>5%%: %d 场" % len(pos))
for r in pos:
    print("  +%4.1f%% | %s | %s vs %s | BSD%s %.0f%% @%.2f" % (
        r["ev_1x2"] * 100, r["kickoff"], r["home"], r["away"], r["bsd_dir"], r["bsd_prob"], r["odds_1x2"]))
