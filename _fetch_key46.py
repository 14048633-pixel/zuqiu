# -*- coding: utf-8 -*-
"""批量拉 46 场重点联赛赔率+方向 (BSD全量 + the-odds-api交叉)
输出: analysis_records/key46_YYYYMMDD_HHMM.json / .md
"""
import sys, io, os, json, urllib.request, time, collections
from datetime import datetime, timezone, timedelta
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "prediction_v2", "src"))
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
sys.path.insert(0, os.path.join(ROOT, "form_phase0"))
from live_odds import fetch_league_odds, flatten_events
from fetch_live_48h import simpl

env = {}
for line in io.open(ROOT + r"\.env", encoding="utf-8"):
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    env[k.strip()] = v.split("#")[0].strip()
BTOK = env.get("BZZOIRO_API_KEY", "").strip('"').strip("'")
OKEY = env.get("ODDS_API_KEY_3") or env.get("ODDS_API_KEY")

def bsd_get(path, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request("https://sports.bzzoiro.com/api/v2" + path,
                                         headers={"User-Agent": "Mozilla/5.0", "Authorization": "Token " + BTOK})
            return json.load(urllib.request.urlopen(req, timeout=40))
        except Exception as e:
            if i == tries - 1:
                return {"__err__": "%s: %s" % (type(e).__name__, str(e)[:80])}
            time.sleep(2)

def devig3(a, b, c):
    ia, ib, ic = 1/a, 1/b, 1/c
    s = ia + ib + ic
    return ia/s, ib/s, ic/s
def devig2(a, b):
    ia, ib = 1/a, 1/b
    s = ia + ib
    return ia/s, ib/s
def lev(a, b):
    m, n = len(a), len(b)
    d = [[0]*(n+1) for _ in range(m+1)]
    for i in range(m+1): d[i][0] = i
    for j in range(n+1): d[0][j] = j
    for i in range(1, m+1):
        for j in range(1, n+1):
            d[i][j] = min(d[i-1][j]+1, d[i][j-1]+1, d[i-1][j-1]+(a[i-1] != b[j-1]))
    return d[m][n]

scan = json.load(io.open(ROOT + r"\analysis_records\scan48h_20260818_2300.json", encoding="utf-8"))
KEY_LG = {"欧冠", "欧联", "欧协联", "中超", "西甲"}
targets = [m for m in scan["matches"] if m["league"] in KEY_LG]

# ===== 1) the-odds-api 交叉验证 (欧冠资格/中超/西甲) =====
TO_SPORT = {"欧冠": "soccer_uefa_champs_league_qualification", "中超": "soccer_china_superleague", "西甲": "soccer_spain_la_liga"}
to_rows = []
ts_now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
for lg in ("欧冠", "中超", "西甲"):
    try:
        ev, quota = fetch_league_odds(OKEY, TO_SPORT[lg], markets="h2h,totals,spreads", regions="eu", timeout=40)
        to_rows += flatten_events(ev, lg, ts_now)
        print("the-odds %s: %d events | remaining=%s" % (lg, len(ev or []), (quota or {}).get("remaining")))
    except Exception as e:
        print("the-odds %s ERR %s" % (lg, str(e)[:100]))
    time.sleep(0.5)

def to_team_ok(row, hs, as_):
    h2, a2 = simpl(row["home_team"]), simpl(row["away_team"])
    return (hs == h2 or lev(hs, h2) <= 2) and (as_ == a2 or lev(as_, a2) <= 2)

to_idx = {}
for t in targets:
    if t["league"] not in TO_SPORT:
        continue
    hs, as_ = simpl(t["home"]), simpl(t["away"])
    for row in to_rows:
        if row["league"] == t["league"] and to_team_ok(row, hs, as_):
            to_idx.setdefault(t["id"], []).append(row)

def to_summary(tid):
    rows = to_idx.get(tid, [])
    if not rows:
        return None
    import pandas as pd
    df = pd.DataFrame(rows)
    h2h = df[df["market"] == "h2h"]; tot = df[df["market"] == "totals"]; spr = df[df["market"] == "spreads"]
    def bp(g, side):
        g = g[g["side_key"] == side]
        return g.sort_values("price").iloc[0]["price"] if len(g) else None
    out = {}
    hh, dd, aa = bp(h2h, "home"), bp(h2h, "draw"), bp(h2h, "away")
    if hh and dd and aa:
        f = devig3(hh, dd, aa)
        nm = ["主胜", "平局", "客胜"]
        mx = max(f); out["1x2"] = {"odds": [hh, dd, aa], "fair": [round(x*100, 1) for x in f],
                                   "dir": nm[f.index(mx)], "dir_prob": round(mx*100, 1)}
    ov, un = bp(tot, "over@2.5"), bp(tot, "under@2.5")
    if ov and un:
        po, pu = devig2(ov, un)
        out["ou25"] = {"over": ov, "under": un, "fair": [round(po*100, 1), round(pu*100, 1)],
                       "dir": "大2.5" if po > pu else "小2.5", "dir_prob": round(max(po, pu)*100, 1)}
    if spr is not None and len(spr):
        sp2 = spr[spr["side"] == "home"].sort_values("price")
        if len(sp2):
            r0 = sp2.iloc[0]
            ap = bp(spr, "away@%.2f" % r0["point"])
            if ap:
                ph, pa = devig2(r0["price"], ap)
                out["spread"] = {"hdp_home": float(r0["point"]), "odds": [r0["price"], ap],
                                 "fair": [round(ph*100, 1), round(pa*100, 1)]}
    return out

# ===== 2) BSD 拉取 46 场 =====
results = []
for i, t in enumerate(targets):
    rec = {"id": t["id"], "league": t["league"], "kickoff": t["kickoff"],
           "home": t["home"], "away": t["away"]}
    od = bsd_get("/events/%d/odds/" % t["id"])
    if "__err__" in od:
        rec["bsd_odds_err"] = od["__err__"]
    else:
        o = od.get("odds") or {}
        rec["bsd_odds"] = o
        rec["bsd_odds_ts"] = od.get("last_update_at")
        if o.get("home_win") and o.get("draw") and o.get("away_win"):
            f = devig3(o["home_win"], o["draw"], o["away_win"])
            nm = ["主胜", "平局", "客胜"]
            mx = max(f)
            rec["bsd_1x2"] = {"dir": nm[f.index(mx)], "prob": round(mx*100, 1),
                              "odds": [o["home_win"], o["draw"], o["away_win"]],
                              "fair": [round(x*100, 1) for x in f]}
        if o.get("over_25_goals") and o.get("under_25_goals"):
            po, pu = devig2(o["over_25_goals"], o["under_25_goals"])
            rec["bsd_ou25"] = {"dir": "大2.5" if po > pu else "小2.5",
                               "prob": round(max(po, pu)*100, 1),
                               "odds": [o["over_25_goals"], o["under_25_goals"]],
                               "fair": [round(po*100, 1), round(pu*100, 1)]}
    pr = bsd_get("/events/%d/prediction/" % t["id"])
    if "__err__" in pr:
        rec["bsd_pred_err"] = pr["__err__"]
    else:
        m = pr.get("markets") or {}
        rec["bsd_pred"] = {
            "dir": (m.get("match_result") or {}).get("predicted"),
            "prob": round(((m.get("match_result") or {}).get("prob_away") or 0) if ((m.get("match_result") or {}).get("predicted") == "A") else ((m.get("match_result") or {}).get("prob_home") or 0), 1) if (m.get("match_result") or {}).get("predicted") in ("H", "A") else round(((m.get("match_result") or {}).get("prob_draw") or 0), 1),
            "eg": (m.get("expected_goals") or {}),
            "ou": {k: v for k, v in (m.get("over_under") or {}).items() if k.startswith("prob_over")},
            "recs": (pr.get("recommendations") or {}),
            "conf": round((pr.get("model") or {}).get("confidence", 0) * 100, 1),
            "score": (m.get("score") or {}).get("most_likely"),
        }
    rec["to"] = to_summary(t["id"])
    results.append(rec)
    if (i + 1) % 8 == 0:
        print("  ... %d/%d" % (i + 1, len(targets)), flush=True)
    time.sleep(0.35)

# ===== 3) 输出 =====
now8 = datetime.now(timezone(timedelta(hours=8)))
fn = "key46_%s.json" % now8.strftime("%Y%m%d_%H%M")
io.open(ROOT + r"\analysis_records\\" + fn, "w", encoding="utf-8").write(
    json.dumps({"ts": ts_now, "n": len(results), "results": results}, ensure_ascii=False, indent=1))
print("saved analysis_records/%s" % fn)

def dir_cell(bsd, to, key):
    b = (bsd or {}).get(key)
    t = (to or {}).get(key)
    if b and t:
        return "%s %.0f%% (BSD) / %s %.0f%% (TO)" % (b["dir"], b["prob"], t["dir"], t["prob"])
    if b:
        return "%s %.0f%%" % (b["dir"], b["prob"])
    if t:
        return "%s %.0f%% (TO)" % (t["dir"], t["prob"])
    return "—"

L = ["# 46 场重点联赛方向扫描（欧冠7/欧联12/欧协联24/中超1/西甲2）", ""]
L.append("> 拉取 %s | BSD 共识赔率+预测 + the-odds-api 交叉(欧冠/中超/西甲) | 测试期只观察不下单" % now8.strftime("%Y-%m-%d %H:%M"))
L.append("> 方向=去水后最大概率边; BSD预测=BSD dc-blend-v1; ★仅当 模型/BSD/市场 三方同向且优势≥8pp 才标注")
L.append("")
for lg in ("欧冠", "欧联", "欧协联", "中超", "西甲"):
    grp = [r for r in results if r["league"] == lg]
    L.append("## %s（%d 场）" % (lg, len(grp)))
    L.append("| 开赛 | 比赛 | 1X2 | 大小2.5 | BSD预测(置信) | BSD λ(主/客) | 让球(TO) |")
    L.append("|---|---|---|---|---|---|---|")
    for r in grp:
        b = r.get("bsd_1x2"); t1 = (r.get("to") or {}).get("1x2")
        c1 = dir_cell(r.get("bsd_1x2"), r.get("to"), "1x2")
        c2 = dir_cell(r.get("bsd_ou25"), r.get("to"), "ou25")
        pd = r.get("bsd_pred") or {}
        eg = pd.get("eg") or {}
        pdir = pd.get("dir") or "—"
        if pdir == "H": pdir = "主胜"
        elif pdir == "A": pdir = "客胜"
        elif pdir == "D": pdir = "平局"
        sp = (r.get("to") or {}).get("spread")
        sp_s = "—"
        if sp:
            hdp = sp["hdp_home"]
            sp_s = ("主让%s %d%%" % (hdp, sp["fair"][0])) if hdp < 0 else ("主受+%s %d%%" % (abs(hdp), sp["fair"][0]))
        L.append("| %s | %s vs %s | %s | %s | %s(%.0f%%) | %.2f/%.2f | %s |" % (
            r["kickoff"], r["home"], r["away"], c1, c2, pdir, pd.get("prob", 0),
            eg.get("home", 0), eg.get("away", 0), sp_s))
    L.append("")
L.append("## 三方同向提示（BSD方向 + 市场方向 同向且优势≥8pp）")
n_hint = 0
for r in results:
    b = r.get("bsd_1x2") or {}
    to = (r.get("to") or {}).get("1x2")
    pd = r.get("bsd_pred") or {}
    if not b or not pd.get("dir"):
        continue
    dir_cn = {"H": "主胜", "D": "平局", "A": "客胜"}.get(pd["dir"])
    agree = dir_cn and dir_cn == b.get("dir")
    strong = (b.get("prob") or 0) >= 55
    if agree and strong:
        L.append("- **%s**（%s %s）：市场%s %.0f%% = BSD%s %.0f%%，λ %.2f/%.2f" % (
            r["home"] + " vs " + r["away"], r["league"], r["kickoff"], b["dir"], b["prob"],
            dir_cn, pd.get("prob", 0), (pd.get("eg") or {}).get("home", 0), (pd.get("eg") or {}).get("away", 0)))
        n_hint += 1
if n_hint == 0:
    L.append("- 无")
L.append("")
md = "\n".join(L)
fnm = "key46_%s.md" % now8.strftime("%Y%m%d_%H%M")
io.open(ROOT + r"\analysis_records\\" + fnm, "w", encoding="utf-8").write(md)
print("saved analysis_records/%s" % fnm)
