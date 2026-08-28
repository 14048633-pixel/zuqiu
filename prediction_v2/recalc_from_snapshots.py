# -*- coding: utf-8 -*-
"""用最新 snapshots.csv(含 InferSports 亚盘) 重算指定比赛清单的方向.
用法: python recalc_from_snapshots.py --matches <scan json> [--archive <infersports archive json>]
"""
import sys, os, json, io, glob, re, unicodedata, collections
from datetime import datetime, timezone, timedelta
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
import scan_upcoming as su

SNAP = os.path.join(ROOT, "prediction_v2", "output", "odds_snapshots", "snapshots.csv")
BJT = timezone(timedelta(hours=8))

def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", s.lower())

def find_archive():
    cands = sorted(glob.glob(os.path.join(ROOT, "analysis_records", "infersports_lines_*.json")), key=os.path.getmtime)
    return cands[-1] if cands else None

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--matches", required=True)
    ap.add_argument("--archive", default="")
    args = ap.parse_args()
    ms = json.load(io.open(os.path.join(ROOT, args.matches), encoding="utf-8"))
    arch = None
    apath = args.archive or find_archive()
    if apath and os.path.exists(os.path.join(ROOT, apath)):
        arch = json.load(io.open(os.path.join(ROOT, apath), encoding="utf-8"))

    team_stats, lavg, index = su.load_team_stats()
    events, _ = su.parse_snapshots(SNAP)
    ev_by_id = {e["id"]: e for e in events}

    def best_event(m):
        home, away = m["home"], m["away"]
        lg = m.get("league", "")
        try:
            kt = datetime.fromisoformat(m.get("ko_utc", "").replace("Z", "+00:00"))
        except Exception:
            kt = None
        best, best_s = None, 0.0
        for e in events:
            if e["league"] != lg:
                continue
            if kt and abs((e["ct"] - kt).total_seconds()) > 3 * 3600:
                continue
            sh = _sim(e["home"], home)
            sa = _sim(e["away"], away)
            score = (sh + sa) / 2
            # 单侧强匹配加分
            if sh >= 0.7 and sa >= 0.35:
                score = max(score, sh * 0.8 + 0.1)
            if sa >= 0.7 and sh >= 0.35:
                score = max(score, sa * 0.8 + 0.1)
            if score > best_s:
                best, best_s = e, score
        return best, best_s

    def _sim(a, b):
        na, nb = norm(a), norm(b)
        if not na or not nb:
            return 0.0
        if na == nb:
            return 1.0
        if len(na) >= 6 and len(nb) >= 6 and (na in nb or nb in na):
            return 0.86
        import difflib
        return difflib.SequenceMatcher(None, na, nb).ratio()

    results = []
    for m in ms:
        ev, ev_s = best_event(m)
        if not ev or ev_s < 0.5:
            results.append({"home": m["home"], "away": m["away"], "league": m.get("league", ""),
                            "ko": m.get("ko_utc"), "status": "no_snapshot_event"})
            continue
        ev["coach_mods"] = {}
        try:
            r = su.analyze_match(ev, team_stats, lavg, index)
        except Exception as e:
            results.append({"home": m["home"], "away": m["away"], "league": m.get("league", ""),
                            "ko": m.get("ko_utc"), "status": "error", "err": str(e)[:200]})
            continue
        bb = r.get("best_bet")
        di = r.get("direction")
        results.append({
            "home": ev["home"], "away": ev["away"], "league": ev["league"],
            "ko": ev["ct"].astimezone(BJT).strftime("%m-%d %H:%M") if ev.get("ct") else None,
            "status": "ok",
            "lambda": r.get("lambda"), "wdl": r.get("wdl"), "market_fair": r.get("market_fair"),
            "direction": di["name"] if di else None,
            "dir_prob": round(di["prob"] * 100, 1) if di else None,
            "dir_odds": di["odds"] if di else None,
            "dir_ev": round(di["ev"] * 100, 1) if di and di.get("ev") is not None else None,
            "vetoed": di.get("vetoed") if di else None,
            "veto_reason": di.get("veto_reason") if di else None,
            "draw_warn": r.get("draw_warn"),
            "star": r.get("star"), "ev_tier": r.get("ev_tier"),
            "risk_tags": r.get("risk_tags"),
            "best_bet": bb and {"name": bb["name"], "prob": round(bb["prob"] * 100, 1),
                                "odds": bb["odds"], "ev": round(bb["ev"] * 100, 1),
                                "star": bb.get("star"), "ev_tier": bb.get("ev_tier")},
            "dir_consistency": r.get("dir_consistency"),
            "bets": r.get("bets"),
            "notes": r.get("notes"),
        })

    ts = datetime.now(BJT).strftime("%Y%m%d_%H%M")
    out = os.path.join(ROOT, "analysis_records", "recalc_infersports_%s.json" % ts)
    with io.open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print("saved ->", out)
    print()
    for r in results:
        if r.get("status") != "ok":
            print("SKIP %s vs %s [%s]" % (r.get("home"), r.get("away"), r.get("status")))
            continue
        bb = r.get("best_bet")
        bb_s = ("%s %.0f%% @%.2f EV%+.1f%% ★%d[%s]" % (bb["name"], bb["prob"], bb["odds"], bb["ev"], bb["star"], bb["ev_tier"])) if bb else "-无正EV-"
        dw = r.get("draw_warn") or {}
        dw_s = (" ⚠平局预警(市场%.0f%%)" % dw["market_draw_prob"]) if dw.get("market_draw_prob") else ""
        v = " ⛔否决(%s)" % r.get("veto_reason") if r.get("vetoed") else ""
        print("%s %s vs %s | λ%.2f | %s | best=%s%s%s" % (
            r.get("ko"), r.get("home"), r.get("away"), (r.get("lambda") or {}).get("sum", 0),
            r.get("direction") or "-", bb_s, dw_s, v))

if __name__ == "__main__":
    main()
