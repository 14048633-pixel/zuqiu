# -*- coding: utf-8 -*-
"""实盘推荐追踪闭环: 推荐落库 / 赛果回填 / 统计报告。

数据: strategy_data/live_tracker.json (新系统追踪)
记录状态: open(待赛) -> won / lost / push(走盘) / void(作废)
规则(沿用旧系统 RULE_CHANGE_POLICY 思路):
  - 记录必含赔率, 缺赔率标记 odds_missing, 不参与 ROI 统计
  - 样本 < 100 条不出结论
  - odds_source=estimated 的记录在统计中单独分组(估计赔率不可靠)

CLI:
  python tracker.py record <match_id>           # 从分析记录落库(也可由 analyze.py 自动)
  python tracker.py settle <match_id> <hg> <ag>
  python tracker.py report
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from config import ROOT

TRACK_FILE = ROOT / "strategy_data" / "live_tracker.json"
MIN_SAMPLE = 100          # 结论样本门槛
STOP_LOSS = 0.20          # 与 config daily_loss_stop 对应(报告参考)


def _empty() -> list:
    return []


def load() -> list:
    if not TRACK_FILE.exists():
        return _empty()
    try:
        with open(TRACK_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return _empty()


def save(records: list) -> bool:
    """落盘。成功返回 True; 沙箱/权限/文件占用等失败返回 False(打印警告, 不抛异常)。"""
    try:
        TRACK_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = TRACK_FILE.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        tmp.replace(TRACK_FILE)
        return True
    except OSError as e:
        print(f"[tracker] 落盘失败(沙箱/权限/文件占用): {e}")
        print("[tracker] 本次记录未落盘(不影响分析); 可 --no-track 关闭追踪")
        return False


def match_id(date, league, home, away) -> str:
    return f"{date}_{league}_{home}_vs_{away}"


def record(res: dict) -> dict:
    """从 analyze_match 结果构建并追加一条追踪记录。

    res 需含: home/away/league/date/model_prob/market_prob/market_odds/
              edge/ev_unit/stars/best_pick/odds_estimated
    返回写入的记录(幂等: 同 match_id 已存在则更新而非重复)。
    """
    records = load()
    mid = match_id(res["date"].date(), res["league"], res["home"], res["away"])
    p = res["model_prob"]
    mkt_prob = res["market_prob"]
    odds = res["market_odds"]
    mkt = res.get("mkt", "1x2")
    line = res.get("line")
    if mkt == "ou":
        mid = mid + "#ou"   # OU 与 1X2 同场不同腿, id 必须区分(2026-09-04)
        # OU 腿: 大=0 / 小=1, odds 单元素
        pick_idx = 0 if str(res.get("best_pick", "")).startswith("大") else 1
        odds_list = [float(x) if x else None for x in (odds if isinstance(odds, (list, tuple)) else [odds])]
        odds_ok = bool(odds_list and odds_list[0] and odds_list[0] > 1)
    else:
        mkt = "1x2"
        pick_idx = {"主胜": 0, "平局": 1, "客胜": 2}.get(res.get("best_pick"), 0)
        odds_list = [float(x) if x else None for x in odds]
        odds_ok = bool(odds_list and all(o and o > 1 for o in odds_list))
    rec = {
        "id": mid,
        "date": str(res["date"].date()),
        "league": res["league"],
        "home": res["home"],
        "away": res["away"],
        "pick": res.get("best_pick"),
        "pick_idx": pick_idx,
        "mkt": mkt,
        "line": line if mkt == "ou" else None,
        "model_prob": [round(float(x), 4) for x in p],
        "market_prob": [round(float(x), 4) for x in mkt_prob] if mkt_prob else None,
        "odds": odds_list,
        "odds_source": "estimated" if res.get("odds_estimated") else "live",
        "odds_missing": not odds_ok,
        "edge": round(float(res.get("edge", 0.0)), 4),
        "ev": round(float(res.get("ev_unit", 0.0)), 4),
        "stars": int(res.get("stars", 0)),
        "status": "open",
        "actual_hg": None,
        "actual_ag": None,
        "settled_date": None,
        "profit_pct": None,
    }
    idx = next((i for i, r in enumerate(records) if r["id"] == mid), None)
    if idx is None:
        records.append(rec)
    else:
        # 已存在: 保留已结算字段, 只更新推荐侧(避免覆盖赛果)
        old = records[idx]
        if old["status"] == "open":
            records[idx] = rec
        else:
            rec["status"] = old["status"]
            rec["actual_hg"] = old["actual_hg"]
            rec["actual_ag"] = old["actual_ag"]
            rec["settled_date"] = old["settled_date"]
            rec["profit_pct"] = old["profit_pct"]
            records[idx] = rec
    save(records)
    return rec


def _settle_one(rec: dict, hg: int, ag: int, settled_date: str) -> dict:
    """按推荐方向结算单条记录。返回更新后的 rec。"""
    if rec["status"] != "open":
        return rec
    rec["actual_hg"] = int(hg)
    rec["actual_ag"] = int(ag)
    rec["settled_date"] = settled_date
    odds = rec.get("odds") or []
    mkt = rec.get("mkt", "1x2")
    if mkt == "ou":
        # OU 结算: 总进球 vs line (2.5 无走水; 整数线走水留待扩展)
        line = rec.get("line", 2.5)
        price = odds[0] if odds else None
        if rec.get("odds_missing") or not price or price <= 1:
            rec["status"] = "void"
            rec["profit_pct"] = None
            return rec
        total = int(hg) + int(ag)
        over = str(rec.get("pick", "")).startswith("大")
        if (total > line) if over else (total < line):
            rec["status"] = "won"
            rec["profit_pct"] = round(price - 1.0, 4)
        else:
            rec["status"] = "lost"
            rec["profit_pct"] = -1.0
        return rec
    actual = 0 if hg > ag else (1 if hg == ag else 2)
    pick_idx = rec.get("pick_idx", 0)
    if rec.get("odds_missing") or not odds or odds[pick_idx] is None or odds[pick_idx] <= 1:
        rec["status"] = "void"
        rec["profit_pct"] = None
        return rec
    if actual == pick_idx:
        rec["status"] = "won"
        rec["profit_pct"] = round(rec["odds"][pick_idx] - 1.0, 4)  # 以 stake=1 计, 与回测同口径
    else:
        rec["status"] = "lost"
        rec["profit_pct"] = -1.0
    return rec


def settle(match_id_str: str, hg: int, ag: int, settled_date: str | None = None) -> dict | None:
    """按 id 结算。返回更新后的记录, 未找到返回 None。"""
    import datetime as dt
    settled_date = settled_date or dt.date.today().isoformat()
    records = load()
    for i, rec in enumerate(records):
        if rec["id"] == match_id_str and rec["status"] == "open":
            records[i] = _settle_one(rec, hg, ag, settled_date)
            save(records)
            return records[i]
    return None


def report() -> dict:
    """统计: 总体 + 按 odds_source/星级 分组。样本 < MIN_SAMPLE 注明不出结论。"""
    records = load()
    settled = [r for r in records if r["status"] in ("won", "lost")]
    def _stats(sub):
        if not sub:
            return {"n": 0}
        n = len(sub)
        wins = sum(1 for r in sub if r["status"] == "won")
        profit = sum(r["profit_pct"] or 0.0 for r in sub)
        stake = float(n)
        return {
            "n": n,
            "hit_rate": round(wins / n, 4),
            "profit_units": round(profit, 4),
            "roi": round(profit / stake, 4) if stake else None,
        }
    out = {
        "total_records": len(records),
        "open": sum(1 for r in records if r["status"] == "open"),
        "settled": len(settled),
        "all": _stats(settled),
        "by_source": {
            "live": _stats([r for r in settled if r["odds_source"] == "live"]),
            "estimated": _stats([r for r in settled if r["odds_source"] == "estimated"]),
        },
        "by_stars": {str(s): _stats([r for r in settled if r["stars"] == s])
                     for s in sorted({r["stars"] for r in settled})},
        "conclusion_ready": len(settled) >= MIN_SAMPLE,
    }
    return out


def _self_test() -> None:
    import datetime as dt
    import tempfile

    import pandas as pd
    global TRACK_FILE
    saved = TRACK_FILE
    with tempfile.TemporaryDirectory() as td:
        TRACK_FILE = Path(td) / "tracker_test.json"
        res = {
            "home": "A", "away": "B", "league": "T",
            "date": pd.Timestamp("2024-01-01"),
            "model_prob": [0.6, 0.25, 0.15], "market_prob": [0.55, 0.27, 0.18],
            "market_odds": (1.8, 3.6, 5.0), "odds_estimated": True,
            "edge": 0.05, "ev_unit": 0.08, "stars": 3, "best_pick": "主胜",
        }
        rec = record(res)
        assert rec["status"] == "open"
        assert rec["odds_source"] == "estimated"
        assert not rec["odds_missing"]
        # 结算: 主胜命中(2-0)
        s = settle(rec["id"], 2, 0, "2024-01-02")
        assert s["status"] == "won"
        assert abs(s["profit_pct"] - 0.8) < 1e-9, s["profit_pct"]
        # 再记一条并输
        res2 = dict(res, home="C", away="D")
        res2["date"] = pd.Timestamp("2024-01-03")
        res2["best_pick"] = "客胜"
        rec2 = record(res2)
        settle(rec2["id"], 0, 0, "2024-01-04")  # 平局, 客胜未中 -> lost
        rep = report()
        assert rep["settled"] == 2
        assert rep["by_source"]["estimated"]["n"] == 2
        assert rep["conclusion_ready"] is False  # 样本不足
    TRACK_FILE = saved
    print("== tracker 自检通过 ==")


def main(argv=None) -> int:
    argv = argv if argv is not None else list(sys.argv[1:])
    if not argv:
        print(__doc__)
        return 0
    cmd = argv[0]
    if cmd == "record":
        if len(argv) < 2:
            print("用法: tracker.py record <match_id>  (或由 analyze.py --track 自动)")
            return 1
        records = load()
        hit = [r for r in records if r["id"] == argv[1]]
        print(json.dumps(hit, ensure_ascii=False, indent=2) if hit else "未找到记录")
        return 0
    if cmd == "settle":
        if len(argv) < 4:
            print("用法: tracker.py settle <match_id> <hg> <ag>")
            return 1
        s = settle(argv[1], int(argv[2]), int(argv[3]))
        if s is None:
            print("未找到 open 状态记录")
            return 1
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return 0
    if cmd == "report":
        print(json.dumps(report(), ensure_ascii=False, indent=2))
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
