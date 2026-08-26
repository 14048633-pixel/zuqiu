"""结算 v2 逐注账本 CLI
=================================================
用法:
  python settle_live.py "金浦 vs 忠南 1-1" "温州 vs 贵州 2-0"

规则(与回测一致): 只结算账本里已推荐的"大小球2.5 小球/大球"注;
2.5 为半球盘(无走水), 整数盘(如2.0)总进球=盘口时走水。
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)  # 足球竞猜模型训练/
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src", "features"))

from predict_v2_bridge import settle_bets, LEDGER_PATH  # noqa: E402


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    score_map = {}
    for arg in sys.argv[1:]:
        if " " not in arg:
            print(f"跳过无效参数(需 '比赛 比分'): {arg}")
            continue
        *match_parts, score = arg.rsplit(" ", 1)
        score_map[" ".join(match_parts)] = score
    settled = settle_bets(score_map)
    # 线上实时校准 (SOP第三类): 每场赛后自动更新球队滚动攻防强度
    try:
        sys.path.insert(0, os.path.join(PROJECT_ROOT, "src", "models"))
        from team_strength import update_from_result
        from datetime import date
        _today = date.today().isoformat()
        for mkey, score in score_map.items():
            if " vs " not in mkey or "-" not in score:
                continue
            _h, _a = [x.strip() for x in mkey.split(" vs ", 1)]
            try:
                _hg, _ag = (int(x) for x in score.split("-", 1))
            except Exception:
                continue
            update_from_result(_h, _a, _hg, _ag, _today, 2.6)
        print("  ✅ 已更新 team_strength.json 滚动攻防 (线上实时校准)")
    except Exception as e:
        print(f"  ⚠️ team_strength 更新跳过: {e}")
    if not settled:
        print(f"没有可结算的待定注(账本: {LEDGER_PATH})")
        sys.exit(0)
    stake = 1.0  # 平注口径
    total_pnl = 0.0
    print(f"结算 {len(settled)} 注:")
    for e in settled:
        if e["status"] == "win":
            pnl = stake * (e.get("odds", 0) - 1)
        elif e["status"] == "push":
            pnl = 0.0
        else:
            pnl = -stake
        total_pnl += pnl
        print(f"  {e['match']:<22} {e['side']:<10} 比分{e.get('score'):>5} "
              f"赔率{e.get('odds',0):.2f} -> {e['status']:<5} P&L={pnl:+.2f}")
    print(f"\n平注口径合计 P&L: {total_pnl:+.2f} (1注=1本金)")
    print(f"账本: {LEDGER_PATH}")


if __name__ == "__main__":
    main()
