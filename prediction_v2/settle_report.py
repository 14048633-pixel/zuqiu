"""账本 ROI 报表 CLI —— 验证闭环的"每50注一结算"
=================================================
用法：
  python settle_report.py [--ledger output/live_bets.jsonl] [--window 50]

汇总已结算注: 赢/走水/输、平注口径 ROI(1注=1本金)、分联赛/分月、累计 P&L；
达到窗口(默认50注)即输出"可判定"结论, 连续两期 ROI<0 触发"停用该方向"告警。
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src", "features"))


def load_entries(ledger_path):
    if not os.path.exists(ledger_path):
        return []
    with open(ledger_path, encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def report(ledger_path, window=50):
    entries = load_entries(ledger_path)
    settled = [e for e in entries if e.get("status") in ("win", "lose", "push")]
    pending = [e for e in entries if e.get("status") == "pending"]
    stake = 1.0
    pnl = 0.0
    wins = pushes = losses = 0
    by_league = defaultdict(lambda: {"n": 0, "pnl": 0.0})
    by_month = defaultdict(lambda: {"n": 0, "pnl": 0.0})
    for e in settled:
        odds = float(e.get("odds", 0))
        if e["status"] == "win":
            p = stake * (odds - 1)
            wins += 1
        elif e["status"] == "push":
            p = 0.0
            pushes += 1
        else:
            p = -stake
            losses += 1
        pnl += p
        by_league[e.get("league", "?")]["n"] += 1
        by_league[e.get("league", "?")]["pnl"] += p
        by_month[str(e.get("ts", ""))[:7] or "?"]["n"] += 1
        by_month[str(e.get("ts", ""))[:7] or "?"]["pnl"] += p

    decided = wins + losses
    win_rate = wins / decided if decided else None
    roi = pnl / (len(settled) * stake) if settled else None
    out = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ledger": ledger_path,
        "total_entries": len(entries),
        "settled": len(settled),
        "pending": len(pending),
        "wins": wins, "pushes": pushes, "losses": losses,
        "win_rate": round(win_rate, 4) if win_rate is not None else None,
        "roi_flat": round(roi, 4) if roi is not None else None,
        "total_pnl": round(pnl, 4),
        "by_league": {k: {"n": v["n"], "pnl": round(v["pnl"], 4)} for k, v in by_league.items()},
        "by_month": {k: {"n": v["n"], "pnl": round(v["pnl"], 4)} for k, v in sorted(by_month.items())},
        "window_ok": len(settled) >= window,
        "alerts": [],
    }
    if out["window_ok"] and roi is not None:
        out["alerts"].append(
            f"已满{window}注可判定: 平注ROI={roi:+.2%} 命中率={win_rate:.1%}"
            if roi > 0 else f"⚠️ 已满{window}注且ROI={roi:+.2%}<0, 连续两期如此应停用该方向")
    if not out["window_ok"]:
        out["alerts"].append(f"已结算{len(settled)}注, 距{window}注判定窗口还差{window - len(settled)}注")
    return out


def main():
    ap = argparse.ArgumentParser(description="v2 逐注账本 ROI 报表")
    ap.add_argument("--ledger", default=os.environ.get("V2_LEDGER") or
                    os.path.join(HERE, "output", "live_bets.jsonl"))
    ap.add_argument("--window", type=int, default=50)
    args = ap.parse_args()
    out = report(args.ledger, args.window)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print("\n".join("  - " + a for a in out["alerts"]))


if __name__ == "__main__":
    main()