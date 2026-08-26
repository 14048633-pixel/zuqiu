# -*- coding: utf-8 -*-
"""实盘账本 × 拉取数据 对比报告 CLI —— 逐注核对: 当时拉到什么 / 模型预测什么 / 实际结果如何
=========================================================================================
用法: python prediction_v2/ledger_vs_data.py [--ledger analysis_records/bet_ledger.csv]
拉取数据关联:
  A. the-odds-api 赔率快照 prediction_v2/output/odds_snapshots/snapshots.csv (赛前快照, 56/58覆盖)
  B. BSD 共识赔率 analysis_records/bsd_odds_*.json (按事件id)
  C. BSD 预期进球 analysis_records/bsd_predictions_*.json
  D. 赛果: 结算JSON score -> ESPN CSV -> BSD events home_score/away_score
输出: analysis_records/ledger_vs_data_YYYYMMDD.json + .md
关键对比: 账本EV vs 快照同盘EV(若快照价算EV为负=当时拉取数据不支持该价值, 多为快照过期)
"""
import glob
import io
import json
import os
import re
import sys
from datetime import datetime

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _ev_list(evs):
    if isinstance(evs, dict):
        if isinstance(evs.get("events"), list):
            return evs["events"]
        return [v for v in evs.values() if isinstance(v, dict)]
    return evs or []


def _tname(v):
    if isinstance(v, dict):
        return v.get("name")
    return v


def load_scores():
    """结算JSON -> ESPN CSV -> BSD events, 返回 {(league,norm_h,norm_a): "hg-ag"}"""
    out = {}
    for fn in glob.glob(os.path.join(ROOT, "analysis_records", "*结算*.json")):
        try:
            d = json.load(io.open(fn, encoding="utf-8"))
        except Exception:
            continue
        for r in d.get("rows", []):
            sc = r.get("score")
            if sc and "-" in sc:
                out[(r.get("league"), norm(r.get("home")), norm(r.get("away")))] = sc
    for fn in glob.glob(os.path.join(ROOT, "data", "raw", "football_data", "espn_*_results.csv")):
        lg = os.path.basename(fn).split("espn_")[1].split("_results")[0]
        try:
            d = pd.read_csv(fn)
        except Exception:
            continue
        for _, r in d.iterrows():
            k = (lg, norm(r["HomeTeam"]), norm(r["AwayTeam"]))
            if k not in out:
                out[k] = "%d-%d" % (int(r["FTHG"]), int(r["FTAG"]))
    for fn in glob.glob(os.path.join(ROOT, "analysis_records", "bzzoiro_events_*.json")):
        try:
            evs = json.load(io.open(fn, encoding="utf-8"))
        except Exception:
            continue
        for e in _ev_list(evs):
            if not isinstance(e, dict):
                continue
            hs, as_ = e.get("home_score"), e.get("away_score")
            if hs is None or as_ is None:
                continue
            lg = _tname(e.get("league")) or ""
            if not isinstance(lg, str):
                lg = str(lg)
            out.setdefault((lg, norm(_tname(e.get("home_team"))), norm(_tname(e.get("away_team")))),
                           "%d-%d" % (hs, as_))
    return out


def load_snapshots():
    """-> {(nh,na): [rows]} 每场保留, 按 snapshot_ts 排序"""
    fp = os.path.join(ROOT, "prediction_v2", "output", "odds_snapshots", "snapshots.csv")
    if not os.path.exists(fp):
        return {}
    d = pd.read_csv(fp)
    out = {}
    for _, r in d.iterrows():
        k = (norm(r["home_team"]), norm(r["away_team"]))
        out.setdefault(k, []).append({
            "ts": r["snapshot_ts"], "commence": r["commence_time"],
            "market": r["market"], "side": r["side"], "point": r["point"], "price": r["price"]})
    for v in out.values():
        v.sort(key=lambda x: x["ts"])
    return out


