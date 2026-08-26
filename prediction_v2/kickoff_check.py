# -*- coding: utf-8 -*-
"""开盘临场盘口检查（定时任务入口）
用法:
  python kickoff_check.py --league J1 [--fetch]
  python kickoff_check.py --league 西甲 [--fetch]
逻辑:
  1) --fetch 时抓取最新赔率并追加快照
  2) 读取 pre-match 存档中的候选注单(场次/腿/原赔率/原盘口)
  3) 从最新快照提取临场盘口(ML/让球/大小球; 让球按线分组, 大小球优先2.5线)
  4) 按注单同一条线对比原价/原线 -> 判定(同步升盘降水=可信 / 升盘升水=诱盘 / 急速降水=大热必死 / 深盘升盘=诱热 / 无移动=维持)
  5) 写 analysis_records/YYYYMMDD_HHMM_盘口检查_<league>.json
"""
import argparse
import json
import io as _io
import os
import sys
import re
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "src", "odds"))
sys.stdout.reconfigure(encoding="utf-8")

from src.live_odds import load_snapshots, LEAGUE_SPORT_KEYS

BJT = timezone(timedelta(hours=8))
SNAP = os.path.join(HERE, "output", "odds_snapshots", "snapshots.csv")

# ---------------- pre-match 存档读取 ----------------
def load_pre(league):
    if league == "J1":
        d = json.load(_io.open(os.path.join(ROOT, "analysis_records", "20260815_J1第2轮_9场_重分析.json"), encoding="utf-8"))
        out = []
        for m in d["matches"]:
            odds = m.get("odds", {})
            spread = odds.get("spread", {}) or {}
            totals = odds.get("totals", {}) or {}
            ml = odds.get("ml", {}) or {}
            en = m.get("en", "").split(" vs ")
            out.append({
                "match": m["match"], "home": (en[0] if len(en) > 1 else ""), "away": (en[1] if len(en) > 1 else ""),
                "kickoff": m.get("kickoff_beijing", ""), "bets": m.get("bets", []) or [],
                "bb": m.get("best_bet"), "veto": m.get("veto", False), "star": m.get("star", 0),
                "pre_spread": {"line": spread.get("line"), "home": spread.get("home"),
                               "away": spread.get("away"), "book": spread.get("book")},
                "pre_totals": {"line": totals.get("line"), "over": totals.get("over"),
                               "under": totals.get("under"), "book": totals.get("book")},
                "pre_ml": {"home": ml.get("home"), "draw": ml.get("draw"), "away": ml.get("away")},
            })
        return out
    if league == "西甲":
        d = json.load(_io.open(os.path.join(ROOT, "analysis_records", "20260815_西甲_重预测.json"), encoding="utf-8"))
        out = []
        for m in d["matches"]:
            s31 = m.get("step31", {})
            h2h = m.get("step0_5", {}).get("h2h_odds") or [None, None, None]
            out.append({
                "match": m["match"], "home": m["match"].split(" vs ")[0], "away": m["match"].split(" vs ")[1],
                "kickoff": m.get("kickoff_beijing", ""), "bets": s31.get("bets", []) or [],
                "bb": s31.get("best_bet"), "veto": s31.get("veto", False), "star": s31.get("star", 0),
                "pre_spread": {}, "pre_totals": {},
                "pre_ml": {"home": h2h[0], "draw": h2h[1], "away": h2h[2]},
            })
        return out

    if league == "中超":
        _csl_v2 = os.path.join(ROOT, "analysis_records", "20260815_csl_tonight_v2.json")
        _csl_path = _csl_v2 if os.path.exists(_csl_v2) else os.path.join(ROOT, "analysis_records", "20260815_csl_tonight.json")
        d = json.load(_io.open(_csl_path, encoding="utf-8"))
        out = []
        for m in d["matches"]:
            o = m.get("odds", {}) or {}
            h2h = o.get("h2h", {}).get("prices", {}) or {}
            sp = o.get("spread", {}) or {}
            sp_p = sp.get("prices", {}) or {}
            tt = o.get("totals", {}) or {}
            tt_p = tt.get("prices", {}) or {}
            kt = ""
            if m.get("ct"):
                kt = datetime.fromisoformat(m["ct"].replace("Z", "+00:00")).astimezone(BJT).strftime("%Y-%m-%d %H:%M")
            out.append({
                "match": "%s vs %s" % (m["home"], m["away"]),
                "home": m.get("home_en", m["home"]), "away": m.get("away_en", m["away"]),
                "kickoff": kt, "bets": m.get("bets", []) or [], "bb": m.get("bb") or m.get("best_bet") or None,
                "veto": bool(m.get("star", 0) == 0 and m.get("risk")), "star": m.get("star", 0),
                "pre_spread": {"line": sp.get("line"), "home": sp_p.get("home"), "away": sp_p.get("away"), "book": sp.get("book")},
                "pre_totals": {"line": tt.get("line"), "over": tt_p.get("over"), "under": tt_p.get("under"), "book": tt.get("book")},
                "pre_ml": {"home": h2h.get("home"), "draw": h2h.get("draw"), "away": h2h.get("away")},
            })
        return out

    return []

