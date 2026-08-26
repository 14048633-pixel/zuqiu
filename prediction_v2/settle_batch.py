# -*- coding: utf-8 -*-
"""批量赛后结算 CLI (the-odds-api /scores 自动拉比分)
用法:
  python settle_batch.py [--fetch] [--league J1|中超|欧系|ALL]
来源存档:
  J1   -> analysis_records/20260815_J1第2轮_9场_重分析.json (match.en + best_bet)
  中超 -> analysis_records/20260815_csl_tonight.json (home_en/away_en + best_bet)
  欧系 -> analysis_records/20260815_scan_upcoming.json (39场, result.best_bet)
规则: 只结算 completed=True 场次; 让球含1/4、3/4盘拆半, 整数盘走水; 大小球2.5半球无走水。
"""
import argparse
import io as _io
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "src", "odds"))
sys.stdout.reconfigure(encoding="utf-8")

from api_router import OddsApiRouter
from src.live_odds import LEAGUE_SPORT_KEYS

BJT = timezone(timedelta(hours=8))
SPORT = dict(LEAGUE_SPORT_KEYS)
SPORT["西乙"] = "soccer_spain_segunda_division"
SPORT["英冠"] = "soccer_efl_champ"
SPORT["德乙"] = "soccer_germany_bundesliga2"

LEAGUES_39 = ["德乙", "荷甲", "西甲", "西乙", "英冠"]