def load_bsd():
    """events(队名->id) + odds consensus + preds expected_goals
    -> {(nh,na): {"odds": {...}, "eg": {...}}}"""
    ev_id = {}
    for fn in glob.glob(os.path.join(ROOT, "analysis_records", "bzzoiro_events_*.json")):
        try:
            evs = json.load(io.open(fn, encoding="utf-8"))
        except Exception:
            continue
        for e in _ev_list(evs):
            if not isinstance(e, dict):
                continue
            ev_id.setdefault((norm(_tname(e.get("home_team"))), norm(_tname(e.get("away_team")))), e.get("id"))
    odds, preds = {}, {}
    for fn in glob.glob(os.path.join(ROOT, "analysis_records", "bsd_odds_*.json")):
        try:
            odds.update(json.load(io.open(fn, encoding="utf-8")))
        except Exception:
            pass
    for fn in glob.glob(os.path.join(ROOT, "analysis_records", "bsd_predictions_*.json")):
        try:
            preds.update(json.load(io.open(fn, encoding="utf-8")))
        except Exception:
            pass
    out = {}
    for k, eid in ev_id.items():
        o = odds.get(eid) or {}
        p = preds.get(eid) or {}
        if o or p:
            out[k] = {"odds": o.get("consensus") or {}, "eg": (p.get("expected_goals") or {})}
    return out


def parse_bet(name):
    n = str(name).replace(" ", "")
    m = re.match(r"^(小|大)([\d.]+)$", n)
    if m:
        return ("totals", "under" if m.group(1) == "小" else "over", float(m.group(2)))
    m = re.match(r"^让球(主|客)\(([+-]?[\d.]+)\)$", n)
    if m:
        return ("spreads", "home" if m.group(1) == "主" else "away", float(m.group(2)))
    m = re.match(r"^让球(主|客)([+-]?[\d.]+)$", n)
    if m:
        return ("spreads", "home" if m.group(1) == "主" else "away", float(m.group(2)))
    return (None, None, None)


