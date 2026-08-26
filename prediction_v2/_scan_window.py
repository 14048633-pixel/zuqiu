# -*- coding: utf-8 -*-
"""窗口扫描: 未来 N 小时即将开赛 + 平局预警输出 (复用 scan_upcoming.analyze_match)"""
import sys, json, os, io, collections
from datetime import datetime, timezone, timedelta
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import scan_upcoming as su

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BJT = timezone(timedelta(hours=8))
SNAP = os.path.join(ROOT, "prediction_v2", "output", "odds_snapshots", "snapshots.csv")
WINDOW_H = float(os.environ.get("SCAN_WINDOW_H", "36"))

def main():
    ts, lavg, index = su.load_team_stats()
    out, _ = su.parse_snapshots(SNAP)
    now = datetime.now(BJT)
    lo, hi = now - timedelta(minutes=30), now + timedelta(hours=WINDOW_H)
    rows = []
    n_draw_warn = 0
    n_bet = 0
    for m in out:
        ct = m["ct"].astimezone(BJT)
        if not (lo <= ct <= hi):
            continue
        r = su.analyze_match(m, ts, lavg, index)
        dw = r.get("draw_warn")
        if dw:
            n_draw_warn += 1
        if r.get("best_bet"):
            n_bet += 1
        bb = r.get("best_bet")
        bb_s = ("%s %.0f%% @%.2f EV%+.1f%% ★%d[%s]" % (bb["name"], bb["prob"]*100, bb["odds"], bb["ev"]*100,
                bb.get("star", 0), bb.get("ev_tier", "?"))) if bb else "-无正EV-"
        di = r.get("direction")
        if di:
            mk_s = ("市场%.0f%%" % (di["market_fair"]*100)) if di.get("market_fair") is not None else "市场-"
            dir_s = "%s %.0f%%@%.2f(%s)" % (di["name"], di["prob"]*100, di["odds"], mk_s)
            if di.get("vetoed"):
                dir_s += " ⛔否决"
            if di.get("wdl_name"):
                wmk = ("市场%.0f%%" % (di["wdl_market_fair"]*100)) if di.get("wdl_market_fair") is not None else "市场-"
                dir_s += " | %s %.0f%%(%s)" % (di["wdl_name"], di["wdl_prob"]*100, wmk)
            if di.get("draw_warn"):
                dir_s += " ⚠平局预警(市场%.0f%%)" % di["draw_warn"]["market_draw_prob"]
        else:
            dir_s = "-无盘口-"
        risk_s = (" 风险:%s" % ",".join(r["risk_tags"])) if r["risk_tags"] else ""
        rows.append({
            "ct": ct.strftime("%m-%d %H:%M"), "league": m["league"], "home": m["home"], "away": m["away"],
            "lam": r.get("lambda", {}), "src": r.get("data_src", {}),
            "dir": di, "best": bb, "risk": r.get("risk_tags", []),
            "draw_warn": dw, "star": r.get("star"), "ev_tier": r.get("ev_tier"),
            "upset": (r.get("upset") or {}).get("level"),
            "wdl": r.get("wdl"), "market_fair": r.get("market_fair"),
            "notes": r.get("notes", []),
        })
        print("%s %-4s %s vs %s | λ%.2f/%.2f | 方向[%s] | BEST[%s] | %s%s" % (
            ct.strftime("%m-%d %H:%M"), m["league"], m["home"], m["away"],
            r["lambda"]["home"], r["lambda"]["away"], dir_s, bb_s,
            ("冷门:%s(%d)" % ((r.get("upset") or {}).get("level"), (r.get("upset") or {}).get("count"))), risk_s))
    rows.sort(key=lambda x: x["ct"])
    os.makedirs(os.path.join(ROOT, "analysis_records", "scans"), exist_ok=True)
    outp = os.path.join(ROOT, "analysis_records", "scans", "scan_window_%s.json" % now.strftime("%Y%m%d_%H%M"))
    json.dump({"ts": now.isoformat(), "window_h": WINDOW_H, "n": len(rows),
               "n_draw_warn": n_draw_warn, "n_bet": n_bet, "matches": rows},
              open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n共%d场(未来%.0fh) | 平局预警%d场 | 可出best_bet%d场" % (len(rows), WINDOW_H, n_draw_warn, n_bet))
    print("saved:", outp)

if __name__ == "__main__":
    main()