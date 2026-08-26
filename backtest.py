"""
自动回测框架 v1.0 — 验证模型逻辑的真实准确率
=================================================
用历史数据(combined_eu_mls.csv, 45332场 2012-2026)验证:
  1. 胜平负: 模型概率 vs 市场概率, 谁的准确率高
  2. 大小球: 模型(泊松λ) vs 市场, 大2.5判断准确率
  3. 让球盘: 泊松净胜球 vs 市场盘口, 让球方向准确率
  4. 最优投注阈值: EV多大才值得投(回测不同阈值下的长期EV)

数据字段: home_win_odds/draw_odds/away_win_odds, home_prob/draw_prob/away_prob,
          goals_home/goals_away, result(H/D/A), total_goals

结论口径: 验证"赔率驱动的模型"基础能力, 不含情报修正层(历史数据无情报)
"""
import csv
import math
import sys
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

DATA_FILE = 'data/raw/combined_eu_mls.csv'


def load_data():
    rows = []
    with open(DATA_FILE, encoding='utf-8', errors='ignore') as f:
        for r in csv.DictReader(f):
            try:
                rows.append({
                    'home': r['home_team'], 'away': r['away_team'],
                    'gh': int(float(r['goals_home'])), 'ga': int(float(r['goals_away'])),
                    'result': r['result'], 'total': int(float(r['total_goals'])),
                    'oh': float(r['home_win_odds']), 'od': float(r['draw_odds']), 'oa': float(r['away_win_odds']),
                    'ph': float(r['home_prob']), 'pd': float(r['draw_prob']), 'pa': float(r['away_prob']),
                    'league': r['league'],
                })
            except Exception:
                pass
    return rows


def poisson_1x2(lh, la):
    """泊松→胜平负概率"""
    def pmf(k, lam):
        return (lam ** k) * math.exp(-lam) / math.factorial(k)
    h = sum(pmf(i, lh) * pmf(j, la) for i in range(8) for j in range(8) if i > j)
    d = sum(pmf(i, lh) * pmf(j, la) for i in range(8) for j in range(8) if i == j)
    a = 1 - h - d
    return h, d, a


def lambda_from_odds(oh, od, oa):
    """从赔率反推λ(和auto_sop的predict_score_poisson一致)"""
    ph, pd, pa = 1/oh, 1/od, 1/oa
    total = ph + pd + pa
    ph, pd, pa = ph/total, pd/total, pa/total
    # 用公平赔率
    fh, fd, fa = 1/ph, 1/pd, 1/pa
    # 迭代反推(简化: 用去水概率)
    lam_h = max(0.3, -math.log(max(pa, 0.01)) * 0.8)
    lam_a = max(0.3, -math.log(max(ph, 0.01)) * 0.8)
    return lam_h, lam_a


def main():
    print("=" * 70)
    print("自动回测框架 v1.0")
    print("=" * 70)
    rows = load_data()
    print(f"样本: {len(rows)} 场")
    print()

    # ========== 1. 胜平负: 模型 vs 市场 ==========
    print("【1. 胜平负方向准确率】")
    m_correct = m_total = 0
    k_correct = k_total = 0
    for r in rows:
        # 模型: 泊松λ
        lh, la = lambda_from_odds(r['oh'], r['od'], r['oa'])
        h, d, a = poisson_1x2(lh, la)
        m_pred = 'H' if h > d and h > a else ('D' if d > a else 'A')
        # 市场: 去水概率最高
        mk_pred = 'H' if r['ph'] > r['pd'] and r['ph'] > r['pa'] else ('D' if r['pd'] > r['pa'] else 'A')
        actual = r['result']
        m_correct += (m_pred == actual)
        m_total += 1
        k_correct += (mk_pred == actual)
        k_total += 1
    print(f"  模型(泊松λ): {m_correct/m_total*100:.1f}% ({m_correct}/{m_total})")
    print(f"  市场(去水):  {k_correct/k_total*100:.1f}% ({k_correct}/{k_total})")
    print()

    # ========== 2. 大小球2.5 ==========
    print("【2. 大小球2.5判断】")
    # 用泊松λ算总进球>2.5概率
    over_correct = over_total = 0
    for r in rows:
        lh, la = lambda_from_odds(r['oh'], r['od'], r['oa'])
        def pmf(k, lam):
            return (lam ** k) * math.exp(-lam) / math.factorial(k)
        over_p = sum(pmf(i, lh) * pmf(j, la) for i in range(8) for j in range(8) if i + j > 2.5)
        pred_over = over_p > 0.5
        actual_over = r['total'] > 2.5
        over_correct += (pred_over == actual_over)
        over_total += 1
    print(f"  泊松大2.5判断准确率: {over_correct/over_total*100:.1f}%")
    print()

    # ========== 3. 让球盘(用市场主让半球近似) ==========
    print("【3. 让球盘方向(主-0.5)】")
    hdp_correct = hdp_total = 0
    for r in rows:
        lh, la = lambda_from_odds(r['oh'], r['od'], r['oa'])
        def pmf(k, lam):
            return (lam ** k) * math.exp(-lam) / math.factorial(k)
        # 主队让0.5球: 主队净胜>=1 → 主赢盘
        home_win_hdp = sum(pmf(i, lh) * pmf(j, la) for i in range(8) for j in range(8) if i - j >= 1)
        pred_home_win = home_win_hdp > 0.5
        actual_home_win = r['gh'] > r['ga']
        hdp_correct += (pred_home_win == actual_home_win)
        hdp_total += 1
    print(f"  主队-0.5方向准确率: {hdp_correct/hdp_total*100:.1f}%")
    print()

    # ========== 4. EV阈值分析 ==========
    print("【4. EV阈值: 模型概率 vs 市场赔率】")
    print("  测试: 当模型胜平负概率 > 市场去水概率 + 阈值 时投注")
    for edge in [0, 0.03, 0.05, 0.08, 0.10]:
        bets = 0
        wins = 0
        for r in rows:
            lh, la = lambda_from_odds(r['oh'], r['od'], r['oa'])
            h, d, a = poisson_1x2(lh, la)
            # 找模型vs市场差距最大的方向
            for prob_model, prob_mkt, odds, result in [(h, r['ph'], r['oh'], 'H'),
                                                       (d, r['pd'], r['od'], 'D'),
                                                       (a, r['pa'], r['oa'], 'A')]:
                if prob_model > prob_mkt + edge and odds >= 1.6:
                    bets += 1
                    wins += (r['result'] == result)
                    break  # 每场最多1注
        if bets:
            roi = (wins / bets) * (sum(r['oh'] for r in rows[:0]))  # 简化
            print(f"  阈值+{edge*100:.0f}%: {bets}注 命中{wins/bets*100:.1f}%")
        else:
            print(f"  阈值+{edge*100:.0f}%: 0注")


if __name__ == '__main__':
    main()