# ---------------- 临场盘口提取 ----------------
def _norm(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())

def _tokens(s):
    return set(re.findall(r"[a-z]{3,}", (s or "").lower()))

def _match_name(a, b):
    """整名或词集子集匹配(处理 Sanfrecce Hiroshima vs Hiroshima Sanfrecce FC 类差异)."""
    na, nb = _tokens(a), _tokens(b)
    if not na or not nb:
        return _norm(a) == _norm(b)
    return na == nb or na <= nb or nb <= na

def live_lines(df, home, away):
    """返回 {ts, ml, spreads:{abs_line:{line,home,away,orr,book}}, totals:{line:{over,under,orr,book}}}"""
    if df is None or df.empty:
        return None
    nh, na = _norm(home), _norm(away)
    mask = df["home_team"].astype(str).map(_norm).eq(nh) & df["away_team"].astype(str).map(_norm).eq(na)
    sub = df[mask]
    if sub.empty:
        # 词集子集兜底(整名不一致但词集匹配)
        m2 = df.apply(lambda r: _match_name(str(r["home_team"]), home) and _match_name(str(r["away_team"]), away), axis=1)
        sub = df[m2]
    if sub.empty:
        return None
    out = {"ts": sub["snapshot_ts"].max().isoformat(), "ml": None, "spreads": {}, "totals": {}}
    h = sub[(sub["market"] == "h2h") & (sub["side"] == "home")]
    dd = sub[(sub["market"] == "h2h") & (sub["side"] == "draw")]
    a = sub[(sub["market"] == "h2h") & (sub["side"] == "away")]
    if not h.empty and not dd.empty and not a.empty:
        for bk in h["bookmaker"].unique():
            hp = h[h["bookmaker"] == bk].sort_values("snapshot_ts")["price"].astype(float).iloc[-1]
            dp = dd[dd["bookmaker"] == bk].sort_values("snapshot_ts")["price"].astype(float).iloc[-1]
            ap = a[a["bookmaker"] == bk].sort_values("snapshot_ts")["price"].astype(float).iloc[-1]
            if hp and dp and ap:
                orr = 1 / hp + 1 / dp + 1 / ap
                if out["ml"] is None or orr < out["ml"]["orr"]:
                    out["ml"] = {"home": float(hp), "draw": float(dp), "away": float(ap),
                                 "orr": round(orr, 4), "book": bk, "ts": sub["snapshot_ts"].max().isoformat()}
    sp = sub[sub["market"] == "spreads"]
    if not sp.empty:
        for line_abs, g in sp.groupby(sp["point"].astype(float).abs()):
            best = None
            for bk, gg in g.groupby("bookmaker"):
                home_px = gg[gg["side"] == "home"].sort_values("snapshot_ts")
                away_px = gg[gg["side"] == "away"].sort_values("snapshot_ts")
                if home_px.empty or away_px.empty:
                    continue
                hp = float(home_px["price"].astype(float).iloc[-1])
                ap = float(away_px["price"].astype(float).iloc[-1])
                if not hp or not ap:
                    continue
                orr = 1 / hp + 1 / ap
                if best is None or orr < best["orr"]:
                    best = {"line": float(home_px.iloc[-1]["point"]), "home": hp, "away": ap,
                            "orr": round(orr, 4), "book": bk,
                            "ts": max(home_px.iloc[-1]["snapshot_ts"], away_px.iloc[-1]["snapshot_ts"]).isoformat()}
            if best:
                out["spreads"][round(line_abs, 2)] = best
    tt = sub[sub["market"] == "totals"]
    if not tt.empty:
        for line, g in tt.groupby(tt["point"].astype(float)):
            best = None
            for bk, gg in g.groupby("bookmaker"):
                op = gg[gg["side"] == "over"].sort_values("snapshot_ts")
                up = gg[gg["side"] == "under"].sort_values("snapshot_ts")
                if op.empty or up.empty:
                    continue
                ov = float(op["price"].astype(float).iloc[-1]); un = float(up["price"].astype(float).iloc[-1])
                if not ov or not un:
                    continue
                orr = 1 / ov + 1 / un
                if best is None or orr < best["orr"]:
                    best = {"over": ov, "under": un, "orr": round(orr, 4), "book": bk,
                            "ts": max(op.iloc[-1]["snapshot_ts"], up.iloc[-1]["snapshot_ts"]).isoformat()}
            if best:
                out["totals"][round(float(line), 2)] = best
    return out

