"""单场预测 CLI（复用 predict_api）：
  python run_predict.py "英超" "曼城" "阿森纳" 2026-08-15 \
      --odds 1.75 3.60 4.50 --ou-over 1.90 --ou-under 1.92 \
      --ah -0.5 --ah-home 2.05 --ah-away 1.80
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.predict_api import feature_row_from_dataset, score_feature_row
from src.live_odds import load_snapshots, movement_table, match_event, judge_text

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser(description="单场预测")
    ap.add_argument("league")
    ap.add_argument("home")
    ap.add_argument("away")
    ap.add_argument("date")
    ap.add_argument("--config", default=os.path.join(HERE, "config.yaml"))
    ap.add_argument("--odds", nargs=3, type=float, metavar=("H", "D", "A"))
    ap.add_argument("--ou-over", type=float)
    ap.add_argument("--ou-under", type=float)
    ap.add_argument("--ou-line", type=float, default=2.5)
    ap.add_argument("--ah", type=float, help="主队让球盘（正=主受让）")
    ap.add_argument("--ah-home", type=float)
    ap.add_argument("--ah-away", type=float)
    ap.add_argument("--live-odds", nargs="?", const="auto", default=None,
                    help="临场赔率快照CSV(默认 auto=output/odds_snapshots/snapshots.csv)")
    args = ap.parse_args()

    row = feature_row_from_dataset(args.league, args.home, args.away, args.date)
    ou = (args.ou_over, args.ou_under) if (args.ou_over and args.ou_under) else None
    ah = (args.ah, args.ah_home, args.ah_away) if (args.ah is not None and args.ah_home) else None
    res = score_feature_row(row, odds=args.odds, ou_line=args.ou_line, ou=ou, ah=ah)

    # 临场赔率: 初盘->临场变化(策略层, 禁入训练特征)
    odds_flow = None
    snap_path = None
    if args.live_odds == 'auto' or args.live_odds is None:
        _p = os.path.join(HERE, 'output', 'odds_snapshots', 'snapshots.csv')
        if os.path.exists(_p):
            snap_path = _p
    elif args.live_odds:
        snap_path = args.live_odds
    if snap_path:
        mv = movement_table(load_snapshots(snap_path))
        rec = match_event(mv, args.league, args.home, args.away)
        if rec is not None:
            odds_flow = {
                'n_snapshots': int(rec.get('n_snapshots') or 0),
                'hours_to_kickoff_last': rec.get('hours_to_kickoff_last'),
                'judge': judge_text(rec),
            }
            for col in ('pinnacle_h2h_home_first', 'pinnacle_h2h_home_last', 'pinnacle_h2h_home_move',
                        'pinnacle_h2h_away_first', 'pinnacle_h2h_away_last', 'pinnacle_h2h_away_move',
                        'pinnacle_totals_over@2.5_first', 'pinnacle_totals_over@2.5_last',
                        'pinnacle_totals_over@2.5_move', 'pinnacle_totals_under@2.5_first',
                        'pinnacle_totals_under@2.5_last', 'pinnacle_totals_under@2.5_move'):
                if col in rec.index:
                    odds_flow[col] = float(rec[col])
            if res.get('pre') is not None:
                res['pre']['odds_flow'] = odds_flow

    print("=" * 64)
    print(f"  {args.home} vs {args.away}  ({args.league}, {args.date})")
    print("=" * 64)
    print(f"  泊松λ: 主 {res['lam_h']:.2f}  客 {res['lam_a']:.2f}  预期总进球 {res['lam_h'] + res['lam_a']:.2f}")
    print(f"  [1X2] 模型: 主 {res['p_home']:.1%} 平 {res['p_draw']:.1%} 客 {res['p_away']:.1%}")
    print(f"  [大小] 模型大{res['ou_line']}: {res['p_over']:.1%}")

    pre = res.get("pre")
    if pre:
        fh, fa, hh = pre["form_home"], pre["form_away"], pre["h2h"]
        print(f"  [赛前] 联赛场均 主{pre['league_avg_home']:.2f}/客{pre['league_avg_away']:.2f} "
              f"进球强弱系数{pre['league_scoring_idx']:.2f} 联赛Elo{pre['league_strength']:.0f}")
        if fh.get("gf10"):
            print(f"  主队近10: 场均进{fh['gf10'] / 10:.2f} 失{fh['ga10'] / 10:.2f} 积分{fh['pts10']:.0f} "
                  f"(主场进{fh['gf_home10'] / 10:.2f}/失{fh['ga_home10'] / 10:.2f})")
        else:
            print("  主队近10: 无历史数据(样本不足)")
        if fa.get("gf10"):
            print(f"  客队近10: 场均进{fa['gf10'] / 10:.2f} 失{fa['ga10'] / 10:.2f} 积分{fa['pts10']:.0f} "
                  f"(客场进{fa['gf_away10'] / 10:.2f}/失{fa['ga_away10'] / 10:.2f})")
        else:
            print("  客队近10: 无历史数据(样本不足)")
        if hh["n5"]:
            print(f"  交锋近{hh['n5']}场: 场均总{hh['total5']:.2f} 主胜{hh['h_win5']:.0%} "
                  f"客胜{hh['a_win5']:.0%} 平{hh['draw5']:.0%}")
        else:
            print("  交锋: 无历史交手记录")
    if odds_flow:
        h2k = odds_flow.get('hours_to_kickoff_last')
        h2k_txt = f"{h2k:.1f}h" if h2k is not None else "?"
        print(f"  [临场] 快照x{odds_flow['n_snapshots']} 距开赛{h2k_txt}: {odds_flow['judge']}")
    print()
    print("  候选投注(模型 vs 市场):")
    for b in res["bets"]:
        print(f"    {b['market']:<4} {b['side']:<10} 模型{b['prob']:.1%} 市场{b['market_prob']:.1%} "
              f"边际{b['edge']:+.1%} EV={b['ev']:+.1%} Kelly={b['kelly']:.1%}")
    print("\n  提示: 回测显示仅「大小球2.5小球 边际>=5%」为正期望；1X2/亚盘/大球建议不投。")


if __name__ == "__main__":
    main()
