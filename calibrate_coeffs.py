"""月度校准流水线 CLI — 离线拟合特征修正系数 + 联赛基准 + 概率后校准 (SOP 第二/四类)
================================================================
用法:
  python calibrate_coeffs.py                          # 五大联赛快速校准(不写盘)
  python calibrate_coeffs.py --leagues 英超 西甲      # 指定联赛
  python calibrate_coeffs.py --write                  # 校验通过后写 calibration.json
  python calibrate_coeffs.py --write --verify         # 写盘后自动跑回归测试
  python calibrate_coeffs.py --leagues 英超 --quick

铁律:
  - 严格时序隔离 / 滚动原点 CV / 分联赛独立 / 系数硬钳位 / 过拟合红线
  - 拟合系数触界或过拟合 → 不采用极端值, 回退默认系数 (coef_status=BOUNDARY_DEFAULT/OVERFIT_DEFAULT)
  - 概率后校准 (Dixon-Coles rho + ShrinkPower + 分箱表) 仅在校准改善测试段 LogLoss 时启用
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src", "models"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

sys.stdout.reconfigure(encoding="utf-8")

from calibrate import (load_matches, compute_league_baseline, calibrate_league,
                       write_calibration, load_prob_calib, MAJOR_LEAGUES, OVFIT_GAP_LIMIT)


def main():
    ap = argparse.ArgumentParser(description="月度校准流水线 (泊松系数 + 概率后校准)")
    ap.add_argument("--leagues", nargs="*", default=MAJOR_LEAGUES, help="待校准联赛")
    ap.add_argument("--write", action="store_true", help="校验通过后写入 calibration.json")
    ap.add_argument("--quick", action="store_true", help="快速模式 (减少滚动窗口)")
    ap.add_argument("--verify", action="store_true", help="写盘后自动运行回归测试")
    args = ap.parse_args()

    print("=" * 70)
    print("  月度校准流水线: 时序隔离 + 滚动原点CV + 系数钳位 + OOS校验 + 概率后校准")
    print("=" * 70)
    df = load_matches(leagues=args.leagues)
    if df.empty:
        print("  ❌ 未加载到历史数据, 请检查 data/raw/football_data/*.csv")
        sys.exit(1)
    print(f"  历史数据: {len(df):,} 场正赛 ({sorted(df['league_name'].unique())})\n")

    all_ok = True
    for league in args.leagues:
        print("-" * 60)
        coefs, report = calibrate_league(df, league, quick=args.quick)
        if coefs is None:
            print(f"  {league}: ⚠️ {report.get('status')} (样本 {report.get('matches', 0)})")
            all_ok = False
            continue
        b = report["baseline"]
        print(f"  {league}: {report['matches']} 场 | league_avg={b['league_avg']} "
              f"avg_atk={b['avg_atk']} 主{b['home_avg']}/客{b['away_avg']}")
        c = report["coefs"]
        print(f"    拟合系数: 主{c['home_coef']:.2f} 客{c['away_coef']:.2f} 疲劳{c['fatigue_coef']:.2f} "
              f"| CV LogLoss={report['cv_logloss']}")
        o = report["oos"]
        flag = "✅" if not o["overfit_flag"] else "❌"
        print(f"    OOS(校准后EV): train_LL={o['train_logloss']} test_LL={o['test_logloss']} "
              f"gap={o['gap']}(红线{OVFIT_GAP_LIMIT}) EV={o['ev']} 注数={o['n_bets']} {flag}")
        if o.get("ev_suspicious"):
            print(f"    ⚠️ EV={o['ev']} > 0.5 疑似过高 (单赛季样本外 EV 波动大, 概率可能过度自信)")
            print(f"       提示: 该 EV 需仿真资金 300+ 场验证后才可信, 严禁直接按此 EV 放大仓位")
        if o["overfit_flag"]:
            all_ok = False
            print(f"    ⚠️ 过拟合/无预测价值: {o.get('reason')} → 拒绝覆盖生产系数")
        st = report["stored_coefs"]
        print(f"    落地系数: 主{st['home_coef']:.2f} 客{st['away_coef']:.2f} 疲劳{st['fatigue_coef']:.2f} "
              f"状态={report['coef_status']}")
        if report["boundary_hits"]:
            print(f"    ⚠️ 系数触界(值域内LogLoss最优点在边界): {', '.join(report['boundary_hits'])}"
                  f" → 按铁律不采用极端值, 保留默认")
        pc = report.get("prob_calib")
        if pc:
            evc = pc["ev_calib"]
            en = "✅启用" if pc["enabled"] else "⏭未改善不启用"
            print(f"    概率后校准: rho={pc['rho']} shrink={pc['shrink_power']} "
                  f"测试LL {pc['test_logloss_raw']}→{pc['test_logloss_calib']} "
                  f"校准后EV={evc['mean_ev']} (n={evc['n_bets']}) {en}")
        else:
            print("    ⏭ 概率后校准: 样本不足, 未拟合")

        if args.write:
            meta = {
                "status": "OK",
                "matches": report["matches"],
                "baseline": b,
                "cv_logloss": report["cv_logloss"],
                "oos": o,
                "coef_status": report["coef_status"],
                "fitted_at": report["fitted_at"],
                "note": "月度校准: 修改任何系数/校准参数后必须重跑 regression_test.py",
            }
            write_calibration(league, (st['home_coef'], st['away_coef'], st['fatigue_coef']),
                              meta, prob_calib=pc, coef_status=report["coef_status"])
            print(f"    💾 已写入 strategy_data/calibration.json (系数{report['coef_status']} + 概率校准{'启用' if (pc and pc['enabled']) else '未启用'})")

    print("=" * 70)
    if args.verify:
        import subprocess
        r = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "regression_test.py")])
        if r.returncode != 0:
            print("  ❌ 回归测试未通过, 校准结果需人工复核")
            sys.exit(1)
        print("  ✅ 回归测试全绿")
    print(f"  校准完成: {'全部通过' if all_ok else '存在告警, 请检查上方明细'}")


if __name__ == "__main__":
    main()