# ---------------- 判定 ----------------
def _pick_nearest(d, want, key_getter):
    if not d:
        return None
    best = None
    for k, v in d.items():
        if best is None or abs(k - want) < abs(best[0] - want):
            best = (k, v)
    return best

def verdict_for_leg(name, pre_price, live):
    if not live:
        return "无临场快照", "按原判, 无法检查", None
    if name.startswith("让球"):
        side = name[2]
        hdp = float(name.split("(")[1].rstrip(")"))
        abs_h = abs(hdp)
        spreads = live.get("spreads", {})
        if not spreads:
            return "临场缺让球盘", "按原判", None
        # 优先找与注单同线(abs差<0.01); 否则最近线但差>=0.25标人工复核
        exact = None
        for k, v in spreads.items():
            if abs(k - abs_h) < 0.01:
                exact = (k, v)
                break
        if exact:
            grp = exact[1]
            line_gap = 0.0
        else:
            hit = _pick_nearest(spreads, abs_h, None)
            grp = hit[1]
            line_gap = abs(hit[0] - abs_h)
            if line_gap >= 0.5:
                return "临场无同线盘(原线%.2f/现主盘%.2f), 建议人工核对" % (abs_h, hit[0]), "人工复核", None
        live_line = grp["line"]
        live_price = grp["home"] if side == "主" else grp["away"]
        pre_home_line = hdp if side == "主" else -hdp
        line_move = round(live_line - pre_home_line, 2)
        favor = line_move if side == "主" else -line_move
        return _judge(pre_price, live_price, line_move, favor, "让球", abs_h, live_line, side, grp.get("book", "?"))
    if name.startswith(("大", "小")):
        line = float(name[1:])
        hit = _pick_nearest(live.get("totals", {}), 2.5, None)
        if not hit:
            return "临场缺大小球盘", "按原判", None
        grp = hit[1]
        live_line = hit[0]
        live_price = grp["over"] if name.startswith("大") else grp["under"]
        line_move = round(live_line - line, 2)
        favor = -line_move if name.startswith("大") else line_move
        return _judge(pre_price, live_price, line_move, favor, "大小球", line, live_line, "大" if name.startswith("大") else "小", grp.get("book", "?"))
    return "非让球/大小球腿", "按原判", None