def _norm(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _tokens(s):
    return set(re.findall(r"[a-z]{3,}", (s or "").lower()))


def _match_name(a, b):
    na, nb = _tokens(a), _tokens(b)
    if not na or not nb:
        return _norm(a) == _norm(b)
    return na == nb or na <= nb or nb <= na


def fetch_scores(sport_key, api_key, base_url, days=3):
    url = "%s/sports/%s/scores/?apiKey=%s&daysFrom=%d&dateFormat=iso" % (base_url, sport_key, api_key, days)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def split_line(hdp):
    """让球线拆子盘(十进制0.2/0.8按0.25/0.75处理): 0.25 -> [0, 0.5]; 0.75 -> [0.5, 1.0]; 其他 -> [hdp]"""
    sign = 1 if hdp >= 0 else -1
    q = sign * (round(abs(hdp) * 4) / 4.0)
    n = int(round(abs(q) * 4)) % 4
    if n == 1:   # 0.25
        base = q - sign * 0.25
        return [base, base + sign * 0.5]
    if n == 3:   # 0.75
        base = q - sign * 0.75
        return [base + sign * 0.5, base + sign * 1.0]
    return [q]


def settle_leg(name, odds, hg, ag):
    """返回 (result, 回报倍数). result: win/push/lose 或 half"""
    n = name.replace(" ", "")
    if n.startswith("让球主"):
        hdp = float(n.split("(")[1].rstrip(")"))
        subs = split_line(hdp)
        outs = []
        for sub in subs:
            d = (hg + sub) - ag
            outs.append("win" if d > 1e-9 else ("push" if abs(d) <= 1e-9 else "lose"))
        return _merge(outs, odds)
    if n.startswith("让球客"):
        hdp = float(n.split("(")[1].rstrip(")"))
        subs = split_line(hdp)
        outs = []
        for sub in subs:
            d = hg - (ag + sub)   # 客队受让sub后 vs 主队
            outs.append("win" if d < -1e-9 else ("push" if abs(d) <= 1e-9 else "lose"))
        return _merge(outs, odds)
    m = re.match(r"^(大|小)([\d.]+)", n)
    if m:
        line = float(m.group(2))
        tot = hg + ag
        if m.group(1) == "大":
            return ("win", odds) if tot > line else ("lose", 0.0)
        return ("win", odds) if tot < line else (("push", 1.0) if abs(tot - line) < 1e-9 else ("lose", 0.0))
    if n == "1X2主胜":
        return ("win", odds) if hg > ag else ("lose", 0.0)
    if n == "1X2平局":
        return ("win", odds) if hg == ag else ("lose", 0.0)
    if n == "1X2客胜":
        return ("win", odds) if hg < ag else ("lose", 0.0)
    return ("未知", None)


def pnl_for_result(res, ret):
    """单注盈亏: win/half=ret-1, push/未知=0, lose=ret-1 (全输-1, 半输-0.5; 曾把输单算成0致ROI虚高)."""
    if ret is None or res == "push":
        return 0.0
    return ret - 1.0


def _merge(outs, odds):
    if "lose" in outs:
        if "push" in outs and "win" not in outs:
            return ("lose", 0.5)   # 1/4盘半输: 退一半本金(修复: 曾误判全输)
        return ("lose", 0.0)
    if all(o == "win" for o in outs):
        return ("win", odds)
    if all(o == "push" for o in outs):
        return ("push", 1.0)
    return ("half", (1.0 + odds) / 2.0)  # 半赢: [win,push]


def load_targets():
    targets = []
    # J1
    d = json.load(_io.open(os.path.join(ROOT, "analysis_records", "20260815_J1第2轮_9场_重分析.json"), encoding="utf-8"))
    for m in d["matches"]:
        bb = m.get("best_bet") or {}
        if bb.get("name"):
            en = (m.get("en") or " vs ").split(" vs ")
            targets.append({"league": "J1", "match": m["match"], "home": en[0].strip(), "away": en[1].strip() if len(en) > 1 else "",
                            "bb": bb, "star": m.get("star", 0), "src": "J1重分析"})
    # 中超
    _csl_v2 = os.path.join(ROOT, "analysis_records", "20260815_csl_tonight_v2.json")
    _csl_path = _csl_v2 if os.path.exists(_csl_v2) else os.path.join(ROOT, "analysis_records", "20260815_csl_tonight.json")
    d = json.load(_io.open(_csl_path, encoding="utf-8"))
    for m in d["matches"]:
        bb = m.get("bb") or m.get("best_bet") or {}
        if bb.get("name"):
            targets.append({"league": "中超", "match": "%s vs %s" % (m.get("home", ""), m.get("away", "")),
                            "home": m.get("home_en", m.get("home", "")), "away": m.get("away_en", m.get("away", "")),
                            "bb": bb, "star": m.get("star", 0), "src": "中超今晚"})
    # 39场欧系 (排除已单独结算的 J1/中超, 防重复)
    _excl = {"J1", "中超"}
    d = json.load(_io.open(os.path.join(ROOT, "analysis_records", "20260815_scan_upcoming.json"), encoding="utf-8"))
    for m in d["matches"]:
        if m.get("league") in _excl:
            continue
        bb = (m.get("result") or {}).get("best_bet") or {}
        if bb.get("name"):
            targets.append({"league": m.get("league", ""), "match": "%s vs %s" % (m.get("home", ""), m.get("away", "")),
                            "home": m.get("home", ""), "away": m.get("away", ""), "bb": bb,
                            "star": bb.get("star", 0), "src": "39场欧系"})
    return targets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--league", default="ALL", help="ALL 或单联赛")
    args = ap.parse_args()
    router = OddsApiRouter(base_dir=HERE, project_root=ROOT)
    key, src = router.keys[0]
    base = router.meta.get(src)
    targets = load_targets()
    if args.league != "ALL":
        targets = [t for t in targets if t["league"] == args.league]
    print("== 批量结算: 目标注单 %d 条 ==" % len(targets))
    by_league = {}
    for t in targets:
        by_league.setdefault(t["league"], []).append(t)
    score_cache = {}
    quota = None
    if args.fetch:
        for lg, lst in by_league.items():
            try:
                evs = fetch_scores(SPORT[lg], key, base)
                score_cache[lg] = evs
            except Exception as e:
                print("  ⚠️ %s 拉比分失败: %r" % (lg, e))
        print("  ✔ 比分抓取完成")
    rows = []
    for lg, lst in by_league.items():
        evs = score_cache.get(lg) or []
        for t in lst:
            ev = None
            for e in evs:
                if e.get("completed") and _match_name(e.get("home_team"), t["home"]) and _match_name(e.get("away_team"), t["away"]):
                    ev = e
                    break
            if not ev:
                rows.append({**t, "status": "未完成/未匹配", "score": None, "result": None, "ret": None, "pnl": None})
                continue
            sc = {s["name"]: int(s["score"]) for s in (ev.get("scores") or [])}
            hg, ag = sc.get(ev["home_team"], 0), sc.get(ev["away_team"], 0)
            res, ret = settle_leg(t["bb"]["name"], float(t["bb"]["odds"]), hg, ag)
            pnl = 0.0 if ret is None else (ret - 1.0 if res != "push" and ret is not None else 0.0)
            rows.append({**t, "status": "已结算", "score": "%d-%d" % (hg, ag), "result": res, "ret": ret, "pnl": pnl})
            print("  %-22s %-14s %-8s %s %s" % (t["match"], t["bb"]["name"], res, "%d-%d" % (hg, ag), "✅" if res == "win" else ("◐" if res in ("push", "half") else "❌")))
    settled = [r for r in rows if r["status"] == "已结算"]
    wins = sum(1 for r in settled if r["result"] == "win")
    halves = sum(1 for r in settled if r["result"] == "half")
    pushes = sum(1 for r in settled if r["result"] == "push")
    losses = sum(1 for r in settled if r["result"] == "lose")
    pnl = sum(r["pnl"] or 0 for r in settled)
    roi = pnl / len(settled) if settled else None
    print()
    print("== 汇总: 已结算%d 赢%d 半赢%d 走水%d 输%d | 总P&L %+.1f | ROI %s ==" % (
        len(settled), wins, halves, pushes, losses, pnl, ("%+.1f%%" % (roi * 100)) if roi is not None else "-"))
    out = os.path.join(ROOT, "analysis_records", "%s_批量结算.json" % datetime.now(BJT).strftime("%Y%m%d_%H%M"))
    with _io.open(out, "w", encoding="utf-8") as f:
        json.dump({"time": datetime.now(BJT).isoformat(), "n_settled": len(settled), "wins": wins, "halves": halves,
                   "pushes": pushes, "losses": losses, "pnl": pnl, "roi": roi, "rows": rows}, f, ensure_ascii=False, indent=1)
    print("saved:", out)


if __name__ == "__main__":
    main()