def snap_price(snap_rows, market, side, line):
    """取该盘最新一条赛前快照价(snapshot_ts<=kickoff), 无则None"""
    best = None
    for r in snap_rows:
        if r["market"] != market or r["side"] != side:
            continue
        pt = r["point"]
        if pt is None or abs(float(pt) - line) > 1e-9:
            continue
        best = r  # 已按ts升序, 覆盖即最新
    return best["price"] if best else None


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=os.path.join(ROOT, "analysis_records", "bet_ledger.csv"))
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    scores = load_scores()
    snaps = load_snapshots()
    bsd = load_bsd()
    led = pd.read_csv(args.ledger)
    settled = led[led["status"] == "已结算"].copy()
    # 隔离: 剔除赛后才拉盘
    leak = settled[settled["snap_age_h"].fillna(999) < 0]
    settled = settled[settled["snap_age_h"].fillna(999) >= 0]

    rows = []
    for _, r in settled.iterrows():
        nh, na = norm(r["home"]), norm(r["away"])
        mkt, side, line = parse_bet(r["bet_name"])
        score = scores.get((r["league"], nh, na)) or scores.get((r["league"], na, nh))
        sp = snaps.get((nh, na)) or snaps.get((na, nh))
        bsd_row = bsd.get((nh, na)) or bsd.get((na, nh))
        sp_price = snap_price(sp, mkt, side, line) if (sp and mkt) else None
        sp_ev = (r["prob"] * sp_price - 1) if (sp_price is not None and pd.notna(r["prob"])) else None
        eg = bsd_row["eg"] if bsd_row else {}
        cons = bsd_row["odds"] if bsd_row else {}
        cons_key = "under_%d_goals" % int(round(line * 10)) if side == "under" else "over_%d_goals" % int(round(line * 10))
        cons_price = cons.get(cons_key) if cons else None
        cons_ev = (r["prob"] * cons_price - 1) if cons_price is not None and pd.notna(r["prob"]) else None
        rows.append({
            "league": r["league"], "match": r["match"], "date": r["date"],
            "bet": r["bet_name"], "odds": r["odds"], "prob": r["prob"], "ev": r["ev"],
            "star": r["star"], "veto": r["veto"], "snap_age_h": r["snap_age_h"],
            "result": r["result"], "ret": r["ret"], "pnl": r["pnl"],
            "score": score, "snap_price": sp_price, "snap_ev": sp_ev,
            "bsd_eg_home": eg.get("home"), "bsd_eg_away": eg.get("away"),
            "bsd_cons_price": cons_price, "bsd_cons_ev": cons_ev,
            "mkt": mkt, "line": line,
        })

    # 汇总
    n = len(rows); with_score = sum(1 for x in rows if x["score"]); with_snap = sum(1 for x in rows if x["snap_price"] is not None)
    with_bsd = sum(1 for x in rows if x["bsd_cons_price"] is not None)
    print("无泄漏样本:", n, "| 赛果覆盖:", with_score, "| 快照同盘价:", with_snap, "| BSD共识价:", with_bsd)

    def hit(x):
        return 1.0 if x["result"] == "win" else (0.5 if x["result"] == "half" else (None if x["result"] == "push" else 0.0))
    def roi(x):
        if x["result"] == "win": return x["odds"] - 1
        if x["result"] == "lose": return -1.0
        if x["result"] == "push": return 0.0
        return (x["ret"] - 1) if pd.notna(x["ret"]) else -0.5

    def grp(sub, label):
        if not sub: print(label, "n=0"); return
        hs = [h for x in sub if (h := hit(x)) is not None]
        print("%s: n=%d 命中=%.1f%% 平注ROI=%.2f%%" % (
            label, len(sub), 100 * sum(hs) / len(hs) if hs else 0, 100 * sum(roi(x) for x in sub) / len(sub)))

    grp(rows, "【全量】")
    for x in rows:
        x["gap"] = (x["odds"] - x["snap_price"]) if x["snap_price"] is not None else None
    snap_pos = [x for x in rows if x["snap_ev"] is not None and x["snap_ev"] > 0]
    snap_neg = [x for x in rows if x["snap_ev"] is not None and x["snap_ev"] <= 0]
    grp(snap_pos, "【快照价支持(快照EV>0)】")
    grp(snap_neg, "【快照价不支持(快照EV<=0, 假价值)】")
    cons_pos = [x for x in rows if x["bsd_cons_ev"] is not None and x["bsd_cons_ev"] > 0]
    grp(cons_pos, "【BSD共识支持(共识EV>0)】")
    # 价差分组: 账本odds vs 最新赛前快照价
    better = [x for x in rows if x["gap"] is not None and x["gap"] >= 0.05]
    same = [x for x in rows if x["gap"] is not None and -0.05 < x["gap"] < 0.05]
    worse = [x for x in rows if x["gap"] is not None and x["gap"] <= -0.05]
    grp(better, "【账本价优于快照价>=+0.05】")
    grp(same, "【账本价≈快照价(±0.05)】")
    grp(worse, "【账本价劣于快照价<=-0.05】")

    # 落盘
    TS = datetime.now().strftime("%Y%m%d")
    outp = os.path.join(ROOT, "analysis_records", "ledger_vs_data_%s.json" % TS)
    outm = os.path.join(ROOT, "analysis_records", "ledger_vs_data_%s.md" % TS)
    io.open(outp, "w", encoding="utf-8").write(json.dumps({
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "n": n, "leak_excluded": len(leak), "rows": rows}, ensure_ascii=False, indent=1))
    md = ["# 实盘账本 × 拉取数据 对比 (%d 注, 剔除%d条赛后才拉盘)" % (n, len(leak)), "",
          "| 联赛 | 比赛 | 注单 | 账本EV | 实际比分 | 结果 | 快照价 | 价差 | 快照EV | BSD预期 | BSD共识EV |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for x in rows:
        md.append("| %s | %s | %s(%.2f) | %.1f%% | %s | %s | %s | %s | %s | %s/%s | %s |" % (
            x["league"], x["match"], x["bet"], x["odds"], x["ev"] * 100,
            x["score"] or "?", x["result"],
            ("%.2f" % x["snap_price"]) if x["snap_price"] is not None else "-",
            ("%+.2f" % x["gap"]) if x["gap"] is not None else "-",
            ("%.1f%%" % (x["snap_ev"] * 100)) if x["snap_ev"] is not None else "-",
            x["bsd_eg_home"] if x["bsd_eg_home"] is not None else "?",
            x["bsd_eg_away"] if x["bsd_eg_away"] is not None else "?",
            ("%.1f%%" % (x["bsd_cons_ev"] * 100)) if x["bsd_cons_ev"] is not None else "-"))
    io.open(outm, "w", encoding="utf-8").write("\n".join(md))
    print("已存:", outp, "+", outm)


if __name__ == "__main__":
    main()