def _judge(pre_price, live_price, line_move, favor, mkt, pre_line, live_line, side, book):
    """favor=盘口对注单持有者是否更有利(主:线变高=有利; 客:主让变深=有利). 判定以持有者视角."""
    if not pre_price or not live_price:
        return "缺价", "按原判", None
    price_delta = round(live_price - pre_price, 3)
    line_txt = "线%.2f→%.2f" % (pre_line, live_line) if line_move else "线不变"
    deep = abs(pre_line) >= 1.0 if mkt == "让球" else False
    if deep and favor <= -0.25:
        return "深盘升盘(诱热,难穿盘)", "放弃", {"line_move": line_move, "price_delta": price_delta}
    if favor >= 0.25 and price_delta < -0.05:
        return "盘口利好+降水(真实)", "维持/可加信心", {"line_move": line_move, "price_delta": price_delta}
    if favor >= 0.25 and price_delta > 0.05:
        return "盘口利好但升水(造势诱盘)", "降星", {"line_move": line_move, "price_delta": price_delta}
    if favor <= -0.25:
        return "盘口利空(反方向移动)", "降星/放弃", {"line_move": line_move, "price_delta": price_delta}
    if price_delta <= -0.20:
        return "急速降水%.2f(大热必死)" % price_delta, "放弃", {"line_move": line_move, "price_delta": price_delta}
    if price_delta <= -0.05:
        return "稳步降水%.2f(自然涌入)" % price_delta, "维持", {"line_move": line_move, "price_delta": price_delta}
    if price_delta >= 0.10:
        return "升水%.2f(资金背离)" % price_delta, "降星", {"line_move": line_move, "price_delta": price_delta}
    return "无实质移动(%s)" % line_txt, "维持原判", {"line_move": line_move, "price_delta": price_delta}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", choices=["J1", "西甲", "中超"], default="J1")
    ap.add_argument("--fetch", action="store_true", help="先抓最新赔率")
    ap.add_argument("--now", default=None, help="检查时间 HH:MM(缺省=当前)")
    args = ap.parse_args()
    now = datetime.now(BJT) if not args.now else datetime.strptime(args.now, "%H:%M").replace(tzinfo=BJT)
    print("== %s 开盘盘口检查 @ %s ==" % (args.league, now.strftime("%m-%d %H:%M")))

    if args.fetch:
        import fetch_live_odds as flo
        from api_router import OddsApiRouter
        router = OddsApiRouter(base_dir=HERE, project_root=ROOT)
        if not router.available():
            print("❌ 无赔率key, 仅用现有快照")
        else:
            sport = LEAGUE_SPORT_KEYS.get(args.league)
            rows, quota, sel, err = flo._fetch_with_failover(router, args.league, sport,
                                                              flo.DEFAULT_MARKETS, flo.DEFAULT_REGIONS)
            if rows:
                n = flo.append_snapshots(SNAP, rows)
                print("✔ 已抓取并追加 %d 行(总%d), 剩余配额=%s" % (len(rows), n, quota.get("remaining")))
            else:
                print("⚠️ 抓取失败: %s" % err)

    df = load_snapshots(SNAP)
    pre = load_pre(args.league)
    if not pre:
        print("❌ 无 pre-match 存档")
        sys.exit(1)
    report = {"time": now.isoformat(), "league": args.league, "rows": []}
    for m in pre:
        if m["kickoff"]:
            kt = datetime.strptime(m["kickoff"], "%Y-%m-%d %H:%M").replace(tzinfo=BJT)
            if kt < now:
                continue
        live = live_lines(df, m["home"], m["away"])
        bb = m["bb"]
        ml_note = None
        if live and live.get("ml") and m.get("pre_ml", {}).get("home"):
            pml, lml = m["pre_ml"]["home"], live["ml"]["home"]
            if pml and lml and abs(lml - pml) >= 0.30:
                ml_note = "ML主胜 %.2f->%.2f(大幅异动, 人工复核)" % (pml, lml)
        row = {"match": m["match"], "kickoff": m["kickoff"], "bb": bb,
               "veto": m["veto"], "star": m["star"], "live": live, "ml_note": ml_note}
        if not bb:
            row["verdict"] = "否决" if m["veto"] else "无单"
            row["advice"] = "不检查"
            print("%s | %s | 跳过" % (m["match"], row["verdict"]))
        else:
            v, adv, detail = verdict_for_leg(bb["name"], bb["odds"], live)
            row["verdict"], row["advice"], row["detail"] = v, adv, detail
            if ml_note:
                row["ml_note"] = ml_note
                adv = adv + "；" + ml_note
            ml_txt = ""
            if live and live.get("ml"):
                ml_txt = "ML %.2f/%.2f/%.2f(%s)" % (live["ml"]["home"], live["ml"]["draw"], live["ml"]["away"], live["ml"]["book"])
            print("%s | %s @%.2f | %s | %s -> %s" % (m["match"], bb["name"], bb["odds"], ml_txt, v, adv))
        report["rows"].append(row)

    out = os.path.join(ROOT, "analysis_records", "%s_%s_盘口检查.json" % (now.strftime("%Y%m%d_%H%M"), args.league))
    with _io.open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print("saved:", out)

if __name__ == "__main__":
    main()
