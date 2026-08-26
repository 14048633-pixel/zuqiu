# -*- coding: utf-8 -*-
"""临场盘定时重扫: 快照窗口(02:30-03:30 BJT) + 重点overlay, 输出结论JSON."""
import sys, json, os, io
from datetime import datetime, timezone, timedelta
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import scan_upcoming as su

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BJT = timezone(timedelta(hours=8))
SNAP = os.path.join(ROOT, "prediction_v2", "output", "odds_snapshots", "snapshots.csv")

def main():
    ts, lavg, index = su.load_team_stats()
    out, _ = su.parse_snapshots(SNAP)
    now = datetime.now(BJT)
    lo, hi = now - timedelta(minutes=30), now + timedelta(minutes=120)
    rows = []
    for m in out:
        ct = m["ct"].astimezone(BJT)
        if lo <= ct <= hi:
            r = su.analyze_match(m, ts, lavg, index)
            bb = r.get("best_bet")
            rows.append({"ct": ct.strftime("%m-%d %H:%M"), "league": m["league"],
                         "home": m["home"], "away": m["away"],
                         "best": None if bb is None else {"name": bb["name"], "ev": round(bb["ev"], 3), "star": bb.get("star")},
                         "dir": (r.get("direction") or {}).get("name"),
                         "risk": [t for t in r.get("risk_tags", []) if "否决" in t or "禁出" in t],
                         "lam": r.get("lambda", {}).get("sum")})
    outp = os.path.join(ROOT, "analysis_records", "relaunch_%s.json" % now.strftime("%m%d_%H%M"))
    json.dump({"ts": now.isoformat(), "matches": rows}, io.open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for x in rows:
        flag = " | " + ";".join(x["risk"]) if x["risk"] else ""
        bb = ("BEST:" + x["best"]["name"] + " ev" + str(x["best"]["ev"]) + " ★" + str(x["best"]["star"])) if x["best"] else "无单"
        print(x["ct"], x["league"], x["home"], "vs", x["away"], "| 方向", x["dir"], "|", bb, flag)
    print("saved", outp, len(rows))

if __name__ == "__main__":
    main()